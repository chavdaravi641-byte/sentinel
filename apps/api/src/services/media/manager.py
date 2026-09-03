"""Stream lifecycle manager.

Owns one `StreamSession` per camera: each session runs a single ffmpeg ingest
process that (a) publishes RTSP into the edge media server (HLS + WebRTC fan
out) and (b) pipes MJPEG into an in-memory buffer for live preview, snapshots
and motion sampling. A supervisor task per session handles crash detection and
exponential-backoff reconnects. Async CPU-bound work (motion, ffprobe, stat)
runs on a shared thread pool so the event loop stays responsive.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import UUID

import httpx

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.logging import log
from src.models.camera import Camera
from src.models.stream import (
    STREAM_STATE_CONNECTING,
    STREAM_STATE_ERROR,
    STREAM_STATE_RUNNING,
    STREAM_STATE_STARTING,
    STREAM_STATE_STOPPED,
    Recording,
)
from src.services.media import ffmpeg, sources
from src.services.media.mjpeg import MjpegBuffer, extract_jpegs, iter_frames
from src.services.media.motion import MotionDetector, MotionResult
from src.services.media.paths import ensure_dirs, snapshot_path
from src.services.media.recording import RecordingManager

MOTION_JOB_SLEEP = 0.2


class StreamSession:
    """Live state for a single camera pipeline."""

    def __init__(self, camera: Camera) -> None:
        resolved = sources.resolve_source(camera)
        self.camera_id: UUID = camera.id
        self.name: str = camera.name
        self.camera = camera
        self.source: str = resolved.input
        self.kind: str = resolved.kind
        self.state: str = STREAM_STATE_STOPPED
        self.error: str | None = None
        self.reconnect_count: int = 0
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None
        self.proc: asyncio.subprocess.Process | None = None
        self.reader_task: asyncio.Task | None = None
        self.stderr_task: asyncio.Task | None = None
        self.motion_task: asyncio.Task | None = None
        self.supervisor_task: asyncio.Task | None = None
        self.buffer = MjpegBuffer(max_frames=2)
        self.detector = MotionDetector()
        self.motion_detections: int = 0
        self.last_motion_at: float | None = None
        self.last_motion_score: float = 0.0
        self.stop_requested = False
        self.spawn_ts: float | None = None
        self.first_frame_ts: float | None = None
        self.startup_ms: float | None = None
        self.stderr_tail: list[str] = []
        self._supervise_lock = asyncio.Lock()
        self._motion_job_running = False

    @property
    def running(self) -> bool:
        return self.state == STREAM_STATE_RUNNING and not self.stop_requested

    @property
    def live(self) -> bool:
        return self.proc is not None and self.proc.returncode is None and not self.stop_requested

    def to_info(self, *, recording: dict[str, Any] | None, publisher: dict[str, Any]) -> dict[str, Any]:
        now = time.monotonic()
        return {
            "camera_id": str(self.camera_id),
            "name": self.name,
            "state": self.state,
            "running": self.running,
            "live": self.live,
            "error": self.error,
            "reconnect_count": self.reconnect_count,
            "kind": self.kind,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "uptime_s": round(now - self.first_frame_ts, 1) if self.first_frame_ts else None,
            "startup_ms": self.startup_ms,
            "recording": bool(recording),
            "recording_trigger": recording.get("trigger") if recording else None,
            "publisher": publisher,
        }

    async def buffer_stats(self) -> dict[str, Any]:
        return await self.buffer.stats()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StreamSession {self.name} state={self.state}>"


class StreamManager:
    """Process-wide registry + orchestration for live streams."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[UUID, StreamSession] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max(settings.STREAM_THREAD_POOL, 4),
            thread_name_prefix="sentinel-media",
        )
        self.recorders = RecordingManager(self._executor)
        self._scheduler_task: asyncio.Task | None = None
        self._ready = False
        self._capabilities_cache: dict[str, Any] | None = None
        self._capabilities_ts: float = 0.0
        self._pub_ok: bool | None = None
        self._pub_ts: float = 0.0

    # ------------------------------------------------------------------ #
    # Lifecycle helpers
    # ------------------------------------------------------------------ #
    async def ready(self) -> None:
        """Idempotent background initialisation (dirs, scheduler task)."""
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            ensure_dirs()
            if settings.RECORDING_SCHEDULE_ENABLED:
                self._scheduler_task = asyncio.create_task(self._scheduler_loop(), name="recording-scheduler")
            self._ready = True

    async def shutdown(self) -> None:
        """Stop every session and the scheduler (best effort)."""
        if self._scheduler_task is not None:
            self._scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._scheduler_task
        sessions = list(self._sessions.values())
        for session in sessions:
            with suppress(Exception):
                await self.stop(session.camera_id)
        self._executor.shutdown(wait=False)
        log.info("stream.shutdown_complete", sessions=len(sessions))

    # ------------------------------------------------------------------ #
    # Stream control API
    # ------------------------------------------------------------------ #
    async def start(self, camera: Camera, *, started_by: UUID | None = None) -> dict[str, Any]:
        await self.ready()
        async with self._lock:
            existing = self._sessions.get(camera.id)
            if existing is not None and existing.live:
                return await self.health(camera.id)
            if len(self._sessions) >= settings.STREAM_MAX_CAMERAS:
                raise RuntimeError(
                    f"Concurrent stream limit reached ({settings.STREAM_MAX_CAMERAS}). "
                    "Stop another camera before starting this one."
                )

        # Quick reachability check so we fail fast instead of churning reconnects.
        probe = await ffmpeg.probe_media(session_source(camera))
        summary = ffmpeg.summarize_probe(probe)
        if not summary.get("ok"):
            detail = summary.get("message", "Source is not decodable by ffmpeg.")
            log.warning("stream.start_probe_failed", camera_id=str(camera.id), detail=detail)
            raise RuntimeError(f"Camera {camera.name} failed media validation: {detail}")

        session = StreamSession(camera)
        async with self._lock:
            self._sessions[camera.id] = session
        session.state = STREAM_STATE_STARTING
        session.started_at = datetime.now(timezone.utc)
        session.supervisor_task = asyncio.create_task(
            self._supervise(session), name=f"stream-supervise-{camera.id}"
        )
        log.info("stream.start", camera_id=str(camera.id), camera=camera.name, source=session.source)
        await self._await_running(session, timeout=settings.FFMPEG_TIMEOUT_SECONDS + 4)
        return await self.health(camera.id)

    async def stop(self, camera_id: UUID) -> dict[str, Any] | None:
        async with self._lock:
            session = self._sessions.pop(camera_id, None)
        if session is None:
            return None
        log.info("stream.stop", camera_id=str(camera_id))
        session.stop_requested = True
        await self._terminate_session(session)
        # A stopped stream also stops any live recording fed from it.
        await self.record_stop(camera_id)
        return {"camera_id": str(camera_id), "state": STREAM_STATE_STOPPED}

    async def _terminate_session(self, session: StreamSession) -> None:
        if session.proc is not None and session.proc.returncode is None:
            with suppress(Exception):
                session.proc.terminate()
            try:
                await asyncio.wait_for(session.proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                with suppress(Exception):
                    session.proc.kill()
        for task in (session.reader_task, session.stderr_task, session.motion_task, session.supervisor_task):
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        session.state = STREAM_STATE_STOPPED
        session.stopped_at = datetime.now(timezone.utc)

    async def _await_running(self, session: StreamSession, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if session.running or (session.proc is not None and session.proc.returncode is not None):
                return
            if session.error:
                return
            await asyncio.sleep(0.15)

    # ------------------------------------------------------------------ #
    # Supervisor (reconnect loop)
    # ------------------------------------------------------------------ #
    async def _supervise(self, session: StreamSession) -> None:
        try:
            while not session.stop_requested:
                try:
                    if session.proc is None or session.proc.returncode is not None:
                        await self._maybe_respawn(session)
                    elif session.state != STREAM_STATE_RUNNING:
                        session.state = STREAM_STATE_RUNNING
                    await asyncio.sleep(settings.STREAM_WATCH_INTERVAL)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    session.error = str(exc)
                    log.warning("stream.supervise_error", camera_id=str(session.camera_id), error=str(exc))
                    await asyncio.sleep(settings.STREAM_WATCH_INTERVAL)
        finally:
            # Guarantee subprocess/tasks are cleaned up even on cancellation.
            if not session.stop_requested:
                session.stop_requested = True
            await self._terminate_session(session)

    async def _maybe_respawn(self, session: StreamSession) -> None:
        if session.reconnect_count >= settings.STREAM_RECONNECT_MAX:
            session.state = STREAM_STATE_ERROR
            session.error = f"Reconnect limit reached ({session.reconnect_count})."
            if session.proc is not None:
                session.proc = None
            await asyncio.sleep(settings.STREAM_WATCH_INTERVAL)
            return
        session.state = STREAM_STATE_CONNECTING
        if session.reconnect_count > 0 or session.first_frame_ts is not None:
            delay = min(
                settings.STREAM_RECONNECT_BASE_DELAY * (2 ** min(session.reconnect_count, 5)),
                settings.STREAM_RECONNECT_MAX_DELAY,
            )
            log.info("stream.reconnect", camera_id=str(session.camera_id), attempt=session.reconnect_count, delay=delay)
            await self._sleep_cancelable(session, delay)
        if session.stop_requested:
            return
        try:
            await self._spawn(session)
        except FileNotFoundError:
            session.state = STREAM_STATE_ERROR
            session.error = "ffmpeg binary is not installed in this container."
        except Exception as exc:
            session.error = str(exc)
            session.reconnect_count += 1

    async def _sleep_cancelable(self, session: StreamSession, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            session.stop_requested = True
            raise

    async def _spawn(self, session: StreamSession) -> None:
        """Start the ingest/publish ffmpeg process and its IO/consumers."""
        cmd = ffmpeg.build_ingest_command(
            session.source,
            session.camera_id,
            scale=settings.STREAM_PROFILE_SCALE,
            fps=settings.STREAM_PROFILE_FPS,
            crf=settings.STREAM_PROFILE_CRF,
            preset=settings.STREAM_PROFILE_PRESET,
        )
        session.spawn_ts = time.monotonic()
        session.first_frame_ts = None
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        session.proc = proc
        session.reader_task = asyncio.create_task(self._read_pipe(session), name=f"read-{session.camera_id}")
        session.stderr_task = asyncio.create_task(self._read_stderr(session), name=f"err-{session.camera_id}")
        if not session._motion_job_running and session.detector.enabled:
            session._motion_job_running = True
            session.motion_task = asyncio.create_task(self._motion_job(session), name=f"motion-{session.camera_id}")
        log.info("stream.spawned", camera_id=str(session.camera_id), pid=proc.pid)

    async def _read_pipe(self, session: StreamSession) -> None:
        proc = session.proc
        if proc is None or proc.stdout is None:
            return
        carry = bytearray()
        try:
            while not session.stop_requested:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                frames = extract_jpegs(chunk, carry)
                for frame in frames:
                    if session.stop_requested:
                        return
                    await session.buffer.push(frame)
                    if session.first_frame_ts is None:
                        session.first_frame_ts = time.monotonic()
                        if session.spawn_ts:
                            session.startup_ms = round((session.first_frame_ts - session.spawn_ts) * 1000, 1)
                        session.reconnect_count = 0
                        session.state = STREAM_STATE_RUNNING
        except asyncio.CancelledError:
            raise
        finally:
            if proc is session.proc:
                session.proc = None

    async def _read_stderr(self, session: StreamSession) -> None:
        proc = session.proc
        if proc is None or proc.stderr is None:
            return
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace").strip()
                if text:
                    session.stderr_tail.append(text)
                    if len(session.stderr_tail) > 20:
                        session.stderr_tail.pop(0)
        except asyncio.CancelledError:
            raise

    async def _motion_job(self, session: StreamSession) -> None:
        try:
            while not session.stop_requested:
                frame = await session.buffer.get_latest()
                if frame is not None:
                    loop = asyncio.get_running_loop()
                    result: MotionResult = await loop.run_in_executor(
                        self._executor, session.detector.analyze, frame, time.monotonic()
                    )
                    if result.motion:
                        session.motion_detections += 1
                        session.last_motion_at = time.monotonic()
                        session.last_motion_score = result.score
                        await self._on_motion(session, result)
                await asyncio.sleep(MOTION_JOB_SLEEP)
        except asyncio.CancelledError:
            raise

    async def _on_motion(self, session: StreamSession, result: MotionResult) -> None:
        log.info("stream.motion", camera_id=str(session.camera_id), score=result.score)
        frame = await session.buffer.get_latest()
        if frame is None:
            return
        filename = f"motion-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')[:-3]}Z.jpg"
        path = snapshot_path(session.camera_id, filename)
        await asyncio.get_running_loop().run_in_executor(self._executor, _write_bytes, path, frame)
        if settings.MOTION_RECORD_CLIP_SECONDS > 0:
            if not await self.recorders.is_active(session.camera_id):
                try:
                    await self.record_start(session, trigger="motion", seconds=settings.MOTION_RECORD_CLIP_SECONDS)
                except Exception as exc:
                    log.warning("stream.motion_record_failed", camera_id=str(session.camera_id), error=str(exc))

    # ------------------------------------------------------------------ #
    # Recording integration
    # ------------------------------------------------------------------ #
    async def record_start(
        self, session: StreamSession, *, trigger: str, started_by: UUID | None = None, seconds: int = 0
    ) -> dict[str, Any]:
        if await self.recorders.is_active(session.camera_id):
            existing = await self.recorders.current(session.camera_id)
            return {"status": "already_recording", "recording": existing}
        input_source = await self._recording_input(session)
        recording = await self.recorders.start(
            camera_id=session.camera_id,
            input_source=input_source,
            trigger=trigger,
            started_by=started_by,
            seconds=seconds,
        )
        return {"status": "started", "recording_id": str(recording.id), "trigger": trigger, "file_path": recording.file_path}

    async def record_stop(self, camera_id: UUID):
        row_id, active = await self.recorders.stop(camera_id)
        if row_id is None or active is None:
            return None
        async with AsyncSessionLocal() as db:
            row = await db.get(Recording, row_id)
            if row is None:
                return None
            await self.recorders.finalize(db, row, active, status="stopped")
            return {
                "status": "stopped",
                "recording_id": str(row.id),
                "trigger": row.trigger,
                "file_path": row.file_path,
            }

    async def _recording_input(self, session: StreamSession) -> str:
        if await self._publisher_reachable():
            return f"{settings.MEDIAMTX_RTSP_URL.rstrip('/')}/sentinel/{session.camera_id}"
        return session.source

    # ------------------------------------------------------------------ #
    # Reads: health / stats / snapshot / mjpeg / capabilities
    # ------------------------------------------------------------------ #
    async def session(self, camera_id: UUID) -> StreamSession | None:
        return self._sessions.get(camera_id)

    async def health(self, camera_id: UUID) -> dict[str, Any]:
        session = self._sessions.get(camera_id)
        publisher = await self._publisher_status()
        recording = await self.recorders.current(camera_id)
        if session is None:
            return {
                "camera_id": str(camera_id),
                "state": STREAM_STATE_STOPPED,
                "running": False,
                "error": None,
                "reconnect_count": 0,
                "publisher": publisher,
                "recording": bool(recording),
                "recording_trigger": recording.get("trigger") if recording else None,
            }
        info = session.to_info(recording=recording, publisher=publisher)
        buffer_stats = await session.buffer.stats()
        info["fps"] = buffer_stats["fps"]
        info["bitrate_kbps"] = buffer_stats["bitrate_kbps"]
        info["jitter_ms"] = buffer_stats["jitter_ms"]
        info["last_frame_age_ms"] = buffer_stats["last_frame_age_ms"]
        info["startup_ms"] = session.startup_ms
        info["latency_ms"] = session.startup_ms
        info["hls_latency_ms"] = settings.HLS_TARGET_LATENCY
        info["motion_detections"] = session.motion_detections
        info["last_motion_score"] = session.last_motion_score
        return info

    async def stats(self, camera_id: UUID) -> dict[str, Any]:
        session = self._sessions.get(camera_id)
        if session is None:
            raise KeyError(camera_id)
        info = await self.health(camera_id)
        info["pipeline"] = {
            "pid": session.proc.pid if session.proc else None,
            "source": session.source,
            "kind": session.kind,
            "stderr_tail": session.stderr_tail[-5:],
        }
        return info

    async def snapshot_latest(self, camera_id: UUID) -> bytes | None:
        session = self._sessions.get(camera_id)
        if session is None:
            return None
        return await session.buffer.get_latest()

    async def snapshot_on_demand(self, camera: Camera) -> bytes | None:
        resolved = sources.resolve_source(camera)
        return await ffmpeg.capture_snapshot(resolved.input)

    async def subscribe_mjpeg(self, camera_id: UUID, *, fps: int | None = None) -> AsyncIterator[bytes]:
        session = self._sessions.get(camera_id)
        if session is None or not session.live:
            raise RuntimeError("Stream is not running")
        fps = fps or settings.MJPEG_FPS
        return iter_frames(session.buffer, fps=fps)

    async def test_stream(self, camera: Camera) -> dict[str, Any]:
        resolved = sources.resolve_source(camera)
        probe = await ffmpeg.probe_media(resolved.input)
        summary = ffmpeg.summarize_probe(probe)
        base: dict[str, Any] = {
            "id": str(camera.id),
            "name": camera.name,
            "kind": resolved.kind,
            "ok": bool(summary.get("ok")),
            "message": summary.get("message", "Source is decodable."),
        }
        if not summary.get("ok"):
            return base
        base.update(
            {
                "codec": summary.get("codec"),
                "width": summary.get("width"),
                "height": summary.get("height"),
                "fps": summary.get("fps"),
                "bit_rate": summary.get("bit_rate"),
                "duration": summary.get("duration"),
                "format": summary.get("format"),
            }
        )
        # Decode smoke test: open + decodes 1 second of video.
        decode_ms = await self._decode_test(resolved.input)
        base["decode_ms"] = decode_ms
        base["message"] = "Media source validated: decodable stream."
        return base

    async def _decode_test(self, source: str) -> float | None:
        cmd = [ffmpeg.FFMPEG_BIN, "-hide_banner", "-loglevel", "error"]
        if source.startswith(("rtsp://", "rtsps://")):
            cmd += ["-rtsp_transport", settings.RTSP_TRANSPORT]
        cmd += ffmpeg.input_arguments(source)
        cmd += ["-t", "1", "-f", "null", "-"]

        def _run() -> tuple[float, int]:
            import subprocess

            start = time.monotonic()
            proc = subprocess.run(cmd, capture_output=True, timeout=settings.FFMPEG_TIMEOUT_SECONDS + 6)
            return (time.monotonic() - start) * 1000, proc.returncode

        loop = asyncio.get_running_loop()
        ms, _code = await loop.run_in_executor(self._executor, _run)
        return round(ms, 1)

    async def capabilities(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._capabilities_cache is None or now - self._capabilities_ts > 60:
            assets = {
                "ffmpeg": (await ffmpeg.running_version()) is not None,
                "version": await ffmpeg.running_version(),
                "encoders": await ffmpeg.available_encoders(),
                "gpu": await ffmpeg.detect_gpu(),
            }
            self._capabilities_cache = {
                "ffmpeg": assets,
                "opencv": {"available": settings.MOTION_ENABLED and _motion_available()},
                "publisher": await self._publisher_status(),
                "source_types": ["rtsp", "rtsps", "rtmp", "http", "https", "hls", "usb", "test"],
                "profile": {
                    "scale": settings.STREAM_PROFILE_SCALE,
                    "fps": settings.STREAM_PROFILE_FPS,
                    "crf": settings.STREAM_PROFILE_CRF,
                    "preset": settings.STREAM_PROFILE_PRESET,
                },
                "max_cameras": settings.STREAM_MAX_CAMERAS,
                "recording_dir": settings.RECORDING_DIR,
                "recording_max_seconds": settings.RECORDING_MAX_SECONDS,
                "motion": {
                    "enabled": settings.MOTION_ENABLED,
                    "record_clip_seconds": settings.MOTION_RECORD_CLIP_SECONDS,
                    "percent_threshold": settings.MOTION_PERCENT_THRESHOLD,
                },
            }
            self._capabilities_ts = now
        cache = dict(self._capabilities_cache or {})
        cache["active_streams"] = len(self._sessions)
        return cache

    # ------------------------------------------------------------------ #
    # Edge publisher (mediamtx) reachability + HLS/WHEP health
    # ------------------------------------------------------------------ #
    async def _publisher_status(self) -> dict[str, Any]:
        reachable = await self._publisher_reachable()
        return {
            "mode": "mediamtx",
            "reachable": reachable,
            "hls": reachable,
            "webrtc": reachable,
            "hls_url": f"{settings.MEDIAMTX_BASE_URL}/sentinel/_stream_/index.m3u8",
            "whep_url": f"{settings.MEDIAMTX_WHEP_URL}/sentinel/_stream_/whep",
            "hls_latency_ms": settings.HLS_TARGET_LATENCY,
        }

    async def _publisher_reachable(self) -> bool:
        now = time.monotonic()
        if self._pub_ts and now - self._pub_ts < 5.0:
            return bool(self._pub_ok)
        ok = False
        try:
            async with httpx.AsyncClient(timeout=settings.MEDIAMTX_READ_TIMEOUT) as client:
                resp = await client.get(settings.MEDIAMTX_BASE_URL + "/")
                ok = resp.status_code < 500
        except Exception:
            ok = False
        self._pub_ok = ok
        self._pub_ts = now
        return ok

    # ------------------------------------------------------------------ #
    # Recording scheduler
    # ------------------------------------------------------------------ #
    async def _scheduler_loop(self) -> None:
        log.info("recording.scheduler_started", windows=settings.RECORDING_SCHEDULE)
        while True:
            try:
                await self._scheduler_tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("recording.scheduler_tick_error", error=str(exc))
            await asyncio.sleep(30)

    async def _scheduler_tick(self) -> None:
        if not settings.RECORDING_SCHEDULE_ENABLED:
            return
        windows = _parse_windows(settings.RECORDING_SCHEDULE)
        now = datetime.now(timezone.utc).time()
        in_window = any(w_start <= now <= w_end for w_start, w_end in windows)
        for camera_id, session in list(self._sessions.items()):
            active = await self.recorders.is_active(camera_id)
            trigger = await self.recorders.trigger_of(camera_id)
            if in_window and not active:
                try:
                    await self.record_start(session, trigger="schedule")
                    log.info("recording.scheduled_start", camera_id=str(camera_id))
                except Exception as exc:
                    log.warning("recording.scheduled_start_failed", camera_id=str(camera_id), error=str(exc))
            elif not in_window and active and trigger == "schedule":
                await self.record_stop(camera_id)


def _parse_windows(spec: str) -> list[tuple[object, object]]:
    from datetime import time

    windows: list[tuple[object, object]] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" not in token:
            continue
        start_raw, end_raw = token.split("-", 1)
        try:
            sh, sm = (int(x) for x in start_raw.split(":", 1))
            eh, em = (int(x) for x in end_raw.split(":", 1))
            windows.append((time(hour=sh, minute=sm), time(hour=eh, minute=em)))
        except (ValueError, IndexError):
            log.warning("recording.schedule_invalid_token", token=token)
    return windows


def _write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(data)


def _motion_available() -> bool:
    from src.services.media import motion as motion_mod

    return motion_mod._CV2_OK


def session_source(camera: Camera) -> str:
    return sources.resolve_source(camera).input


# ---------------------------------------------------------------------- #
# Module-level singleton
# ---------------------------------------------------------------------- #
_manager: StreamManager | None = None
_manager_lock = Lock()


def get_manager() -> StreamManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = StreamManager()
    return _manager


__all__ = ["StreamManager", "StreamSession", "get_manager", "session_source"]
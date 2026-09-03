"""Recording lifecycle: start/stop, bounded clips, scheduler integration.

Live recorders run as bounded ffmpeg MP4 subprocesses keyed by camera. Metadata
is persisted to the `recordings` table; the *live* process bookkeeping lives
here in memory (one `ActiveRecorder` per camera).
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.logging import log
from src.models.stream import Recording
from src.services.media import ffmpeg
from src.services.media.paths import recording_path


@dataclass
class ActiveRecorder:
    camera_id: UUID
    row_id: UUID
    file_path: str
    trigger: str
    started_at: datetime
    proc: asyncio.subprocess.Process | None = None
    task: asyncio.Task | None = None
    stop_requested: bool = False
    error: str | None = None


class RecordingManager:
    """Owns running recording subprocesses and finalizes them on stop."""

    def __init__(self, executor: ThreadPoolExecutor) -> None:
        self._executor = executor
        self._active: dict[UUID, ActiveRecorder] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # Live bookkeeping
    # ------------------------------------------------------------------ #
    async def is_active(self, camera_id: UUID) -> bool:
        async with self._lock:
            rec = self._active.get(camera_id)
            return rec is not None and rec.proc is not None and rec.proc.returncode is None

    async def active_cameras(self) -> list[UUID]:
        async with self._lock:
            return [cid for cid, rec in self._active.items() if rec.proc and rec.proc.returncode is None]

    async def trigger_of(self, camera_id: UUID) -> str | None:
        async with self._lock:
            rec = self._active.get(camera_id)
            return rec.trigger if rec else None

    # ------------------------------------------------------------------ #
    # Starting / stopping
    # ------------------------------------------------------------------ #
    async def start(
        self,
        *,
        camera_id: UUID,
        input_source: str,
        trigger: str,
        started_by: UUID | None = None,
        seconds: int = 0,
        segment: int | None = None,
    ) -> Recording:
        """Create the recording row and launch the MP4 recorder."""
        segment = segment or settings.RECORDING_SEGMENT_SECONDS
        seconds = min(seconds, settings.RECORDING_MAX_SECONDS) if settings.RECORDING_MAX_SECONDS and seconds else seconds

        filename = f"{camera_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{str(uuid4())[:8]}.mp4"
        file_path = recording_path(camera_id, filename)

        async with AsyncSessionLocal() as db:
            recording = Recording(
                camera_id=camera_id,
                started_by=started_by,
                trigger=trigger,
                status="recording",
                file_path=file_path,
                segment_seconds=segment,
                started_at=datetime.now(timezone.utc),
            )
            db.add(recording)
            await db.commit()
            await db.refresh(recording)

        cmd = ffmpeg.build_recorder_command(input_source, file_path, seconds=seconds, segment=segment)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        active = ActiveRecorder(
            camera_id=camera_id,
            row_id=recording.id,
            file_path=file_path,
            trigger=trigger,
            started_at=datetime.now(timezone.utc),
            proc=proc,
        )
        async with self._lock:
            await self._release_existing(camera_id, "starting new recording")
            self._active[camera_id] = active

        active.task = asyncio.create_task(self._watch(active, seconds=seconds))
        log.info("recording.started", camera_id=str(camera_id), trigger=trigger, file=file_path)
        return recording

    async def stop(self, camera_id: UUID) -> tuple[UUID | None, ActiveRecorder | None]:
        """Request the recorder process stop and return (row_id, active) for finalize."""
        async with self._lock:
            active = self._active.get(camera_id)
            if active is None:
                return None, None
            active.stop_requested = True
            proc = active.proc
        if proc is not None and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        if active.task is not None:
            with suppress(asyncio.CancelledError):
                try:
                    await asyncio.wait_for(asyncio.shield(active.task), timeout=5.0)
                except Exception:
                    pass
        return active.row_id, active

    async def finalize(
        self, db: AsyncSession, row: Recording, active: ActiveRecorder, *, status: str = "stopped"
    ) -> Recording:
        """Persist final metadata once a recorder has stopped."""
        size, duration = await self._file_meta(active.file_path)
        row.status = status
        row.size_bytes = size
        row.duration_seconds = duration
        row.ended_at = datetime.now(timezone.utc)
        row.started_at = row.started_at or active.started_at
        async with self._lock:
            self._active.pop(active.camera_id, None)
        await db.commit()
        await db.refresh(row)
        log.info(
            "recording.finalized", camera_id=str(active.camera_id), status=status,
            size_bytes=size, duration_seconds=duration,
        )
        return row

    async def current(self, camera_id: UUID) -> dict[str, Any] | None:
        async with self._lock:
            active = self._active.get(camera_id)
            if active is None:
                return None
            return {
                "recording": active.proc is not None and active.proc.returncode is None,
                "trigger": active.trigger,
                "file_path": active.file_path,
                "started_at": active.started_at.isoformat(),
                "error": active.error,
            }

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    async def _watch(self, active: ActiveRecorder, seconds: int) -> None:
        try:
            proc = active.proc
            if proc is None:
                return
            # Fixed-duration clips stop themselves.
            if seconds and seconds > 0:
                await asyncio.sleep(seconds)
                active.stop_requested = True
                if proc.returncode is None:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        proc.kill()
            if proc.returncode not in (None, 0):
                stderr = b""
                try:
                    stderr = (await proc.stderr.read()).decode("utf-8", "replace") if proc.stderr else ""
                except Exception:
                    pass
                active.error = (stderr or "recorder exited").splitlines()[-1] if stderr else "recorder exited"
                log.warning("recording.proc_exited", camera_id=str(active.camera_id), code=proc.returncode, error=active.error)
                await self._auto_finalize(active, status="failed")
                return
            if active.stop_requested:
                await self._auto_finalize(active, status="stopped")
        except asyncio.CancelledError:
            raise

    async def _auto_finalize(self, active: ActiveRecorder, status: str) -> None:
        """Finalize a recording in the background (scheduler/motion paths)."""
        try:
            async with AsyncSessionLocal() as db:
                row = await self._load_row(active.row_id)
                if row is not None:
                    await self.finalize(db, row, active, status=status)
        except Exception as exc:  # pragma: no cover - best effort
            log.warning("recording.auto_finalize_failed", error=str(exc))

    async def _load_row(self, row_id: UUID) -> Recording | None:
        async with AsyncSessionLocal() as db:
            return await db.get(Recording, row_id)

    async def _release_existing(self, camera_id: UUID, reason: str) -> None:
        existing = self._active.get(camera_id)
        if existing is not None and existing.proc is not None and existing.proc.returncode is None:
            await self.stop(camera_id)
            log.warning("recording.replace", camera_id=str(camera_id), reason=reason)

    @staticmethod
    async def _file_meta(path: str) -> tuple[int | None, float | None]:
        def _stat() -> tuple[int | None, float | None]:
            try:
                size = os.path.getsize(path)
            except OSError:
                return None, None
            duration = None
            try:
                import subprocess

                result = subprocess.run(
                    [ffmpeg.FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", path],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    duration = round(float(result.stdout.strip()), 2)
            except Exception:
                duration = None
            return size, duration

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _stat)


__all__ = ["ActiveRecorder", "RecordingManager"]
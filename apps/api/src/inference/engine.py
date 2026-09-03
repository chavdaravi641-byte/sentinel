"""Inference engine — orchestrates the Phase 3 AI stack.

Model registry + loader + YOLOv12 plugin -> per-camera frame pumps -> batch
scheduler (GPU across cameras, CPU single-frame) -> tracking -> detection
store -> alert engine -> realtime WebSocket event bus. Zero changes are made
to the Phase 1/2 stream engine: frames are read through the public
`StreamManager.session(...).buffer.get_latest()` surface.

Concurrency model: each camera runs one pump task that only *enqueues* frames;
a single scheduler task owns the plugin runtime (onnxruntime sessions are
thread-safe but serialized here anyway), tracking, storage and alert state.
CPU-bound decode/preprocess/forward passes run on a shared thread pool so the
event loop never blocks.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import numpy as np
from src.core.config import settings
from src.core.logging import log
from src.inference.alerts import AlertEngine
from src.inference.events import EventBus
from src.inference.loader import ModelLoader
from src.inference.plugin import ModelPlugin
from src.inference.primitives import BoxResult, InferItem, Timings
from src.inference.storage import (
    AI_MODEL_STATUS_ERROR,
    AI_MODEL_STATUS_LOADED,
    AI_MODEL_STATUS_UNLOADED,
    DetectionStore,
    build_model_snapshot,
)
from src.inference.tracking import IoUTracker
from src.inference.yolov12 import YoloV12Plugin
from src.models.camera import Camera
from src.services.media.manager import get_manager

_INFER_FPS_MAX = 60.0


@dataclass
class FrameItem:
    camera_id: str
    jpeg: bytes
    ts: float


@dataclass
class CameraRuntime:
    camera_id: str
    camera_name: str | None
    model_name: str
    seed: int
    active: bool = False
    worker_task: asyncio.Task | None = None
    frame_seq: int = 0
    last_processed_frame_at: float | None = None
    tracker: IoUTracker = field(default_factory=IoUTracker)
    started_ts: float = field(default_factory=time.monotonic)
    frames_analyzed: int = 0
    total_detections: int = 0
    fps: float = 0.0
    avg_infer_ms: float = 0.0
    avg_total_ms: float = 0.0
    last_run_ts: float = 0.0
    last_overlay: dict[str, Any] | None = None
    last_overlay_ts: float = 0.0
    last_counts: dict[str, int] = field(default_factory=dict)
    last_tracked: list[tuple[int, BoxResult, int]] = field(default_factory=list)
    _period_alpha: float = 0.15

    def tick(self, timings: Timings, now: float) -> None:
        self.frames_analyzed += 1
        if self.last_run_ts:
            period = max(1e-3, now - self.last_run_ts)
            inst_fps = 1.0 / period
            self.fps = self._period_alpha * inst_fps + (1.0 - self._period_alpha) * self.fps
        else:
            self.fps = 1.0 / max(1e-3, timings.total_ms / 1000.0)
        self.last_run_ts = now
        self.avg_infer_ms = _ewma(self.avg_infer_ms, timings.infer_ms)
        self.avg_total_ms = _ewma(self.avg_total_ms, timings.total_ms)


def _ewma(current: float, sample: float, alpha: float = 0.15) -> float:
    return alpha * sample + (1.0 - alpha) * current if current else sample


class InferenceManager:
    """Process-wide singleton orchestrating model + camera inference."""

    def __init__(self) -> None:
        self._loader = ModelLoader(settings.AI_WEIGHTS_DIR, settings.AI_ACCEL)
        self._registry: dict[str, ModelPlugin] = {}
        self._cameras: dict[str, CameraRuntime] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._queue: asyncio.Queue[FrameItem] = asyncio.Queue(maxsize=512)
        self._executor = None
        self.bus = EventBus()
        self.store = DetectionStore(enabled=settings.AI_STORE_ENABLED)
        self.alerts = AlertEngine(
            enabled=settings.AI_ALERT_ENABLED,
            persistence=settings.AI_ALERT_PERSISTENCE,
            crowd_persons=settings.AI_ALERT_CROWD_PERSONS,
            traffic_vehicles=settings.AI_ALERT_TRAFFIC_VEHICLES,
            cooldown=settings.AI_ALERT_COOLDOWN,
        )
        self._scheduler_task: asyncio.Task | None = None
        self._stats_task: asyncio.Task | None = None
        self.default_model: str = settings.AI_MODEL

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        if not settings.AI_ENABLED:
            log.warning("ai.engine.disabled", enabled=settings.AI_ENABLED)
            return
        await self._ensure_executor()
        # Register plugins (modular framework: add providers here).
        self.register_plugin(YoloV12Plugin(self._loader, self._loader.detect_device(), settings.AI_CONFIDENCE))
        for plugin in self._registry.values():
            try:
                await asyncio.get_running_loop().run_in_executor(self._executor, plugin.load)
            except Exception as exc:  # noqa: BLE001
                plugin._error = str(exc)
                log.error("ai.model.load_failed", model=plugin.name, error=str(exc))
            await self._persist_model(plugin)
        self.store.start()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(), name="ai-scheduler")
        self._stats_task = asyncio.create_task(self._stats_loop(), name="ai-stats")
        self._running = True
        log.info("ai.engine.started", models=list(self._registry), device=self.device().to_dict())

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        for cam_id in list(self._cameras):
            await self.camera_stop(cam_id)
        for task in (self._scheduler_task, self._stats_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await self.store.shutdown()
        await self._ensure_executor(teardown=True)
        log.info("ai.engine.stopped")

    def register_plugin(self, plugin: ModelPlugin) -> None:
        self._registry[plugin.name] = plugin

    async def _ensure_executor(self, teardown: bool = False) -> None:
        if teardown:
            if self._executor is not None:
                self._executor.shutdown(wait=False)
                self._executor = None
            return
        if self._executor is None:
            import concurrent.futures

            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=4, thread_name_prefix="sentinel-ai"
            )

    def device(self) -> Any:
        return self._loader.detect_device()

    # ------------------------------------------------------------------ #
    # Models / registry
    # ------------------------------------------------------------------ #
    def plugin(self, name: str | None = None) -> ModelPlugin:
        name = name or self.default_model
        plugin = self._registry.get(name)
        if plugin is None:
            raise KeyError(name)
        return plugin

    async def model_load(self, name: str | None = None) -> dict[str, Any]:
        plugin = self.plugin(name)
        try:
            await asyncio.get_running_loop().run_in_executor(self._executor, plugin.load)
        except Exception as exc:
            plugin._error = str(exc)
            raise
        await self._persist_model(plugin)
        return plugin.health()

    async def model_reload(self, name: str | None = None) -> dict[str, Any]:
        plugin = self.plugin(name)
        try:
            await asyncio.get_running_loop().run_in_executor(self._executor, plugin.reload)
        except Exception as exc:
            plugin._error = str(exc)
            raise
        await self._persist_model(plugin)
        return plugin.health()

    async def model_unload(self, name: str | None = None) -> dict[str, Any]:
        plugin = self.plugin(name)
        try:
            await asyncio.get_running_loop().run_in_executor(self._executor, plugin.unload)
        except Exception as exc:  # noqa: BLE001
            plugin._error = str(exc)
        await self._persist_model(plugin)
        return plugin.health()

    def model_health(self, name: str | None = None) -> dict[str, Any]:
        return self.plugin(name).health()

    def models(self) -> list[dict[str, Any]]:
        return [p.health() for p in self._registry.values()]

    async def _persist_model(self, plugin: ModelPlugin) -> None:
        h = plugin.health()
        status = AI_MODEL_STATUS_LOADED if h["loaded"] else AI_MODEL_STATUS_UNLOADED
        if h.get("error"):
            status = AI_MODEL_STATUS_ERROR
        self.store.submit_model(
            build_model_snapshot(
                name=h["name"],
                version=h["version"],
                backend=h["backend"],
                status=status,
                generation=h["generation"],
                accelerator=h.get("accelerator"),
                device=h.get("device_name"),
                providers=h.get("providers"),
                weights_path=None,
                classes=h["classes"],
                error=h.get("error"),
                loaded_at=datetime.fromtimestamp(h["loaded_at"], tz=timezone.utc) if h.get("loaded_at") else None,
            )
        )

    # ------------------------------------------------------------------ #
    # Single-image analysis (REST infer + CLI)
    # ------------------------------------------------------------------ #
    async def analyze_image(
        self,
        jpeg: bytes,
        *,
        model_name: str | None = None,
        ctx: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one frame through the active plugin and return full telemetry."""
        plugin = self.plugin(model_name)

        def _run() -> tuple[list[BoxResult], Timings]:
            img = _decode_jpeg(jpeg)
            items = [InferItem(image=img, ctx=ctx)]
            results, timings = plugin.infer_batch(items)
            return results[0], timings

        detections, timings = await asyncio.get_running_loop().run_in_executor(self._executor, _run)
        h = plugin.health()
        return {
            "model": h["name"],
            "generation": h["generation"],
            "backend": h["backend"],
            "accelerator": h.get("accelerator"),
            "device_name": h.get("device_name"),
            "providers": h.get("providers"),
            "timings": {
                "pre_ms": round(timings.pre_ms, 3),
                "infer_ms": round(timings.infer_ms, 3),
                "post_ms": round(timings.post_ms, 3),
                "total_ms": round(timings.total_ms, 3),
            },
            "detections": [d.to_dict() for d in detections],
            "count": len(detections),
        }

    # ------------------------------------------------------------------ #
    # Camera inference workers
    # ------------------------------------------------------------------ #
    async def camera_start(self, camera: Camera) -> dict[str, Any]:
        cam_id = str(camera.id)
        async with self._lock:
            existing = self._cameras.get(cam_id)
            if existing is not None and existing.active:
                return await self.camera_status(camera)
            runtime = CameraRuntime(
                camera_id=cam_id,
                camera_name=camera.name,
                model_name=self.default_model,
                seed=int(uuid.UUID(cam_id).int & 0x7FFFFFFF),
            )
            self._cameras[cam_id] = runtime
        runtime.worker_task = asyncio.create_task(
            self._pump(runtime), name=f"ai-pump-{cam_id[:8]}"
        )
        runtime.active = True
        log.info("ai.camera.started", camera_id=cam_id, camera=camera.name)
        return await self.camera_status(camera)

    async def camera_stop(self, camera_id: str) -> dict[str, Any]:
        cam_id = str(camera_id)
        async with self._lock:
            runtime = self._cameras.get(cam_id)
            if runtime is None:
                return {"camera_id": cam_id, "active": False}
            runtime.active = False
            task = runtime.worker_task
            self._cameras.pop(cam_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        log.info("ai.camera.stopped", camera_id=cam_id, frames=runtime.frames_analyzed)
        return {"camera_id": cam_id, "active": False, "frames_analyzed": runtime.frames_analyzed}

    def camera_active(self, camera_id: str) -> bool:
        runtime = self._cameras.get(str(camera_id))
        return bool(runtime and runtime.active)

    def cameras(self) -> list[CameraRuntime]:
        return [rt for rt in self._cameras.values()]

    async def camera_status(self, camera: Camera) -> dict[str, Any]:
        cam_id = str(camera.id)
        runtime = self._cameras.get(cam_id)
        manager = get_manager()
        session = await manager.session(camera.id)
        stream_running = bool(session and session.live)
        if runtime is None:
            return {
                "camera_id": cam_id,
                "camera_name": camera.name,
                "stream_running": stream_running,
                "inference_active": False,
            }
        stats = await self.camera_stats(camera)
        payload = stats
        payload["inference_active"] = runtime.active
        payload["stream_running"] = stream_running
        return payload

    async def camera_stats(self, camera: Camera) -> dict[str, Any]:
        cam_id = str(camera.id)
        runtime = self._cameras.get(cam_id)
        if runtime is None:
            return {"camera_id": cam_id, "camera_name": camera.name, "inference_active": False}
        plugin = self._registry.get(runtime.model_name)
        h = plugin.health() if plugin else {}
        device = self._loader.scheduler.device.to_dict()
        return {
            "camera_id": cam_id,
            "camera_name": runtime.camera_name,
            "inference_active": runtime.active,
            "model": runtime.model_name,
            "backend": h.get("backend"),
            "accelerator": h.get("accelerator"),
            "device_name": h.get("device_name"),
            "generation": h.get("generation"),
            "frames_analyzed": runtime.frames_analyzed,
            "total_detections": runtime.total_detections,
            "last_frame_counts": dict(runtime.last_counts),
            "fps": round(runtime.fps, 2),
            "avg_infer_ms": round(runtime.avg_infer_ms, 2),
            "avg_total_ms": round(runtime.avg_total_ms, 2),
            "frame_seq": runtime.frame_seq,
            "started_ts": runtime.started_ts,
            "uptime_s": round(time.monotonic() - runtime.started_ts, 1),
            "last_overlay": runtime.last_overlay,
            "device": device,
        }

    def last_overlay(self, camera_id: str) -> dict[str, Any] | None:
        runtime = self._cameras.get(str(camera_id))
        return runtime.last_overlay if runtime else None

    # ------------------------------------------------------------------ #
    # Frame pump (one task per camera)
    # ------------------------------------------------------------------ #
    async def _pump(self, runtime: CameraRuntime) -> None:
        cam_uuid = uuid.UUID(runtime.camera_id)
        interval = 1.0 / max(0.5, min(settings.AI_INFER_FPS, _INFER_FPS_MAX))
        stream_manager = get_manager()
        while runtime.active:
            try:
                session = await stream_manager.session(cam_uuid)
                if session is not None and session.live:
                    latest = await session.buffer.get_latest()
                    frame_ts = session.buffer.last_frame_at
                    if (
                        latest is not None
                        and frame_ts is not None
                        and frame_ts != runtime.last_processed_frame_at
                    ):
                        runtime.last_processed_frame_at = frame_ts
                        runtime.frame_seq += 1
                        try:
                            self._queue.put_nowait(
                                FrameItem(camera_id=runtime.camera_id, jpeg=latest, ts=frame_ts)
                            )
                        except asyncio.QueueFull:
                            pass  # drop frame under backpressure
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("ai.pump_error", camera_id=runtime.camera_id, error=str(exc))
                await asyncio.sleep(max(interval, 1.0))

    # ------------------------------------------------------------------ #
    # Batch scheduler (single task; owns plugin + tracking + store)
    # ------------------------------------------------------------------ #
    async def _scheduler_loop(self) -> None:
        batch_size = settings.AI_BATCH_SIZE
        window = settings.AI_BATCH_WINDOW_MS / 1000.0
        while True:
            try:
                batch: list[FrameItem] = []
                deadline = time.monotonic() + window
                while len(batch) < batch_size:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        item = await asyncio.wait_for(self._queue.get(), remaining)
                    except asyncio.TimeoutError:
                        break
                    batch.append(item)
                    if self.device().accelerator == "cpu" and len(batch) >= 1:
                        break
                if batch:
                    await self._process_batch(self.plugin(), batch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("ai.scheduler_error", error=str(exc))
                await asyncio.sleep(0.05)

    async def _process_batch(self, plugin: ModelPlugin, batch: list[FrameItem]) -> None:
        loop = asyncio.get_running_loop()

        def _build() -> list[InferItem]:
            items: list[InferItem] = []
            for it in batch:
                rt = self._cameras.get(it.camera_id)
                seq = rt.frame_seq if rt else 0
                seed = rt.seed if rt else 1
                img = _decode_jpeg(it.jpeg)
                items.append(
                    InferItem(image=img, ctx={"camera_id": it.camera_id, "frame_seq": seq, "seed": seed})
                )
            return items

        items = await loop.run_in_executor(self._executor, _build)
        results, timings = await loop.run_in_executor(self._executor, plugin.infer_batch, items)
        now = time.monotonic()
        h = plugin.health()

        runs: list[dict[str, Any]] = []
        dets: list[dict[str, Any]] = []

        for idx, (item, boxes) in enumerate(zip(batch, results)):
            rt = self._cameras.get(item.camera_id)
            if rt is None or not rt.active:
                continue
            seq = rt.frame_seq
            ts = datetime.now(timezone.utc)
            img0 = items[idx].image
            run_row = {
                "camera_id": uuid.UUID(rt.camera_id),
                "model_name": plugin.name,
                "model_version": h["version"],
                "model_generation": h["generation"],
                "frame_seq": seq,
                "ts": ts,
                "width": int(img0.shape[1]),
                "height": int(img0.shape[0]),
                "pre_ms": round(timings.pre_ms, 3),
                "infer_ms": round(timings.infer_ms, 3),
                "post_ms": round(timings.post_ms, 3),
                "total_ms": round(timings.total_ms, 3),
                "batch_size": len(batch),
                "detections": len(boxes),
                "fps": round(rt.fps, 3),
                "accelerator": h.get("accelerator"),
                "backend": h.get("backend"),
            }

            tracked = rt.tracker.update(boxes, now)
            rt.last_tracked = tracked
            det_rows = [
                {
                    "camera_id": uuid.UUID(rt.camera_id),
                    "model_name": plugin.name,
                    "class_name": box.class_name,
                    "confidence": box.confidence,
                    "track_id": tid,
                    "x": box.x,
                    "y": box.y,
                    "w": box.w,
                    "h": box.h,
                    "cx": box.cx,
                    "cy": box.cy,
                    "frame_seq": seq,
                    "ts": ts,
                }
                for tid, box, _hits in tracked
            ]
            rt.total_detections += len(tracked)
            rt.last_counts.clear()
            for _tid, box, _h in tracked:
                rt.last_counts[box.class_name] = rt.last_counts.get(box.class_name, 0) + 1
            rt.tick(timings, now)
            runs.append(run_row)
            dets.extend(det_rows)

            for alert in self.alerts.evaluate(
                camera_id=rt.camera_id,
                model_name=plugin.name,
                tracked=tracked,
                counts=rt.last_counts,
            ):
                payload = {
                    k: (v.isoformat() if isinstance(v, datetime) else (str(v) if isinstance(v, uuid.UUID) else v))
                    for k, v in alert.items()
                }
                self.store.submit_alert(payload)
                await self.bus.publish("alert", {"type": "alert", **payload})
            await self._maybe_publish_overlay(rt, plugin, timings)

        if runs:
            self.store.submit_runs(runs, dets)

    async def _maybe_publish_overlay(
        self, rt: CameraRuntime, plugin: ModelPlugin, timings: Timings
    ) -> None:
        now_mono = time.monotonic()
        if now_mono - rt.last_overlay_ts < settings.AI_OVERLAY_INTERVAL:
            return
        h = plugin.health()
        payload = {
            "type": "overlay",
            "camera_id": rt.camera_id,
            "camera_name": rt.camera_name,
            "model": plugin.name,
            "generation": h["generation"],
            "backend": h["backend"],
            "accelerator": h.get("accelerator"),
            "device_name": h.get("device_name"),
            "ts": datetime.now(timezone.utc).isoformat(),
            "pre_ms": round(timings.pre_ms, 2),
            "infer_ms": round(timings.infer_ms, 2),
            "post_ms": round(timings.post_ms, 2),
            "total_ms": round(timings.total_ms, 2),
            "fps": round(rt.fps, 2),
            "frame_seq": rt.frame_seq,
            "detection_count": len(rt.last_tracked),
            "boxes": [
                {"class_name": box.class_name, "confidence": box.confidence, "track_id": tid}
                | box.to_dict()
                for tid, box, _h in rt.last_tracked
            ],
        }
        rt.last_overlay = payload
        rt.last_overlay_ts = now_mono
        await self.bus.publish("overlay", payload)

    # ------------------------------------------------------------------ #
    # Aggregated stats broadcast
    # ------------------------------------------------------------------ #
    async def _stats_loop(self) -> None:
        while True:
            await asyncio.sleep(2.0)
            try:
                for cam_id, rt in list(self._cameras.items()):
                    if not rt.active:
                        continue
                    plugin = self._registry.get(rt.model_name)
                    h = plugin.health() if plugin else {}
                    payload = {
                        "type": "stats",
                        "camera_id": rt.camera_id,
                        "camera_name": rt.camera_name,
                        "model": rt.model_name,
                        "backend": h.get("backend"),
                        "accelerator": h.get("accelerator"),
                        "device_name": h.get("device_name"),
                        "generation": h.get("generation"),
                        "fps": round(rt.fps, 2),
                        "avg_infer_ms": round(rt.avg_infer_ms, 2),
                        "avg_total_ms": round(rt.avg_total_ms, 2),
                        "frames_analyzed": rt.frames_analyzed,
                        "total_detections": rt.total_detections,
                        "last_frame_counts": dict(rt.last_counts),
                        "uptime_s": round(time.monotonic() - rt.started_ts, 1),
                        "gpu": None,
                    }
                    dev = self.device()
                    if dev.accelerator == "cuda":
                        payload["gpu"] = dev.gpu or {"name": dev.device_name}
                    await self.bus.publish("stats", payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("ai.stats_loop_error", error=str(exc))

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    async def config_payload(self) -> dict[str, Any]:
        dev = self.device()
        return {
            "enabled": settings.AI_ENABLED,
            "model": self.default_model,
            "weights_dir": settings.AI_WEIGHTS_DIR,
            "accel_mode": settings.AI_ACCEL,
            "plugins": self.models(),
            "device": dev.to_dict(),
            "batch": {
                "size": settings.AI_BATCH_SIZE,
                "window_ms": settings.AI_BATCH_WINDOW_MS,
            },
            "confidence": settings.AI_CONFIDENCE,
            "max_fps_per_camera": settings.AI_INFER_FPS,
            "store_enabled": settings.AI_STORE_ENABLED,
            "alert_enabled": settings.AI_ALERT_ENABLED,
            "processes_active": len([rt for rt in self._cameras.values() if rt.active]),
        }

    async def summary(self, db) -> dict[str, Any]:
        from datetime import timedelta

        from sqlalchemy import func, select
        from src.models.inference import Detection, InferenceAlert, InferenceRun

        runs_total = int((await db.execute(select(func.count(InferenceRun.id)))).scalar_one())
        detections_total = int((await db.execute(select(func.count(Detection.id)))).scalar_one())
        alerts_open = int(
            (
                await db.execute(
                    select(func.count(InferenceAlert.id)).where(InferenceAlert.resolved.is_(False))
                )
            ).scalar_one()
        )
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        runs_last_minute = int(
            (
                await db.execute(
                    select(func.count(InferenceRun.id)).where(
                        InferenceRun.ts >= datetime.now(timezone.utc) - timedelta(minutes=1)
                    )
                )
            ).scalar_one()
        )
        by_class_rows = await db.execute(
            select(Detection.class_name, func.count()).group_by(Detection.class_name)
        )
        by_class = dict(by_class_rows.all())
        avg_latency = (
            await db.execute(
                select(func.avg(InferenceRun.infer_ms)).where(InferenceRun.ts >= hour_ago)
            )
        ).scalar_one()
        return {
            "runs_total": runs_total,
            "detections_total": detections_total,
            "by_class": by_class,
            "alerts_open": alerts_open,
            "runs_last_minute": runs_last_minute,
            "avg_infer_ms_recent": round(float(avg_latency or 0.0), 2),
            "active_cameras": len([rt for rt in self._cameras.values() if rt.active]),
            "up": self._running,
        }


def _decode_jpeg(jpeg: bytes):
    import cv2

    return cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)


# ---------------------------------------------------------------------- #
# Module-level singleton
# ---------------------------------------------------------------------- #
_manager: InferenceManager | None = None
_manager_lock = Lock()


def get_inference_manager() -> InferenceManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = InferenceManager()
    return _manager


__all__ = ["InferenceManager", "get_inference_manager"]
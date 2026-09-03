"""ANPR pipeline manager — orchestrates the Phase 4 stack.

Pipeline per camera frame:

    Frame -> vehicle detection (Phase 3) -> plate detection -> perspective
    correction -> OCR (batch) -> validation -> vehicle attributes -> DB -> alerts

Frames are read through the public Phase 2 ``StreamManager.session(...).buffer``
surface (no Phase 1/2 changes). One pump task per camera enqueues frames; a
single pipeline task drains the queue, batches plate crops into the OCR engine,
rectifies, extracts attributes, validates, persists through the ANPR store and
fires the ANPR alert engine + WebSocket event bus.

CPU-bound stages (decode, rectify, OCR, attribute, evidence writes) run on a
shared ``ThreadPoolExecutor`` so the event loop never blocks. This mirrors the
proven Phase 3 concurrency model while living in a separate module.
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

from src.anpr.alerts import AnprAlertEngine
from src.anpr.blacklist import BlacklistEngine
from src.anpr.evidence import EvidenceStore
from src.anpr.ocr import OcrEngine
from src.anpr.onnx_backend import StageBackend
from src.anpr.plate_detector import PlateDetector
from src.anpr.plate_rectifier import rectify_plate
from src.anpr.primitives import (
    AnprResult,
    PlateEvent,
    PlateBox,
    Timings,
    normalize_plate,
    parse_state_rto,
)
from src.anpr.vehicles import VehicleIntelligence
from src.anpr.validator import PlateValidator
from src.core.config import settings
from src.core.logging import log
from src.models.camera import Camera
from src.services.media.manager import get_manager


@dataclass
class FrameItem:
    camera_id: str
    jpeg: bytes
    ts: float


@dataclass
class CameraRuntime:
    camera_id: str
    camera_name: str | None
    seed: int
    active: bool = False
    worker_task: asyncio.Task | None = None
    frame_seq: int = 0
    last_processed_frame_at: float | None = None
    plates_read: int = 0
    started_ts: float = field(default_factory=time.monotonic)
    frames_analyzed: int = 0
    last_run_ts: float = 0.0
    last_event: dict[str, Any] | None = None
    _period_alpha: float = 0.15
    fps: float = 0.0

    def tick(self, now: float) -> None:
        self.frames_analyzed += 1
        if self.last_run_ts:
            period = max(1e-3, now - self.last_run_ts)
            self.fps = self._period_alpha * (1.0 / period) + (1.0 - self._period_alpha) * self.fps
        self.last_run_ts = now


class AnprEventBus:
    """Tiny in-process event hub for ANPR realtime fan-out (own bus)."""

    def __init__(self) -> None:
        from asyncio import Queue

        self._q: Queue[dict[str, Any]] = Queue(maxsize=512)

    async def publish(self, payload: dict[str, Any]) -> None:
        try:
            self._q.put_nowait(payload)
            forced = self._q.get_nowait() if self._q.qsize() > 480 else None
        except Exception:  # noqa: BLE001
            pass

    def subscribe(self):
        from asyncio import Queue

        q: Queue[dict[str, Any]] = Queue(maxsize=128)
        return q


class AnprManager:
    """Process-wide singleton for the ANPR pipeline."""

    def __init__(self) -> None:
        self._backend = StageBackend(settings.ANPR_WEIGHTS_DIR, settings.ANPR_ACCEL)
        self._detector = PlateDetector(self._backend, settings.ANPR_PLATE_MIN_CONF)
        self._ocr = OcrEngine(self._backend, settings.ANPR_OCR_MIN_CONF)
        self._vehicles = VehicleIntelligence(self._backend)
        self._validator = PlateValidator()
        self._blacklist = BlacklistEngine(
            strict_eq=settings.ANPR_PLATE_STRICT_EQ,
            sync_seconds=settings.ANPR_BLACKLIST_SYNC_SECONDS,
        )
        self._evidence = EvidenceStore(
            enabled=settings.ANPR_EVIDENCE_ENABLED,
            root_dir=settings.ANPR_EVIDENCE_DIR,
        )
        self._alerts = AnprAlertEngine(
            enabled=settings.ANPR_ALERT_ENABLED,
            low_conf_threshold=settings.ANPR_ALERT_LOW_CONF_THRESHOLD,
            multi_camera_window=settings.ANPR_ALERT_MULTI_CAMERA_WINDOW,
            reappear_after=settings.ANPR_ALERT_REAPPEAR_AFTER,
            cooldown=settings.ANPR_ALERT_COOLDOWN,
            blacklist_enabled=settings.ANPR_ALERT_BLACKLIST,
            low_conf_enabled=settings.ANPR_ALERT_LOW_CONF,
            multi_camera_enabled=settings.ANPR_ALERT_MULTI_CAMERA_ENABLED,
            reappear_enabled=settings.ANPR_ALERT_REAPPEAR,
        )
        from src.anpr.store import get_store

        self._store = get_store()
        self._store.enabled = settings.ANPR_STORE_ENABLED
        self._cameras: dict[str, CameraRuntime] = {}
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[FrameItem] = asyncio.Queue(maxsize=512)
        self._running = False
        self._executor = None
        self._scheduler_task: asyncio.Task | None = None
        self._stats_task: asyncio.Task | None = None
        self._blacklist_task: asyncio.Task | None = None
        self.bus = AnprEventBus()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        if not settings.ANPR_ENABLED:
            log.warning("anpr.engine.disabled", enabled=settings.ANPR_ENABLED)
            return
        await self._ensure_executor()
        self._running = True
        self._store.start()
        self._scheduler_task = asyncio.create_task(self._pipeline_loop(), name="anpr-pipeline")
        self._stats_task = asyncio.create_task(self._stats_loop(), name="anpr-stats")
        await self.start_blacklist_sync()
        dev = self._backend.detect_device()
        log.info(
            "anpr.engine.started",
            accelerator=dev["accelerator"],
            plate=self._detector.is_sim,
            ocr=self._ocr.engine,
            vehicle=self._vehicles.is_sim,
        )

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        for cam_id in list(self._cameras):
            await self.camera_stop(cam_id)
        for task in (self._scheduler_task, self._stats_task, self._blacklist_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await self._store.shutdown()
        await self._ensure_executor(teardown=True)
        log.info("anpr.engine.stopped")

    async def _ensure_executor(self, teardown: bool = False) -> None:
        import concurrent.futures

        if teardown:
            if self._executor is not None:
                self._executor.shutdown(wait=False)
                self._executor = None
            return
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=settings.STREAM_THREAD_POOL, thread_name_prefix="sentinel-anpr"
            )

    # ------------------------------------------------------------------ #
    # Camera workers
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
                seed=int(uuid.UUID(cam_id).int & 0x7FFFFFFF),
            )
            self._cameras[cam_id] = runtime
        runtime.worker_task = asyncio.create_task(
            self._pump(runtime), name=f"anpr-pump-{cam_id[:8]}"
        )
        runtime.active = True
        log.info("anpr.camera.started", camera_id=cam_id, camera=camera.name)
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
        return {"camera_id": cam_id, "active": False, "frames_analyzed": runtime.frames_analyzed}

    def camera_active(self, camera_id: str) -> bool:
        runtime = self._cameras.get(str(camera_id))
        return bool(runtime and runtime.active)

    def cameras(self) -> list[CameraRuntime]:
        return list(self._cameras.values())

    async def camera_status(self, camera: Camera) -> dict[str, Any]:
        cam_id = str(camera.id)
        runtime = self._cameras.get(cam_id)
        manager = get_manager()
        session = await manager.session(camera.id)
        stream_running = bool(session and session.live)
        if runtime is None:
            return {"camera_id": cam_id, "camera_name": camera.name, "inference_active": False}
        return {
            "camera_id": cam_id,
            "camera_name": camera.name,
            "inference_active": runtime.active,
            "stream_running": stream_running,
            "frames_analyzed": runtime.frames_analyzed,
            "plates_read": runtime.plates_read,
            "fps": round(runtime.fps, 2),
            "backend": "sim" if self._detector.is_sim else "onnx",
            "ocr_engine": self._ocr.engine,
            "accelerator": self._backend.detect_device()["accelerator"],
        }

    # ------------------------------------------------------------------ #
    # Frame pump
    # ------------------------------------------------------------------ #
    async def _pump(self, runtime: CameraRuntime) -> None:
        cam_uuid = uuid.UUID(runtime.camera_id)
        interval = 1.0 / max(0.5, min(settings.ANPR_INFER_FPS, 60.0))
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
                            pass
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("anpr.pump_error", camera_id=runtime.camera_id, error=str(exc))
                await asyncio.sleep(max(interval, 1.0))

    # ------------------------------------------------------------------ #
    # Pipeline
    # ------------------------------------------------------------------ #
    async def _pipeline_loop(self) -> None:
        while True:
            try:
                item = await self._queue.get()
                batch = [item]
                for _ in range(settings.ANPR_OCR_BATCH_SIZE - 1):
                    try:
                        batch.append(self._queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                await self._process_batch(batch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("anpr.pipeline_error", error=str(exc))
                await asyncio.sleep(0.05)

    async def _process_batch(self, batch: list[FrameItem]) -> None:
        loop = asyncio.get_running_loop()

        # Decode all frames + run plate detection on the executor.
        def _step():
            decoded = [_decode_jpeg(it.jpeg) for it in batch]
            return [(decoded[i], self._detector.detect(decoded[i])) for i in range(len(batch))]

        detections = await loop.run_in_executor(self._executor, _step)

        # Collect rectified plate crops across the batch (index-keyed so frames
        # from the same camera in one batch never collide).
        rectified: dict[int, list[np.ndarray]] = {}
        plate_boxes: dict[int, list[PlateBox]] = {}
        for i, (frame, boxes) in enumerate(detections):
            rectified[i] = [rectify_plate(frame, b) for b in boxes]
            plate_boxes[i] = boxes

        # Batch OCR across all crops in one executor call (amortizes warm-up).
        def _read_all():
            return {i: self._ocr.read_batch(crops) for i, crops in rectified.items()}

        ocr_batches = await loop.run_in_executor(self._executor, _read_all)

        results: list[AnprResult] = []
        for i, item in enumerate(batch):
            cam_id = item.camera_id
            rt = self._cameras.get(cam_id)
            if rt is None or not rt.active:
                continue
            result = await self._compose(
                rt,
                detections[i][0],
                plate_boxes.get(i, []),
                ocr_batches.get(i, []),
                item=item,
            )
            results.append(result)
            await self._emit(result)

    async def _compose(
        self,
        rt: CameraRuntime,
        frame: np.ndarray,
        boxes: list[PlateBox],
        reads,
        *,
        item: FrameItem,
    ) -> AnprResult:
        now_iso = datetime.now(timezone.utc).isoformat()
        result = AnprResult(
            camera_id=rt.camera_id,
            frame_seq=rt.frame_seq,
            ts=now_iso,
            timings=Timings(),
        )
        seq = rt.frame_seq

        for box, read in zip(boxes, reads):
            if not read.normalized:
                continue
            # Validate + correct the OCR read (confusable correction, format
            # rejection, state/RTO parsing). The validated plate is canonical.
            val = self._validator.validate(read.text)
            # Reject impossible formats outright; keep format-valid low-conf
            # reads so low-confidence alerts can still fire.
            if not val.valid or not val.validated_plate:
                continue
            norm = val.validated_plate
            # Vehicle attributes from the full (un-cropped) frame.
            attrs = self._vehicles.recognize(frame, plate_text=norm)
            state, rto = (val.state, val.rto) if val.state else parse_state_rto(norm)
            # Evidence artifacts live on the event (crop paths + hashes).
            ev_doc = self._evidence.save_frame(rt.camera_id, frame)
            plate_crop = rectify_plate(frame, box)
            p_doc = self._evidence.save_plate(rt.camera_id, plate_crop)
            v_doc = self._evidence.save_vehicle(rt.camera_id, frame)

            event = PlateEvent(
                camera_id=rt.camera_id,
                plate=read.text,
                normalized_plate=norm,
                ocr_confidence=read.confidence,
                state_code=state,
                rto_code=rto,
                vehicle=attrs,
                frame_seq=seq,
                ts=now_iso,
                plate_box=box,
                detection_confidence=box.confidence,
                backend="sim" if self._detector.is_sim else "onnx",
                evidence_id=str(uuid.uuid4()) if any(d is not None for d in (ev_doc, p_doc, v_doc)) else None,
            )
            result.plates.append(event)
            result.vehicles.append(attrs)
            if any(d is not None for d in (ev_doc, p_doc, v_doc)):
                result.evidence.append(
                    {
                        "camera_id": rt.camera_id,
                        "plate": read.text,
                        "normalized_plate": norm,
                        "detection_confidence": box.confidence,
                        "ocr_confidence": read.confidence,
                        "ts": now_iso,
                        "frame": ev_doc.to_dict() if ev_doc else None,
                        "plate_crop": p_doc.to_dict() if p_doc else None,
                        "vehicle_crop": v_doc.to_dict() if v_doc else None,
                        "ocr_text": read.text,
                        "validation": val.to_dict() if val else None,
                    }
                )

        rt.tick(time.monotonic())
        rt.plates_read += len(result.plates)
        return result

    async def _emit(self, result: AnprResult) -> None:
        # Persist each plate detection + its evidence + any fired alerts.
        for event in result.plates:
            alerts = self._alerts.evaluate(
                event=event,
                blacklist_match=self._blacklist.match(event.plate),
            )
            package = next(
                (e for e in result.evidence if e["normalized_plate"] == event.normalized_plate),
                None,
            )
            self._submit(event, package, alerts)
        if result.plates:
            self._publish_event(result)

    def _submit(self, event: PlateEvent, package: dict | None, alerts: list[dict]) -> None:
        """Build ORM kwarg dicts and enqueue to the background store."""
        row = {
            "camera_id": event.camera_id,
            "camera_name": (self._cameras.get(event.camera_id).camera_name
                            if self._cameras.get(event.camera_id) else None),
            "plate": event.plate,
            "normalized_plate": event.normalized_plate,
            "state_code": event.state_code,
            "rto_code": event.rto_code,
            "ocr_confidence": event.ocr_confidence,
            "detection_confidence": event.detection_confidence,
            "vehicle_type": event.vehicle.vehicle_type,
            "color": event.vehicle.color,
            "make": event.vehicle.make,
            "model": event.vehicle.model,
            "attribute_confidence": event.vehicle.confidence,
            "x": event.plate_box.x,
            "y": event.plate_box.y,
            "w": event.plate_box.w,
            "h": event.plate_box.h,
            "backend": event.backend,
            "frame_seq": event.frame_seq,
            "ts": event.ts,
            "evidence_id": event.evidence_id,
        }
        self._store.submit_plate(row)

        if package:
            frame = package.get("frame") or {}
            plate_crop = package.get("plate_crop") or {}
            vehicle_crop = package.get("vehicle_crop") or {}
            self._store.submit_evidence(
                {
                    "camera_id": event.camera_id,
                    "plate": event.plate,
                    "normalized_plate": event.normalized_plate,
                    "frame_path": frame.get("path"),
                    "plate_path": plate_crop.get("path"),
                    "vehicle_path": vehicle_crop.get("path"),
                    "ocr_text": package.get("ocr_text"),
                    "frame_hash": frame.get("sha256"),
                    "plate_hash": plate_crop.get("sha256"),
                    "vehicle_hash": vehicle_crop.get("sha256"),
                    "detection_confidence": event.detection_confidence,
                    "ocr_confidence": event.ocr_confidence,
                }
            )

        for alert in alerts:
            self._store.submit_alert(
                {
                    "camera_id": str(alert["camera_id"]),
                    "plate": alert["plate"],
                    "normalized_plate": alert["normalized_plate"],
                    "rule": alert["rule"],
                    "class_name": alert["class_name"],
                    "level": alert["level"],
                    "message": alert["message"],
                    "confidence": alert["confidence"],
                    "count": alert["count"],
                    "first_seen_at": alert["first_seen_at"],
                    "last_seen_at": alert["last_seen_at"],
                    "resolved": alert["resolved"],
                    "resolved_at": alert["resolved_at"],
                }
            )

    def _publish_event(self, result: AnprResult) -> None:
        payload = {
            "type": "plate",
            "camera_id": result.camera_id,
            "frame_seq": result.frame_seq,
            "ts": result.ts,
            "plates": [p.to_dict() for p in result.plates],
            "vehicles": [v.to_dict() for v in result.vehicles],
            "timings": result.timings.to_dict(),
        }
        rt = self._cameras.get(result.camera_id)
        if rt is not None:
            rt.last_event = payload
        self.bus.publish(payload)

    # ------------------------------------------------------------------ #
    # Blacklist sync
    # ------------------------------------------------------------------ #
    async def start_blacklist_sync(self) -> None:
        if self._blacklist_task is not None:
            return
        self._blacklist_task = asyncio.create_task(self._blacklist_loop(), name="anpr-blacklist-sync")

    async def _blacklist_loop(self) -> None:
        from src.core.database import AsyncSessionLocal

        while True:
            await asyncio.sleep(settings.ANPR_BLACKLIST_SYNC_SECONDS)
            try:
                async with AsyncSessionLocal() as db:
                    await self._blacklist.sync_from_db(db)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("anpr.blacklist_sync_error", error=str(exc))

    # ------------------------------------------------------------------ #
    # Stats / sync loop
    # ------------------------------------------------------------------ #
    async def _stats_loop(self) -> None:
        while True:
            await asyncio.sleep(2.0)
            try:
                for rt in self._cameras.values():
                    if not rt.active:
                        continue
                    self.bus.publish(
                        {
                            "type": "stats",
                            "camera_id": rt.camera_id,
                            "camera_name": rt.camera_name,
                            "frames_analyzed": rt.frames_analyzed,
                            "plates_read": rt.plates_read,
                            "fps": round(rt.fps, 2),
                        }
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("anpr.stats_loop_error", error=str(exc))

    async def sync_blacklist(self, db) -> None:
        await self._blacklist.sync_from_db(db)

    def blacklist_match(self, event: PlateEvent) -> dict | None:
        return self._blacklist.match(event.plate)

    # ------------------------------------------------------------------ #
    # Config payload
    # ------------------------------------------------------------------ #
    def config_payload(self) -> dict[str, Any]:
        dev = self._backend.detect_device()
        return {
            "enabled": settings.ANPR_ENABLED,
            "weights_dir": settings.ANPR_WEIGHTS_DIR,
            "accel_mode": settings.ANPR_ACCEL,
            "device": dev,
            "plate": {
                "backend": "sim" if self._detector.is_sim else "onnx",
                "min_confidence": settings.ANPR_PLATE_MIN_CONF,
            },
            "ocr": {
                "engine": self._ocr.engine,
                "min_confidence": settings.ANPR_OCR_MIN_CONF,
                "batch_size": settings.ANPR_OCR_BATCH_SIZE,
            },
            "vehicle": {"backend": "sim" if self._vehicles.is_sim else "onnx"},
            "store_enabled": settings.ANPR_STORE_ENABLED,
            "evidence_enabled": self._evidence.enabled,
            "evidence_dir": settings.ANPR_EVIDENCE_DIR,
            "alert_enabled": settings.ANPR_ALERT_ENABLED,
            "blacklist": self._blacklist.all(),
            "infer_fps": settings.ANPR_INFER_FPS,
        }


def _decode_jpeg(jpeg: bytes):
    import cv2

    return cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)


# ---------------------------------------------------------------------- #
# Module-level singleton
# ---------------------------------------------------------------------- #
_manager: AnprManager | None = None
_manager_lock = Lock()


def get_anpr_manager() -> AnprManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = AnprManager()
    return _manager


__all__ = ["AnprManager", "get_anpr_manager"]

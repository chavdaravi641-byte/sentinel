"""Detection database: batched async persistence for runs/detections/alerts.

Every analyzed frame produces one `InferenceRun` row plus one `Detection` row
per bounding box (stored on every frame, per requirement). A single background
writer task drains a bounded queue and commits grouped batches so the
inference hot path never blocks on the database. Model registry rows are
persisted through the same queue.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from src.core.database import AsyncSessionLocal
from src.core.logging import log
from src.models.inference import (
    AI_MODEL_STATUS_ERROR,
    AI_MODEL_STATUS_LOADED,
    AI_MODEL_STATUS_UNLOADED,
    AiModel,
    Detection,
    InferenceAlert,
    InferenceRun,
)


class DetectionStore:
    """Async writer that batches inference telemetry into Postgres."""

    def __init__(self, enabled: bool = True, max_queue: int = 8000) -> None:
        self.enabled = enabled
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_queue)
        self._task: asyncio.Task | None = None
        self.frames_written = 0
        self.alerts_written = 0

    def start(self) -> None:
        if not self.enabled:
            log.info("ai.storage.disabled")
            return
        if self._task is None:
            self._task = asyncio.create_task(self._writer(), name="ai-storage-writer")
            log.info("ai.storage.started")

    async def shutdown(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    # ------------------------------------------------------------------ #
    # Submit API (caller never blocks)
    # ------------------------------------------------------------------ #
    def submit_runs(self, runs: list[dict[str, Any]], detections: list[dict[str, Any]]) -> None:
        self._put({"kind": "runs", "runs": runs, "detections": detections})

    def submit_alert(self, alert: dict[str, Any]) -> None:
        self._put({"kind": "alert", "alert": alert})

    def submit_model(self, model: dict[str, Any]) -> None:
        self._put({"kind": "model", "model": model})

    def _put(self, item: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            log.warning("ai.storage.queue_full", item=item["kind"], drop="true")

    # ------------------------------------------------------------------ #
    # Writer
    # ------------------------------------------------------------------ #
    async def _writer(self) -> None:
        while True:
            item = await self._queue.get()
            batch = [item]
            for _ in range(200):
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            await self._flush(batch)

    async def _flush(self, batch: list[dict[str, Any]]) -> None:
        runs_batch: list[dict[str, Any]] = []
        dets_batch: list[dict[str, Any]] = []
        alerts_batch: list[dict[str, Any]] = []
        models_batch: list[dict[str, Any]] = []
        for item in batch:
            kind = item.get("kind")
            if kind == "runs":
                runs_batch.extend(item["runs"])
                dets_batch.extend(item["detections"])
            elif kind == "alert":
                alerts_batch.append(item["alert"])
            elif kind == "model":
                models_batch.append(item["model"])
        try:
            async with AsyncSessionLocal() as db:
                if runs_batch:
                    await self._flush_runs(db, runs_batch, dets_batch)
                if alerts_batch:
                    db.add_all([InferenceAlert(**alert) for alert in alerts_batch])
                if models_batch:
                    await self._flush_models(db, models_batch)
                await db.commit()
            self.frames_written += len(runs_batch)
            self.alerts_written += len(alerts_batch)
        except Exception as exc:  # noqa: BLE001 - storage must never crash the engine
            log.warning("ai.storage.flush_failed", error=str(exc), runs=len(runs_batch))

    async def _flush_runs(self, db, runs: list[dict[str, Any]], detections: list[dict[str, Any]]) -> None:
        run_rows = [InferenceRun(**r) for r in runs]
        db.add_all(run_rows)
        await db.flush()
        run_ids_by_seq: dict[tuple[str, int], Any] = {
            (str(r.camera_id), r.frame_seq): r.id for r in run_rows
        }
        det_rows = []
        for d in detections:
            key = (str(d["camera_id"]), int(d["frame_seq"]))
            run_id = run_ids_by_seq.get(key)
            if run_id is None:
                continue
            det_rows.append(Detection(run_id=run_id, **d))
        db.add_all(det_rows)

    async def _flush_models(self, db, models: list[dict[str, Any]]) -> None:
        for m in models:
            m.pop("kind", None)
            row = await db.execute(_model_select(m["name"]))
            model_row = row.scalar_one_or_none()
            status = m.pop("status", AI_MODEL_STATUS_UNLOADED)
            if model_row is None:
                model_row = AiModel(name=m["name"])
                db.add(model_row)
            model_row.status = status
            for key, value in m.items():
                setattr(model_row, key, value)


def _model_select(name: str):
    from sqlalchemy import select
    from src.models.inference import AiModel

    return select(AiModel).where(AiModel.name == name)


def build_model_snapshot(
    *,
    name: str,
    version: str,
    backend: str,
    status: str,
    generation: int,
    accelerator: str | None,
    device: str | None,
    providers: list[str] | None,
    weights_path: str | None,
    classes: list[str] | None,
    error: str | None,
    loaded_at,
) -> dict[str, Any]:
    return {
        "kind": "model",
        "name": name,
        "version": version,
        "backend": backend,
        "status": status,
        "generation": generation,
        "accelerator": accelerator,
        "device": device,
        "providers": providers,
        "weights_path": weights_path,
        "classes": classes,
        "error": error,
        "loaded_at": loaded_at,
    }


__all__ = [
    "AI_MODEL_STATUS_ERROR",
    "AI_MODEL_STATUS_LOADED",
    "AI_MODEL_STATUS_UNLOADED",
    "DetectionStore",
    "build_model_snapshot",
]
"""ANPR persistence: batched async writes for detections/evidence/alerts.

Mirrors the proven Phase 3 `DetectionStore` queue-writer so the pipeline hot
path never blocks on Postgres. The pipeline enqueues ready-to-insert ORM kwarg
dicts (``{}``-style row payloads) which a single background task drains and
commits in grouped batches.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from src.core.database import AsyncSessionLocal
from src.core.logging import log
from src.models.anpr import AnprAlert, EvidenceRecord, PlateDetection


class AnprStore:
    """Async writer that batches ANPR telemetry into Postgres."""

    def __init__(self, enabled: bool = True, max_queue: int = 8000) -> None:
        self.enabled = enabled
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(
            maxsize=max_queue
        )
        self._task: asyncio.Task | None = None
        self.plates_written = 0
        self.alerts_written = 0
        self.evidence_written = 0

    def start(self) -> None:
        if not self.enabled:
            log.info("anpr.store.disabled")
            return
        if self._task is None:
            self._task = asyncio.create_task(self._writer(), name="anpr-store-writer")
            log.info("anpr.store.started")

    async def shutdown(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    # ------------------------------------------------------------------ #
    # Submit API (never blocks the caller)
    # ------------------------------------------------------------------ #
    def submit_plate(self, row: dict[str, Any]) -> None:
        self._put("plate", row)

    def submit_evidence(self, row: dict[str, Any]) -> None:
        self._put("evidence", row)

    def submit_alert(self, row: dict[str, Any]) -> None:
        self._put("alert", row)

    def _put(self, kind: str, row: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            self._queue.put_nowait((kind, row))
        except asyncio.QueueFull:
            log.warning("anpr.store.queue_full", drop="true")

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

    async def _flush(self, batch: list[tuple[str, dict[str, Any]]]) -> None:
        plates: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        for kind, row in batch:
            if kind == "plate":
                plates.append(row)
            elif kind == "evidence":
                evidence.append(row)
            elif kind == "alert":
                alerts.append(row)
        try:
            async with AsyncSessionLocal() as db:
                if plates:
                    db.add_all([PlateDetection(**p) for p in plates])
                if evidence:
                    db.add_all([EvidenceRecord(**e) for e in evidence])
                if alerts:
                    db.add_all([AnprAlert(**a) for a in alerts])
                await db.commit()
            self.plates_written += len(plates)
            self.evidence_written += len(evidence)
            self.alerts_written += len(alerts)
        except Exception as exc:  # noqa: BLE001 - storage must never crash the pipeline
            log.warning(
                "anpr.store.flush_failed",
                error=str(exc),
                plates=len(plates),
                evidence=len(evidence),
                alerts=len(alerts),
            )
        finally:
            # Drop evidence orphaned by a missing plate (defensive only).
            pass


_store: AnprStore | None = None


def get_store() -> AnprStore:
    global _store
    if _store is None:
        _store = AnprStore()
    return _store


__all__ = ["AnprStore", "get_store"]

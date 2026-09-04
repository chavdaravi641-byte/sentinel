"""ANPR alert engine.

Fires realtime + persisted alerts for the ANPR domain:

* **blacklist** — a blacklisted plate appears.
* **low_confidence** — OCR/plate confidence is below a configurable threshold.
* **multi_camera** — the same plate appears on more than one camera within a
  configurable window.
* **reappear** — a previously seen plate returns after a configurable absence.

Like the Phase 3 alert engine this keeps in-memory cooldown/recency state and
emits JSON-safe dicts for the event bus and the evidence/store writer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from src.anpr.primitives import PlateEvent, normalize_plate

RULE_BLACKLIST = "blacklist"
RULE_LOW_CONFIDENCE = "low_confidence"
RULE_MULTI_CAMERA = "multi_camera"
RULE_REAPPEAR = "reappear"


class AnprAlertEngine:
    """Rule-based alerting for the ANPR stream."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        low_conf_threshold: float = 0.45,
        multi_camera_window: float = 120.0,
        reappear_after: float = 3600.0,
        cooldown: float = 60.0,
        blacklist_enabled: bool = True,
        low_conf_enabled: bool = True,
        multi_camera_enabled: bool = True,
        reappear_enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.low_conf_threshold = low_conf_threshold
        self.multi_camera_window = multi_camera_window
        self.reappear_after = reappear_after
        self.cooldown = cooldown
        self.blacklist_enabled = blacklist_enabled
        self.low_conf_enabled = low_conf_enabled
        self.multi_camera_enabled = multi_camera_enabled
        self.reappear_enabled = reappear_enabled
        self._last_fire: dict[str, float] = {}
        self._last_seen: dict[str, str] = {}  # normalized plate -> camera_id
        self._last_seen_ts: dict[str, float] = {}
        self._camera_seen: dict[str, set[str]] = {}  # plate -> {camera_ids}
        self.emitted = 0

    def evaluate(
        self,
        *,
        event: PlateEvent,
        blacklist_match: dict | None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        now_mono = monotonic()
        now_iso = datetime.now(timezone.utc)
        norm = normalize_plate(event.plate)
        fired: list[dict[str, Any]] = []

        def _fire(rule: str, class_name: str, level: str, message: str, conf: float | None) -> None:
            key = f"{norm}:{rule}"
            last = self._last_fire.get(key, -1e9)
            if now_mono - last < self.cooldown:
                return
            self._last_fire[key] = now_mono
            self.emitted += 1
            fired.append(
                {
                    "id": uuid.uuid4(),
                    "camera_id": event.camera_id,
                    "plate": event.plate,
                    "normalized_plate": norm,
                    "rule": rule,
                    "class_name": class_name,
                    "level": level,
                    "message": message,
                    "confidence": conf,
                    "count": 1,
                    "first_seen_at": now_iso,
                    "last_seen_at": now_iso,
                    "resolved": False,
                    "resolved_at": None,
                }
            )

        # 1. Blacklist.
        if self.blacklist_enabled and blacklist_match:
            _fire(
                RULE_BLACKLIST,
                "vehicle",
                "critical" if event.ocr_confidence >= 0.6 else "high",
                f"BLACKLISTED vehicle {event.plate} on {event.camera_id}",
                event.ocr_confidence,
            )

        # 2. Low confidence.
        if self.low_conf_enabled and event.ocr_confidence < self.low_conf_threshold:
            _fire(
                RULE_LOW_CONFIDENCE,
                "plate",
                "info",
                f"Low-confidence plate read {event.plate} (conf={event.ocr_confidence:.2f})",
                event.ocr_confidence,
            )

        # 3. Multi-camera presence.
        seen_cams = self._camera_seen.setdefault(norm, set())
        seen_cams.add(event.camera_id)
        for cam in list(seen_cams):
            if cam == event.camera_id:
                continue
            if self.multi_camera_enabled and self._last_seen_ts.get(
                f"{norm}:{cam}", 0.0
            ) >= now_mono - self.multi_camera_window:
                _fire(
                    RULE_MULTI_CAMERA,
                    "vehicle",
                    "medium",
                    f"Vehicle {event.plate} seen on multiple cameras ({cam} + {event.camera_id})",
                    event.ocr_confidence,
                )
                break

        # 4. Reappearance.
        prev = self._last_seen_ts.get(norm, 0.0)
        if self.reappear_enabled and prev > 0 and (now_mono - prev) >= self.reappear_after:
            _fire(
                RULE_REAPPEAR,
                "vehicle",
                "info",
                f"Vehicle {event.plate} reappeared after {(now_mono - prev):.0f}s",
                event.ocr_confidence,
            )

        # Update recency. Store both the global last-seen stamp (for the
        # reappearance rule) and a per-camera stamp (for the multi-camera rule,
        # which queries `{norm}:{camera_id}`).
        self._last_seen[norm] = event.camera_id
        self._last_seen_ts[norm] = now_mono
        self._last_seen_ts[f"{norm}:{event.camera_id}"] = now_mono
        return fired

    def reset(self) -> None:
        self._last_fire.clear()
        self._last_seen.clear()
        self._last_seen_ts.clear()
        self._camera_seen.clear()


__all__ = ["AnprAlertEngine", "RULE_BLACKLIST", "RULE_LOW_CONFIDENCE", "RULE_MULTI_CAMERA", "RULE_REAPPEAR"]

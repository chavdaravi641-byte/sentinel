"""Rule-based alert engine operating on tracked detections.

Rules (explicitly scoped to the six approved classes — plate recognition, face
recognition, OCR and weapon/fire/fight analysis are out of scope by design):

* ``persistence`` — an object tracked continuously for N frames fires an
  alert (per camera + class + track).
* ``crowd`` — K+ persons simultaneously on one camera.
* ``traffic`` — V+ vehicles (car/bike/bus/truck) simultaneously on one camera.

Cooldowns throttle repeats while a condition persists; alerts are emitted as
JSON-safe dicts for the detection store and the WebSocket event bus.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from src.inference.primitives import BoxResult

_VEHICLES = {"car", "bike", "bus", "truck"}

PERSISTENCE_RULE = "persistence"
CROWD_RULE = "crowd"
TRAFFIC_RULE = "traffic"


class AlertEngine:
    """Evaluates detection streams and emits alert records."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        persistence: int = 4,
        crowd_persons: int = 5,
        traffic_vehicles: int = 6,
        cooldown: float = 30.0,
    ) -> None:
        self.enabled = enabled
        self.persistence = max(2, int(persistence))
        self.crowd_persons = crowd_persons
        self.traffic_vehicles = traffic_vehicles
        self.cooldown = cooldown
        self._last_fire: dict[str, float] = {}
        self.emitted = 0

    def evaluate(
        self,
        *,
        camera_id: str,
        model_name: str,
        tracked: list[tuple[int, BoxResult, int]],
        counts: dict[str, int],
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        now_mono = monotonic()
        now_iso = datetime.now(timezone.utc)
        fired: list[dict[str, Any]] = []

        def _fire(key: str, rule: str, class_name: str, level: str, message: str, conf: float | None, count: int = 1) -> None:
            last = self._last_fire.get(key, -1e9)
            if now_mono - last < self.cooldown:
                return
            self._last_fire[key] = now_mono
            self.emitted += 1
            fired.append(
                {
                    "id": uuid.uuid4(),
                    "camera_id": camera_id,
                    "model_name": model_name,
                    "rule": rule,
                    "class_name": class_name,
                    "level": level,
                    "message": message,
                    "confidence": conf,
                    "count": count,
                    "first_seen_at": now_iso,
                    "last_seen_at": now_iso,
                    "resolved": False,
                    "resolved_at": None,
                }
            )

        # 1. Track persistence rule.
        for tid, box, hits in tracked:
            if hits >= self.persistence:
                key = f"{camera_id}:{PERSISTENCE_RULE}:{box.class_name}:{tid}"
                level = "high" if box.class_name == "person" else "medium"
                _fire(
                    key,
                    PERSISTENCE_RULE,
                    box.class_name,
                    level,
                    f"Sustained {box.class_name} on track #{tid} ({hits} frames)",
                    box.confidence,
                )

        # 2. Crowd rule (persons only — no person-scanning analytics otherwise).
        people = counts.get("person", 0)
        if people >= self.crowd_persons:
            _fire(
                f"{camera_id}:{CROWD_RULE}",
                CROWD_RULE,
                "person",
                "high",
                f"Crowd formation: {people} people on one camera",
                None,
                count=people,
            )

        # 3. Traffic spike rule.
        vehicles = sum(counts.get(v, 0) for v in _VEHICLES)
        if vehicles >= self.traffic_vehicles:
            _fire(
                f"{camera_id}:{TRAFFIC_RULE}",
                TRAFFIC_RULE,
                "vehicle",
                "medium",
                f"Traffic spike: {vehicles} vehicles on one camera",
                None,
                count=vehicles,
            )

        return fired

    def reset(self) -> None:
        self._last_fire.clear()


__all__ = ["AlertEngine"]
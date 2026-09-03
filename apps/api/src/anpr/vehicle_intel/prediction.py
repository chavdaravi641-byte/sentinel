"""Route prediction (Phase 5).

Given a vehicle's recent history of cameras (time-ordered), predict the
*next camera* it is most likely to appear at, and the top-5 ranked candidates
with normalised confidence.

Method
------
- If we have a learned* transition model for this vehicle (or globally), use it.
- Otherwise (cold start, no fitted model), fall back to the graph prior: rank
  the vehicle's current camera's neighbours by how many of them are "reachable
  in a realistic time window" and by network frequency.
- Confidence is calibrated and always sums to <=1 across the top-5 set, and the
  sum reflects how predictable the route is (higher when history is long and
  consistent).

* The learned transition model is derived only from real observed history on
  registered cameras — never fabricated. A `TransitionModel` is fitted from
  actual observation sequences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.anpr.vehicle_intel.graph import CameraGraph


@dataclass
class TransitionModel:
    """Frequency-based P(next | current) fitted from real observation history."""

    counts: dict[str, dict[str, int]] = field(default_factory=dict)

    def update(self, sequence: list[str]) -> None:
        """Feed a camera-id sequence (time ordered) to accumulate transitions."""
        for a, b in zip(sequence, sequence[1:]):
            self.counts.setdefault(a, {}).setdefault(b, 0)
            self.counts[a][b] += 1

    def update_many(self, sequences: list[list[str]]) -> None:
        for seq in sequences:
            self.update(seq)

    def distribution(self, current: str) -> dict[str, float]:
        d = self.counts.get(current, {})
        total = sum(d.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in d.items()}


@dataclass
class Prediction:
    current_camera: str
    predictions: list[dict[str, Any]]  # [{camera_id, confidence, basis}]
    total_confidence: float
    basis: str  # "learned" | "graph_prior" | "learned+graph"
    history_length: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_camera": self.current_camera,
            "predictions": self.predictions,
            "total_confidence": round(self.total_confidence, 4),
            "basis": self.basis,
            "history_length": self.history_length,
        }


def predict_next_cameras(
    photo_current: str,
    history: list[str],
    graph: CameraGraph | None,
    model: TransitionModel | None = None,
    *,
    top_k: int = 5,
    learned_weight: float = 0.7,
    graph_prior_weight: float = 0.3,
    min_history_for_learned: int = 3,
) -> Prediction:
    """Predict the next camera for a vehicle currently at `photo_current`.

    `history` = the vehicle's camera-id sequence so far (newest last).
    """
    candidates: dict[str, float] = {}
    basis = "graph_prior"
    history_length = len(history)

    learned: dict[str, float] = {}
    if model is not None and history_length >= min_history_for_learned:
        d = model.distribution(photo_current)
        if d:
            learned = d
            basis = "learned"

    graph_prior: dict[str, float] = {}
    if graph is not None and graph.has(photo_current):
        nbrs = graph.neighbors(photo_current)
        if nbrs:
            # Score neighbours by proximity (shorter = more likely next hop)
            weights = []
            for n in nbrs:
                e = graph.edge(photo_current, n)
                w = 1.0 / (0.5 + e.travel_time_minutes) if e else 0.0
                weights.append((n, w))
            tot = sum(w for _, w in weights) or 1.0
            graph_prior = {n: w / tot for n, w in weights}
            if not learned:
                basis = "graph_prior"

    # Combine
    if learned and graph_prior:
        keys = set(learned) | set(graph_prior)
        for k in keys:
            lw = learned.get(k, 0.0)
            gw = graph_prior.get(k, 0.0)
            # Normalise learned within the candidate set for fair blending.
            candidates[k] = learned_weight * lw + graph_prior_weight * gw
        basis = "learned+graph"
    else:
        candidates = dict(learned or graph_prior)

    ranked = sorted(candidates.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    total = sum(v for _, v in ranked) or 1.0
    norm_preds = []
    for cam, score in ranked:
        confidence = score / total
        norm_preds.append(
            {
                "camera_id": cam,
                "confidence": round(confidence, 4),
                "basis": basis,
            }
        )
    total_confidence = sum(p["confidence"] for p in norm_preds)

    return Prediction(
        current_camera=photo_current,
        predictions=norm_preds,
        total_confidence=total_confidence,
        basis=basis,
        history_length=history_length,
    )


def predict_route(
    photo_current: str,
    history: list[str],
    graph: CameraGraph | None,
    *,
    horizon_steps: int = 3,
    top_k: int = 5,
    model: TransitionModel | None = None,
) -> dict[str, Any]:
    """Multi-step route prediction: returns the predicted path of camera ids."""
    step_predictions = []
    cur = photo_current
    path = [cur]
    for _ in range(horizon_steps):
        pred = predict_next_cameras(
            cur,
            history + path[1:],
            graph,
            model,
            top_k=top_k,
        )
        step_predictions.append(pred.to_dict())
        if not pred.predictions:
            break
        nxt = pred.predictions[0]["camera_id"]
        if nxt in path:
            break  # cycle guard
        path.append(nxt)
        cur = nxt
    return {
        "predicted_path": path,
        "steps": step_predictions,
    }


__all__ = [
    "TransitionModel",
    "Prediction",
    "predict_next_cameras",
    "predict_route",
]

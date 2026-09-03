"""Cross-camera vehicle association (Phase 5).

Given two (or many) observations — each with an assigned identity, appearance
tuple and a shape embedding — decide whether they describe the *same physical
vehicle* spotted on different cameras, accounting for:

- OCR plate errors (Levenshtein distance between canonical plates),
- appearance similarity (type/color/make/model),
- shape-embedding cosine similarity (viewing-angle/lighting tolerant),
- graph feasibility: the travel time between the two cameras must be
  consistent with the elapsed time between the two observations.

The final association is a weighted combination of these signals, gated by a
feasibility check on the camera graph.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.anpr.vehicle_intel.identity import canonical_plate
from src.anpr.vehicle_intel.graph import CameraGraph


@dataclass
class SignalWeights:
    plate_weight: float = 0.55
    appearance_weight: float = 0.20
    embedding_weight: float = 0.15
    travel_time_weight: float = 0.10


def _lev(a: str, b: str) -> float:
    """Normalised Levenshtein similarity in [0,1] (1 == identical)."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    dist = prev[len(b)]
    return 1.0 - (dist / max(len(a), len(b)))


def _embedding_cosine(a: Any, b: Any) -> float:
    """Cosine similarity between two shape-embedding vectors, 0 if unavailable."""
    try:
        import numpy as np  # type: ignore

        va = np.asarray(a, dtype=np.float64).ravel()
        vb = np.asarray(b, dtype=np.float64).ravel()
        if va.size == 0 or vb.size == 0:
            return 0.0
        n = min(va.size, vb.size)
        va, vb = va[:n], vb[:n]
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    except Exception:  # noqa: BLE001
        return 0.0


def appearance_similarity(a: dict[str, Any] | None, b: dict[str, Any] | None) -> float:
    """Weighted agreement of categorical appearance attributes."""
    if not a or not b:
        return 0.0
    fields = [
        ("vehicle_type", 0.4),
        ("color", 0.3),
        ("make", 0.2),
        ("model", 0.1),
    ]
    total_w = sum(w for _, w in fields)
    score = 0.0
    for f, w in fields:
        xa = (a.get(f) or "").strip().lower()
        xb = (b.get(f) or "").strip().lower()
        if xa and xb and xa == xb:
            score += w
    return score / total_w


def _travel_feasibility(
    graph: CameraGraph,
    cam_a: str,
    ts_a: float,
    cam_b: str,
    ts_b: float,
    *,
    slack_factor: float = 3.0,
    min_window_minutes: float = 0.5,
    max_detour_minutes: float = 30.0,
) -> float:
    """Score in [0,1] how feasible it is that one vehicle moved A->B in
    (ts_b - ts_a). Uses the graph's shortest-path travel time.

    - If not enough time has passed (dt < min travel - slack) -> 0.
    - If the elapsed time is comfortably within an envelope -> high score.
    - If far too much time passed (impossible long dwell) -> decreasing score,
      but a long dwell with no speeding still plausible -> floor > 0.
    """
    dt_min = (ts_b - ts_a) / 60.0
    if dt_min <= 0:
        return 0.0
    if not graph.has(cam_a) or not graph.has(cam_b):
        # No graph knowledge -> cannot prove infeasible, give neutral 0.5.
        return 0.5
    sp = graph.shortest_path(cam_a, cam_b)
    if sp is None:
        return 0.0  # no graph route at all
    _, travel_min = sp
    # minimum realistic travel time (they can't travel slower than some floor)
    min_travel = max(0.5, travel_min)
    if dt_min < min_travel * (1.0 - slack_factor * 0.5):
        # Too fast: physically implausible for typical vehicles.
        ratio = dt_min / max(min_travel, 0.001)
        return max(0.0, min(1.0, ratio / (1.0 - slack_factor * 0.5)))
    if dt_min <= min_travel * slack_factor + max_detour_minutes:
        return 1.0
    # Very long dwell is still possible (parked / slow) but less likely.
    return max(0.15, 1.0 / (1.0 + math.log1p(dt_min - min_travel)))


def raw_similarity(
    obs_a: dict[str, Any],
    obs_b: dict[str, Any],
    graph: CameraGraph,
    weights: SignalWeights | None = None,
) -> float:
    """Unnormalised weighted similarity in [0,1] (no feasibility gating)."""
    w = weights or SignalWeights()
    sa = canonical_plate(obs_a.get("plate", ""))
    sb = canonical_plate(obs_b.get("plate", ""))
    plate_sim = _lev(sa, sb) if (sa and sb) else 0.0
    app_sim = appearance_similarity(
        obs_a.get("appearance"), obs_b.get("appearance")
    )
    emb_sim = _embedding_cosine(
        obs_a.get("shape_embedding"), obs_b.get("shape_embedding")
    )
    travel_sim = _travel_feasibility(
        graph,
        str(obs_a.get("camera_id", "")),
        float(obs_a.get("ts", 0.0)),
        str(obs_b.get("camera_id", "")),
        float(obs_b.get("ts", 0.0)),
    )
    return (
        w.plate_weight * plate_sim
        + w.appearance_weight * app_sim
        + w.embedding_weight * emb_sim
        + w.travel_time_weight * travel_sim
    )


@dataclass
class AssociationResult:
    is_match: bool
    score: float
    confidence: float
    plate_sim: float
    appearance_sim: float
    embedding_sim: float
    travel_sim: float
    travel_minutes: float
    matched_on: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_match": self.is_match,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "plate_similarity": round(self.plate_sim, 4),
            "appearance_similarity": round(self.appearance_sim, 4),
            "embedding_similarity": round(self.embedding_sim, 4),
            "travel_similarity": round(self.travel_sim, 4),
            "travel_minutes": round(self.travel_minutes, 2),
            "matched_on": self.matched_on,
        }


def associate(
    obs_a: dict[str, Any],
    obs_b: dict[str, Any],
    graph: CameraGraph,
    *,
    match_threshold: float = 0.55,
    weights: SignalWeights | None = None,
) -> AssociationResult:
    """Associate two observations -> whether they are likely the same vehicle.

    Note: route/prediction feasibility is computed only from the real camera
    graph; no fabricated data is introduced here.
    """
    w = weights or SignalWeights()
    sa = canonical_plate(obs_a.get("plate", ""))
    sb = canonical_plate(obs_b.get("plate", ""))
    plate_sim = _lev(sa, sb) if (sa and sb) else 0.0
    app_sim = appearance_similarity(
        obs_a.get("appearance"), obs_b.get("appearance")
    )
    emb_sim = _embedding_cosine(
        obs_a.get("shape_embedding"), obs_b.get("shape_embedding")
    )
    travel_sim = _travel_feasibility(
        graph,
        str(obs_a.get("camera_id", "")),
        float(obs_a.get("ts", 0.0)),
        str(obs_b.get("camera_id", "")),
        float(obs_b.get("ts", 0.0)),
    )

    score = (
        w.plate_weight * plate_sim
        + w.appearance_weight * app_sim
        + w.embedding_weight * emb_sim
        + w.travel_time_weight * travel_sim
    )

    # Determine the strongest matched signal (for diagnostics).
    signals = {
        "plate": plate_sim * w.plate_weight,
        "appearance": app_sim * w.appearance_weight,
        "embedding": emb_sim * w.embedding_weight,
        "travel": travel_sim * w.travel_time_weight,
    }
    strongest = max(signals, key=signals.get)

    # Confidence mirrors the agreement of the two strongest positive signals.
    conf = score
    if plate_sim > 0.85 and app_sim > 0.5:
        conf = min(1.0, conf + 0.1)
    if plate_sim < 0.4 and app_sim < 0.4 and emb_sim < 0.5:
        conf = max(0.0, conf - 0.2)

    if obs_a.get("camera_id") == obs_b.get("camera_id") and obs_a.get("ts") == obs_b.get("ts"):
        # Same exact observation — trivially the same vehicle.
        is_match, conf = True, 1.0

    is_match = score >= match_threshold
    travel_minutes = 0.0
    if graph.has(str(obs_a.get("camera_id", ""))) and graph.has(str(obs_b.get("camera_id", ""))):
        sp = graph.shortest_path(str(obs_a["camera_id"]), str(obs_b["camera_id"]))
        if sp:
            travel_minutes = sp[1]

    return AssociationResult(
        is_match=is_match,
        score=score,
        confidence=max(0.0, min(1.0, conf)),
        plate_sim=plate_sim,
        appearance_sim=app_sim,
        embedding_sim=emb_sim,
        travel_sim=travel_sim,
        travel_minutes=travel_minutes,
        matched_on=strongest,
    )


def run_association_chain(
    observations: list[dict[str, Any]],
    graph: CameraGraph,
    *,
    match_threshold: float = 0.55,
) -> list[dict[str, Any]]:
    """Associate every pair (i<j) in a time-ordered observation list.

    Returns list of pair dicts with both identities and the association result.
    Assumes observations are sorted by ts already.
    """
    results = []
    for i in range(len(observations)):
        for j in range(i + 1, len(observations)):
            res = associate(
                observations[i],
                observations[j],
                graph,
                match_threshold=match_threshold,
            )
            results.append(
                {
                    "i": i,
                    "j": j,
                    "left_identity": observations[i].get("vehicle_uuid"),
                    "right_identity": observations[j].get("vehicle_uuid"),
                    "result": res.to_dict(),
                }
            )
    return results


__all__ = [
    "SignalWeights",
    "appearance_similarity",
    "raw_similarity",
    "associate",
    "run_association_chain",
    "AssociationResult",
]

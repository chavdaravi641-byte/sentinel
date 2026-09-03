"""Phase 5.1 — Multi-Modal Probabilistic Vehicle Identity.

Extends the Phase 5 UUID identity engine WITHOUT replacing it. Where Phase 5
keyed identity essentially on the license plate, Phase 5.1 fuses TWELVE signals
probabilistically so identity keeps working when the plate is missing, partial,
mis-OCR'd, swapped or fake.

Signals (the 12 required by the spec)
-------------------------------------
  1  plate_similarity      - canonical Levenshtein similarity
  2  vehicle_embedding     - shape-embedding cosine similarity
  3  vehicle_color         - categorical colour agreement
  4  vehicle_type          - categorical type agreement
  5  vehicle_make          - categorical make agreement
  6  vehicle_model         - categorical model agreement
  7  aspect_ratio          - bbox width/height ratio agreement
  8  wheelbase             - estimated wheelbase-length agreement
  9  roofline              - roofline-shape categorical/hash agreement
  10 travel_time           - graph-consistent transit feasibility
  11 camera_graph          - shortest-path reachability + proximity
  12 historical_sightings  - agreement with the candidate's known history

Design
------
- Every real-world vehicle corresponds to a `VehicleCandidate` that is *keyed
  by the existing Phase 5 UUID* (so the UUID system is preserved). A candidate
  carries an accumulated body of attributes across all its sightings.
- A probe (a new observation) is scored against each candidate with
  **confidence-weighted fusion**: each signal contributes a similarity and has
  a reliability weight; the *effective* weight is `reliability * availability`.
  Crucially, the plate reliability is modulated by the observed plate
  confidence, so when plate confidence is low the plate weight is **reduced
  automatically**, and when the plate is missing its availability is 0 (others
  take over). Identity therefore never *depends primarily* on the plate.
- The winning fused score drives `identity_confidence`, `feature_contributions`,
  `ambiguity_score` and a structured `identity_reasoning`.
- If no candidate is close enough, a **new** identity is created using the same
  Phase 5 `assign_identity` keying (plate UUID when trustworthy, else
  embedding/appearance UUID), guaranteeing we never double-assign.

Ambiguity
---------
`ambiguity_score` = 1 - margin, where margin is the gap between the best and
second-best fused score. Low ambiguity means the answer is clear; high
ambiguity (near-tie) flags a vehicle that needs a human or more data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.anpr.vehicle_intel.identity import (
    canonical_plate,
    assign_identity,
)
from src.anpr.vehicle_intel.association import _embedding_cosine
from src.anpr.vehicle_intel.graph import CameraGraph


# --------------------------------------------------------------------------- #
# Candidate model
# --------------------------------------------------------------------------- #
@dataclass
class VehicleCandidate:
    """An entity in the identity gallery, keyed by the existing UUID."""

    vehicle_uuid: str
    canonical_plate: str = ""
    plate_confidence: float = 0.0
    # Modal appearance attributes.
    color: str = ""
    vehicle_type: str = ""
    make: str = ""
    model: str = ""
    aspect_ratio: float | None = None
    wheelbase: float | None = None
    roofline: str = ""
    embedding: Any = None
    # Historical sightings: list of (camera_id, ts).
    history: list[tuple[str, float]] = field(default_factory=list)
    sighting_count: int = 0

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = []

    def last_sighting(self) -> tuple[str, float] | None:
        return self.history[-1] if self.history else None

    def basis_for_label(self) -> str:
        if self.canonical_plate:
            return "plate"
        if self.embedding is not None:
            return "appearance"
        return "appearance"


def aggregate_candidate(
    appearance: dict[str, Any] | None = None,
    *,
    plate: str = "",
    plate_confidence: float = 0.0,
    aspect_ratio: float | None = None,
    wheelbase: float | None = None,
    roofline: str = "",
    embedding: Any = None,
    camera_id: str = "",
    ts: float = 0.0,
) -> dict[str, Any]:
    """Collapse one observation into a candidate-attribute dict (for a gallery
    build from sighting history). Missing attributes remain empty so signals
    can be marked unavailable."""
    return {
        "canonical_plate": canonical_plate(plate),
        "plate_confidence": plate_confidence,
        "color": (appearance or {}).get("color") or "",
        "vehicle_type": (appearance or {}).get("vehicle_type") or "",
        "make": (appearance or {}).get("make") or "",
        "model": (appearance or {}).get("model") or "",
        "aspect_ratio": aspect_ratio,
        "wheelbase": wheelbase,
        "roofline": roofline or "",
        "embedding": embedding,
        "camera_id": camera_id,
        "ts": ts,
    }


# --------------------------------------------------------------------------- #
# Individual signal similarities
# --------------------------------------------------------------------------- #
def _plate_sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    n = max(len(a), len(b))
    if n == 0:
        return 0.0
    dist = _edit_distance(a, b)
    return max(0.0, 1.0 - dist / n)


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[len(b)]


def _cat_sim(a: str, b: str) -> float:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if a and b and a == b:
        return 1.0
    return 0.0


def _ratio_sim(a: float | None, b: float | None, *, tol: float = 0.12) -> float:
    """Agreement of two scalar measurements (aspect ratio / wheelbase)."""
    if a is None or b is None or a <= 0 or b <= 0:
        return 0.0
    diff = abs(a - b) / max(a, b)
    if diff <= tol:
        return 1.0 - diff
    return max(0.0, 1.0 - 2.0 * diff)


def _travel_sim(
    graph: CameraGraph,
    ref_cam: str,
    ref_ts: float,
    probe_cam: str,
    probe_ts: float,
) -> float:
    if not ref_cam or not probe_cam or probe_ts <= ref_ts:
        return 0.0
    if not graph.has(ref_cam) or not graph.has(probe_cam):
        return 0.5
    sp = graph.shortest_path(ref_cam, probe_cam)
    if sp is None:
        return 0.0
    _, travel_min = sp
    dt_min = (probe_ts - ref_ts) / 60.0
    travel_min = max(0.5, travel_min)
    if dt_min < travel_min * 0.5:
        return 0.0  # too fast to be plausible
    if dt_min <= travel_min * 3.0 + 30:
        return 1.0
    return max(0.15, 1.0 / (1.0 + math.log1p(dt_min - travel_min)))


def _graph_sim(graph: CameraGraph, ref_cam: str, probe_cam: str) -> float:
    if not ref_cam or not probe_cam:
        return 0.0
    if ref_cam == probe_cam:
        return 1.0
    if not graph.has(ref_cam) or not graph.has(probe_cam):
        return 0.5
    e = graph.edge(ref_cam, probe_cam)
    if e is not None:
        return 1.0 / (1.0 + e.travel_time_minutes / 15.0)
    sp = graph.shortest_path(ref_cam, probe_cam)
    if sp is None:
        return 0.0
    return 1.0 / (1.0 + sp[1] / 30.0)


def _history_sim(
    history: list[tuple[str, float]],
    ref_cam: str,
    ref_ts: float,
    probe_cam: str,
    probe_ts: float,
) -> float:
    """Similarity based on the candidate's historical sightings — do the ref and
    probe fits a known movement pattern (same camera window / recurring
    route)?"""
    if not history:
        return 0.0
    best = 0.0
    for (cam, t) in history:
        s = 0.0
        if cam == probe_cam:
            s = 0.6
        if abs(t - probe_ts) < 30 * 60:
            s = max(s, 0.6)
        elif abs(t - probe_ts) < 6 * 3600:
            s = max(s, 0.3)
        if ref_cam and cam == ref_cam:
            s = max(s, 0.8)
        best = max(best, s)
    return best


# --------------------------------------------------------------------------- #
# Confidence-weighted fusion
# --------------------------------------------------------------------------- #
SIGNAL_NAMES = [
    "plate_similarity",
    "vehicle_embedding",
    "vehicle_color",
    "vehicle_type",
    "vehicle_make",
    "vehicle_model",
    "aspect_ratio",
    "wheelbase",
    "roofline",
    "travel_time",
    "camera_graph",
    "historical_sightings",
]

# Base reliability of each signal (how trustworthy it is when available).
_SIGNAL_RELIABILITY: dict[str, float] = {
    "plate_similarity": 0.34,
    "vehicle_embedding": 0.20,
    "vehicle_color": 0.10,
    "vehicle_type": 0.10,
    "vehicle_make": 0.06,
    "vehicle_model": 0.05,
    "aspect_ratio": 0.04,
    "wheelbase": 0.03,
    "roofline": 0.03,
    "travel_time": 0.03,
    "camera_graph": 0.01,
    "historical_sightings": 0.01,
}


@dataclass
class FusedIdentity:
    identity_uuid: str
    identity_confidence: float
    identity_reasoning: list[str]
    feature_contributions: dict[str, float]
    ambiguity_score: float
    basis: str
    matched_candidate_uuid: str | None = None
    raw_score: float = 0.0
    runner_up_score: float = 0.0
    plate_weight_used: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_uuid": self.identity_uuid,
            "identity_confidence": round(self.identity_confidence, 4),
            "identity_reasoning": list(self.identity_reasoning),
            "feature_contributions": {
                k: round(v, 4) for k, v in self.feature_contributions.items()
            },
            "ambiguity_score": round(self.ambiguity_score, 4),
            "basis": self.basis,
            "matched_candidate_uuid": self.matched_candidate_uuid,
            "raw_score": round(self.raw_score, 4),
            "runner_up_score": round(self.runner_up_score, 4),
            "plate_weight_used": round(self.plate_weight_used, 4),
        }


def effective_plate_weight(ocr_confidence: float, plate_present: bool) -> float:
    """Auto-reduce the plate reliability as plate confidence drops.

    - missing plate -> 0 (other signals take over)
    - very low confidence -> small residual weight
    - plate_confidence converges to full reliability near 1.0
    """
    if not plate_present:
        return 0.0
    rel = _SIGNAL_RELIABILITY["plate_similarity"]
    # Scale down below the trust threshold (0.45), ramping toward normal.
    c = ocr_confidence
    if c >= 0.45:
        return rel
    # Between 0 and 0.45: weight scales with a floor of ~15% of nominal.
    return rel * (0.15 + 0.85 * (c / 0.45))


def _weight_for(reliability: float, availability: bool) -> float:
    return reliability if availability else 0.0


def _probe_signal_values(probe: dict[str, Any]) -> dict[str, Any]:
    """Extract probe attribute values used by all signals."""
    appearance = probe.get("appearance") or {}
    emb = probe.get("shape_embedding") or probe.get("embedding")
    if emb is not None and not isinstance(emb, (list, tuple)):
        emb = None
    return {
        "plate": canonical_plate(probe.get("plate", "")),
        "plate_conf": float(probe.get("ocr_confidence", 0.0)),
        "color": str(appearance.get("color") or ""),
        "vehicle_type": str(appearance.get("vehicle_type") or ""),
        "make": str(appearance.get("make") or ""),
        "model": str(appearance.get("model") or ""),
        "aspect_ratio": probe.get("aspect_ratio"),
        "wheelbase": probe.get("wheelbase"),
        "roofline": probe.get("roofline") or "",
        "embedding": emb,
        "camera_id": str(probe.get("camera_id", "")),
        "ts": float(probe.get("ts", 0.0)),
    }


def score_candidate(
    probe: dict[str, Any],
    candidate: "VehicleCandidate",
    graph: CameraGraph | None = None,
) -> dict[str, Any]:
    """Score a probe against one candidate.

    Returns dict {signal_name: similarity} plus `_used_plate_weight`.
    """
    p = _probe_signal_values(probe)
    sig: dict[str, float] = {}
    sig["plate_similarity"] = _plate_sim(p["plate"], candidate.canonical_plate)
    sig["vehicle_embedding"] = _embedding_cosine(p["embedding"], candidate.embedding)
    sig["vehicle_color"] = _cat_sim(p["color"], candidate.color)
    sig["vehicle_type"] = _cat_sim(p["vehicle_type"], candidate.vehicle_type)
    sig["vehicle_make"] = _cat_sim(p["make"], candidate.make)
    sig["vehicle_model"] = _cat_sim(p["model"], candidate.model)
    sig["aspect_ratio"] = _ratio_sim(p["aspect_ratio"], candidate.aspect_ratio)
    sig["wheelbase"] = _ratio_sim(p["wheelbase"], candidate.wheelbase)
    sig["roofline"] = _cat_sim(p["roofline"], candidate.roofline)

    last = candidate.last_sighting()
    ref_cam, ref_ts = (last[0], last[1]) if last else ("", 0.0)

    if graph is not None:
        sig["travel_time"] = _travel_sim(
            graph, ref_cam, ref_ts, p["camera_id"], p["ts"]
        )
        sig["camera_graph"] = _graph_sim(graph, ref_cam, p["camera_id"])
    else:
        sig["travel_time"] = 0.0
        sig["camera_graph"] = 0.0

    sig["historical_sightings"] = _history_sim(
        candidate.history, ref_cam, ref_ts, p["camera_id"], p["ts"]
    )

    plate_used = effective_plate_weight(
        p["plate_conf"], bool(p["plate"])
    )
    sig["_used_plate_weight"] = plate_used
    return sig


def _dedupe_reasoning(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for r in reasons:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out[:8]


def fuse_identity(
    probe: dict[str, Any],
    candidates: list["VehicleCandidate"],
    graph: CameraGraph | None = None,
    *,
    match_threshold: float = 0.40,
) -> FusedIdentity:
    """Run confidence-weighted fusion of the probe against the gallery.

    Returns a `FusedIdentity` with all required fields. When no candidate
    clears the threshold, a NEW identity is minted through the Phase 5 UUID
    keying (plate > embedding > appearance), so we never replace the UUID
    system and never double-assign plates.
    """
    p = _probe_signal_values(probe)
    plate_present = bool(p["plate"])
    plate_weight_used = effective_plate_weight(p["plate_conf"], plate_present)

    scored: list[tuple[float, "VehicleCandidate", dict[str, float]]] = []
    for cand in candidates:
        sig = score_candidate(probe, cand, graph)

        # weights: reliability x availability, with plate weight already
        # confidence-modulated.
        def _avail(name: str) -> bool:
            if name == "plate_similarity":
                return plate_present
            if name == "vehicle_embedding":
                return p["embedding"] is not None and cand.embedding is not None
            if name in ("aspect_ratio", "wheelbase"):
                return True  # availability handled by _ratio_sim returning 0
            return True

        raw = 0.0
        contributions: dict[str, float] = {}
        for name in SIGNAL_NAMES:
            rel = _SIGNAL_RELIABILITY[name]
            w = plate_weight_used if name == "plate_similarity" else rel
            if not _avail(name):
                w = 0.0
            contrib = w * sig[name]
            contributions[name] = contrib
            raw += contrib

        scored.append((raw, cand, contributions))

    if not scored:
        scored = [(0.0, VehicleCandidate(vehicle_uuid=""), {})]

    scored.sort(key=lambda x: x[0], reverse=True)
    best_raw, best_cand, best_contrib = scored[0]
    runner_raw = scored[1][0] if len(scored) > 1 else 0.0

    # Fused confidence: normalise raw by the max possible weight sum and clip.
    max_possible = plate_weight_used + sum(
        _SIGNAL_RELIABILITY[n] for n in SIGNAL_NAMES if n != "plate_similarity"
    )
    conf = 0.0
    if max_possible > 0:
        conf = best_raw / max_possible

    # Margin / ambiguity
    margin = best_raw - runner_raw
    ambiguity = 1.0 - min(1.0, max(0.0, margin / (max_possible + 1e-9)))

    matched = best_raw >= match_threshold

    # ---- Build reasoning -------------------------------------------------- #
    reasons: list[str] = []

    if not plate_present:
        reasons.append("plate_missing: identity built from non-plate signals")
    elif p["plate_conf"] < 0.45:
        reasons.append(
            f"plate_confidence_low({p['plate_conf']:.2f}): plate weight auto-reduced to {plate_weight_used:.2f}"
        )

    if matched:
        reasons.append(f"matched_candidate={best_cand.vehicle_uuid[:8]}")
        top_contrib = sorted(
            best_contrib.items(), key=lambda kv: kv[1], reverse=True
        )[:4]
        for name, val in top_contrib:
            if val > 0.01:
                reasons.append(f"{name}={val:.2f}")
        if best_cand.sighting_count:
            reasons.append(f"candidate_history={best_cand.sighting_count} sightings")
    else:
        reasons.append("no_candidate_above_threshold: minting new identity")

    # ---- UUID derivation (preserves Phase 5 system) ----------------------- #
    if matched:
        identity_uuid = best_cand.vehicle_uuid
        basis = "matched:" + best_cand.basis_for_label()
    else:
        base = assign_identity(
            plate=p["plate"],
            appearance=probe.get("appearance"),
            shape_embedding=p["embedding"],
            ocr_confidence=p["plate_conf"],
        )
        identity_uuid = base.vehicle_uuid
        basis = base.basis

    return FusedIdentity(
        identity_uuid=identity_uuid,
        identity_confidence=conf,
        identity_reasoning=_dedupe_reasoning(reasons),
        feature_contributions=dict(best_contrib),
        ambiguity_score=ambiguity,
        basis=basis,
        matched_candidate_uuid=(best_cand.vehicle_uuid if matched else None),
        raw_score=best_raw,
        runner_up_score=runner_raw,
        plate_weight_used=plate_weight_used,
    )


__all__ = [
    "VehicleCandidate",
    "aggregate_candidate",
    "FusedIdentity",
    "fuse_identity",
    "score_candidate",
    "effective_plate_weight",
    "SIGNAL_NAMES",
]

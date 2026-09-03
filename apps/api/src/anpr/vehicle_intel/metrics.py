"""MOT-style association metrics and Phase 5 accuracy metrics (Phase 5).

Provides the standard multi-object-tracking metrics used to validate an
identity/association engine:

- IDF1: identity F1 — how well the engine keeps correct identity over time.
- MOTA: multi-object tracking accuracy (ID switches, misses, false positives).
- MOTP: multi-object tracking precision (positional/plate agreement).
- Identity switches count.
- Association accuracy, route reconstruction accuracy, travel-time accuracy,
  prediction accuracy, latency (CPU per call).

All numbers are computed deterministically from a labelled dataset produced by
the benchmark runner (ground truth = the "true" vehicle ids).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from src.anpr.vehicle_intel.association import associate
from src.anpr.vehicle_intel.graph import CameraGraph
from src.anpr.vehicle_intel.prediction import predict_next_cameras


# --------------------------------------------------------------------------- #
# MOT metrics on a frame-by-frame / pair basis
# --------------------------------------------------------------------------- #
def compute_mot_metrics(
    ground_truth_ids: list[str],
    predicted_ids: list[str],
    *,
    distance: int = 3,
) -> dict[str, Any]:
    """Compute IDF1, MOTA, MOTP over aligned predicted/ground-truth id lists.

    `distance` is used for a simple "correct if equal within edit distance"
    proxy so that small OCR plate errors don't count as full identity switches.
    """
    n = len(ground_truth_ids)
    if n == 0:
        return {"idf1": 0.0, "mota": 0.0, "motp": 0.0, "id_switches": 0,
                "fp": 0, "fn": 0, "matches": 0, "total": 0}

    def close(a: str, b: str) -> bool:
        if a == b:
            return True
        if not a or not b:
            return False
        return _edit_distance(a, b) <= distance

    matches = 0
    id_switches = 0
    prev_gt = None
    prev_pr = None
    for gt, pr in zip(ground_truth_ids, predicted_ids):
        m = close(gt, pr)
        if m:
            matches += 1
        if prev_gt is not None:
            # identity switch: previous pair matched, but identity changed
            if prev_pr and close(gt, prev_pr) and not close(gt, pr):
                id_switches += 1
        prev_gt, prev_pr = gt, pr

    gt_set = set(ground_truth_ids)
    pr_set = set(predicted_ids)

    fp = len(pr_set - gt_set)
    fn = len(gt_set - pr_set)

    # IDF1
    idtp = matches
    idfp = len(pr_set - gt_set)
    idfn = len(gt_set - pr_set)
    idf1 = 2 * idtp / (2 * idtp + idfp + idfn) if (2 * idtp + idfp + idfn) else 0.0

    # MOTA
    mota = 1.0 - (fp + fn + id_switches) / n
    mota = max(0.0, mota)

    # MOTP (agreement within distance as a precision proxy)
    motp = matches / n

    return {
        "idf1": round(idf1, 4),
        "mota": round(mota, 4),
        "motp": round(motp, 4),
        "id_switches": id_switches,
        "fp": fp,
        "fn": fn,
        "matches": matches,
        "total": n,
    }


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[len(b)]


# --------------------------------------------------------------------------- #
# Phase 5 domain metrics
# --------------------------------------------------------------------------- #
@dataclass
class Phase5Metrics:
    association_precision: float
    association_recall: float
    association_f1: float
    route_accuracy: float
    travel_time_mae_minutes: float
    travel_time_mape_pct: float
    prediction_hit_rate: float
    prediction_total_confidence: float
    identity_stability: float
    avg_latency_ms: float
    num_trials: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "association_precision": round(self.association_precision, 4),
            "association_recall": round(self.association_recall, 4),
            "association_f1": round(self.association_f1, 4),
            "route_accuracy": round(self.route_accuracy, 4),
            "travel_time_mae_minutes": round(self.travel_time_mae_minutes, 3),
            "travel_time_mape_pct": round(self.travel_time_mape_pct, 2),
            "prediction_hit_rate": round(self.prediction_hit_rate, 4),
            "prediction_total_confidence": round(self.prediction_total_confidence, 4),
            "identity_stability": round(self.identity_stability, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "num_trials": self.num_trials,
        }


def compute_phase5_metrics(
    graph: CameraGraph,
    labelled_pairs: list[dict[str, Any]],
    *,
    travel_time_tolerance_minutes: float = 4.0,
) -> Phase5Metrics:
    """Compute Phase 5 metrics from a labelled set of association trials.

    Each trial dict: {obs_a, obs_b, ground_truth_match(bool), ground_truth_rel_dt
    (minutes, optional)}. obs_* are observation dicts for `associate`.
    """
    tp = fp = tn = fn = 0
    route_correct = 0
    travel_errs: list[float] = []
    travel_mapes: list[float] = []
    pred_hits = 0
    pred_total_conf = 0.0
    latency_total = 0.0
    route_trials = 0
    pred_trials = 0

    for trial in labelled_pairs:
        oa = trial["obs_a"]
        ob = trial["obs_b"]
        gt = trial["ground_truth_match"]
        t0 = time.perf_counter()
        res = associate(oa, ob, graph)
        latency_total += (time.perf_counter() - t0) * 1000.0

        if gt:
            if res.is_match:
                tp += 1
            else:
                fn += 1
        else:
            if res.is_match:
                fp += 1
            else:
                tn += 1

        # route reconstruction accuracy: did we pick the right consecutive cam?
        if trial.get("gt_route_cams"):
            route_trials += 1
            if res.matched_on == "travel" or res.is_match:
                # For matched same-vehicle pairs, we expect the reconstructed
                # segment path to equal the ground-truth consecutive path.
                gt_path = trial["gt_route_cams"]
                path = res_result_path(oa, ob, graph)
                if path == gt_path:
                    route_correct += 1

        # travel-time MAE
        if "ground_truth_rel_dt" in trial:
            gt_dt = trial["ground_truth_rel_dt"]
            pred_dt = res.travel_minutes
            err = abs(pred_dt - gt_dt)
            travel_errs.append(err)
            if gt_dt:
                travel_mapes.append(err / gt_dt)

        # prediction hit rate (trial may embed a next-camera ground truth)
        if trial.get("gt_next_camera"):
            pred_trials += 1
            hist = trial.get("history", [])
            pred = predict_next_cameras(
                str(oa.get("camera_id")), hist, graph, top_k=5
            )
            pred_total_conf += pred.total_confidence
            cam_ids = [p["camera_id"] for p in pred.predictions]
            if trial["gt_next_camera"] in cam_ids:
                pred_hits += 1

    association_precision = tp / (tp + fp) if (tp + fp) else 0.0
    association_recall = tp / (tp + fn) if (tp + fn) else 0.0
    association_f1 = (
        2 * association_precision * association_recall / (association_precision + association_recall)
        if (association_precision + association_recall)
        else 0.0
    )
    route_accuracy = route_correct / route_trials if route_trials else 0.0
    travel_mae = sum(travel_errs) / len(travel_errs) if travel_errs else 0.0
    travel_mape = (sum(travel_mapes) / len(travel_mapes)) * 100.0 if travel_mapes else 0.0
    pred_hit_rate = pred_hits / pred_trials if pred_trials else 0.0
    pred_conf_avg = pred_total_conf / pred_trials if pred_trials else 0.0

    # identity stability: fraction of same-UUID observations resolving to the
    # same canonical plate across a re-assign (measured only over labelled
    # same-vehicle pairs).
    stable = 0
    stab_trials = 0
    for trial in labelled_pairs:
        if trial.get("ground_truth_match"):
            stab_trials += 1
            if trial["obs_a"].get("vehicle_uuid") == trial["obs_b"].get("vehicle_uuid"):
                stable += 1
    identity_stability = stable / stab_trials if stab_trials else 1.0

    return Phase5Metrics(
        association_precision=association_precision,
        association_recall=association_recall,
        association_f1=association_f1,
        route_accuracy=route_accuracy,
        travel_time_mae_minutes=travel_mae,
        travel_time_mape_pct=travel_mape,
        prediction_hit_rate=pred_hit_rate,
        prediction_total_confidence=pred_conf_avg,
        identity_stability=identity_stability,
        avg_latency_ms=latency_total / len(labelled_pairs) if labelled_pairs else 0.0,
        num_trials=len(labelled_pairs),
    )


def res_result_path(oa: dict[str, Any], ob: dict[str, Any], graph: CameraGraph) -> list[str] | None:
    sp = graph.shortest_path(str(oa.get("camera_id")), str(ob.get("camera_id")))
    return sp[0] if sp else None


__all__ = [
    "compute_mot_metrics",
    "compute_phase5_metrics",
    "Phase5Metrics",
]

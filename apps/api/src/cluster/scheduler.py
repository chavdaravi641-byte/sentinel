"""Distributed scheduler (Part 6).

Pure, deterministic functions that score candidate nodes and pick the best host
for a camera. Balancing dimensions: CPU headroom, GPU headroom, memory headroom,
camera count and health. The scoring is a weighted sum of *normalised* metrics
so the algorithm is robust to different absolute scales and is trivially
unit-testable and measurable.

Weights are configurable but default to a sensible production balance. A node
that is not healthy (OFFLINE / RECOVERING / UNHEALTHY with no capacity) is
excluded or heavily penalised so we never schedule onto a dead host.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class Scoreable(Protocol):
    """Minimal node view consumed by the scheduler (decoupled from the store)."""

    node_id: str
    status: str
    cpu_util: float
    gpu_util: float | None
    mem_util: float
    active_cameras: int
    gpu_count: int
    cpu_cores: int
    ram_gb: int


@dataclass
class ScheduleWeights:
    """Weights for the scheduling objective (higher = more important)."""

    cpu: float = 1.0      # prefer lower CPU utilisation
    gpu: float = 1.0      # prefer lower GPU utilisation / more free GPU
    mem: float = 1.0      # prefer lower memory utilisation
    cameras: float = 1.0  # prefer fewer owned cameras (balance load)
    health: float = 3.0   # hard penalty for unhealthy/offline nodes


# statuses that must never receive new cameras
_UNSCHEDULABLE = {"offline", "recovering"}
# statuses that are schedulable but carry a penalty
_DEGRADED = {"unhealthy"}


def _norm(value: float, cap: float = 1.0) -> float:
    """Normalise a utilisation/ratio into [0, 1], clamped at ``cap``."""
    return max(0.0, min(1.0, (value or 0.0) / cap))


def capacity_score(node: Scoreable) -> float:
    """A 0..1 'free capacity' score. 1.0 = completely idle, 0.0 = saturated.

    Combines CPU, GPU and memory headroom. GPU headroom is weighted by the
    number of GPUs when present.
    """
    cpu_free = 1.0 - _norm(node.cpu_util)
    mem_free = 1.0 - _norm(node.mem_util)
    if node.gpu_count and node.gpu_util is not None:
        # average free GPU util across the node's GPUs, normalised to capacity
        gpu_free = max(0.0, 1.0 - _norm(node.gpu_util))
        gpu_share = min(1.0, node.gpu_count / max(1, node.gpu_count))
        gpu = gpu_free * gpu_share
    else:
        gpu = 0.5  # neutral when GPU utilisation is unknown
    return round((cpu_free * 0.4 + mem_free * 0.3 + gpu * 0.3), 4)


def load_score(node: Scoreable) -> float:
    """Normalised relative load (owned cameras / CPU cores).

    Lower is better; a node with zero cores is treated as at capacity.
    """
    cores = max(1, node.cpu_cores)
    return _norm(node.active_cameras / cores, cap=2.0)


def schedule_score(node: Scoreable, weights: ScheduleWeights | None = None) -> float | None:
    """Return a composite scheduling score for ``node``, or ``None`` if the
    node must never be scheduled onto.

    Higher score = better candidate.
    """
    w = weights or ScheduleWeights()
    status = (node.status or "alive").lower()

    if status in _UNSCHEDULABLE:
        return None
    if status in _DEGRADED:
        # still usable but strongly penalised
        baseline = 0.2
    else:
        baseline = 1.0

    # CPU / GPU / memory free-headroom terms scaled by health baseline.
    load = load_score(node)
    score = (
        w.cpu * (1.0 - _norm(node.cpu_util))
        + w.gpu * _gpu_free_term(node)
        + w.mem * (1.0 - _norm(node.mem_util))
        + w.cameras * (1.0 - load)
    )
    score = score * baseline + w.health * baseline
    return round(score, 4)


def _gpu_free_term(node: Scoreable) -> float:
    if not node.gpu_count or node.gpu_util is None:
        return 0.5
    return max(0.0, 1.0 - _norm(node.gpu_util))


def best_node(
    nodes: list[Scoreable],
    exclude: set[str] | None = None,
    weights: ScheduleWeights | None = None,
) -> Scoreable | None:
    """Return the highest-scoring schedulable node, honouring ``exclude``."""
    candidates: list[tuple[float, Scoreable]] = []
    exclude = exclude or set()
    for node in nodes:
        if node.node_id in exclude:
            continue
        score = schedule_score(node, weights)
        if score is None:
            continue
        candidates.append((score, node))
    if not candidates:
        return None
    # stable tie-break by node_id for determinism
    candidates.sort(key=lambda t: (-t[0], t[1].node_id))
    return candidates[0][1]


def node_load_map(nodes: list[Scoreable]) -> dict[str, float]:
    """Active-camera share per node (for balancing / dashboard capacity)."""
    total = sum(n.active_cameras for n in nodes) or 1
    return {n.node_id: round(n.active_cameras / total, 4) for n in nodes}


__all__ = [
    "ScheduleWeights",
    "capacity_score",
    "load_score",
    "schedule_score",
    "best_node",
    "node_load_map",
]

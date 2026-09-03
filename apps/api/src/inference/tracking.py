"""Lightweight IoU-overlap object tracker.

Associates detections across frames so every object carries a stable `track_id`
(per worker). Pure IoU + deadline matching is more than adequate for the fixed
6-class traffic/person model this Phase targets and avoids heavyweight frame
embedding costs on CPU hosts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

from src.inference.primitives import BoxResult


@dataclass
class TrackState:
    track_id: int
    class_name: str
    box: BoxResult
    last_seen: float = field(default_factory=monotonic)
    hits: int = 1
    misses: int = 0


class IoUTracker:
    """Greedy IoU assignment with expiry; one instance per camera worker."""

    def __init__(self, max_age: float = 2.0, iou_threshold: float = 0.25) -> None:
        self.max_age = max_age
        self.iou_threshold = iou_threshold
        self._tracks: dict[int, TrackState] = {}
        self._next_id = 1

    def update(self, detections: list[BoxResult], now: float | None = None) -> list[tuple[int, BoxResult, int]]:
        """Associate detections with existing tracks.

        Returns `(track_id, box, hits)` for every matched/unmatched detection.
        Tracks whose class changes are re-keyed as new tracks.
        """
        now = now or monotonic()
        # expire stale tracks
        for tid in list(self._tracks.keys()):
            if now - self._tracks[tid].last_seen > self.max_age:
                del self._tracks[tid]

        result: list[tuple[int, BoxResult, int]] = []
        used_tracks: set[int] = set()

        # Order detections by confidence for greedy assignment quality.
        ordered = sorted(detections, key=lambda b: -b.confidence)
        candidates = sorted(self._tracks.values(), key=lambda t: -t.box.confidence)

        for box in ordered:
            best_tid: int | None = None
            best_iou = 0.0
            for track in candidates:
                if track.track_id in used_tracks:
                    continue
                if track.class_name != box.class_name:
                    continue
                iou = track.box.iou(box)
                if iou > best_iou:
                    best_iou = iou
                    best_tid = track.track_id
            if best_tid is not None and best_iou >= self.iou_threshold:
                track = self._tracks[best_tid]
                track.box = box
                track.last_seen = now
                track.hits += 1
                track.misses = 0
                used_tracks.add(best_tid)
                result.append((best_tid, box, track.hits))
            else:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = TrackState(track_id=tid, class_name=box.class_name, box=box, last_seen=now)
                used_tracks.add(tid)
                result.append((tid, box, 1))

        # bump misses for unobserved tracks (kept alive for max_age)
        for tid, track in self._tracks.items():
            if tid not in used_tracks:
                track.misses += 1
                track.last_seen = now
        return result

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1

    @property
    def active(self) -> int:
        return len(self._tracks)


__all__ = ["IoUTracker"]
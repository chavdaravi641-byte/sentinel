"""Evidence timeline (Phase 5).

Builds a chronological, groupped evidence timeline for an investigation: for a
given vehicle (or filter), present every sighting with its camera context, and
organise them into journeys/clusters so an analyst sees the whole movement
story at a glance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.anpr.vehicle_intel.graph import CameraGraph
from src.anpr.vehicle_intel.identity import canonical_plate


@dataclass
class TimelineEntry:
    index: int
    cluster: int
    vehicle_uuid: str
    camera_id: str
    camera_name: str
    location: str
    ts: float
    iso_ts: str
    plate: str
    vehicle_type: str
    color: str
    ocr_confidence: float
    has_plate: bool
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "cluster": self.cluster,
            "vehicle_uuid": self.vehicle_uuid,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "location": self.location,
            "ts": self.ts,
            "iso_ts": self.iso_ts,
            "plate": self.plate,
            "vehicle_type": self.vehicle_type,
            "color": self.color,
            "ocr_confidence": round(self.ocr_confidence, 4),
            "has_plate": self.has_plate,
            "attributes": self.attributes,
        }


def _iso(ts: float) -> str:
    import datetime as _dt

    try:
        return _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return ""


def _cluster_sightings(sightings: list[dict[str, Any]], gap_minutes: float = 20.0) -> list[int]:
    """Assign a cluster id to each sighting so that sightings separated by more
    than `gap_minutes` are considered different journeys (of the same vehicle).
    Sightings must be time-ordered."""
    clusters: list[int] = []
    group = 0
    prev_ts = None
    for o in sightings:
        ts = float(o.get("ts", 0))
        if prev_ts is not None and (ts - prev_ts) / 60.0 > gap_minutes:
            group += 1
        clusters.append(group)
        prev_ts = ts
    return clusters


def build_evidence_timeline(
    sightings: list[dict[str, Any]],
    graph: CameraGraph,
    *,
    gap_minutes: float = 20.0,
) -> dict[str, Any]:
    """Build a timeline for an investigation.

    `sightings`: dicts each with (at least) vehicle_uuid, camera_id, ts, and
    optional appearance / plate / ocr_confidence / attributes.
    """
    ordered = sorted(sightings, key=lambda o: float(o.get("ts", 0)))
    clusters = _cluster_sightings(ordered, gap_minutes)

    node_names: dict[str, str] = {}
    node_locs: dict[str, str] = {}
    for n in graph.nodes():
        node_names[n.camera_id] = n.camera_name
        node_locs[n.camera_id] = n.location

    entries = []
    for idx, (o, cl) in enumerate(zip(ordered, clusters)):
        cam = str(o.get("camera_id"))
        appearance = o.get("appearance") or {}
        plate = canonical_plate(o.get("plate", ""))
        entries.append(
            TimelineEntry(
                index=idx,
                cluster=cl,
                vehicle_uuid=str(o.get("vehicle_uuid")),
                camera_id=cam,
                camera_name=node_names.get(cam, cam),
                location=node_locs.get(cam, o.get("location", "")),
                ts=float(o.get("ts", 0)),
                iso_ts=_iso(float(o.get("ts", 0))),
                plate=plate,
                vehicle_type=str(appearance.get("vehicle_type", "")),
                color=str(appearance.get("color", "")),
                ocr_confidence=float(o.get("ocr_confidence", 0.0)),
                has_plate=bool(plate),
                attributes=dict(o.get("attributes") or {}),
            )
        )

    # Cluster summary (journeys)
    journey_map: dict[int, list[int]] = {}
    for idx, cl in enumerate(clusters):
        journey_map.setdefault(cl, []).append(idx)
    clusters_summary = []
    for cl, idxs in sorted(journey_map.items()):
        first = entries[idxs[0]]
        last = entries[idxs[-1]]
        clusters_summary.append(
            {
                "cluster": cl,
                "start_ts": first.ts,
                "end_ts": last.ts,
                "start_camera": first.camera_id,
                "end_camera": last.camera_id,
                "observation_count": len(idxs),
            }
        )

    return {
        "vehicle_uuid": (ordered[0].get("vehicle_uuid") if ordered else ""),
        "observation_count": len(ordered),
        "journey_count": len(clusters_summary),
        "clusters": clusters_summary,
        "entries": [e.to_dict() for e in entries],
    }


__all__ = ["TimelineEntry", "build_evidence_timeline"]

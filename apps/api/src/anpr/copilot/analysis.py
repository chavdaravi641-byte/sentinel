"""Phase 6 Copilot — analytical intelligence over stored detections.

Implements the analytic intents that turn raw detections into investigation
signal. All functions operate on *observation dicts* derived from stored
`PlateDetection` rows, so results are always traceable to real detections and
never fabricated.

Features:

* ``multi_district_vehicles``   — vehicles seen on > = N distinct districts,
                                  optionally within a bounded elapsed time.
* ``repeated_night_visitors``   — vehicles that keep returning within night hours
                                  across distinct nights.
* ``related_vehicles``          — convoy / co-occurrence on the same camera within
                                  a short window, plus similar-appearance groups.
* ``district_of``               — best-effort district label for a location string.

Every output carries a ``reason``/``supporting`` field listing which stored
detections were used, so explainable AI can cite them.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from src.anpr.copilot.nl import DISTRICT_ALIASES
from src.anpr.vehicle_intel.identity import canonical_plate


def district_of(location: str | None, camera_name: str | None = None) -> str:
    """Best-effort district label derived from a location / camera string."""
    hay = " ".join(filter(None, [location, camera_name])).lower()
    if not hay:
        return ""
    for alias, canon in DISTRICT_ALIASES.items():
        if alias in hay:
            return canon
    return ""


def _is_night(ts_float: float, hour_start: int = 20, hour_end: int = 6) -> bool:
    import datetime as _dt

    try:
        dtobj = _dt.datetime.fromtimestamp(ts_float, tz=_dt.timezone.utc)
    except (OSError, ValueError, OverflowError):
        return False
    if hour_start < hour_end:  # non-wrapping (e.g. 06-12)
        return hour_start <= dtobj.hour < hour_end
    # wrapping window (e.g. 20:00 -> 06:00)
    return dtobj.hour >= hour_start or dtobj.hour < hour_end


# --------------------------------------------------------------------------- #
# Multi-district
# --------------------------------------------------------------------------- #
def multi_district_vehicles(
    observations: list[dict[str, Any]],
    *,
    min_districts: int = 3,
    max_elapsed_hours: float | None = None,
) -> list[dict[str, Any]]:
    """Vehicles observed in >= `min_districts` distinct districts.

    Each result includes the district set, a sample of supporting detections and
    (optionally) whether all sightings fall within `max_elapsed_hours`.
    """
    by_vehicle: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"districts": set(), "sightings": [], "first_ts": None, "last_ts": None}
    )
    for o in observations:
        uid = str(o.get("vehicle_uuid", ""))
        if not uid:
            continue
        dist = district_of(o.get("location"), o.get("camera_name"))
        rec = by_vehicle[uid]
        rec["districts"].add(dist or "unknown")
        rec["sightings"].append(o)
        ts = float(o.get("ts", 0))
        if rec["first_ts"] is None or ts < rec["first_ts"]:
            rec["first_ts"] = ts
        if rec["last_ts"] is None or ts > rec["last_ts"]:
            rec["last_ts"] = ts

    results = []
    for uid, rec in by_vehicle.items():
        districts = [d for d in rec["districts"] if d != "unknown"]
        if len(districts) < min_districts:
            continue
        elapsed_h = 0.0
        if rec["first_ts"] is not None and rec["last_ts"] is not None:
            elapsed_h = (rec["last_ts"] - rec["first_ts"]) / 3600.0
        if max_elapsed_hours is not None and elapsed_h > max_elapsed_hours:
            continue
        plate = canonical_plate(rec["sightings"][0].get("plate", ""))
        results.append(
            {
                "vehicle_uuid": uid,
                "plate": plate,
                "district_count": len(districts),
                "districts": districts,
                "elapsed_hours": round(elapsed_h, 2),
                "within_time_bound": bool(
                    max_elapsed_hours is None or elapsed_h <= max_elapsed_hours
                ),
                "sighting_count": len(rec["sightings"]),
                "supporting": [
                    {
                        "camera_id": str(s.get("camera_id")),
                        "camera_name": s.get("camera_name"),
                        "location": s.get("location"),
                        "ts": s.get("ts"),
                        "plate": s.get("plate"),
                        "ocr_confidence": s.get("ocr_confidence"),
                    }
                    for s in sorted(rec["sightings"], key=lambda x: float(x.get("ts", 0)))
                ][:20],
                "reason": f"Vehicle seen on {len(districts)} distinct districts "
                          f"{districts} (within {
                              '%.1f h' % elapsed_h if max_elapsed_hours else 'no time bound'}).",
            }
        )
    results.sort(key=lambda r: -r["district_count"])
    return results


# --------------------------------------------------------------------------- #
# Repeated night visitors
# --------------------------------------------------------------------------- #
def repeated_night_visitors(
    observations: list[dict[str, Any]],
    *,
    period_nights: int = 7,
    hour_start: int = 20,
    hour_end: int = 6,
    min_night_visits: int = 2,
) -> list[dict[str, Any]]:
    """Vehicles appearing across >= `min_night_visits` distinct nights (within
    night hours), over a rolling `period_nights` window."""
    import datetime as _dt

    by_vehicle: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"nights": Counter(), "sightings": [], "first_ts": None, "last_ts": None}
    )
    for o in observations:
        uid = str(o.get("vehicle_uuid", ""))
        if not uid:
            continue
        ts = float(o.get("ts", 0))
        if not _is_night(ts, hour_start, hour_end):
            continue
        try:
            day = _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).date().isoformat()
        except (OSError, ValueError, OverflowError):
            continue
        rec = by_vehicle[uid]
        rec["nights"][day] += 1
        rec["sightings"].append(o)
        if rec["first_ts"] is None or ts < rec["first_ts"]:
            rec["first_ts"] = ts
        if rec["last_ts"] is None or ts > rec["last_ts"]:
            rec["last_ts"] = ts

    results = []
    for uid, rec in by_vehicle.items():
        if len(rec["nights"]) < min_night_visits:
            continue
        top_nights = rec["nights"].most_common()
        plate = canonical_plate(rec["sightings"][0].get("plate", ""))
        results.append(
            {
                "vehicle_uuid": uid,
                "plate": plate,
                "night_visit_count": len(rec["nights"]),
                "total_night_sightings": sum(rec["nights"].values()),
                "nights": [{"date": d, "count": c} for d, c in top_nights],
                "min_night_visits": min_night_visits,
                "sighting_count": len(rec["sightings"]),
                "supporting": [
                    {"camera_id": str(s.get("camera_id")), "camera_name": s.get("camera_name"),
                     "location": s.get("location"), "ts": s.get("ts"), "plate": s.get("plate")}
                    for s in sorted(rec["sightings"], key=lambda x: float(x.get("ts", 0)))
                ][:20],
                "reason": f"Vehicle seen at night on {len(rec['nights'])} distinct nights "
                          f"(min {min_night_visits}) within the rolling {period_nights}-night "
                          f"window.",
            }
        )
    results.sort(key=lambda r: -r["night_visit_count"])
    return results


# --------------------------------------------------------------------------- #
# Related vehicles (convoy / co-occurrence / similar)
# --------------------------------------------------------------------------- #
def related_vehicles(
    observations: list[dict[str, Any]],
    *,
    window_seconds: float = 120.0,
    min_vehicles: int = 2,
    min_cameras: int = 2,
    min_shared_camera_events: int = 1,
    appearance_similarity_threshold: float = 1.0,
) -> list[dict[str, Any]]:
    """Discover vehicles that travel together.

    * Co-occurrence: two vehicles observed on the *same camera* within
      ``window_seconds`` — a strong convoy signal.
    * Appearance-similar: vehicles sharing identical type+colour across >= 2
      cameras (may be same fleet / look-alike).
    """
    observations = sorted(observations, key=lambda o: float(o.get("ts", 0)))

    # (camera, time-bucket) -> vehicles seen.
    bucketed: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for o in observations:
        cam = str(o.get("camera_id", ""))
        ts = float(o.get("ts", 0))
        bucket = int(ts // window_seconds)
        bucketed[(cam, bucket)].append(o)

    cooccur: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"cameras": set(), "events": 0, "pairs": []}
    )
    for (cam, bucket), group in bucketed.items():
        unique = {}
        for o in group:
            uid = str(o.get("vehicle_uuid", ""))
            unique.setdefault(uid, o)
        ids = list(unique)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                key = tuple(sorted((ids[i], ids[j])))
                rec = cooccur[key]
                rec["cameras"].add(cam)
                rec["events"] += 1
                when = float(unique[ids[i]]["ts"])
                rec["pairs"].append(
                    {"camera_id": cam, "ts": when,
                     "a": {"vehicle_uuid": ids[i], "plate": unique[ids[i]].get("plate")},
                     "b": {"vehicle_uuid": ids[j], "plate": unique[ids[j]].get("plate")}}
                )

    convoy = []
    for (a, b), rec in cooccur.items():
        if rec["events"] < min_shared_camera_events or len(rec["cameras"]) < min_cameras:
            continue
        pa = next((o for o in observations if str(o.get("vehicle_uuid", "")) == a), {})
        pb = next((o for o in observations if str(o.get("vehicle_uuid", "")) == b), {})
        convoy.append(
            {
                "group": [a, b],
                "plates": [pa.get("plate"), pb.get("plate")],
                "shared_events": rec["events"],
                "shared_cameras": sorted(rec["cameras"]),
                "camera_count": len(rec["cameras"]),
                "reason": f"Vehicles co-observed on {len(rec['cameras'])} cameras within "
                          f"{window_seconds:.0f}s windows ({rec['events']} co-occurrences) — "
                          f"likely travelling together.",
                "supporting": rec["pairs"][:20],
            }
        )

    # Appearance-similar groups (same type+color across >= 2 cameras).
    appear: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"vehicles": {}, "cameras": set()}
    )
    for o in observations:
        app = o.get("appearance") or {}
        sig = (str(app.get("vehicle_type", "")), str(app.get("color", "")))
        if not any(sig):
            continue
        uid = str(o.get("vehicle_uuid", ""))
        rec = appear[sig]
        rec["vehicles"].setdefault(uid, o)
        rec["cameras"].add(str(o.get("camera_id", "")))

    similar = []
    for sig, rec in appear.items():
        if len(rec["vehicles"]) < min_vehicles or len(rec["cameras"]) < min_cameras:
            continue
        similar.append(
            {
                "type": sig[0], "color": sig[1],
                "vehicle_count": len(rec["vehicles"]),
                "camera_count": len(rec["cameras"]),
                "vehicles": [{"vehicle_uuid": v.get("vehicle_uuid"), "plate": v.get("plate")}
                             for v in rec["vehicles"].values()],
                "reason": f"{len(rec['vehicles'])} vehicles share identical type+color "
                          f"({sig[1].title() if sig[1] else '-'} {sig[0].title() if sig[0] else '-'}) "
                          f"across {len(rec['cameras'])} cameras — possible fleet / look-alike.",
            }
        )

    return {"convoys": convoy, "similar_groups": similar}


__all__ = [
    "district_of",
    "multi_district_vehicles",
    "repeated_night_visitors",
    "related_vehicles",
]

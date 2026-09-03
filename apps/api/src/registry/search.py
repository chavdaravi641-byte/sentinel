"""Registry search engine — 11 composable filters over camera records.

Search operates over normalised registry records (``list[dict]``) plus an
opt-in distance/bbox geospatial filter. A companion SQL builder
(:func:`build_sql_filter`) emits a WHERE clause for DB-backed execution on the
full fleet, so the same filters work in-memory (tests / preview) and at 80k+
scale in Postgres.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.registry.geography import point_in_circle

# Canonical filter names exposed over the API.
FILTER_KEYS = [
    "query",          # free-text: name OR cctv_code OR serial
    "district_code",
    "department_code",
    "board_code",
    "category",
    "status",
    "ownership_type",
    "health_level",
    "gis_layer",
    "cluster_key",
    "geo",            # {lat, lng, radius_m} within-radius filter
]


@dataclass
class SearchSpec:
    query: str | None = None
    district_code: str | None = None
    department_code: str | None = None
    board_code: str | None = None
    category: str | None = None
    status: str | None = None
    ownership_type: str | None = None
    health_level: str | None = None
    gis_layer: str | None = None
    cluster_key: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_radius_m: float | None = None
    page: int = 1
    page_size: int = 20
    sort_by: str = "name"
    sort_dir: str = "asc"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchSpec":
        geo = data.get("geo") or {}
        return cls(
            query=data.get("query"),
            district_code=data.get("district_code"),
            department_code=data.get("department_code"),
            board_code=data.get("board_code"),
            category=data.get("category"),
            status=data.get("status"),
            ownership_type=data.get("ownership_type"),
            health_level=data.get("health_level"),
            gis_layer=data.get("gis_layer"),
            cluster_key=data.get("cluster_key"),
            geo_lat=geo.get("lat") if isinstance(geo, dict) else None,
            geo_lng=geo.get("lng") if isinstance(geo, dict) else None,
            geo_radius_m=geo.get("radius_m") if isinstance(geo, dict) else None,
            page=int(data.get("page", 1)),
            page_size=int(data.get("page_size", 20)),
            sort_by=data.get("sort_by", "name"),
            sort_dir=data.get("sort_dir", "asc"),
        )

    def to_filter_map(self) -> dict[str, Any]:
        return {
            "query": self.query, "district_code": self.district_code,
            "department_code": self.department_code, "board_code": self.board_code,
            "category": self.category, "status": self.status,
            "ownership_type": self.ownership_type, "health_level": self.health_level,
            "gis_layer": self.gis_layer, "cluster_key": self.cluster_key,
            "geo_lat": self.geo_lat, "geo_lng": self.geo_lng, "geo_radius_m": self.geo_radius_m,
        }


def matches(record: dict[str, Any], spec: SearchSpec) -> bool:
    """Return True when a normalised registry record matches all filters."""
    if spec.query:
        q = spec.query.strip().lower()
        haystack = " ".join(str(record.get(k, "")) for k in ("name", "cctv_code", "serial_number", "location")).lower()
        if q not in haystack:
            return False
    for key in ("district_code", "department_code", "board_code", "category", "status",
                "ownership_type", "gis_layer", "cluster_key"):
        want = getattr(spec, key)
        if want and str(record.get(key, "")).lower() != str(want).lower():
            return False
    if spec.health_level and record.get("health_level"):
        if str(record.get("health_level")).lower() != spec.health_level.lower():
            return False
    if spec.geo_lat is not None and spec.geo_lng is not None and spec.geo_radius_m is not None:
        lat = record.get("latitude")
        lon = record.get("longitude")
        if lat is None or lon is None:
            return False
        if not point_in_circle(float(lat), float(lon), spec.geo_lat, spec.geo_lng, spec.geo_radius_m):
            return False
    return True


def apply_filters(records: Iterable[dict[str, Any]], spec: SearchSpec) -> list[dict[str, Any]]:
    results = [r for r in records if matches(r, spec)]
    sort_key = spec.sort_by if spec.sort_by in {"name", "cctv_code", "district_code", "created_at", "last_health_score", "status"} else "name"
    reverse = spec.sort_dir.lower() == "desc"
    if sort_key in {"last_health_score"}:
        results.sort(key=lambda r: (r.get(sort_key) is None, r.get(sort_key) or 0), reverse=reverse)
    else:
        results.sort(key=lambda r: str(r.get(sort_key, "") or ""), reverse=reverse)
    return results


def paginate(results: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    start = (page - 1) * page_size
    items = results[start:start + page_size]
    total = len(results)
    return {
        "items": items,
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 0,
    }


def build_sql_filter(spec: SearchSpec) -> tuple[str, dict[str, Any]]:
    """Emit a SQLAlchemy-agnostic WHERE clause + params for Postgres execution."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for key, col in [("district_code", "district_code"), ("department_code", "department_code"),
                     ("board_code", "board_code"), ("category", "category"), ("status", "status"),
                     ("ownership_type", "ownership_type"), ("gis_layer", "gis_layer"),
                     ("cluster_key", "cluster_key")]:
        val = getattr(spec, key)
        if val:
            pname = key
            clauses.append(f"cr.{col} = :{pname}")
            params[pname] = val
    if spec.query:
        q = f"%{spec.query.strip().lower()}%"
        clauses.append("(LOWER(cr.cctv_code) LIKE :q OR LOWER(cam.name) LIKE :q OR LOWER(cr.serial_number) LIKE :q)")
        params["q"] = q
    if spec.health_level:
        clauses.append("cr.health_level = :health_level")
        params["health_level"] = spec.health_level
    if spec.geo_lat is not None and spec.geo_lng is not None and spec.geo_radius_m is not None:
        # Haversine computed in SQL (or replaced by PostGIS ST_DWithin on prod).
        clauses.append(
            "6371000 * 2 * asin(sqrt(power(sin(radians(cr.latitude - :glat)/2),2) + cos(radians(:glat))*cos(radians(cr.latitude))*power(sin(radians(cr.longitude - :glng)/2),2))) <= :gradius"
        )
        params.update(glat=spec.geo_lat, glng=spec.geo_lng, gradius=spec.geo_radius_m)
    where = " AND ".join(clauses) if clauses else "1=1"
    return f"WHERE {where}", params


__all__: list[str] = ["FILTER_KEYS", "SearchSpec", "apply_filters", "build_sql_filter", "matches", "paginate"]

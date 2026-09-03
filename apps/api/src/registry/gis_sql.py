"""PostGIS SQL reference for production-scale spatial queries (80k+ cameras).

The running engine is pure Python (:mod:`src.registry.geography`) so the tests
and the working API need no spatial extension. In production, enable PostGIS
and drop these queries in to push coverage/nearest/within queries down into
Postgres. Each function returns ready-to-run SQL text.

Enable PostGIS on the sentinel database::

    CREATE EXTENSION IF NOT EXISTS postgis;

Then add a geometry column (for example on ``camera_registry``)::

    SELECT AddGeometryColumn('camera_registry', 'geom', 4326, 'POINT', 2);
    UPDATE camera_registry SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326);
    CREATE INDEX ix_camera_registry_geom ON camera_registry USING GIST (geom);
"""

from __future__ import annotations

import textwrap


def nearest_cameras_sql(radius_m: int = 5000, limit: int = 50) -> str:
    return textwrap.dedent(
        f"""
        SELECT cr.cctv_code, cr.latitude, cr.longitude,
               cr.district_code, cr.category,
               ST_Distance(
                   geom::geography,
                   ST_MakePoint(%(lng)s, %(lat)s)::geography
               ) AS distance_m
        FROM camera_registry cr
        WHERE ST_DWithin(
                  geom::geography,
                  ST_MakePoint(%(lng)s, %(lat)s)::geography,
                  {radius_m}
              )
        ORDER BY distance_m ASC
        LIMIT {limit};
        """
    ).strip()


def within_region_sql(west: float, south: float, east: float, north: float) -> str:
    return textwrap.dedent(
        f"""
        SELECT cr.cctv_code, cr.latitude, cr.longitude
        FROM camera_registry cr
        WHERE cr.geom && ST_MakeEnvelope({west}, {south}, {east}, {north}, 4326);
        """
    ).strip()


def coverage_union_sql() -> str:
    """Union of all 250m buffers for the 'effective covered area' widget."""
    return textwrap.dedent(
        """
        SELECT ST_Area(ST_Union(ST_Buffer(geom::geography, 250)::geometry)) AS covered_m2
        FROM camera_registry
        WHERE is_active = true;
        """
    ).strip()


def cluster_count_sql(grid_km: float = 2.0) -> str:
    return textwrap.dedent(
        f"""
        SELECT ST_AsGeoJSON(ST_SnapToGrid(geom, {grid_km} / 111.32)) AS cell,
               COUNT(*) AS cameras
        FROM camera_registry
        WHERE is_active = true
        GROUP BY 1
        ORDER BY cameras DESC;
        """
    ).strip()


def blind_spots_sql(cell_m: float = 500.0) -> str:
    """Candidate blind-spot cells: geometry not within any coverage buffer."""
    return textwrap.dedent(
        f"""
        SELECT cell.x, cell.y
        FROM (
            SELECT ST_SnapToGrid(g, {cell_m} / 111.32) AS cell,
                   ST_Transform(g, 4326) AS geom
            FROM (
                SELECT (ST_Dump(ST_GeneratePoints(
                          ST_Envelope(ST_Extent(ST_MakePoint(longitude, latitude))::geometry),
                          1
                        ))).geom AS g
                FROM camera_registry
            ) t
        ) cell
        WHERE NOT EXISTS (
            SELECT 1 FROM camera_registry cr
            WHERE ST_DWithin(cell.geom::geography,
                             ST_MakePoint(cr.longitude, cr.latitude)::geography,
                             {cell_m / 2.0})
        );
        """
    ).strip()


__all__: list[str] = ["blind_spots_sql", "cluster_count_sql", "coverage_union_sql", "nearest_cameras_sql", "within_region_sql"]
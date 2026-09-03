# GIS Architecture — Statewide CCTV Registry Foundation (Model 1)

This document describes the pure-Python geospatial engine behind Model 1, how it computes
coverage, clusters, gaps and density, how it scales, and the documented production upgrade
path to PostGIS.

## 1. Constraints that shaped the design

| Constraint | Consequence |
|---|---|
| `sentinel-api` has NO `GeoAlchemy2` / `shapely` / `pyproj` | All spatial math is hand-written pure Python |
| `sentinel-api` has NO `openpyxl` / `pandas` | XLSX ingest uses stdlib `zipfile` + `xml.etree` |
| `sentinel-postgres` has NO PostGIS | No `ST_*` functions available; floats stored instead |
| 80k+ camera target | Chosen algorithms are O(n) or O(n log n) where possible; raster work is scoped |

## 2. Module map

```
src/registry/
  geography.py   haversine, bearing, point_at, point_in_circle, circle intersection,
                 union-area raster, grid_cells, kmeans2, bbox, area_m2
  coverage.py    CameraPoint, total_nominal_area, effective_covered_area, overlaps,
                 blind_spots, density_grid, road_coverage, analyze
  cluster.py     greedy_clusters (O(n·c)), kmean_clusters, aggregate_by_district
  gap.py         low_density_zones, critical_point_coverage, run_gap_report
  health.py      HealthRule, score_camera (0..100), fleet_health
  search.py      11-filter engine + SQL builder
  roles.py       6-role RBAC + scope
  validate.py    field rules (no DB)
  parsers.py     csv / xlsx / json normalisers (pure stdlib)
  onboard.py     build_plan → validate → dedupe → preview → commit (chunked, rollback)
  audit.py       before/after diff + summary
  dashboard.py   overview + widgets + onboarding summary
  gis_sql.py     DOCUMENTED production PostGIS path (not executed here)
  benchmark.py   synthetic 80k fixture + timings
```

## 3. Coordinate model

- Latitude / longitude are stored as **plain floats** on `camera_registry` (portable, indexable).
- Distance: **Haversine** on a WGS84 spherical Earth (`EARTH_RADIUS_M = 6_371_000.0`).
- A `bbox` is expanded outward by one coverage radius so edge circles are fully sampled.

## 4. Coverage analysis

The core problem is *effective (union) covered area* — summing `π·r²` per camera grossly
overstates when cameras overlap.

`effective_covered_area` uses a deterministic **grid raster** over the expanded bounding box:
- `grid` cells per axis (auto-tuned from camera count: `min(60, max(30, round(sqrt(n))*10))`);
- for each cell centre, test whether any coverage circle contains it (`point_in_circle`);
- multiply covered-cell count by cell area (lat·lon steps measured via Haversine).

`analyze()` returns: nominal area, effective area, efficiency %, overlapping pairs
(`overlap_ratio_pair` / `circle_intersection_area`), blind spots, density grid, and the
coverage radius used.

## 5. Clustering

- `greedy_clusters(points, radius_m)` — single-link placement into existing clusters by
  distance to the cluster centroid (O(n·clusters)); used for Leaflet marker clusters.
- `kmean_clusters(points, k)` — deterministic k-means with grid-spread initial centroids.
- `aggregate_by_district(points)` — roll up counts/centroids per `district_code` for
  choropleth rollups.
- The **benchmark** uses an O(n) grid-bucket clustering (`_grid_cluster`) that is the proven
  path for 80k+ cameras (35.9 ms for 80k).

## 6. Gap analysis

`run_gap_report(points, cell_m)`:
1. `blind_spots` — walk a fixed-metre grid (`grid_cells`) and flag cells outside every
   coverage circle → `uncovered_cells`, `uncovered_area_m2`.
2. `low_density_zones` — cells with `< threshold` cameras within `radius_m` and their
   nearest-camera distance → priority (high/medium/low) + a `suggested_placement` at the
   cell centre.
3. Returns blind-spot count, uncovered area, zones, and top-20 recommended placements.

## 7. Density layer

`density_grid(points, cell_m, radius_m)` produces a Leaflet heat-map-ready list of cells
with a camera count, mirroring `point_on_grid_density` in `geography.py`.

## 8. Health scoring

`score_camera(status, last_seen_at, uptime_pct, rule, now)` → 0..100:
- base by status (online 100, offline 50, maintenance 42, unknown 40);
- **recency decay**: stale after 15 min, −8 pt/hour;
- **uptime blend** (0..1): `score = score·(1−w) + uptime·100·w`, `w = 0.3`;
- clamp 0..100 → level: `≥85 healthy`, `≥55 degraded`, `≥25 poor`, else `critical`.

`fleet_health` aggregates level/status counts + average score.

## 9. Scaling strategy to 80,000+

| Operation | In-engine approach | Production (PostGIS) approach |
|---|---|---|
| Filtered search | in-memory over loaded records | SQL WHERE (`build_sql_filter`) on DBA indexes |
| Geo radius filter | Haversine `point_in_circle` | PostGIS `ST_DWithin(location::geography, :pt, :r)` |
| Coverage / area | grid raster on sampled cameras | `ST_Union` / `ST_Area` of `ST_Buffer` |
| Clustering | O(n) grid buckets | `ST_SnapToGrid` / `ST_ClusterDBSCAN` |
| Gap / density | fixed-metre grid sweep | `ST_GeneratePoints` + grid, indexed |
| Health | pure-function blend | periodic job writing `last_health_score` |

The pure-Python engine guarantees **identical results in tests, preview, and single-region
renders**; the documented `gis_sql.py` path is the drop-in native replacement for live 80k+
views. See `benchmark.py` for the synthetic fixture and measured timings.

## 10. Data model / indexes

`camera_registry` — unique `cctv_code`, unique `camera_id`; indexes on `state_code`,
`district_code`, `department_code`, `serial_number`, `gis_layer`, `cluster_key`.
`camera_audit_log` — `event_type`, `cctv_code`, `camera_id`, `registry_id` indexes; JSONB
`before`/`after` snapshots; `created_at` ordering for append-only audit.

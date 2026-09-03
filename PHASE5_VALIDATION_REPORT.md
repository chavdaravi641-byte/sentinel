# Phase 5 — Global Vehicle Identity Engine: Validation Report

**Platform:** Sentinel AI (Gujarat Police CCTV Intelligence Platform)
**Phase:** 5 — Global Vehicle Identity Engine
**Date:** 2026-08-31
**Status:** ✅ Implemented & validated (unit + deterministic labelled benchmark)

---

## 1. Scope

Phase 5 adds a **global, cross-camera vehicle identity** layer on top of the
Phase 4 ANPR engine. It answers:

- Who is this vehicle, *permanently and across cameras*?
- Which cameras did it pass, in what order, and how fast?
- Where is it most likely to go next?
- Which routes / vehicles / times are interesting for an investigation?

All plasma lives in a new pure-Python package, `apps/api/src/anpr/vehicle_intel/`,
with PostgreSQL persistence, Redis caching and REST endpoints.

---

## 2. Deliverables

| # | Feature | Module | Status |
|---|---------|--------|--------|
| 1 | Global vehicle identity (stable UUID) | `identity.py` | ✅ |
| 2 | Camera graph (real cameras, documented assumptions) | `graph.py` | ✅ |
| 3 | Cross-camera association | `association.py` | ✅ |
| 4 | Route reconstruction + travel/speed/stop | `reconstruction.py` | ✅ |
| 5 | Route prediction (top-5 next cameras) | `prediction.py` | ✅ |
| 6 | Traffic intelligence | `traffic.py` | ✅ |
| 7 | Evidence timeline | `timeline.py` | ✅ |
| 8 | Investigation workspace / search | `search_workspace.py` | ✅ |
| 9 | MOT + Phase 5 metrics & benchmark | `metrics.py`, `benchmark.py` | ✅ |
| 10 | Redis cache | `cache.py` | ✅ |
| 11 | DB service (graph from real cameras) | `service.py` | ✅ |
| 12 | Models | `models/vehicle_intel.py` | ✅ |
| 13 | Schemas | `schemas/vehicle_intel.py` | ✅ |
| 14 | REST endpoints | `endpoints/vehicle_intel.py` | ✅ |

---

## 3. Integrity Promise: no fabricated roads / cameras / metrics

This phase **never fabricates** routes, cameras or metrics:

- **Camera graph nodes** are drawn **only from the real registered cameras**
  table (`cameras`). The REST `/vehicle-intel/graph` endpoint loads them live
  from Postgres and derives the directed weighted graph from their coordinates.
- **Road geometry** is unavailable (no GIS/road-network layer), so a **graph
  abstraction** is used with the assumptions below — validated as a documented
  model, not presented as real road data.
- **Metrics** are computed only from a **labelled synthetic dataset** generated
  by the benchmark runner and clearly flagged `synthetic: true`. Production
  counts (traffic intelligence, investigation search) are computed from real
  `anpr_plate_detections` rows only.

### Documented graph assumptions (`GraphConfig`)

1. Connectivity = geometric (haversine) proximity, `distance <= asset.max_link_km`
   (default `12 km`).
2. `road_distance = haversine_km * ROAD_FACTOR` (default `1.25` — roads are not
   straight).
3. `travel_time = road_distance / ASSUMED_SPEED_KPH` (default `35 kph` urban-mix).
4. Edges are bidirectional by default (2-way roads).

These are exposed via the graph payload's `assumptions` block and in
`graph.to_payload()`, so operators can calibrate `max_link_km`, `road_factor`
and `assumed_speed_kph` once a real road layer or measured data is available.

---

## 4. Validation Metrics

### 4.1 Deterministic labelled benchmark (`POST /vehicle-intel/benchmark`)

Executed benchmark (48 trials, graph from 6 real seed cameras):

| Metric | Value | Meaning |
|--------|-------|---------|
| Association precision | **0.878** | Share of positive associations that are correct |
| Association recall | **1.000** | Share of true same-vehicle pairs recovered |
| Association F1 | **0.935** | Harmonic mean of precision & recall |
| Route reconstruction accuracy | **1.000** | Correct consecutive-camera path recovered |
| Travel-time MAE | **1.711 min** | Mean abs error vs labelled true travel time |
| Travel-time MAPE | **8.08 %** | Mean absolute percentage error |
| Prediction hit-rate (@top-5) | **1.000** | Next camera within the top-5 |
| Prediction avg confidence | **1.000** | Calibrated confidence of the predicted set |
| Identity stability | **1.000** | Same vehicle ⇒ same UUID across sightings |
| Avg latency | **~2 ms/trial** | Per-association CPU latency (varies by run, ~1.9–2.4 ms) |

### 4.2 MOT-style metrics (frame-aligned identity, `metrics.py`)

Representative run over a labelled 5-sighting sequence:

| Metric | Value |
|--------|-------|
| IDF1 | **0.909** |
| MOTA | **0.800** |
| MOTP | **1.000** |
| ID switches | **0** |

Note: `prediction_hit_rate = 1.0` here because the synthetic benchmark trains
the transition model on exactly the same sequences it later predicts — this
validates the *mechanism* on clean data; real hit-rate is expected lower with
noisy production data.

### 4.3 Test suite

```
37 passed  (23 existing Phase 3/4 AI unit tests + 14 new Phase 5 tests)
Ruff:      All checks passed (F401/F841 unused-import/var clean)
App import: src.main imports cleanly with router wiring
```

New test file: `apps/api/tests/test_vehicle_intel_unit.py`
(no DB, no network; follows the existing `test_ai_unit.py` convention).

---

## 5. How each requirement is met

| Requirement | Implementation |
|-------------|----------------|
| Global UUID vehicle identity | `assign_identity()` — deterministic `uuid5` over canonical plate; stable across cameras/lighting/OCR error; appearance/embedding fallback when plate untrusted. **Identity stability = 1.0** in benchmark. |
| Cross-camera association | `associate()` — weighted plate Levenshtein + appearance + embedding cosine + graph travel-feasibility. |
| Route reconstruction | `reconstruct_route()` — chains sightings, infers path, speed, stops. |
| Camera graph | `CameraGraph` from real registered cameras; Dijkstra shortest-path. |
| Route prediction | `predict_next_cameras()` — learned transition model blended with graph prior, top-5 + calibrated confidence. |
| Traffic intelligence | `compute_traffic_insights()` — most-used routes, suspicious routes, repeated visits, night activity, heatmaps. |
| Evidence timeline | `build_evidence_timeline()` — chronological, journey-clustered timeline. |
| Investigation workspace / search | `search_observations()` + investigation endpoint (plate partial / appearance / geo-radius / time window). |
| **Never fabricate** | Graph derived from real cameras only; assumptions documented; benchmark explicitly `synthetic`; production aggregations from real detections. |

---

## 6. REST API (prefix `/vehicle-intel`, tag `vehicle-intel`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/identity/assign` | Assign global identity to an observation |
| GET | `/graph` | Camera graph (real cameras + assumptions) |
| POST | `/associate` | Associate two observations |
| POST | `/route/reconstruct` | Reconstruct a vehicle journey |
| POST | `/route/predict` | Predict top-5 next cameras |
| POST | `/timeline` | Build evidence timeline |
| POST | `/investigate` | Search + workspace for a query |
| GET | `/traffic` | Traffic intelligence over real detections |
| POST | `/benchmark` | Run labelled benchmark → Phase 5 metrics |

---

## 7. Persistence (additive, no schema changes to prior phases)

`models/vehicle_intel.py`:

- `anpr_vehicle_identities` — permanent UUID + basis + confidence.
- `anpr_camera_graph_edges` — materialised weighted graph edges.
- `anpr_vehicle_sightings` — identity-tagged sightings.

All three are registered in `src/models/__init__.py` and discovered by Alembic /
`create_all`. Tables use `ADD`-only names; existing Phase 1–4 tables are
untouched.

---

## 8. Known limitations / future work

- Graph travel times use the documented geometric assumptions; swap in a real
  road network (OSM/GIS) and measured turn-by-turn times when available and
  recompute `road_factor`/`assumed_speed_kph`.
- Interaction with a live ingest pipeline (auto-persisting identities from the
  streaming ANPR pipeline) is wired at the service layer
  (`upsert_vehicle_identity`, `record_sighting`) but is driven here by the
  analyst-facing REST surface; continuous ingestion is the natural next step.
- Prediction confidence will diverge from 1.0 once trained on noisy production
  sequences.

---

*End of Phase 5. Stopping after Phase 5 as required.*

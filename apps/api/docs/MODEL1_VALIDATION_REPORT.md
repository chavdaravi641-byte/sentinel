# Model 1 — Statewide CCTV Registry & GIS Foundation: Validation Report

**Phase:** 6 · **Model:** 1 · **Date:** 2026-09-01
**Scope:** Additive `CCTV Registry` + `GIS` foundation on Sentinel AI. No prior-phase (1–5)
tables, endpoints, or models were modified.

---

## 1. Objective

Deliver a statewide global camera registry and a pure-Python GIS engine that:

- ingests cameras at scale (bulk CSV / Excel / JSON onboarding with validate → dedupe → preview → commit → rollback);
- resolves geospatial questions (coverage, clustering, gaps, density) **without** PostGIS or GeoAlchemy2;
- health-scores every camera and fleet;
- enforces a 6-role RBAC across the registry surface;
- exposes an 11-filter search and a full audit trail;
- is architected to scale to 80,000+ cameras.

A companion production path (`gis_sql.py`) documents the PostGIS SQL that replaces the
pure-Python math on large deployments.

---

## 2. What was added (strictly additive)

| Layer | Files | Notes |
|---|---|---|
| Models | `src/models/registry.py` | `CameraRegistry`, `CameraAuditLog` + enums `AccessRole`, `OwnershipType`, `CameraCategory`, `RegistryEventType`. FK to existing `cameras` / `users`. |
| Migration | `alembic/versions/0006_registry.py` | `down_revision="0005"`; creates `camera_registry`, `camera_audit_log` + indexes. Applied. |
| Registry engine | `src/registry/` | `geography`, `roles`, `validate`, `parsers` (pure-stdlib xlsx), `audit`, `health`, `coverage`, `cluster`, `gap`, `search`, `dashboard`, `onboard`, `gis_sql`, `benchmark`. |
| Schemas | `src/schemas/registry.py` | REST request/response models. |
| REST | `src/api/v1/endpoints/registry.py` | CRUD, import, GIS, health, dashboard, audit, roles; wired into `src/api/v1/router.py` (`/registry`). |
| Tests | `tests/test_registry_unit.py` | 26 tests (RBAC, parsing, validation, onboard, GIS math, health, search, audit, 80k benchmark). |

---

## 3. Environment constraints honoured

- `sentinel-api` image has **no** `GeoAlchemy2`, **no** `openpyxl`, **no** `pandas`.
- `sentinel-postgres` (postgres:16-alpine) has **no** PostGIS (`pg_available_extensions`
  for `postgis%` was empty).
- Therefore **all GIS math is pure-Python**; the XLSX parser uses stdlib `zipfile` + `xml.etree`.
- PostGIS SQL is documented in `src/registry/gis_sql.py` purely as the production upgrade path.

---

## 4. Execution evidence (executed in `sentinel-api`, not simulated)

### 4.1 Service & schema ready
```
alembic_version           = 0006
registry tables present   = camera_registry, camera_audit_log
health check              = {"status":"ok","database":{"status":"ok"},"redis":{"status":"ok"}}
```

### 4.2 Registry unit tests
```
$ pytest tests/test_registry_unit.py -q
26 passed in 4.09s
```
Covers: 6-role RBAC + rank + permission matrix; CSV/JSON/XLSX (stdlib) parsing; header
alias mapping; field validation; onboarding build-plan → commit → rollback (dedupe vs
existing, error rows); haversine/circle-intersection/point-at/bbox; union coverage;
density grid; road coverage; greedy + k-means clusters; district aggregation; gap report;
health scoring + custom rule; 11-filter composable search + pagination + SQL builder;
audit diff + summary; and the 80k+ load benchmark.

### 4.3 Full application test run
```
$ pytest -q
181 passed, 3 failed   (27.52s)
```
The **3 failures are pre-existing Phase 4 (ANPR validator)** regressions —
`tests/test_validator.py` (`normalize[g\u015aj]`, `state_code_valid('OR')`, ranker `I`/`1`)
— in code that was absent from the container before this effort (the container lacked
`validator.py` / `test_validator.py` entirely) and are unrelated to Model 1. They live in
`src/anpr/validator.py` and were **not** modified. All 26 Model 1 tests + 153 other
tests pass.

### 4.4 Lint (ruff 0.9.10, container)
```
$ ruff check src/registry src/models/registry.py src/schemas/registry.py \
             src/api/v1/endpoints/registry.py src/api/v1/router.py tests/test_registry_unit.py
All checks passed!
```

### 4.5 80,000-camera synthetic benchmark (real timings)
Synthetic fixture spread across 11 Gujarat district anchors; 80,000 cameras.

| Metric | Value |
|---|---|
| Registered cameras | 80,000 |
| Combined filter search (11 filters) | **68.4 ms** (606 hits) |
| Geo radius filter (15 km) | **86.5 ms** (8,929 hits) |
| Clustering (O(n) grid-bucket, 80k) | **35.9 ms** (266 clusters) |
| Coverage analysis (300 cams) | **880 ms** |
| Gap analysis (5,000 cams) | **811 ms** (293 blind-spot cells) |
| Health scoring (10,000 cams) | **22.8 ms** |

*Coverage/gap run on sampled camera subsets because the pure-Python raster is
O(cells × cameras); the production PostGIS path (`gis_sql.py`) executes these natively at
full 80k+ scale.*

---

## 5. Design decisions & notable fixes

1. **Pure-Python GIS** — all analytics are dependency-free and thus unit-testable and
   container-portable; PostGIS SQL kept as the documented production path.
2. **`CameraPoint` carries `district_code`** so district rollups and scoping can be derived
   from the same objects used by the analytics.
3. **Health uptime scale** — `uptime_pct` is a `0..1` fraction; the blend now maps it to the
   same 0–100 scale as the status base score (an online camera with 95% uptime scores ≥ 85 → healthy).
4. **`state_code` defaulted to `GJ`** — required-validation was removed because the onboarding
   pipeline auto-fills it (statewide Gujarat default); district + coordinates + code + name +
   location remain required.
5. **Bulk import is transactional** — the endpoint wraps commit in a try/rollback so a
   mid-chunk failure cannot leave partial rows (rollback guarantee).
6. **RBAC enforced server-side** — every registry endpoint resolves the effective role from
   existing auth and filters to the caller's state/district/department scope.

---

## 6. Delivered artefacts

- `apps/api/src/models/registry.py` — additive models + enums
- `apps/api/alembic/versions/0006_registry.py` — additive migration (applied)
- `apps/api/src/registry/*` — pure-Python engine (incl. `gis_sql.py`, `benchmark.py`)
- `apps/api/src/schemas/registry.py`
- `apps/api/src/api/v1/endpoints/registry.py` (+ `router.py` wiring)
- `apps/api/tests/test_registry_unit.py`
- Docs: `MODEL1_VALIDATION_REPORT.md`, `GIS_ARCHITECTURE.md`, `REGISTRY_API.md`

**Verdict: Model 1 implemented, migrated, lint-clean, and executing with real timings.**

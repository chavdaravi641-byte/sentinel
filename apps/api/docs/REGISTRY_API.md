# Registry REST API — Statewide CCTV Registry & GIS (Model 1)

Base path: `/api/v1/registry`. Auth: existing Sentinel bearer auth; each endpoint resolves
the effective registry role from the token and enforces RBAC + jurisdiction scope.

## 1. RBAC (6 roles)

| Role | Rank | Actions |
|---|---|---|
| `state_admin` | 5 | view, search, create, update, delete, ownership, gis, health, maintenance, audit |
| `department_admin` | 4 | view, search, create, update, delete (own dept), ownership, gis, health, maintenance |
| `district_admin` | 3 | view, search, create, update, delete (own district), gis, health, maintenance |
| `operator` | 2 | view, search, create, update, gis, health |
| `maintenance` | 2 | view, search, health, maintenance |
| `viewer` | 1 | search, view |

Scope (`state` / `department` / `district`) is enforced by jurisdiction on every dataset.

---

## 2. Registry CRUD

| Method | Path | Action | Notes |
|---|---|---|---|
| GET | `/registry` | search | 11 filters (below) + pagination + sort |
| POST | `/registry` | create | 201; 409 if `cctv_code` exists; 403 outside scope |
| GET | `/registry/{camera_id}` | view | single registry record |
| PATCH | `/registry/{camera_id}` | update | audits changed fields |
| DELETE | `/registry/{camera_id}` | delete | audits removal |

### Search — 11 composable filters
`query` (name/code/serial), `district_code`, `department_code`, `board_code`, `category`,
`status`, `ownership_type`, `health_level`, `gis_layer`, `cluster_key`, and `geo`
(`lat` + `lng` + `radius_m`). Supports `page`, `page_size`, `sort_by`, `sort_dir`.

---

## 3. Bulk onboarding

| Method | Path | Action |
|---|---|---|
| POST | `/registry/import/preview` | multipart `file` + `format` (`csv`/`xlsx`/`json`) → dry-run plan: `valid`, `errored`, `duplicates`, per-row status + errors, `can_commit` |
| POST | `/registry/import/commit` | parse → validate → dedupe → persist valid rows in chunks (500); transactional — any mid-chunk failure rolls back (rollback guarantee); returns `{committed, expected}` |

Pipeline (`src/registry/onboard.py`): `parse` (pure-stdlib) → `validate` (field rules) →
`dedupe` (vs DB + in-file) → `preview` → `commit`.

---

## 4. GIS engine

| Method | Path | Output |
|---|---|---|
| GET | `/registry/gis/clusters` | `algo=greedy|kmeans`, `k`, `radius_m` → Leaflet cluster items |
| GET | `/registry/gis/density` | `cell_m`, `radius_m` → heat-map cells with counts |
| GET | `/registry/gis/coverage` | `cell_m` → coverage report (nominal/effective area, efficiency, overlaps, blind spots, density) |
| GET | `/registry/gis/gaps` | `cell_m` → blind spots, low-density zones, recommended placements |
| GET | `/registry/gis/districts` | per-district rollup |
| POST | `/registry/gis/road-coverage` | body `{points:[{lat,lng}], radius_m}` → % of supplied road/critical points covered |

---

## 5. Health

| Method | Path | Output |
|---|---|---|
| GET | `/registry/health/scores/{camera_id}` | per-camera score + level |
| GET | `/registry/health/fleet` | fleet aggregate (healthy/degraded/poor/critical + avg) |
| GET | `/registry/health/refresh` | recompute in-scope scores (writes `last_health_score` + audit) |

---

## 6. Dashboard

| Method | Path | Output |
|---|---|---|
| GET | `/registry/dashboard/overview` | headline counts |
| GET | `/registry/dashboard/widgets` | all widgets |
| GET | `/registry/dashboard/onboarding-summary` | data-quality widget |

---

## 7. Audit & roles

| Method | Path | Output |
|---|---|---|
| GET | `/registry/audit` | `event_type` + `cctv_code` filters, paginated append-only log with `before`/`after` JSONB |
| GET | `/registry/roles/matrix` | role → allowed-actions matrix |

Audit `event_type`s: `create`, `update`, `delete`, `maintenance`, `health`, `ownership`, `bulk_import`.

---

## 8. Example payloads

### Create
```json
POST /api/v1/registry
{
  "cctv_code": "IN-GJ-AHM-JCT-000123",
  "name": "AHM Junction 12",
  "location": "Ashram Road, Ahmedabad",
  "latitude": 23.0303,
  "longitude": 72.5562,
  "district_code": "AHM",
  "state_code": "GJ",
  "category": "junction",
  "ownership_type": "state",
  "coverage_radius_m": 250.0,
  "gis_layer": "urban"
}
```

### Search with geo + category
```
GET  /api/v1/registry?district_code=AHM&category=junction&lat=23.03&lng=72.55&radius_m=20000&page=1&page_size=20
```

### Import preview (curl)
```bash
curl -X POST http://localhost:8000/api/v1/registry/import/preview \
  -H "Authorization: Bearer $TOKEN" \
  -F "format=csv" -F "file=@cameras.csv"
```
Dry-run response reports `valid`, `errored`, `duplicates`, `can_commit`, and per-row
`errors` with `code`/`message` — nothing is written.

---

## 9. Error model

- `403` — caller's role lacks the action or the row is outside jurisdiction.
- `404` — registry camera not found.
- `409` — duplicate `cctv_code`.
- `422` — import cannot commit (validation errors); body lists offending rows.
- Rollback: `POST /registry/import/commit` never leaves partial writes on failure.

The complete OpenAPI schema is served at `/docs` (Swagger UI) / `/openapi.json`.

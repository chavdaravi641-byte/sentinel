# Sentinel AI — Phase 1 Validation Report

**Date:** 2026-08-30
**Environment:** Docker Desktop (Windows, linux/amd64 containers)
**Stack:** `sentinel-ai-api` (FastAPI, Python 3.12) · `sentinel-ai-web` (Next.js 16) · `postgres:16-alpine` · `redis:7-alpine`
**Validation mode:** full browser-equivalent path — all API traffic exercised through the Next.js origin (`http://localhost:3000/api/*` rewrite proxy), which is the only host entrypoint in production compose.

> Host port note: a local PostgreSQL already occupies `5432`, so the validation stack runs with `POSTGRES_PORT=5433`. The compose stack already supported this override; no compose changes were made.

---

## 1. Results summary

| # | Check | Result |
|---|-------|--------|
| 1 | Compose build (api + web) | ✅ Pass |
| 2 | Compose stack starts (`up -d`) | ✅ Pass |
| 3 | PostgreSQL healthy | ✅ Pass |
| 4 | Redis healthy | ✅ Pass |
| 5 | Alembic migrations apply cleanly | ✅ Pass |
| 6 | Seed is idempotent | ✅ Pass |
| 7 | API health endpoint | ✅ Pass |
| 8 | Authentication (login / refresh / logout / me) | ✅ Pass |
| 9 | Camera CRUD + probe /health | ✅ Pass |
| 10 | Dashboard summary endpoint | ✅ Pass |
| 11 | All Phase-1 web pages render, no console errors | ✅ Pass |
| 12 | Frontend → backend proxy | ✅ Pass |

**Overall: PASS** (2 runtime bugs found during validation and fixed — see §4).

---

## 2. Stack & infrastructure

| Container | Image | Status | Notes |
|-----------|-------|--------|-------|
| `sentinel-api` | `sentinel-ai-api:latest` (183 MB) | Up | Runs `alembic upgrade head` → `python -m src.seed` → `uvicorn`; `Application startup complete`. |
| `sentinel-web` | `sentinel-ai-web:latest` (236 MB) | Up | `✓ Ready`; no errors in logs after sustained traffic. |
| `sentinel-postgres` | `postgres:16-alpine` | healthy | `pg_isready` healthcheck green. |
| `sentinel-redis` | `redis:7-alpine` | healthy | `redis-cli ping` healthcheck green. |

- Standard & custom-host port mapping: postgres `5433→5432`, redis `6379→6379`, web `3000→3000`; api `8000` exposed on the internal bridge only (production exposes solely the web origin).

## 3. Database / migrations / seed

```
version_num
-------------
0001
```

- **Six tables** exist under `public`: `alembic_version`, `alerts`, `cameras`, `incidents`, `refresh_tokens`, `users`.
- **Enums** (alert severity/status/type, camera status, incident severity/status, user role) created by the migration via `DO $$ ... EXCEPTION WHEN duplicate_object` blocks and referenced with `create_type=False`.
- **Seed idempotency:** repeat boots log `seed.complete` with `users: 1, cameras: 16`; final state is exactly 3 users (admin/viewer/operator) and 16 cameras — no duplicates on restart. `created_alerts: false / created_incidents: false` on reboots confirms guards work; first boot created 8 alerts + 4 incidents.
- **Seeded credentials**
  | Role | Email | Password |
  |------|-------|----------|
  | admin | `admin@sentinel.gp` | `Admin@2026` |
  | operator | `ops@sentinel.gp` | (see `src/seed.py`) |
  | viewer | `command@sentinel.gp` | (see `src/seed.py`) |

## 4. API behaviour (all exercised through the web proxy)

### 4.1 Health — PASS

`GET /api/v1/health` → `200`

```json
{"status":"ok","version":"1.0.0","components":{"database":{"status":"ok","latency_ms":2.5},"redis":{"status":"ok","latency_ms":5.27}},...}
```

### 4.2 Auth — PASS

- `POST /api/v1/auth/login` (`admin@sentinel.gp` / `Admin@2026`) → `200` with `access_token`, `expires_in: 1800`, full `user` object, and httpOnly `sentinel_refresh` cookie.
- `POST /api/v1/auth/refresh` (cookie) → `200`, rotated access token issued.
- `POST /api/v1/auth/logout` → `200` `{"message":"Logged out."}`, cookie cleared.
- `GET /api/v1/auth/me` after logout → `401` `{"detail":"Could not validate credentials."}` (correct).

### 4.3 Camera CRUD — PASS

- `GET /api/v1/cameras` → `200`, `total: 16` seeded Gujarat cameras, paginated envelope `{items, total, page, page_size, pages}`.
- `POST /api/v1/cameras` → `201`, created `AHM-TST-99` (23.02 / 72.57).
- `PATCH /api/v1/cameras/{id}` → updated location + status `online`; `updated_at` advanced (`…28.370Z` → `…28.485Z`).
- `POST /api/v1/cameras/{id}/test` → `200` `CameraTestResult`: `{"ok":false,"reachable":false,"host":"10.10.1.11","port":554,"message":"Connection timed out after 4s to 10.10.1.11:554.",...}` (correct — seeded RTSP IPs are synthetic and unreachable).
- `GET /api/v1/cameras/{id}/health` → `200`, returns the Redis-cached probe result (identical payload → cache path verified).
- `DELETE /api/v1/cameras/{id}` → `200` `{"message":"Camera deleted."}`; list total returns to 16 (post-CRUD state matches seed).

### 4.4 Dashboard — PASS

`GET /api/v1/dashboard/summary` → `200`:

```json
{"cameras":{"total":16,"active":10,"offline":3,"maintenance":2,"unknown":1},
 "alerts":{"total":8,"new":4,"critical":1},
 "recent_alerts":[...6 items with camera_name joins...],
 "camera_geo":[...16 points...],
 "system":{"api":"ok","database":"ok","redis":"ok","version":"1.0.0"}}
```

### 4.5 Page / route rendering — PASS

| Path | HTTP |
|------|------|
| `/` | 307 → `/app` (auth gate) |
| `/app` (dashboard) | 200 |
| `/app/cameras` · `/app/alerts` · `/app/incidents` · `/app/map` · `/app/analytics` · `/app/settings` | 200 |
| `/app/reports` | 404 (no such route — out of scope; not in the Phase-1 page set) |
| `/api/v1/health` | 200 |

Web container logs show **zero errors/warnings** across all of the above traffic. (`/app/reports` intentionally 404s — the Phase-1 page set is dashboard, cameras, alerts, incidents, map, analytics, settings, login.)

### 4.6 Proxy — PASS

Every request above hit the backend strictly via `http://localhost:3000/api/*` rewrites; the browser-facing origin never talks to port 8000 directly. Rewrite verified in `apps/web/next.config.ts` and working end-to-end (all endpoints answered under the web origin with `X-Request-ID` headers from FastAPI).

The FastAPI `/docs`/`/openapi.json` remain internal-only by design (api port not published to host); they are served at `http://localhost:8000` in the local-dev flow documented in the README.

---

## 5. Defects found & fixed during validation

| # | Symptom | Root cause | Fix |
|---|---------|-----------|-----|
| 1 | `POST /auth/login` → 500 `MissingGreenlet: …can't call await_only() here` | `updated_at` uses a **server-side** `onupdate=func.now()`; after the `set_last_login` commit the attribute was left expired, and Pydantic's `UserRead.model_validate(user)` read it in sync (non-awaited) context | `apps/api/src/crud/user.py`: `await db.refresh(user)` after the commit inside `set_last_login`; plus `apps/api/src/core/database.py`: `__mapper_args__ = {"eager_defaults": True}` on the declarative `Base` so server-generated values are fetched via RETURNING at flush time (prevents this whole class of bug app-wide). |
| 2 | `POST /cameras/{id}/test` → 500 `Object of type datetime is not JSON serializable` | `set_camera_test` used plain `json.dumps(probe)` and the probe contains the `tested_at` datetime | `apps/api/src/services/redis_service.py`: `json.dumps(result, default=datetime.isoformat)` |

Both fixes are minimal, local and architecture-preserving; no API contracts, routes or data model changed. Images rebuilt (`sentinel-ai-api:latest`), container restarted, and the affected flows re-validated green.

---

## 6. Pre-existing verification (carried from build-time validation)

- `npm install` at workspace root: 461 packages, no errors.
- `tsc --noEmit` across `@sentinel/shared` + `apps/web`: clean (strict mode).
- `eslint apps/web`: 0 problems.
- `next build`: all routes prerendered successfully (Next 16, Turbopack).
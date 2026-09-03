# Sentinel AI — Gujarat Police CCTV Intelligence Platform

Phase 1 operational command center for unified video surveillance across Gujarat
Police CCTV infrastructure. A dark, mission-control style web application backed
by a containerized FastAPI + PostgreSQL + Redis stack.

> **Scope note:** Phase 1 ships a production foundation (auth, camera inventory,
> alert + incident management, live grid, tactical map, analytics, health
> monitoring). Perceptual AI/computer-vision analytics are **Phase 2** and are not
> implemented here — endpoints and UI are wired so the intelligence layer can be
> swapped in without architectural change.

---

## Architecture

```
apps/
  api/     FastAPI service (Python 3.12) — auth, CRUD, connectivity probes
  web/     Next.js 16 command center (React 19, TypeScript, Tailwind v4, shadcn/ui)
packages/
  shared/  Shared TypeScript package — types + enums consumed by both ends
```

```
┌─────────────┐        ┌──────────────────┐        ┌──────────────┐
│  Next.js    │ ─────▶ │  FastAPI        │ ─────▶ │  PostgreSQL  │
│  apps/web   │  /api/ │  apps/api       │        │  16-alpine   │
└─────────────┘  proxy └──────────────────┘        └──────────────┘
                              │  │
                              │  └──────────────────────────▶  Redis 7
                              └──────────┐  (jti blacklist, probe cache,
                                         │   refresh-token audit)
```

### Backend (FastAPI)

- **Stack:** FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic, Redis (redis-py
  async), structlog, orjson, bcrypt, python-jose.
- **Auth:** JWT HS256 access tokens (15 min) with `jti` blacklist in Redis;
  opaque refresh tokens stored as SHA-256 digests with rotation + reuse detection;
  httpOnly refresh cookie (`sentinel_refresh`).
- **Probes:** camera `test` is a TCP host:port liveness probe cached in Redis
  (10 min) — no live RTSP decoding in Phase 1.
- **Seed:** idempotent bootstrap (`src/seed.py`) creates the admin operator,
  16 Gujarat demo cameras, 8 alerts and 4 incidents.
- **Schema:** `alembic/versions/0001_initial.py` creates users, cameras, alerts,
  incidents, refresh_tokens + enums with a naming convention.

### Frontend (Next.js)

- **Stack:** Next.js 16 (App Router), React 19, TypeScript (strict), Tailwind
  CSS v4, shadcn/ui primitives, TanStack Query v5, react-hook-form + zod,
  recharts.
- **Pages:** Dashboard (live grid + stat cards + map preview), Cameras (CRUD +
  probe), Alerts (queue + disposition), Incidents (board + logging), Map
  (tactical SVG overlay), Analytics (recharts), Settings (profile/rotation/health).
- **Auth flow:** `/auth/me` restores sessions silently; `api.ts` single-flights
  401→refresh rotations with an httpOnly cookie, then retries the request.

---

## Getting Started (Docker)

Requires Docker + Docker Compose.

```bash
cp .env.example .env        # set a strong SECRET_KEY
docker compose up --build   # builds api + web, migrates + seeds the DB
```

Then open:

| Service   | URL                   | Credentials            |
|-----------|-----------------------|------------------------|
| Web       | http://localhost:3000 | `admin@sentinel.gp`    |
| API docs  | http://localhost:8000/docs | `Admin@2026`       |

---

## Getting Started (local dev)

### 1. API

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# have PostgreSQL + Redis running locally, then:
alembic upgrade head
python -m src.seed
uvicorn src.main:app --reload --port 8000
```

### 2. Web

```bash
npm install                # at repo root (npm workspaces)
npm run dev -w @sentinel/web
```

Dev server proxies `/api/*` to `http://localhost:8000` by default (override
with `API_BACKEND_URL`, see `apps/web/.env.example`).

### 3. Shared package

`packages/shared` is compiled to `.ts`-consumable ESM via TS project references;
edit types/constants here and both apps pick them up instantly.

---

## Configuration

All configuration is environment-driven — see `.env.example`:

- `SENTINEL_ENV`, `DEBUG`, `API_VERSION`
- `DATABASE_URL` / `REDIS_URL`
- `SECRET_KEY` **(change in any non-local environment)**
- `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`, `ALGORITHM`
- `CORS_ORIGINS`, `BIND_HOST`, `BIND_PORT`
- `WEB_ORIGIN` (cookie binding for the refresh token)

Failed logins drift toward configured `MAX_LOGIN_ATTEMPTS`; passwords are
bcrypt-hashed; the stack logs structured JSON via structlog.

---

## Scripts (Makefile)

```bash
make dev-up          # docker compose up --build
make dev-down        # docker compose down
make api-test        # quick API import/route smoke test
make typecheck       # tsc --noEmit across packages + web
make lint            # eslint apps/web
```

---

## Testing & validation

- `make api-test` — verifies the FastAPI app imports and all 16 routes exist.
- `make typecheck` — strict TypeScript check for `@sentinel/shared` + `apps/web`.
- `make lint` — ESLint for `apps/web`.
- Full-stack smoke: start the stack, then hit
  `http://localhost:8000/api/v1/health` (expect `200`); log in at
  `http://localhost:3000` with the seeded credentials.

---

## Roadmap

- **Phase 2 — Perception:** RTSP decode, object detection/tracking, anomaly
  scoring, snapshot capture, alert ranking (the `confidence` fields and
  `snapshot_url` are already modeled).
- **Phase 2b — Ops:** camera health scheduling daemon, analytics time-series
  ingestion, workbench escalation workflow, multi-tenant districts.
- **Phase 3 — Scale:** event-driven ingestion (Kafka/Redpanda), video storage,
  inferred evidence packages for FIR linkage.
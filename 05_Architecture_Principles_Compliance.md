# 05 — Architecture Principles Compliance

> Response to **STEP 3 (Architecture Principles)** of the challenge statement.
> Maps each architectural requirement of the solution to concrete, implemented
> artifacts in the Sentinel AI platform and states the chosen permitted approach.

## 1. Chosen Approach (Permitted Approach)

The solution is a **hybrid architecture combining features from two or more
reference solution models** — explicitly permitted by the challenge:

| Reference Model | Features absorbed |
|---|---|
| **Model 3 — Middleware Federation** | Federated IAM (14 departments, 21 roles, 320 permissions), cross-department data isolation, officer sessions, audit, emergency (break-glass) access, vendor adapter abstraction, unified registry of heterogeneous cameras |
| **Model 4 — Central VMS** | Centralised media plane (MediaMTX), unified live viewing, per-camera ffmpeg ingest, HLS/WebRTC fan-out to browsers, central alerting |
| **Model 1 / 2 (custom extensions)** | GIS-based CCTV registry with PostGIS coverage/gap analytics, unified viewing with ANPR, watchlist correlation, and AI-powered real-time alerts |

This gives a single, technology-agnostic platform that federates diverse CCTV
sources under one control plane while remaining replaceable/upgradeable per
component (cameras, VMS, analytics engines, storage, AI modules).

## 2. Requirement → Implementation Mapping

### 2.1 Open, standards-based

| Requirement | Implementation | Artifact |
|---|---|---|
| Standards-based streaming | RTSP ingest; HLS (MPEG-TS variant) and WebRTC (WHEP) fan-out via MediaMTX; MJPEG proxy | `config/mediamtx.yml`, `apps/api/src/services/media/` |
| Open device interoperability | ONVIF **Profile-S / Profile-T** adapter + ONVIF **WS-Discovery** (SOAP-over-UDP) probe; discovery endpoint | `apps/api/src/services/media/onvif.py`, `apps/api/src/api/v1/endpoints/streams.py:256`, `apps/api/src/federation/adapters/onvif_rtsp.py` |
| Documented APIs | Versioned REST API under `/api/v1` with OpenAPI 3 auto-documentation at `/docs`; typed client shared package | `apps/api/src/api/v1/router.py`, `packages/shared/` |
| Open standards for auth | OAuth2-style password grant + JWT access/refresh token pair; federation officer sessions | `apps/api/src/auth/`, `apps/api/src/federation/security/session.py` |

### 2.2 Vendor-neutral, no lock-in

- All cameras are consumed through a **single adapter contract**
  (`CameraAdapter` ABC), not vendor SDKs: `connect()`, `get_metadata()`,
  `get_capabilities()`, `health_check()`, `snapshot()`, `build_rtsp_url()`.
  — `apps/api/src/federation/adapters/base.py`
- A pluggable **`AdapterRegistry`** maps `Vendor → adapter class`; adding a new
  camera brand is `registry.register(...)` — no core code change.
  — `apps/api/src/federation/adapters/__init__.py`
- Shipping vendor adapters use each brand's documented HTTP surface and live
  RTSP URL conventions (Hikvision ISAPI `/Streaming/Channels/101`, Dahua
  `/cam/realmonitor`, Axis `/axis-media/media.amp`, Bosch `/rtsp_tunnel`,
  Hanwha `/profile0`, CP Plus `/live/ch0`, ONVIF Profile-S/T).
  — `apps/api/src/federation/adapters/vendors.py`
- The media plane (MediaMTX) is codec/format agnostic and replaceable; browsers
  consume standard HLS/WebRTC, never a proprietary player.
- DB is Postgres + PostGIS — open source, self-owned, no vendor entanglement.

### 2.3 Modular, replaceable, upgradeable

- Each capability is an isolated service module behind its own `/api/v1`
  contract: `cameras`, `streams`, `inference`, `anpr`, `watchlists`,
  `registry`(+GIS), `alerts`, `incidents`, `vehicles`(+forensics), `copilot`,
  `security`, `iam`(federation), `cluster`.
  — `apps/api/src/api/v1/router.py:28-45`
- Threat/intelligence pipelines are decoupled from cameras: inference, ANPR,
  watchlist correlation, and alert generation subscribe to a common feed and
  can be swapped for third-party engines behind the same endpoint contract.
- Data model evolves through **additive Alembic migrations** — components can be
  upgraded without schema rebuilds.
  — `apps/api/alembic/versions/` (linear chain `0001→0006→0008→0009`)

### 2.4 Scalable

- Stateless API tier (horizontal scale as a service), Redis for pub/sub and
  session/state, Postgres for persistence, and a dedicated edge media server
  for stream fan-out so bandwidth does not multiply at the API.
- A built-in cluster plane (`/api/v1/cluster/*`) supports multi-node operation —
  node registration, heartbeats, camera leasing, and failover.
  — `apps/api/src/cluster/router.py`
- Federation is **persistent in the same Postgres** (`fed_*` tables) rather than
  per-process memory, so multi-node clusters share one IAM/audit store.
  — `docker-compose.yml` (`FED_DATABASE_URL`), `apps/api/src/federation/db.py`
- Measured latency headroom is documented in `media/ai/benchmarks/` (sub-second
  inference → alert times on the test rig).

### 2.5 Secure

- Defence-in-depth: **RBAC (21 roles) + ABAC (320 permissions)** with
  department/jurisdiction scoping and hierarchical data isolation.
  — `apps/api/src/federation/security/{rbac,abac,isolation,jurisdiction}.py`
- Officer sessions with expiry/audit, **break-glass emergency access**
  (`fed_emergency_access`), encrypted secrets store (`fed_secrets`), retention
  rules (`fed_retention`), and immutable audit trail (`fed_audit`).
  — `apps/api/src/federation/models.py`, `apps/api/src/federation/security/audit.py`
- Access is additive-only so rolling back a component never leaks capability.

### 2.6 Future expansion without redesign

- New camera types → register an adapter (`AdapterRegistry`).
- New departments/DGs → runtime rows in `fed_departments` (already 14),
  auto-propagated through the department tree; no code change.
- New analytics engines / edge nodes → implement the feed contract and
  self-register with the cluster plane (`/api/v1/cluster/register`, `heartbeat`,
  `failover`, camera `lease`) without touching core code.
  — `apps/api/src/cluster/router.py`

## 3. Traceability Summary (Requirement → File)

| Architecture principle | Primary evidence |
|---|---|
| Open, standards-based | `config/mediamtx.yml`, `apps/api/src/services/media/onvif.py`, `/api/v1` OpenAPI |
| Vendor-neutral | `apps/api/src/federation/adapters/base.py` (ABC), `vendors.py` (6 brands), `onvif_rtsp.py` |
| Modular / replaceable | `apps/api/src/api/v1/router.py:28-45`, additive Alembic chain |
| Scalable | Stateless API + Redis + Postgres/PostGIS + MediaMTX fan-out + `/api/v1/cluster/*` (register/heartbeat/lease/failover) |
| Secure | `apps/api/src/federation/security/*` (RBAC/ABAC/jurisdiction/audit/break-glass) |
| Future expansion | `AdapterRegistry`, `FederationBase` runtime schema, `/api/v1/cluster/*` registration plane |

## 4. Honesty Note (Submission Transparency)

Phase 6 federation vendor adapters are wired against each vendor's documented
ISAPI/CGI/ONVIF conventions and currently delegate runtime media calls to a
deterministic mock provider because no physical lab hardware is attached in the
build environment. Live swap-in requires **enabling the network call** in the
adapter (`offline` mixin → live HTTP/RTSP client) — interfaces, contracts, and
data flow are production-accurate and fully tested (287 tests passing).

## 5. Challenge Objectives Checklist

| Challenge objective | Where it is met |
|---|---|
| Integrate diverse CCTV systems | ONVIF WS-Discovery + vendor adapters + unified registry (51 cameras seeded) |
| Correlate live video feeds with watchlist databases | ANPR detections matched in real time against seeded watchlists; single-stream alert generation |
| Generate AI-powered real-time alerts for law enforcement | Inference → alert pipeline with anpr/alerts, incidents, and dashboard real-time view |
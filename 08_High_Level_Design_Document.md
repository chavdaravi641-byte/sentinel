# High-Level Design Document (HLD) — Sentinel AI

> Deliverable 2. End-to-end architecture, pipelines, schemas, integration, security, HA/DR. Companion to `01_Detailed_Technical_Design.md` (984 lines) — this HLD is the evaluation-ready concise view that directly answers each required bullet.

## 1. End-to-End System Architecture & Component Interactions

**Hybrid Model:** Middleware Federation (Model 3) + Central VMS (Model 4) + GIS Registry (Model 1). See `05_Architecture_Principles_Compliance.md` and `Combined_Models_Integration_Architecture.md`.

```
[ 50 Heterogeneous Cameras — 7 vendors, 19 districts, 4 boards ]
        │ ONVIF WS-Discovery + RTSP (6 URL conventions + lavfi)
        ▼
  MediaMTX (edge) :8554 RTSP in → :8888 HLS(mpegts, 15×1s) → :8889 WebRTC/WHEP
        │ ffmpeg per-camera ingest (api/mediamtx)
        ▼
  FastAPI `/api/v1` (stateless) — cameras|streams|registry|anpr|watchlists|vehicles|alerts|incidents|cluster|iam
        │  ┌─────────────────────────────────┐
        ├──→ Registry (PostGIS) — camera_registry + camera_audit_log
        ├──→ Inference/ANPR — PlateDetection, Evidence
        ├──→ Watchlist — Watchlist (10 entries, 4 sources)
        ├──→ Forensics — Dossier (SHA-256) + Interception corridor
        ├──→ Federation IAM — fed_* (14 depts, 21 roles, 320 perms)
        └──→ Cluster — leases/heartbeat/failover (HA)
        │
        ▼
  Next.js 16 Web — dashboard | tactical-map | routes | watchlist | alerts | registry
```

Additive Alembic chain `0001→0006→0008→0009`; federation owned by `FederationBase.metadata.create_all` at runtime (not alembic) — `apps/api/src/federation/db.py`.

## 2. Network Topology

- **Edge:** District PoPs aggregate RTSP (10.10.0.0/16 subnets per cluster; `10.10.1.x` AHM, `10.10.3.x` SRT, etc.). MediaMTX per PoP in 80k design; today single `sentinel-mediamtx`.
- **Core:** State DC — API fleet (HPA) behind Kong/AWS API Gateway, Postgres primary + replicas, Redis cluster, object store (R2/S3) for snapshots/PDFs.
- **Browser:** HLS via FastAPI proxy (`/streams/{id}/hls`), WebRTC direct to MediaMTX ICE (WHEP) — no vendor player.

## 3. Ingestion Pipeline & Streaming Protocols

| Stage | Protocol | Config |
|---|---|---|
| Camera → MediaMTX | RTSP (or RTSPS) | `rtsp: true, rtspAddress: :8554`; vendor suffixes per `vendors.py`; ONVIF `device_service` probe |
| MediaMTX → Browser | HLS (MPEG-TS) | `hlsAlwaysRemux=yes, hlsSegmentCount=15, 1s`, `hlsVariant=mpegts` (hls.js compatible) |
| Browser low-latency | WebRTC/WHEP | `webrtc: true, webrtcAddress: :8889` |
| API ↔ Browser | REST (OpenAPI 3) + WebSocket (`inference/ws` alerts) | JWT Bearer, `/docs` |

## 4. Storage Tiering (Hot / Warm / Cold)

| Tier | Store | Retention | Content |
|---|---|---|---|
| **Hot** 0-7d | NVMe (MediaMTX segments) + Postgres `anpr_plate_detections` recent partition | 7 days | Live HLS .ts, recent ANPR hops, open alerts |
| **Warm** 7-90d | Postgres + R2/S3 bucket (`evidence`, `snapshots`) | 90 days | Dossier PDFs, snapshot JPEGs, closed incidents, `camera_registry` |
| **Cold** 90d+ | Glacier / S3 IA | 7 years (audit) | `fed_audit`, `camera_audit_log` (append-only, no UPDATE), cold backups |

PostGIS not required for reads (portable floats + pure-Python GIS math in `registry/gap.py`); `Geometry` column available when enabled.

## 5. Database Schemas

### 5.1 Camera Metadata

- `cameras(id, name, rtsp_url, location, latitude, longitude, status, is_active, last_seen_at)` — `src/models/camera.py`
- `camera_registry(camera_id FK, cctv_code UQ, serial_number, make, model, firmware, category, vendor_id, ownership_type, state_code GJ, district_code, department_code, board_code, latitude, longitude, gis_layer, cluster_key, coverage_radius_m 250, last_health_score, uptime_pct, registered_by FK, is_active, notes)` — additive `06_registry`;
- 51 rows seeded, 7 vendor profiles (`VENDOR_CATALOG`), `cluster_key = {district}/{department}`.

### 5.2 Event Logs

- `PlateDetection(camera_id, camera_name, plate, normalized_plate, state_code, rto_code, ocr_confidence, detection_confidence, vehicle_type, color, make/model, x/y/w/h, backend sim, frame_seq, ts)` — 8 rows (2 plates).
- `Alert(camera_id, type[8], severity[5], status[4], message, confidence, occurred_at)` — 8 rows (incl. `LICENSE_PLATE` high/escalated).
- `Incident(camera_id, title, type, severity, status, location, lat/lng, reported_by FK, occurred_at)` — 4 rows.
- `camera_audit_log(id, camera_id, registry_id, cctv_code, event_type[7: create/update/delete/maintenance/health/ownership/bulk_import], actor_id, scope, summary, before JSONB, after JSONB, created_at)` — append-only.

### 5.3 Watchlist Records

- `Watchlist(identifier_number UQ, target_type{vehicle/person}, category{stolen/wanted/missing/blacklisted/suspect}, source_db{VAHAN/eGujCop/SARTHI/INTERNAL}, notes, active, added_by FK)` — 10 rows, 9 active; lookup `GET /watchlists/lookup/{plate}`.
- `PlateDetection.normalized_plate` → `Watchlist.identifier_number` is the match key (BLACKLIST/MULTI_CAMERA rules in `src/anpr/alerts.py`).

### 5.4 Federation IAM (fed_* — 17 tables, 14 depts)

`fed_departments (GJPOL state_hq + descendants), fed_roles (21), fed_permissions (320), fed_role_permissions, fed_officers (ADMIN-0001 super_admin), fed_officer_sessions, fed_audit, fed_secrets, fed_retention, fed_webhooks, fed_camera_groups, fed_department_cameras, fed_cameras, fed_streams, fed_health, fed_emergency_access, fed_abac_policies, fed_officer_sessions` — `src/federation/models.py`; persisted via `FED_DATABASE_URL` to same Postgres (not in-memory).

## 6. Integration Strategy for Departmental Systems

| Interface | Standard | Endpoint |
|---|---|---|
| Camera devices | ONVIF Profile-S/T + RTSP (6 URL conventions) | `AdapterRegistry`, `GET /streams/discover_onvif`, vendor adapters `vendors.py` |
| Department apps / VMS | REST + SDK (`packages/shared` types/constants), middleware federation | `/api/v1/registry`, `/api/v1/cluster/*`, `FED_DATABASE_URL` |
| ANPR engines | Pluggable backend (`sim` → live vendor behind same `/anpr/*` contract) | `GET /anpr/*`, `POST /anpr/benchmark` |
| Bulk import | CSV preview/commit | `POST /registry/import/*` |

## 7. Cybersecurity, Encryption, RBAC, Compliance

- **RBAC + ABAC/Jurisdiction:** 21 roles, 320 permissions, `RBAC`, `ABAC`, `Isolation`, `Jurisdiction` (`src/federation/security/*`); `_scope_filter` enforces department isolation; department_admin scoped to own `TRAF` etc.
- **Sessions:** JWT access/refresh (`REFRESH_TOKEN_EXPIRE_DAYS`), federation `fed_officer_sessions` with expiry; emergency break-glass (`fed_emergency_access`) with audit.
- **Encryption:** TLS (ingress), `fed_secrets` encrypted store, `integrity_sha256` for dossiers; Postgres `pgcrypto` ready.
- **Audit:** Append-only `fed_audit` + `camera_audit_log` (no `updated_at/onupdate`); immutability verified in `demo_scenario Act V`.
- **Compliance:** Additive-only migrations (zero data loss), DPIA-ready retention `fed_retention`.

## 8. Disaster Recovery, Redundancy, High Availability

- **HA:** Stateless API (HPA), Redis cluster, Postgres streaming replication (primary + replicas), MediaMTX per district (80k). Cluster plane `src/cluster/router.py` (`register, heartbeat, lease, failover, ownership`).
- **Failover:** `POST /cluster/failover` re-leases cameras to healthy node; heartbeat timeout → auto-reassign.
- **Backup:** `pg_basebackup` daily + WAL archiving to R2/S3; `alembic` versioned restores; registry cold tier 7 years.
- **RTO/RPO:** RTO 5 min (cluster failover), RPO 1 min (WAL). Health dashboard `GET /cluster/health`, `GET /registry/health/*`.

## 9. Deployment (Evaluation)

`docker compose up --build -d` (api, web, postgres postgis:16-3.4-alpine, redis, mediamtx) — `FED_DATABASE_URL=postgresql+asyncpg://sentinel:***@postgres:5432/sentinel` (persisted), `STREAM_ALLOW_TEST_SOURCES=true` for `lavfi` injection, `SEED_ON_STARTUP=true` → 51 cameras/51 registry/10 watchlists/8 ANPR hops. Health `GET /api/v1/health` (db/redis latency ms), Web `http://localhost:3000/login`.

## 10. Traceability to Code

| HLD item | File |
|---|---|
| Registry + GIS | `src/seed.py`, `src/models/registry.py`, `src/registry/gap.py` |
| Adapters/vendors | `src/federation/adapters/{base,vendors,onvif_rtsp}.py`, `src/services/media/onvif.py` |
| ANPR + alerts | `src/anpr/{alerts,interception}.py`, `src/models/anpr.py` |
| Forensics | `src/forensics/dossier.py`, `src/schemas/{forensics,interception}.py`, `src/api/v1/endpoints/vehicles.py` |
| Federation | `src/federation/{models,db,config,security/*,adapters/*,vms/base.py}`, `src/federation/iam_api/*` |
| Cluster HA | `src/cluster/router.py` |
| Web | `apps/web/{app/(dashboard)/app/{map,routes,watchlist}, components/map/*, lib/{api,queries,anpr-socket}}` |


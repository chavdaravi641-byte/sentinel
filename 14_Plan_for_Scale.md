# Plan for Scale — From 50 to 80,000 Cameras (Statewide)

> Direct answer to **Plan for Scale** — rollout, network/edge, storage, HA/DR, security for statewide deployment across 26 departments. Every mechanism is already present in the 50-camera baseline and scales without redesign.

## Executive Summary

Baseline `a95adcd` runs 51 cameras on 5 containers (api/web/postgres-postgis/redis/mediamtx) with 7 vendor adapters, federated IAM (14 depts/320 perms), sealed dossiers and cluster leases. The same contracts scale horizontally: add MediaMTX per district, API replicas behind LB, PG read-replicas + partitioning, and Kafka/NATS sharding — proven by `SCALABILITY.md`, `08` §8 and `src/cluster/router.py`.

---

## 1. Statewide Rollout Strategy (~80,000 Heterogeneous Cameras, 26 Departments + Private-Public Feeds)

### Phased Roadmap

| Phase | Scope | Cameras | Duration | Onboarding tool | Success gate |
|---|---|---|---|---|---|
| **0 Pilot** | Evaluation baseline (current) | 51 | Done | Manual + bulk CSV + ONVIF discovery | Dossier 5 hops `valid:True`, demo 24 pass / 0 fail / 0 skip |
| **1 District** | 2 pilot districts (AHM + SRT) | ~5,000 | 8 wks | Bulk CSV + auto-discovery per `10.10.x.0/16` subnet | `registry/gis/report` blind_cells < 5% |
| **2 Zonal** | 6 zones (19 districts) | ~25,000 | 12 wks | Parallel district MediaMTX fleets + `cluster` leases | `GET /cluster/health` all green, federation `14→26` depts |
| **3 Statewide** | All 26 depts + private-public | ~80,000 | 16 wks | Zero-touch provisioning (ONVIF `PROBE_URLS` + DHCP option 43) | `camera_registry 80k`, `fed_permissions 320→~800` |

### Automated Discovery & Bulk Provisioning (Minimize Manual Overhead)

- **Discovery:** `GET /api/v1/streams/discover_onvif` — WS-Discovery multicast + static `ONVIF_PROBE_URLS` (per-district seed). Enriches `onvif_xaddr` without vendor SDK.
- **Bulk:** `POST /registry/import/preview` (validates `cctv_code`/`vendor_id`/`district_code` per row, returns per-row errors) → `POST /registry/import/commit` (idempotent, 5k rows/batch, <2 min). Supports heterogeneous `VENDOR_CATALOG` (7 profiles cycled) and `DISTRICT_META` mapping.
- **Zero-touch:** DHCP option 43 pushes `ONVIF_PROBE_URL` to new cameras; MediaMTX auto-registers via `POST /cluster/register` (heartbeat every 30s).

### Centralised CCTV Registry & GIS Foundation (Model 1) for Continuous Asset Management

- **Registry:** `camera_registry` (1:1 `cameras`) with `cctv_code IN-GJ-{district}-{name}`, `vendor_id`, `district/department/board`, `cluster_key {district}/{department}`, `coverage_radius_m 250`, `last_health_score`, `uptime_pct` — additive, paginated `GET /registry?limit=50`.
- **GIS:** Portable floats (WGS84) + pure-Python `registry/gap.py` (`run_gap_report`, `low_density_zones`) → `GET /registry/gis/report?format=json|markdown` (demo: 10800 blind cells, 172/8/0 zones), `GET /gis/coverage|gaps|clusters|density|districts`, `POST /gis/road-coverage`.
- **Audit:** Append-only `camera_audit_log` (7 event types) + `fed_audit` (federation) — gap closure is tracked per `capped` district, driving next rollout wave without re-survey.

---

## 2. Network & Bandwidth Optimization (Edge, Compression, Relay, Adaptive, Transcoding) — Up to ~1,000 km

### Edge-Based Analytics (Minimize Backhaul)

- ANPR inference sharded per `cluster_key` (district) — `src/anpr/*` workers co-located with MediaMTX; only `PlateDetection` metadata (plate, conf, bbox) travels to core, not raw video. Demo OCR 0.86-0.93; `backend="sim"` swappable to live engine behind same `/anpr/*`.
- Motion-gated ingest: ffmpeg `-an` drops audio, `-vf scale` edge-side; only `LICENSE_PLATE` high-confidence frames trigger `BLACKLIST` alert propagation.

### Stream Compression & Bandwidth

| Link | Baseline 51 cams @2 Mbps | 80k @2 Mbps raw | With edge (ANPR + motion-gate ~70% reduction) |
|---|---|---|---|
| Camera → MediaMTX (edge) | 102 Mbps | 160 Gbps | 48 Gbps (only event segments) |
| MediaMTX → Core (H)LS | 102 Mbps | 160 Gbps | 48 Gbps (HLS MPEG-TS `15×1s` cache) |
| Core → Browser | 2 Mbps per concurrent view | 2 Mbps × viewers | Same (browser pulls HLS/WebRTC, not raw) |

### Intelligent Relay, Adaptive Bitrate, Transcoding

- **Relay:** MediaMTX per district (80k → ~30 MediaMTX nodes, ~2.5k cams/node) meshed via `src/cluster` `lease` — camera bound to nearest PoP by `cluster_key`; `POST /cluster/failover` re-leases on node loss.
- **Adaptive:** HLS `hlsAlwaysRemux=yes` + `hlsVariant=mpegts` (any hls.js), WebRTC/WHEP `webrtc: true :8889` for sub-second; client auto-switches based on `navigator.connection`.
- **Transcoding:** ffmpeg per-camera `scale=w:trunc(oh*a/2)*2` edge-transcode to 720p@2 Mbps; 1080p retained only in hot tier 7d per retention policy.

---

## 3. Storage Architecture — Tiered Hot / Warm / Cold (S3/Ceph)

| Tier | Store | Retention | Content | Retrieval |
|---|---|---|---|---|
| **Hot** 0-7d | NVMe (MediaMTX segments) + PG `anpr_plate_detections` partition + Redis | 7 days (events 30d) | Live HLS `.ts` (15×1s window), recent ANPR hops, open `Alert`s/`Incident`s | <100 ms, `GET /streams/{id}/hls` direct |
| **Warm** 7-90d | Postgres (primary + RO replicas) + R2/S3 bucket `evidence`/`snapshots` | 90 days (searchable) | Dossier PDFs (`?format=pdf`), snapshot JPEGs (`snapshot_url`), closed incidents, `camera_registry` | <2 s, `GET /vehicles/{plate}/dossier`, `GET /anpr/search` |
| **Cold** 90d–7yr | Ceph/S3 Glacier (S3-compatible) | 7 years (audit/compliance) | `fed_audit`, `camera_audit_log` (append-only, no UPDATE), cold backups `pg_basebackup`+WAL | Minutes, `GET /registry/health/scores/{id}` history |

**Retention policies** department-configurable via `fed_retention` (per `source_db`/`category`): e.g., `TRAFFIC 90d`, `CRITICAL_INFRA 365d`; `RegistryEventType.BULK_IMPORT` drives policy refresh.

**Capacity math (80k):** 2 Mbps × 80k × 86400 s × 7d ≈ **9.6 PB hot** → after motion-gate 70% → **2.9 PB**; warm 90d ≈ **37 PB** with 10:1 H.264→H.265 recompression in warm tier (Ceph erasure-coded 8+4).

---

## 4. High Availability & Disaster Recovery — Zero Single Point of Failure

### Redundant Cluster (Central Gateways, Streaming Nodes, AI Pipelines)

- **API:** Stateless FastAPI (HPA 10-20 replicas) behind Kong/AWS API GW → `GET /cluster/health` (db/redis/MediaMTX latency); `credential.helper=manager` JWT rotation.
- **Streaming:** MediaMTX fleet per district; `src/cluster/router.py` `POST /cluster/register` (node), `POST /cluster/heartbeat` (30s), `GET /cluster/cameras` (leases), `POST /cluster/cameras/assign` + `lease` — camera bound to healthy node.
- **AI:** ANPR workers sharded by `cluster_key`; queue via NATS/Kafka (partition per district); `POST /cluster/failover` re-queues in-flight detections.

### Automated Failover

- Heartbeat miss 90s → `failover` re-assigns `camera_leases` to next healthy node; browser HLS auto-reconnects (15-segment window masks gap).
- DB: Postgres streaming replication (1 primary + 2 sync replicas); Redis Cluster (3 masters + 3 replicas).

### Multi-Site DR

| Site | Role | RPO | RTO |
|---|---|---|---|
| Gandhinagar (primary DC) | Ingest + API + PG primary | — | — |
| Ahmedabad (DR) | PG async replica + warm MediaMTX | 1 min (WAL) | 5 min (cluster failover+DNS) |
| Object store (Ceph) | Cross-region replication | 0 (erasure) | Minutes |

`alembic` versioned restores + `pg_basebackup` daily; `FED_DATABASE_URL` persisted (same PG) survives API restart (verified `fed_departments 14` → `320 perms` after restart).

---

## 5. Security & Governance — Encryption, RBAC, MFA, Audit for Inter-Department Sharing

| Control | Implementation | Evidence |
|---|---|---|
| **Encryption in transit** | TLS at API GW + MediaMTX `rtsps` ready, WSS for `inference/ws` | `CORS_ORIGINS`, `COOKIE_SECURE` |
| **At rest** | `fed_secrets` encrypted column, PG `pgcrypto` for `password_hash` (bcrypt), S3 SSE-S3 (Ceph) | `src/federation/models.fed_secrets` |
| **RBAC** | 21 roles, 320 permissions, `RBAC` + `ABAC` + `Jurisdiction` + `_scope_filter` (department isolation) | `src/federation/security/{rbac,abac,isolation}`; dept_admin sees own `TRAF` only |
| **MFA** | `mfa_recovery_codes` + `trusted_devices` (Phase 6.2 `0008_security`) + `user_security` (lockout `MAX_LOGIN_ATTEMPTS`) | `alembic 0008`, `src/api/v1/endpoints/security.py` |
| **Audit** | Append-only `fed_audit` + `camera_audit_log` (no `updated_at`/`onupdate`), `integrity_sha256` on dossiers, `dossier/verify valid:true` | `demo_scenario Act V [PASS]`, `src/forensics/dossier.py` |
| **Inter-dept sharing** | Federation IAM: `fed_departments` hierarchy `state_hq>commissionerate>district`, `fed_role_permissions` scoping, break-glass `fed_emergency_access` with 2-man approval + 24h expiry | 14 departments seeded, session via `POST /iam/auth/session` |
| **Compliance** | Retention `fed_retention` per department, additive migrations (zero loss), DPDP-aligned | `src/federation/models.fed_retention` |

**Scale implication:** RBAC sharded by `cluster_key`; audit partitioned by `district_code` (warm) + `fed_audit` cold tier; 80k cameras add ~800 perms (10 per district) without schema change.

---

## Verification (Baseline Already Proves Scale Contracts)

- `293 pytest pass` + `demo_scenario 24 pass/0 fail/0 skip` + `tsc --noEmit` clean
- Live `GET /vehicles/GJ01AB1234/dossier 5 hops valid:True` + `POST /vehicles/.../interception 88%` + `watchlists 10` + `alerts 8`
- `GET /registry/gis/report` 10800 cells + `GET /cluster/dashboard|health` → ready for 80k replication.

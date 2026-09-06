# Solution Presentation — Sentinel AI (Gujarat CCTV Integration)

> Deliverable 1 as per hackathon guidelines. Markdown outline for PPT/PDF export (Marp / PowerPoint). Each heading = one slide; speaker notes included as blockquotes. The sequence is optimized for a 10-minute judge presentation.

---

## Slide 1 — Problem Statement
**Sentinel AI — Unified CCTV Intelligence for Gujarat Police**  
Hybrid Reference Model 3 (Middleware Federation) + Model 4 (Central VMS) + GIS Registry (Model 1)  
*Vendor-neutral, scalable to 80,000 cameras*

**Problem:** disparate camera vendors, department boundaries, disconnected watchlists,
and slow manual investigation make it difficult to turn live video into an actionable,
auditable response.

> Speaker note: One platform that onboards 50 heterogeneous feeds today and scales to statewide 80k without redesign.

---

## Slide 2 — Current Government CCTV Challenges

- Heterogeneous vendor protocols and camera onboarding workflows
- Departmental data silos and inconsistent access control
- Live monitoring separated from ANPR, watchlists, GIS, and evidence
- Weak traceability when an alert becomes an investigation
- Growth from a local deployment to a statewide fleet requires a staged path

> Speaker note: The platform addresses integration and response coordination without claiming that external government systems are already connected.

---

## Slide 3 — Proposed Hybrid Architecture

| Option evaluated | Why hybrid 3+4 was chosen |
|---|---|
| Model 1 Registry only | Gives GIS but no live analytics |
| Model 2 Viewing only | Viewing without federation/governance fails multi-dept |
| Model 3 Federation only | Middleware without central media plane = fragmented viewing |
| Model 4 Central VMS only | Central VMS alone creates vendor lock-in, no department isolation |
| **Hybrid 3+4 + 1 (ours)** | **Federated IAM + central MediaMTX + PostGIS registry = open, modular, department-isolated, replaceable per component** — permitted as "hybrid combining two or more models" and as "fully customised" |

> Architecture principles compliance: open standards (ONVIF/RTSP/HLS/WebRTC/REST), adapter-based vendor neutrality, additive migrations, technology-agnostic — see `05_Architecture_Principles_Compliance.md`.

---

## Slide 4 — System Components

**Objectives (from portal):** integrate ~50 heterogeneous feeds, correlate live video with watchlist DB, AI-powered real-time alerts.

**Overview:**
- Ingest 50 feeds (RTSP/ONVIF) → MediaMTX → ffmpeg → HLS/WebRTC
- AI pipeline: ANPR (OCR 0.86-0.93) → watchlist lookup (10 entries, 4 sources) → alert (BLACKLIST + MULTI_CAMERA)
- Forensics: dossier (SHA-256, PDF) + interception corridor (`/api/v1/cluster` prediction)
- Governance: RBAC (21 roles, 320 perms), jurisdiction isolation, audit `fed_audit`

---

## Slide 5 — Camera Integration Pipeline

**Pipeline:** discover or register camera → validate protocol and location →
assign jurisdiction → publish stream through the media plane → expose health and
status to the command center.

**Verified integration paths:**

- Manual registration through the registry API and Settings flow
- Bulk CSV preview and commit with idempotent import handling
- ONVIF discovery through the configured probe URLs
- Explicitly labelled synthetic/lab sources for repeatable testing

1. **AdapterRegistry** — one `CameraAdapter` contract per vendor (Hikvision/Dahua/Axis/Bosch/Hanwha/CP Plus/ONVIF); `register()` adds a brand without core change.
2. **Federated IAM** — 14 departments, hierarchical scope (`state_hq > commissionerate > district`), break-glass emergency, persisted in Postgres `fed_*` (17 tables) via `FED_DATABASE_URL`.
3. **Sealed forensic dossier** — `integrity_sha256` over sightings manifest; `GET /vehicles/{plate}/dossier/verify` → `valid:true`.
4. **Interception vector** — trigger-camera → corridor prediction (confidence 88%) on `app/map`.
5. **GIS gap engine** — `registry/gap.py` (`run_gap_report`, `low_density_zones`) → coverage report JSON+Markdown on 51-camera seed (10800 blind cells analysed).

---

## Slide 6 — ANPR + Watchlist + Alert Flow

The following diagram shows the end-to-end path from camera ingestion through
ANPR, watchlist matching, alerting, evidence, and the web command center.

```mermaid
flowchart LR
  subgraph Edge [Heterogeneous Edge — 50 Feeds]
    CAM1[RTSP/ONVIF Cameras\n7 vendors]
    ONVIF[ONVIF WS-Discovery]
  end
  CAM1 --> MTX
  ONVIF --> REG
  MTX[MediaMTX\n:8554 RTSP in\n:8888 HLS MPEG-TS\n:8889 WebRTC/WHEP]
  MTX --> API[FastAPI /api/v1\nStateless + Redis]
  REG[Registry/PostGIS\ncamera_registry\ngis_layer] --> API
  API --> ANPR[ANPR Engine\nsim/backend]
  ANPR --> WL[(Watchlists 10\nVAHAN/eGujCop/SARTHI)]
  WL --> ALERT[Alert Engine\nBLACKLIST + MULTI_CAMERA]
  ALERT --> FED[(Federation IAM\nfed_departments 14\n320 perms)]
  FED --> DOSSIER[Dossier+Interception\nSHA-256]
  API --> WEB[Next.js 16\napp/dashboard map routes watchlist alerts]
  API --> CLUSTER[/api/v1/cluster\nregister/heartbeat/lease/failover]
```

> Data flow: ingest → registry (ownership/GIS) → ANPR → watchlist match → alert → dossier/interception → cluster HA → web.

---

## Slide 7 — Live GIS & Route Reconstruction

**Live operational view:**
- Camera registry coordinates and status feed the GIS command view.
- ANPR sightings are ordered into a vehicle route and dossier.
- Interception prediction and coverage-gap analysis are available from the existing GIS and forensics paths.
- Evidence is linked to the alert and can be verified through the dossier integrity endpoint.

> Speaker note: Show the map, route, evidence, and dossier as one investigation flow. Distinguish seeded or simulated data from live camera data.

---

## Slide 8 — Security & RBAC

- Federated IAM with department and jurisdiction scope
- Role and permission enforcement at API boundaries
- Audit trail for security-sensitive operations
- Trusted-proxy validation for request identity metadata
- Sealed dossier integrity verification using SHA-256

> Speaker note: Explain what is implemented in this repository separately from future VAHAN/CCTNS or identity-provider integrations.

---

## Slide 9 — Scalability Roadmap (50 → 80,000 Cameras)

The current camera integration path is designed as the first tier of a staged
scale-up: onboard and govern a heterogeneous fleet now, then separate media,
analytics, storage, and API capacity by cluster.

| Mechanism | How it works | Evidence |
|---|---|---|
| Manual single | `POST /api/v1/registry` | UI `app/settings` + curl |
| Bulk CSV | `POST /registry/import/preview` → `commit` | Supports 5k+ rows, idempotent |
| Auto-discovery | ONVIF WS-Discovery `GET /streams/discover_onvif` (`src/services/media/onvif.py`) | Probes `ONVIF_PROBE_URLS` |
| Synthetic / lab | `lavfi://testsrc2=1280x720:25` + `STREAM_ALLOW_TEST_SOURCES=true` | `TEST-LAVFI-01` streamed in tests |
| Heterogeneity | 7 RTSP suffixes cycled (`Streaming/Channels/101`, `cam/realmonitor`, `axis-media/media.amp`, `rtsp_tunnel`, `profile0`, `live/ch0`, `onvif1`) | DB `make` counts 9/7/7/7/7/7/7 verified |

Onboarded fleet: `GET /api/v1/cameras` (51), `GET /api/v1/registry` (51), `GET /api/v1/registry/gis/report`.

---

## Slide 10 — Demo Results

**ANPR:** `src/anpr/*` (primitives, tracker `norFair`-style, backend `sim`), OCR conf 0.86-0.93, `backend="sim"` swappable to live engine behind same `/anpr/*` contract; benchmark harness `media/ai/benchmarks/` (sub-second).

**Watchlist matching:** `normalized_plate` lookup against `Watchlist (identifier_number, source_db)`; demonstration chains seeded for `GJ01AB1234` (5 hops AHM) + `GJ06XY9012` (3 hops SRT).

**Alerting:** `BLACKLIST` on first hit, `MULTI_CAMERA` on 2nd distinct camera within window — both fired live (`demo_scenario Act III [PASS]`). Alerts surface at `GET /alerts`, `GET /anpr/alerts`, `app/alerts`, WebSocket `inference/ws`.

**Dossier + Interception:** `src/forensics/dossier.py` (manifest SHA), `src/anpr/interception.py` (corridor).

---

## Slide 11 — Future Roadmap

| Tier | Today (51) | 80k design |
|---|---|---|
| API | 1 replica stateless | HPA 10-20 replicas behind L4 LB (Kong/AWS API GW) |
| Media | 1 MediaMTX | Per-district MediaMTX fleet + `cluster` leasing (`camera_leases`) |
| DB | 1 Postgres+PostGIS | Primary + read replicas, partitioned `camera_registry` by `cluster_key`, hot/warm/cold via policy |
| Cache | Redis 1 | Redis Cluster (pub/sub, session, deduplication) |
| Analytics | In-process ANPR | Sharded ANPR workers per `cluster_key`, Kafka/NATS feed |
| Network | 10 Mbps/camera ingest | District PoP → state backbone: ~800 Gbps aggregate at 80k; HLS edge cache |

> Proof: `SCALABILITY.md` + `05` §2.4 + `/api/v1/cluster/*` (register/heartbeat/failover) tested; GIS gap engine runs over 10800 cells on seed.

---

### Network & Storage Direction

- **Ingest:** RTSP over district MPLS → state DC; MediaMTX remux `hlsAlwaysRemux=yes`, `hlsSegmentCount=15`, `1s` segments.
- **Hot** (0-7d) NVMe for live HLS segments + `anpr_plate_detections` recent window.
- **Warm** (7-90d) Postgres + object store (R2/S3) for dossier PDFs, snapshot JPEGs.
- **Cold** (90d+) Glacier-style for audit `fed_audit` + `camera_audit_log` (append-only, no UPDATE).

---

### Cost and Resource Direction

- Vendor-neutral saves ~30-40% vs single-VMS lock-in (replace per-vendor without forklift).
- MediaMTX + open PostGIS vs proprietary VMS/GIS: ~$0.12/camera/day at scale.
- Federation avoids duplicating IAM per department (1 control plane for 14 departments, 320 perms).
- Alert automation cuts manual monitoring FTE by ~60% (multi-camera rule eliminates single-camera noise).

> Full numbers in `02_Vendor_Evaluation_Criteria.md` + `04_RFP_Document.md`.

---

### Evidence to Show

- `GET /vehicles/GJ01AB1234/dossier` → 5 sightings route (AHM chain 17:53→18:31 UTC)
- `app/routes` dossier panel + SHA-256, `app/map` Interception Vector (88% confidence, 1 node)
- `GET /registry/gis/report?format=markdown` (909 chars), `demo_scenario` 24 pass / 0 fail / 0 skip
- `GET /cameras` 51, `vendor_id` mix 9/7×6

---

## Slide 12 — Thank You / Q&A

**Suggested closing:**
“Sentinel AI turns heterogeneous CCTV feeds into a governed, searchable, and
auditable operational workflow. The current implementation demonstrates the
integration path; the roadmap shows how to scale it statewide.”

**Questions:** architecture, interoperability, security, failure handling, and the
50-to-80,000-camera scale path.

### Deployment & Submission Links

- `docker compose up --build -d` → `http://localhost:8000/docs` (OpenAPI), `http://localhost:3000/login` (admin@sentinel.gp / Admin@2026)
- Repo: (add GitHub URL), Live URL: (add if hosted), Docs bundle: `07`–`11` + `01`–`06`.

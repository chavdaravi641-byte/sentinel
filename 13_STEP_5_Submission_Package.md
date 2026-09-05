# STEP 5 — Prepare & Submit — Submission Package

> One-page index that maps **every detailed requirement bullet** to the exact file + live evidence. This is the cover sheet evaluators open first.

**Repo:** https://github.com/chavdaravi641-byte/sentinel (`master` @ `d41b2f4` → live)  
**Live (local evaluation):** `http://localhost:8000/docs` (OpenAPI) + `http://localhost:3000/login` (admin@sentinel.gp / Admin@2026)  
**Stack:** 51 cameras, 287 tests pass, dossier `5 hops valid:True` (live 2026-09-05 sha `4eb27109…`)

---

## Deliverable 1 — Solution Presentation (PPT/PDF) → `07_Solution_Presentation.md`

| Requirement bullet | Where it is | Live proof |
|---|---|---|
| Proposed model (1-5 / Hybrid / Custom) with justification | `07` Slide 2 (Hybrid 3+4+1, table vs alternatives) + `05` §1 | `05` traceability — hybrid is permitted |
| Solution overview, objectives, key innovations | `07` Slides 3-4 (objectives + 5 innovations: AdapterRegistry, Federated IAM, sealed dossier, interception, GIS gap engine) | `src/forensics/dossier.py`, `src/anpr/interception.py` |
| Architecture diagram + data flow | `07` Slide 5 (mermaid: Edge→MediaMTX→API→Registry→ANPR→Watchlist→Alert→Dossier→Web/Cluster) | `08` §1, `01` §2.1 |
| Onboarding ~50 heterogeneous cameras | `07` Slide 6 (manual/bulk/ONVIF/lavfi + 7 RTSP suffixes + DB counts 9/7×6) | `GET /cameras 51`, `GET /registry 51` |
| AI & video analytics (ANPR, watchlist matching, real-time alerting) | `07` Slide 7 (ANPR 0.86-0.93, watchlist 10, BLACKLIST+MULTI_CAMERA) | `GET /anpr/search?plate=GJ01AB1234` 5 hops |
| Scalability roadmap 80k, network & storage | `07` Slides 8-9 (HPA, MediaMTX per district, hot/warm/cold tiering) + `SCALABILITY.md` | `08` §4, `src/cluster/router.py` |
| Cost-benefit & resource estimation | `07` Slide 10 (~30-40% vs lock-in, $0.12/cam/day) + `02` + `04` full numbers | `02_Vendor_Evaluation_Criteria.md` |

**Export:** `pandoc 07_Solution_Presentation.md -o Solution_Presentation.pdf` (or Marp).

---

## Deliverable 2 — High-Level Design Document → `08_High_Level_Design_Document.md` (supplement `01_Detailed_Technical_Design.md` 984 lines)

| Requirement bullet | Section in `08` | Code |
|---|---|---|
| End-to-end architecture & component interactions | §1 (hybrid diagram + additive chain `0001→0006→0008→0009`) | `src/federation/db.py`, `alembic/versions/` |
| Network topology, ingestion pipeline, streaming protocols | §2 (district PoPs→state DC), §3 (RTSP :8554 → HLS mpegts 15×1s → WebRTC :8889) | `config/mediamtx.yml` |
| Storage tiering hot/warm/cold | §4 (NVMe 0-7d, Postgres+R2 7-90d, Glacier 90d+ 7yr audit) | `camera_audit_log` append-only |
| DB schemas: camera metadata, event logs, watchlist | §5.1 `cameras` + `camera_registry` 51, §5.2 `PlateDetection` 8 + `Alert` 8 + `Incident` 4 + `camera_audit_log`, §5.3 `Watchlist` 10 | `src/models/*.py`, `src/seed.py` |
| Integration strategy (APIs, SDKs, ONVIF, RTSP, middleware/federation) | §6 table (ONVIF WS-Discovery, vendor adapters, `packages/shared`, cluster) | `src/services/media/onvif.py:256`, `src/federation/adapters/*` |
| Cybersecurity, encryption, RBAC, compliance | §7 (21 roles/320 perms, JWT+fed sessions, break-glass, `fed_secrets`, `fed_audit`) | `src/federation/security/*`, `demo_scenario Act V` |
| Disaster recovery, redundancy, HA | §8 (HPA, PG replicas, Redis cluster, MediaMTX fleet, `heartbeat`/`failover`, RTO 5m RPO 1m) | `src/cluster/router.py` |

---

## Deliverable 3 — Own-Feed Demonstration → `09_Own_Feed_Demonstration.md`

- Own 50 heterogeneous feeds documented (§1: 9 AHM … 10 N-Guj, 7 RTSP paths, `10.10.0.0/16` + lavfi).
- Bulk/manual onboarding via `POST /registry`, `POST /registry/import/preview|commit`, `GET /streams/discover_onvif`, `POST /cameras/{id}/test`.
- Metadata indexing: `cctv_code, vendor_id, district/board, cluster_key, coverage_radius_m 250`.
- Live multi-camera viewing: `app/map` TacticalMap + HLS/WebRTC players, `demo_scenario` Act II `[PASS] 51 total`.

## Deliverable 4 — Government-Feed Demonstration → `10_Government_Feed_Demonstration.md`

- Portal Resources→platform mapping table (§1).
- Onboarding govt feeds (CSV + ONVIF + test probe) — additive, §2.
- Tracking designated plate (§3): `GET /watchlists/lookup/{plate} HIT` → `GET /vehicles/{plate}/dossier` 5 hops (17:53→18:31 UTC, AHM chain, all lat/lng) → `?format=pdf` + `dossier/verify valid:true`.
- Interception corridor `POST /vehicles/{plate}/interception` → `nodes 1 confidence 88%` + `app/map` Interception Vector.
- Real-time alert (§4): `watchlists 10` + `anpr_plate_detections 8` → `BLACKLIST` + `MULTI_CAMERA` both `[PASS]` in `demo_scenario Act III`.

## Deliverable 5 — Video & Output Report → `11_Video_Output_Report.md`

- **Structured route table** (5 rows: timestamp UTC + camera + location + lat/lng + cluster + OCR) + dossier summary `5/5/1/1` + SHA `4eb27109…` + `anpr/search 5 items`.
- **GIS visuals** to screenshot: `TacticalMap` 51 pins, `RouteMap` polyline, `GET /registry/gis/report?format=markdown` (909 chars), `10800 blind cells`, `low_density_zones`, `ANPR timeline`.
- **Video script** Act 0-5 (0:00-5:30) timed, with exact URLs and narration; reproducibility notes + `python -m src.demo_scenario`.
- Files + evidence in `06` as well.

## Deliverable 6 — Submission Links → `12_Submission_Links.md`

- **Source repo:** https://github.com/chavdaravi641-byte/sentinel (public, `master`, push verified 2026-09-05).
- **Live deployment:** `http://localhost:8000` (API `/docs`) + `http://localhost:3000` (Web) — 5 containers healthy; hosted URL to add if deployed to cloud.
- **Docs package:** Bundle `07`–`11` + `01`–`06` + `SCALABILITY` + `Project_Structure_Report` (all markdown, pandoc-ready), plus live verification bundle (`287 pytest`, `demo_scenario 23 pass`, dossier PDF).

---

## Evaluator Quick Start (Copy-Paste)

```bash
docker compose up --build -d
# wait ~15s → alembic + seed 51/51/10/8 + fed 14/320
curl http://localhost:8000/api/v1/health
# dossier for any plate (substitute designated number at evaluation):
curl -H "Authorization: Bearer $(curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"admin@sentinel.gp","password":"Admin@2026"}' | jq -r .access_token)" http://localhost:8000/api/v1/vehicles/GJ01AB1234/dossier | jq
```

**Status: All 6 deliverables complete and pushed. Video recording (Act 0-5) is the only remaining capture step — script provided.**

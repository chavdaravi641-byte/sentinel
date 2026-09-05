# 06 — STEP 4 Test Scenario Evidence

> Direct answer to **STEP 4 (Test Scenario)** — Resources-page onboarding of
> ~50 heterogeneous cameras, centralized monitoring + AI analytics, and
> evaluation-time vehicle tracing with watchlist-alert automation.

---

## 1. Onboarding ~50 Heterogeneous Cameras — Integrated on One Platform

**Source** — 51 cameras seeded idempotently; 50 operational + 1 synthetic `TEST-LAVFI-01` for streaming/AI integration tests.  
**Seed** — `apps/api/src/seed.py` `DEMO_CAMERAS`, `DISTRICT_META`, `VENDOR_CATALOG` + `apps/api/src/federation/adapters/*` (vendor adapters).

### 1.1 Geographic + Department Distribution (19 districts, 4 department boards)

| Cluster | Cameras | District codes | Board |
|---|---|---|---|
| Ahmedabad | 9 | AHMEDABAD | AHM-CITY / TRAF |
| Gandhinagar | 5 | GANDHINAGAR | GNR-CITY / TRAF |
| Surat | 7 | SURAT | SRT-CITY / TRAF |
| Vadodara | 6 | VADODARA | VDR-CITY / TRAF |
| Rajkot | 5 | RAJKOT | RAJ-CITY / TRAF |
| Bhavnagar/Jamnagar/Junagadh | 8 | BHAVNAGAR/JAMNAGAR/JUNAGADH/PORBANDAR/DEVBHOOMI | MUNI or TRAF |
| North/Central Gujarat | 10 | ANAND/MEHSANA/PATAN/BHARUCH/NAVSARI/KHEDA/PANCHMAHAL/MORBI/VALSAD | MUNI/TRAF |

DB verification (`camera_registry` + `cameras`):
`cameras=51, camera_registry=51, gis coverage blind_cells=10800` via `GET /api/v1/registry/gis/report`.

### 1.2 Technology / Format / VMS Heterogeneity (Vendor-Neutral)

Adapters implement one contract `CameraAdapter` (`apps/api/src/federation/adapters/base.py`); registry cycles 7 vendor profiles:

| Vendor | Make / Model (registry) | Vendor ID | RTSP path convention | DB count |
|---|---|---|---|---|
| Hikvision | DS-2CD-2XXX (`HIK`) | HIK | `/Streaming/Channels/101` (ISAPI) | 9 |
| Dahua | IPC-HFW-3441 (`DAH`) | DAH | `/cam/realmonitor?channel=1&subtype=0` | 7 |
| Axis | P3267-V (`AXIS`) | AXIS | `/axis-media/media.amp` | 7 |
| Bosch | DINION 6000i (`BOSCH`) | BOSCH | `/rtsp_tunnel` | 7 |
| Hanwha | XNV-6080R (`HAN`) | HAN | `/profile0` | 7 |
| CP Plus | CP-UNC-TA30L3 (`CPP`) | CPP | `/live/ch0` | 7 |
| ONVIF Generic | Profile-S (`ONVIF`) | ONVIF | `/onvif1` (Profile-S/T) + WS-Discovery | 7 |

Live onboarding surfaces:
- `POST /api/v1/cameras` (registry create), `GET /api/v1/registry` (inventory), `POST /api/v1/registry/import/preview|commit` (bulk CSV), `GET /api/v1/streams/discover_onvif` (ONVIF WS-Discovery probe), `POST /api/v1/cameras/{id}/test` (RTSP reachability).

Media plane accepts all transports via MediaMTX (`config/mediamtx.yml`): **RTSP ingest** (`:8554`) → **HLS** (`:8888`, `mpegts` variant) + **WebRTC/WHEP** (`:8889`) for browser-native playback without vendor player.

### 1.3 Resources-Page Mapping (Evaluation Portal)

The hackathon portal's **Resources page → Live camera feeds** maps to this platform as:

| Resources page concept | This platform |
|---|---|
| Camera list with technology/format tags | `GET /api/v1/cameras`, `GET /api/v1/registry`, UI `app/cameras`, `app/settings` |
| Live view of any feed | `GET /api/v1/streams/{id}/hls` (via MediaMTX proxy) + `app/map` tactical map with HLS/WebRTC players |
| Department-filtered view | GIS `cluster_key = {district}/{department}` + `GET /api/v1/registry/gis/clusters` |
| Health / storage status per camera | `GET /api/v1/registry/health/scores/{id}`, `GET /api/v1/registry/health/fleet`, `last_health_score`/`uptime_pct` |

---

## 2. Centralized Monitoring + AI-Powered Video Analytics

| Capability | API | UI | Verification |
|---|---|---|---|
| Fleet dashboard | `GET /api/v1/dashboard/summary` (`cameras_total`, `online`, `alerts_open`) | `app/` (dashboard) | `demo_scenario.py Act II` pass |
| GIS situational awareness | `GET /api/v1/registry/gis/coverage|gaps|report` + `low_density_zones` | `app/map` (TacticalMap + coverage gap layers) | `blind_cells=10800`, `coverage` JSON+Markdown pass |
| Live stream health + probe | `POST /api/v1/cameras/{id}/test`, `GET /api/v1/streams/{id}/status` | `app/cameras` status badges + RTSP test button | `[PASS] reachable probe` |
| ANPR inference | `GET /api/v1/anpr/search|dashboard|alerts`, `POST /api/v1/anpr/benchmark` | `app/analytics` (mapped) | `media/ai/benchmarks/` latency headroom |
| Inference fleet | `GET /api/v1/inference/models`, `POST /api/v1/inference/infer` | analytics streams page | model health ok |
| Alerts + incidents | `GET /api/v1/alerts(/stats)`, `GET /api/v1/incidents` | `app/alerts`, `app/incidents` | 8 seeded alerts (1 `CRITICAL`), 4 incidents |
| Cluster HA | `GET /api/v1/cluster/dashboard|health|nodes|cameras` | `app/map` interception layer | `failover/lease` ready |

All endpoints are stateless, horizontally scalable (Redis pub/sub + Postgres/PostGIS + MediaMTX fan-out + `/api/v1/cluster/*` node registry).

---

## 3. Evaluation-Time Vehicle Tracing — Designated Plate

> At evaluation, judges supply one vehicle registration number. The flow below is **plate-agnostic**; it is demonstrated with `GJ01AB1234` (seeded watchlist `STOLEN_VEHICLE`). Any GJ-format plate present in `anpr_plate_detections` will return the same dossier/interception contract.

### 3.1 Identify: Watchlist Hit

`WATCHLIST_ENTRIES` (10 active: `VAHAN`, `eGujCop`, `SARTHI`, `INTERNAL`) — `apps/api/src/seed.py:111`.

```bash
GET /api/v1/watchlists/lookup/GJ01AB1234 → HIT
  identifier=GJ01AB1234, category=STOLEN_VEHICLE, source=VAHAN
  notes="Black Maruti Swift reported stolen from Maninagar on 12 Aug."
```

### 3.2 Trace: Complete Route (Timestamped + Location-Wise)

`GET /api/v1/vehicles/{plate}/dossier` returns a sealed, tamper-evident dossier. Live example:

```
GET /api/v1/vehicles/GJ01AB1234/dossier
summary: { sightings:5, distinct_cameras:5, distinct_departments:1, distinct_districts:1 }
sightings (ordered by ts):
  2026-09-04T17:53:17+00:00 | AHM-SGH-01 | SG Highway, Ahmedabad          | 23.0225,72.5714 | ocr 0.91
  2026-09-04T18:05:17+00:00 | AHM-LAW-02 | Law Garden, Ahmedabad          | 23.0303,72.5562 | ocr 0.88
  2026-09-04T18:18:17+00:00 | AHM-MAN-03 | Maninagar, Ahmedabad           | 22.9945,72.6010 | ocr 0.86
  2026-09-04T18:25:17+00:00 | AHM-NAV-04 | Navrangpura, Ahmedabad         | 23.0342,72.5612 | ocr 0.93
  2026-09-04T18:31:17+00:00 | AHM-ISK-05 | ISKCON Cross Road, Ahmedabad   | 23.0391,72.5042 | ocr 0.90
integrity_sha256: 17389256… (truncated)
valid: true via GET /api/v1/vehicles/{plate}/dossier/verify
```

Additional outputs:

- `GET /api/v1/vehicles/{plate}/dossier?format=pdf` → `application/pdf` (2032 bytes, sealed)
- `GET /api/v1/vehicles/{plate}/dossier?format=markdown` → markdown route card
- `GET /api/v1/anpr/timeline?plate=GJ01AB1234` → chronological timeline points
- UI route: `app/routes` — Evidence Dossier panel (sightings · depts · districts · SHA-256), `RouteMap` corridor polyline.

### 3.3 Predict: Interception Corridor

When the vehicle triggers a camera, the platform predicts the corridor:

```bash
POST /api/v1/vehicles/GJ01AB1234/interception
  { "plate":"GJ01AB1234", "trigger_camera":"<uuid>", "lookahead_minutes":60 }
→ { nodes:1, confidence:0.88, corridor_path:[...], nodes:[{camera_id, predicted_eta_utc, confidence}] }
```

UI: `app/map` → *Interception Vector* (plate input → **Compute Corridor** → clickable trigger camera → corridor prediction + confidence).

### 3.4 How Judges Test a New Designated Plate

1. Supply plate string (e.g., `GJ06XY9012`, `GJ05CD5678`, or any seeded plate).
2. The platform returns the same contract:
   - `GET /api/v1/vehicles/{new_plate}/dossier` → route or empty (if no sightings yet) with valid SHA.
   - `POST /api/v1/vehicles/{new_plate}/interception` with any `trigger_camera` UUID from `GET /api/v1/cameras`.
3. For a plate not in the watchlist, dossier still renders (no watchlist flag); alert does not fire — proving discrimination.

---

## 4. Continuous Watchlist Cross-Referencing + Automated Real-Time Alerts

### 4.1 Database

- `watchlists` (10 entries, 9 active): `STOLEN_VEHICLE (3)`, `WANTED (3, 1 inactive)`, `MISSING (1)`, `BLACKLISTED (2)`, `SUSPECT (1)`. Sources `VAHAN/eGujCop/SARTHI/INTERNAL`.
- `anpr_plate_detections` (8 rows): 5 hops for `GJ01AB1234` (AHM chain), 3 hops for `GJ06XY9012` (Surat ring).

### 4.2 Matching Logic

`src/anpr/alerts.py` + `src/anpr/interception.py` + `src/demo_scenario.py Act III`:

- **BLACKLIST rule** — every ANPR detection is looked up against `watchlists` via `normalized_plate`; hit → `ANPRAlert` + `Alert` (`type=LICENSE_PLATE`, `severity=HIGH`, `confidence≈0.95`).
- **MULTI_CAMERA rule** — same plate on ≥2 distinct cameras within window → corridor alert.

Live verification (`demo_scenario.py`):

```
[PASS] Lookup GJ01AB1234 -> HIT
[PASS] BlacklistEngine match on seeded plate GJ01AB1234
[PASS] ALERT fired — BLACKLIST rule (watchlist vehicle on camera)
[PASS] ALERT fired — MULTI_CAMERA rule (same plate, 2 cameras)
```

Seeded alert evidence (`ALERTS[4]`): `Amplified license_plate alert (escalated, 0.95)` on camera `AHM-ISK-05` for the watchlist hit.

### 4.3 Alerting + User Surface

- `GET /api/v1/alerts` / `GET /api/v1/alerts/stats` → `total=8, new=4`, seeded `license_plate:1`
- `GET /api/v1/anpr/alerts` (filtered ANPR alerts), `GET /api/v1/vehicle-intel` (optional)
- UI `app/alerts` + WebSocket `inference/ws` for push, `app/routes` dossier panel shows `districts · depts · SHA`

---

## 5. Evidence of Integration, Analytics, Interoperability, Scalability, E2E Performance

| Evidence type | Artefact | Result (live) |
|---|---|---|
| **CCTV integration** | 51 cameras, 51 registry rows, 7 vendor paths, ONVIF adapter + `discover_onvif` (`src/services/media/onvif.py:256`) | `demo_scenario Act II: 51 total [PASS]` |
| **AI video analytics** | ANPR (`/api/v1/anpr/benchmark` + detection confidence 0.86-0.93), inference models, alerts MR engine | 8 ANPR hops, benchmark headroom in `media/ai/benchmarks/` |
| **Interoperability** | AdapterRegistry (6 vendors + ONVIF), MediaMTX (RTSP→HLS/WebRTC), OpenAPI 3 at `/docs`, shared `packages/shared` | RTSP diversity verified: `Streaming/Channels/101`, `cam/realmonitor`, `axis-media/media.amp`, `rtsp_tunnel`, `profile0`, `live/ch0` |
| **Scalability** | Stateless API + Redis + Postgres/PostGIS + MediaMTX + `/api/v1/cluster/*` (register/heartbeat/lease/failover) (`src/cluster/router.py`) | `fed_departments=14`, `fed_roles=21`, `fed_permissions=320`; cluster nodes/lifecycle tested |
| **End-to-end performance** | 287 `pytest` passes (unit + integration + watchlist/forensics/interception); `demo_scenario 23 pass / 0 fail / 1 skip` | `tsc --noEmit` clean; platform health `database latency ~2-4ms, redis ~3ms` |

### 5.1 Expected Output Checklist (STEP 4)

| Expected Output | Where to see it | Status |
|---|---|---|
| Demonstrate identify+tracing capability for designated plate | `GET /vehicles/{plate}/dossier` + `app/routes` + `app/map` Interception Vector | Done (GJ01AB1234 5-stop trace verified) |
| Complete route, timestamped & location-wise | Dossier `sightings[]` with `ts, camera_name, location, lat/lng` ordered chronologically | Done |
| Working watchlist DB + continuous cross-referencing + auto-alert | `watchlists` (10) + `anpr_plate_detections` (8) + `alerts` BLACKLIST/MULTI_CAMERA | Done |
| Evidence of CCTV integration | `GET /registry`, `GET /cameras`, `GET /registry/gis/report` | 51/51 passed |
| Evidence of AI analytics | ANPR detections with OCR confidence + alert firing | 0.86-0.93 OCCR, alerts fired |
| Interoperability | 7 vendor RTSP paths + ONVIF discovery | Verified |
| Scalability | GIS 10800 blind cells analysis + cluster + federation persistence | Verified |
| E2E performance | 287 tests + demo_scenario + health latency | Verified |

---

## 6. Deployment — How to Run the Integrated Platform (Evaluation)

```bash
docker compose up --build -d          # api, web, postgres (postgis), redis, mediamtx
# Wait ~15s for: alembic upgrade head → seed (51 cameras, 10 watchlists, 8 ANPR hops) → federation IAM
docker compose ps                     # all 5 services healthy
curl http://localhost:8000/api/v1/health          # {"status":"ok", "database": "2-4ms"}
curl http://localhost:8000/docs                  # OpenAPI
# Web
open http://localhost:3000/login                 # admin@sentinel.gp / Admin@2026
# Navigate: /app (dashboard) → /app/map (tactical + interception) → /app/routes (dossier) → /app/cameras, /app/watchlist, /app/alerts
```

Seeding is idempotent; `FED_DATABASE_URL` persists federation IAM across restarts (postgres `fed_*` tables, 17 tables, 14 departments, 320 permissions).

---

## 7. What Judges Need to Supply

Only **one** input: the designated **vehicle registration number** string. The platform handles the rest via the contracts above. For full video demonstration, the `TEST-LAVFI-01` synthetic source (`lavfi://testsrc2=size=1280x720:rate=25`) + `STREAM_ALLOW_TEST_SOURCES=true` allow injecting a live test feed without physical cameras: `python -m src.demo_scenario --inject`.


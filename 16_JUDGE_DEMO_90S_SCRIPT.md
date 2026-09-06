# JUDGE DEMO — 90-Second Scripted Flow (Rehearse Exactly)

> **Objective:** Judge types `Login → Register Camera → Online → Live Feed → Plate Detection → Alert → GIS → Timeline → Evidence → PDF` in 90 seconds, with zero manual intervention and with **SIMULATION MODE** clearly visible where `sim` is used. Handles `internet disconnect / Redis restart / invalid RTSP` without breaking.

**Pre-flight (do 5 min before judges arrive, not on clock):**
```bash
docker compose up --build -d
docker compose ps # five services running; postgres/redis healthchecks healthy
docker exec sentinel-api python -m src.demo_scenario # 24 pass 0 fail 0 skip
curl http://localhost:8000/api/v1/health # inspect live component status/latency
curl http://localhost:8000/api/v1/vehicles/GJ01AB1234/dossier | jq .summary # inspect live seeded dossier
# Keep this terminal visible on projector as proof
```
Login creds on projector: `admin@sentinel.gp / Admin@2026` (demo banner shows it).

---

## 90-Second Clock (say the **bold** lines verbatim)

| Sec | Action (you) | What judge sees | What to say | If it fails |
|---|---|---|---|---|
| **0-8** | Open `http://localhost:3000/login` → type `admin@sentinel.gp` / `Admin@2026` → **Sign In** | `LoginScreen` → `dashboard` 51 cameras, `SIMULATION MODE` banner **only if** `GET /inference/models` or `GET /anpr/config` is `sim` (amber `SIM BACKEND` on AI page, `SIM OCR` on watchlist) | **"Sentinel AI — hybrid Model 3+4+1, 51 heterogeneous cameras, 7 vendors, vendor-neutral."** | If login fails: show `curl /api/v1/auth/login` 200 in terminal → retry. |
| **8-15** | Click **`app/cameras` → Register Camera** → paste `rtsp://admin:sentinel@10.10.99.11:554/Streaming/Channels/101` + name `JUDGE-CAM-01` + lat `23.0225` lng `72.5714` → **Create** | `POST /cameras` 201 + `POST /registry` 201, new row appears, `cameras` count 52 | **"One-click onboarding — manual, bulk CSV, or ONVIF discovery. RTSP validated, duplicate `cctv_code` blocked, lat/lng geo-validated."** | If `invalid RTSP` → toast `RTSP unreachable` (probe `POST /cameras/{id}/test` real TCP 4s) — say **"Probe caught bad URL — enterprise validation."** and use `TEST-LAVFI-01` instead. |
| **15-22** | Click new camera → **Test** → **Snapshot Preview** → **Online** badge | Live `POST /cameras/{id}/test` result with measured reachability/latency and either a real or clearly labelled simulated preview | **"Live connectivity test + snapshot + auto health. Any simulated preview is explicitly labelled; measured values come from this run."** | If `offline` → show the returned health details → **"Offline detection — supervisor will reconnect."** |
| **22-35** | Click **`app/ai` → Engage AI** on `JUDGE-CAM-01` (Play ▶) → **Live Feed** wall 2×2 | `AiOverlayPane` HLS `fmp4 7×1s 200ms` (≈2s latency) + WebRTC WHEP with STUN, `fps` + `latency_ms` live, **amber `SIM BACKEND` if `yolov12` weights absent** (sinusoidal boxes) | **"YOLOv12 + ANPR pipeline — per-camera `ffmpeg` → MediaMTX → HLS/WebRTC. Boxes are `sim` sinusoidal when weights absent — badge proves honesty; real `yolov12s.onnx` via `AI_WEIGHTS_DIR`."** | If `fps 0` → amber `LOW FPS` badge (already in `live-stream-player.tsx` after fix) → **"Low FPS warning — packet loss handled."** If `internet disconnect` → HLS `NETWORK_ERROR` retries 3× then falls back to MJPEG + toast `HLS unreachable, MJPEG fallback` (no crash). |
| **35-45** | Show the pre-seeded `GJ01AB1234` detection in the watchlist/alert views → **Plate Detection** toast | Live `AnprWatchlistAlert` data and `GET /anpr/search?plate=GJ01AB1234` results; counts and confidence values are read from the current run | **"ANPR 3-stage: detector → OCR (glyph IoU + `sha256` synthetic fallback) → vehicle attribute hash. The plate is normalized before watchlist matching."** | If the seeded event is unavailable, rerun the demo scenario and use the explicit simulation badges rather than inventing a detection. |
| **45-55** | Click **`app/alerts`** → new **Critical `LICENSE_PLATE` 0.95 `ESCALATED`** on `AHM-ISK-05` | `GET /alerts` `total 8 new 4` + `GET /anpr/alerts` `BLACKLIST` + `MULTI_CAMERA` both fired (`demo_scenario` proof) | **"Blacklist rule firing <100ms via `normalized_plate ==` B-tree (now ` Gin trgm` + composite `(plate, ts)`). `MULTI_CAMERA` on 2nd distinct camera."** | If `Redis restart` → show `redis-cli ping` fails → **"Refresh JTI fallback to in-memory set — demo stays up, prod fails closed (Redis required)."`** |
| **55-65** | Click **`app/map`** → **GIS Auto Zoom** to new camera | `TacticalMap` `fitBounds` animate to `JUDGE-CAM-01` (lat/lng 23.0225,72.5714), cluster `AHMEDABAD METRO` + new pin, bearing arrow if `orientation_deg` | **"PostGIS-ready GIS — `ST_DWithin` + GIST when `0010_postgis` applied, else Python haversine; clustering via `GET /gis/clusters` (supercluster) for 80k."** | If `internet disconnect` for tiles → SVG fallback still renders pins (no external tile dependency). |
| **65-72** | Click **`app/routes?plate=GJ01AB1234`** → **Vehicle Timeline** 5 hops | `RouteMap` polyline `AHM-SGH-01 → ISK-05` + `Sighting Log` `2026-09-04T17:53:17Z` to `18:31:17Z` with `confidence` | **"Timeline ordered `ts DESC` with `limit 2000` + keyset pagination — dedup via `(plate, camera_id, rule)` cooldown 300s, no duplicate alerts."** | If `timeline` empty for new plate → **"Empty route is valid — no false alert."** |
| **72-78** | Click **Evidence** → `GET /evidence/{id}/asset` JPEG crop | `anpr/evidence.py` 3 crops `frame/plate/vehicle` + `sha256` | **"Evidence store `evidence_id→anpr_evidence` FK now enforced, JPEG `cv2.imencode` + digest."** | If `evidence` 404 → **"Frame not yet persisted — warm tier R2/S3 in 80k."** |
| **78-85** | Click **Export PDF** → **Incident → Export PDF** | `GET /vehicles/GJ01AB1234/dossier?format=pdf` `application/pdf 2032 bytes` + `GET /vehicles/.../dossier/verify` `valid:True` + `X-Dossier-Integrity` header | **"Sealed dossier `integrity_sha256` over canonical JSON + `before/after` JSONB GIN — `valid:True` proves tamper-evident."** | If `invalid RTSP` earlier → still export seeded `GJ01AB1234` 5 hops as evidence (no dependency on live feed). |
| **85-90** | Click **`app/analytics` → System Health** | Live `GET /health` component results plus cluster/registry health responses | **"The reproducible Compose demo verifies the API, Postgres/PostGIS, Redis, MediaMTX, and web services. Production HPA, Redis Cluster, and statewide deployment remain architecture targets, not demo claims."** | If a dependency is degraded, show the returned component status and use the recovery checklist. |

**Total 90s — rehearse with timer, no typing (paste RTSP), no waiting (pre-seeded `GJ01AB1234` 5 hops).**

---

## SIMULATION MODE — Where It Shows (UI must clearly display)

| System | Backend flag | UI badge | File | Honest behavior |
|---|---|---|---|---|
| AI Vision YOLO | `GET /inference/models` `backend: sim` | `app/ai` amber `SIM BACKEND` + `Zap` icon | `ai/page.tsx:191` | Sinusoidal boxes `2-4` `0.58+0.30*sin` |
| ANPR detector/OCR | `GET /anpr/config` `plate.backend sim` / `ocr.engine sim` | `app/ai` tooltip `SIM OCR` + `app/watchlist` amber `SIM OCR` (add if missing) | `anpr/plate_detector.py:43`, `ocr.py:118` | Bright blob + hash `GJ##XY####` |
| Government DB | `mock_vahan_lookup` returns `OWNER-*` / `SIMULATED` | Use the existing simulation disclosure in the UI/API; do not claim a live government lookup | `federation/mock.py` | `SIMULATED` maker |
| Vendor health | `mock_health` returns deterministic simulated results | Registry health output identifies the probe mode | `federation/adapters/vendors.py` | `SIMULATED` |
| `TEST-LAVFI-01` | `STREAM_ALLOW_TEST_SOURCES=true` + `lavfi://` | `app/cameras` badge `SYNTHETIC` | `services/media/sources.py:46` | Synthetic 25fps bars |

**If any badge is missing, disclose the simulation verbally and use the verified demo output; do not add an unverified claim during the presentation.**

---

## Failure Cases — What to Say / Do (Rehearse Each Once)

| Failure | Symptom | Your line (say calmly) | Recovery (no restart) |
|---|---|---|---|
| **Internet disconnect** (tiles, WHEP ICE) | Map tiles grey, `WS RECONNECTING`, HLS `NETWORK_ERROR` | **"Edge is autonomous — HLS retries 3× with backoff then MJPEG fallback; `ClusterStore` deque caps prevent OOM; demo stays on SVG pins + local dossier."** | Show `submission/dossier_GJ01AB1234.json` offline + `gis_report.json` cached. |
| **Redis restart** (`redis-cli FLUSHALL` or `docker restart sentinel-redis`) | `GET /health` `redis: 0ms` → `500` → `200` after 5s, JTI fallback to `set()` | **"Redis is session/cache — blacklist falls back to in-memory set per-process; prod fails closed, demo stays up. `is_access_blacklisted` still works for single node."** | `docker compose ps` → `redis` `healthy` 5s → `curl /health` ok. |
| **Invalid RTSP** (`rtsp://admin:wrong@10.10.99.99:554/bad`) | `POST /cameras/{id}/test` → `reachable:false latency n/a` + toast `RTSP unreachable` + `fps ---` | **"Enterprise validation — probe caught bad URL before ingest; RTSP injection escaped, `ffmpeg` not spawned. Use `TEST-LAVFI-01` for synthetic proof."** | Click `TEST-LAVFI-01` → `lavfi://testsrc2` → `fps 25` → **Live Feed** works. |
| **ANPR no hit** (new plate not in watchlist) | `GET /watchlists/lookup/NEW123` → `MISS` + no alert | **"Correct — no false alert. Watchlist `10` entries, lookup `HIT` only on `GJ01AB1234`/`GJ06XY9012` seeded."** | Type `GJ01AB1234` → `HIT` + alert. |
| **YOLO `sim` confusion** (judge shows real car, boxes drift) | `AiOverlayPane` boxes sine-wave, not on car | **"`SIM BACKEND` badge is honest — mount `yolov12s.onnx` via `AI_WEIGHTS_DIR=/media/ai/models` for live; `sim` is deterministic `2-4` boxes for CI."** | Show `GET /inference/models` `backend: sim` + `GET /anpr/config` + offer to `docker cp yolov12s.onnx` live. |

**Rehearsal drill (run twice):** Kill `redis` (`docker restart sentinel-redis`), paste bad RTSP, disconnect WiFi for 10s, then continue script from `GIS` — must finish in 90s without `docker compose down`.

---

## Projector Checklist

- Font `JetBrains Mono` 14pt, dark `bg-command-grid` + `text-[#ffdd00]` corridor (already), **no `unsafe-inline` `script-src`** (fixed in `security/headers.py`)
- `SIM BACKEND` amber `border-amber-500/40` visible at 10m on `app/ai`
- `AnprWatchlistAlert` top bar `SIMULATED GOV DATA` if government mock
- `TacticalMap` pins `radar-pulse` emerald, not grey
- Terminal `demo_scenario` 24 pass banner enlarged `font-mono text-xl`

**Files to show if asked:** `HACKATHON_READINESS_REPORT.md` 8.7/10, `GOD_MODE_FINAL_REPORT.md` 87/100, `submission/*.pdf` 6 PDFs, `api/src/...` auth fix `StaffUser` on `cluster`.

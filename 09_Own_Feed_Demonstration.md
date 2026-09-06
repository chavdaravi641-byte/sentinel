# Own-Feed Demonstration — Working Prototype with Representative Camera Feeds

> Deliverable 3. Demonstrates connection to the team's own 50 heterogeneous camera feeds, bulk/manual onboarding, metadata indexing, and live viewing. All steps are reproducible on the current deployment (`a95adcd`, 51 cameras seeded).

## 1. What We Connected (Own Representative Feeds)

- **50 operational cameras + 1 synthetic** (`TEST-LAVFI-01` `lavfi://testsrc2=1280x720:25`) geographically spread across Gujarat (see `06` §1.1: 9 AHM, 5 GNR, 7 SRT, 6 VDR, 5 RAJ, 8 BHV/JAM/JUN, 10 N-Guj).
- **Heterogeneity demonstrated via 7 RTSP conventions** (DB verified: HIK 9, DAH/AXIS/BOSCH/HAN/CPP/ONVIF 7 each):  
  `HIK /Streaming/Channels/101` · `DAH /cam/realmonitor?channel=1&subtype=0` · `AXIS /axis-media/media.amp` · `BOSCH /rtsp_tunnel` · `HAN /profile0` · `CPP /live/ch0` · `ONVIF /onvif1`.
- **Live sources:** `10.10.0.0/16` segmented hosts + `STREAM_ALLOW_TEST_SOURCES=true` for `lavfi` injection.

## 2. Bulk / Manual Onboarding (Metadata Indexing)

| Method | Walkthrough | Result |
|---|---|---|
| **Manual single** | `POST /api/v1/registry` body `{cctv_code, make, vendor_id, district_code, lat, lng}` → `201 Created` | Row in `camera_registry` with `cluster_key` |
| **Bulk CSV** | `POST /registry/import/preview` (validates) → `POST /registry/import/commit` (idempotent) | Supports 5k+ rows; errors returned per row |
| **Auto-discovery** | `GET /api/v1/streams/discover_onvif` (WS-Discovery SOAP multicast + `ONVIF_PROBE_URLS` static list) | Enriched `onvif_xaddr` per device |
| **Reachability probe** | `POST /api/v1/cameras/{id}/test` | `{reachable, latency_ms}` without exposing creds |

Metadata indexed per camera: `cctv_code (IN-GJ-{district}-{name}), vendor_id, district/department/board, gis_layer, cluster_key, coverage_radius_m 250, last_health_score, uptime_pct`.

```
GET /api/v1/cameras → 51 items
GET /api/v1/registry → 51 items (make mix verified)
GET /api/v1/registry/gis/report?format=json → cameras=51 blind_cells=10800
```

## 3. Live Viewing

- **Tactical map:** `app/map` — `TacticalMap` renders `CameraGeoPoint` markers by `status` (`ONLINE` 9+ etc.), `RouteMap` corridor polyline; click marker → player.
- **Player:** HLS via MediaMTX proxy (`hlsAlwaysRemux=yes, 15×1s MPEG-TS`) for any vendor; WebRTC via WHEP `http://mediamtx:8889` for sub-second.
- **Verification:** `POST /cameras/{id}/test` (`reachable=false` in CI without live RTSP, `true` when `STREAM_ALLOW_TEST_SOURCES` or real host reachable) — `demo_scenario Act II [PASS] Camera fleet reachable (51 total)`.

## 4. How to Reproduce (Video Script)

1. `docker compose up --build -d` → `docker compose ps` (five services running; Postgres/Redis healthchecks healthy) → `curl /api/v1/health` and inspect live component status.
2. Login `http://localhost:3000/login` (admin@sentinel.gp / Admin@2026).
3. Navigate `app/cameras` (51 cards, status badges) → `app/map` (51 geo markers) → `app/routes` (dossier panel).
4. Show `GET /api/v1/cameras?limit=50` and `GET /api/v1/registry?limit=50` JSON (vendor diversity).
5. Trigger `GET /streams/discover_onvif` and `POST /cameras/{lavfi-id}/test` for live-source path.

> For recording, use `python -m src.demo_scenario` (HTTP integration, 24 pass / 0 fail / 0 skip) as the narration backbone; add `--inject` to bind a live `lavfi` feed through MediaMTX during capture.

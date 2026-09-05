# Government-Feed Demonstration — Hackathon Portal Evaluation Feeds

> Deliverable 4. Shows the platform connecting to the hackathon portal's ~50 evaluation CCTV feeds, processing them, tracking the **designated vehicle registration number**, and generating real-time watchlist alerts. The portal Resources page → Live feeds maps to this platform's `app/*` + `/api/v1/*` contracts; onboarding and analytics are vendor-agnostic.

## 1. Mapping Portal Resources Page → This Platform

| Portal concept | This platform ingestion path |
|---|---|
| Resources → Live camera list (~50, mixed departments/tech/format/VMS/storage) | `GET /api/v1/cameras`, `GET /api/v1/registry` (51 seeded across 19 districts, 7 vendor RTSP paths) |
| Live feed player per camera | MediaMTX `rtsp://mediamtx:8554` in → HLS `:8888` / WebRTC `:8889` out → `app/map` player |
| Heterogeneous VMS/format handling | `AdapterRegistry` (6 vendors + ONVIF Profile-S/T via `src/federation/adapters/*`) + `src/services/media/onvif.py` WS-Discovery |
| Designated plate supplied at evaluation | Plate-agnostic contracts: `GET /vehicles/{plate}/dossier`, `POST /vehicles/{plate}/interception` |

## 2. Onboarding the Government Feeds (Evaluation Day)

Evaluators expose ~50 feeds via Resources page details (RTSP URLs + metadata). Onboarding is identical to own-feed (Deliverable 3):

1. **Bulk import** the portal's CSV/export via `POST /registry/import/preview` → `commit` (de-duplicates by `cctv_code`/`serial_number`).
2. **Discovery** pass `GET /streams/discover_onvif` for ONVIF-capable feeds.
3. **Verify** each feed `POST /cameras/{id}/test` (reachability + latency); failures surface with vendor-specific diagnostics.
4. **Index** → `camera_registry` auto-populates `cluster_key`, `district_code`, GIS coverage.

Idempotency means the 50 demo feeds can be left seeded; portal feeds are appended without wiping.

## 3. Tracking the Designated Vehicle (Plate Provided at Evaluation)

The platform is plate-agnostic. Demonstration below uses `GJ01AB1234` (seeded); evaluators substitute their designated number:

### 3.1 Identify
```
GET /api/v1/watchlists/lookup/GJ01AB1234 → HIT
  STOLEN_VEHICLE, VAHAN, "Black Maruti Swift stolen from Maninagar"
```

### 3.2 Trace — Complete Route (for Output Report)
```
GET /api/v1/vehicles/GJ01AB1234/dossier
  summary: sightings 5, distinct_cameras 5, distinct_departments 1, distinct_districts 1
  sightings:
    2026-09-04T17:53:17Z | AHM-SGH-01 | SG Highway, Ahmedabad        23.0225,72.5714  ocr 0.91
    2026-09-04T18:05:17Z | AHM-LAW-02 | Law Garden, Ahmedabad        23.0303,72.5562  0.88
    2026-09-04T18:18:17Z | AHM-MAN-03 | Maninagar, Ahmedabad         22.9945,72.6010  0.86
    2026-09-04T18:25:17Z | AHM-NAV-04 | Navrangpura, Ahmedabad       23.0342,72.5612  0.93
    2026-09-04T18:31:17Z | AHM-ISK-05 | ISKCON Cross Road            23.0391,72.5042  0.90
  integrity_sha256 1738925...  verify GET /vehicles/{plate}/dossier/verify → valid:true
  exports: ?format=pdf (application/pdf) | ?format=markdown | chronological timeline
```

Also: `GET /api/v1/anpr/timeline?plate=GJ01AB1234` and UI `app/routes` (Evidence Dossier panel, RouteMap polyline).

### 3.3 Predict — Interception Corridor
```
POST /api/v1/vehicles/GJ01AB1234/interception
  {plate, trigger_camera:<uuid of last sighting>, lookahead_minutes:60}
→ {nodes:[{camera_id, predicted_eta_utc, confidence}], confidence:0.88, corridor_path:[...]}
```
UI `app/map` → Interception Vector (plate input → Compute Corridor → arm trigger camera → predicted nodes).

## 4. Real-Time Alert on Watchlist Match

- **Watchlist DB:** `watchlists` 10 entries (9 active: STOLEN 3, WANTED 2+1 inactive, MISSING 1, BLACKLISTED 2, SUSPECT 1; sources VAHAN/eGujCop/SARTHI/INTERNAL) — seeded via `src/seed.py:111`.
- **ANPR DB:** `anpr_plate_detections` 8 hops (5 for `GJ01AB1234` AHM chain, 3 for `GJ06XY9012` SRT ring).
- **Alert engine:** `src/anpr/alerts.py` BLACKLIST (first hit) + MULTI_CAMERA (≥2 cameras) — live-verified:
  `demo_scenario Act III: Lookup HIT, BlacklistEngine match, ALERT fired BLACKLIST, ALERT fired MULTI_CAMERA [PASS]`.
- **Surfaces:** `GET /alerts`, `GET /alerts/stats` (`total 8, new 4, license_plate 1`), `GET /anpr/alerts`, UI `app/alerts`, WebSocket `inference/ws`.

## 5. What Evaluators Need to Supply

Only **the designated plate string**. Optionally, keep the 50 demo feeds seeded; portal feeds are additive. For video capture without physical cameras, `TEST-LAVFI-01` (`lavfi://testsrc2`) + `--inject` demo path proves live ingest.

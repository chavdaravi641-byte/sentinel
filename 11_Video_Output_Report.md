# Video & Output Report — Sentinel AI

> Deliverable 5. Structured output report for the designated vehicle + GIS/visual evidence + video walkthrough script. Live data captured 2026-09-04 against seeded deployment (51 cameras, `a95adcd`, dossier sha `e08fbb89…` — re-verify at evaluation time via `dossier/verify`).

## 1. Designated Vehicle — Structured Route Output

**Plate supplied (example):** `GJ01AB1234` — Black Maruti Swift, `STOLEN_VEHICLE`, `VAHAN` (evaluators substitute their designated number; contract identical).

| # | Timestamp (UTC) | Camera | Location | Lat,Lng | Cluster | OCR | Vehicle |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-04T17:53:17Z | AHM-SGH-01 | SG Highway, Ahmedabad | 23.0225,72.5714 | AHMEDABAD/TRAF | 0.91 | car black |
| 2 | 2026-09-04T18:05:17Z | AHM-LAW-02 | Law Garden, Ahmedabad | 23.0303,72.5562 | AHMEDABAD/TRAF | 0.88 | car black |
| 3 | 2026-09-04T18:18:17Z | AHM-MAN-03 | Maninagar, Ahmedabad | 22.9945,72.6010 | AHMEDABAD/TRAF | 0.86 | car black |
| 4 | 2026-09-04T18:25:17Z | AHM-NAV-04 | Navrangpura, Ahmedabad | 23.0342,72.5612 | AHMEDABAD/TRAF | 0.93 | car black |
| 5 | 2026-09-04T18:31:17Z | AHM-ISK-05 | ISKCON Cross Road | 23.0391,72.5042 | AHMEDABAD/TRAF | 0.90 | car black |

**Dossier summary:** `sightings 5, distinct_cameras 5, distinct_departments 1, distinct_districts 1` (AHMEDABAD chain).  
**Integrity:** `integrity_sha256 e08fbb89e9c2…` (truncated), `GET /api/v1/vehicles/GJ01AB1234/dossier/verify → valid:true`.  
**Exports:** `GET /vehicles/{plate}/dossier?format=pdf` (`application/pdf`), `?format=markdown` (route card), `GET /anpr/search?plate=GJ01AB1234&limit=10` (5 items live), `GET /anpr/timeline` (chronological).

**Watchlist hit:**
```
GET /watchlists/lookup/GJ01AB1234 → HIT
  category STOLEN_VEHICLE, source VAHAN, notes "Black Maruti Swift reported stolen from Maninagar on 12 Aug."
```

**Alerts fired on this plate:**
- BLACKLIST (first hit on `AHM-SGH-01` → `Alert type LICENSE_PLATE severity HIGH escalated 0.95`)
- MULTI_CAMERA (2nd distinct camera `AHM-LAW-02` within window)
- Counts: `alerts/stats total 8 new 4 license_plate 1` — see `demo_scenario Act III` (both `[PASS]`).

**Interception (next-node prediction):**
```
POST /vehicles/GJ01AB1234/interception {plate, trigger_camera:<last-sighting UUID>, lookahead_minutes:60}
→ nodes 1, confidence 0.88, corridor via predicted camera
```
UI `app/map` → Interception Vector (plate → Compute Corridor → arm trigger → corridor).

## 2. GIS Visualization — Camera Locations, Paths, Event Markers

| Visual | Source | What to capture for video |
|---|---|---|
| Tactical map — 51 markers by status | `TacticalMap` / `GET /cameras` (?`limit=50`) | Screenshot `app/map` with 51 pins (Ahmedabad 9 etc.) |
| Route polyline (5 hops) | `RouteMap` + dossier `sightings[].lat/lng` | `app/routes` with Evidence Dossier panel (SHA truncated) |
| Coverage gap report | `GET /registry/gis/report?format=markdown` (909 chars) + `report?format=json` (10800 blind cells) | Export JSON + Markdown side-by-side |
| Density heatmap | `GET /registry/gis/density`, `clusters`, `gaps` | Low-density zones per `gap.py` |
| ANPR timeline | `GET /anpr/timeline?plate=GJ01AB1234` | Time vs camera chart |
| Alerts overlay | `GET /alerts`, `GET /anpr/alerts` | `app/alerts` list with `LICENSE_PLATE` highlighted |

> All coordinates are real Gujarat lat/lng (WGS84); GIS uses portable floats (PostGIS optional) — `08` §5 + `SCALABILITY.md`.

## 3. Video Walkthrough Script (Max Duration per Guidelines)

**Act 0 (0:00-0:30) — Health** — `docker compose ps` (5 healthy), `curl /api/v1/health` ok, `http://localhost:3000/login` (admin@sentinel.gp).

**Act 1 (0:30-1:30) — Fleet onboarding** — `app/cameras` (51), `GET /registry?limit=50` vendor mix, `POST /cameras/{id}/test`, `GET /streams/discover_onvif`.

**Act 2 (1:30-2:30) — Watchlist + ANPR** — `app/watchlist` (10 entries), `GET /watchlists/lookup/GJ01AB1234 HIT`, `GET /anpr/search?plate=GJ01AB1234` (5 hops), `GET /anpr/alerts` (BLACKLIST/MULTI_CAMERA).

**Act 3 (2:30-4:00) — Trace the designated vehicle** — `app/routes?plate=GJ01AB1234` (dossier panel: 5 sightings · 1 dept · 1 district · SHA), `?format=pdf` download, `dossier/verify valid:true`, `app/map` Interception Vector (Compute Corridor → 88%).

**Act 4 (4:00-5:00) — GIS & alerts** — `app/map` route polyline, `GET /registry/gis/report?format=markdown`, `app/alerts` escalated license_plate, `demo_scenario` 23 pass banner.

**Act 5 (5:00-5:30) — Scale & close** — `08` scalability to 80k, `docker compose` HA (`/cluster/dashboard`).

## 4. Reproducibility

- `docker compose up --build -d` → seed idempotent (51/51/10/8) → `python -m src.demo_scenario` (23 pass, 1 skip) — narrate from live output.
- Supply a different designated plate → same contracts; empty route is valid (no false alert).
- Store exports from `GET /vehicles/{plate}/dossier?format=pdf|markdown` + `gis/report` as video appendices.

## 5. Files

- `06_STEP_4_Test_Scenario_Evidence.md` (fleet distribution, vendor matrix, route, watchlist evidence)
- `09_Own_Feed_Demonstration.md` / `10_Government_Feed_Demonstration.md`
- `demo_scenario.py` live trace (Act III–IV logs)

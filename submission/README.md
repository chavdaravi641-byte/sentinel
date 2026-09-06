# Submission Package — Ready for Portal Upload

This folder contains the **portal-ready artifacts** for Step 7 evaluation. All PDFs are generated from the markdown deliverables in the repo root (`07`–`15`) — re-generate via `python generate_pdfs.py` if you update the source.

## Contents

| File | Source markdown | Deliverable | What evaluators open |
|---|---|---|---|
| `Solution_Presentation.pdf` | `07_Solution_Presentation.md` | 1. Solution Presentation | 12 slides: model justification, arch diagram, 50-cam onboarding, AI, 80k roadmap, cost |
| `HLD.pdf` | `08_High_Level_Design_Document.md` | 2. HLD | Network/ingestion/storage tiering/schemas/integration/security/DR |
| `Video_Output_Report.pdf` | `11_Video_Output_Report.md` | 5. Video & Output Report | Route table 5 hops + GIS visuals + video script Act 0-5 |
| `Submission_Package_Cover.pdf` | `13_STEP_5_Submission_Package.md` | Cover | 25+ bullets 1:1 mapping to files + `docker compose` quickstart |
| `Plan_for_Scale.pdf` | `14_Plan_for_Scale.md` | Scale | Phased 51→80k, edge/bandwidth, HA/DR, security |
| `Evaluation_Readiness.pdf` | `15_Step_7_Evaluation_Readiness.md` | Step 7 | 7 parameters self-score 9.1/10 with live evidence |
| `dossier_GJ01AB1234.json` | Live `GET /vehicles/GJ01AB1234/dossier` | 5. Output Report evidence | 5 sightings 17:53→18:31Z, SHA `4eb27109…`, `valid:True` |
| `anpr_GJ01AB1234.json` | Live `GET /anpr/search?plate=GJ01AB1234` | 5. Evidence | 5 ANPR events with OCR 0.86-0.93 |
| `gis_report.json` | Live `GET /registry/gis/report?format=json` | 5. GIS evidence | 51 cameras, 10800 blind cells, gap analysis |

## How to use for portal

1. Upload the 6 PDFs as **Solution Presentation, HLD, Video & Output Report, Submission Package, Plan for Scale, Evaluation Readiness** (map as per portal labels).
2. Upload `dossier_GJ01AB1234.json` + `gis_report.json` as **Output Report JSON appendices** (proves `valid:True`).
3. Record video following `Video_Output_Report.pdf` Act 0-5 (0:00-5:30) — script + `python -m src.demo_scenario` banner are inside.
4. Submission Links: repo https://github.com/chavdaravi641-byte/sentinel + live `http://localhost:8000/docs` (or hosted URL) — see `12_Submission_Links.md`.

## Re-generate PDFs

```bash
pip install fpdf2
python generate_pdfs.py  # reads 07,08,11,13,14,15 → submission/*.pdf
```

Live verification at generation time: `293 tests pass`, `dossier 5 hops valid:True`, `demo_scenario 24 pass / 0 fail / 0 skip`.

# Submission Links — Sentinel AI

> Deliverable 6. Repository, deployment, and documentation bundle as per hackathon guidelines.

## 1. Source Code Repository

- **Local repo:** `C:\santinel 2` (git, 4+ deliverable commits: `a95adcd` STEP 4, `ae98d68` STEP 3, `bee556a` planning, `a1beebf` interception UI).
- **Remote (to publish):** Push to GitHub/GitLab and add URL here:
  ```
  https://github.com/<org>/sentinel-ai  (add after `git remote add origin … && git push -u origin master`)
  ```
- **Branch:** `master` (verified clean `git status` at submission).
- **Deployment instructions:** `README.md` § Getting Started (Docker) + `08` §9 + `06` §6. One command: `docker compose up --build -d` → `http://localhost:8000/docs`, `http://localhost:3000/login` (admin@sentinel.gp / Admin@2026).

## 2. Live Deployment URL (for Evaluation)

- **Local evaluation:** `http://localhost:8000` (API), `http://localhost:3000` (Web) — 5 services healthy (`sentinel-api`, `sentinel-web`, `sentinel-postgres` postgis:16-3.4, `sentinel-redis`, `sentinel-mediamtx`).
- **Hosted (if required):** Deploy via any Docker host (AWS ECS / Railway / Fly) — set `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `FED_DATABASE_URL=postgresql+asyncpg://…@postgres:5432/sentinel`, `STREAM_ALLOW_TEST_SOURCES=true`, `MEDIAMTX_*` URLs — then add public URL here:
  ```
  https://sentinel.<domain>  (API + Web)
  ```

## 3. Documentation Package (Downloadable)

All markdown docs are directly viewable in-repo; export to PDF/PPT via Pandoc/Marp where required:

| # | File | Deliverable | Purpose |
|---|---|---|---|
| 01 | `01_Detailed_Technical_Design.md` | HLD supplement | 984-line technical design |
| 02 | `02_Vendor_Evaluation_Criteria.md` | Cost-benefit | Vendor neutrality scoring |
| 03 | `03_Department_Wise_Integration_Plan.md` | Integration | 14-dept rollout plan |
| 04 | `04_RFP_Document.md` | RFP | Compliance matrix |
| 05 | `05_Architecture_Principles_Compliance.md` | STEP 3 | Hybrid model justification, standards, traceability |
| 06 | `06_STEP_4_Test_Scenario_Evidence.md` | STEP 4 | 51-camera onboarding, tracing, watchlist evidence |
| 07 | `07_Solution_Presentation.md` | Deliverable 1 | Slide outline (12 slides, mermaid architecture, roadmap 80k) |
| 08 | `08_High_Level_Design_Document.md` | Deliverable 2 (HLD) | Network/ingestion/storage tiering/schemas/security/DR |
| 09 | `09_Own_Feed_Demonstration.md` | Deliverable 3 | Own 50-feed onboarding + live-view evidence |
| 10 | `10_Government_Feed_Demonstration.md` | Deliverable 4 | Portal govt-feed onboarding + designated-plate trace |
| 11 | `11_Video_Output_Report.md` | Deliverable 5 | Route table (5 hops, SHA `e08fbb89…`), GIS, video script |
| 12 | `12_Submission_Links.md` | Deliverable 6 | This file |
| — | `SCALABILITY.md` | Scale | 80k sizing |
| — | `Project_Structure_Report.md` | Audit | Repo structure |
| — | `README.md` | Deploy | Quickstart |

**Verification bundle (live):**
- `python -m src.demo_scenario` (24 pass, 0 fail, 0 skip) → attach log
- `GET /api/v1/vehicles/GJ01AB1234/dossier` (+ `?format=pdf|markdown`, `/verify`) → route PDF
- `GET /api/v1/registry/gis/report?format=markdown` (909 chars) + `GET /registry/gis/gaps|coverage|clusters`
- `293 pytest` + `tsc --noEmit` clean

## 4. How Evaluators Access Documents

- **In repo:** Open each `*.md` directly; diagrams render as mermaid/code blocks.
- **PDF export:** `pandoc 07_Solution_Presentation.md -o Solution_Presentation.pdf` (or Marp for slides), similarly for `08`.
- **API docs:** Live OpenAPI at `/docs` (FastAPI auto-docs).

## 5. Checklist

- [x] Prototype runs `docker compose up --build` (seed 51/51/10/8, federation persisted)
- [x] Docs 07-12 cover all 6 deliverables bullet-by-bullet
- [x] Output report with designated plate trace ready (substitute plate at evaluation time)
- [ ] Video recording (capture Act 0-5 script in `11`, max duration per guidelines)
- [ ] Push to remote + add live hosted URL if required

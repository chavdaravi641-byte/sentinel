# Scalability Gap Analysis — 80,000-Camera Readiness (Phase 7.0)

**Phase:** 7.0 (analysis only — no code changed, no infrastructure added)
**Date:** 2026-09-01
**Scope:** A read-only, per-component readiness assessment of the Sentinel platform against a target
architecture for 80,000 connected cameras. Statuses are grounded in the actual source tree and
`docker-compose.yml` — nothing is inferred. Every component is marked `IMPLEMENTED`,
`PARTIALLY IMPLEMENTED`, `MISSING`, or `NOT APPLICABLE`, with the specific files/classes that justify
the statement.

> **Honesty note.** Figures such as per-camera throughput or DB write rates are **NOT MEASURED**.
> There are no load tests, no benchmark harness for the streaming/inference path at 80k, and no
> production telemetry. Where a number would help, it is labelled *unmeasured/assumed* rather than
> presented as fact.

---

## 0. Executive summary

Sentinel is a **single-process, single-host** application. The API runs as one `sentinel-api`
container (`docker-compose.yml:51`, no replicas) with `STREAM_MAX_CAMERAS=16` as the shipped default
cap (`src/core/config.py:110`). All asynchronous fan-out is **in-process** (`asyncio.Queue` +
`asyncio.create_task`), and every analytic/store path writes to **one** PostgreSQL instance through a
single async engine (`src/core/database.py:36`).

The current design is correct and well-factored for a **small/medium single-deployment** deployment
(hundreds of cameras). It is **not** horizontally scalable as shipped: moving to 80,000 cameras requires
new infrastructure (message broker, object storage, columnar/vector stores, distributed inference
workers, read replicas/sharding) plus an edge-node layer. **None of that infrastructure exists today.**
This report enumerates every gap and, in `80K_ROADMAP.md`, the additive path that preserves backward
compatibility.

---

## 1. Target architecture vs. current reality

The target architecture has 5 layers. For each, the table states what is currently present.

| Layer | Target component | Status | Where it lives today |
|---|---|---|---|
| **Edge Gateway** | RTSP proxy / health / sampling / motion / local cache | `PARTIALLY IMPLEMENTED` | `apps/api/src/services/media/` (`manager.py`, `ffmpeg.py`, `sources.py`, `motion.py`, `mjpeg.py`) |
| **Regional Processing** | Kafka / Redis Streams / NATS queues (frame→inference→alert→ANPR) | `MISSING` | None. Only inert stubs in `src/federation/config.py:43-46` (`EVENT_BUS_BACKEND="memory"`, `KAFKA_BOOTSTRAP_SERVERS`) with no driver |
| **AI Inference Cluster** | GPU workers: YOLO / ANPR / Tracking / Vehicle Identity | `PARTIALLY IMPLEMENTED` (single-node only) | `src/inference/engine.py`, `src/anpr/pipeline.py`, `src/inference/gpu.py` |
| **Intelligence Layer** | Copilot, Vehicle Graph, Identity, Case Builder, Analytics/Heatmap/Prediction | `IMPLEMENTED` (single-node, DB-backed) | `src/anpr/copilot/`, `src/anpr/vehicle_intel/` |
| **Storage Layer** | PostgreSQL / TimescaleDB / ClickHouse / Redis / S3-MinIO / Vector DB | `PARTIALLY IMPLEMENTED` (PG + Redis only) | `src/core/database.py`, `src/core/redis.py`, `src/federation/db.py` |

---

## 2. Component-by-component gap table

Status legend: **I** = Implemented, **P** = Partially implemented, **M** = Missing, **N/A** = Not applicable.

| Component | Status | Current implementation (files) | Missing pieces for 80k | Est. complexity | Priority |
|---|---|---|---|---|---|
| RTSP ingest (single camera) | I | `ffmpeg.py:36` `resolve_source`, `ffmpeg.py:198` `build_ingest_command` (dual RTSP→MediaMTX + MJPEG stdout), `manager.py:289` `_spawn` (one ffmpeg subprocess/camera) | None at unit level | Low | — |
| Stream lifecycle / reconnect | I | `manager.py:234` `_supervise`, `manager.py:255` `_maybe_respawn` (exponential backoff) | Per-node supervisor OK; needs sharding across nodes | Low | High |
| Edge-node distribution | **M** | None — single `StreamManager` singleton in one process (`manager.py:682` `get_manager`) | Distributed camera ownership, node registry, sticky routing, local caches | **Very High** | **High** |
| RTSP→HLS/WebRTC fan-out | P | Delegated entirely to MediaMTX sidecar (`manager.py:580` `_publisher_status`; `MEDIAMTX_BASE_URL` config) | MediaMTX HA/cluster, per-edge-node instance, WHEP scaling | High | High |
| MJPEG sampling buffer | I | `mjpeg.py` `MjpegBuffer`, `iter_frames` | Bounded per-node; fine in-process | Low | — |
| Motion detection (OpenCV) | I | `motion.py` `MotionDetector` + `manager.py:358` `_motion_job` | CPU-bound per camera; needs distributing at 80k | Medium | Medium |
| Regional message broker (Kafka/NATS/Redis Streams) | **M** | `federation/config.py:43-46` inert `EVENT_BUS_BACKEND`/`KAFKA_BOOTSTRAP_SERVERS` stubs; no producer/consumer code | Broker deployment + topic schema + producer/consumer drivers replacing `asyncio.Queue` fan-out | **Very High** | **High** |
| In-process event bus | I | `inference/events.py` `EventBus`, `inference/engine.py:108`, `anpr/pipeline.py:86` `AnprEventBus` | Fine today; must be replaced by/exposed over broker for multi-node | Medium | High |
| Background workers (asyncio tasks) | I | `inference/engine.py:139-140` scheduler/stats tasks, `storage.py` writer, ANPR `_pipeline_loop` | In-process only; no external worker pool/queue | Medium | High |
| GPU scheduler / device select | I | `inference/gpu.py` `GpuScheduler` (CUDA auto-detect + CPU fallback), `_ort()` | Single-host device; no multi-GPU resource pool | Medium | High |
| AI scheduler (drain) | I | `inference/engine.py:422` `_scheduler_loop` — single task owns plugin runtime, `_queue(maxsize=512)` | Single-process scheduler; no multi-worker partitioning | Medium | High |
| AI store (persistence) | I | `inference/storage.py` `DetectionStore` — one background writer to Postgres, `_queue(maxsize=8000)` | Single writer → single PG; needs partition/columnar at 80k | High | High |
| ANPR pipeline | I | `anpr/pipeline.py` `AnprManager` — single pipeline task drains queue, batch OCR | Same single-node constraint | High | High |
| ANPR evidence store (disk) | P | `anpr/evidence.py` `EvidenceStore`, writes PNG crops to `/media/anpr/evidence` (bind mount) | **MISSING object storage (S3/MinIO)**; local disk does not scale | **Very High** | **High** |
| Vehicle Graph / Identity | P | `anpr/vehicle_intel/graph.py` `CameraGraph` (in-memory, haversine-proxy edges), `identity.py` | In-memory graph rebuilt from DB; needs graph DB/scale-out + real GIS | High | Medium |
| Copilot / analytics | I | `anpr/copilot/analysis.py` (multi-district, night visitors, convoys, cases), `executor.py`, `cases.py` | DB-backed queries over single PG; QPS-bound at 80k | Medium | Medium |
| PostgreSQL | P | `src/core/database.py:36` single `create_async_engine` (asyncpg, `pool_pre_ping=True`, pool_size=10, max_overflow=20, pool_recycle=1800, `expire_on_commit=False`) | No read replicas, no sharding/partitioning strategy | **Very High** | **High** |
| TimescaleDB (time-series detections) | **M** | Not present (no dependency in `requirements.txt`) | Add TimescaleDB hypertables for detections/runs | Medium | High |
| ClickHouse (analytics/heatmap) | **M** | Not present | Add columnar store for heatmap/prediction | Medium | Medium |
| Vector DB (similarity search) | **M** | Not present | Add vector store for vehicle appearance embeddings | Medium | Medium |
| Redis usage | P | `src/core/redis.py:3` `from redis import asyncio as aioredis` — used only for cache/counter/ping (`health.py:36`), **not** streams/queues | Upgrade to Redis Streams for regional queues, or use broker | Medium | High |
| Object storage | **M** | Not present (`requirements.txt` has no boto3/minio) | Add S3/MinIO for evidence/recordings | **Very High** | **High** |
| Federation / regional DB | I | `src/federation/db.py` isolated `FederationBase.metadata` (its own DB) | Multi-region / per-region sharding | Medium | Medium |
| IAM / RBAC / ABAC / audit | I | `src/federation/security/*`, `src/federation/iam_api/*` (Phase 6.1) | Scale is DB-backed; no cross-cutting scale-out blocker | Low | Low |
| Observability: structured logging | I | `src/core/logging.py` structlog JSON (prod) | N/A — good foundation | Low | — |
| Observability: metrics / Prometheus | **M** | No metrics endpoint (health only, `health.py`) | Add Prometheus metrics + dashboarding | Medium | High |
| Observability: health probes | P | `health.py` DB+Redis liveness/readiness only | No stream/AI/ANPR/GPU component health in probes | Low | Medium |
| Distributed tracing | **M** | None | Add tracing across broker/workers | Medium | Medium |
| Deployment topology | P | `docker-compose.yml:51` single `api` service, **no replicas**; `STREAM_MAX_CAMERAS=16` (`config.py:110`) | Orchestration (K8s/nomad), replica scale-out, node pools | **Very High** | **High** |

---

## 3. Bottleneck list (ordered by impact at 80k)

1. **Single `sentinel-api` process / no horizontal replicas** — `docker-compose.yml:51`. Every camera
   session, inference pump, event bus and store writer lives in one container. At 80k this is the
   hard ceiling on ingest, decode, and IQ. (Blocking, highest severity.)
2. **Single PostgreSQL writer** — `src/core/database.py:36` + `inference/storage.py` one writer queue.
   Every `InferenceRun` + per-box `Detection` row lands in one table on one instance. Write rate at
   80k × infer-fps is untenable on a single PG. TimescaleDB/ClickHouse sharding is absent.
3. **In-process event bus as the only fan-out** — `inference/events.py` / `anpr/pipeline.py:86`. Alert,
   overlay, and realtime feeds cannot cross process boundary. Replaces/crosses the missing broker.
4. **MISSING object storage** — `anpr/evidence.py` writes crops to a local bind-mounted dir
   (`/media/anpr/evidence`). No S3/MinIO. Local disk cannot hold 80k-camera evidence.
5. **Single-node AI/ANPR scheduler** — `inference/engine.py:422` (`_scheduler_loop`), `anpr/pipeline.py:305`
   (`_pipeline_loop`). One task owns the model runtime/tracking/store for all cameras. GPU batch
   `GPU_Scheduler` is host-local. No multi-GPU resource pool or worker partitioning.
6. **In-memory CameraGraph** — `anpr/vehicle_intel/graph.py` builds the whole graph in process from
   DB rows. O(n²) `_connect` (`graph.py:147`) is impractical for 80k nodes and doesn't scale across
   replicas.
7. **`STREAM_MAX_CAMERAS=16` cap** (`config.py:110`) — a per-process safety valve, not a scaling
   mechanism; raises the question of per-node ownership before any scale-out works.
8. **No metrics/tracing** — only DB+Redis health probes (`health.py`); no Prometheus, no tracing, no
   per-component (stream/AI/ANPR/GPU) health signal, so 80k fault isolation is blind.

---

## 4. Validation constraints honoured

- **Read-only.** No source files were modified; no dependency was added; no container or service was
  started. `docker-compose.yml` is unchanged.
- **No new infrastructure.** No Kafka, NATS, ClickHouse, TimescaleDB, MinIO/S3, Vector DB, or Redis
  Streams was introduced — they are catalogued only as *missing* targets.
- **Everything is grounded** in files listed above, with line references.
- **Unsupported numbers are labelled** `NOT MEASURED` / *unmeasured*.

---

## 5. Companion document

The additive, backwards-compatible implementation path (phases 7.1–7.5) is in
[`80K_ROADMAP.md`](./80K_ROADMAP.md).

# 80K_ROADMAP — Additive Roadmap to 80,000 Cameras (Phase 7.0)

**Phase:** 7.0 (roadmap only — nothing implemented here)
**Date:** 2026-09-01
**Companion:** [`SCALABILITY_GAP_ANALYSIS.md`](./SCALABILITY_GAP_ANALYSIS.md)
**Constraint:** every phase below is **additive** and **backward-compatible**. No Phase 1–6 table,
endpoint, or model is broken; new services and schemas are introduced alongside the existing
single-node pipeline, which keeps working unchanged (the existing in-process path becomes the
fallback/development mode). Existing `.env` and `docker-compose.yml` settings remain valid.

---

## Guiding principles

1. **Additive only.** New infrastructure is opt-in via environment variables. The default
   `docker-compose.yml` keeps today's single-node behavior. Scale-out activates only when the new
   env vars and services are present.
2. **Keep the proven API surface.** REST + WebSocket endpoints are stable. Message-bus plumbing is
   behind the existing `EventBus`/store interfaces, so swapping the transport does not change the API.
3. **Shards before scale.** Move from *one big node* to *many small nodes* (camera ownership shards),
   each with local caches — a pattern the codebase is already structured for (per-camera
   `StreamSession`, per-camera pump tasks).
4. **Observability first.** Nothing scales blindly; metrics/tracing come before load.
5. **Measure, don't assume.** Each phase adds a benchmark/load harness so the *unmeasured* figures in
   the gap analysis get replaced by real numbers.

---

## Phase 7.1 — Deployability & orchestration (foundation)

**Why:** every later phase needs multiple instances; they cannot run on `docker-compose` replicas
that each spawn independent ffmpeg with no coordination.

**Additive steps**
- Introduce an **edge-node ownership model**: each `sentinel-api` instance is tagged with a
  `SENTINEL_NODE_ID` and a shard/membership config (e.g. camera-id hash ranges). `StreamManager`
  remains the owner of its assigned cameras.
- Add a lightweight **registry** (writes camera→node mapping to the existing federation DB schema —
  an additive table) so the control plane knows where each camera lives.
- Move from docker-compose to an orchestrator (K8s/Nomad) as an **optional** `deploy/` charter; keep
  docker-compose for dev.
- **Metrics:** add a Prometheus `/metrics` endpoint (uvicorn + pipeline gauges: active streams,
  queue depth, infer fps, store write lag) and a per-component (stream/AI/ANPR/GPU) health block in
  the readiness probe (`health.py`).
- **Load harness:** add a synthetic 80k-camera fixture driving the ingest/control plane (extending
  the existing `registry.benchmark` ideas) so numbers become measured.

**Exits:** multi-node control plane runs; metrics emitted; first measured numbers.

**Effort:** High · **Priority:** High

---

## Phase 7.2 — Regional message bus (replace in-process fan-out at the boundary)

**Why:** the in-process `EventBus`/`asyncio.Queue` fan-out (`inference/events.py`, `anpr/pipeline.py:86`)
cannot span processes/hosts. A broker is the additive substitute.

**Additive steps**
- Adopt **NATS** (JetStream) or **Redis Streams** as the regional bus, selected by env
  (`EVENT_BUS_BACKEND`, replacing the inert stub in `federation/config.py:43-46`). **No breakage:** the
  default stays `memory`.
- Implement producer/consumer drivers behind the **existing** `EventBus` interface so `engine.py` and
  `pipeline.py` publish to topics (`frame`, `inference`, `alert`, `anpr`) without changing their logic.
- Define the topic/key schema (`camera_id` as partition key) so processing is ordered per camera.
- Keep the in-memory bus for single-node dev; broker is used only when configured.

**Exits:** alerts/overlays/ANPR events flow over the broker across 2+ nodes; single-node mode
unchanged.

**Effort:** Very High · **Priority:** High

---

## Phase 7.3 — Storage scale-out (object store + time-series + partition)

**Why:** the single-PG writer (`inference/storage.py`) and local-disk evidence (`anpr/evidence.py`) are
the hard write ceiling at 80k.

**Additive steps**
- **Tests first, additive:** keep `DetectionStore`/ANPR store writing to PG, but introduce a
  **partitioning** strategy on detections/runs by time (`ts`) in the existing schema (additive
  migration), keeping the current table names/queries valid.
- Add **object storage (MinIO/S3)** behind a new `EvidenceStore` backend (env `ANPR_EVIDENCE_BACKEND`).
  Default remains local disk. Evidence crops, frame hashes, and recordings migrate to buckets with the
  same `evidence_id` contract.
- Add **TimescaleDB** hypertables for detections/runs as an **additive** database (vector/predictive and
  heatmap analytics migrate to it). Default remains plain PG.
- **Read replicas** for the analytic/read endpoints, configurable via the DB engine; writes stay on
  the primary (or the columnar store).

**Exits:** evidence on object store; detections on hypertables; measured write rates.

**Effort:** Very High · **Priority:** High

---

## Phase 7.4 — Distributed AI/ANPR inference workers

**Why:** the single-node scheduler in `inference/engine.py:422` and `anpr/pipeline.py:305` owns model
runtime/tracking/store for all cameras.

**Additive steps**
- Split inference into **workers** that consume the frame topic (Phase 7.2) and own a model runtime,
  keyed by camera so tracking state stays consistent. Workers are **additive** replicas; the
  in-process scheduler remains the dev fallback.
- Introduce a **GPU resource pool** so batch planning (`inference/gpu.py`) allocates across GPUs/nodes
  rather than a single host device.
- ANPR stages (detect→rectify→OCR→attribute) run as pipeline workers consuming their topic, mirroring
  the existing `pipeline.py` stages but distributed.
- Vehicle Graph/Identity move to a **graph DB or partitioned store** (replacing the in-memory
  `CameraGraph` O(n²) `_connect` at `graph.py:147`) when camera count exceeds a threshold, still fed by
  the same stored detections.

**Exits:** 2+ inference nodes processing distinct cameras; measured per-node fps.

**Effort:** Very High · **Priority:** High

---

## Phase 7.5 — Intelligence & scale-hardening

**Why:** Copilot/analytics (`anpr/copilot/*`) are DB-backed single-PG queries; at 80k they need the
columnar/vector stores plus federation sharding.

**Additive steps**
- Route heatmap/prediction analytics to ClickHouse (or TimescaleDB) when present; **default** stays
  single-PG for compatibility.
- Add **vector DB** for vehicle-appearance similarity (additive; the existing string-based identity
  remains).
- **Federation/regional sharding:** extend `src/federation/db.py` to per-region databases behind the
  existing federation abstraction so regional coalescing scales.
- **Tracing** across broker/workers; **fault-tolerance** review (dead-letter topics, replay, backpressure
  metrics that already exist in `EventBus`/`DetectionStore`).
- **Perf test** the full 80k load harness and publish measured numbers, closing every *unmeasured*
  figure from the gap analysis.

**Exits:** full 80k load harness measured end-to-end; all scale paths optional and toggleable.

**Effort:** High · **Priority:** Medium–High

---

## Backward-compatibility guarantee

| Concern | Guarantee |
|---|---|
| Existing API/REST/WebSocket contracts | Unchanged |
| Existing `docker-compose.yml` default | Runs exactly as today (single-node, `memory` bus, local disk) |
| Existing `.env` / `settings.py` | All new knobs are **new env vars** with safe defaults (`memory` bus, local storage, single PG) |
| Phase 1–6 tables/models | Only additive columns/partitioning/migration; no break |
| Existing tests | New code is additive; existing unit/integration suites continue to pass |

---

## Summary

The codebase is architecturally sound for a single deployment. Scaling to 80,000 cameras is **not a
single feature** — it is a deliberately ordered, **additive** migration:

1. **7.1** orchestration + ownership + metrics (foundation)
2. **7.2** regional broker (fan-out across nodes)
3. **7.3** object store + time-series + partitioning (write ceiling)
4. **7.4** distributed inference workers + GPU pool + graph store (compute ceiling)
5. **7.5** columnar/vector analytics + federation sharding + full measured load test

Each phase ships behind a flag, keeps the current single-node path working, and replaces an
*unmeasured* assumption with a measured number.

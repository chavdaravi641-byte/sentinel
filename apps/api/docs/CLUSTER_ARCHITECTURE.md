# Cluster Architecture (Phase 7.1)

**Phase:** 7.1 (distributed edge orchestration)
**Date:** 2026-09-01
**Scope:** Broker-free orchestration over a fleet of edge nodes, each owning cameras. This document
describes the data model, the state machine, the split-brain guarantee, the scheduler, the API, and
how the layer plugs into Sentinel without disturbing the Phase 1-6 codebase.

---

## 1. Design goals

- Orchestrate N edge nodes with **no message broker**: nodes join via `POST /cluster/register` and
  push heartbeats via `POST /cluster/heartbeat`; reconciliation and failover are in-process.
- **No split-brain**: a camera is owned by exactly one node at a time, decided by a **lease** plus
  an **`ownership_version` CAS**, never by "last writer wins" on a shared counter.
- **Degrades to today**: if no remote node registers, the store holds only the local node; single-node
  deployment is unaffected.
- **Additive and isolated**: a self-contained `src/cluster/` package with its own `CL_` settings,
  its own DB base, and no change to any Phase 1-6 table, route, or contract.

---

## 2. Layered view

| Layer | Component | Role |
|---|---|---|
| Settings | `src/cluster/config.py` | `ClusterSettings` (env prefix `CL_`): heartbeat TTL (15s), grace (30s), lease TTL (30s), failover check interval. |
| State | `src/cluster/store.py` | `ClusterStore`: in-memory single-writer, `asyncio.Lock`-guarded; the **source of truth**. Inject-able `now` clock for determinism/tests. |
| Scheduler | `src/cluster/scheduler.py` | Pure, deterministic node scoring + `best_node`. |
| Service | `src/cluster/service.py` | Singleton facade + background maintenance loop (`reconcile` + `failover_sweep`). |
| Persistence | `src/cluster/{db,models,persistence}.py` | Optional SQLAlchemy snapshot (isolated `ClusterBase`) for a durable registry/audit. The in-memory store is authoritative. |
| API | `src/cluster/router.py` | `/cluster/*` REST surface. |
| Simulation | `src/cluster/simulator.py` | Deterministic node-scale sweep over the real code paths. |

---

## 3. Heartbeat state machine

A node's `status` is derived from heartbeat freshness using the settings thresholds:

| Status | Meaning | Trigger |
|---|---|---|
| `alive` | Healthy, schedulable | heartbeat within `HEARTBEAT_TTL_SECONDS` (15s) is not required to stay alive; a heartbeat sets ALIVE. |
| `unhealthy` | Stale but not yet failed out | last heartbeat older than `HEARTBEAT_GRACE_SECONDS` (30s). |
| `offline` | Assumed dead | past grace; **cannot own** new cameras, **cannot** receive a failover. |
| `recovering` | Rejoined, waiting for a fresh heartbeat | re-registered after being offline; promoted to `alive` on the next heartbeat. |

`reconcile()` walks every node, computes age from the last heartbeat, and transitions stale nodes to
OFFLINE. `failover_sweep()` only ever reassigns a camera whose owner is OFFLINE/RECOVERING **and**
whose lease has expired.

---

## 4. Camera ownership: lease + CAS

A `CameraLease` carries `owner_node_id`, `lease_expiry`, and `ownership_version`:

- **Assignment** (`assign_camera`) sets the owner, refreshes `lease_expiry` (`now + LEASE_TTL`), and
  bumps `ownership_version`. This is the CAS token.
- **Renewal** (`renew_lease`) requires the caller to present the current `ownership_version`; a stale
  token, or a wrong owner, is rejected (409) instead of clobbering a newer owner.
- **Failover** (`failover_sweep`) transfers only leases that both (a) expired and (b) whose owner is
  not schedulable. The transfer is done under the store lock and re-bumps `ownership_version`, so a
  concurrent/duplicate sweep finds nothing left to transfer.

This is why two workers can race `failover_sweep` without ever owning the same camera: only the first
passes the CAS; the second observes the already-bumped version and a fresh lease.

---

## 5. Distributed scheduler (deterministic)

`src/cluster/scheduler.py` is a set of pure functions, independent of the store, so they are trivial
to unit-test and measure:

- `capacity_score` - free CPU/GPU/memory headroom (0..1).
- `load_score` - owned-cameras-per-core ratio (balanced).
- `schedule_score` - weighted sum of CPU/GPU/mem headroom + (1 - load), scaled by a health baseline;
  returns `None` for OFFLINE/RECOVERING (never scheduled onto).
- `best_node` - highest schedulable score, stable tie-break by `node_id` for determinism, honouring
  an `exclude` set (e.g. a failing node).

Weights are configurable via `ScheduleWeights`. Scheduling is O(nodes) per camera, which the
simulator treats honestly for large clusters (bounded sample, separate full-node-count decision
probe).

---

## 6. API surface (`/cluster/*`)

- **Registry**: `GET /cluster/nodes`, `GET /cluster/nodes/{id}`, `POST /cluster/register`.
- **Heartbeat**: `POST /cluster/heartbeat` (returns ack + `failover_pending` count).
- **Ownership**: `GET /cluster/cameras`, `GET /cluster/cameras/{id}`, `POST /cluster/cameras/assign`,
  `POST /cluster/cameras/{id}/lease`.
- **Failover**: `POST /cluster/failover` (sweep, or a single camera, optionally to a fixed node).
- **Observability**: `GET /cluster/health`, `GET /cluster/dashboard`, `GET /cluster/ownership`.

The router is mounted in `src/api/v1/router.py` under the `/cluster` prefix and the service is
started/stopped in the `src/main.py` lifespan - both additive include lines.

---

## 7. Integration with the Phase 1-6 platform

- **Additive package**: `src/cluster/` is self-contained; it does not import or modify Phase 1-6
  modules.
- **Isolated settings**: `CL_` prefix, no collision with existing `STREAM_*`, `FED_*`, etc.
- **Isolated DB**: `ClusterBase.metadata` on its own engine; the in-memory store remains the source of
  truth, and the SQL snapshot is optional.
- **No infrastructure change**: `docker-compose.yml` is untouched. Single-node behaviour is
  byte-for-byte identical whether or not a cluster is configured.

---

## 8. Verification

- Unit tests (`tests/test_cluster_unit.py`): scheduler scoring/tie-break/unschedulable, lifecycle,
  lease CAS, failover conditions, concurrent no-double-transfer.
- API tests (`tests/test_cluster_api.py`): every `/cluster/*` endpoint.
- Simulation tests (`tests/test_cluster_simulation.py`): deterministic 1/5/20+ scale invariants.
- See `PHASE7_1_VALIDATION.md` for measured (synthetic) latencies and the honesty note.

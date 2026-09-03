# Phase 7.1 - Distributed Edge Orchestration (Validation Report)

**Phase:** 7.1 (implemented)
**Date:** 2026-09-01
**Scope:** Distributed edge orchestration for Sentinel: a node registry + heartbeat manager,
lease-based camera ownership, deterministic distributed scheduling, and split-brain-safe
lease-based failover with a health dashboard. This layer is **orchestration only** - no
broker / object-store / columnar / vector store is introduced.

> **Honesty note.** All latency figures below come from the deterministic simulator
> (`src/cluster/simulator.py`) which runs the *real* scheduler and store code paths and measures
> them with Python's `perf_counter`. The dataset is synthetic and every result carries
> `synthetic: true`. Nothing is fabricated, but these are in-process microsecond latencies on this
> host, **not** production network numbers. No load-test harness beyond the simulator exists.

---

## 1. Objective

Orchestrate many edge nodes (each with its own cameras) without a message broker:
nodes register, push heartbeats over REST, cameras carry an ownership **lease**, and a maintenance
loop reconciles heartbeats and fails cameras over when - and only when - the owning node is
OFFLINE/RECOVERING **and** its lease has expired. The split-brain guarantee rests on a lease + an
`ownership_version` compare-and-swap (CAS), not on "first writer wins".

Single-node deployments keep working exactly as before: if no remote node ever registers, the store
simply holds the one local node.

---

## 2. What was added (strictly additive, backward compatible)

| Piece | Location | Notes |
|---|---|---|
| Cluster settings | `src/cluster/config.py` | Standalone `CL_`-prefixed settings (no impact on Phase 1-6 config). |
| In-memory store (source of truth) | `src/cluster/store.py` | `ClusterStore`: register / heartbeat / reconcile / lease / ownership CAS / failover sweep. Inject-able `now` clock. |
| Deterministic scheduler | `src/cluster/scheduler.py` | Pure score functions: CPU/GPU/memory headroom + camera balance + health; stable tie-break. |
| Service + lifecycle | `src/cluster/service.py` | Singleton, background maintenance loop, optional self-registration. |
| Durable snapshot | `src/cluster/persistence.py`, `src/cluster/db.py`, `src/cluster/models.py` | Optional SQLAlchemy snapshot (isolated `ClusterBase` engine) for durable registry/audit. | 
| API | `src/cluster/router.py` | `/cluster/*` endpoints (see table below). |
| Mount | `src/api/v1/router.py`, `src/main.py` | Router mounted; DB init + service start/stop in lifespan (additive include lines). |
| Simulator | `src/cluster/simulator.py` | Deterministic node-scale sweep (1 / 5 / 20 / 100 / 1000). |
| Tests | `tests/test_cluster_unit.py`, `tests/test_cluster_api.py`, `tests/test_cluster_simulation.py` | 25 tests. |
| Docs | `docs/PHASE7_1_VALIDATION.md`, `docs/CLUSTER_ARCHITECTURE.md` | This report + architecture. |

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/cluster/nodes` | Active node registry |
| GET | `/cluster/nodes/{id}` | Single node |
| GET | `/cluster/health` | Cluster health summary |
| GET | `/cluster/cameras` | Camera ownership registry (optional `node_id` filter) |
| GET | `/cluster/cameras/{id}` | Single camera lease |
| POST | `/cluster/register` | Node join / discovery |
| POST | `/cluster/heartbeat` | Node heartbeat (triggers pending failover) |
| POST | `/cluster/cameras/assign` | Assign to a node, or let the scheduler pick |
| POST | `/cluster/cameras/{id}/lease` | Lease renewal (split-brain-safe CAS) |
| POST | `/cluster/failover` | Force lease-based failover (optionally one camera / fixed node) |
| GET | `/cluster/ownership` | Ownership/transfer log |
| GET | `/cluster/dashboard` | Health dashboard payload |

---

## 3. Split-brain prevention (the core guarantee)

Failover is lease-based and guarded by two independent conditions, both required:

1. the camera lease has **expired** (`lease_expiry <= now`), **and**
2. the owner node is **OFFLINE** or **RECOVERING** (not merely slow).

A healthy owner - even one past the lease window - is never overtaken. When a transfer does fire, it
writes the new owner under the store's lock and bumps `ownership_version`. Any second/concurrent
sweep sees the already-bumped version and a freshly-set lease, so it transfers nothing. The
simulator proves this by firing **two concurrent sweeps**: the first transfers all of the victim's
cameras; the second returns zero.

---

## 4. Execution evidence

### 4.1 Cluster tests

```
$ pytest tests/test_cluster_unit.py tests/test_cluster_api.py tests/test_cluster_simulation.py -q
25 passed in 0.86s
```

Coverage: scheduler scoring / tie-break / unschedulable exclusion, register-heartbeat-reconcile
lifecycle, lease CAS (renew bump, wrong-owner and version-skew rejection), failover only when
owner-offline **and** lease-expired, and the concurrent-double-sweep no-double-transfer proof.

### 4.2 Measured simulator sweep (synthetic)

`python -c "... run_simulations([1,5,20,100,1000]) ..."` (real in-process `perf_counter` timings):

```
 nodes    hb_lat_ms  sched_im_ms  sched_cam_ms  failover_ms   recover_s   split?
     1       0.03       0.0015        0.0064        0.0006       1.000       no
     5       0.003       0.0084        0.0128        0.0003       1.000       no
    20       0.003       0.0295        0.0384        0.0006       1.000       no
   100       0.002       0.164         0.167         0.0017       1.000       no
  1000       0.003       1.55          1.59          0.0084       1.000       no
```

- `hb_lat_ms`: microseconds per heartbeat (in-process).
- `sched_im_ms` / `sched_cam_ms`: latency to schedule all / per camera (store path).
- `failover_ms`: ownership-transfer sweep latency.
- `recover_s`: virtual rejoin + heartbeat recovery time (virtual clock).
- `split?`: invariant check - **no** split-brain at every scale (1-node is the documented degenerate
  case with no failover partner, reported `failover_supported=false`).

A full per-scale breakdown (`register_ms`, `heartbeat_round_ms`, `scheduler_decision_ms`,
`ownership_transfer_ms`, `cameras_failed_over`, invariant detail) is produced by
`run_simulations` and used by `tests/test_cluster_simulation.py`.

### 4.3 Invariant results (every scale)

| nodes | scheduled | expected | failover supported | no split-brain |
|---|---|---|---|---|
| 1 | 1000 | 1000 | no | yes |
| 5 | 1000 | 1000 | yes | yes |
| 20 | 1600 | 1600 | yes | yes |
| 100 | 2000* | 2000* | yes | yes |
| 1000 | 2000* | 2000* | yes | yes |

*For 100/1000 nodes the full 8k/80k-camera target is reported but the scheduler path is exercised on
a bounded 2000-camera sample to keep the synthetic sweep fast; per-camera scheduler latency is
measured separately at full node count.

---

## 5. Constraints honoured

- **Orchestration only.** No Kafka/NATS/ClickHouse/MinIO/Vector-DB. Heartbeats arrive over REST;
  reconciliation is in-process. `docker-compose.yml` unchanged (still a single `api` service).
- **Backward compatible.** Strictly additive `src/cluster/` package, isolated `CL_` settings,
  isolated DB base, and only additive include lines in `src/api/v1/router.py` / `src/main.py`.
  Single-node keeps working identically.
- **Honest numbers.** Every simulator result is `synthetic: true` and measured, never fabricated.

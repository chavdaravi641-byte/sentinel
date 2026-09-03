"""Phase 7.2 -- Distributed Cluster State.

This package is fully additive. It does not modify any Phase 1-6 module or
router. It exposes its own FastAPI router (``cluster.router``) and keeps a
standalone configuration plus a cluster store.

* Phase 7.1 moved orchestration logic out of the monolith: node registry,
  heartbeat manager, LEASE-based camera ownership and split-brain-safe failover.
* Phase 7.2 moves the *state* itself out of process memory into shared durable
  storage. The registry, leases and ownership log live in the cluster DB with
  generation numbers and optimistic-concurrency (CAS) updates, so a restarted
  process recovers persistent ownership, leases expire against durable state,
  and two processes sharing the same DB cannot create a split brain.

Phase 7.2 remains orchestration/state only: there is no message broker, no
object store, no columnar / vector database introduced here.
"""

__version__ = "7.2.0"

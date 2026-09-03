"""Cluster orchestration configuration.

Phase 7.1 -- Distributed Edge Orchestration.

Deliberately a *standalone* pydantic-settings model (env prefix ``CL_``). It
does not inherit the main ``src.core.config.Settings`` and does not modify it.
All values are overridable via environment variables or a ``.env`` file.

Only orchestration is configured here: heartbeats, leases, failover cadence and
optional durability. There is deliberately **no** message-broker setting -- the
Phase 7.1 mission excludes Kafka/NATS/etc.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ClusterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="CL_",
    )

    # --- cluster identity (self-registration defaults) --------------------
    NODE_ID: str = ""            # if set, this process auto-registers on startup
    HOSTNAME: str = ""           # if empty, socket.gethostname() is used
    REGION: str = "Gujarat"
    DISTRICT: str = ""
    VERSION: str = "7.2.0"

    # --- heartbeat timing (seconds) ----------------------------------------
    # A node is ALIVE while its last heartbeat is within TTL.
    # UNHEALTHY once TTL < age <= TTL + GRACE.
    # OFFLINE once age > TTL + GRACE (it no longer feeds the failover sweep).
    HEARTBEAT_TTL_SECONDS: float = 15.0
    HEARTBEAT_GRACE_SECONDS: float = 30.0
    # used only for derived "offline" reporting / explicit transitions.

    # --- camera lease (seconds) --------------------------------------------
    # Each camera owned by a node carries a lease. Ownership is valid until the
    # lease expires; a live owner keeps renewing. Failover is triggered when a
    # lease expires (the owner has stopped renewing = it is gone). Lease-based
    # ownership is the basis of split-brain prevention.
    LEASE_TTL_SECONDS: float = 30.0

    # --- scheduling / failover cadence -------------------------------------
    FAILOVER_CHECK_INTERVAL_SECONDS: float = 5.0

    # --- optional durability (snapshot of the registry) ---------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    DB_ECHO: bool = False


@lru_cache
def get_cluster_settings() -> ClusterSettings:
    return ClusterSettings()


settings = get_cluster_settings()

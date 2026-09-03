"""Federation platform configuration.

Deliberately a *standalone* pydantic-settings model. It does not inherit the
main ``src.core.config.Settings`` class and does not modify it. All values are
overridable via environment variables (prefixed ``FED_``) or a ``.env`` file.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class FederationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="FED_",
    )

    # --- Core identity ----------------------------------------------------
    STATE: str = "Gujarat"
    TARGET_CAMERA_COUNT: int = 80_000

    # --- Isolated database (optional; falls back to in-memory for tests) --
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    DB_ECHO: bool = False

    # --- Vendor adapters --------------------------------------------------
    CAMERA_PROBE_TIMEOUT_SECONDS: float = 3.0
    RTSP_DEFAULT_PORT: int = 554
    ONVIF_DEFAULT_PORT: int = 80

    # --- VMS connectors ----------------------------------------------------
    VMS_TOKEN_CACHE_TTL_SECONDS: int = 300

    # --- Storage & retention ----------------------------------------------
    DEFAULT_RETENTION_DAYS: int = 30
    STORAGE_BASE_DIR: str = "var/federation/media"

    # --- Event bus ----------------------------------------------------------
    EVENT_BUS_BACKEND: str = "memory"  # memory | redis_streams | kafka
    REDIS_URL: str = "redis://localhost:6379/0"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    EVENT_STREAM_NAME: str = "federation:events"

    # --- Security -------------------------------------------------------------
    WEBHOOK_SIGNING_SECRET: str = "federation-webhook-signing-secret"
    WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS: int = 300
    RATE_LIMIT_DB_URL: str = "redis://localhost:6379/0"  # e.g. redis for limiter
    RATE_LIMIT_PER_MINUTE: int = 600

    # --- Health monitoring ---------------------------------------------------
    HEALTH_CHECK_INTERVAL_SECONDS: int = 60
    HEALTH_DEGRADED_THRESHOLD_SECONDS: int = 8


@lru_cache
def get_federation_settings() -> FederationSettings:
    return FederationSettings()


settings = get_federation_settings()

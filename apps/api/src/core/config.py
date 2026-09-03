"""Application configuration loaded from environment variables.

Uses pydantic-settings. All values are overridable via environment variables
or a root `.env` file (docker-compose injects them directly).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Project
    PROJECT_NAME: str = "Sentinel AI"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    VERSION: str = "1.0.0"

    # Security
    SECRET_KEY: str = "unsafe-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: str | None = None

    # CORS
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # --- Phase 6.2: Enterprise security hardening ---------------------------
    # Secret management (see src/security/secrets.py startup diagnostics).
    SECRET_STEALTH_LOG: bool = True       # only log whether a secret is set, never its value
    SECRET_MIN_LENGTH: int = 32
    SECRET_MAX_AGE_DAYS: int = 180
    # Unsafe defaults are flagged unless overridden in a non-development env.
    SECRET_ALLOW_UNSAFE_DEFAULT: bool = False

    # JWT / auth hardening
    JWT_ROTATION_ENABLED: bool = True
    JWT_ROTATION_GRACE_SECONDS: int = 300   # old-key validity window during rotation
    JWT_ROTATION_KEYS: str = "1"            # comma list: absolute key file paths, or count of auto keys
    ACCESS_TOKEN_EXPIRE_MINUTES_HARD: int = 15  # access token rotation target
    SESSION_FINGERPRINT_ENABLED: bool = True
    SESSION_FINGERPRINT_TOLERANCE: float = 0.75
    MAX_CONCURRENT_SESSIONS: int = 5
    LOGIN_FAILURE_LIMIT: int = 5            # before lockout
    LOGIN_LOCKOUT_MINUTES: int = 15
    LOGIN_PROGRESSIVE_BACKOFF: bool = True
    PASSWORD_HISTORY_LIMIT: int = 5
    PASSWORD_EXPIRY_DAYS: int = 90
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPER: bool = True
    PASSWORD_REQUIRE_LOWER: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SYMBOL: bool = True

    # MFA
    MFA_ENABLED: bool = True
    MFA_ISSUER: str = "Sentinel AI"
    MFA_TOTP_WINDOW: int = 1
    MFA_RECOVERY_CODE_COUNT: int = 10
    MFA_TRUSTED_DEVICE_TTL_DAYS: int = 30

    # API security / headers
    SECURITY_HEADERS_ENABLED: bool = True
    SECURITY_HEADERS_HSTS: bool = True       # HSTS only when ENVIRONMENT=production
    CORS_ALLOWED_ORIGINS: str = BACKEND_CORS_ORIGINS  # explicit allowlist
    CSRF_PROTECTION_ENABLED: bool = True
    CSRF_COOKIE_NAME: str = "sentinel_csrf"
    REPLAY_PROTECTION_ENABLED: bool = True
    REPLAY_WINDOW_SECONDS: int = 300
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_BASE_REQUESTS: int = 120      # per window per client
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_LOGIN_REQUESTS: int = 10      # stricter per-window for /auth/login
    MAX_BODY_BYTES: int = 1_048_576          # 1 MiB request body cap

    # Database
    POSTGRES_USER: str = "sentinel"
    POSTGRES_PASSWORD: str = "sentinel"
    POSTGRES_DB: str = "sentinel"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str | None = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Seed
    SEED_ON_STARTUP: bool = True
    ADMIN_EMAIL: str = "admin@sentinel.gp"
    ADMIN_PASSWORD: str = "Admin@2026"

    # Camera test
    CAMERA_TEST_TIMEOUT_SECONDS: float = 4.0

    # --- Phase 2: live streaming engine -----------------------------------
    MEDIA_ROOT: str = "/media"
    RECORDING_DIR: str = "/media/recordings"
    SNAPSHOT_DIR: str = "/media/snapshots"

    # Concurrency / pipeline caps
    STREAM_MAX_CAMERAS: int = 16
    STREAM_THREAD_POOL: int = 8
    # Allow lavfi/test synthetic inputs (validation only — never in production)
    STREAM_ALLOW_TEST_SOURCES: bool = False

    # Transcode profile (H.264 baseline for HLS + WebRTC publish)
    STREAM_PROFILE_SCALE: int = 720
    STREAM_PROFILE_FPS: int = 25
    STREAM_PROFILE_CRF: int = 27
    STREAM_PROFILE_PRESET: str = "veryfast"
    RTSP_TRANSPORT: str = "tcp"
    FFMPEG_TIMEOUT_SECONDS: float = 12.0

    # Resilience
    STREAM_RECONNECT_MAX: int = 30
    STREAM_RECONNECT_BASE_DELAY: float = 1.5
    STREAM_RECONNECT_MAX_DELAY: float = 30.0
    STREAM_WATCH_INTERVAL: float = 2.0

    # Stream authentication (signed media URLs)
    STREAM_AUTH_TTL_SECONDS: int = 3600

    # MJPEG ingest
    MJPEG_FPS: int = 15
    MJPEG_QUALITY: int = 3

    # Edge media server (HLS + WebRTC fan-out)
    MEDIAMTX_BASE_URL: str = "http://mediamtx:8888"
    MEDIAMTX_WHEP_URL: str = "http://mediamtx:8889"
    MEDIAMTX_RTSP_URL: str = "rtsp://mediamtx:8554"
    MEDIAMTX_READ_TIMEOUT: float = 8.0
    HLS_TARGET_LATENCY: float = 2.5

    # Recording
    RECORDING_SEGMENT_SECONDS: int = 15
    RECORDING_MAX_SECONDS: int = 0  # 0 = run until explicit stop
    RECORDING_SCHEDULE_ENABLED: bool = False
    # Comma-separated local-time windows, e.g. "00:00-08:00,20:00-23:59"
    RECORDING_SCHEDULE: str = ""

    # Motion snapshot (OpenCV frame-difference; not AI)
    MOTION_ENABLED: bool = True
    MOTION_BACKGROUND_FRAMES: int = 24
    MOTION_PERCENT_THRESHOLD: float = 0.08
    MOTION_PIXEL_THRESHOLD: int = 28
    MOTION_DETECT_FPS: int = 5
    MOTION_RECORD_CLIP_SECONDS: int = 0  # 0 = snapshot only

    # ONVIF discovery
    ONVIF_DISCOVERY_TIMEOUT: float = 2.5
    ONVIF_PROBE_URLS: str = ""  # comma-separated direct device URLs to probe

    # GPU acceleration (auto-detected; nvenc/vaapi/qsv when available)
    GPU_ACCELERATION: str = "auto"

    # --- Phase 3: AI inference engine --------------------------------------
    AI_ENABLED: bool = True
    # Where model weights live inside the API container. Drop YOLOv12 ONNX
    # weights at {AI_WEIGHTS_DIR}/yolov12/yolov12s.onnx to enable the real
    # ONNX backend; when absent the plugin runs a deterministic simulation
    # backend so the full pipeline (tracking/events/store/alerts) still works.
    AI_WEIGHTS_DIR: str = "/media/ai/models"
    # "auto" prefers CUDA when available with automatic CPU fallback,
    # "cuda" forces GPU, "cpu" forces CPU.
    AI_ACCEL: str = "auto"
    AI_MODEL: str = "yolov12"
    # Max inference throughput per camera (frames analyzed per second).
    AI_INFER_FPS: float = 5.0
    AI_CONFIDENCE: float = 0.4
    # Batch scheduler (batch inference across cameras on a GPU).
    AI_BATCH_SIZE: int = 4
    AI_BATCH_WINDOW_MS: float = 15.0
    # Overlay (WS) publish interval in seconds per camera.
    AI_OVERLAY_INTERVAL: float = 0.3
    # Object tracker max age (seconds before a track is dropped).
    AI_TRACK_MAX_AGE: float = 2.0
    # Persist every run + detection to Postgres.
    AI_STORE_ENABLED: bool = True
    # Alert engine.
    AI_ALERT_ENABLED: bool = True
    AI_ALERT_PERSISTENCE: int = 4  # frames a track must persist before alerting
    AI_ALERT_CROWD_PERSONS: int = 5
    AI_ALERT_TRAFFIC_VEHICLES: int = 6
    AI_ALERT_COOLDOWN: float = 30.0  # seconds between alert repeats per key

    # --- Phase 4: ANPR & vehicle intelligence ------------------------------
    ANPR_ENABLED: bool = True
    # Where ANPR model weights + OCR assets live inside the API container.
    # Drop YOLO plate-detector ONNX at {ANPR_WEIGHTS_DIR}/plate/yolo_plate.onnx,
    # the OCR engine under {ANPR_WEIGHTS_DIR}/ocr/..., and the vehicle-attribute
    # vision model under {ANPR_WEIGHTS_DIR}/vehicle/... . When any asset is
    # absent the corresponding stage runs its deterministic simulation path so
    # the full pipeline (rectify -> OCR -> validate -> attribute -> store ->
    # alert) still works end-to-end.
    ANPR_WEIGHTS_DIR: str = "/media/ai/models/anpr"
    ANPR_ACCEL: str = "auto"  # auto / cuda / cpu (auto-falls back to CPU)
    # Plate-grid scanning cadence per camera (analyzed frames per second).
    ANPR_INFER_FPS: float = 5.0
    ANPR_PLATE_MIN_CONF: float = 0.35
    ANPR_OCR_MIN_CONF: float = 0.55
    # How many plate crops are sent to the OCR engine in one batched call.
    ANPR_OCR_BATCH_SIZE: int = 8
    # Persist every recognized plate + vehicle to Postgres.
    ANPR_STORE_ENABLED: bool = True
    # Persist evidence artifacts (frame/plate/vehicle crops + hash) to disk.
    ANPR_EVIDENCE_ENABLED: bool = True
    ANPR_EVIDENCE_DIR: str = "/media/anpr/evidence"
    # Blacklist detection tolerance (strip non-alphanumerics before compare).
    ANPR_PLATE_STRICT_EQ: bool = True
    # Alerts.
    ANPR_ALERT_ENABLED: bool = True
    ANPR_ALERT_BLACKLIST: bool = True
    ANPR_ALERT_LOW_CONF: bool = True
    ANPR_ALERT_LOW_CONF_THRESHOLD: float = 0.45
    ANPR_ALERT_MULTI_CAMERA_WINDOW: float = 120.0  # seconds
    ANPR_ALERT_MULTI_CAMERA_ENABLED: bool = True
    ANPR_ALERT_REAPPEAR: bool = True
    ANPR_ALERT_REAPPEAR_AFTER: float = 3600.0  # seconds since last seen
    ANPR_ALERT_COOLDOWN: float = 60.0  # seconds between repeat alerts per key
    # Blacklist auto-sync into memory from the DB on startup.
    ANPR_BLACKLIST_SYNC_SECONDS: float = 60.0

    @property
    def anpr_sqlalchemy_database_uri(self) -> str:  # noqa: S105 - kept for parity
        return self.sqlalchemy_database_uri

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Resolve the SQLAlchemy async URL.

        Docker-compose overrides DATABASE_URL. Falls back to one built from
        the individual POSTGRES_* variables for local development.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
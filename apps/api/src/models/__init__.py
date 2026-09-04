"""ORM models.

Importing this package registers every table on Base.metadata so that both
`create_all` and Alembic autogenerate can discover them.
"""

from src.models.alert import Alert
from src.models.anpr import AnprAlert, BlacklistEntry, EvidenceRecord, PlateDetection
from src.models.base import Base, TimestampMixin
from src.models.camera import Camera
from src.models.copilot import (
    CaseBookmark,
    CaseEvidence,
    CaseNote,
    InvestigationCase,
    InvestigationLog,
)
from src.models.incident import Incident
from src.models.inference import (
    AiModel,
    Detection,
    InferenceAlert,
    InferenceRun,
)
from src.models.refresh_token import RefreshToken
from src.models.registry import (
    AccessRole,
    CameraAuditLog,
    CameraCategory,
    CameraRegistry,
    OwnershipType,
    RegistryEventType,
)
from src.models.security import (
    LoginAttempt,
    MfaRecoveryCode,
    PasswordHistory,
    SecurityEvent,
    SecurityThreat,
    TrustedDevice,
    UserSecurity,
)
from src.models.stream import Recording, Stream
from src.models.user import User
from src.models.vehicle_intel import CameraGraphEdge, VehicleIdentity, VehicleSighting
from src.models.watchlist import Watchlist, WatchlistCategory, WatchlistSourceDB, WatchlistTargetType

__all__ = [
    "AccessRole",
    "AiModel",
    "Alert",
    "AnprAlert",
    "Base",
    "BlacklistEntry",
    "Camera",
    "CameraAuditLog",
    "CameraCategory",
    "CameraGraphEdge",
    "CameraRegistry",
    "CaseBookmark",
    "CaseEvidence",
    "CaseNote",
    "Detection",
    "EvidenceRecord",
    "Incident",
    "InferenceAlert",
    "InferenceRun",
    "InvestigationCase",
    "InvestigationLog",
    "LoginAttempt",
    "MfaRecoveryCode",
    "OwnershipType",
    "PasswordHistory",
    "PlateDetection",
    "Recording",
    "RefreshToken",
    "RegistryEventType",
    "SecurityEvent",
    "SecurityThreat",
    "Stream",
    "TimestampMixin",
    "TrustedDevice",
    "User",
    "UserSecurity",
    "VehicleIdentity",
    "VehicleSighting",
    "Watchlist",
    "WatchlistCategory",
    "WatchlistSourceDB",
    "WatchlistTargetType",
]
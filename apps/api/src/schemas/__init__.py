"""Pydantic request/response schemas (v2)."""

from src.schemas.alert import AlertRead, AlertStats, AlertUpdate
from src.schemas.auth import LoginRequest, TokenPair
from src.schemas.camera import (
    CameraCreate,
    CameraRead,
    CameraTestResult,
    CameraUpdate,
)
from src.schemas.common import ErrorResponse, HealthResponse, MessageResponse, Paginated
from src.schemas.dashboard import CameraGeoPoint, DashboardSummary, SystemHealth
from src.schemas.incident import IncidentCreate, IncidentRead, IncidentUpdate
from src.schemas.user import (
    ChangePasswordRequest,
    UserCreate,
    UserRead,
    UserUpdate,
)

__all__ = [
    "AlertRead",
    "AlertStats",
    "AlertUpdate",
    "CameraCreate",
    "CameraGeoPoint",
    "CameraRead",
    "CameraTestResult",
    "CameraUpdate",
    "ChangePasswordRequest",
    "DashboardSummary",
    "ErrorResponse",
    "HealthResponse",
    "IncidentCreate",
    "IncidentRead",
    "IncidentUpdate",
    "LoginRequest",
    "MessageResponse",
    "Paginated",
    "SystemHealth",
    "TokenPair",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
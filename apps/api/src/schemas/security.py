"""Phase 6.2 security endpoint schemas (additive)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MfaSetupRequest(BaseModel):
    """Empty request body for starting MFA enrollment."""

    model_config = ConfigDict(extra="forbid")


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_url: str = ""


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MfaConfirmResponse(BaseModel):
    enabled: bool
    recovery_codes: list[str] = Field(default_factory=list)


class MfaDisableRequest(BaseModel):
    current_password: str = Field(min_length=1)
    code: str = Field(default="", max_length=8)


class MfaChallengeRequest(BaseModel):
    code: str = Field(default="", max_length=8)
    recovery_code: str = Field(default="", max_length=32)


class MfaStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int = 0


class SessionOut(BaseModel):
    id: str
    device_name: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: str | None = None
    last_used_at: str | None = None
    current: bool = False


class SingleDeviceRequest(BaseModel):
    keep_session_id: str | None = Field(default=None, max_length=64)


class PasswordChangeRequestExisting(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class SecretDiagnosticsResponse(BaseModel):
    environment: str
    secrets: list[dict[str, Any]] = Field(default_factory=list)


class ThreatReportResponse(BaseModel):
    findings: int
    threats: list[dict[str, Any]] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    risk: dict[str, Any] = Field(default_factory=dict)
    open_vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    auth_events: list[dict[str, Any]] = Field(default_factory=list)
    threat_timeline: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class CsrfTokenResponse(BaseModel):
    csrf_token: str


class Message(BaseModel):
    message: str

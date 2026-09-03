"""Phase 6.2 security & hardening endpoints (additive, /security).

Provides: secret diagnostics, security dashboard, threat report, MFA lifecycle,
sessions (multi-device) management, password security checks and CSRF tokens.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from src.api.deps import CurrentUser, DBDep, get_request_meta
from src.core.config import settings
from src.crud import user as user_crud
from src.schemas.common import MessageResponse
from src.schemas.security import (
    CsrfTokenResponse,
    DashboardResponse,
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaSetupResponse,
    MfaStatusResponse,
    PasswordChangeRequestExisting,
    SecretDiagnosticsResponse,
    SessionOut,
    SingleDeviceRequest,
    ThreatReportResponse,
)
from src.security import mfa as mfa_service
from src.security import password as password_service
from src.security import secrets as secrets_service
from src.security import threat as threat_service
from src.security.auth import (
    device_fingerprint,
    device_label_from,
    list_user_sessions,
    revoke_other_sessions,
    revoke_session_by_id,
)
from src.security.dashboard import dashboard as build_dashboard
from src.security.mfa import totp_uri

router = APIRouter()


# ------------------------------------------------------------------ #
# Secret management diagnostics (Part 6)
# ------------------------------------------------------------------ #
@router.get("/secrets/diagnostics", response_model=SecretDiagnosticsResponse)
async def secret_diagnostics(_: CurrentUser, db: DBDep) -> SecretDiagnosticsResponse:
    diags = secrets_service.run_secret_diagnostics()
    return SecretDiagnosticsResponse(
        environment=settings.ENVIRONMENT,
        secrets=[d.to_dict() for d in diags],
    )


# ------------------------------------------------------------------ #
# Security dashboard & threat report (Parts 7 & 8)
# ------------------------------------------------------------------ #
@router.get("/dashboard", response_model=DashboardResponse)
async def security_dashboard(db: DBDep, _: CurrentUser) -> DashboardResponse:
    return DashboardResponse(**await build_dashboard(db))


@router.get("/threats", response_model=ThreatReportResponse)
async def threat_report(db: DBDep, _: CurrentUser) -> ThreatReportResponse:
    timeline = await _build_threat_timeline(db)
    return ThreatReportResponse(findings=len(timeline), threats=timeline)


async def _build_threat_timeline(db):
    from src.security.threat import threat_timeline as _tl

    return await _tl(db)


# ------------------------------------------------------------------ #
# MFA lifecycle (Part 3)
# ------------------------------------------------------------------ #
@router.get("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(db: DBDep, current_user: CurrentUser) -> MfaSetupResponse:
    secret = await mfa_service.provision_totp(db, current_user.id)
    return MfaSetupResponse(
        secret=secret,
        otpauth_url=totp_uri(secret, current_user.email),
    )


@router.post("/mfa/confirm", response_model=MfaConfirmResponse)
async def mfa_confirm(
    body: MfaConfirmRequest, db: DBDep, current_user: CurrentUser
) -> MfaConfirmResponse:
    enabled = await mfa_service.confirm_and_enable_mfa(db, current_user.id, code=body.code)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code."
        )
    codes = await mfa_service.generate_recovery_codes(db, current_user.id)
    await threat_service.record_event(
        db,
        event_type="mfa_enabled",
        severity="info",
        actor_id=str(current_user.id),
    )
    return MfaConfirmResponse(enabled=True, recovery_codes=codes)


@router.post("/mfa/disable", response_model=MessageResponse)
async def mfa_disable(
    body: MfaDisableRequest, db: DBDep, current_user: CurrentUser
) -> MessageResponse:
    from src.core.security import verify_password

    pw_ok = verify_password(body.current_password, current_user.password_hash)
    if not pw_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    # Require a valid TOTP or recovery code to disable.
    if not (await _can_disable_mfa(db, current_user.id, body.code)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA code or recovery code required to disable.",
        )
    await mfa_service.disable_mfa(db, current_user.id, current_password_ok=True)
    await threat_service.record_event(
        db,
        event_type="mfa_disabled",
        severity="warning",
        actor_id=str(current_user.id),
    )
    return MessageResponse(message="Multi-factor authentication disabled.")


async def _can_disable_mfa(db, user_id, code: str) -> bool:
    from src.security.mfa import _get_or_create as mfa_get_or_create

    sec = await mfa_get_or_create(db, user_id)
    if not sec:
        return False
    if code and mfa_service.verify_totp(sec.mfa_secret or "", code):
        return True
    if code and await mfa_service.consume_recovery_code(db, user_id, code):
        return True
    return False


@router.get("/mfa/status", response_model=MfaStatusResponse)
async def mfa_status(db: DBDep, current_user: CurrentUser) -> MfaStatusResponse:
    enabled = await mfa_service.mfa_required(db, current_user.id)
    remaining = await mfa_service.backup_codes_remaining(db, current_user.id)
    return MfaStatusResponse(enabled=enabled, recovery_codes_remaining=remaining)


@router.get("/mfa/recovery-codes", response_model=MfaConfirmResponse)
async def mfa_new_recovery_codes(
    db: DBDep, current_user: CurrentUser
) -> MfaConfirmResponse:
    enabled = await mfa_service.mfa_required(db, current_user.id)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA must be enabled before regenerating recovery codes.",
        )
    codes = await mfa_service.generate_recovery_codes(db, current_user.id)
    return MfaConfirmResponse(enabled=True, recovery_codes=codes)


# ------------------------------------------------------------------ #
# Session / multi-device management (Part 1)
# ------------------------------------------------------------------ #
@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    db: DBDep,
    current_user: CurrentUser,
    request: Request,
) -> list[SessionOut]:
    user_agent, ip = get_request_meta(request)
    fp = device_fingerprint(user_agent=user_agent, ip=ip, user_id=current_user.id)
    sessions = await list_user_sessions(db, current_user.id)
    return [
        SessionOut(
            id=str(s.id),
            device_name=s.device_name or device_label_from(s.user_agent),
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at.isoformat() if s.created_at else None,
            last_used_at=s.last_used_at.isoformat() if s.last_used_at else None,
            current=s.fingerprint == fp,
        )
        for s in sessions
    ]


@router.post("/sessions/{session_id}/revoke", response_model=MessageResponse)
async def revoke_session(
    session_id: str, db: DBDep, current_user: CurrentUser
) -> MessageResponse:
    try:
        sid = uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session id."
        ) from exc
    if not await revoke_session_by_id(db, current_user.id, sid):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked.",
        )
    return MessageResponse(message="Session revoked.")


@router.post(
    "/sessions/single-device", response_model=MessageResponse
)
async def single_device(
    body: SingleDeviceRequest, db: DBDep, current_user: CurrentUser, request: Request
) -> MessageResponse:
    """Log out all devices except the current one."""
    user_agent, ip = get_request_meta(request)
    fp = device_fingerprint(user_agent=user_agent, ip=ip, user_id=current_user.id)
    sessions = await list_user_sessions(db, current_user.id)
    keep = next((s for s in sessions if s.fingerprint == fp), None)
    if keep is None and body.keep_session_id:
        keep = next(
            (s for s in sessions if str(s.id) == body.keep_session_id), None
        )
    keep_id = keep.id if keep else None
    if keep_id:
        await revoke_other_sessions(db, current_user.id, keep_id)
    return MessageResponse(
        message="All other devices were logged out."
    )


@router.post("/sessions/revoke-all", response_model=MessageResponse)
async def revoke_all_sessions(
    db: DBDep, current_user: CurrentUser
) -> MessageResponse:
    from src.services import tokens as token_service

    await token_service.purge_user_sessions(db, current_user.id)
    return MessageResponse(
        message="Logged out from all devices."
    )


# ------------------------------------------------------------------ #
# Password security (Part 2)
# ------------------------------------------------------------------ #
@router.post("/password/change", response_model=MessageResponse)
async def change_password_secure(
    body: PasswordChangeRequestExisting,
    db: DBDep,
    current_user: CurrentUser,
) -> MessageResponse:
    from src.core.security import verify_password

    if not verify_password(body.current_password, current_user.password_hash):
        await threat_service.record_event(
            db,
            event_type="password_changed",
            severity="warning",
            actor_id=str(current_user.id),
            detail={"outcome": "wrong_current_password"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if await password_service.password_is_reused(db, current_user.id, body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password was used recently. Please choose a different password.",
        )
    issues = password_service.password_strength_issues(body.new_password)
    if issues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password " + ", ".join(issues) + ".",
        )
    await user_crud.update_password(db, current_user, body.new_password)
    await password_service.record_password_change(db, current_user, body.new_password)
    from src.services import tokens as token_service

    await token_service.purge_user_sessions(db, current_user.id)
    await threat_service.record_event(
        db,
        event_type="password_changed",
        severity="info",
        actor_id=str(current_user.id),
        detail={"outcome": "success"},
    )
    return MessageResponse(
        message="Password updated. Please sign back in on your other devices."
    )


# ------------------------------------------------------------------ #
# CSRF token (Part 4)
# ------------------------------------------------------------------ #
@router.get("/csrf-token", response_model=CsrfTokenResponse)
async def csrf_token(current_user: CurrentUser) -> CsrfTokenResponse:
    from src.security.api import csrf_token as make_csrf
    from src.security.auth import hash_token

    entropy = hash_token(str(current_user.id))
    return CsrfTokenResponse(csrf_token=make_csrf(str(current_user.id), entropy))

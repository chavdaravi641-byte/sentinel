"""Authentication endpoints: login, refresh, logout, me, change-password.

Phase 6.2 integrates additive hardening on top of the existing flow:

- Login rate limiting + account lockout + progressive backoff (Part 2/4)
- Device fingerprinting + session binding + concurrent session limits (Part 1)
- Opt-in MFA challenge (Part 3) — only engages when a user enables MFA,
  preserving the existing password-only behaviour for everyone else.
- Security event + threat recording (Parts 7/8).

The successful password-only path is unchanged (full backward compatibility).
"""


from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from src.api.deps import CurrentUser, DBDep, get_request_meta
from src.core.config import settings as app_settings
from src.core.logging import log
from src.core.security import create_access_token, verify_password
from src.crud import user as user_crud
from src.schemas.auth import LoginRequest, TokenPair
from src.schemas.common import MessageResponse
from src.schemas.security import MfaChallengeRequest
from src.schemas.user import ChangePasswordRequest, UserRead
from src.security import auth as sec_auth
from src.security import mfa as mfa_service
from src.security import password as password_service
from src.security import threat as threat_service
from src.security.api import rate_limit_hit
from src.services import tokens as token_service

router = APIRouter()

MFA_REQUIRED_DETAIL = "mfa_required"


async def _issue_and_set_cookie(
    db,
    user,
    response: Response,
    request: Request,
    *,
    challenge_nonce: str | None = None,
) -> TokenPair:
    """Create tokens, set the refresh httpOnly cookie, return the pair."""
    user_agent, ip = get_request_meta(request)
    device_fp = sec_auth.device_fingerprint(
        user_agent=user_agent, ip=ip, user_id=user.id
    )
    access_token, refresh_raw, access_max, refresh_max = await token_service.create_token_pair(
        db, user, user_agent=user_agent, ip_address=ip
    )
    # Bind device metadata to the newly created refresh session.
    await _bind_fingerprint(db, user.id, device_fp, user_agent)
    # Enforce concurrent-session limits (revoke oldest beyond max).
    await sec_auth.enforce_concurrent_sessions(db, user.id)
    response.set_cookie(**token_service.make_refresh_cookie(refresh_raw, refresh_max))
    await user_crud.set_last_login(db, user)
    await threat_service.record_event(
        db,
        event_type="login_success",
        severity="info",
        actor_id=str(user.id),
        ip_address=ip,
        user_agent=user_agent,
        trace_id=request.state.trace_id if hasattr(request.state, "trace_id") else None,
        request_id=request.state.request_id if hasattr(request.state, "request_id") else None,
    )
    return TokenPair(
        access_token=access_token,
        expires_in=access_max,
        user=UserRead.model_validate(user),
    )


async def _bind_fingerprint(db, user_id, fingerprint: str, user_agent: str | None) -> None:
    from sqlalchemy import select, update

    from src.models.refresh_token import RefreshToken

    stmt = (
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .where(RefreshToken.revoked_at.is_(None))
        .where(RefreshToken.fingerprint.is_(None))
        .order_by(RefreshToken.created_at.desc())
        .limit(1)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        return
    device_name = sec_auth.device_label_from(user_agent)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == session.id)
        .values(
            fingerprint=fingerprint,
            device_name=device_name,
            last_used_at=sec_auth._utcnow(),
        )
    )
    await db.commit()


@router.post("/login", response_model=TokenPair, summary="Authenticate with email + password")
async def login(
    *,
    db: DBDep,
    request: Request,
    response: Response,
    body: LoginRequest,
) -> TokenPair:
    user_agent, ip = get_request_meta(request)

    # Rate-limit the login endpoint by client (Part 4).
    allowed, _remaining = await rate_limit_hit(
        f"login:{ip or 'unk'}", login_path=True
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait and try again.",
        )

    user_obj = await user_crud.get_by_email(db, body.email)

    # Account lockout / brute-force protection (Part 2).
    if user_obj is not None:
        locked, retry_after = await password_service.lockout_probe(db, user_obj.id)
        if locked:
            log.info("auth.lockout", user_id=str(user_obj.id), retry_after=retry_after)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

    valid = user_obj is not None and verify_password(body.password, user_obj.password_hash)
    if not valid:
        if user_obj is not None:
            await password_service.register_failed_attempt(
                db,
                identifier=body.email,
                user_agent=user_agent,
                ip_address=ip,
                user_id=user_obj.id,
            )
        else:
            await password_service.register_failed_attempt(
                db,
                identifier=body.email,
                user_agent=user_agent,
                ip_address=ip,
            )
        await threat_service.evaluate_login_patterns(db, ip_address=ip, identifier=body.email)
        await threat_service.record_event(
            db,
            event_type="login_failure",
            severity="warning",
            ip_address=ip,
            user_agent=user_agent,
            detail={"identifier": body.email},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated. Contact an administrator.",
        )

    await password_service.register_successful_attempt(
        db, identifier=body.email, user_agent=user_agent, ip_address=ip, user_id=user_obj.id
    )

    # Opt-in MFA challenge (Part 3). Only for accounts with MFA enabled.
    device_fp = sec_auth.device_fingerprint(
        user_agent=user_agent, ip=ip, user_id=user_obj.id
    )
    mfa_on = await mfa_service.mfa_required(db, user_obj.id)
    device_trusted = await mfa_service.is_device_trusted(db, user_obj.id, device_fp)
    if mfa_on and not device_trusted:
        nonce = sec_auth.create_mfa_challenge(
            user_obj.id, user_obj.email, user_agent=user_agent, ip=ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MFA_REQUIRED_DETAIL,
            headers={"X-MFA-Nonce": nonce},
        )

    token_pair = await _issue_and_set_cookie(db, user_obj, response, request)
    log.info("auth.login", user_id=str(user_obj.id), email=user_obj.email)
    return token_pair


@router.post("/mfa/verify", response_model=TokenPair)
async def mfa_verify(
    *,
    db: DBDep,
    request: Request,
    response: Response,
    body: MfaChallengeRequest,
) -> TokenPair:
    """Complete a login that was gated by MFA (TOTP or recovery code)."""
    nonce = request.headers.get("x-mfa-nonce")
    challenge = sec_auth.consume_mfa_challenge(nonce or "")
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA challenge expired. Please log in again.",
        )
    user_obj = await user_crud.get_by_id(db, challenge["user_id"])
    if user_obj is None or not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not valid.",
        )

    code = body.code or ""
    recovery = body.recovery_code or ""
    if code and await mfa_service.verify_totp(await _secret_for(db, user_obj.id), code):
        ok = True
    elif recovery and await mfa_service.consume_recovery_code(db, user_obj.id, recovery):
        ok = True
        await threat_service.record_event(
            db,
            event_type="mfa_recovery_used",
            severity="info",
            actor_id=str(user_obj.id),
        )
    else:
        await threat_service.record_event(
            db,
            event_type="mfa_failure",
            severity="warning",
            actor_id=str(user_obj.id),
            detail={"identifier": challenge.get("email")},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code.",
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code.",
        )

    # Bind this device as trusted so subsequent logins skip the challenge.
    user_agent, ip = get_request_meta(request)
    device_fp = sec_auth.device_fingerprint(
        user_agent=user_agent, ip=ip, user_id=user_obj.id
    )
    await mfa_service.trust_device(db, user_obj.id, device_fp, label=sec_auth.device_label_from(user_agent))
    return await _issue_and_set_cookie(db, user_obj, response, request)


async def _secret_for(db, user_id) -> str:
    from src.security.mfa import _get_or_create as _goc

    sec = await _goc(db, user_id)
    return sec.mfa_secret or ""


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    *,
    db: DBDep,
    request: Request,
    response: Response,
    sentinel_refresh: str | None = Cookie(default=None),
) -> TokenPair:
    """Rotate the refresh session and return a fresh access token."""
    raw = sentinel_refresh
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token.",
        )
    user_agent, ip = get_request_meta(request)
    rotated = await token_service.rotate_refresh_session(
        db, raw, user_agent=user_agent, ip_address=ip
    )
    if rotated is None:
        # A replayed / already-rotated token is a token-replay signal (Part 7).
        await threat_service.report_token_replay(db, actor_id=None, ip_address=ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired.",
        )
    user_obj, new_raw, refresh_max = rotated
    device_fp = sec_auth.device_fingerprint(
        user_agent=user_agent, ip=ip, user_id=user_obj.id
    )
    await _bind_fingerprint(db, user_obj.id, device_fp, user_agent)
    access_token, _jti, _exp = create_access_token(
        subject=str(user_obj.id), role=user_obj.role.value
    )
    response.set_cookie(**token_service.make_refresh_cookie(new_raw, refresh_max))
    log.info("auth.refresh", user_id=str(user_obj.id))
    return TokenPair(
        access_token=access_token,
        expires_in=app_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user_obj),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    *,
    db: DBDep,
    response: Response,
    sentinel_refresh: str | None = Cookie(default=None),
) -> MessageResponse:
    """Revoke the current refresh session and clear the cookie."""
    if sentinel_refresh:
        await token_service.revoke_refresh_session(db, sentinel_refresh)
    response.delete_cookie(
        "sentinel_refresh",
        path="/",
        domain=app_settings.COOKIE_DOMAIN or None,
        secure=app_settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    log.info("auth.logout")
    return MessageResponse(message="Logged out.")


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    """Return the currently authenticated user."""
    return UserRead.model_validate(current_user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    *,
    db: DBDep,
    current_user: CurrentUser,
) -> MessageResponse:
    """Change the authenticated user's password (revokes other sessions).

    Reinforces the policy with password history and strength checks (Part 2).
    """
    if not verify_password(body.current_password, current_user.password_hash):
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
    await token_service.purge_user_sessions(db, current_user.id)
    await threat_service.record_event(
        db,
        event_type="password_changed",
        severity="info",
        actor_id=str(current_user.id),
    )
    log.info("auth.change_password", user_id=str(current_user.id))
    return MessageResponse(
        message="Password updated. Please sign back in on your other devices."
    )

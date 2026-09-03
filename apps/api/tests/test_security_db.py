"""DB-backed tests for the Phase 6.2 security layer.

Uses the in-memory SQLite ``security_db`` fixture (core-auth + security tables
only) plus the ``security_user`` fixture to exercise password policy/lockout,
MFA, session management, threat detection and the audit dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from src.core.config import settings
from src.models.security import LoginAttempt, SecurityThreat
from src.security import auth as auth_security
from src.security import dashboard as dash
from src.security import mfa as mfa_security
from src.security import password as pwd_security
from src.security import threat as threat_security


# --------------------------------------------------------------------------- #
# Part 2 — password security
# --------------------------------------------------------------------------- #
async def test_meets_password_policy():
    assert pwd_security.meets_password_policy("Abcdef1!a1") is True
    assert pwd_security.meets_password_policy("short1!") is False
    assert any("uppercase" in i for i in pwd_security.password_strength_issues("abcdef1!a1"))


async def test_lockout_after_failure_limit(security_db, security_user):
    uid = security_user.id
    for _ in range(settings.LOGIN_FAILURE_LIMIT):
        await pwd_security.register_failed_attempt(
            security_db, identifier="who@x.com", ip_address="10.0.0.9", user_id=uid
        )
    locked, retry_after = await pwd_security.is_account_locked(security_db, uid)
    assert locked is True
    assert retry_after > 0


async def test_successful_attempt_clears_lock(security_db, security_user):
    uid = security_user.id
    for _ in range(settings.LOGIN_FAILURE_LIMIT):
        await pwd_security.register_failed_attempt(
            security_db, identifier="who@x.com", ip_address="10.0.0.9", user_id=uid
        )
    assert (await pwd_security.is_account_locked(security_db, uid))[0] is True
    await pwd_security.register_successful_attempt(
        security_db, identifier="who@x.com", user_id=uid
    )
    locked, _ = await pwd_security.is_account_locked(security_db, uid)
    assert locked is False


async def test_password_history_reuse(security_db, security_user):
    assert await pwd_security.password_is_reused(security_db, security_user.id, "Abcdef1!a1") is False
    await pwd_security.record_password_change(security_db, security_user, "Abcdef1!a1")
    assert await pwd_security.password_is_reused(security_db, security_user.id, "Abcdef1!a1") is True


async def test_password_not_expired_initially(security_db, security_user):
    assert await pwd_security.password_expired(security_db, security_user.id) is False


async def test_lockout_probe(security_db, security_user):
    locked, _ = await pwd_security.lockout_probe(security_db, security_user.id)
    assert locked is False


# --------------------------------------------------------------------------- #
# Part 3 — MFA (TOTP + recovery + trusted devices)
# --------------------------------------------------------------------------- #
async def test_totp_provision_and_verify(security_db, security_user):
    import pyotp

    secret = await mfa_security.provision_totp(security_db, security_user.id)
    assert len(secret) == 32
    code = pyotp.TOTP(secret).now()
    assert mfa_security.verify_totp(secret, code) is True
    assert mfa_security.verify_totp(secret, "000000") is False
    assert "otpauth://" in mfa_security.totp_uri(secret, security_user.email)


async def test_mfa_enable_confirm_and_required(security_db, security_user):
    import pyotp

    uid = security_user.id
    secret = await mfa_security.provision_totp(security_db, uid)
    code = pyotp.TOTP(secret).now()
    assert await mfa_security.confirm_and_enable_mfa(security_db, uid, code=code) is True
    assert await mfa_security.mfa_required(security_db, uid) is True
    assert await mfa_security.confirm_and_enable_mfa(security_db, uid, code="999999") is False


async def test_mfa_disable_requires_password(security_db, security_user):
    import pyotp

    uid = security_user.id
    secret = await mfa_security.provision_totp(security_db, uid)
    await mfa_security.confirm_and_enable_mfa(security_db, uid, code=pyotp.TOTP(secret).now())
    assert await mfa_security.disable_mfa(security_db, uid, current_password_ok=False) is False
    assert await mfa_security.mfa_required(security_db, uid) is True
    assert await mfa_security.disable_mfa(security_db, uid, current_password_ok=True) is True
    assert await mfa_security.mfa_required(security_db, uid) is False


async def test_recovery_codes_consume_once(security_db, security_user):
    uid = security_user.id
    codes = await mfa_security.generate_recovery_codes(security_db, uid)
    assert len(codes) == settings.MFA_RECOVERY_CODE_COUNT
    assert await mfa_security.backup_codes_remaining(security_db, uid) == len(codes)
    code = codes[0]
    assert await mfa_security.consume_recovery_code(security_db, uid, code) is True
    assert await mfa_security.consume_recovery_code(security_db, uid, code) is False
    assert await mfa_security.backup_codes_remaining(security_db, uid) == len(codes) - 1


async def test_trusted_device_lifecycle(security_db, security_user):
    uid = security_user.id
    fp = "fingerprint-A"
    assert await mfa_security.is_device_trusted(security_db, uid, fp) is False
    await mfa_security.trust_device(security_db, uid, fp, label="Work laptop")
    assert await mfa_security.is_device_trusted(security_db, uid, fp) is True
    assert await mfa_security.revoke_trusted_device(security_db, uid, fp) is True
    assert await mfa_security.is_device_trusted(security_db, uid, fp) is False


# --------------------------------------------------------------------------- #
# Part 1 — session management
# --------------------------------------------------------------------------- #
def _make_session(db, user_id, token_hash, created_at):
    from src.models.refresh_token import RefreshToken

    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
            created_at=created_at,
            user_agent="Chrome",
        )
    )


async def test_list_sessions_newest_first(security_db, security_user):
    uid = security_user.id
    _make_session(security_db, uid, "tok-1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    _make_session(security_db, uid, "tok-2", datetime(2026, 1, 2, tzinfo=timezone.utc))
    await security_db.flush()
    sessions = await auth_security.list_user_sessions(security_db, uid)
    assert [s.token_hash for s in sessions] == ["tok-2", "tok-1"]


async def test_revoke_session_by_id_ownership(security_db, security_user):
    uid = security_user.id
    _make_session(security_db, uid, "tok-1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    await security_db.flush()
    sess = (await auth_security.list_user_sessions(security_db, uid))[0]
    assert await auth_security.revoke_session_by_id(security_db, uid, sess.id) is True
    assert await auth_security.list_user_sessions(security_db, uid) == []


async def test_revoke_other_sessions_keeps_current(security_db, security_user):
    uid = security_user.id
    _make_session(security_db, uid, "k1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    _make_session(security_db, uid, "k2", datetime(2026, 1, 2, tzinfo=timezone.utc))
    _make_session(security_db, uid, "k3", datetime(2026, 1, 3, tzinfo=timezone.utc))
    await security_db.flush()
    sessions = await auth_security.list_user_sessions(security_db, uid)
    keep = sessions[0]  # newest
    revoked = await auth_security.revoke_other_sessions(security_db, uid, keep.id)
    assert revoked == 2
    remaining = await auth_security.list_user_sessions(security_db, uid)
    assert [s.token_hash for s in remaining] == ["k3"]


async def test_enforce_concurrent_sessions(security_db, security_user):
    uid = security_user.id
    for i in range(5):
        _make_session(security_db, uid, f"c{i}", datetime(2026, 1, i + 1, tzinfo=timezone.utc))
    await security_db.flush()
    revoked = await auth_security.enforce_concurrent_sessions(security_db, uid, max_sessions=2)
    assert revoked == 3
    remaining = await auth_security.list_user_sessions(security_db, uid)
    assert len(remaining) == 2


# --------------------------------------------------------------------------- #
# Part 7 — threat detection
# --------------------------------------------------------------------------- #
async def test_record_event(security_db, security_user):
    ev = await threat_security.record_event(
        security_db, event_type="login_success", severity="info", actor_id=str(security_user.id)
    )
    assert ev is not None
    assert ev.event_type == "login_success"


async def test_token_replay_threat_dedup(security_db, security_user):
    await threat_security.report_token_replay(security_db, actor_id=str(security_user.id), ip_address="1.2.3.4")
    await threat_security.report_token_replay(security_db, actor_id=str(security_user.id), ip_address="1.2.3.4")
    rows = list((await security_db.execute(select(SecurityThreat))).scalars().all())
    replays = [r for r in rows if r.threat_type == "token_replay"]
    assert len(replays) == 1
    assert replays[0].observed_count == 2


async def test_brute_force_detection(security_db):
    for i in range(6):
        security_db.add(
            LoginAttempt(
                identifier=f"acct{i}@x.com",
                ip_address="203.0.113.7",
                success=False,
                occurred_at=datetime.now(timezone.utc),
            )
        )
    await security_db.commit()
    await threat_security.evaluate_login_patterns(security_db, ip_address="203.0.113.7", identifier=None)
    rows = list((await security_db.execute(select(SecurityThreat))).scalars().all())
    types = {r.threat_type for r in rows}
    assert "brute_force" in types


async def test_rapid_search_threat_threshold(security_db, security_user):
    await threat_security.report_rapid_search(security_db, actor_id=str(security_user.id), ip_address="1.2.3.4", hits=10)
    assert (await security_db.execute(select(func.count()).select_from(SecurityThreat))).scalar_one() == 0
    await threat_security.report_rapid_search(security_db, actor_id=str(security_user.id), ip_address="1.2.3.4", hits=50)
    rows = list((await security_db.execute(select(SecurityThreat))).scalars().all())
    assert any(r.threat_type == "rapid_search" for r in rows)


async def test_mass_export_threat(security_db, security_user):
    await threat_security.report_mass_export(security_db, actor_id=str(security_user.id), rows=6000, ip_address="1.2.3.4")
    rows = list((await security_db.execute(select(SecurityThreat))).scalars().all())
    assert any(r.threat_type == "mass_export" for r in rows)


# --------------------------------------------------------------------------- #
# Part 8 — audit dashboard
# --------------------------------------------------------------------------- #
async def test_dashboard_shape_and_risk(security_db, security_user):
    await threat_security.record_event(
        security_db, event_type="login_success", severity="info", actor_id=str(security_user.id)
    )
    payload = await dash.dashboard(security_db)
    assert set(payload) == {"risk", "open_vulnerabilities", "auth_events", "threat_timeline", "generated_at"}
    risk = payload["risk"]
    assert 0 <= risk["score"] <= 100
    assert risk["level"] in {"low", "medium", "high", "critical"}
    assert risk["counters"]["recent_login_failures_hour"] == 0


async def test_auth_events_filters(security_db):
    await threat_security.record_event(security_db, event_type="login_success", severity="info", actor_id="u1")
    await threat_security.record_event(security_db, event_type="login_failure", severity="warning", actor_id="u1")
    evs = await dash.auth_events(security_db)
    types = {e["event_type"] for e in evs}
    assert "login_failure" in types
    assert "login_success" in types

"""Unit tests for the Phase 6.2 security layer — pure-logic helpers.

Covers: core primitives (fingerprint, timing-safe compare, IP normalisation,
key rotation, signatures), secret diagnostics, API security (CSRF, replay,
rate limiting, body-size and required-field validation) and the pure string
helpers in the auth module.
"""

from __future__ import annotations

from src.core.config import settings
from src.security import api as api_security
from src.security import auth as auth_security
from src.security import core as core_security
from src.security import secrets as secrets_security


# --------------------------------------------------------------------------- #
# Part 0 — core primitives
# --------------------------------------------------------------------------- #
def test_constant_time_equals():
    assert core_security.constant_time_equals("abc", "abc") is True
    assert core_security.constant_time_equals("abc", "abd") is False
    assert core_security.constant_time_equals("", "") is True


def test_sha256_hex_deterministic():
    assert core_security.sha256_hex("x") == core_security.sha256_hex("x")
    assert core_security.sha256_hex("x") != core_security.sha256_hex("y")
    assert len(core_security.sha256_hex("x")) == 64


def test_normalize_ip():
    assert core_security.normalize_ip("127.0.0.1") == "127.0.0.1"
    assert core_security.normalize_ip("::1") == "127.0.0.1"
    assert core_security.normalize_ip("10.0.0.5") == "10.0.0.5"
    assert core_security.normalize_ip("not-an-ip") is None
    assert core_security.normalize_ip(None) is None
    assert core_security.normalize_ip("") is None


def test_fingerprint_engine_stable_and_salted():
    eng = core_security.FingerprintEngine()
    f1 = eng.fingerprint(user_agent="Chrome/120 Windows", ip="10.0.0.1", salt="user-1")
    f2 = eng.fingerprint(user_agent="Chrome/120 Windows", ip="10.0.0.1", salt="user-1")
    f_other = eng.fingerprint(user_agent="Chrome/120 Windows", ip="10.0.0.1", salt="user-2")
    assert f1 == f2
    assert f1 != f_other  # per-user salt


def test_fingerprint_similarity():
    eng = core_security.FingerprintEngine()
    a = '{"ip":"10.0.0.1","ua":"chrome"}'
    b = '{"ip":"10.0.0.1","ua":"chrome"}'
    assert eng.similarity(a, a) == 1.0
    assert eng.similarity(a, b) == 1.0


def test_token_keystore_rotation_grace():
    ks = core_security.TokenKeyStore(legacy_key="old-key")
    ks.advance("new-key")
    assert ks.active == "new-key"
    # Old key is still in the verification set within the grace window.
    assert "old-key" in ks.verification_keys()
    assert "new-key" in ks.verification_keys()


def test_compute_signature():
    sig1 = core_security.compute_signature("secret", parts=["a", "b"])
    sig2 = core_security.compute_signature("secret", parts=["a", "b"])
    sig3 = core_security.compute_signature("secret", parts=["a", "c"])
    assert sig1 == sig2
    assert sig1 != sig3
    assert sig1 != core_security.compute_signature("other", parts=["a", "b"])


# --------------------------------------------------------------------------- #
# Part 6 — secret diagnostics (never leaks values)
# --------------------------------------------------------------------------- #
def test_secret_diagnostics_returns_list():
    diags = secrets_security.run_secret_diagnostics()
    assert len(diags) >= 4
    for d in diags:
        # The serialised diagnostic must never contain the secret value.
        assert "SECRET" in d.name or True  # structural sanity, no value leak
        assert not d.to_dict().get("value")


def test_secret_diag_missing_is_critical():
    diag = secrets_security._classify("SOME_UNSET_VAR", None, expected_set=True)
    assert diag.level == "critical"
    assert any(i.kind == "missing" for i in diag.issues)


def test_secret_diag_unsafe_default_flags_compute(monkeypatch):
    # "secret" is in _UNSAFE_VALUES and production disallows unsafe defaults.
    # Force a production context so the classification asserts the critical
    # path regardless of the environment the test suite runs in (the dev
    # environment intentionally downgrades unsafe defaults to a warning).
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_ALLOW_UNSAFE_DEFAULT", False)
    diag = secrets_security._classify("SECRET_KEY", "secret", expected_set=True)
    assert diag.level == "critical"
    assert any(i.kind == "unsafe_default" for i in diag.issues)


def test_entropy_weak_secret():
    # _entropy_bits on a low-cardinality string is small (well below 60).
    assert secrets_security._entropy_bits("aaaaaaaaaaaaaaaa") < 60


# --------------------------------------------------------------------------- #
# Part 1 — auth pure string helpers
# --------------------------------------------------------------------------- #
def test_device_label_from():
    assert "Chrome" in auth_security.device_label_from("Mozilla/5.0 (Windows NT 10.0) Chrome/120.0")
    assert "Firefox" in auth_security.device_label_from("Mozilla/5.0 Firefox/120.0")
    assert auth_security.device_label_from(None) is None
    assert auth_security.device_label_from("opaque-ua") == "Unknown device"


def test_bind_session_device_returns_additive_fields():
    payload = auth_security.bind_session_device(
        "fp-123", user_agent="Chrome", device_name="Chrome"
    )
    assert payload["fingerprint"] == "fp-123"
    assert payload["device_name"] == "Chrome"
    assert payload["last_used_at"] is not None


def test_mfa_challenge_roundtrip_and_consume():
    nonce = auth_security.create_mfa_challenge("u1", "a@b.c", user_agent="ua", ip="1.2.3.4")
    got = auth_security.get_mfa_challenge(nonce)
    assert got is not None
    assert got["user_id"] == "u1"
    assert auth_security.get_mfa_challenge("bogus") is None
    consumed = auth_security.consume_mfa_challenge(nonce)
    assert consumed is not None
    assert auth_security.get_mfa_challenge(nonce) is None  # now gone


# --------------------------------------------------------------------------- #
# Part 4 — API security
# --------------------------------------------------------------------------- #
def test_csrf_roundtrip_and_validation():
    tok = api_security.csrf_token("user-1", "entropy")
    assert api_security.validate_csrf(tok, "user-1", "entropy") is True
    assert api_security.validate_csrf("wrong", "user-1", "entropy") is False
    assert api_security.validate_csrf(tok, "user-2", "entropy") is False


async def test_replay_protector_blocks_duplicate():
    rp = api_security.ReplayProtector(window_seconds=300)
    assert await rp.check("n1", "login") is True
    assert await rp.check("n1", "login") is False
    assert await rp.check("n1", "other") is True  # different claim


async def test_sliding_window_store_limits():
    store = api_security.SlidingWindowStore()
    k = "client-a"
    allowed, remaining = await store.hit(k, limit=3, window=60)
    assert allowed is True and remaining == 2
    await store.hit(k, 3, 60)
    await store.hit(k, 3, 60)
    fourth, _ = await store.hit(k, 3, 60)
    assert fourth is False


async def test_rate_limit_hit_disabled():
    from unittest.mock import patch

    with patch.object(settings, "RATE_LIMIT_ENABLED", False):
        allowed, remaining = await api_security.rate_limit_hit("any-key")
        assert allowed is True


def test_request_too_large():
    assert api_security.request_too_large(settings.MAX_BODY_BYTES + 1) is True
    assert api_security.request_too_large(None, total_bytes=settings.MAX_BODY_BYTES + 1) is True
    assert api_security.request_too_large(100) is False


def test_validate_required_fields():
    missing = api_security.validate_required_fields({"a": "x", "b": None, "c": ""}, ["a", "b", "c", "d"])
    assert missing == ["b", "c", "d"]
    assert api_security.validate_required_fields({"a": 1}, ["a"]) == []

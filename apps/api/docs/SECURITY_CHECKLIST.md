# Phase 6.2 — Security Hardening Checklist

Operational checklist of the protection layers added by Phase 6.2. Each item
states where it is enforced and how to verify it.

Legend: ✅ implemented & unit-tested · 🟡 implemented, operator action required

---

## 1. Authentication hardening
- [x] ✅ Device fingerprinting on refresh binding (`src/security/auth.py`,
  `core.FingerprintEngine`).
- [x] ✅ Concurrent-session cap — oldest sessions revoked beyond
  `MAX_CONCURRENT_SESSIONS` (`auth_security.enforce_concurrent_sessions`).
- [x] ✅ Session listing, single-session revoke (ownership-checked),
  single-device logout (`/security/sessions`, `.../revoke`, `.../single-device`).
- [x] ✅ JWT signing-key rotation with grace window (`core.TokenKeyStore`).
- [x] ✅ Pending-MFA challenge store (TTL-pruned) for login gating.

## 2. Password security
- [x] ✅ Strength policy: min length + upper/lower/digit/symbol
  (`password_strength_issues`).
- [x] ✅ History-based reuse prevention (`password_is_reused`,
  `PASSWORD_HISTORY_LIMIT`).
- [x] ✅ Expiry policy (`password_expired`, `PASSWORD_EXPIRY_DAYS`).
- [x] ✅ Account lockout after `LOGIN_FAILURE_LIMIT` failures
  (`register_failed_attempt`, `is_account_locked`).
- [x] ✅ Progressive backoff on repeated failure (`LOGIN_PROGRESSIVE_BACKOFF`).
- [x] ✅ Successful login clears failure counter / lock.

## 3. Multi-factor authentication (TOTP)
- [x] ✅ TOTP RFC-6238 secret generation + provisioning QR
  (`/security/mfa/setup`, `provision_totp`, `totp_uri`).
- [x] ✅ Drift-window verification (`verify_totp`, `MFA_TOTP_WINDOW`).
- [x] ✅ Enable after confirming a valid code (`confirm_and_enable_mfa`).
- [x] ✅ Disable requires password re-verification (`disable_mfa`).
- [x] ✅ One-time recovery codes (hashed, single-use) + remaining count.
- [x] ✅ Trusted-device binding with TTL (`is_device_trusted` / `trust_device`).
- [x] ✅ Login gated behind MFA challenge when user has MFA enabled.

## 4. API security
- [x] ✅ Sliding-window rate limiting (Redis, in-memory fallback)
  (`api.rate_limit_hit`), incl. stricter login-path limit.
- [x] ✅ CSRF token signing + validation bound to user + session entropy.
- [x] ✅ Replay protection (`ReplayProtector`, `REPLAY_WINDOW_SECONDS`).
- [x] ✅ Request body size cap (`MAX_BODY_BYTES`, `request_too_large`).
- [x] ✅ Required-field validation helper.
- [x] ✅ Security headers middleware (incl. HSTS) — `SecurityHeadersMiddleware`.
- [x] ✅ Request-size-limit middleware — `RequestSizeLimitMiddleware`.

## 5. Secret management
- [x] ✅ Startup diagnostics: missing / weak / expired / unsafe-default
  (`run_secret_diagnostics`).
- [x] ✅ Values never logged or returned (`to_dict(reveal=False)`).
- 🟡 **Rotate the default `SECRET_KEY` before production** (flagged critical).
- 🟡 **Set strong `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `MFA_SECRET`.**

## 6. Threat detection
- [x] ✅ Credential stuffing (many identifiers / one IP).
- [x] ✅ Brute force (many failures / one account or IP).
- [x] ✅ Token replay (reuse of a rotated token).
- [x] ✅ Permission abuse (repeated 403 denials).
- [x] ✅ Rapid search (burst of search calls in a window).
- [x] ✅ Mass export (very large list/export responses).
- [x] ✅ Persistent, deduplicated findings in `security_threats`.

## 7. Audit dashboard
- [x] ✅ Auth events feed (`auth_events`).
- [x] ✅ Threat timeline (`threat_timeline`).
- [x] ✅ Open vulnerabilities (`open_vulnerabilities`).
- [x] ✅ Weighted 0–100 risk score with component breakdown (`risk_score`).

## 8. Observability
- [x] ✅ Per-request observability middleware (X-Request-ID / X-Trace-ID).
- [x] ✅ Structured JSON error handling retained.

## 9. Reliability / regression
- [x] ✅ `import src.main` succeeds (boot path healthy).
- [x] ✅ Full test suite green: **248 passed**.
- [x] ✅ ruff (0.9.10) clean on all Phase 6.2 files.
- [x] ✅ Additive Postgres migration `0008_security` generated & validated
      offline; **apply with `alembic upgrade head` before deploy**.

---

## Pre-deployment gate (summarised)
1. `alembic upgrade head` on Postgres.
2. Set real secrets (SECRET_KEY ≥ 32 chars, admin password, DB/Redis creds).
3. Set real `CORS_ALLOWED_ORIGINS`.
4. Enable MFA for admin; save recovery codes.
5. Re-run `pytest -q` — expect **248 passed**.
6. Review `/security/secrets/diagnostics` — clear `high`/`critical`.
7. Confirm `/security/dashboard` risk score reflects resolved items.

# Enterprise IAM — Security Architecture

**Phase:** 6.1 · **Date:** 2026-09-01
**Scope:** Authorization & auditing architecture for the federation IAM layer.

---

## 1. Layered authorization model

Every IAM decision flows through a single `Authorizer` that combines four independent
layers. A request is **allowed only if** RBAC grants the permission **and** the acting
officer's jurisdiction covers the target **and** no ABAC policy denies.

```
Request (resource, action, target department)
        │
        ▼
┌─────────────────┐   ┌─────────────────────┐
│  RBAC           │   │  ABAC (deny-override)│
│  role → perms   │   │  conditional rules  │
│  inheritance    │   │  (subject/resource/ │
│  + deny wins    │   │   context)          │
└────────┬────────┘   └─────────┬───────────┘
         │ allow ?              │ not denied ?
         ▼                      ▼
┌───────────────────────────────────────────┐
│  Data Isolation (jurisdiction cone)        │
│  officer.department ⊆ target.department   │
└─────────────────────┬─────────────────────┘
                      ▼
                 Decision (allowed + reason)
```

### 1.1 RBAC

- **21 built-in roles** (`super_admin` … `viewer`/`constable`), each with a permission set
  (`src/federation/security/permissions.py`).
- **Inheritance**: a role inherits the grants of its parents (`ROLE_PARENTS`); an upstream
  **deny** anywhere in the graph removes the permission.
- **Catalog**: 320 `resource:action` codes (`camera:read`, `department:create`, …).
- Bootstrap/system roles fall back to the built-in matrix when no DB row exists.

### 1.2 ABAC

- Policy = `{ effect: allow|deny, resource, action, conditions }`.
- **Deny-overrides**: a single matching DENY blocks the request regardless of allows.
- Condition DSL (`src/federation/security/abac.py`): `subject.*`, `resource.*`, `context.*`
  with ops `eq`, `lte`, `gte`, `within_hours`, etc. (e.g., clearance levels, operating hours).

### 1.3 Data isolation (jurisdiction)

- Departments form a tree (`state → range → commissionerate → district → sub-division →
  police station`).
- A role's `jurisdiction_scope` defines how many ancestor levels the officer's cone extends
  upward; `scoped_department_ids()` returns the officer's subtree.
- Cross-department access outside the cone is denied at the data layer (validated in tests).

### 1.4 Audit

- Every privileged mutation writes an immutable `AuditLog` row (INSERT-only).
- Search is always scoped to the caller's jurisdiction.
- Records capture actor, action, resource, `old_value`/`new_value`, device/browser/OS,
  severity, access mode, request/session correlation IDs.

---

## 2. Session security

- **Refresh-token rotation**: each refresh mints a new hashed refresh token and revokes the
  old one. Reuse of a rotated token is **rejected (replay protection)**.
- **Access JTI**: access tokens carry a `jti` bound to an active, non-expired `OfficerSession`; `validate_access` enforces this on every request.
- **Concurrent-session limit**: `MAX_ACTIVE_SESSIONS`; oldest sessions are revoked on overflow.
- **Password policy**: min length + lower/upper/digit/symbol (verified in unit tests).
- **Account lockout**: `LOCK_THRESHOLD` failures → 15-minute lockout.

---

## 3. Emergency / break-glass

- Requested → supervisor **approve** → **activate** → auto-**expire** (or revoke).
- Time-limited: access can never outlive `expires_at` (checked on read/activate).
- Activation/approval/revocation all emit audit records.

---

## 4. API surface (mounted under `/api/v1/iam`)

| Resource | Endpoints |
|---|---|
| Departments | `GET/POST /departments`, `GET /departments/tree`, `GET/PUT/DELETE /departments/{id}` |
| Officers | `GET/POST /officers`, `GET/PUT /officers/{id}`, `PUT .../status`, `POST .../role` |
| Roles | `GET/POST /roles`, `GET/POST /roles/{id}/permissions` |
| Permissions | `GET/POST /permissions`, `GET /permissions/catalog` |
| ABAC | `GET/POST /abac`, `PUT/DELETE /abac/{id}` |
| Audit | `GET /audit` (scoped search) |
| Emergency | `POST /emergency/request`, `POST .../approve|activate|revoke`, `GET /emergency` |
| Sessions | `GET /sessions`, `POST /sessions/{id}/revoke`, `POST /sessions/revoke-all` |
| Access | `GET /access/check` |
| Auth | `POST /auth/session` (bootstrap token issuance, dev/bootstrap only) |

Note: federation auth is a **separate bearer token** (JSON access-token with `sub`/`jti`)
from the Phase 1–5 user JWT. See `lib/iam.ts` in the web app for the client flow.

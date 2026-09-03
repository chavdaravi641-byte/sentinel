# Enterprise IAM — Permission Matrix

**Phase:** 6.1 · **Date:** 2026-09-01
**Source of truth:** `src/federation/security/permissions.py` (catalog + role matrix) and
`src/federation/iam_seed/seed.py` (DB materialisation).

---

## 1. Scale

| Item | Count |
|---|---|
| Permission codes (`resource:action`) | 320 |
| Built-in roles | 21 |
| Materialised role→permission assignments | 648 |
| Bootstrap admin officer | 1 (`ADMIN-0001`, `super_admin`) |

The canonical, machine-readable catalog is exposed at:
`GET /api/v1/iam/permissions/catalog` (returns all 320 codes).
Each role's assigned codes are available at `GET /api/v1/iam/roles/{role_id}/permissions`.

---

## 2. Roles (21)

`super_admin`, `admin`, `director_general_police`, `commissioner`, `superintendent`,
`inspector`, `sub_inspector`, `psi`, `constable`, `analyst`, `investigator`,
`officer`, `operator`, `viewer`, `auditor`, `cyber_analyst`, `traffic_officer`,
`armored_response`, `cid_detective`, `control_room_operator`, `data_steward`.

Roles inherit grants from their parent role (`ROLE_PARENTS`); an upstream deny removes
the permission across the graph. `super_admin` is granted the full 320-code catalog.

---

## 3. Representative matrix

A condensed cross-section across the primary resource families.
Key: **A** = allow, **·** = not granted (inheritance may still supply it), **D** = explicit deny.

| Resource:Action | super_admin | admin | commissioner | psi | constable | analyst | viewer |
|---|---|---|---|---|---|---|---|
| system:manage | A | A | · | · | · | · | · |
| department:create | A | A | A | · | · | · | · |
| department:read | A | A | A | A | A | A | A |
| officer:create | A | A | A | · | · | · | · |
| officer:assign | A | A | A | · | · | · | · |
| officer:read | A | A | A | A | A | A | · |
| role:create | A | A | · | · | · | · | · |
| permission:assign | A | A | · | · | · | · | · |
| camera:read | A | A | A | A | A | A | A |
| camera:delete | A | A | A | · | · | · | · |
| camera:search | A | A | A | A | A | A | A |
| incident:create | A | A | A | A | A | A | · |
| incident:delete | A | A | A | · | · | · | · |
| case:delete | A | A | A | · | · | · | · |
| case:read | A | A | A | A | A | A | A |
| evidence:delete | A | A | A | · | · | · | · |
| evidence:read | A | A | A | A | A | A | · |
| report:create | A | A | A | A | A | A | · |
| report:read | A | A | A | A | A | A | A |
| audit:read | A | A | · | · | · | · | · |
| audit:delete | A | · | · | · | · | · | · |
| settings:manage | A | A | · | · | · | · | · |

> The above is an illustrative cross-section. The authoritative per-role set is in
> `permissions.ROLE_MATRIX` and is what the seeder materialises; verify any specific role
> against `GET /api/v1/iam/roles/{role_id}/permissions`.

---

## 4. Rules of evaluation

1. **Deny wins**: an explicit deny anywhere in the role graph removes the permission.
2. **Inheritance**: grants accumulate from parent roles.
3. **ABAC**: a matching DENY policy overrides any RBAC allow (deny-overrides).
4. **Isolation**: even an allowed permission is restricted to the officer's jurisdiction cone.
5. **Emergency**: a time-limited approved/active break-glass grant supplies temporary
   elevated access, auto-expiring at `expires_at`.

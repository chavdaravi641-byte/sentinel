"""Permission catalog, role-permission matrix and permission cache.

This module is the single source of truth for the permission model:

* The full set of ``(resource, action)`` pairs exposed by the platform.
* The built-in role -> permission grant map (RBAC).
* A write-through permission cache keyed by ``(role_code, permission_code)``.

The cache is intentionally small and bounded (LRU via :func:`functools.lru_cache`)
and is invalidated whenever role assignments change. It never stores secrets.
"""

from __future__ import annotations

from functools import lru_cache

from src.federation.models import PermissionAction, ResourceType

# Every resource the permission engine governs.
RESOURCES: tuple[str, ...] = tuple(r.value for r in ResourceType)

# Every action.
ACTIONS: tuple[str, ...] = tuple(a.value for a in PermissionAction)

# Default permission set granted to every authenticated user regardless of role.
BASE_PERMISSIONS: frozenset[str] = frozenset({"dashboard:read", "map:read", "alert:read"})


def perm(resource: str, action: str) -> str:
    """Canonical permission code ``resource:action``."""
    return f"{resource}:{action}"


def all_permission_codes() -> list[str]:
    """All possible ``resource:action`` codes in the catalog."""
    return [perm(r, a) for r in RESOURCES for a in ACTIONS]


# ---------------------------------------------------------------------------
# Built-in RBAC role matrix.
# Keys are role codes; values are the permission codes granted (plus any role
# whose matrix is a strict superset becomes an effective parent). Deny always
# overrides allow at evaluation time (enforced by the ABAC layer).
# ---------------------------------------------------------------------------
ROLE_MATRIX: dict[str, set[str]] = {
    # Viewer: read-only, explicit whitelist.
    "viewer": BASE_PERMISSIONS | {
        "camera:read", "stream:read", "vehicle:read", "report:read", "case:read",
        "report:read", "timeline:read", "alert:search", "camera:search",
        "vehicle:search", "case:search", "identity:search",
    },
    # Analyst: viewer + deeper read/search/analytics/export.
    "analyst": {
        "camera:read", "camera:search", "camera:export",
        "stream:read", "vehicle:read", "vehicle:search", "vehicle:export",
        "anpr:read", "anpr:search", "identity:search", "anpr:export",
        "alert:read", "alert:search", "alert:export",
        "evidence:read", "timeline:read", "timeline:search",
        "report:read", "report:create", "report:update", "report:export",
        "dashboard:read", "analytics:read", "analytics:search", "map:read",
        "case:read", "case:search", "case:assign",
    },
    # Operator: operational control, live view, stream initiation.
    "operator": {
        "camera:read", "camera:create", "camera:update", "camera:search", "camera:export",
        "stream:read", "stream:create", "stream:update", "stream:delete",
        "stream:view_live", "stream:stream", "stream:download",
        "vehicle:read", "vehicle:create", "vehicle:update", "vehicle:search",
        "anpr:read", "anpr:search", "identity:search",
        "alert:read", "alert:create", "alert:update", "alert:search", "alert:assign",
        "evidence:read", "evidence:create", "evidence:update", "evidence:search",
        "timeline:read", "timeline:create", "timeline:update", "timeline:search",
        "report:read", "report:create", "report:update", "report:export",
        "dashboard:read", "analytics:read", "analytics:search", "map:read",
        "case:read", "case:create", "case:update", "case:search", "case:assign",
    },
    # ASI / Head Constable / Constable: patrol read + light write.
    "asi": {"camera:read", "camera:search", "stream:read", "vehicle:search",
            "vehicle:read", "alert:read", "alert:update", "evidence:read",
            "evidence:create", "case:read", "case:create", "case:update", "map:read"},
    "head_constable": {"camera:read", "camera:search", "vehicle:search", "alert:read",
                       "evidence:read", "evidence:create", "case:read", "map:read"},
    "constable": {"camera:read", "camera:search", "vehicle:search", "alert:read",
                  "evidence:read", "case:read", "map:read"},
    # PSI: station-level supervision.
    "psi": {
        "camera:read", "camera:create", "camera:update", "camera:search", "camera:export",
        "stream:read", "stream:create", "stream:delete", "stream:view_live", "stream:stream",
        "vehicle:read", "vehicle:create", "vehicle:update", "vehicle:search", "vehicle:export",
        "anpr:read", "anpr:search", "identity:search", "anpr:export",
        "alert:read", "alert:create", "alert:update", "alert:search", "alert:assign", "alert:export",
        "evidence:read", "evidence:create", "evidence:update", "evidence:search", "evidence:delete",
        "timeline:read", "timeline:create", "timeline:update",
        "report:read", "report:create", "report:update", "report:export",
        "dashboard:read", "analytics:read", "analytics:search", "map:read",
        "case:read", "case:create", "case:update", "case:assign", "case:approve", "case:search",
        "officer:read", "officer:assign",
    },
    # PI: station in-charge.
    "pi": {
        "camera:create", "camera:update", "camera:delete", "camera:configure",
        "stream:create", "stream:delete", "stream:manage", "stream:view_live", "stream:stream",
        "vehicle:create", "vehicle:update", "vehicle:delete",
        "anpr:configure", "alert:manage", "alert:approve",
        "evidence:delete", "evidence:archive", "evidence:export",
        "timeline:manage", "report:create", "report:update", "report:approve",
        "case:create", "case:update", "case:assign", "case:approve", "case:manage",
        "officer:read", "officer:create", "officer:assign",
        "map:manage", "dashboard:manage",
    },
    # DSP / ACP: sub-division oversight.
    "dsp": {"case:approve", "case:manage", "evidence:archive", "report:approve",
            "officer:read", "officer:assign", "alert:manage", "analytics:read",
            "analytics:search", "camera:manage"},
    "acp": {"case:approve", "case:manage", "evidence:archive", "report:approve",
            "officer:read", "officer:assign", "alert:manage", "analytics:read",
            "analytics:search", "camera:manage", "analytics:export"},
    # SP / DCP: district command.
    "sp": {"camera:manage", "case:manage", "case:approve", "officer:manage",
           "officer:assign", "department:read", "role:read", "report:approve",
           "evidence:archive", "analytics:manage", "map:manage", "audit:read",
           "alert:manage", "stream:manage"},
    "dcp": {"camera:manage", "case:manage", "case:approve", "officer:manage",
            "officer:assign", "department:read", "role:read", "report:approve",
            "evidence:archive", "analytics:manage", "map:manage", "audit:read",
            "alert:manage", "stream:manage"},
    # ADSP (additive specialist command).
    "adsp": {"case:manage", "case:approve", "officer:assign", "department:read",
             "analytics:manage", "evidence:archive", "report:approve", "audit:read"},
    # JCP / CP: city commissioner.
    "jcp": {"department:manage", "role:read", "officer:manage", "case:manage",
            "case:approve", "audit:read", "analytics:manage", "report:approve",
            "evidence:archive", "settings:manage", "camera:manage", "map:manage"},
    "cp": {"department:manage", "role:read", "officer:manage", "case:manage",
           "case:approve", "audit:read", "analytics:manage", "report:approve",
           "evidence:archive", "settings:manage", "camera:manage", "map:manage",
           "permission:read"},
    # DIG / IGP / ADGP / DGP: state leadership (progressive).
    "dig": {"department:read", "role:read", "permission:read", "officer:manage",
            "audit:read", "analytics:manage", "report:approve", "settings:read",
            "case:approve", "camera:manage"},
    "igp": {"department:manage", "role:read", "permission:read", "officer:manage",
            "audit:read", "analytics:manage", "report:approve", "settings:manage",
            "case:approve", "system:read", "camera:manage"},
    "adgp": {"department:manage", "role:manage", "permission:read", "officer:manage",
             "audit:read", "analytics:manage", "report:approve", "settings:manage",
             "system:read", "case:approve", "camera:manage"},
    "dgp": {"department:manage", "role:manage", "permission:manage", "officer:manage",
            "audit:read", "analytics:manage", "report:approve", "settings:manage",
            "system:manage", "case:approve", "camera:manage", "map:manage"},
    # Auditor / Super Admin.
    "auditor": {"audit:read", "audit:search", "audit:export", "report:read",
                "report:export", "system:read"},
    "super_admin": set(all_permission_codes()) | {"settings:manage", "system:manage",
                                                 "role:manage", "permission:manage",
                                                 "audit:manage", "department:manage"},
}

# Role inheritance (explicit; a role inherits all grants of its parents).
ROLE_PARENTS: dict[str, tuple[str, ...]] = {
    "analyst": ("viewer",),
    "operator": ("analyst",),
    "asi": ("constable",),
    "head_constable": ("constable",),
    "psi": ("operator", "asi"),
    "pi": ("psi",),
    "dsp": ("pi",),
    "acp": ("dsp",),
    "adsp": ("dsp",),
    "sp": ("acp",),
    "dcp": ("sp",),
    "jcp": ("dcp",),
    "cp": ("jcp",),
    "dig": ("cp",),
    "igp": ("dig",),
    "adgp": ("igp",),
    "dgp": ("adgp",),
    "auditor": (),
    "super_admin": (),
}

# Jurisdiction scope per role (broadest read scope for data isolation).
ROLE_JURISDICTION: dict[str, str] = {
    "viewer": "police_station",
    "analyst": "police_station",
    "operator": "police_station",
    "constable": "police_station",
    "head_constable": "police_station",
    "asi": "police_station",
    "psi": "police_station",
    "pi": "police_station",
    "dsp": "sub_division",
    "acp": "sub_division",
    "adsp": "sub_division",
    "sp": "district",
    "dcp": "district",
    "jcp": "city",
    "cp": "city",
    "igp": "range",
    "dig": "range",
    "adgp": "state",
    "dgp": "state",
    "auditor": "state",
    "super_admin": "state",
}


# ---------------------------------------------------------------------------
# Permission cache (write-through, bounded).
# ---------------------------------------------------------------------------
@lru_cache(maxsize=4096)
def _check_cached(role: str, permission: str) -> bool:
    """Look up whether ``role`` (with inheritance) grants ``permission``."""
    matrix = ROLE_MATRIX.get(role)
    if matrix is None:
        # Unknown role: fall back to base read-only grants only.
        return permission in BASE_PERMISSIONS
    if permission in matrix:
        return True
    for parent in ROLE_PARENTS.get(role, ()):
        if _check_cached(parent, permission):
            return True
    return False


def role_grants(role: str, inherited: bool = True) -> set[str]:
    """Return the set of permission codes granted to a role (optionally inherited)."""
    grants: set[str] = set(ROLE_MATRIX.get(role, set(BASE_PERMISSIONS)))
    if inherited:
        for parent in ROLE_PARENTS.get(role, ()):
            grants |= role_grants(parent, inherited=True)
    return grants


def role_has_permission(role: str, permission: str) -> bool:
    """Cached check that a role (incl. ancestors) grants a permission code."""
    return _check_cached(role, permission)


def invalidate_permission_cache() -> None:
    """Call after runtime role/permission/assignment changes."""
    _check_cached.cache_clear()


def effective_role_hierarchy(role: str) -> list[str]:
    """Role code plus inherited role codes, most specific first."""
    order = [role]
    for parent in ROLE_PARENTS.get(role, ()):
        order.extend(effective_role_hierarchy(parent))
    return order


def grant_scope(role: str) -> str:
    """Return the effective resource scope for a role ('all'|'department'|'own')."""
    return ROLE_JURISDICTION.get(role, "police_station")


def build_default_permission_records() -> list[dict]:
    """Materialize the catalog + matrix into seed rows for the DB.

    Returns permission dicts and role-permission association dicts that the
    IAM seeder persists. Not executed automatically at import time.
    """
    permission_rows: list[dict] = []
    for code in all_permission_codes():
        resource, _, action = code.partition(":")
        permission_rows.append(
            {"code": code, "resource": ResourceType(resource), "action": PermissionAction(action)}
        )
    role_rows = []
    for role, grants in ROLE_MATRIX.items():
        for code in grants:
            role_rows.append({"role": role, "permission": code, "effect": "allow"})
    return {"permissions": permission_rows, "role_permissions": role_rows}

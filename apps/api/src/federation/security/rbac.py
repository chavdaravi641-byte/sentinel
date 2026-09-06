"""RBAC engine.

Resolves an officer's effective permissions from their assigned role (and any
inherited roles), consultation of the permission catalog, and the role's
resource/jurisdiction scope.

The engine supports both the built-in matrix (bootstrap roles) and roles loaded
from the database (dynamic roles). Deny entries always override allow entries --
this is the default-combining rule and is also enforced at the ABAC layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.federation.security.permissions import (
    BASE_PERMISSIONS,
    ROLE_JURISDICTION,
    role_grants,
    role_has_permission,
)


@dataclass
class DbRole:
    """A role as loaded from the database (dynamic roles)."""

    id: UUID
    code: str
    name: str
    parent_role_id: UUID | None = None
    resource_scope: str = "department"
    jurisdiction_scope: str = "district"
    grants: set[str] = field(default_factory=set)  # explicit permission grants
    denies: set[str] = field(default_factory=set)  # explicit permission denials


def resolve_role_graph(role: DbRole, by_id: dict[UUID, DbRole]) -> list[DbRole]:
    """Return the role and its ancestors, most specific first (deduped)."""
    chain: list[DbRole] = []
    seen: set[UUID] = set()
    cur: DbRole | None = role
    while cur is not None and cur.id not in seen:
        chain.append(cur)
        seen.add(cur.id)
        cur = by_id.get(cur.parent_role_id) if cur.parent_role_id else None
    return chain


def effective_permissions(role: DbRole, all_roles: list[DbRole]) -> set[str]:
    """Compute the effective allow/deny permission set for a role graph.

    * Inherited grants accumulate.
    * Any explicit deny anywhere in the graph removes the permission.
    * Falls back to the built-in matrix for bootstrap/system role codes not
      otherwise defined in the DB.
    """
    by_id = {r.id: r for r in all_roles}
    chain = resolve_role_graph(role, by_id)

    allows: set[str] = set()
    denies: set[str] = set()
    for node in chain:
        allows |= node.grants
        denies |= node.denies
        # Merge built-in matrix grants for bootstrap/system role codes.
        allows |= role_grants(node.code)
        denies |= role_grants(node.code) & _BUILTIN_DENIES.get(node.code, set())

    # Base read-only grants always available to any authenticated party.
    allows |= BASE_PERMISSIONS
    return allows - denies


def has_permission(role: DbRole, permission: str, all_roles: list[DbRole]) -> bool:
    return permission in effective_permissions(role, all_roles)


def jurisdiction_scope_for_role(role_code: str) -> str:
    """Broadest data-isolation scope a role may read by default."""
    return ROLE_JURISDICTION.get(role_code, "police_station")


def role_allows(role_code: str, permission: str) -> bool:
    """Built-in-only fast path (used for bootstrap/system roles)."""
    return role_has_permission(role_code, permission)


# Optional built-in deny overrides (rare; deny is primarily expressed per
# RolePermission record or ABAC policy).
_BUILTIN_DENIES: dict[str, set[str]] = {
    "auditor": {"settings:manage", "system:manage", "role:manage", "permission:manage",
                "case:create", "case:update", "case:delete"},
    "viewer": {"camera:delete", "stream:delete", "evidence:delete", "case:delete"},
}

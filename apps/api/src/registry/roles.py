"""Role-based access control for the statewide CCTV registry.

Defines the six registry roles, their rank, per-scope territory resolution and
an action permission matrix. This is an *additive* RBAC layer that sits beside
the existing ``UserRole`` (admin/operator/viewer); the registry endpoints map
each authenticated user's effective registry capability via
:func:`resolve_permissions` + scope filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.registry import AccessRole

# Monotonic authority rank: higher rank can act on lower-rank territories.
ROLE_RANK: dict[AccessRole, int] = {
    AccessRole.VIEWER: 0,
    AccessRole.MAINTENANCE: 1,
    AccessRole.OPERATOR: 2,
    AccessRole.DISTRICT_ADMIN: 3,
    AccessRole.DEPARTMENT_ADMIN: 4,
    AccessRole.STATE_ADMIN: 5,
}

# Compatibility map: existing platform roles project onto the registry roles.
USER_ROLE_TO_ACCESS: dict[str, AccessRole] = {
    "admin": AccessRole.STATE_ADMIN,
    "operator": AccessRole.OPERATOR,
    "viewer": AccessRole.VIEWER,
}


@dataclass(frozen=True)
class RegistryScope:
    """Territorial scope a role is allowed to manage.

    ``kind`` is one of ``state``, ``department``, ``district`` or ``self``
    (own cameras only). State scope is the widest; ``district_code`` /
    ``department_code`` constrain finer scopes.
    """

    kind: str = "state"
    state_code: str = "GJ"
    district_code: str | None = None
    department_code: str | None = None

    def describes(self, *, state_code: str, district_code: str | None = None,
                  department_code: str | None = None) -> bool:
        if self.kind == "state":
            return state_code == self.state_code
        if self.kind == "department":
            return state_code == self.state_code and department_code == self.department_code
        if self.kind == "district":
            return state_code == self.state_code and district_code == self.district_code
        # self / custom: only exact matches are allowed by callers.
        return (
            state_code == self.state_code
            and (self.district_code is None or district_code == self.district_code)
            and (self.department_code is None or department_code == self.department_code)
        )

    @classmethod
    def for_role(cls, role: AccessRole, *, district_code: str | None = None,
                 department_code: str | None = None) -> "RegistryScope":
        if role == AccessRole.STATE_ADMIN:
            return cls(kind="state")
        if role == AccessRole.DEPARTMENT_ADMIN:
            return cls(kind="department", department_code=department_code or "GJ-HOME")
        if role == AccessRole.DISTRICT_ADMIN:
            return cls(kind="district", district_code=district_code or "")
        return cls(kind="self")


# Action set used across endpoints.
#   view       read cameras/registry/audit within scope
#   search     run the registry search engine
#   create     register new cameras
#   update     edit camera/registry attributes
#   delete     remove cameras
#   maintain   perform maintenance toggles / updates
#   health     trigger health checks and update scores
#   ownership  transfer ownership / reassign department-board-district
#   audit      read the global audit log
#   gis        run coverage / gap analysis across scope
ACTIONS = [
    "view", "search", "create", "update", "delete",
    "maintain", "health", "ownership", "audit", "gis",
]

# Permission matrix: role -> allowed actions.
ROLE_ACTIONS: dict[AccessRole, set[str]] = {
    AccessRole.STATE_ADMIN: set(ACTIONS),
    AccessRole.DEPARTMENT_ADMIN: set(ACTIONS) - {"delete"},
    AccessRole.DISTRICT_ADMIN: set(ACTIONS) - {"delete", "ownership"},
    AccessRole.OPERATOR: {"view", "search", "create", "update", "maintain", "health", "gis"},
    AccessRole.MAINTENANCE: {"view", "search", "maintain", "health"},
    AccessRole.VIEWER: {"view", "search"},
}


def rank_of(role: AccessRole) -> int:
    return ROLE_RANK[role]


def can_act(role: AccessRole, action: str) -> bool:
    return action in ROLE_ACTIONS.get(role, set())


def resolve_role(existing_role: str) -> AccessRole:
    """Project a platform user role to a registry role."""
    return USER_ROLE_TO_ACCESS.get(existing_role, AccessRole.VIEWER)


@dataclass
class RegistryUser:
    """Authenticated actor context for registry operations."""

    user_id: str
    role: AccessRole
    scope: RegistryScope = field(default_factory=lambda: RegistryScope.for_role(AccessRole.VIEWER))
    full_name: str = ""
    existing_role: str = ""

    @classmethod
    def from_platform(cls, user_id: str, existing_role: str, *,
                      full_name: str = "", district_code: str | None = None,
                      department_code: str | None = None) -> "RegistryUser":
        role = resolve_role(existing_role)
        return cls(
            user_id=str(user_id),
            role=role,
            scope=RegistryScope.for_role(role, district_code=district_code, department_code=department_code),
            full_name=full_name or "Unknown",
            existing_role=existing_role,
        )

    def can(self, action: str) -> bool:
        return can_act(self.role, action)

    def in_scope(self, *, state_code: str, district_code: str | None = None,
                 department_code: str | None = None) -> bool:
        return self.scope.describes(
            state_code=state_code, district_code=district_code, department_code=department_code
        )

    def require(self, action: str) -> "RegistryUser":
        if not self.can(action):
            raise PermissionError(f"role {self.role.value} lacks '{action}' permission")
        return self


def build_permission_matrix() -> dict[str, list[str]]:
    """Snapshot of the permission matrix, e.g. for docs / OpenAPI."""
    return {role.value: sorted(ROLE_ACTIONS[role]) for role in AccessRole}


__all__: list[str] = [
    "RegistryScope",
    "RegistryUser",
    "ROLE_ACTIONS",
    "ROLE_RANK",
    "build_permission_matrix",
    "can_act",
    "rank_of",
    "resolve_role",
]

"""Data isolation & authorization orchestration.

This is the central enforcement point for the IAM layer. Every controller /
service that touches tenant data must call :func:`authorize` before acting, and
must scope database queries with the department IDs returned by
:func:`scoped_department_ids`.

Enforcement order (deny always wins):

1. Subject is active (no lockout).
2. Emergency (break-glass) grant, if active, may widen access -- still audited.
3. ABAC deny-overrides.
4. RBAC permission check.
5. Jurisdiction scope computation (department filter for queries).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.federation.security.abac import AbacPolicy, AccessRequest, evaluate
from src.federation.security.jurisdiction import (
    DeptNode,
    jurisdiction_department_ids,
)
from src.federation.security.rbac import DbRole, effective_permissions


@dataclass
class Subject:
    """Authorized principal attributes."""

    officer_id: UUID
    department_id: UUID
    role_code: str
    rank: str | None = None
    active: bool = True
    access_mode: str = "normal"
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "officer_id": str(self.officer_id),
            "department_id": str(self.department_id),
            "role_code": self.role_code,
            "rank": self.rank,
            "active": self.active,
            "access_mode": self.access_mode,
            **self.extra,
        }


@dataclass
class AuthDecision:
    allowed: bool
    reason: str
    matched_abac: str | None = None
    emergency_id: UUID | None = None


def _deny(reason: str) -> AuthDecision:
    return AuthDecision(allowed=False, reason=reason)


def authorizer(
    subject: Subject,
    all_roles: list[DbRole],
    policies: list[AbacPolicy],
    departments: list[DeptNode],
    emergency_active_ids: set[UUID] | None = None,
) -> "Authorizer":
    """Build a bound authorizer for a subject (already resolved from DB)."""
    return Authorizer(
        subject=subject,
        all_roles=all_roles,
        policies=policies,
        departments=departments,
        emergency_ids=emergency_active_ids or set(),
    )


class Authorizer:
    """Bound authorizer: resolves permissions + scopes for one subject."""

    def __init__(
        self,
        subject: Subject,
        all_roles: list[DbRole],
        policies: list[AbacPolicy],
        departments: list[DeptNode],
        emergency_ids: set[UUID] | None = None,
    ) -> None:
        self.subject = subject
        self.all_roles = all_roles
        self.policies = policies
        self.departments = {d.id: d for d in departments}
        self.dept_nodes = departments
        self.emergency_ids: set[UUID] = emergency_ids or set()
        self._role = self._find_role(subject.role_code)

    def _find_role(self, code: str) -> DbRole | None:
        for r in self.all_roles:
            if r.code == code:
                return r
        return None

    def _permissions(self) -> set[str]:
        if self._role is not None:
            return effective_permissions(self._role, self.all_roles)
        from src.federation.security.permissions import BASE_PERMISSIONS, role_grants

        return role_grants(self.subject.role_code) | BASE_PERMISSIONS

    def is_emergency_active(self) -> bool:
        return bool(self.emergency_ids)

    # -- ABAC evaluation ---------------------------------------------------
    def _abac(self, resource_type: str, action: str,
              resource: dict[str, Any], context: dict[str, Any]) -> tuple[bool, str | None]:
        req = AccessRequest(
            subject=self.subject.as_dict(),
            resource={"type": resource_type, "action": action, **resource},
            context=context,
        )
        return evaluate(self.policies, req)

    # -- RBAC check --------------------------------------------------------
    def rbac_allows(self, resource_type: str, action: str) -> bool:
        return f"{resource_type}:{action}" in self._permissions()

    # -- Public authorize ---------------------------------------------------
    def authorize(
        self,
        resource_type: str,
        action: str,
        resource: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        *,
        emergency_id: UUID | None = None,
    ) -> AuthDecision:
        if not self.subject.active:
            return _deny("subject_inactive")

        resource = resource or {}
        context = context or {}

        # Emergency grant: if active and scoped for this resource/action.
        current_emergency = emergency_id if emergency_id else (
            next(iter(self.emergency_ids)) if self.emergency_ids else None
        )
        if current_emergency:
            # Break-glass bypasses the ordinary jurisdiction cone but still
            # requires the emergency grant to be for this target.
            grant_target = context.get("target_department_id")
            if grant_target and str(grant_target) in context.get("emergency_scope", []):
                return AuthDecision(
                    allowed=True, reason="emergency_grant", emergency_id=current_emergency
                )

        # 1) ABAC deny-overrides first.
        abac_ok, matched = self._abac(resource_type, action, resource, context)
        if not abac_ok:
            return AuthDecision(allowed=False, reason=f"abac_deny:{matched}", matched_abac=matched)

        # 2) RBAC.
        if not self.rbac_allows(resource_type, action):
            return _deny("rbac_deny")

        return AuthDecision(allowed=True, reason="allow")

    # -- Scoping for queries -------------------------------------------------
    def scoped_department_ids(self, scope_hint: str | None = None) -> set[UUID]:
        """Return department IDs the subject may query, by their jurisdiction."""
        role_scope = scope_hint or self._jurisdiction_scope()
        from src.federation.security.permissions import ROLE_JURISDICTION

        effective_scope = role_scope or ROLE_JURISDICTION.get(self.subject.role_code, "police_station")
        return jurisdiction_department_ids(
            self.subject.department_id, effective_scope, self.dept_nodes
        )

    def _jurisdiction_scope(self) -> str | None:
        if self._role is not None:
            return self._role.jurisdiction_scope
        from src.federation.security.permissions import ROLE_JURISDICTION

        return ROLE_JURISDICTION.get(self.subject.role_code)

    def owner_department(self) -> UUID:
        return self.subject.department_id

"""IAM API dependencies: resolve the acting principal (officer) and authorize.

The IAM API is self-contained and does NOT reuse the Phase 1-5 auth stack. It
authenticates via a federation access JWT whose ``jti`` must be bound to a valid
active :class:`OfficerSession`. The resolved :class:`Officer` becomes the
principal; the :class:`Authorizer` for that officer is attached to the request.
"""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.federation.db import get_federation_db
from src.federation.models import (
    AbacPolicy as AbacModel,
    Department,
    Officer,
    OfficerAccountStatus,
    Role,
    RolePermission,
)
from src.federation.security.isolation import Authorizer, Subject
from src.federation.security.jurisdiction import DeptNode
from src.federation.security.rbac import DbRole
from src.federation.security.session import SessionManager

_bearer = HTTPBearer(auto_error=False)

FederatedDBDep = Annotated[AsyncSession, Depends(get_federation_db)]


def _dept_node(dep: Department) -> DeptNode:

    return DeptNode(
        id=dep.id,
        code=dep.code,
        name=dep.name,
        dept_type=dep.dept_type,
        parent_id=dep.parent_id,
        jurisdiction=dep.jurisdiction_scope,
        hierarchy_level=dep.hierarchy_level,
        district=dep.district,
        state=dep.state,
    )


async def load_authorizer_inputs(db: AsyncSession):
    """Load roles (with grants), ABAC policies and the department tree."""
    roles: list[DbRole] = []
    role_rows = (await db.execute(select(Role))).scalars().all()
    # Permission grants per role.
    rp_rows = (await db.execute(select(RolePermission))).scalars().all()
    role_id_to_grants: dict[UUID, tuple[set[str], set[str]]] = {}
    for rp in rp_rows:
        perm_id = rp.permission_id
        grants, denies = role_id_to_grants.setdefault(rp.role_id, (set(), set()))
        # Resolve the permission code by loading it below via a cache map.
        (grants if rp.effect.value == "allow" else denies).add(perm_id)

    # Resolve permission codes.
    from src.federation.models import Permission

    perm_rows = (await db.execute(select(Permission))).scalars().all()
    code_by_id = {p.id: p.code for p in perm_rows}

    for r in role_rows:
        grants_ids, denies_ids = role_id_to_grants.get(r.id, (set(), set()))
        grants = {code_by_id.get(i, "") for i in grants_ids} - {""}
        denies = {code_by_id.get(i, "") for i in denies_ids} - {""}
        roles.append(
            DbRole(
                id=r.id,
                code=r.code,
                name=r.name,
                parent_role_id=r.parent_role_id,
                resource_scope=r.resource_scope,
                jurisdiction_scope=r.jurisdiction_scope.value
                if hasattr(r.jurisdiction_scope, "value")
                else str(r.jurisdiction_scope),
                grants=grants,
                denies=denies,
            )
        )

    policies = [
        AbacModelPolicyRecord(
            name=p.name,
            effect=p.effect,
            resource=p.resource,
            action=p.action,
            conditions=p.conditions,
            priority=p.priority,
            is_active=p.is_active,
        )
        for p in (await db.execute(select(AbacModel))).scalars().all()
    ]

    departments = [
        _dept_node(d) for d in (await db.execute(select(Department))).scalars().all()
    ]
    return roles, policies, departments


class AbacModelPolicyRecord:
    """Lightweight ABAC policy record bridging model -> engine dataclass."""

    def __init__(self, name, effect, resource, action, conditions, priority, is_active):
        from src.federation.security.abac import AbacPolicy
        from src.federation.models import PermissionEffect

        eff = effect if isinstance(effect, PermissionEffect) else PermissionEffect(effect)
        self._p = AbacPolicy(
            name=name, effect=eff, resource=resource, action=action,
            conditions=conditions, priority=priority, is_active=is_active,
        )

    @property
    def abac(self):
        return self._p


async def build_authorizer(db: AsyncSession, subject: Subject) -> Authorizer:
    roles, policy_records, departments = await load_authorizer_inputs(db)
    policies = [p.abac for p in policy_records]
    return Authorizer(subject=subject, all_roles=roles, policies=policies,
                      departments=departments)


class Principal:
    def __init__(self, officer: Officer, authorizer: Authorizer) -> None:
        self.officer = officer
        self.subject = Subject(
            officer_id=officer.id,
            department_id=officer.department_id,
            role_code=officer.role.code if officer.role else "viewer",
            rank=officer.rank.value if officer.rank else None,
            active=officer.status == OfficerAccountStatus.ACTIVE,
            extra={"designation": officer.designation, "badge": officer.badge_number},
        )
        self.authorizer = authorizer


async def get_current_principal(
    request: Request,
    db: FederatedDBDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = json.loads(credentials.credentials)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

    await _validate_access_jti(db, payload)

    officer_id = payload.get("sub")
    if not officer_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing subject.")
    officer = (
        await db.execute(
            select(Officer).options(selectinload(Officer.role)).where(Officer.id == UUID(str(officer_id)))
        )
    ).scalars().first()
    if officer is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Officer not found.")
    if officer.status != OfficerAccountStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Officer account not active.")

    authorizer = await build_authorizer(db, _subject_for(officer))
    return Principal(officer, authorizer)


def _subject_for(officer: Officer) -> Subject:
    from src.federation.models import OfficerAccountStatus

    rank = officer.rank.value if officer.rank else None
    return Subject(
        officer_id=officer.id,
        department_id=officer.department_id,
        role_code=officer.role.code if officer.role else "viewer",
        rank=rank,
        active=officer.status == OfficerAccountStatus.ACTIVE,
        extra={"designation": officer.designation, "badge": officer.badge_number},
    )


async def _validate_access_jti(db: AsyncSession, payload: dict) -> None:
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing jti.")
    mgr = SessionManager(db)
    valid = await mgr.validate_access(str(jti))
    if not valid:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked or expired."
        )


PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


def require_permission(resource: str, action: str):
    """Dependency factory: enforce RBAC via the principal's authorizer."""

    def _guard(principal: PrincipalDep) -> Principal:
        decision = principal.authorizer.authorize(resource, action)
        if not decision.allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission {resource}:{action}.",
            )
        return principal

    return _guard

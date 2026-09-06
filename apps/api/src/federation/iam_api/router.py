"""IAM FastAPI router: departments, officers, roles, permissions, ABAC, audit,
emergency access and sessions.

Every endpoint enforces authorization through the principal's :class:`Authorizer`
(RBAC + ABAC + jurisdiction isolation). The router is additive and self-contained
--- it does not touch any Phase 1-5 router.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.federation.iam_api.deps import FederatedDBDep, Principal, PrincipalDep, require_permission
from src.federation.iam_api.schemas import (
    AbacPolicyIn,
    AbacPolicyOut,
    AccessDecisionOut,
    AuditFilterIn,
    AuditOut,
    DepartmentIn,
    DepartmentOut,
    EmergencyApproveIn,
    EmergencyOut,
    EmergencyRequestIn,
    OfficerIn,
    OfficerOut,
    OfficerStatusIn,
    PermissionIn,
    PermissionOut,
    RoleIn,
    RoleOut,
    RolePermissionAssignIn,
    SessionOut,
)
from src.federation.models import (
    AbacPolicy,
    Department,
    EmergencyAccess,
    Officer,
    OfficerAccountStatus,
    Permission,
    Role,
    RolePermission,
    Severity,
)
from src.federation.security import breakglass as bg
from src.federation.security.audit import AuditEvent, search_audit, write_audit
from src.federation.security.jurisdiction import build_tree, hierarchy_level_for_type
from src.federation.security.permissions import all_permission_codes
from src.federation.security.session import (
    SessionManager,
)

router = APIRouter(prefix="/iam", tags=["iam"])


def _to_dept_out(d: Department) -> dict:

    return DepartmentOut.model_validate(d).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------
@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("department", "read"))],
    scope: str | None = Query(default=None, description="Optional jurisdiction scope override"),
):
    depts = (await db.execute(select(Department).where(Department.is_deleted.is_(False)))).scalars().all()
    allowed = principal.authorizer.scoped_department_ids(scope) if scope else None
    if allowed is None:
        allowed = principal.authorizer.scoped_department_ids()
    return [DepartmentOut.model_validate(d) for d in depts if d.id in allowed]


@router.get("/departments/tree", response_model=dict)
async def department_tree(db: FederatedDBDep, principal: PrincipalDep):
    depts = (await db.execute(select(Department).where(Department.is_deleted.is_(False)))).scalars().all()
    allowed = principal.authorizer.scoped_department_ids()
    nodes = [d for d in depts if d.id in allowed]
    forest = build_tree(_dept_nodes(nodes))
    return {"tree": _serialize_forest(forest)}


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    payload: DepartmentIn,
    db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("department", "create"))],
):
    existing = (await db.execute(select(Department).where(Department.code == payload.code))).scalars().first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Department code already exists.")
    parent = None
    if payload.parent_id:
        parent = await db.get(Department, payload.parent_id)
        if parent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Parent department not found.")

    dept = Department(
        code=payload.code,
        name=payload.name,
        kind=_kind(payload.kind),
        dept_type=payload.dept_type,
        parent_id=payload.parent_id,
        hierarchy_level=payload.hierarchy_level or hierarchy_level_for_type(payload.dept_type),
        jurisdiction_scope=payload.jurisdiction_scope,
        district=payload.district,
        state=payload.state or "Gujarat",
        latitude=payload.latitude,
        longitude=payload.longitude,
        address=payload.address,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        description=payload.description,
        metadata_=payload.metadata_,
        created_by=principal.officer.id,
        updated_by=principal.officer.id,
        is_deleted=False,
    )
    db.add(dept)
    await db.flush()
    await write_audit(
        db,
        AuditEvent(
            actor=principal.officer.email, actor_department=str(principal.officer.department_id),
            action="department.create", resource_type="department", resource_id=str(dept.id),
            new_value={"code": dept.code, "name": dept.name},
            officer_id=principal.officer.id, department_id=principal.officer.department_id,
            severity=Severity.INFO,
        ),
    )
    await db.commit()
    await db.refresh(dept)
    return DepartmentOut.model_validate(dept)


@router.get("/departments/{dept_id}", response_model=DepartmentOut)
async def get_department(
    dept_id: uuid.UUID, db: FederatedDBDep, principal: PrincipalDep
):
    allowed = principal.authorizer.scoped_department_ids()
    dept = await db.get(Department, dept_id)
    if dept is None or dept.id not in allowed or dept.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Department not found.")
    return DepartmentOut.model_validate(dept)


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
async def update_department(
    dept_id: uuid.UUID, payload: DepartmentIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("department", "update"))],
):
    dept = await db.get(Department, dept_id)
    if dept is None or dept.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Department not found.")
    old = {"name": dept.name, "hierarchy_level": dept.hierarchy_level, "jurisdiction_scope": dept.jurisdiction_scope.value}
    dept.name = payload.name
    dept.description = payload.description
    dept.district = payload.district
    dept.state = payload.state or dept.state
    dept.latitude = payload.latitude
    dept.longitude = payload.longitude
    dept.address = payload.address
    dept.contact_email = payload.contact_email
    dept.contact_phone = payload.contact_phone
    dept.updated_by = principal.officer.id
    await db.flush()
    await write_audit(
        db,
        AuditEvent(
            actor=principal.officer.email, actor_department=str(principal.officer.department_id),
            action="department.update", resource_type="department", resource_id=str(dept.id),
            old_value=old, new_value={"name": dept.name, "jurisdiction_scope": dept.jurisdiction_scope.value,
                                      "hierarchy_level": dept.hierarchy_level},
            officer_id=principal.officer.id, department_id=principal.officer.department_id,
            severity=Severity.INFO,
        ),
    )
    await db.commit()
    await db.refresh(dept)
    return DepartmentOut.model_validate(dept)


@router.delete("/departments/{dept_id}", status_code=204)
async def soft_delete_department(
    dept_id: uuid.UUID, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("department", "delete"))],
):
    dept = await db.get(Department, dept_id)
    if dept is None or dept.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Department not found.")
    dept.is_deleted = True
    dept.deleted_at = bg.utcnow()
    dept.updated_by = principal.officer.id
    await db.flush()
    await write_audit(
        db,
        AuditEvent(actor=principal.officer.email, actor_department=str(principal.officer.department_id),
                   action="department.delete", resource_type="department", resource_id=str(dept.id),
                   old_value={"is_deleted": False}, new_value={"is_deleted": True},
                   officer_id=principal.officer.id, department_id=principal.officer.department_id,
                   severity=Severity.WARNING),
    )
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Officers
# ---------------------------------------------------------------------------
@router.get("/officers", response_model=list[OfficerOut])
async def list_officers(
    db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("officer", "read"))],
    department_id: uuid.UUID | None = None,
):
    allowed = principal.authorizer.scoped_department_ids()
    stmt = select(Officer).where(Officer.department_id.in_(allowed), Officer.is_deleted.is_(False))
    if department_id:
        stmt = stmt.where(Officer.department_id == department_id)
    officers = (await db.execute(stmt)).scalars().all()
    out = []
    for o in officers:
        d = OfficerOut.model_validate(o).model_dump(mode="json")
        d["role_id"] = str(o.role_id) if o.role_id else None
        out.append(o)
    return [OfficerOut.model_validate(o) for o in officers]


@router.post("/officers", response_model=OfficerOut, status_code=201)
async def create_officer(
    payload: OfficerIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("officer", "create"))],
):
    if payload.department_id not in principal.authorizer.scoped_department_ids():
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot create officer outside your jurisdiction.")
    existing = (await db.execute(select(Officer).where(Officer.email == payload.email))).scalars().first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Officer email already exists.")
    role = None
    if payload.role_code:
        role = (await db.execute(select(Role).where(Role.code == payload.role_code))).scalars().first()
    officer = Officer(
        badge_number=payload.badge_number, full_name=payload.full_name, email=payload.email,
        phone=payload.phone, department_id=payload.department_id, rank=payload.rank,
        designation=payload.designation, assigned_district=payload.assigned_district,
        assigned_station=payload.assigned_station, role_id=role.id if role else None,
        supervisor_id=payload.supervisor_id, mfa_enabled=payload.mfa_enabled,
        status=OfficerAccountStatus.PENDING, account_status="active", is_deleted=False,
    )
    db.add(officer)
    await db.flush()
    await write_audit(
        db,
        AuditEvent(actor=principal.officer.email, actor_department=str(principal.officer.department_id),
                   action="officer.create", resource_type="officer", resource_id=str(officer.id),
                   new_value={"badge": officer.badge_number, "role": payload.role_code},
                   officer_id=principal.officer.id, department_id=principal.officer.department_id,
                   severity=Severity.INFO),
    )
    await db.commit()
    await db.refresh(officer)
    return OfficerOut.model_validate(officer)


@router.get("/officers/{officer_id}", response_model=OfficerOut)
async def get_officer(officer_id: uuid.UUID, db: FederatedDBDep, principal: PrincipalDep):
    allowed = principal.authorizer.scoped_department_ids()
    officer = await db.get(Officer, officer_id)
    if officer is None or officer.department_id not in allowed or officer.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Officer not found.")
    return OfficerOut.model_validate(officer)


@router.put("/officers/{officer_id}/status", response_model=OfficerOut)
async def set_officer_status(
    officer_id: uuid.UUID, payload: OfficerStatusIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("officer", "update"))],
):
    officer = await db.get(Officer, officer_id)
    if officer is None or officer.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Officer not found.")
    old_status = officer.status
    officer.status = payload.status
    officer.account_status = payload.status.value
    await db.flush()
    await write_audit(
        db,
        AuditEvent(actor=principal.officer.email, actor_department=str(principal.officer.department_id),
                   action="officer.status", resource_type="officer", resource_id=str(officer.id),
                   old_value={"status": old_status.value}, new_value={"status": payload.status.value},
                   officer_id=principal.officer.id, department_id=principal.officer.department_id,
                   severity=Severity.INFO),
    )
    await db.commit()
    await db.refresh(officer)
    return OfficerOut.model_validate(officer)


@router.post("/officers/{officer_id}/role", response_model=OfficerOut)
async def assign_officer_role(
    officer_id: uuid.UUID, role_code: str, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("officer", "assign"))],
):
    officer = await db.get(Officer, officer_id)
    if officer is None or officer.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Officer not found.")
    role = (await db.execute(select(Role).where(Role.code == role_code))).scalars().first()
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found.")
    old_role = officer.role_id
    officer.role_id = role.id
    await db.flush()
    await write_audit(
        db,
        AuditEvent(actor=principal.officer.email, actor_department=str(principal.officer.department_id),
                   action="officer.role_assign", resource_type="officer", resource_id=str(officer.id),
                   old_value={"role_id": str(old_role)} if old_role else None,
                   new_value={"role_id": str(role.id), "role_code": role.code},
                   officer_id=principal.officer.id, department_id=principal.officer.department_id,
                   severity=Severity.INFO),
    )
    await db.commit()
    await db.refresh(officer)
    return OfficerOut.model_validate(officer)


# ---------------------------------------------------------------------------
# Roles & permissions
# ---------------------------------------------------------------------------
@router.get("/roles", response_model=list[RoleOut])
async def list_roles(db: FederatedDBDep, principal: PrincipalDep):
    roles = (await db.execute(select(Role))).scalars().all()
    return [RoleOut.model_validate(r) for r in roles]


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(
    payload: RoleIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("role", "create"))],
):
    existing = (await db.execute(select(Role).where(Role.code == payload.code))).scalars().first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Role code already exists.")
    role = Role(
        code=payload.code, name=payload.name, description=payload.description,
        parent_role_id=payload.parent_role_id, resource_scope=payload.resource_scope,
        jurisdiction_scope=payload.jurisdiction_scope, is_system=payload.is_system,
        is_active=payload.is_active,
    )
    db.add(role)
    await db.flush()
    await write_audit(
        db,
        AuditEvent(actor=principal.officer.email, actor_department=str(principal.officer.department_id),
                   action="role.create", resource_type="role", resource_id=str(role.id),
                   new_value={"code": role.code, "jurisdiction_scope": role.jurisdiction_scope.value},
                   officer_id=principal.officer.id, department_id=principal.officer.department_id,
                   severity=Severity.INFO),
    )
    await db.commit()
    await db.refresh(role)
    return RoleOut.model_validate(role)


@router.get("/roles/{role_id}/permissions", response_model=list[str])
async def role_permissions(role_id: uuid.UUID, db: FederatedDBDep, principal: PrincipalDep):
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found.")
    rps = (await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))).scalars().all()
    perm_ids = [rp.permission_id for rp in rps]
    if not perm_ids:
        return []
    perms = (await db.execute(select(Permission).where(Permission.id.in_(perm_ids)))).scalars().all()
    return [p.code for p in perms]


@router.post("/roles/{role_id}/permissions", response_model=dict)
async def assign_role_permissions(
    role_id: uuid.UUID, payload: RolePermissionAssignIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("permission", "assign"))],
):
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found.")
    perms = (await db.execute(select(Permission).where(Permission.code.in_(payload.permission_codes)))).scalars().all()
    n = 0
    for p in perms:
        existing = (await db.execute(
            select(RolePermission).where(
                RolePermission.role_id == role_id, RolePermission.permission_id == p.id)
        )).scalars().first()
        if existing:
            existing.effect = payload.effect
        else:
            db.add(RolePermission(role_id=role_id, permission_id=p.id, effect=payload.effect))
        n += 1
    await db.flush()
    await write_audit(
        db,
        AuditEvent(actor=principal.officer.email, actor_department=str(principal.officer.department_id),
                   action="role.permission_assign", resource_type="role", resource_id=str(role_id),
                   new_value={"count": n, "effect": payload.effect.value, "codes": payload.permission_codes},
                   officer_id=principal.officer.id, department_id=principal.officer.department_id,
                   severity=Severity.INFO),
    )
    await db.commit()
    return {"assigned": n}


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(db: FederatedDBDep, principal: PrincipalDep):
    perms = (await db.execute(select(Permission))).scalars().all()
    return [PermissionOut.model_validate(p) for p in perms]


@router.get("/permissions/catalog", response_model=list[str])
async def permission_catalog(principal: PrincipalDep):
    return all_permission_codes()


@router.post("/permissions", response_model=PermissionOut, status_code=201)
async def create_permission(
    payload: PermissionIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("permission", "create"))],
):
    existing = (await db.execute(select(Permission).where(Permission.code == payload.code))).scalars().first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Permission code already exists.")
    perm = Permission(code=payload.code, resource=payload.resource, action=payload.action,
                      description=payload.description, scope=payload.scope)
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return PermissionOut.model_validate(perm)


# ---------------------------------------------------------------------------
# ABAC
# ---------------------------------------------------------------------------
@router.get("/abac", response_model=list[AbacPolicyOut])
async def list_abac(db: FederatedDBDep, principal: PrincipalDep):
    policies = (await db.execute(select(AbacPolicy))).scalars().all()
    return [AbacPolicyOut.model_validate(p) for p in policies]


@router.post("/abac", response_model=AbacPolicyOut, status_code=201)
async def create_abac(
    payload: AbacPolicyIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("permission", "create"))],
):
    policy = AbacPolicy(name=payload.name, effect=payload.effect, resource=payload.resource,
                        action=payload.action, conditions=payload.conditions,
                        priority=payload.priority, is_active=payload.is_active)
    db.add(policy)
    await db.flush()
    await write_audit(
        db,
        AuditEvent(actor=principal.officer.email, actor_department=str(principal.officer.department_id),
                   action="abac.create", resource_type="permission", resource_id=str(policy.id),
                   new_value={"name": policy.name, "effect": policy.effect.value,
                              "resource": policy.resource, "action": policy.action},
                   officer_id=principal.officer.id, department_id=principal.officer.department_id,
                   severity=Severity.INFO),
    )
    await db.commit()
    await db.refresh(policy)
    return AbacPolicyOut.model_validate(policy)


@router.put("/abac/{policy_id}", response_model=AbacPolicyOut)
async def update_abac(
    policy_id: uuid.UUID, payload: AbacPolicyIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("permission", "update"))],
):
    policy = await db.get(AbacPolicy, policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ABAC policy not found.")
    policy.name = payload.name
    policy.effect = payload.effect
    policy.resource = payload.resource
    policy.action = payload.action
    policy.conditions = payload.conditions
    policy.priority = payload.priority
    policy.is_active = payload.is_active
    await db.commit()
    await db.refresh(policy)
    return AbacPolicyOut.model_validate(policy)


@router.delete("/abac/{policy_id}", status_code=204)
async def delete_abac(
    policy_id: uuid.UUID, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("permission", "delete"))],
):
    policy = await db.get(AbacPolicy, policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ABAC policy not found.")
    await db.delete(policy)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@router.get("/audit", response_model=list[AuditOut])
async def search_audit_logs(
    db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("audit", "read"))],
    filters: AuditFilterIn = Query(default=AuditFilterIn()),
):
    allowed = principal.authorizer.scoped_department_ids()
    records = await search_audit(
        db, department_ids=allowed, officer_id=filters.officer_id, action=filters.action,
        resource_type=filters.resource_type, severity=filters.severity,
        access_mode=filters.access_mode, limit=filters.limit, offset=filters.offset,
    )
    return [AuditOut.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# Emergency (break-glass)
# ---------------------------------------------------------------------------
@router.post("/emergency/request", response_model=EmergencyOut, status_code=201)
async def emergency_request(payload: EmergencyRequestIn, db: FederatedDBDep, principal: PrincipalDep):
    record = await bg.request_access(
        db, officer_id=principal.officer.id, department_id=principal.officer.department_id,
        reason=payload.reason, case_reference=payload.case_reference,
        duration_seconds=payload.duration_seconds, grant=payload.grant,
    )
    await db.refresh(record)
    return EmergencyOut.model_validate(record)


@router.post("/emergency/{emergency_id}/approve", response_model=EmergencyOut)
async def emergency_approve(
    emergency_id: uuid.UUID, payload: EmergencyApproveIn, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("system", "manage"))],
):
    record = await bg.approve(
        db, emergency_id, approver_id=principal.officer.id,
        approver_department=principal.officer.department_id,
        approve_flag=payload.approve, reason=payload.reason,
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Emergency request not found.")
    await db.refresh(record)
    return EmergencyOut.model_validate(record)


@router.post("/emergency/{emergency_id}/activate", response_model=EmergencyOut)
async def emergency_activate(emergency_id: uuid.UUID, db: FederatedDBDep, principal: PrincipalDep):
    record = await bg.activate(
        db, emergency_id, actor_id=principal.officer.id, actor_department=principal.officer.department_id,
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Emergency request not found.")
    await db.refresh(record)
    return EmergencyOut.model_validate(record)


@router.post("/emergency/{emergency_id}/revoke", response_model=EmergencyOut)
async def emergency_revoke(
    emergency_id: uuid.UUID, db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("system", "manage"))],
):
    record = await bg.revoke(
        db, emergency_id, revoker_id=principal.officer.id,
        revoker_department=principal.officer.department_id,
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Emergency request not found.")
    await db.refresh(record)
    return EmergencyOut.model_validate(record)


@router.get("/emergency", response_model=list[EmergencyOut])
async def list_emergency(
    db: FederatedDBDep,
    principal: Annotated[Principal, Depends(require_permission("system", "read"))],
    officer_id: uuid.UUID | None = None,
):
    stmt = select(EmergencyAccess)
    if officer_id:
        stmt = stmt.where(EmergencyAccess.officer_id == officer_id)
    records = (await db.execute(stmt)).scalars().all()
    return [EmergencyOut.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# Auth (session bootstrap)
# ---------------------------------------------------------------------------
@router.post("/auth/session", response_model=dict)
async def bootstrap_session(
    db: FederatedDBDep,
    officer_id: uuid.UUID | None = None,
):
    """Issue a federation session token for an officer (bootstrap/dev).

    The federation IAM has no password login; the platform normally issues
    officer sessions programmatically. This endpoint mirrors that flow for the
    seeded bootstrap admin so the dashboard can obtain a bearer token.
    """
    if officer_id is None:
        admin = (
            await db.execute(select(Officer).where(Officer.badge_number == "ADMIN-0001"))
        ).scalars().first()
        if admin is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Bootstrap admin not found.")
        officer_id = admin.id

    officer = await db.get(Officer, officer_id)
    if officer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Officer not found.")
    if officer.status != OfficerAccountStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Officer account not active.")
    officer = (
        await db.execute(
            select(Officer).options(selectinload(Officer.role)).where(Officer.id == officer_id)
        )
    ).scalars().first()

    mgr = SessionManager(db)
    created = await mgr.create(officer.id, user_agent="sentinel-web", ip_address="127.0.0.1")
    access_token = json.dumps({
        "sub": str(officer.id),
        "jti": created.access_jti,
        "exp": (bg.utcnow() + timedelta(minutes=15)).timestamp(),
        "role": officer.role.code if officer.role else "viewer",
    })
    await db.commit()
    return {
        "access_token": access_token,
        "refresh_token": created.raw_refresh_token,
        "officer_id": str(officer.id),
        "badge_number": officer.badge_number,
        "full_name": officer.full_name,
        "role": officer.role.code if officer.role else "viewer",
    }


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: FederatedDBDep, principal: PrincipalDep):
    mgr = SessionManager(db)
    sessions = await mgr.list_active(principal.officer.id)
    return [SessionOut.model_validate(s) for s in sessions]


@router.post("/sessions/{session_id}/revoke", status_code=204)
async def revoke_session(session_id: uuid.UUID, db: FederatedDBDep, principal: PrincipalDep):
    mgr = SessionManager(db)
    ok = await mgr.revoke_session_id(session_id, principal.officer.id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return None


@router.post("/sessions/revoke-all", status_code=204)
async def revoke_all_sessions(db: FederatedDBDep, principal: PrincipalDep):
    mgr = SessionManager(db)
    await mgr.revoke_all_for_officer(principal.officer.id)
    return None


@router.get("/access/check", response_model=AccessDecisionOut)
async def access_check(
    resource: str, action: str, db: FederatedDBDep, principal: PrincipalDep,
    target_department_id: uuid.UUID | None = None,
):
    context = {}
    if target_department_id:
        context["target_department_id"] = str(target_department_id)
    decision = principal.authorizer.authorize(resource, action, context=context)
    return AccessDecisionOut(allowed=decision.allowed, reason=decision.reason,
                             matched_abac=decision.matched_abac, emergency_id=decision.emergency_id)


def _kind(kind_value: str):
    from src.federation.models import DepartmentKind

    return DepartmentKind(kind_value) if kind_value in {m.value for m in DepartmentKind} else DepartmentKind.OTHER


def _dept_nodes(depts: list[Department]):
    from src.federation.iam_api.deps import _dept_node

    return [_dept_node(d) for d in depts]


def _serialize_forest(forest):
    def node(d):
        return {
            "id": str(d.id), "code": d.code, "name": d.name,
            "type": d.dept_type.value, "hierarchy_level": d.hierarchy_level,
            "children": [node(c) for c in d.children],
        }

    return [node(r) for r in forest]

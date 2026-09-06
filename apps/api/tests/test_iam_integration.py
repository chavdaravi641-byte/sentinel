"""Phase 6.1 IAM -- integration tests (DB-backed, in-memory SQLite).

Covers department isolation, cross-department access prevention, audit logging,
emergency (break-glass) access and session revocation.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from src.federation.models import (
    AccessMode,
    Department,
    EmergencyStatus,
    Officer,
    OfficerAccountStatus,
    OfficerRank,
    Role,
    Severity,
)
from src.federation.security import audit as audit_mod
from src.federation.security import breakglass as bg
from src.federation.security import session as sess
from src.federation.security.isolation import Subject, authorizer
from src.federation.security.jurisdiction import DeptNode
from src.federation.security.rbac import DbRole


async def _dept_nodes(db):
    depts = (await db.execute(select(Department))).scalars().all()
    return [
        DeptNode(id=d.id, code=d.code, name=d.name, dept_type=d.dept_type,
                 parent_id=d.parent_id, jurisdiction=d.jurisdiction_scope,
                 hierarchy_level=d.hierarchy_level)
        for d in depts
    ]


async def _make_officer(db, *, badge, email, dept_code, rank=OfficerRank.PSI,
                        role_code="psi", status=OfficerAccountStatus.ACTIVE):
    dept = (await db.execute(select(Department).where(Department.code == dept_code))).scalars().first()
    role = (await db.execute(select(Role).where(Role.code == role_code))).scalars().first()
    ofc = Officer(badge_number=badge, full_name=badge, email=email, department_id=dept.id,
                  rank=rank, status=status, role_id=role.id if role else None,
                  account_status=status.value)
    db.add(ofc)
    await db.flush()
    return ofc, dept


async def _role_for(db, code):
    role = (await db.execute(select(Role).where(Role.code == code))).scalars().first()
    return DbRole(id=role.id, code=role.code, name=role.name,
                  parent_role_id=role.parent_role_id,
                  jurisdiction_scope=role.jurisdiction_scope.value,
                  grants=set())  # dynamic grants lazily resolved elsewhere


# --- Department isolation --------------------------------------------------------
async def test_department_isolation(fed_db):
    db = fed_db
    ps_ofc, ps_dept = await _make_officer(db, badge="PSI-2001", email="p2001@test",
                                          dept_code="GAHM-NAV")
    dist = (await db.execute(select(Department).where(Department.code == "GAHMD"))).scalars().first()

    nodes = await _dept_nodes(db)
    psi_role = await _role_for(db, "psi")
    authz = authorizer(Subject(officer_id=ps_ofc.id, department_id=ps_dept.id,
                               role_code="psi", active=True), [psi_role], [], nodes)
    allowed = authz.scoped_department_ids()
    # PSI may only access its own police station cone.
    assert all(n.id in allowed for n in nodes if n.id == ps_dept.id)
    assert dist.id not in allowed


async def test_cross_department_leakage_prevented(fed_db):
    db = fed_db
    ps_ofc, ps_dept = await _make_officer(db, badge="PSI-2002", email="p2002@test",
                                          dept_code="GAHM-NAV")
    dist = (await db.execute(select(Department).where(Department.code == "GAHMD"))).scalars().first()
    nodes = await _dept_nodes(db)
    psi_role = await _role_for(db, "psi")
    authz = authorizer(Subject(officer_id=ps_ofc.id, department_id=ps_dept.id,
                               role_code="psi", active=True), [psi_role], [], nodes)
    # Cross-department read of a *district* resource is denied (out of scope).
    allowed = authz.scoped_department_ids()
    assert dist.id not in allowed
    # The authorizer also denies actions the role cannot perform.
    assert authz.authorize("department", "delete").allowed is False


# --- Privilege escalation prevention ----------------------------------------------
async def test_privilege_escalation_prevention(fed_db):
    db = fed_db
    constable, c_dept = await _make_officer(db, badge="CON-3001", email="c3001@test",
                                            dept_code="GAHM-NAV", rank=OfficerRank.CONSTABLE,
                                            role_code="constable")
    nodes = await _dept_nodes(db)
    con_role = await _role_for(db, "constable")
    authz = authorizer(Subject(officer_id=constable.id, department_id=c_dept.id,
                               role_code="constable", active=True), [con_role], [], nodes)
    # A constable must not be able to escalate into admin operations.
    for res, act in (("role", "create"), ("permission", "manage"), ("department", "create"),
                     ("officer", "assign"), ("settings", "manage")):
        assert authz.authorize(res, act).allowed is False


# --- Audit logging ------------------------------------------------------------------
async def test_audit_writes_and_isolation(fed_db):
    db = fed_db
    ps_ofc, ps_dept = await _make_officer(db, badge="PSI-2003", email="p2003@test",
                                          dept_code="GAHM-NAV")
    await audit_mod.write_audit(
        db, audit_mod.AuditEvent(
            actor="p2003@test", actor_department=str(ps_dept.id), action="camera.search",
            resource_type="camera", resource_id="cam-9", officer_id=ps_ofc.id,
            department_id=ps_dept.id, access_mode=AccessMode.NORMAL, severity=Severity.INFO,
            old_value={"x": 1}, new_value={"x": 2},
        ))
    await db.commit()
    records = await audit_mod.search_audit(db, department_ids={ps_dept.id}, action="camera.search")
    assert len(records) >= 1
    r = records[0]
    assert r.department_id == ps_dept.id
    assert r.old_value == {"x": 1}
    assert r.new_value == {"x": 2}


# --- Emergency access ----------------------------------------------------------------
async def test_emergency_lifecycle_and_auto_expiry(fed_db):
    db = fed_db
    ps_ofc, ps_dept = await _make_officer(db, badge="PSI-2004", email="p2004@test",
                                          dept_code="GAHM-NAV")
    admin = (await db.execute(select(Officer).where(Officer.badge_number == "ADMIN-0001"))).scalars().first()
    rec = await bg.request_access(db, officer_id=ps_ofc.id, department_id=ps_dept.id,
                                  reason="Urgent", duration_seconds=600, case_reference="C-99")
    assert rec.status == EmergencyStatus.REQUESTED
    rec = await bg.approve(db, rec.id, approver_id=admin.id,
                           approver_department=admin.department_id, approve_flag=True)
    assert rec.status == EmergencyStatus.APPROVED
    rec = await bg.activate(db, rec.id, actor_id=ps_ofc.id, actor_department=ps_dept.id)
    assert rec.status == EmergencyStatus.ACTIVE
    assert bg.is_active(rec)
    # Auto-expire.
    rec.expires_at = bg.utcnow() + timedelta(seconds=-5)
    await db.flush()
    rec = await bg.check_expiry(db, rec.id)
    assert rec.status == EmergencyStatus.EXPIRED


async def test_emergency_revoke(fed_db):
    db = fed_db
    ps_ofc, ps_dept = await _make_officer(db, badge="PSI-2005", email="p2005@test",
                                          dept_code="GAHM-NAV")
    admin = (await db.execute(select(Officer).where(Officer.badge_number == "ADMIN-0001"))).scalars().first()
    rec = await bg.request_access(db, officer_id=ps_ofc.id, department_id=ps_dept.id,
                                  reason="Req", duration_seconds=600)
    rec = await bg.approve(db, rec.id, approver_id=admin.id,
                           approver_department=admin.department_id, approve_flag=True)
    rec = await bg.activate(db, rec.id, actor_id=ps_ofc.id, actor_department=ps_dept.id)
    rec = await bg.revoke(db, rec.id, revoker_id=admin.id, revoker_department=admin.department_id)
    assert rec.status == EmergencyStatus.REVOKED


# --- Session revocation ----------------------------------------------------------------
async def test_session_revocation_and_rotation(fed_db):
    db = fed_db
    ps_ofc, ps_dept = await _make_officer(db, badge="PSI-2006", email="p2006@test",
                                          dept_code="GAHM-NAV")
    mgr = sess.SessionManager(db)
    created = await mgr.create(ps_ofc.id, user_agent="UA/1", ip_address="10.0.0.1")
    assert await mgr.validate_access(created.access_jti) is True
    rotated = await mgr.rotate_refresh(created.raw_refresh_token)
    assert rotated is not None
    assert await mgr.validate_access(rotated.access_jti) is True
    # Revoke and confirm access invalidated.
    await mgr.revoke(rotated.raw_refresh_token)
    assert await mgr.validate_access(rotated.access_jti) is False
    await db.commit()

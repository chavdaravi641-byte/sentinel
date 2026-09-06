"""Phase 6.1 IAM -- unit tests (pure logic, no DB).

Covers RBAC, permission inheritance, permission cache, ABAC (incl. deny
overrides), jurisdiction scoping, password policy and account lockout.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from src.federation.models import (
    DepartmentType,
    JurisdictionScope,
    PermissionEffect,
)
from src.federation.security.abac import AbacPolicy, AccessRequest, evaluate, policy_matches
from src.federation.security.isolation import Subject, authorizer
from src.federation.security.jurisdiction import (
    DeptNode,
    build_tree,
    descendants,
    hierarchy_level_for_type,
    jurisdiction_department_ids,
    validate_jurisdiction,
)
from src.federation.security.permissions import (
    ROLE_MATRIX,
    all_permission_codes,
    invalidate_permission_cache,
    role_grants,
    role_has_permission,
)
from src.federation.security.rbac import DbRole, effective_permissions
from src.federation.security.session import (
    is_locked_out,
    password_meets_policy,
    should_lock,
    validate_password_policy,
)

_x = uuid.uuid4


# --- RBAC ---------------------------------------------------------------------
def test_super_admin_has_all_permissions():
    assert role_has_permission("super_admin", "system:manage")
    assert role_has_permission("super_admin", "audit:delete")
    assert len(ROLE_MATRIX["super_admin"] & set(all_permission_codes())) > 300


def test_low_privilege_denied():
    assert not role_has_permission("viewer", "case:delete")
    assert not role_has_permission("constable", "camera:delete")
    assert not role_has_permission("constable", "evidence:delete")


def test_permission_inheritance():
    # analyst inherits from viewer; operator inherits from analyst.
    assert "camera:read" in role_grants("analyst", inherited=True)
    assert "camera:read" in role_grants("operator", inherited=True)
    assert "report:create" in role_grants("operator", inherited=True)
    # viewer base read-only promotions are inherited downstream.
    assert "camera:search" in role_grants("analyst", inherited=True)


def test_effective_permissions_with_db_role_deny_overrides():
    role = DbRole(
        id=_x(), code="custom-analyst", name="Custom Analyst",
        grants={"camera:read", "case:read"}, denies={"case:delete"},
    )
    eff = effective_permissions(role, [role])
    assert "camera:read" in eff
    assert "case:delete" not in eff


def test_permission_cache_invalidation():
    invalidate_permission_cache()
    assert role_has_permission("viewer", "camera:read") is True
    invalidate_permission_cache().__class__  # noqa: B018 - cache model smoke
    # after invalidation the same lookup still resolves.
    assert role_has_permission("viewer", "camera:read") is True


# --- ABAC ---------------------------------------------------------------------
def _req(resource_type="camera", action="read", **kw):
    return AccessRequest(
        subject=kw.pop("subject", {"department_id": "D1", "rank": "psi"}),
        resource={"type": resource_type, "action": action, **kw.pop("resource", {})},
        context=kw.pop("context", {}),
    )


def test_abac_allow_policy():
    p = AbacPolicy(name="own-dept", effect=PermissionEffect.ALLOW, resource="camera",
                   action="read", conditions={"resource.department_id": {"op": "eq", "value": "D1"}})
    assert policy_matches(p, _req(resource={"department_id": "D1"}))
    assert evaluate([p], _req(resource={"department_id": "D1"}))[0] is True


def test_abac_deny_overrides_allow():
    allow = AbacPolicy(name="allow", effect=PermissionEffect.ALLOW, resource="*", action="*",
                       conditions={})
    deny = AbacPolicy(name="deny-role", effect=PermissionEffect.DENY, resource="*", action="*",
                      conditions={"subject.rank": {"op": "eq", "value": "psp"}})
    ok = evaluate([allow], _req(subject={"rank": "dsp"}))[0]
    blocked = evaluate([allow, deny], _req(subject={"rank": "psp"}))
    assert ok is True
    assert blocked == (False, "deny-role")


def test_abac_clearance_and_time():
    # A non-matching ALLOW policy is ignored -> RBAC remains authoritative (allowed).
    p = AbacPolicy(name="sensitive", effect=PermissionEffect.ALLOW, resource="camera",
                   action="read", conditions={"resource.classification": {"op": "lte", "value": 3}})
    assert evaluate([p], _req(resource={"classification": 2}))[0] is True
    assert evaluate([p], _req(resource={"classification": 5}))[0] is True  # policy not matched
    # An explicit DENY below clearance is enforced (deny overrides).
    deny_c = AbacPolicy(name="no-high", effect=PermissionEffect.DENY, resource="camera", action="read",
                        conditions={"resource.classification": {"op": "gt", "value": 3}})
    assert evaluate([p, deny_c], _req(resource={"classification": 5}))[0] is False
    t_pol = AbacPolicy(name="hours", effect=PermissionEffect.ALLOW, resource="camera", action="read",
                       conditions={"context.hour": {"op": "within_hours", "value": [0, 23]}})
    assert evaluate([t_pol], _req(context={"hour": 14}))[0] is True


# --- Jurisdiction & isolation ---------------------------------------------------
def _tree():
    police = DeptNode(_x(), "GJPOL", "Gujarat Police", DepartmentType.STATE_HQ, None,
                      JurisdictionScope.STATE, 1)
    range1 = DeptNode(_x(), "R1", "Range 1", DepartmentType.RANGE, police.id,
                      JurisdictionScope.RANGE, 2)
    dist = DeptNode(_x(), "D1", "Ahmedabad", DepartmentType.DISTRICT, range1.id,
                    JurisdictionScope.DISTRICT, 4)
    ps = DeptNode(_x(), "PS1", "Navrangpura", DepartmentType.POLICE_STATION, dist.id,
                  JurisdictionScope.POLICE_STATION, 6)
    police.children = [range1]
    range1.children = [dist]
    dist.children = [ps]
    return [police, range1, dist, ps]


def test_jurisdiction_cone():
    t = _tree()
    ps = t[3]
    ids = jurisdiction_department_ids(ps.id, JurisdictionScope.POLICE_STATION, t)
    assert ids == {ps.id}
    dist = t[2]
    ids = jurisdiction_department_ids(dist.id, JurisdictionScope.DISTRICT, t)
    assert ids == {dist.id, ps.id}
    assert len(descendants(t, t[0].id)) == 4


def test_authorizer_rbac_and_isolation():
    t = _tree()
    ps = t[3]
    role = DbRole(id=_x(), code="psi", name="PSI", grants={"camera:read", "camera:search"},
                  jurisdiction_scope="police_station")
    authz = authorizer(Subject(officer_id=_x(), department_id=ps.id, role_code="psi", active=True),
                       [role], [], t)
    assert authz.authorize("camera", "read").allowed is True
    assert authz.authorize("camera", "delete").allowed is False  # not in grants
    assert authz.scoped_department_ids() == {ps.id}


def test_hierarchy_validation():
    assert validate_jurisdiction(
        DeptNode(_x(), "", "", DepartmentType.SUB_DIVISION, None, JurisdictionScope.CUSTOM, 0),
        DepartmentType.POLICE_STATION) is True
    assert hierarchy_level_for_type(DepartmentType.POLICE_STATION) == 6
    assert not validate_jurisdiction(
        DeptNode(_x(), "", "", DepartmentType.POLICE_STATION, None, JurisdictionScope.CUSTOM, 0),
        DepartmentType.DISTRICT)


def test_build_tree_forest():
    t = _tree()
    forest = build_tree(t)
    assert len(forest) == 1
    assert forest[0].code == "GJPOL"


# --- Password policy & lockout ---------------------------------------------------
def test_password_policy():
    assert password_meets_policy("Abcdef1!") is True
    assert password_meets_policy("short1!") is False
    problems = validate_password_policy("abcdefgh")
    assert "missing_uppercase" in problems


def test_lockout():
    assert is_locked_out(5, datetime.now(timezone.utc)) is True
    assert is_locked_out(5, datetime.now(timezone.utc) - timedelta(minutes=20)) is False
    assert should_lock(5) is True
    assert not should_lock(3)

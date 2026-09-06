"""Phase 6.1 IAM seed: default departments, roles, permissions and admin officer.

Seeding is idempotent. It populates the federation DB with:

* The Gujarat department hierarchy (representative subset).
* All catalog permissions and the built-in role-permission matrix.
* A default Super Admin officer for bootstrap access.

Used by tests, the validation harness and (optionally) Docker startup.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.federation.models import (
    Department,
    DepartmentKind,
    DepartmentType,
    Officer,
    OfficerAccountStatus,
    OfficerRank,
    Permission,
    PermissionAction,
    PermissionEffect,
    ResourceType,
    Role,
    RolePermission,
)
from src.federation.security.permissions import (
    ROLE_MATRIX,
    ROLE_PARENTS,
    all_permission_codes,
)


def _dept(**kw) -> Department:
    base = dict(
        kind=DepartmentKind.POLICE,
        dept_type=DepartmentType.OTHER,
        hierarchy_level=0,
        state="Gujarat",
        is_deleted=False,
    )
    base.update(kw)
    return Department(**base)


def build_default_departments() -> list[Department]:
    nodes: dict[str, Department] = {}

    def make(key: str, name: str, dtype: DepartmentType, parent: str | None = None,
             level: int = 0, code: str = "") -> Department:
        dept = _dept(
            code=code or key,
            name=name,
            dept_type=dtype,
            hierarchy_level=level,
            parent_id=nodes[parent].id if parent else None,
            jurisdiction_scope=_scope_for(dtype),
        )
        nodes[key] = dept
        return dept

    d = []
    d.append(make("police", "Gujarat Police", DepartmentType.STATE_HQ, None, 0, "GJPOL"))
    d.append(make("staterange1", "State HQ", DepartmentType.STATE_HQ, "police", 1, "GJHQ"))
    d.append(make("range1", "Range - Ahmedabad", DepartmentType.RANGE, "staterange1", 2, "GJRNG-AHM"))
    d.append(make("traffic", "Traffic Police", DepartmentType.TRAFFIC, "police", 1, "GJTRF"))
    d.append(make("cid", "CID Crime", DepartmentType.CID, "police", 1, "GJCID"))
    d.append(make("ats", "ATS", DepartmentType.ATS, "police", 1, "GJATS"))
    d.append(make("srp", "SRP", DepartmentType.SRP, "police", 1, "GJSRP"))
    d.append(make("cyber", "Cyber Crime", DepartmentType.CYBER_CRIME, "police", 1, "GJCYB"))
    d.append(make("controlroom", "Control Room", DepartmentType.CONTROL_ROOM, "police", 1, "GJCTRL"))
    d.append(make("home", "Home Department", DepartmentType.HOME_DEPARTMENT, None, 0, "GJHOME"))
    d.append(make("commissionerate_ahm", "Ahmedabad City Commissionerate",
                  DepartmentType.COMMISSIONERATE, "range1", 3, "GAHM"))
    d.append(make("dist_ahm", "Ahmedabad District", DepartmentType.DISTRICT,
                  "commissionerate_ahm", 4, "GAHMD"))
    d.append(make("subdiv_ahm", "Ahmedabad Sub Division", DepartmentType.SUB_DIVISION,
                  "dist_ahm", 5, "GAHMS"))
    d.append(make("ps_navrangpura", "Navrangpura Police Station",
                  DepartmentType.POLICE_STATION, "subdiv_ahm", 6, "GAHM-NAV"))
    return d


def _scope_for(dtype: DepartmentType) -> str:
    from src.federation.models import JurisdictionScope

    mapping = {
        DepartmentType.STATE_HQ: JurisdictionScope.STATE,
        DepartmentType.RANGE: JurisdictionScope.RANGE,
        DepartmentType.COMMISSIONERATE: JurisdictionScope.CITY,
        DepartmentType.DISTRICT: JurisdictionScope.DISTRICT,
        DepartmentType.SUB_DIVISION: JurisdictionScope.SUB_DIVISION,
        DepartmentType.POLICE_STATION: JurisdictionScope.POLICE_STATION,
        DepartmentType.OTHER: JurisdictionScope.CUSTOM,
    }
    return mapping.get(dtype, JurisdictionScope.CUSTOM).value


def build_default_roles() -> tuple[list[Role], list[RolePermission], list[Permission]]:
    permissions = [
        Permission(
            code=code,
            resource=ResourceType(code.split(":")[0]),
            action=PermissionAction(code.split(":")[1]),
            scope="department",
        )
        for code in all_permission_codes()
    ]
    perm_by_code = {p.code: p for p in permissions}

    roles: list[Role] = []
    role_permissions: list[RolePermission] = []
    parent_map: dict[str, str] = ROLE_PARENTS

    for code in ROLE_MATRIX:
        if code == "super_admin":
            continue  # created separately to avoid duplication
        role = Role(
            code=code,
            name=code.replace("_", " ").title(),
            parent_role_id=None,
            description=f"Built-in role: {code}",
            is_system=True,
            is_active=True,
        )
        roles.append(role)

    # Resolve parent role ids (by code) for role inheritance within seeded set.
    code_to_role = {r.code: r for r in roles}
    for role in roles:
        for parent_code in parent_map.get(role.code, ()):
            parent_role = code_to_role.get(parent_code)
            if parent_role is not None:
                role.parent_role_id = parent_role.id

    # Super Admin grants everything.
    super_admin = Role(
        code="super_admin", name="Super Admin", parent_role_id=None,
        description="Full platform administration", is_system=True, is_active=True,
    )
    roles.append(super_admin)

    for role in roles:
        grants = set(ROLE_MATRIX.get(role.code, set()))
        if role.code == "super_admin":
            grants |= set(all_permission_codes())
        for code in grants:
            p = perm_by_code.get(code)
            if p is None:
                continue
            role_permissions.append(
                RolePermission(role_id=role.id, permission_id=p.id, effect=PermissionEffect.ALLOW)
            )
    return roles, role_permissions, permissions


async def seed(db: AsyncSession, *, with_admin: bool = True) -> dict[str, int]:
    """Idempotently seed the IAM data. Returns counts of inserted rows.

    Safe to re-run: existing departments/roles by unique code are skipped.
    """
    counts = {"departments": 0, "roles": 0, "permissions": 0, "role_permissions": 0, "officers": 0}

    existing_dept = set(
        (await db.execute(select(Department.code))).scalars().all()
    )
    for d in build_default_departments():
        if d.code not in existing_dept:
            db.add(d)
            counts["departments"] += 1
    await db.flush()

    existing_perm = set(
        (await db.execute(select(Permission.code))).scalars().all()
    )
    permissions = build_default_roles()[2]
    perm_by_code: dict[str, Permission] = {}
    for p in permissions:
        if p.code not in existing_perm:
            db.add(p)
            counts["permissions"] += 1
        else:
            db.add(p)  # ensure in session
        perm_by_code[p.code] = p
    await db.flush()

    existing_role = set((await db.execute(select(Role.code))).scalars().all())
    roles, _, _ = build_default_roles()
    role_by_code: dict[str, Role] = {}
    for r in roles:
        if r.code not in existing_role:
            role_by_code[r.code] = r
            db.add(r)
            counts["roles"] += 1
        else:
            existing_role_row = (
                await db.execute(select(Role).where(Role.code == r.code))
            ).scalars().first()
            role_by_code[r.code] = existing_role_row
    await db.flush()

    # Resolve parent role ids now that roles are flushed.
    for r in roles:
        role_obj = role_by_code.get(r.code)
        if role_obj is None:
            continue
        for parent_code in ROLE_PARENTS.get(r.code, ()):
            parent = role_by_code.get(parent_code)
            if parent is not None:
                role_obj.parent_role_id = parent.id
    await db.flush()

    # Build role-permission associations from the flushed objects.
    existing_rp = set()
    existing_rp_rows = (
        await db.execute(select(RolePermission.role_id, RolePermission.permission_id))
    ).all()
    existing_rp = {(str(r), str(p)) for r, p in existing_rp_rows}
    for code, grants in ROLE_MATRIX.items():
        role_obj = role_by_code.get(code)
        if role_obj is None:
            continue
        effective = set(grants)
        if code == "super_admin":
            effective |= set(all_permission_codes())
        for perm_code in effective:
            perm_obj = perm_by_code.get(perm_code)
            if perm_obj is None:
                continue
            key = (str(role_obj.id), str(perm_obj.id))
            if key in existing_rp:
                continue
            db.add(
                RolePermission(
                    role_id=role_obj.id, permission_id=perm_obj.id,
                    effect=PermissionEffect.ALLOW,
                )
            )
            counts["role_permissions"] += 1

    if with_admin:
        admins = (await db.execute(
            select(Officer).where(Officer.badge_number == "ADMIN-0001")
        )).scalars().first()
        if admins is None:
            police = (
                await db.execute(select(Department).where(Department.code == "GJPOL"))
            ).scalars().first()
            admin_role = role_by_code.get("super_admin")
            db.add(
                Officer(
                    badge_number="ADMIN-0001",
                    full_name="Platform Super Admin",
                    email="admin@sentinel.gujarat.gov.in",
                    department_id=police.id if police else uuid.uuid4(),
                    rank=OfficerRank.DGP,
                    designation="System Administrator",
                    status=OfficerAccountStatus.ACTIVE,
                    role_id=admin_role.id if admin_role else None,
                    account_status="active",
                    mfa_enabled=False,
                )
            )
            counts["officers"] += 1

    await db.commit()
    return counts

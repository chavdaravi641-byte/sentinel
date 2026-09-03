"""Jurisdiction engine.

Models the department hierarchy and computes the set of department IDs (and
geographic scopes) a given officer may access. Data isolation builds on this:
an officer can only reach resources owned by departments within their
jurisdiction cone.

Hierarchy example
    Gujarat Police (STATE)
      └ State HQ (STATE)
          └ Range (RANGE)
              └ Commissionerate (CITY)
                  └ District (DISTRICT)
                      └ Sub Division (SUB_DIVISION)
                          └ Police Station (POLICE_STATION)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.federation.models import DepartmentType, JurisdictionScope


@dataclass
class DeptNode:
    id: UUID
    code: str
    name: str
    dept_type: DepartmentType
    parent_id: UUID | None
    jurisdiction: JurisdictionScope
    hierarchy_level: int
    district: str | None = None
    state: str | None = None
    children: list["DeptNode"] = field(default_factory=list)


def build_tree(departments: list[DeptNode]) -> list[DeptNode]:
    """Assemble a forest of :class:`DeptNode` from a flat department list."""
    by_id: dict[UUID, DeptNode] = {d.id: d for d in departments}
    roots: list[DeptNode] = []
    for d in departments:
        if d.parent_id and d.parent_id in by_id:
            by_id[d.parent_id].children.append(d)
        else:
            roots.append(d)
    return roots


def ancestry(departments: list[DeptNode], node_id: UUID) -> list[DeptNode]:
    """Return the node and all of its ancestors (leaf -> root)."""
    by_id = {d.id: d for d in departments}
    chain: list[DeptNode] = []
    cur = by_id.get(node_id)
    while cur is not None:
        chain.append(cur)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return chain


def descendants(departments: list[DeptNode], node_id: UUID) -> list[DeptNode]:
    """Return the node and all of its descendants (the jurisdiction cone)."""
    by_id = {d.id: d for d in departments}
    result: list[DeptNode] = []
    stack = [by_id[node_id]] if node_id in by_id else []
    while stack:
        n = stack.pop()
        result.append(n)
        stack.extend(n.children)
    return result


def jurisdiction_department_ids(
    officer_department_id: UUID,
    scope: JurisdictionScope | str,
    departments: list[DeptNode],
) -> set[UUID]:
    """Compute allowed department IDs for an officer given their scope.

    * STATE          -> all departments.
    * RANGE/CITY/DISTRICT/SUB_DIVISION/POLICE_STATION -> the officer's department
      plus all descendants (they oversee the whole cone at or below their node).
    * CAMERA / CUSTOM -> only the officer's own department.
    """
    scope_s = scope.value if isinstance(scope, JurisdictionScope) else str(scope)
    if scope_s == JurisdictionScope.STATE.value:
        return {d.id for d in departments}
    if scope_s in {JurisdictionScope.CAMERA.value, JurisdictionScope.CUSTOM.value}:
        return {officer_department_id}
    cone = descendants(departments, officer_department_id)
    return {d.id for d in cone}


def hierarchy_level_for_type(dept_type: DepartmentType) -> int:
    """Map a department type to a numeric hierarchy level."""
    order = {
        DepartmentType.HOME_DEPARTMENT: 0,
        DepartmentType.STATE_HQ: 1,
        DepartmentType.RANGE: 2,
        DepartmentType.COMMISSIONERATE: 3,
        DepartmentType.DISTRICT: 4,
        DepartmentType.SUB_DIVISION: 5,
        DepartmentType.POLICE_STATION: 6,
    }
    return order.get(dept_type, 6)


def validate_jurisdiction(parent: DeptNode | None, child_type: DepartmentType) -> bool:
    """Ensure child_type is a valid child under the given parent type."""
    valid_children: dict[DepartmentType, set[DepartmentType]] = {
        DepartmentType.HOME_DEPARTMENT: {
            DepartmentType.STATE_HQ, DepartmentType.TRAFFIC, DepartmentType.CID,
            DepartmentType.ATS, DepartmentType.SRP, DepartmentType.CYBER_CRIME,
            DepartmentType.CONTROL_ROOM, DepartmentType.SPECIAL_BRANCH, DepartmentType.OTHER,
        },
        DepartmentType.STATE_HQ: {DepartmentType.RANGE},
        DepartmentType.RANGE: {DepartmentType.COMMISSIONERATE, DepartmentType.DISTRICT},
        DepartmentType.COMMISSIONERATE: {DepartmentType.DISTRICT},
        DepartmentType.DISTRICT: {DepartmentType.SUB_DIVISION},
        DepartmentType.SUB_DIVISION: {DepartmentType.POLICE_STATION},
        DepartmentType.POLICE_STATION: set(),
    }
    if parent is None:
        return True
    allowed = valid_children.get(parent.dept_type, set())
    return child_type in allowed

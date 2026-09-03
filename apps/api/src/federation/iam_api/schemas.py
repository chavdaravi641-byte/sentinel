"""IAM API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.federation.models import (
    AccessMode,
    AccessStatus,
    DepartmentType,
    EmergencyStatus,
    JurisdictionScope,
    OfficerAccountStatus,
    OfficerRank,
    PermissionAction,
    PermissionEffect,
    ResourceType,
    Severity,
)


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Department ---------------------------------------------------------------
class DepartmentIn(BaseModel):
    code: str
    name: str
    dept_type: DepartmentType = DepartmentType.OTHER
    kind: str = "police"
    parent_id: UUID | None = None
    hierarchy_level: int = 0
    jurisdiction_scope: JurisdictionScope = JurisdictionScope.STATE
    district: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    description: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict)


class DepartmentOut(OrmModel):
    id: UUID
    code: str
    name: str
    dept_type: DepartmentType
    parent_id: UUID | None
    hierarchy_level: int
    jurisdiction_scope: JurisdictionScope
    district: str | None
    state: str | None
    latitude: float | None
    longitude: float | None
    address: str | None
    contact_email: str | None
    contact_phone: str | None
    is_deleted: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


# --- Officer --------------------------------------------------------------------
class OfficerIn(BaseModel):
    badge_number: str
    full_name: str
    email: str
    phone: str | None = None
    department_id: UUID
    rank: OfficerRank = OfficerRank.CONSTABLE
    designation: str | None = None
    assigned_district: str | None = None
    assigned_station: str | None = None
    role_code: str | None = None
    supervisor_id: UUID | None = None
    mfa_enabled: bool = False


class OfficerOut(OrmModel):
    id: UUID
    badge_number: str
    full_name: str
    email: str
    department_id: UUID
    rank: OfficerRank
    designation: str | None
    status: OfficerAccountStatus
    role_id: UUID | None
    supervisor_id: UUID | None
    mfa_enabled: bool
    last_login_at: datetime | None
    account_status: str


class OfficerStatusIn(BaseModel):
    status: OfficerAccountStatus


# --- Role -------------------------------------------------------------------------
class RoleIn(BaseModel):
    code: str
    name: str
    description: str | None = None
    parent_role_id: UUID | None = None
    resource_scope: str = "department"
    jurisdiction_scope: JurisdictionScope = JurisdictionScope.DISTRICT
    is_system: bool = False
    is_active: bool = True


class RoleOut(OrmModel):
    id: UUID
    code: str
    name: str
    parent_role_id: UUID | None
    resource_scope: str
    jurisdiction_scope: JurisdictionScope
    is_system: bool
    is_active: bool


class RolePermissionAssignIn(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)
    effect: PermissionEffect = PermissionEffect.ALLOW


# --- Permission -----------------------------------------------------------------
class PermissionIn(BaseModel):
    code: str
    resource: ResourceType
    action: PermissionAction
    description: str | None = None
    scope: str = "department"


class PermissionOut(OrmModel):
    id: UUID
    code: str
    resource: ResourceType
    action: PermissionAction
    description: str | None
    scope: str


# --- ABAC ------------------------------------------------------------------------
class AbacPolicyIn(BaseModel):
    name: str
    effect: PermissionEffect
    resource: str
    action: str
    conditions: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    is_active: bool = True


class AbacPolicyOut(OrmModel):
    id: UUID
    name: str
    effect: PermissionEffect
    resource: str
    action: str
    conditions: dict[str, Any]
    priority: int
    is_active: bool


# --- Audit -------------------------------------------------------------------------
class AuditFilterIn(BaseModel):
    action: str | None = None
    resource_type: str | None = None
    officer_id: UUID | None = None
    severity: Severity | None = None
    access_mode: AccessMode | None = None
    limit: int = 50
    offset: int = 0


class AuditOut(OrmModel):
    id: UUID
    at: datetime
    actor: str
    actor_department: str | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    officer_id: UUID | None
    department_id: UUID | None
    access_mode: AccessMode
    reason: str | None
    old_value: dict | None
    new_value: dict | None
    severity: Severity
    source_ip: str | None


# --- Emergency --------------------------------------------------------------------
class EmergencyRequestIn(BaseModel):
    reason: str
    case_reference: str | None = None
    duration_seconds: int = 1800
    grant: str = "cross_department_read"


class EmergencyApproveIn(BaseModel):
    approve: bool = True
    reason: str | None = None


class EmergencyOut(OrmModel):
    id: UUID
    officer_id: UUID
    department_id: UUID
    reason: str
    case_reference: str | None
    approved_by: UUID | None
    approval_time: datetime | None
    activated_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None
    status: EmergencyStatus
    duration_seconds: int
    grant: str


# --- Session -------------------------------------------------------------------------
class SessionOut(OrmModel):
    id: UUID
    officer_id: UUID
    created_at: datetime
    expires_at: datetime
    status: str
    rotation_count: int
    user_agent: str | None
    ip_address: str | None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


class AccessDecisionOut(BaseModel):
    allowed: bool
    reason: str
    matched_abac: str | None = None
    emergency_id: UUID | None = None

"""Federation entity models.

Includes the **Global Camera Registry** (24 canonical fields per camera) plus
supporting entities: Department, FederatedStream, RetentionPolicy,
HealthRecord, AuditLog, Secret and WebhookEndpoint.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.federation.db import FederationBase


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Vendor(str, enum.Enum):
    HIKVISION = "hikvision"
    DAHUA = "dahua"
    AXIS = "axis"
    BOSCH = "bosch"
    HANWHA = "hanwha"
    CPP_LUS = "cp_plus"
    ONVIF = "onvif"
    RTSP = "rtsp"
    OTHER = "other"


class CameraState(str, enum.Enum):
    REGISTERED = "registered"
    CONNECTED = "connected"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class DepartmentKind(str, enum.Enum):
    POLICE = "police"
    TRAFFIC = "traffic"
    TRANSPORT = "transport"
    MUNICIPAL = "municipal"
    FOREST = "forest"
    OTHER = "other"


class StreamProtocol(str, enum.Enum):
    RTSP = "rtsp"
    HLS = "hls"
    WEBRTC = "webrtc"
    MJPEG = "mjpeg"


# --- Phase 6.1 IAM enums -------------------------------------------------
class DepartmentType(str, enum.Enum):
    STATE_HQ = "state_hq"
    RANGE = "range"
    COMMISSIONERATE = "commissionerate"
    DISTRICT = "district"
    SUB_DIVISION = "sub_division"
    POLICE_STATION = "police_station"
    TRAFFIC = "traffic"
    CID = "cid"
    ATS = "ats"
    SRP = "srp"
    CYBER_CRIME = "cyber_crime"
    CONTROL_ROOM = "control_room"
    HOME_DEPARTMENT = "home_department"
    SPECIAL_BRANCH = "special_branch"
    OTHER = "other"


class JurisdictionScope(str, enum.Enum):
    STATE = "state"
    RANGE = "range"
    CITY = "city"
    DISTRICT = "district"
    SUB_DIVISION = "sub_division"
    POLICE_STATION = "police_station"
    CAMERA = "camera"
    CUSTOM = "custom"


class OfficerRank(str, enum.Enum):
    DGP = "dgp"
    ADGP = "adgp"
    IGP = "igp"
    DIG = "dig"
    CP = "cp"
    JCP = "jcp"
    SP = "sp"
    DCP = "dcp"
    ADSP = "adsp"
    ACP = "acp"
    DSP = "dsp"
    PI = "pi"
    PSI = "psi"
    ASI = "asi"
    HEAD_CONSTABLE = "head_constable"
    CONSTABLE = "constable"
    OPERATOR = "operator"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class AccessMode(str, enum.Enum):
    NORMAL = "normal"
    BREAK_GLASS = "break_glass"
    READ_ONLY = "read_only"
    INVESTIGATION = "investigation"
    SYSTEM = "system"
    API = "api"
    SERVICE_ACCOUNT = "service_account"


class PermissionEffect(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"


class ResourceType(str, enum.Enum):
    CAMERA = "camera"
    STREAM = "stream"
    VEHICLE = "vehicle"
    ANPR = "anpr"
    IDENTITY = "identity"
    ALERT = "alert"
    EVIDENCE = "evidence"
    TIMELINE = "timeline"
    REPORT = "report"
    DASHBOARD = "dashboard"
    ANALYTICS = "analytics"
    MAP = "map"
    CASE = "case"
    OFFICER = "officer"
    DEPARTMENT = "department"
    ROLE = "role"
    PERMISSION = "permission"
    AUDIT = "audit"
    SETTINGS = "settings"
    SYSTEM = "system"


class PermissionAction(str, enum.Enum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    ASSIGN = "assign"
    SEARCH = "search"
    EXPORT = "export"
    IMPORT = "import"
    CONFIGURE = "configure"
    MANAGE = "manage"
    VIEW_LIVE = "view_live"
    STREAM = "stream"
    DOWNLOAD = "download"
    SHARE = "share"
    ARCHIVE = "archive"


class AccessStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class OfficerAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"
    PENDING = "pending"


class EmergencyStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DENIED = "denied"


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALID = "invalid"


class Severity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Camera(FederationBase, TimestampMixin):
    """Global Camera Registry -- canonical 24-field record for every camera."""

    __tablename__ = "fed_cameras"

    # 1. identity
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 2. camera_id (vendor/operator assigned unique code)
    camera_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    # 3. name / display label
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 4. vendor
    vendor: Mapped[Vendor] = mapped_column(
        Enum(Vendor, name="fed_vendor", values_callable=lambda e: [m.value for m in e]),
        default=Vendor.ONVIF,
        nullable=False,
    )
    # 5. model
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 6. firmware version
    firmware: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # --- geographic context ---
    # 7. state (administrative region, e.g. Gujarat)
    region: Mapped[str] = mapped_column(String(64), default="Gujarat", nullable=False)
    # 8. district
    district: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # 9. taluka / sub-division
    taluka: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 10. locality / landmark
    locality: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 11. latitude
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 12. longitude
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- network addressing ---
    # 13. host / ip
    host: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 14. management port
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 15. rtsp_url (primary media endpoint)
    rtsp_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 16. stream_uri (absolute/relative media endpoint for federation)
    stream_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 17. protocol capabilities (list of supported StreamProtocol)
    protocols: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # 18. channel / sub-device
    channel: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- ownership & classification ---
    # 19. owning department
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_departments.id"), index=True, nullable=False
    )
    department: Mapped["Department"] = relationship(back_populates="cameras")  # type: ignore[name-defined]
    # 20. camera type (fixed/PTZ/speed/variable message sign/civilian feed)
    camera_type: Mapped[str] = mapped_column(String(64), default="fixed", nullable=False)
    # 21. public_accessible (whether generic live view is allowed)
    public_accessible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 22. classification / security tier (1..4)
    classification: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    # --- operational state ---
    # 23. runtime state
    state: Mapped[CameraState] = mapped_column(
        Enum(CameraState, name="fed_camera_state", values_callable=lambda e: [m.value for m in e]),
        default=CameraState.REGISTERED,
        nullable=False,
    )
    # 24. custom metadata (vendor specific / extra fields)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # acquired-from VMS (nullable; empty = direct device adapter)
    vms_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Camera camera_id={self.camera_id!r} vendor={self.vendor.value} state={self.state.value}>"


class Department(FederationBase, TimestampMixin):
    __tablename__ = "fed_departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[DepartmentKind] = mapped_column(
        Enum(DepartmentKind, name="fed_dept_kind", values_callable=lambda e: [m.value for m in e]),
        default=DepartmentKind.POLICE,
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Phase 6.1 enterprise extension (additive only) --------------------
    # dept_type is independent of the legacy `kind` column; both are retained.
    dept_type: Mapped[DepartmentType] = mapped_column(
        Enum(
            DepartmentType,
            name="fed_dept_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=DepartmentType.OTHER,
        nullable=False,
    )
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jurisdiction_scope: Mapped[JurisdictionScope] = mapped_column(
        Enum(
            JurisdictionScope,
            name="fed_jurisdiction_scope",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=JurisdictionScope.STATE,
        nullable=False,
    )
    district: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    cameras: Mapped[list["Camera"]] = relationship(back_populates="department")  # type: ignore[name-defined]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Department code={self.code!r} name={self.name!r}>"


class FederatedStream(FederationBase, TimestampMixin):
    __tablename__ = "fed_streams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_cameras.id"), index=True, nullable=False
    )
    protocol: Mapped[StreamProtocol] = mapped_column(
        Enum(StreamProtocol, name="fed_stream_protocol", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)


class RetentionPolicy(FederationBase, TimestampMixin):
    __tablename__ = "fed_retention"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    camera_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    archive_with_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class HealthRecord(FederationBase, TimestampMixin):
    __tablename__ = "fed_health"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_cameras.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # ok | degraded | offline
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AuditLog(FederationBase):
    __tablename__ = "fed_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    actor_department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), default="allow", nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # --- Phase 6.1 additive audit extension --------------------------------
    officer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    device: Mapped[str | None] = mapped_column(String(128), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operating_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(AccessMode, name="fed_access_mode", values_callable=lambda e: [m.value for m in e]),
        default=AccessMode.NORMAL,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="fed_severity", values_callable=lambda e: [m.value for m in e]),
        default=Severity.INFO,
        nullable=False,
        index=True,
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)


class Secret(FederationBase, TimestampMixin):
    __tablename__ = "fed_secrets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # username/password, token, tls
    value: Mapped[str] = mapped_column(Text, nullable=False)
    rotation_policy: Mapped[str] = mapped_column(String(32), default="never", nullable=False)


class WebhookEndpoint(FederationBase, TimestampMixin):
    __tablename__ = "fed_webhooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# --- Phase 6.1 IAM models -------------------------------------------------
class Officer(FederationBase, TimestampMixin):
    """Officer directory with rank, department, role and MFA/account state."""

    __tablename__ = "fed_officers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    badge_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_departments.id"), index=True, nullable=False
    )
    rank: Mapped[OfficerRank] = mapped_column(
        Enum(OfficerRank, name="fed_officer_rank", values_callable=lambda e: [m.value for m in e]),
        default=OfficerRank.CONSTABLE,
        nullable=False,
    )
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_district: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_station: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[OfficerAccountStatus] = mapped_column(
        Enum(
            OfficerAccountStatus,
            name="fed_officer_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=OfficerAccountStatus.PENDING,
        nullable=False,
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_roles.id"), nullable=True
    )
    role: Mapped["Role | None"] = relationship(foreign_keys=[role_id])  # type: ignore[name-defined]
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account_status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Officer badge={self.badge_number!r} name={self.full_name!r}>"


class Role(FederationBase, TimestampMixin):
    __tablename__ = "fed_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resource_scope: Mapped[str] = mapped_column(String(32), default="department", nullable=False)
    jurisdiction_scope: Mapped[JurisdictionScope] = mapped_column(
        Enum(
            JurisdictionScope,
            name="fed_role_jurisdiction_scope",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=JurisdictionScope.DISTRICT,
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Permission(FederationBase, TimestampMixin):
    __tablename__ = "fed_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    resource: Mapped[ResourceType] = mapped_column(
        Enum(
            ResourceType,
            name="fed_resource_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    action: Mapped[PermissionAction] = mapped_column(
        Enum(
            PermissionAction,
            name="fed_permission_action",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Resource scope this permission applies to: all / department / own
    scope: Mapped[str] = mapped_column(String(32), default="department", nullable=False)


class RolePermission(FederationBase):
    __tablename__ = "fed_role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_roles.id"), index=True, nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_permissions.id"), index=True, nullable=False
    )
    effect: Mapped[PermissionEffect] = mapped_column(
        Enum(
            PermissionEffect,
            name="fed_permission_effect",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PermissionEffect.ALLOW,
        nullable=False,
    )
    inherited_from: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class AbacPolicy(FederationBase, TimestampMixin):
    """Attribute-based access control policy (allow or deny, deny overrides)."""

    __tablename__ = "fed_abac_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    effect: Mapped[PermissionEffect] = mapped_column(
        Enum(
            PermissionEffect,
            name="fed_abac_effect",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # Conditions as JSON: {"field": "department_id", "op": "eq", "value": ...}
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EmergencyAccess(FederationBase):
    __tablename__ = "fed_emergency_access"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    officer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_officers.id"), index=True, nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_departments.id"), index=True, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    case_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approval_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[EmergencyStatus] = mapped_column(
        Enum(
            EmergencyStatus,
            name="fed_emergency_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=EmergencyStatus.REQUESTED,
        nullable=False,
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    grant: Mapped[str] = mapped_column(String(64), default="cross_department_read", nullable=False)


class OfficerSession(FederationBase):
    __tablename__ = "fed_officer_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    officer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_officers.id"), index=True, nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    access_token_jti: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="fed_session_status", values_callable=lambda e: [m.value for m in e]),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )
    rotation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CameraGroup(FederationBase, TimestampMixin):
    __tablename__ = "fed_camera_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_departments.id"), index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DepartmentCamera(FederationBase):
    """Associates a camera with a department (many-to-many via registry)."""

    __tablename__ = "fed_department_cameras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_departments.id"), index=True, nullable=False
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fed_cameras.id"), index=True, nullable=False
    )
    access_mode: Mapped[str] = mapped_column(String(32), default="owner", nullable=False)


__all__ = [
    "FederationBase",
    "TimestampMixin",
    "Vendor",
    "CameraState",
    "DepartmentKind",
    "StreamProtocol",
    "DepartmentType",
    "JurisdictionScope",
    "OfficerRank",
    "AccessMode",
    "PermissionEffect",
    "ResourceType",
    "PermissionAction",
    "AccessStatus",
    "OfficerAccountStatus",
    "EmergencyStatus",
    "SessionStatus",
    "Severity",
    "Camera",
    "Department",
    "FederatedStream",
    "RetentionPolicy",
    "HealthRecord",
    "AuditLog",
    "Secret",
    "WebhookEndpoint",
    "Officer",
    "Role",
    "Permission",
    "RolePermission",
    "AbacPolicy",
    "EmergencyAccess",
    "OfficerSession",
    "CameraGroup",
    "DepartmentCamera",
    "Any",
]

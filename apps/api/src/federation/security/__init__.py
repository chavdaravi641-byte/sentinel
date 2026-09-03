"""Phase 6.1 IAM -- Department registry, RBAC, ABAC, data isolation, audit,
emergency access and session security.

This package is self-contained (depends only on the federation models/schemas
and Python stdlib). Nothing here modifies Phase 1-5 code.
"""

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
from src.federation.security import abac, audit, breakglass, isolation, jurisdiction, permissions, rbac, session
from src.federation.security.abac import AbacPolicy, AccessRequest, evaluate, policy_matches
from src.federation.security.audit import AuditEvent, parse_user_agent, search_audit, write_audit
from src.federation.security.breakglass import (
    activate as breakglass_activate,
)
from src.federation.security.breakglass import (
    active_for_officer,
    approve as breakglass_approve,
    check_expiry,
    is_active as breakglass_is_active,
    request_access,
    revoke as breakglass_revoke,
)
from src.federation.security.isolation import AuthDecision, Authorizer, Subject, authorizer
from src.federation.security.jurisdiction import (
    DeptNode,
    build_tree,
    descendants,
    hierarchy_level_for_type,
    jurisdiction_department_ids,
    validate_jurisdiction,
)
from src.federation.security.permissions import (
    ACTIONS,
    RESOURCES,
    ROLE_JURISDICTION,
    ROLE_MATRIX,
    invalidate_permission_cache,
    perm,
    role_grants,
    role_has_permission,
)
from src.federation.security.rbac import DbRole, effective_permissions, has_permission
from src.federation.security.session import (
    SessionManager,
    is_locked_out,
    password_meets_policy,
    should_lock,
    validate_password_policy,
)

__all__ = [
    "abac",
    "audit",
    "breakglass",
    "isolation",
    "jurisdiction",
    "permissions",
    "rbac",
    "session",
    "AbacPolicy",
    "AccessRequest",
    "evaluate",
    "policy_matches",
    "AuditEvent",
    "parse_user_agent",
    "search_audit",
    "write_audit",
    "breakglass_activate",
    "active_for_officer",
    "breakglass_approve",
    "check_expiry",
    "breakglass_is_active",
    "request_access",
    "breakglass_revoke",
    "AuthDecision",
    "Authorizer",
    "Subject",
    "authorizer",
    "DeptNode",
    "build_tree",
    "descendants",
    "hierarchy_level_for_type",
    "jurisdiction_department_ids",
    "validate_jurisdiction",
    "ACTIONS",
    "RESOURCES",
    "ROLE_JURISDICTION",
    "ROLE_MATRIX",
    "invalidate_permission_cache",
    "perm",
    "role_grants",
    "role_has_permission",
    "DbRole",
    "effective_permissions",
    "has_permission",
    "SessionManager",
    "is_locked_out",
    "password_meets_policy",
    "should_lock",
    "validate_password_policy",
    "AccessMode",
    "AccessStatus",
    "DepartmentType",
    "EmergencyStatus",
    "JurisdictionScope",
    "OfficerAccountStatus",
    "OfficerRank",
    "PermissionAction",
    "PermissionEffect",
    "ResourceType",
    "Severity",
]

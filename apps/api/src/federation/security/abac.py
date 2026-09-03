"""Attribute-Based Access Control (ABAC) policy engine.

Policies are expressed as ``(effect, resource, action, conditions)`` where
``effect`` is ALLOW or DENY. Conditions are a small DSL over request attributes.

Combining rule: **deny-overrides** -- if any matching policy yields DENY, the
request is denied regardless of any ALLOW.

Supported condition operators (on simple attribute values):

* ``eq`` ==, ``ne`` !=, ``in`` value ∈ list, ``not_in``
* ``gt`` / ``gte`` / ``lt`` / ``lte`` (numeric/date)
* ``between`` (closed interval on numeric)
* ``contains`` (string containment for path/scope matches)
* ``within_hours`` (time window check; value is list of (start_hour, end_hour))
* ``is_true`` / ``is_false`` (boolean attribute)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.federation.models import PermissionEffect


@dataclass
class AccessRequest:
    """The subject/resource/context attributes of a single authorization check."""

    subject: dict[str, Any] = field(default_factory=dict)
    resource: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AbacPolicy:
    id: str | None = None
    name: str = ""
    effect: PermissionEffect = PermissionEffect.ALLOW
    resource: str = "*"
    action: str = "*"
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    is_active: bool = True


def _resolve(source: dict, path: str) -> Any:
    """Resolve a dotted attribute path against a dict (or a plain value)."""
    if isinstance(source, dict):
        node: Any = source
        for part in path.split("."):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
        return node
    return source.get(path) if isinstance(source, dict) else None


def _evaluate_condition(attr: Any, op: str, expected: Any) -> bool:
    try:
        if op == "eq":
            return bool(attr == expected)
        if op == "ne":
            return bool(attr != expected)
        if op == "in":
            return attr in (expected or [])
        if op == "not_in":
            return attr not in (expected or [])
        if op == "is_true":
            return bool(attr) is True
        if op == "is_false":
            return bool(attr) is False
        if op == "contains":
            return str(expected) in str(attr or "")
        if op in ("gt", "gte", "lt", "lte"):
            num = float(attr)
            exp = float(expected)
            return {"gt": num > exp, "gte": num >= exp, "lt": num < exp, "lte": num <= exp}[op]
        if op == "between":
            lo, hi = float(expected[0]), float(expected[1])
            return lo <= float(attr) <= hi
        if op == "within_hours":
            now = datetime.now(timezone.utc).hour
            start, end = int(expected[0]), int(expected[1])
            if start <= end:
                return start <= now <= end
            return now >= start or now <= end
        if op == "string_eq":
            return str(attr or "").lower() == str(expected or "").lower()
        if op == "equals_any_of_actor_or_resource":
            return attr in expected
    except (TypeError, ValueError, IndexError):
        return False
    return False


def policy_matches(policy: AbacPolicy, req: AccessRequest) -> bool:
    """Return True if every condition of the policy is satisfied."""
    if not policy.is_active:
        return False
    if policy.resource != "*" and policy.resource != req.resource.get("type"):
        # Wildcard or resource-type list support ("camera,stream").
        if not isinstance(policy.resource, str) or policy.resource not in req.resource.get("type", ""):
            expected = [s.strip() for s in policy.resource.split(",")] if policy.resource else []
            if req.resource.get("type") not in expected:
                return False
    if policy.action != "*" and policy.action != req.resource.get("action"):
        expected = [s.strip() for s in policy.action.split(",")] if policy.action else []
        if req.resource.get("action") not in expected:
            return False
    for path, cond in policy.conditions.items():
        op = cond.get("op", "eq") if isinstance(cond, dict) else "eq"
        value = cond.get("value") if isinstance(cond, dict) else cond
        # Look up attribute in subject -> resource -> context order, supporting
        # dotted paths and explicit source prefixes like "subject.", "resource.",
        for prefix, source in (("subject.", req.subject), ("resource.", req.resource),
                               ("context.", req.context)):
            if path.startswith(prefix):
                attr = _resolve(source, path[len(prefix):])
                break
        else:
            attr = _resolve(req.subject, path)
            if attr is None:
                attr = _resolve(req.resource, path)
            if attr is None:
                attr = _resolve(req.context, path)
        if not _evaluate_condition(attr, op, value):
            return False
    return True


def evaluate(policies: list[AbacPolicy], req: AccessRequest) -> tuple[bool, str | None]:
    """Evaluate the request under deny-overrides.

    Returns ``(allowed, matched_policy_name)``. If any matching policy DENIES,
    the result is denied. Otherwise the request is allowed iff at least one
    policy ALLOWs (or no policies exist, in which case it is allowed so that
    RBAC remains authoritative).
    """
    allow_match: str | None = None
    for p in sorted(policies, key=lambda x: x.priority, reverse=True):
        if not policy_matches(p, req):
            continue
        if p.effect == PermissionEffect.DENY:
            return False, p.name
        if p.effect == PermissionEffect.ALLOW:
            allow_match = allow_match or p.name
    # No explicit allow policy, but also no deny: allow (RBAC authoritative).
    return True, allow_match

"""Audit trail helpers for the camera registry.

Provides a lightweight, DB-agnostic :class:`AuditRecord` used by the endpoint
layer to persist rows to :class:`CameraAuditLog`. ``diff_before_after`` helps
record field-level change summaries for update / ownership events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.models.registry import RegistryEventType


@dataclass
class AuditRecord:
    event_type: RegistryEventType
    summary: str
    actor_id: str
    actor_role: str = ""
    scope: str | None = None
    camera_id: str | None = None
    registry_id: str | None = None
    cctv_code: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None

    def to_model_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "event_type": self.event_type,
            "summary": self.summary,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role or None,
            "scope": self.scope,
            "camera_id": self.camera_id,
            "registry_id": self.registry_id,
            "cctv_code": self.cctv_code,
            "before": self.before,
            "after": self.after,
        }
        return kwargs


def diff_before_after(before: dict[str, Any], after: dict[str, Any],
                      ignore: set[str] | None = None) -> dict[str, dict[str, Any]]:
    """Return the changed fields as ``{field: {"before": ..., "after": ...}}``."""
    ignore = ignore or {"created_at", "updated_at"}
    keys = set(before.keys()) | set(after.keys())
    changes: dict[str, dict[str, Any]] = {}
    for key in keys:
        if key in ignore:
            continue
        bv = before.get(key)
        av = after.get(key)
        if bv != av:
            changes[key] = {"before": bv, "after": av}
    return changes


def summarize_changes(changes: dict[str, dict[str, Any]], limit: int = 6) -> str:
    """Build a short human summary from a changed-fields map."""
    parts = [f"{k}: {v['before']!r} -> {v['after']!r}" for k, v in list(changes.items())[:limit]]
    if not parts:
        return "no changes"
    suffix = f" (+{len(changes) - limit} more)" if len(changes) > limit else ""
    return "; ".join(parts) + suffix


__all__: list[str] = ["AuditRecord", "diff_before_after", "summarize_changes"]

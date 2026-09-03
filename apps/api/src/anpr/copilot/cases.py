"""Phase 6 Copilot — Case workspace + audit log service.

Persists investigation cases and logs every action (audit trail). The service is
"work-file" oriented: an analyst creates a case, attaches evidence, writes notes,
bookmarks vehicles and exports the packaged investigation. Every mutating action
writes an `InvestigationLog` row recording the officer, timestamp, action, the
query (if any) and the evidence accessed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.copilot import (
    CaseBookmark,
    CaseEvidence,
    CaseNote,
    InvestigationCase,
    InvestigationLog,
)


class CaseWorkspace:
    """Operations over investigation cases with full audit logging."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    async def _audit(self, *, officer, action: str, query: str | None = None,
                     case_id=None, evidence: dict[str, Any] | None = None) -> None:
        self._db.add(
            InvestigationLog(
                action=action,
                query=query,
                case_id=case_id,
                evidence_accessed=evidence,
                officer_id=_uid(officer),
                officer_name=getattr(officer, "full_name", None) or getattr(officer, "email", None) or None,
            )
        )

    # ------------------------------------------------------------------ #
    async def create_case(self, *, title: str, description: str | None,
                          officer=None) -> InvestigationCase:
        case_number = f"SENT-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        case = InvestigationCase(
            case_number=case_number, title=title, description=description,
            status="open", owner_id=_uid(officer),
        )
        self._db.add(case)
        await self._audit(officer=officer, action="case.create", case_id=None,
                          query=f"title={title!r}")
        await self._db.commit()
        await self._db.refresh(case)
        return case

    async def get_case(self, case_id: uuid.UUID) -> InvestigationCase | None:
        return await self._db.get(InvestigationCase, case_id)

    async def open_case(self, case_id: uuid.UUID, *, officer=None) -> InvestigationCase | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        case.status = "open"
        case.closed_at = None
        await self._audit(officer=officer, action="case.open", case_id=case_id)
        await self._db.commit()
        return case

    async def close_case(self, case_id: uuid.UUID, *, officer=None) -> InvestigationCase | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        case.status = "closed"
        case.closed_at = datetime.now(timezone.utc)
        await self._audit(officer=officer, action="case.close", case_id=case_id)
        await self._db.commit()
        return case

    # ------------------------------------------------------------------ #
    async def add_evidence(self, case_id: uuid.UUID, *, kind: str, ref: str | None,
                           label: str | None, content: dict[str, Any] | None,
                           officer=None) -> CaseEvidence | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        ev = CaseEvidence(case_id=case_id, kind=kind, ref=ref, label=label,
                          content=content, added_by=_uid(officer))
        self._db.add(ev)
        await self._audit(officer=officer, action="evidence.add", case_id=case_id,
                          evidence={"kind": kind, "ref": ref})
        await self._db.commit()
        await self._db.refresh(ev)
        return ev

    async def add_note(self, case_id: uuid.UUID, *, body: str, officer=None) -> CaseNote | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        note = CaseNote(case_id=case_id, body=body, author_id=_uid(officer))
        self._db.add(note)
        await self._audit(officer=officer, action="note.add", case_id=case_id)
        await self._db.commit()
        await self._db.refresh(note)
        return note

    async def bookmark_vehicle(self, case_id: uuid.UUID, *, vehicle_uuid: str,
                               plate: str | None, reason: str | None,
                               officer=None) -> CaseBookmark | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        bm = CaseBookmark(case_id=case_id, vehicle_uuid=vehicle_uuid, plate=plate,
                          reason=reason, created_by=_uid(officer))
        self._db.add(bm)
        await self._audit(officer=officer, action="bookmark.add", case_id=case_id,
                          evidence={"vehicle_uuid": vehicle_uuid, "plate": plate})
        await self._db.commit()
        await self._db.refresh(bm)
        return bm

    # ------------------------------------------------------------------ #
    async def export_case(self, case_id: uuid.UUID, *, officer=None) -> dict[str, Any] | None:
        """Package a case (case + evidence + notes + bookmarks) for export."""
        case = await self.get_case(case_id)
        if case is None:
            return None
        evidence = (await self._db.execute(
            select(CaseEvidence).where(CaseEvidence.case_id == case_id)
            .order_by(CaseEvidence.added_at))).scalars().all()
        notes = (await self._db.execute(
            select(CaseNote).where(CaseNote.case_id == case_id)
            .order_by(CaseNote.created_at))).scalars().all()
        bookmarks = (await self._db.execute(
            select(CaseBookmark).where(CaseBookmark.case_id == case_id)
            .order_by(CaseBookmark.created_at))).scalars().all()
        await self._audit(officer=officer, action="case.export", case_id=case_id,
                          evidence={"evidence_count": len(evidence),
                                    "note_count": len(notes),
                                    "bookmark_count": len(bookmarks)})
        await self._db.commit()
        return {
            "case": {
                "id": str(case.id), "case_number": case.case_number,
                "title": case.title, "description": case.description,
                "status": case.status, "opened_at": case.opened_at.isoformat() if case.opened_at else None,
                "closed_at": case.closed_at.isoformat() if case.closed_at else None,
            },
            "evidence": [{"id": str(e.id), "kind": e.kind, "ref": e.ref, "label": e.label,
                          "content": e.content, "added_at": e.added_at.isoformat() if e.added_at else None}
                         for e in evidence],
            "notes": [{"id": str(n.id), "body": n.body,
                       "created_at": n.created_at.isoformat() if n.created_at else None} for n in notes],
            "bookmarks": [{"id": str(b.id), "vehicle_uuid": b.vehicle_uuid, "plate": b.plate,
                           "reason": b.reason,
                           "created_at": b.created_at.isoformat() if b.created_at else None}
                          for b in bookmarks],
        }

    # ------------------------------------------------------------------ #
    async def recent_cases(self, *, limit: int = 50, officer=None) -> list[Any]:
        rows = (await self._db.execute(
            select(InvestigationCase).order_by(InvestigationCase.created_at.desc()).limit(limit)
        )).scalars().all()
        return rows


def _uid(obj) -> uuid.UUID | None:
    if obj is None:
        return None
    try:
        return uuid.UUID(str(obj.id))
    except Exception:  # noqa: BLE001 - objects without .id become None
        return None


__all__ = ["CaseWorkspace"]

"""Phase 6 — Sentinel AI Police Copilot REST endpoints.

Exposes the investigation assistant: natural-language investigation, evidence
packages, PDF reports, a case workspace and a full audit log. Every response is
traceable to stored detections (never fabricated); when data is unavailable the
API returns an explicit `data_unavailable` note.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.anpr.copilot import CaseWorkspace, NaturalLanguagePlanner, PDFReportGenerator
from src.anpr.copilot.evidence import EvidenceBuilder
from src.anpr.copilot.executor import CopilotExecutor
from src.anpr.copilot.explain import ExplainableAI
from src.anpr.copilot.validation import run_validation
from src.models.copilot import InvestigationCase, InvestigationLog
from src.schemas.copilot import (
    BookmarkCreate,
    CaseCreate,
    EvidenceAttach,
    EvidenceRequest,
    InvestigateRequest,
    NoteCreate,
    ReportRequest,
)

router = APIRouter()


# ------------------------------------------------------------------------ #
# Investigation
# ------------------------------------------------------------------------ #
@router.post("/investigate", response_model=dict)
async def investigate(
    body: InvestigateRequest, *, db: DBDep, user: CurrentUser
) -> dict[str, Any]:
    """Turn a natural-language request into a structured, explainable
    investigation over stored detections."""
    planner = NaturalLanguagePlanner()
    plan = planner.plan(body.query)
    executor = CopilotExecutor(db)
    result = await executor.execute(plan)
    explanation = ExplainableAI().explain(plan, result)

    workspace = CaseWorkspace(db)
    case_number = body.case_number
    case = None
    if case_number:
        cases = (await db.execute(
            select(InvestigationCase)
            .where(InvestigationCase.case_number == case_number)
        )).scalars().all()
        case = cases[0] if cases else None
        if case:
            await workspace.add_evidence(
                case.id, kind="investigation", ref=plan.intent, label=body.query,
                content={"intent": plan.intent, "query": body.query},
                officer=user,
            )
    await workspace._audit(officer=user, action="investigate", query=body.query,
                           case_id=case.id if case else None,
                           evidence={"intent": plan.intent})
    await db.commit()

    return {
        "query": body.query,
        "plan": plan.to_dict(),
        "result": result,
        "explanation": explanation,
        "case_number": case.case_number if case else None,
    }


@router.post("/evidence", response_model=dict)
async def evidence_package(
    body: EvidenceRequest, *, db: DBDep, user: CurrentUser
) -> dict[str, Any]:
    """Assemble a self-contained evidence package for a vehicle."""
    executor = CopilotExecutor(db)
    sightings = await executor.load_detections(limit=4000)
    vehicle_obs = [o for o in sightings if str(o.get("vehicle_uuid", "")) == body.vehicle_uuid]
    if not vehicle_obs:
        return {
            "vehicle_uuid": body.vehicle_uuid,
            "evidence_package": None,
            "data_unavailable": "No stored detections for this vehicle; no evidence was fabricated.",
        }
    builder = EvidenceBuilder(db)
    package = await builder.build_for_vehicle(vehicle_obs, vehicle_uuid=body.vehicle_uuid)

    workspace = CaseWorkspace(db)
    if body.case_number:
        cases = (await db.execute(
            select(InvestigationCase)
            .where(InvestigationCase.case_number == body.case_number)
        )).scalars().all()
        case = cases[0] if cases else None
        if case:
            await workspace.add_evidence(
                case.id, kind="package", ref=body.vehicle_uuid,
                label=f"Evidence package for {package.get('plate', body.vehicle_uuid)}",
                content={"event_count": package.get("event_count", 0)}, officer=user,
            )
    await workspace._audit(officer=user, action="evidence.build", query=body.query,
                           evidence={"vehicle_uuid": body.vehicle_uuid,
                                     "plate": package.get("plate")})
    await db.commit()
    return package


@router.post("/report", response_model=dict)
async def generate_report(
    body: ReportRequest, *, db: DBDep, user: StaffUser
) -> dict[str, Any]:
    """Generate a PDF investigation report and write it to the audit log."""
    pdf = PDFReportGenerator().generate(body.investigation)
    filename = f"sentinel-report-{uuid.uuid4().hex[:8]}.pdf"
    await CaseWorkspace(db)._audit(
        officer=user, action="report.generate", query=None,
        evidence={"bytes": len(pdf), "filename": filename},
    )
    await db.commit()
    return {
        "filename": filename,
        "bytes": len(pdf),
        "format": "application/pdf",
        "preview_base64": _b64(pdf[:256]) if False else None,
    }


@router.get("/report/demo")
async def demo_report(*, db: DBDep, user: StaffUser) -> Response:
    """Generate a sample PDF report to prove the generator works end-to-end."""
    pdf = PDFReportGenerator().generate({
        "executive_summary": "Sample report generated by Sentinel Copilot validation.",
        "vehicle": {"plate": "GJ01AB1234", "vehicle_uuid": "demo"},
        "timeline": [],
        "evidence": [],
        "reasoning": ["This is a generated sample; no detections were consulted."],
        "chain_of_evidence": [],
        "data_availability": "demo",
    })
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=sentinel-demo.pdf"},
    )


# ------------------------------------------------------------------------ #
# Case workspace
# ------------------------------------------------------------------------ #
@router.post("/cases", response_model=dict)
async def create_case(
    body: CaseCreate, *, db: DBDep, user: CurrentUser
) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    case = await workspace.create_case(title=body.title, description=body.description, officer=user)
    return _case_read(case)


@router.get("/cases", response_model=dict)
async def recent_cases(
    *, db: DBDep, user: CurrentUser, limit: int = 50
) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    rows = await workspace.recent_cases(limit=limit)
    return {"cases": [_case_read(c) for c in rows]}


@router.get("/cases/{case_id}", response_model=dict)
async def get_case(case_id: uuid.UUID, *, db: DBDep, user: CurrentUser) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    case = await workspace.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_read(case)


@router.post("/cases/{case_id}/open", response_model=dict)
async def open_case(case_id: uuid.UUID, *, db: DBDep, user: CurrentUser) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    case = await workspace.open_case(case_id, officer=user)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_read(case)


@router.post("/cases/{case_id}/close", response_model=dict)
async def close_case(case_id: uuid.UUID, *, db: DBDep, user: CurrentUser) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    case = await workspace.close_case(case_id, officer=user)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_read(case)


@router.post("/cases/{case_id}/evidence", response_model=dict)
async def attach_evidence(
    case_id: uuid.UUID, body: EvidenceAttach, *, db: DBDep, user: CurrentUser
) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    ev = await workspace.add_evidence(case_id, kind=body.kind, ref=body.ref,
                                      label=body.label, content=body.content, officer=user)
    if ev is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"evidence_id": str(ev.id), "case_id": str(case_id), "kind": ev.kind}


@router.post("/cases/{case_id}/notes", response_model=dict)
async def add_note(
    case_id: uuid.UUID, body: NoteCreate, *, db: DBDep, user: CurrentUser
) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    note = await workspace.add_note(case_id, body=body.body, officer=user)
    if note is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"note_id": str(note.id), "case_id": str(case_id)}


@router.post("/cases/{case_id}/bookmarks", response_model=dict)
async def bookmark_vehicle(
    case_id: uuid.UUID, body: BookmarkCreate, *, db: DBDep, user: CurrentUser
) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    bm = await workspace.bookmark_vehicle(case_id, vehicle_uuid=body.vehicle_uuid,
                                          plate=body.plate, reason=body.reason, officer=user)
    if bm is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"bookmark_id": str(bm.id), "vehicle_uuid": bm.vehicle_uuid}


@router.get("/cases/{case_id}/export", response_model=dict)
async def export_case(case_id: uuid.UUID, *, db: DBDep, user: CurrentUser) -> dict[str, Any]:
    workspace = CaseWorkspace(db)
    export = await workspace.export_case(case_id, officer=user)
    if export is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return export


@router.get("/cases/{case_id}/audit", response_model=dict)
async def case_audit(case_id: uuid.UUID, *, db: DBDep, user: CurrentUser) -> dict[str, Any]:
    rows = (await db.execute(
        select(InvestigationLog)
        .where(InvestigationLog.case_id == case_id)
        .order_by(InvestigationLog.created_at.desc()).limit(500)
    )).scalars().all()
    return {
        "case_id": str(case_id),
        "entries": [
            {"id": str(log_entry.id), "officer_id": str(log_entry.officer_id) if log_entry.officer_id else None,
             "officer_name": log_entry.officer_name, "action": log_entry.action, "query": log_entry.query,
             "evidence_accessed": log_entry.evidence_accessed,
             "created_at": log_entry.created_at.isoformat() if log_entry.created_at else None}
            for log_entry in rows
        ],
        "count": len(rows),
    }


# ------------------------------------------------------------------------ #
# Validation
# ------------------------------------------------------------------------ #
@router.post("/validate", response_model=dict)
async def validate_copilot(*, user: StaffUser) -> dict[str, Any]:
    """Run the Phase 6 validation harness (labelled synthetic corpus)."""
    return run_validation()


def _case_read(case) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "case_number": case.case_number,
        "title": case.title,
        "description": case.description,
        "status": case.status,
        "owner_id": str(case.owner_id) if case.owner_id else None,
        "opened_at": case.opened_at.isoformat() if case.opened_at else None,
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
    }


def _b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode()

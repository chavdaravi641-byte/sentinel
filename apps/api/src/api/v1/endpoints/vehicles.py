"""Vehicle forensic + interception endpoints (grand-finale killer features).

* ``GET /vehicles/{plate}/dossier`` — export the court-admissible, tamper-
  evident forensic dossier as JSON, Markdown or PDF.
* ``GET /vehicles/{plate}/dossier/verify`` — re-seal and confirm integrity.
* ``POST /vehicles/{plate}/interception`` — compute the predictive corridor
  interception vector with PCR arrival windows.

All endpoints are RBAC-guarded by the existing `StaffUser`/`CurrentUser` deps.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.core.logging import log
from src.forensics.dossier import (
    build_dossier,
    render_dossier_markdown,
    render_dossier_pdf,
)
from src.schemas.forensics import DossierVerifyRead
from src.schemas.interception import (
    InterceptionRequest,
    InterceptionVectorRead,
)

router = APIRouter()


def _norm(plate: str) -> str:
    return plate.upper().replace(" ", "")


@router.get("/{plate}/dossier", response_model=None)
async def export_dossier(
    plate: str,
    *,
    db: DBDep,
    _: CurrentUser,
    format: str = Query(default="json", pattern="^(json|markdown|pdf)$"),
) -> Response | dict:
    """Export the sealed forensic dossier for a plate in the requested format."""
    normalized = _norm(plate)
    if len(normalized) < 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Registration number too short.",
        )
    dossier = await build_dossier(db, normalized)

    if format == "pdf":
        pdf_bytes = render_dossier_pdf(dossier)
        log.info(
            "forensics.dossier.export",
            plate=normalized,
            format="pdf",
            sightings=dossier.counts()["sightings"],
        )
        filename = f"dossier_{normalized}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Dossier-Integrity": dossier.integrity_sha256,
            },
        )

    if format == "markdown":
        md = render_dossier_markdown(dossier)
        log.info(
            "forensics.dossier.export",
            plate=normalized,
            format="markdown",
            sightings=dossier.counts()["sightings"],
        )
        return PlainTextResponse(
            content=md,
            media_type="text/markdown",
            headers={"X-Dossier-Integrity": dossier.integrity_sha256},
        )

    payload = dossier.to_dict(with_sightings=True)
    log.info(
        "forensics.dossier.export",
        plate=normalized,
        format="json",
        sightings=dossier.counts()["sightings"],
    )
    return payload


@router.get("/{plate}/dossier/verify", response_model=DossierVerifyRead)
async def verify_dossier(
    plate: str,
    *,
    db: DBDep,
    _: CurrentUser,
) -> DossierVerifyRead:
    """Re-seal a freshly-built dossier and confirm the integrity chain holds."""
    normalized = _norm(plate)
    dossier = await build_dossier(db, normalized)
    return DossierVerifyRead(
        plate=normalized,
        integrity_sha256=dossier.integrity_sha256,
        valid=dossier.verify(),
    )


@router.post(
    "/{plate}/interception",
    response_model=InterceptionVectorRead,
)
async def predict_interception(
    plate: str,
    body: InterceptionRequest,
    *,
    db: DBDep,
    _: StaffUser,
) -> InterceptionVectorRead:
    """Predict the top-K corridor interception nodes + PCR arrival windows for
    a watchlist vehicle that just triggered at ``trigger_camera``."""
    from src.anpr.interception import interception_vector

    normalized = _norm(plate)
    vector = await interception_vector(
        db,
        plate=normalized,
        trigger_camera=body.trigger_camera,
        observed_ts=body.observed_ts,
        speed_kph=body.speed_kph,
        radius_km=body.radius_km,
    )
    log.info(
        "anpr.interception.compute",
        plate=normalized,
        trigger=body.trigger_camera,
        nodes=len(vector.nodes),
    )
    return InterceptionVectorRead(**vector.to_dict())

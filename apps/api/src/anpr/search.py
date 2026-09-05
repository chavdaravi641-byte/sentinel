"""Search engine: intelligent queries over recognized plates and vehicles.

Provides prepared SQLAlchemy queries covering the full Phase 4 search surface:

* plate number (exact)
* partial plate (substring / ILIKE)
* state code
* color
* vehicle type
* manufacturer (make)
* model
* camera
* date range

Every query returns `PlateDetection` rows enveloped in a `Paginated` shape so the
REST layer can stamp page metadata. Field matching uses normalized (uppercase,
alphanumeric-only) plate strings so a search for `gj01` matches `GJ01-AB-1234`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select

from src.anpr.primitives import normalize_plate
from src.models.anpr import PlateDetection


class SearchEngine:
    """Builds + executes ANPR search queries against Postgres."""

    def _base(self) -> Select:
        return select(PlateDetection)

    def _apply(
        self,
        stmt: Select,
        *,
        plate: str | None = None,
        partial: str | None = None,
        state: str | None = None,
        color: str | None = None,
        vehicle_type: str | None = None,
        make: str | None = None,
        model: str | None = None,
        camera_id: UUID | str | None = None,
        camera_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Select:
        if plate:
            stmt = stmt.where(PlateDetection.normalized_plate == normalize_plate(plate).upper())
        if partial:
            escaped = normalize_plate(partial).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{escaped}%"
            stmt = stmt.where(PlateDetection.normalized_plate.like(like, escape="\\"))
        if state:
            stmt = stmt.where(PlateDetection.state_code == state.upper())
        if color:
            stmt = stmt.where(PlateDetection.color == color.lower())
        if vehicle_type:
            stmt = stmt.where(PlateDetection.vehicle_type == vehicle_type.lower())
        if make:
            escaped = make.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(PlateDetection.make.ilike(f"%{escaped}%", escape="\\"))
        if model:
            escaped = model.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(PlateDetection.model.ilike(f"%{escaped}%", escape="\\"))
        if camera_id:
            stmt = stmt.where(PlateDetection.camera_id == UUID(str(camera_id)))
        if camera_name:
            escaped = camera_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(
                or_(
                    PlateDetection.camera_name.ilike(f"%{escaped}%", escape="\\"),
                    PlateDetection.location.ilike(f"%{escaped}%", escape="\\"),
                )
            )
        if start:
            stmt = stmt.where(PlateDetection.ts >= start)
        if end:
            stmt = stmt.where(PlateDetection.ts <= end)
        return stmt

    async def search(
        self,
        db,
        *,
        plate: str | None = None,
        partial: str | None = None,
        state: str | None = None,
        color: str | None = None,
        vehicle_type: str | None = None,
        make: str | None = None,
        model: str | None = None,
        camera_id: UUID | str | None = None,
        camera_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        stmt = self._apply(
            self._base(),
            plate=plate, partial=partial, state=state, color=color,
            vehicle_type=vehicle_type, make=make, model=model,
            camera_id=camera_id, camera_name=camera_name, start=start, end=end,
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar_one() or 0)
        ordered = stmt.order_by(PlateDetection.ts.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(ordered)).scalars().all()
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size else 0,
        }


__all__ = ["SearchEngine"]

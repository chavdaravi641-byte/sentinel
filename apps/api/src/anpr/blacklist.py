"""Blacklist engine.

Holds a normalized in-memory set of blacklisted plates and syncs lazily from
the Postgres `anpr_blacklist` table every `ANPR_BLACKLIST_SYNC_SECONDS` so hot
plate matches never hit the database. Storage rows are written by the pipeline's
evidence/store path; this module owns the read (match / sync) side plus
memory-only helpers used by the REST layer.
"""

from __future__ import annotations

from threading import Lock

from src.anpr.primitives import normalize_plate
from src.core.logging import log


class BlacklistEngine:
    """Thread-safe in-memory blacklist with periodic DB sync."""

    def __init__(
        self,
        *,
        strict_eq: bool = True,
        sync_seconds: float = 60.0,
    ) -> None:
        self.strict_eq = strict_eq
        self.sync_seconds = sync_seconds
        self._lock = Lock()
        self._plates: set[str] = set()
        self._meta: dict[str, dict] = {}
        self._last_sync = 0.0
        self._dirty = True

    # ------------------------------------------------------------------ #
    def upsert(self, plate: str, reason: str | None = None, note: str | None = None) -> None:
        norm = normalize_plate(plate)
        with self._lock:
            self._plates.add(norm)
            self._meta[norm] = {"reason": reason, "note": note}

    def remove(self, plate: str) -> bool:
        norm = normalize_plate(plate)
        with self._lock:
            existed = norm in self._plates
            self._plates.discard(norm)
            self._meta.pop(norm, None)
        return existed

    def is_blacklisted(self, plate: str) -> bool:
        norm = normalize_plate(plate) if self.strict_eq else plate.upper()
        with self._lock:
            return norm in self._plates

    def match(self, plate: str) -> dict | None:
        """Return blacklist metadata for a plate, or None when not blacklisted."""
        norm = normalize_plate(plate) if self.strict_eq else plate.upper()
        with self._lock:
            if norm not in self._plates:
                return None
            return {"plate": norm, **(self._meta.get(norm) or {})}

    def all(self) -> list[dict]:
        with self._lock:
            return [
                {"plate": p, **(self._meta.get(p) or {})}
                for p in sorted(self._plates)
            ]

    def mark_synced(self) -> None:
        with self._lock:
            self._dirty = False

    # ------------------------------------------------------------------ #
    async def sync_from_db(self, db) -> None:
        """Reload the in-memory set from the DB (called periodically)."""
        from sqlalchemy import select
        from src.models.anpr import BlacklistEntry

        rows = (await db.execute(select(BlacklistEntry).where(BlacklistEntry.active.is_(True)))).scalars().all()
        fresh: dict[str, dict] = {}
        for row in rows:
            fresh[normalize_plate(row.plate)] = {"reason": row.reason, "note": row.note}
        with self._lock:
            self._plates = set(fresh.keys())
            self._meta = fresh
            self._dirty = False
        log.info("anpr.blacklist.synced", count=len(self._plates))


__all__ = ["BlacklistEngine"]

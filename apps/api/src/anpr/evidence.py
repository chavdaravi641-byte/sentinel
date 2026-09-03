"""Evidence store: persists detection artifacts to disk with content hashing.

Every recognized plate produces three evidence artifacts:

* **frame** — the full analysed frame (JPEG)
* **plate** — the rectified/upright plate crop
* **vehicle** — the vehicle crop

Each is written as a JPEG under `{ANPR_EVIDENCE_DIR}/{camera_id}/{kind}-{uuid}.jpg`
with a SHA-256 content hash and byte size recorded on the parent `EvidenceRecord`
row. Artifacts are served to the frontend over the authenticated REST layer
(never exposed as raw static files). All file I/O runs on the shared executor so
the inference/capture loop never blocks.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np

from src.anpr.primitives import EvidenceDoc
from src.core.config import settings
from src.core.logging import log


class EvidenceStore:
    """Writes and hashes ANPR evidence artifacts on disk."""

    def __init__(self, *, enabled: bool = True, root_dir: str | None = None) -> None:
        self.enabled = enabled
        self.root_dir = Path(root_dir or settings.ANPR_EVIDENCE_DIR)
        if self.enabled:
            try:
                self.root_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                self.enabled = False

    # ------------------------------------------------------------------ #
    def save_frame(self, camera_id: str, frame: Any) -> EvidenceDoc | None:
        return self._save(camera_id, "frame", frame)

    def save_plate(self, camera_id: str, plate_img: Any) -> EvidenceDoc | None:
        return self._save(camera_id, "plate", plate_img)

    def save_vehicle(self, camera_id: str, vehicle_img: Any) -> EvidenceDoc | None:
        return self._save(camera_id, "vehicle", vehicle_img)

    def _save(self, camera_id: str, kind: str, image: Any) -> EvidenceDoc | None:
        if not self.enabled or image is None:
            return None
        directory = self.root_dir / str(camera_id)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            filename = f"{kind}-{uuid4().hex[:12]}.jpg"
            path = directory / filename
            if not self._encode_jpeg(path, image):
                return None
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()  # noqa: S324 - content hash for integrity, not auth
            return EvidenceDoc(
                kind=kind,
                path=str(path),
                sha256=digest,
                size_bytes=len(data),
            )
        except OSError as exc:
            log.warning("anpr.evidence.save_failed", kind=kind, error=str(exc))
            return None

    @staticmethod
    def _encode_jpeg(path: Path, image: Any) -> bool:
        ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            return False
        try:
            path.write_bytes(buf.tobytes())
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------ #
    def asset_path(self, record: Any, kind: str) -> str | None:
        """Validate + resolve an artifact path, guarding against path traversal."""
        base = self.root_dir.resolve()
        raw = getattr(record, f"{kind}_path", None)
        if not raw:
            return None
        path = Path(str(raw)).resolve()
        # Must live under the evidence root, reference the same camera dir and
        # carry the expected artifact prefix.
        if base not in path.parents:
            return None
        if str(path.parent.name) != str(record.camera_id):
            return None
        if not path.name.lower().startswith(f"{kind}-"):
            return None
        return str(path)


__all__ = ["EvidenceStore"]

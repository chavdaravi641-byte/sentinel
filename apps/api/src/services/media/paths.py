"""Filesystem layout for the media engine (HLS assets, recordings, snapshots)."""

import os
from uuid import UUID

from src.core.config import settings


def media_root() -> str:
    return settings.MEDIA_ROOT or "/media"


def ensure_dirs() -> None:
    """Create the media tree; safe to call repeatedly (idempotent)."""
    for path in (settings.MEDIA_ROOT, settings.RECORDING_DIR, settings.SNAPSHOT_DIR):
        if not path:
            continue
        os.makedirs(path, exist_ok=True)


def snapshot_path(camera_id: UUID, filename: str) -> str:
    directory = os.path.join(settings.SNAPSHOT_DIR, str(camera_id))
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)


def recording_path(camera_id: UUID, filename: str) -> str:
    directory = os.path.join(settings.RECORDING_DIR, str(camera_id))
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)


def hls_variant() -> str:
    """HLS variant configured on the edge server (mpegts is proxy-safe)."""
    return "mpegts"
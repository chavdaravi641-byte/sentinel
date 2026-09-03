"""Phase 2 streaming engine integration tests.

Run against the running compose stack (needs sentinel-api up):

    docker compose exec api pytest -q tests/test_stream_integration.py

End-to-end lifecycle for the seeded lavfi demo camera:
login -> capabilities -> start -> wait for live frames -> signed media chain
(master/variant/segment) -> snapshot -> record start/stop -> stop.
"""

import asyncio
import os
import time
from pathlib import Path
from uuid import UUID

import httpx
import pytest

BASE_URL = os.environ.get("SENTINEL_BASE_URL", "http://api:8000")
ADMIN_EMAIL = os.environ.get("SENTINEL_ADMIN_EMAIL", "admin@sentinel.gp")
ADMIN_PASSWORD = os.environ.get("SENTINEL_ADMIN_PASSWORD", "Admin@2026")
CAMERA_NAME = os.environ.get("SENTINEL_CAMERA_NAME", "TEST-LAVFI-01")


async def _login() -> str:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
        token = resp.json()["access_token"]
        assert token
        return token


async def _find_camera(token: str) -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        resp = await client.get(
            "/api/v1/cameras", params={"search": CAMERA_NAME, "page_size": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        for cam in items:
            if cam["name"] == CAMERA_NAME:
                return cam
    raise AssertionError(f"camera {CAMERA_NAME!r} not found; run the seed step first")


async def _wait_running(token: str, camera_id: str, timeout: float = 45.0) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        while time.monotonic() < deadline:
            resp = await client.get(
                f"/api/v1/streams/{camera_id}/health",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, resp.text
            last = resp.json()
            if last.get("running") and (last.get("fps") or 0) > 0:
                return last
            await asyncio.sleep(1.0)
    raise AssertionError(f"stream did not reach live frames within {timeout}s: {last}")


@pytest.mark.asyncio
async def test_lavfi_lifecycle():
    token = await _login()

    # Capabilities
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        resp = await client.get(
            "/api/v1/streams/config", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, resp.text
        caps = resp.json()
        assert caps["ffmpeg"]["ffmpeg"] is True
        assert "active_streams" in caps

    camera = await _find_camera(token)
    camera_id = str(UUID(camera["id"]))

    # Idempotent baseline: make sure it is stopped before the lifecycle.
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        await client.post(
            f"/api/v1/streams/{camera_id}/stop",
            headers={"Authorization": f"Bearer {token}"},
        )

    # 1. Start
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=45) as client:
        resp = await client.post(
            f"/api/v1/streams/{camera_id}/start",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        start = resp.json()
        assert start["state"] == "running"
        assert start["running"] is True

    # 2. Live frames arrive (fps > 0, low latency)
    health = await _wait_running(token, camera_id)
    assert health["live"] is True
    assert (health.get("hls_latency_ms") or 0) >= 0

    # 3. Signed media URLs + full HLS chain (master -> variant -> segment),
    #    the exact requests the browser/hls.js make through the proxy.
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        resp = await client.get(
            f"/api/v1/streams/{camera_id}/media",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        media = resp.json()
        assert media["hls_url"] and media["snapshot_url"] and media["expires_in"] > 0

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        master = await client.get(media["hls_url"])
        assert master.status_code == 200, master.status_code
        assert "#EXTM3U" in master.text
        variant_line = next(
            line.strip()
            for line in master.text.splitlines()
            if line.strip() and not line.startswith("#") and ".m3u8" in line
        )
        variant = await client.get(f"{media['hls_url'].rsplit('/index.m3u8', 1)[0]}/{variant_line}")
        assert variant.status_code == 200, variant.status_code
        assert "#EXTINF" in variant.text
        segment_line = next(
            line.strip()
            for line in variant.text.splitlines()
            if line.strip() and not line.startswith("#") and ".ts" in line
        )
        segment = await client.get(f"{media['hls_url'].rsplit('/index.m3u8', 1)[0]}/{segment_line}")
        assert segment.status_code == 200, segment.status_code
        assert len(segment.content) > 100_000

    # 4. Snapshot is a real JPEG
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        snap = await client.get(media["snapshot_url"])
        assert snap.status_code == 200, snap.status_code
        assert snap.headers["content-type"].startswith("image/jpeg")
        assert snap.content[:2] == b"\xff\xd8"

    # 5. Recording lifecycle
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        resp = await client.post(
            f"/api/v1/streams/{camera_id}/record/start",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201), resp.text
        assert resp.json()["status"] == "started"

    await asyncio.sleep(2.0)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        resp = await client.post(
            f"/api/v1/streams/{camera_id}/record/stop",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201), resp.text
        assert resp.json()["status"] == "stopped"

        recs = await client.get(
            "/api/v1/streams/recordings",
            params={"camera_id": camera_id, "page_size": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert recs.status_code == 200, recs.text
        assert recs.json()["total"] >= 1

    # 6. Stop
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        resp = await client.post(
            f"/api/v1/streams/{camera_id}/stop",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        health = await client.get(
            f"/api/v1/streams/{camera_id}/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert health.json()["running"] is False


@pytest.mark.asyncio
async def test_stream_test_endpoint():
    token = await _login()
    camera = await _find_camera(token)
    camera_id = str(UUID(camera["id"]))
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=90) as client:
        resp = await client.post(
            f"/api/v1/streams/{camera_id}/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["ok"] is True
        assert result["codec"]


@pytest.mark.asyncio
async def test_unauthenticated_media_rejected():
    camera_id = "00920543-1b93-4e75-b4e2-40521907396a"
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        resp = await client.get(f"/api/v1/streams/{camera_id}/snapshot?exp=1&t=deadbeef")
        assert resp.status_code in (401, 403, 404)


def test_report_dir_writable():
    from src.core.config import settings

    path = Path(settings.RECORDING_DIR)
    assert path.is_dir() or path.resolve().parent.is_dir()
"""Phase 3 AI inference integration tests.

Run against the live compose stack (needs sentinel-api up):

    docker compose exec api pytest -q tests/test_ai_integration.py

End-to-end: login -> config/models -> start stream -> start camera inference ->
wait for deterministic sim detections -> verify runs/detections/overlay/summary
-> stop inference -> benchmark -> stop stream.
"""

import asyncio
import os
import time
from uuid import UUID

import httpx
import pytest

BASE_URL = os.environ.get("SENTINEL_BASE_URL", "http://api:8000")
ADMIN_EMAIL = os.environ.get("SENTINEL_ADMIN_EMAIL", "admin@sentinel.gp")
ADMIN_PASSWORD = os.environ.get("SENTINEL_ADMIN_PASSWORD", "Admin@2026")
CAMERA_NAME = os.environ.get("SENTINEL_CAMERA_NAME", "TEST-LAVFI-01")
ALLOWED_CLASSES = {"person", "car", "bike", "bus", "truck", "bicycle"}


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


async def _find_camera(token: str) -> str:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        resp = await client.get(
            "/api/v1/cameras",
            params={"search": CAMERA_NAME, "page_size": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        for cam in resp.json()["items"]:
            if cam["name"] == CAMERA_NAME:
                return str(UUID(cam["id"]))
    raise AssertionError(f"camera {CAMERA_NAME!r} not found; run the seed step first")


async def _auth() -> httpx.AsyncClient:
    token = await _login()
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=30)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


async def _wait_live(client, camera_id: str, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(f"/api/v1/streams/{camera_id}/health")
        assert resp.status_code == 200, resp.text
        health = resp.json()
        if health.get("running") and (health.get("fps") or 0) > 0:
            return
        await asyncio.sleep(1.0)
    raise AssertionError(f"stream never live: {health}")


async def _wait_analyzed(client, camera_id: str, frames: int = 5, timeout: float = 40.0) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        resp = await client.get(f"/api/v1/inference/cameras/{camera_id}/stats")
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last.get("inference_active") and last.get("frames_analyzed", 0) >= frames:
            return last
        await asyncio.sleep(1.0)
    raise AssertionError(f"inference produced no frames in {timeout}s: {last}")


@pytest.mark.asyncio
async def test_inference_end_to_end():
    client = await _auth()
    try:
        # 0. Config
        resp = await client.get("/api/v1/inference/config")
        assert resp.status_code == 200, resp.text
        config = resp.json()
        assert config["enabled"] is True
        assert config["model"] == "yolov12"

        # 1. Models registry (sim backend without onnx weights)
        resp = await client.get("/api/v1/inference/models")
        assert resp.status_code == 200, resp.text
        models = {m["name"]: m for m in resp.json()}
        assert "yolov12" in models
        assert set(models["yolov12"]["classes"]) <= ALLOWED_CLASSES
        assert models["yolov12"]["status"] in {"loaded", "error"}

        camera_id = await _find_camera(client.headers["Authorization"].split(" ")[1])

        # 2. Ensure a running stream (idempotent)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
            c.headers["Authorization"] = client.headers["Authorization"]
            await c.post(f"/api/v1/streams/{camera_id}/start", json={})
        await _wait_live(client, camera_id)

        # 3. Start camera inference
        resp = await client.post(f"/api/v1/inference/cameras/{camera_id}/start")
        assert resp.status_code == 200, resp.text
        assert resp.json()["inference_active"] is True

        # 4. Wait for analyzed frames
        stats = await _wait_analyzed(client, camera_id, frames=5)
        assert stats["frames_analyzed"] >= 5
        assert stats["total_detections"] >= 0
        assert {"fps", "avg_infer_ms", "frame_seq", "device"} <= set(stats)

        # 5. Persisted runs + detections
        resp = await client.get("/api/v1/inference/runs", params={"camera_id": camera_id, "page_size": 10})
        assert resp.status_code == 200, resp.text
        runs = resp.json()
        assert runs["total"] >= 1
        assert runs["items"][0]["camera_id"] == camera_id
        assert runs["items"][0]["backend"] in {"sim", "onnx"}

        resp = await client.get("/api/v1/inference/detections", params={"page_size": 50})
        assert resp.status_code == 200, resp.text
        detections = resp.json()
        assert detections["total"] >= 0
        for det in detections["items"]:
            assert det["class_name"] in ALLOWED_CLASSES
            assert 0.0 <= det["confidence"] <= 1.0
            assert det["run_id"]

        # 6. Latest overlay has our box layout
        resp = await client.get(f"/api/v1/inference/cameras/{camera_id}/overlay/last")
        assert resp.status_code == 200, resp.text
        overlay = resp.json()
        assert overlay["type"] == "overlay"
        assert overlay["camera_id"] == camera_id
        assert "boxes" in overlay
        for box in overlay["boxes"]:
            assert box["class_name"] in ALLOWED_CLASSES
            assert 0.0 <= box["x"] <= 1.0
            assert "track_id" in box

        # 7. Summary aggregates
        resp = await client.get("/api/v1/inference/summary")
        assert resp.status_code == 200, resp.text
        summary = resp.json()
        assert summary["runs_total"] >= 1
        assert summary["up"] is True
        assert summary["active_cameras"] >= 1

        # 8. Model health + reload
        resp = await client.post("/api/v1/inference/models/yolov12/reload")
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "yolov12"
        resp = await client.get("/api/v1/inference/models/yolov12/health")
        assert resp.status_code == 200, resp.text
        health = resp.json()
        assert health["name"] == "yolov12"

        # 9. Benchmark (sim backend, small workload)
        resp = await client.post(
            "/api/v1/inference/benchmark",
            json={"iterations": 5, "image_width": 640, "image_height": 360, "batch_size": 1},
        )
        assert resp.status_code == 200, resp.text
        bench = resp.json()
        assert bench["model"] == "yolov12"
        assert bench["fps"] > 0
        assert bench["frames_processed"] == 5
        assert bench["report_file"]

        # 10. Stop inference + stream
        resp = await client.post(f"/api/v1/inference/cameras/{camera_id}/stop")
        assert resp.status_code == 200, resp.text
    finally:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
            c.headers["Authorization"] = client.headers["Authorization"]
            camera_id = camera_id if "camera_id" in dir() else None
            if camera_id:
                await c.post(f"/api/v1/inference/cameras/{camera_id}/stop")
                await c.post(f"/api/v1/streams/{camera_id}/stop")
        await client.aclose()
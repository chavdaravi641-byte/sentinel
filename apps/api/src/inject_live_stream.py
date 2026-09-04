"""Standalone hackathon utility — inject a live RTSP feed into a camera.

Usage (inside the API container or with the correct PYTHONPATH + .env):

    python -m src.inject_live_stream \
        --camera-id 01920000-1000-7000-8000-000000000001 \
        --rtsp-url  rtsp://192.168.1.50:554/stream1

The script:
  1. Updates the camera's ``rtsp_url`` in Postgres.
  2. Starts the ffmpeg-based stream (with built-in exponential-backoff reconnect).
  3. Starts ANPR inference for the camera.
  4. Subscribes to the ANPR event bus and prints every recognised plate to the
     console with timestamp, confidence, vehicle colour and state/RTO.
  5. Reconnects automatically on stream failure (handled by StreamManager).
  6. Exits cleanly on Ctrl-C / SIGTERM.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import uuid

from src.core.config import settings
from src.core.database import AsyncSessionLocal, engine
from src.models.camera import Camera, CameraStatus


async def _update_camera_rtsp(db, camera_id: uuid.UUID, rtsp_url: str) -> Camera:
    camera = await db.get(Camera, camera_id)
    if camera is None:
        raise SystemExit(f"Camera {camera_id} not found in database.")
    camera.rtsp_url = rtsp_url
    camera.status = CameraStatus.ONLINE
    camera.is_active = True
    await db.commit()
    await db.refresh(camera)
    return camera


async def _main(camera_id: uuid.UUID, rtsp_url: str) -> None:
    from src.anpr.pipeline import AnprManager, get_anpr_manager
    from src.services.media.manager import get_manager as get_stream_manager

    # 1. Update camera RTSP URL in DB.
    async with AsyncSessionLocal() as db:
        camera = await _update_camera_rtsp(db, camera_id, rtsp_url)
        print(f"[inject] Camera updated: {camera.name} -> {rtsp_url}")

    # 2. Start the stream manager (ffmpeg ingest with reconnect).
    stream_mgr = get_stream_manager()
    await stream_mgr.ready()
    print(f"[inject] Starting stream for {camera.name} ...")
    try:
        await stream_mgr.start(camera)
    except OSError as exc:
        print(f"[inject] Stream start failed ({exc}); will retry via supervisor.")
    print("[inject] Stream active — waiting for first frame ...")

    # 3. Start ANPR inference for this camera.
    anpr: AnprManager = get_anpr_manager()
    await anpr.start()
    await anpr.start_blacklist_sync()
    status = await anpr.camera_start(camera)
    print(f"[inject] ANPR started — backend={status.get('backend', '?')} ocr={status.get('ocr_engine', '?')}")

    # 4. Subscribe to the ANPR event bus and print detections.
    sub_q = anpr.bus.subscribe()
    print("[inject] Listening for plate detections ... Ctrl-C to stop.\n")

    shutdown = asyncio.Event()

    def _signal_handler() -> None:
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    plates_seen = 0

    while not shutdown.is_set():
        try:
            event = await asyncio.wait_for(sub_q.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break

        if event.get("type") != "plate":
            continue

        ts_iso: str = event.get("ts", "")
        for plate in event.get("plates", []):
            plates_seen += 1
            norm: str = plate.get("normalized_plate", plate.get("plate", "?"))
            ocr_conf: float = plate.get("ocr_confidence", 0)
            det_conf: float = plate.get("detection_confidence", 0)
            state: str | None = plate.get("state_code")
            rto: str | None = plate.get("rto_code")
            vehicle = plate.get("vehicle") or plate.get("vehicle_attributes") or {}
            colour: str = vehicle.get("color", "?")
            vtype: str = vehicle.get("vehicle_type", "?")
            make: str = vehicle.get("make", "?")

            tag = f"[{state}-{rto}]" if state and rto else ""
            print(
                f"  #{plates_seen:>4d}  {ts_iso[:19]}Z  "
                f"{norm:<12s} {tag:>8s}  "
                f"ocr={ocr_conf:.2f}  det={det_conf:.2f}  "
                f"{colour} {vtype} ({make})"
            )

    # 5. Graceful shutdown.
    print(f"\n[inject] Shutting down ... ({plates_seen} plates detected)")
    await anpr.camera_stop(str(camera_id))
    await anpr.shutdown()
    await stream_mgr.stop(camera_id)
    await engine.dispose()
    print("[inject] Done.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Inject a live RTSP stream into a Sentinel camera for ANPR evaluation.",
    )
    p.add_argument(
        "--camera-id",
        required=True,
        help="UUID of the seeded camera to bind the RTSP feed to.",
    )
    p.add_argument(
        "--rtsp-url",
        required=True,
        help="RTSP URL of the live feed (e.g. rtsp://192.168.1.50:554/stream1).",
    )
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        cam_uuid = uuid.UUID(args.camera_id)
    except ValueError:
        raise SystemExit(f"Invalid UUID: {args.camera_id}")

    rtsp_url = args.rtsp_url.strip()
    if not rtsp_url.startswith(("rtsp://", "rtsps://", "http://", "https://")):
        raise SystemExit(f"Invalid RTSP URL scheme: {rtsp_url}")

    print(f"[inject] Camera: {cam_uuid}")
    print(f"[inject] RTSP URL: {rtsp_url}")
    print(f"[inject] ANPR weights dir: {settings.ANPR_WEIGHTS_DIR}")
    print(f"[inject] Accelerator: {settings.ANPR_ACCEL}")
    print()

    try:
        asyncio.run(_main(cam_uuid, rtsp_url))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

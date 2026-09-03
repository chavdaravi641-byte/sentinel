"""Phase 3 inference WebSocket hub.

Live bus for realtime event fan-out: connects to `/api/v1/ws/inference` with a
valid access token in the query string and receives curated `overlay` / `stats`
/ `alert` payloads. On connect the last published overlay for each active camera
is replayed so a freshly opened page renders immediately instead of waiting for
the next inference tick.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.core.logging import log
from src.core.security import decode_access_token
from src.inference.engine import get_inference_manager

router = APIRouter()

_CHANNELS = ("overlay", "stats", "alert")


@router.websocket("/ws/inference")
async def inference_ws(
    websocket: WebSocket,
    token: str = Query(default=""),
    channels: str | None = Query(default=None),
) -> None:
    claims = decode_access_token(token)
    if claims is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()

    engine = get_inference_manager()
    selected = [ch for ch in _CHANNELS if not channels or ch in channels.split(",")]
    _, queues = await engine.bus.subscribe_many(selected)
    peer = websocket.client.host if websocket.client else "?"
    log.info("ai.ws.connected", peer=peer, channels=selected)

    try:
        await websocket.send_json(
            {
                "type": "hello",
                "channels": selected,
                "cameras": [rt.camera_id for rt in engine.cameras() if rt.active],
            }
        )
        if "overlay" in selected:
            for rt in engine.cameras():
                if rt.active and rt.last_overlay:
                    await websocket.send_json(rt.last_overlay)
    except Exception:  # noqa: BLE001
        await websocket.close(code=4401)
        return

    consumer_tasks: list[asyncio.Task[Any]] = []
    try:
        consumer_tasks = [asyncio.create_task(_forward(queue, websocket)) for queue in queues]
        async with websocket:
            while True:
                try:
                    msg = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        for task in consumer_tasks:
            task.cancel()
        for task in consumer_tasks:
            with suppress(asyncio.CancelledError):
                await task
        for ch, queue in zip(selected, queues):
            engine.bus.unsubscribe(ch, queue)
        log.info("ai.ws.disconnected", peer=peer)


async def _forward(queue: asyncio.Queue[dict[str, Any]], websocket: WebSocket) -> None:
    while True:
        payload = await queue.get()
        try:
            await websocket.send_json(payload)
        except Exception:  # noqa: BLE001
            raise WebSocketDisconnect


@router.websocket("/ws/anpr")
async def anpr_ws(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    """Phase 4 ANPR realtime feed (plates / stats)."""
    claims = decode_access_token(token)
    if claims is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    from src.anpr.pipeline import get_anpr_manager

    manager = get_anpr_manager()
    queue = manager.bus.subscribe()
    peer = websocket.client.host if websocket.client else "?"
    log.info("anpr.ws.connected", peer=peer)
    try:
        await websocket.send_json(
            {
                "type": "hello",
                "cameras": [rt.camera_id for rt in manager.cameras() if rt.active],
            }
        )
        # Replay last plate event per camera so a fresh page renders instantly.
        for rt in manager.cameras():
            if rt.active and rt.last_event:
                await websocket.send_json(rt.last_event)
    except Exception:  # noqa: BLE001
        await websocket.close(code=4401)
        return

    consumer_task: asyncio.Task | None = None
    try:
        consumer_task = asyncio.create_task(_forward(queue, websocket))
        async with websocket:
            while True:
                try:
                    msg = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if consumer_task is not None:
            consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await consumer_task
        from src.anpr.pipeline import get_anpr_manager

        log.info("anpr.ws.disconnected", peer=peer)


__all__ = ["router"]
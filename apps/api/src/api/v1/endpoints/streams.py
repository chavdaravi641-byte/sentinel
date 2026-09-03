"""Phase 2 streaming endpoints: lifecycle, media, records, discovery."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select

from src.api.deps import CurrentUser, DBDep, StaffUser
from src.core.config import settings
from src.core.logging import log
from src.core.security import decode_access_token
from src.crud import camera as camera_crud
from src.models.camera import Camera
from src.models.stream import Recording
from src.schemas.common import MessageResponse, Paginated
from src.schemas.stream import (
    OnvifDiscoverResult,
    RecordingRead,
    RecordStartRequest,
    RecordStartResponse,
    StreamCapabilities,
    StreamHealth,
    StreamMediaUrls,
    StreamStartRequest,
    StreamTestResult,
)
from src.services.media import onvif
from src.services.media.manager import get_manager
from src.services.media.stream_auth import (
    KIND_HLS,
    KIND_MJPEG,
    KIND_RECORDING,
    KIND_SNAPSHOT,
    KIND_WHEP,
    create_media_token,
    verify_media_token,
)

router = APIRouter()

_MJPEG_BOUNDARY = "frame"

_hls_cookie_cache: str | None = None


async def _mediamtx_hls_cookie() -> str:
    """mediamtx requires a cookieCheck cookie before serving HLS sessions.

    A fresh stateless proxy would get a 302 -> ?cookieCheck=1 on every request
    and lose the HLS session token, so we complete the handshake once and
    replay the cookie on every proxied HLS fetch.
    """
    global _hls_cookie_cache
    if _hls_cookie_cache:
        return _hls_cookie_cache
    try:
        async with httpx.AsyncClient(
            timeout=settings.MEDIAMTX_READ_TIMEOUT, follow_redirects=False
        ) as client:
            resp = await client.get(
                f"{settings.MEDIAMTX_BASE_URL.rstrip('/')}/sentinel/_hls_cookiecheck/index.m3u8"
            )
            for header in resp.headers.get_list("set-cookie"):
                bit = header.split(";", 1)[0]
                if "=" in bit:
                    _hls_cookie_cache = bit
                    return _hls_cookie_cache
    except httpx.HTTPError:
        pass
    return ""


def _camera_404() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")


def _guard_media(request: Request, camera_id: UUID, kind: str) -> None:
    """Allow either a valid access token (Bearer) or a signed media token."""
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        claims = decode_access_token(auth.split(" ", 1)[1])
        if claims is not None:
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")
    exp_raw = request.query_params.get("exp")
    token = request.query_params.get("t")
    try:
        exp = int(exp_raw) if exp_raw else None
    except (TypeError, ValueError):
        exp = None
    if verify_media_token(camera_id, kind, token, exp):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing or expired media token.")


def _media_type_for(uri: str) -> str:
    if uri.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if uri.endswith(".ts"):
        return "video/mp2t"
    if uri.endswith(".vtt"):
        return "text/vtt"
    return "application/octet-stream"


def _rewrite_hls_playlist(body: bytes, exp: str, token: str) -> bytes:
    """Re-embed our signed parameters into playlist child URLs.

    mediamtx signs the root request and issues session-bound child URLs, but it
    echoes any extra query string into those children and then rejects it as an
    unknown token. We therefore forward the upstream request without our exp/t
    params and stamp them back minus session here, so every child fetch still
    passes our media guard while carrying the mediamtx session untouched.
    """
    sentinel = f"exp={exp}&t={token}"
    out = []
    for line in body.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "?" in stripped:
            name, qs = stripped.split("?", 1)
            parts = {}
            for pair in qs.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    if k in ("exp", "t"):
                        continue
                    parts[k] = v
            merged = "&".join(f"{k}={v}" for k, v in parts.items())
            line = f"{name}?{merged}&{sentinel}" if merged else f"{name}?{sentinel}"
        out.append(line)
    return "\n".join(out).encode("utf-8")


def _upstream_params(request: Request) -> dict[str, str]:
    """Forwarded query params for the edge server.

    Our exp/t signature is stripped: mediamtx creates session-bound child URLs
    and rejects foreign tokens echoed back into them.
    """
    return {k: v for k, v in request.query_params.items() if k not in ("exp", "t")}


async def _proxy_edge(
    request: Request,
    upstream: str,
    media_type: str | None = None,
) -> Response:
    """Proxy a GET through to the edge media server (HLS/WHEP)."""
    headers: dict[str, str] = {}
    if upstream.startswith(settings.MEDIAMTX_BASE_URL.rstrip("/")):
        cookie = await _mediamtx_hls_cookie()
        if cookie:
            headers["cookie"] = cookie
    try:
        async with httpx.AsyncClient(
            timeout=settings.MEDIAMTX_READ_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(upstream, params=_upstream_params(request), headers=headers)
    except httpx.HTTPError:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=b'{"detail":"Edge media server unreachable."}',
            media_type="application/json",
        )
    if resp.status_code >= 500:
        return Response(
            status_code=resp.status_code,
            content=b'{"detail":"Edge media server error."}',
            media_type="application/json",
        )
    effective = media_type or _media_type_for(upstream.split("?")[0])
    content = resp.content
    if effective == "application/vnd.apple.mpegurl":
        exp = request.query_params.get("exp")
        token = request.query_params.get("t")
        if exp and token:
            content = _rewrite_hls_playlist(content, exp, token)
    return Response(
        content=content,
        status_code=resp.status_code,
        media_type=effective,
        headers={"Cache-Control": "no-store"},
    )


async def _require_running(camera_id: UUID) -> Any:
    manager = get_manager()
    session = await manager.session(camera_id)
    if session is None or not session.live:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stream is not running. Start it first.",
        )
    return session


# ------------------------------------------------------------------------ #
# Control / listing (declared before the {camera_id} group)
# ------------------------------------------------------------------------ #
@router.get("/config", response_model=StreamCapabilities)
async def stream_config(_: CurrentUser) -> StreamCapabilities:
    """Runtime capabilities of the media engine (encoders, GPU, publisher)."""
    return StreamCapabilities(**await get_manager().capabilities())


@router.get("", response_model=list[StreamHealth])
async def list_streams(*, db: DBDep, _: CurrentUser) -> list[StreamHealth]:
    """Live health snapshot for every camera (state, feed stats, recording)."""
    manager = get_manager()
    result = await db.execute(select(Camera).where(Camera.is_active.is_(True)).order_by(Camera.name))
    cameras = result.scalars().all()
    rows: list[StreamHealth] = []
    for camera in cameras:
        health = await manager.health(camera.id)
        health["name"] = camera.name
        health["location"] = camera.location
        rows.append(StreamHealth(**health))
    return rows


@router.get("/recordings", response_model=Paginated[RecordingRead])
async def list_recordings(
    *,
    db: DBDep,
    _: CurrentUser,
    camera_id: UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Paginated[RecordingRead]:
    stmt = select(Recording, Camera.name).join(Camera, Recording.camera_id == Camera.id).order_by(Recording.started_at.desc())
    count_stmt = select(func.count(Recording.id))
    if camera_id:
        stmt = stmt.where(Recording.camera_id == camera_id)
        count_stmt = count_stmt.where(Recording.camera_id == camera_id)
    if status_:
        stmt = stmt.where(Recording.status == status_)
        count_stmt = count_stmt.where(Recording.status == status_)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    total = int((await db.execute(count_stmt)).scalar_one())
    items = []
    for recording, cam_name in result.all():
        item = RecordingRead.model_validate(recording)
        item.camera_name = cam_name
        items.append(item)
    return Paginated.build(items, total=total, page=page, page_size=page_size)


@router.post("/devices/discover", response_model=OnvifDiscoverResult)
async def discover_onvif(_: StaffUser) -> OnvifDiscoverResult:
    """Run ONVIF WS-Discovery on the local network segment (Staff)."""
    return OnvifDiscoverResult(**await onvif.discover())


@router.get("/recordings/{recording_id}/download")
async def download_recording(
    recording_id: UUID,
    request: Request,
    *,
    db: DBDep,
    _: CurrentUser,
    camera_id: UUID | None = Query(default=None),
) -> FileResponse:
    if camera_id is not None:
        _guard_media(request, camera_id, KIND_RECORDING)
    row = await db.get(Recording, recording_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found.")
    if camera_id is not None and row.camera_id != camera_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recording does not belong to camera.")
    filename = row.file_path.split("/")[-1]
    return FileResponse(
        row.file_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


# ------------------------------------------------------------------------ #
# Per-camera lifecycle
# ------------------------------------------------------------------------ #
@router.post("/{camera_id}/test", response_model=StreamTestResult)
async def test_stream_endpoint(camera_id: UUID, *, db: DBDep, _: CurrentUser) -> StreamTestResult:
    """Full media validation: probe codecs + decode smoke test (not a TCP ping)."""
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    result = await get_manager().test_stream(camera_obj)
    result["tested_at"] = datetime.now(timezone.utc)
    return StreamTestResult(**result)


@router.post("/{camera_id}/start", response_model=StreamHealth)
async def start_stream_endpoint(
    camera_id: UUID,
    body: StreamStartRequest | None = None,
    *,
    db: DBDep,
    current_user: StaffUser,
) -> StreamHealth:
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    manager = get_manager()
    try:
        health = await manager.start(camera_obj)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    health["name"] = camera_obj.name
    if body and body.record:
        session = await manager.session(camera_id)
        if session is not None and health.get("state") == "running":
            try:
                await manager.record_start(
                    session, trigger=body.record_trigger, started_by=current_user.id, seconds=body.record_seconds
                )
                health["recording"] = True
                health["recording_trigger"] = body.record_trigger
            except Exception as exc:
                log.warning("stream.auto_record_failed", camera_id=str(camera_id), error=str(exc))
    return StreamHealth(**health)


@router.post("/{camera_id}/stop", response_model=MessageResponse)
async def stop_stream_endpoint(camera_id: UUID, *, db: DBDep, _: StaffUser) -> MessageResponse:
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    stopped = await get_manager().stop(camera_id)
    log.info("stream.stop_api", camera_id=str(camera_id), had_session=stopped is not None)
    return MessageResponse(message="Stream stopped.")


@router.get("/{camera_id}/health", response_model=StreamHealth)
async def stream_health_endpoint(camera_id: UUID, *, db: DBDep, _: CurrentUser) -> StreamHealth:
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    health = await get_manager().health(camera_id)
    health["name"] = camera_obj.name
    return StreamHealth(**health)


@router.get("/{camera_id}/stats", response_model=dict)
async def stream_stats_endpoint(camera_id: UUID, *, db: DBDep, _: CurrentUser) -> dict:
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    try:
        stats = await get_manager().stats(camera_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stream is not running.")
    stats["name"] = camera_obj.name
    return stats


@router.get("/{camera_id}/media", response_model=StreamMediaUrls)
async def stream_media_urls(camera_id: UUID, request: Request, *, db: DBDep, _: CurrentUser) -> StreamMediaUrls:
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    base = f"{str(request.base_url).rstrip('/')}/api/v1/streams/{camera_id}"
    ttl = settings.STREAM_AUTH_TTL_SECONDS
    hls_token = create_media_token(camera_id, KIND_HLS, ttl=ttl)
    mjpeg_token = create_media_token(camera_id, KIND_MJPEG, ttl=ttl)
    snap_token = create_media_token(camera_id, KIND_SNAPSHOT, ttl=ttl)
    whep_token = create_media_token(camera_id, KIND_WHEP, ttl=ttl)
    return StreamMediaUrls(
        camera_id=camera_id,
        hls_url=f"{base}/hls/index.m3u8?{hls_token.query()}",
        mjpeg_url=f"{base}/mjpeg?{mjpeg_token.query()}",
        snapshot_url=f"{base}/snapshot?{snap_token.query()}",
        whep_url=f"{base}/whep?{whep_token.query()}",
        expires_in=ttl,
        published_at=datetime.now(timezone.utc),
    )


# ------------------------------------------------------------------------ #
# Media
# ------------------------------------------------------------------------ #
@router.get("/{camera_id}/snapshot")
async def snapshot_endpoint(camera_id: UUID, request: Request, *, db: DBDep) -> Response:
    _guard_media(request, camera_id, KIND_SNAPSHOT)
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    manager = get_manager()
    frame = await manager.snapshot_latest(camera_id)
    if frame is None:
        frame = await manager.snapshot_on_demand(camera_obj)
    if frame is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not capture a frame from the source.")
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Sentinel-Camera": camera_obj.name},
    )


@router.get("/{camera_id}/mjpeg")
async def mjpeg_endpoint(camera_id: UUID, request: Request, *, db: DBDep) -> StreamingResponse:
    _guard_media(request, camera_id, KIND_MJPEG)
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    manager = get_manager()
    session = await manager.session(camera_id)
    if session is None or not session.live:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stream is not running. Start it first.")

    async def _stream():
        try:
            async for frame in await manager.subscribe_mjpeg(camera_id, fps=settings.MJPEG_FPS):
                yield (
                    b"--" + _MJPEG_BOUNDARY.encode("ascii") + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + b"Content-Length: " + str(len(frame)).encode("ascii") + b"\r\n\r\n"
                    + frame + b"\r\n"
                )
        except (asyncio.CancelledError, GeneratorExit):
            return

    return StreamingResponse(
        _stream(),
        media_type=f"multipart/x-mixed-replace; boundary={_MJPEG_BOUNDARY}",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{camera_id}/hls/index.m3u8")
async def hls_playlist_endpoint(camera_id: UUID, request: Request, *, db: DBDep) -> Response:
    _guard_media(request, camera_id, KIND_HLS)
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    session = await get_manager().session(camera_id)
    if session is None or not session.live:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stream is not running.")
    cam_key = str(camera_id)
    upstream = f"{settings.MEDIAMTX_BASE_URL.rstrip('/')}/sentinel/{camera_id}/index.m3u8"
    return await _proxy_edge(request, upstream, media_type="application/vnd.apple.mpegurl")


@router.get("/{camera_id}/hls/{segment:path}")
async def hls_segment_endpoint(camera_id: UUID, segment: str, request: Request, *, db: DBDep) -> Response:
    _guard_media(request, camera_id, KIND_HLS)
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    if "/" in segment or ".." in segment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid segment path.")
    session = await get_manager().session(camera_id)
    if session is None or not session.live:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stream is not running.")
    return await _proxy_edge(
        request,
        f"{settings.MEDIAMTX_BASE_URL.rstrip('/')}/sentinel/{camera_id}/{segment}",
    )


@router.post("/{camera_id}/whep")
async def whep_relay_endpoint(camera_id: UUID, request: Request, *, db: DBDep) -> Response:
    """WHEP relay: forward the WebRTC SDP offer to the edge server and return its answer."""
    _guard_media(request, camera_id, KIND_WHEP)
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    session = await get_manager().session(camera_id)
    if session is None or not session.live:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stream is not running.")
    body = await request.body()
    upstream = f"{settings.MEDIAMTX_WHEP_URL.rstrip('/')}/sentinel/{camera_id}/whep"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                upstream,
                content=body,
                headers={"Content-Type": "application/sdp", "Accept": "application/sdp"},
            )
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WebRTC edge server unreachable.")
    content_type = resp.headers.get("content-type", "application/sdp")
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=content_type,
        headers={"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"},
    )


# ------------------------------------------------------------------------ #
# Recording controls
# ------------------------------------------------------------------------ #
@router.post("/{camera_id}/record/start", response_model=RecordStartResponse)
async def record_start_endpoint(
    camera_id: UUID,
    body: RecordStartRequest | None = None,
    *,
    db: DBDep,
    current_user: StaffUser,
) -> RecordStartResponse:
    payload = body or RecordStartRequest()
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    manager = get_manager()
    session = await _require_running(camera_id)
    result = await manager.record_start(
        session,
        trigger=payload.trigger,
        started_by=current_user.id,
        seconds=payload.seconds,
    )
    return RecordStartResponse(**result)


@router.post("/{camera_id}/record/stop", response_model=RecordStartResponse)
async def record_stop_endpoint(camera_id: UUID, *, db: DBDep, _: StaffUser) -> RecordStartResponse:
    camera_obj = await camera_crud.get_by_id(db, camera_id)
    if camera_obj is None:
        raise _camera_404()
    manager = get_manager()
    stopped = await manager.record_stop(camera_id)
    if stopped is None:
        return RecordStartResponse(status="no_active_recording", camera_id=camera_id)
    return RecordStartResponse(**stopped, camera_id=camera_id)
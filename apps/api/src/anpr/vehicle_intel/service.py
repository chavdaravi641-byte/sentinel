"""Phase 5 backend service — loads real registered cameras from the DB and
builds the derived camera graph + exposes identity/association operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.anpr.vehicle_intel.graph import CameraGraph, build_graph_from_cameras, GraphConfig
from src.anpr.vehicle_intel.identity import assign_identity
from src.anpr.vehicle_intel.cache import cache_get_json, cache_set_json
from src.models.camera import Camera
from src.models.vehicle_intel import VehicleIdentity, VehicleSighting


def _camera_rows_to_dicts(cameras: list[Camera]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "location": c.location,
            "latitude": c.latitude,
            "longitude": c.longitude,
        }
        for c in cameras
    ]


async def load_cameras(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (await db.execute(select(Camera))).scalars().all()
    return _camera_rows_to_dicts(rows)


async def get_graph(
    db: AsyncSession,
    *,
    max_link_km: float = 12.0,
) -> CameraGraph:
    """Build the camera graph from real registered cameras in the DB.

    Graph edges are derived purely from the registered camera positions and the
    documented geometric assumptions (see graph.py); no road data is invented.
    The payload is cached in Redis to keep the graph cheap across calls.
    """
    cached = await cache_get_json("graph")
    if cached is not None:
        return _graph_from_payload(cached, max_link_km)

    cameras = await load_cameras(db)
    graph = build_graph_from_cameras(cameras, GraphConfig(max_link_km=max_link_km))
    await cache_set_json("graph", graph.to_payload(), ttl=600)
    return graph


def _graph_from_payload(payload: dict[str, Any], max_link_km: float) -> CameraGraph:
    """Rebuild a CameraGraph from a cached payload (avoids recompute)."""
    config = GraphConfig(max_link_km=max_link_km)
    config.road_factor = float(payload["config"]["road_factor"])
    config.assumed_speed_kph = float(payload["config"]["assumed_speed_kph"])
    graph = CameraGraph(config)
    for n in payload["nodes"]:
        graph.add_camera(
            camera_id=n["camera_id"],
            camera_name=n["camera_name"],
            location=n["location"],
            latitude=n["latitude"],
            longitude=n["longitude"],
        )
    graph.build()
    return graph


async def upsert_vehicle_identity(db: AsyncSession, identity, plate: str) -> None:
    """Persist (or refresh) a vehicle identity row for the given identity."""
    row = (
        await db.execute(
            select(VehicleIdentity).where(VehicleIdentity.vehicle_uuid == identity.vehicle_uuid)
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            VehicleIdentity(
                vehicle_uuid=identity.vehicle_uuid,
                key=identity.key,
                plate=identity.plate or plate,
                basis=identity.basis,
                confidence=identity.confidence,
                appearance_signature=identity.appearance_signature,
                embedding_signature=identity.embedding_signature,
                sighting_count=1,
            )
        )
    else:
        row.sighting_count += 1
    return


async def record_sighting(
    db: AsyncSession,
    *,
    vehicle_uuid: str,
    camera_id: str,
    plate: str,
    normalized_plate: str,
    identity_confidence: float,
    basis: str,
    appearance: dict[str, Any] | None,
    ts,
) -> VehicleSighting:
    sighting = VehicleSighting(
        vehicle_uuid=vehicle_uuid,
        camera_id=None,
        plate=plate,
        normalized_plate=normalized_plate,
        identity_confidence=identity_confidence,
        basis=basis,
        appearance=appearance,
        ts=ts,
    )
    db.add(sighting)
    return sighting


__all__ = [
    "load_cameras",
    "get_graph",
    "upsert_vehicle_identity",
    "record_sighting",
    "assign_identity",
]

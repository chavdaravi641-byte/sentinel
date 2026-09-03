"""Idempotent seed: admin user, demo cameras across Gujarat, alerts, incidents.

Run automatically on startup when SEED_ON_STARTUP=true or manually via
`python -m src.seed`. Safe to run repeatedly.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from src.core.config import settings
from src.core.database import AsyncSessionLocal, init_db
from src.core.logging import log
from src.core.security import hash_password
from src.models.alert import Alert, AlertSeverity, AlertStatus, AlertType
from src.models.camera import Camera, CameraStatus
from src.models.incident import Incident, IncidentStatus, IncidentType
from src.models.user import User, UserRole

SECONDS = 1
_h = 3600
_d = 86400


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ago(**kwargs) -> datetime:
    return _now() - timedelta(**kwargs)


# fmt: off
DEMO_CAMERAS = [
    # (name, location, lat, lng, status, rtsp_host)
    ("AHM-SGH-01",       "SG Highway, Ahmedabad",           23.0225, 72.5714, CameraStatus.ONLINE,       "10.10.1.11"),
    ("AHM-LAW-02",       "Law Garden, Ahmedabad",           23.0303, 72.5562, CameraStatus.ONLINE,       "10.10.1.12"),
    ("AHM-MAN-03",       "Maninagar, Ahmedabad",            22.9945, 72.6010, CameraStatus.OFFLINE,      "10.10.1.13"),
    ("GNR-GFT-01",       "GIFT City, Gandhinagar",          23.1607, 72.6707, CameraStatus.ONLINE,       "10.10.2.11"),
    ("GNR-SEC-02",       "Secretariat Rd, Gandhinagar",     23.2232, 72.6490, CameraStatus.MAINTENANCE,   "10.10.2.12"),
    ("SRT-DMR-01",       "Dumas Road, Surat",               21.1559, 72.7840, CameraStatus.ONLINE,       "10.10.3.11"),
    ("SRT-RNG-02",       "Ring Road, Surat",                21.1959, 72.8300, CameraStatus.ONLINE,       "10.10.3.12"),
    ("VDR-ALK-01",       "Alkapuri, Vadodara",              22.3072, 73.1812, CameraStatus.ONLINE,       "10.10.4.11"),
    ("VDR-MND-02",       "Mandvi Gate, Vadodara",           22.3107, 73.1829, CameraStatus.OFFLINE,      "10.10.4.12"),
    ("RAJ-JGN-01",       "Jagnath Chowk, Rajkot",           22.3039, 70.8022, CameraStatus.ONLINE,       "10.10.5.11"),
    ("BHV-WTC-01",       "Water Tank Chowk, Bhavnagar",     21.7645, 72.1519, CameraStatus.ONLINE,       "10.10.6.11"),
    ("JAM-BDG-01",       "Bedi Gate, Jamnagar",             22.4707, 70.0577, CameraStatus.UNKNOWN,      "10.10.7.11"),
    ("POR-CHP-01",       "Chowpati, Porbandar",             21.6417, 69.6293, CameraStatus.ONLINE,       "10.10.8.11"),
    ("JUN-MGG-01",       "Mahatma Gandhi Gate, Junagadh",   21.5222, 70.4579, CameraStatus.MAINTENANCE,  "10.10.9.11"),
    ("AND-TWN-01",       "Town Hall Crossing, Anand",       22.5645, 72.9289, CameraStatus.ONLINE,       "10.10.10.11"),
    ("MEH-CGT-01",       "City Gate, Mehsana",              23.5880, 72.3693, CameraStatus.OFFLINE,      "10.10.11.11"),
]
# fmt: on

ALERTS = [
    # (camera_idx, type, severity, status, confidence, message, minutes_ago)
    (0,  AlertType.INTRUSION,          AlertSeverity.CRITICAL, AlertStatus.NEW,        0.97, "Perimeter intrusion detected near east boundary.", 12),
    (2,  AlertType.MOTION,             AlertSeverity.MEDIUM,   AlertStatus.NEW,        0.82, "High-velocity motion in restricted zone.", 28),
    (5,  AlertType.CROWD,              AlertSeverity.HIGH,     AlertStatus.ACKNOWLEDGED, 0.91, "Crowd formation exceeding threshold at junction.", 55),
    (7,  AlertType.ABANDONED_OBJECT,   AlertSeverity.MEDIUM,   AlertStatus.NEW,        0.78, "Suspicious abandoned object left unattended.", 90),
    (10, AlertType.LICENSE_PLATE,      AlertSeverity.HIGH,     AlertStatus.ESCALATED,   0.95, "License plate match on watchlist vehicle.", 140),
    (3,  AlertType.LOITERING,          AlertSeverity.LOW,      AlertStatus.RESOLVED,    0.71, "Loitering behaviour in front of facility.", 200),
    (13, AlertType.SUSPICIOUS_BEHAVIOR, AlertSeverity.MEDIUM,  AlertStatus.NEW,        0.85, "Suspicious behaviour near armed forces gate.", 260),
    (15, AlertType.MOTION,             AlertSeverity.INFO,     AlertStatus.RESOLVED,    0.60, "Motion during low-activity window.", 320),
]

INCIDENTS = [
    # (camera_idx, title, desc, type, severity, status, minutes_ago)
    (1,  "Scooter theft at Law Garden",          "Victim reported two-wheeler stolen near gate 2.", IncidentType.THEFT,              AlertSeverity.HIGH,     IncidentStatus.IN_PROGRESS, 95),
    (0,  "Signal-jump multiple offenders",       "Three bikes jumped red light captured on cam.", IncidentType.TRAFFIC,           AlertSeverity.MEDIUM,   IncidentStatus.OPEN,        160),
    (5,  "Fire report near Dumas Road market",   "Smoke observed from vendor stalls.",            IncidentType.FIRE,              AlertSeverity.CRITICAL, IncidentStatus.CLOSED,       520),
    (10, "Missing person last seen near WTC",    "Individual reported missing at 18:40.",         IncidentType.MISSING_PERSON,    AlertSeverity.HIGH,     IncidentStatus.OPEN,        45),
]

OPERATORS = [
    ("ops@sentinel.gp", "Operations Desk", UserRole.OPERATOR),
    ("command@sentinel.gp", "Command Center", UserRole.VIEWER),
]


async def _exists(db, model, **kwargs) -> bool:
    stmt = select(func.count()).select_from(model)
    for col, value in kwargs.items():
        stmt = stmt.where(getattr(model, col) == value)
    return int((await db.execute(stmt)).scalar_one()) > 0


async def seed_users(db) -> list[User]:
    if await _exists(db, User, email=settings.ADMIN_EMAIL.lower()):
        admin = (
            await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL.lower()))
        ).scalar_one()
        return [admin]

    admin = User(
        email=settings.ADMIN_EMAIL.lower(),
        full_name="System Administrator",
        role=UserRole.ADMIN,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        is_active=True,
        last_login_at=None,
    )
    db.add(admin)

    existing_ops = await _exists(db, User, email=OPERATORS[0][0])
    users = [admin]
    if not existing_ops:
        for email, name, role in OPERATORS:
            user = User(
                email=email,
                full_name=name,
                role=role,
                password_hash=hash_password("Ops@2026"),
                is_active=True,
            )
            db.add(user)
            users.append(user)
    await db.commit()
    return users


async def seed_cameras(db) -> tuple[list[Camera], dict[int, Camera]]:
    existing_count = int(
        (await db.execute(select(func.count(Camera.id)))).scalar_one()
    )
    if existing_count > 0:
        rows = (await db.execute(select(Camera))).scalars().all()
        return list(rows), {i: cam for i, cam in enumerate(rows)}

    cameras: list[Camera] = []
    for idx, (name, location, lat, lng, status, host) in enumerate(DEMO_CAMERAS):
        rtsp = f"rtsp://admin:sentinel@{host}:554/streaming/channels/1"
        cam = Camera(
            name=name,
            rtsp_url=rtsp,
            location=location,
            latitude=lat,
            longitude=lng,
            status=status,
            is_active=True,
            last_seen_at=(
                _ago(hours=2) if status == CameraStatus.ONLINE else None
            ),
            description=f"Seeded reference camera {idx + 1}/{len(DEMO_CAMERAS)}.",
        )
        db.add(cam)
        cameras.append(cam)
    await db.commit()
    by_index = {i: cam for i, cam in enumerate(cameras)}
    # refresh to capture created_at
    for cam in cameras:
        await db.refresh(cam)
    return cameras, by_index


async def seed_alerts(db, cameras_by_index: dict[int, Camera]) -> bool:
    if await _exists(db, Alert):
        return False
    for camera_idx, alert_type, severity, alert_status, confidence, message, mins in ALERTS:
        camera = cameras_by_index.get(camera_idx)
        db.add(
            Alert(
                camera_id=camera.id if camera else None,
                type=alert_type,
                severity=severity,
                status=alert_status,
                message=message,
                confidence=confidence,
                snapshot_url=None,
                occurred_at=_ago(minutes=mins),
            )
        )
    await db.commit()
    return True


async def seed_incidents(
    db, users: list[User], cameras_by_index: dict[int, Camera]
) -> bool:
    if await _exists(db, Incident):
        return False
    admin = users[0]
    for camera_idx, title, desc, itype, severity, istatus, mins in INCIDENTS:
        camera = cameras_by_index.get(camera_idx)
        incident = Incident(
            camera_id=camera.id if camera else None,
            title=title,
            description=desc,
            type=itype,
            severity=severity,
            status=istatus,
            location=camera.location if camera else None,
            latitude=camera.latitude if camera else None,
            longitude=camera.longitude if camera else None,
            reported_by=admin.id,
            occurred_at=_ago(minutes=mins),
        )
        db.add(incident)
    await db.commit()
    return True


async def run_seed() -> None:
    """Run the full, idempotent seed routine."""
    await init_db()
    async with AsyncSessionLocal() as db:
        users = await seed_users(db)
        cameras, cameras_by_index = await seed_cameras(db)
        created_alerts = await seed_alerts(db, cameras_by_index)
        created_incidents = await seed_incidents(db, users, cameras_by_index)
        log.info(
            "seed.complete",
            users=len(users),
            cameras=len(cameras),
            created_alerts=created_alerts,
            created_incidents=created_incidents,
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_seed())
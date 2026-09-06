"""Idempotent seed: admin user, demo cameras across Gujarat, alerts, incidents.

Run automatically on startup when SEED_ON_STARTUP=true or manually via
`python -m src.seed`. Safe to run repeatedly.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from src.core.config import settings
from src.core.database import AsyncSessionLocal, init_db
from src.core.logging import log
from src.core.security import hash_password
from src.models.alert import Alert, AlertSeverity, AlertStatus, AlertType
from src.models.anpr import PlateDetection
from src.models.camera import Camera, CameraStatus
from src.models.incident import Incident, IncidentStatus, IncidentType
from src.models.registry import (
    CameraCategory,
    CameraRegistry,
    OwnershipType,
)
from src.models.user import User, UserRole
from src.models.watchlist import (
    Watchlist,
    WatchlistCategory,
    WatchlistSourceDB,
    WatchlistTargetType,
)

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
    # --- Ahmedabad (9) ---
    ("AHM-SGH-01",       "SG Highway, Ahmedabad",           23.0225, 72.5714, CameraStatus.ONLINE,       "10.10.1.11"),
    ("AHM-LAW-02",       "Law Garden, Ahmedabad",           23.0303, 72.5562, CameraStatus.ONLINE,       "10.10.1.12"),
    ("AHM-MAN-03",       "Maninagar, Ahmedabad",            22.9945, 72.6010, CameraStatus.OFFLINE,      "10.10.1.13"),
    ("AHM-NAV-04",       "Navrangpura, Ahmedabad",          23.0342, 72.5612, CameraStatus.ONLINE,       "10.10.1.14"),
    ("AHM-ISK-05",       "ISKCON Cross Road, Ahmedabad",    23.0391, 72.5042, CameraStatus.ONLINE,       "10.10.1.15"),
    ("AHM-CGD-06",       "CG Road, Ahmedabad",              23.0327, 72.5357, CameraStatus.MAINTENANCE,  "10.10.1.16"),
    ("AHM-RLG-07",       "Relief Road, Ahmedabad",          23.0131, 72.5911, CameraStatus.ONLINE,       "10.10.1.17"),
    ("AHM-AIR-08",       "Airport Junction, Ahmedabad",     23.0667, 72.6368, CameraStatus.ONLINE,       "10.10.1.18"),
    ("AHM-GMT-09",       "Gomtipur, Ahmedabad",             23.0020, 72.6150, CameraStatus.OFFLINE,      "10.10.1.19"),
    # --- Gandhinagar (5) ---
    ("GNR-GFT-01",       "GIFT City, Gandhinagar",          23.1607, 72.6707, CameraStatus.ONLINE,       "10.10.2.11"),
    ("GNR-SEC-02",       "Secretariat Rd, Gandhinagar",     23.2232, 72.6490, CameraStatus.MAINTENANCE,   "10.10.2.12"),
    ("GNR-INF-03",       "Infocity, Gandhinagar",           23.1220, 72.6460, CameraStatus.ONLINE,       "10.10.2.13"),
    ("GNR-KDL-04",       "Kudasan, Gandhinagar",            23.1380, 72.6770, CameraStatus.ONLINE,       "10.10.2.14"),
    ("GNR-RIL-05",       "Rilamode Cross, Gandhinagar",     23.1780, 72.6340, CameraStatus.UNKNOWN,      "10.10.2.15"),
    # --- Surat (7) ---
    ("SRT-DMR-01",       "Dumas Road, Surat",               21.1559, 72.7840, CameraStatus.ONLINE,       "10.10.3.11"),
    ("SRT-RNG-02",       "Ring Road, Surat",                21.1959, 72.8300, CameraStatus.ONLINE,       "10.10.3.12"),
    ("SRT-VRV-03",       "Varachha, Surat",                 21.1920, 72.8500, CameraStatus.ONLINE,       "10.10.3.13"),
    ("SRT-PRD-04",       "Pandesara, Surat",                21.2180, 72.8090, CameraStatus.OFFLINE,      "10.10.3.14"),
    ("SRT-CHK-05",       "Chowk Bazaar, Surat",             21.1960, 72.8340, CameraStatus.ONLINE,       "10.10.3.15"),
    ("SRT-KPR-06",       "Kadodara, Surat",                 21.1340, 72.8790, CameraStatus.MAINTENANCE,  "10.10.3.16"),
    ("SRT-MBG-07",       "Motoribhag, Surat",               21.1780, 72.8440, CameraStatus.ONLINE,       "10.10.3.17"),
    # --- Vadodara (6) ---
    ("VDR-ALK-01",       "Alkapuri, Vadodara",              22.3072, 73.1812, CameraStatus.ONLINE,       "10.10.4.11"),
    ("VDR-MND-02",       "Mandvi Gate, Vadodara",           22.3107, 73.1829, CameraStatus.OFFLINE,      "10.10.4.12"),
    ("VDR-GOT-03",       "Gotri, Vadodara",                 22.2940, 73.1530, CameraStatus.ONLINE,       "10.10.4.13"),
    ("VDR-MAN-04",       "Manjalpur, Vadodara",             22.2640, 73.2020, CameraStatus.ONLINE,       "10.10.4.14"),
    ("VDR-KAR-05",       "Karelibaug, Vadodara",            22.3290, 73.1940, CameraStatus.UNKNOWN,      "10.10.4.15"),
    ("VDR-JMB-06",       "Jambuvadi, Vadodara",             22.3040, 73.1910, CameraStatus.MAINTENANCE,  "10.10.4.16"),
    # --- Rajkot (5) ---
    ("RAJ-JGN-01",       "Jagnath Chowk, Rajkot",           22.3039, 70.8022, CameraStatus.ONLINE,       "10.10.5.11"),
    ("RAJ-RCK-02",       "Race Course, Rajkot",             22.2910, 70.7910, CameraStatus.ONLINE,       "10.10.5.12"),
    ("RAJ-KBR-03",       "Kalawad Rd, Rajkot",              22.3150, 70.7550, CameraStatus.OFFLINE,      "10.10.5.13"),
    ("RAJ-UNI-04",       "University Rd, Rajkot",           22.3250, 70.7770, CameraStatus.ONLINE,       "10.10.5.14"),
    ("RAJ-AIR-05",       "Airport Rd, Rajkot",              22.3410, 70.7020, CameraStatus.UNKNOWN,      "10.10.5.15"),
    # --- Bhavnagar / Jamnagar / Junagadh (8) ---
    ("BHV-WTC-01",       "Water Tank Chowk, Bhavnagar",     21.7645, 72.1519, CameraStatus.ONLINE,       "10.10.6.11"),
    ("BHV-TGP-02",       "Tagore Road, Bhavnagar",          21.7640, 72.1460, CameraStatus.ONLINE,       "10.10.6.12"),
    ("JAM-BDG-01",       "Bedi Gate, Jamnagar",             22.4707, 70.0577, CameraStatus.UNKNOWN,      "10.10.7.11"),
    ("JAM-DHJ-02",       "Dhrol Road, Jamnagar",            22.4400, 70.0450, CameraStatus.OFFLINE,      "10.10.7.12"),
    ("JUN-MGG-01",       "Mahatma Gandhi Gate, Junagadh",   21.5222, 70.4579, CameraStatus.MAINTENANCE,  "10.10.9.11"),
    ("JUN-MDD-02",       "Moti Daman Rd, Junagadh",         21.5060, 70.4700, CameraStatus.ONLINE,       "10.10.9.12"),
    ("POR-CHP-01",       "Chowpati, Porbandar",             21.6417, 69.6293, CameraStatus.ONLINE,       "10.10.8.11"),
    ("DWK-KPR-01",       "Krishna Mandir Rd, Dwarka",       22.2428, 68.9784, CameraStatus.ONLINE,       "10.10.12.11"),
    # --- N / Central Gujarat (10) ---
    ("AND-TWN-01",       "Town Hall Crossing, Anand",       22.5645, 72.9289, CameraStatus.ONLINE,       "10.10.10.11"),
    ("AND-VTT-02",       "Vallabh Vidyanagar, Anand",       22.5170, 72.8900, CameraStatus.ONLINE,       "10.10.10.12"),
    ("MEH-CGT-01",       "City Gate, Mehsana",              23.5880, 72.3693, CameraStatus.OFFLINE,      "10.10.11.11"),
    ("PAT-DDN-01",       "Patan Heritage Rd, Patan",        23.8470, 72.1260, CameraStatus.ONLINE,       "10.10.13.11"),
    ("BRJ-ALM-01",       "Almora Chok, Bharuch",            21.7050, 72.9960, CameraStatus.ONLINE,       "10.10.14.11"),
    ("NAL-CHV-01",       "Chhapar Veraval, Nalanda",        20.9050, 72.8720, CameraStatus.MAINTENANCE,  "10.10.15.11"),
    ("NAD-VLT-01",       "Vallabh Bag, Nadiad",             22.6940, 72.8640, CameraStatus.ONLINE,       "10.10.16.11"),
    ("GDR-CGS-01",       "Godhra Main Rd, Godhra",          22.7830, 73.6140, CameraStatus.UNKNOWN,      "10.10.17.11"),
    ("MOR-MRD-01",       "Morbi Junction, Morbi",           22.8180, 70.8370, CameraStatus.ONLINE,       "10.10.18.11"),
    ("VLS-KLD-01",       "Kalavad Rd, Valsad",              20.6100, 72.9260, CameraStatus.OFFLINE,      "10.10.19.11"),
    # --- Synthetic lavfi test source (use by streaming/ai integration tests) ---
    ("TEST-LAVFI-01",    "Synthetic Test Source",           23.0001, 72.5001, CameraStatus.ONLINE,       "lavfi://testsrc2=size=1280x720:rate=25"),
]
# fmt: on

WATCHLIST_ENTRIES = [
    # (identifier, target_type, category, source_db, notes, active)
    ("GJ01AB1234", WatchlistTargetType.VEHICLE, WatchlistCategory.STOLEN_VEHICLE, WatchlistSourceDB.VAHAN,
     "Black Maruti Swift reported stolen from Maninagar on 12 Aug.", True),
    ("GJ05CD5678", WatchlistTargetType.VEHICLE, WatchlistCategory.STOLEN_VEHICLE, WatchlistSourceDB.VAHAN,
     "Stolen two-wheeler (Honda Activa) from Surat.", True),
    ("GJ06XY9012", WatchlistTargetType.VEHICLE, WatchlistCategory.WANTED, WatchlistSourceDB.EGUJCOP,
     "Vehicle linked to extortion case - GJ High Court warrant.", True),
    ("GJ11AB3456", WatchlistTargetType.VEHICLE, WatchlistCategory.WANTED, WatchlistSourceDB.EGUJCOP,
     "Suspect vehicle in chain-snatching ring operating in Rajkot.", True),
    ("GJ27MN7890", WatchlistTargetType.VEHICLE, WatchlistCategory.MISSING, WatchlistSourceDB.SARTHI,
     "Owner reported missing since 02 Sep. Family appeal.", True),
    ("GJ01QR2345", WatchlistTargetType.VEHICLE, WatchlistCategory.BLACKLISTED, WatchlistSourceDB.VAHAN,
     "Repeated traffic violator - 14 challans unpaid.", True),
    ("GJ04ST6789", WatchlistTargetType.VEHICLE, WatchlistCategory.BLACKLISTED, WatchlistSourceDB.SARTHI,
     "Fleet vehicle with expired fitness certificate.", True),
    ("GJ18UV9012", WatchlistTargetType.VEHICLE, WatchlistCategory.SUSPECT, WatchlistSourceDB.INTERNAL,
     "Observed near multiple jewellery heists across Gujarat.", True),
    ("GJ03WX4567", WatchlistTargetType.VEHICLE, WatchlistCategory.STOLEN_VEHICLE, WatchlistSourceDB.VAHAN,
     "Stolen Mahindra Scorpio from Vadodara district.", True),
    ("GJ12YZ8901", WatchlistTargetType.VEHICLE, WatchlistCategory.WANTED, WatchlistSourceDB.EGUJCOP,
     "Vehicle used by smuggler near Kutch border crossing.", False),
]

ALERTS = [
    # (camera_idx, type, severity, status, confidence, message, minutes_ago)
    (0,  AlertType.INTRUSION,          AlertSeverity.CRITICAL, AlertStatus.NEW,        0.97, "Perimeter intrusion detected near east boundary.", 12),
    (2,  AlertType.MOTION,             AlertSeverity.MEDIUM,   AlertStatus.NEW,        0.82, "High-velocity motion in restricted zone.", 28),
    (14, AlertType.CROWD,              AlertSeverity.HIGH,     AlertStatus.ACKNOWLEDGED, 0.91, "Crowd formation exceeding threshold at junction.", 55),
    (21, AlertType.ABANDONED_OBJECT,   AlertSeverity.MEDIUM,   AlertStatus.NEW,        0.78, "Suspicious abandoned object left unattended.", 90),
    (7,  AlertType.LICENSE_PLATE,      AlertSeverity.HIGH,     AlertStatus.ESCALATED,   0.95, "License plate match on watchlist vehicle.", 140),
    (3,  AlertType.LOITERING,          AlertSeverity.LOW,      AlertStatus.RESOLVED,    0.71, "Loitering behaviour in front of facility.", 200),
    (24, AlertType.SUSPICIOUS_BEHAVIOR, AlertSeverity.MEDIUM,  AlertStatus.NEW,        0.85, "Suspicious behaviour near armed forces gate.", 260),
    (10, AlertType.MOTION,             AlertSeverity.INFO,     AlertStatus.RESOLVED,    0.60, "Motion during low-activity window.", 320),
]

INCIDENTS = [
    # (camera_idx, title, desc, type, severity, status, minutes_ago)
    (1,  "Scooter theft at Law Garden",          "Victim reported two-wheeler stolen near gate 2.", IncidentType.THEFT,              AlertSeverity.HIGH,     IncidentStatus.IN_PROGRESS, 95),
    (0,  "Signal-jump multiple offenders",       "Three bikes jumped red light captured on cam.", IncidentType.TRAFFIC,           AlertSeverity.MEDIUM,   IncidentStatus.OPEN,        160),
    (14, "Fire report near Varachha market",     "Smoke observed from vendor stalls.",            IncidentType.FIRE,              AlertSeverity.CRITICAL, IncidentStatus.CLOSED,       520),
    (7,  "Missing person last seen near Airport", "Individual reported missing at 18:40.",        IncidentType.MISSING_PERSON,    AlertSeverity.HIGH,     IncidentStatus.OPEN,        45),
]

OPERATORS = [
    ("ops@sentinel.gp", "Operations Desk", UserRole.OPERATOR),
    ("command@sentinel.gp", "Command Center", UserRole.VIEWER),
]


# District prefix -> (district_code, department_code, board_code)
# Derives the registry ownership scoping from the seeded camera name prefix.
DISTRICT_META: dict[str, tuple[str, str, str]] = {
    "AHM": ("AHMEDABAD", "TRAF", "AHM-CITY"),
    "GNR": ("GANDHINAGAR", "TRAF", "GNR-CITY"),
    "SRT": ("SURAT", "TRAF", "SRT-CITY"),
    "VDR": ("VADODARA", "TRAF", "VDR-CITY"),
    "RAJ": ("RAJKOT", "TRAF", "RAJ-CITY"),
    "BHV": ("BHAVNAGAR", "TRAF", "BHV-CITY"),
    "JAM": ("JAMNAGAR", "MUNI", "JAM-CITY"),
    "JUN": ("JUNAGADH", "TRAF", "JUN-CITY"),
    "POR": ("PORBANDAR", "MUNI", "POR-CITY"),
    "DWK": ("DEVBHOOMI", "MUNI", "DWK-CITY"),
    "AND": ("ANAND", "TRAF", "AND-CITY"),
    "MEH": ("MEHSANA", "TRAF", "MEH-CITY"),
    "PAT": ("PATAN", "TRAF", "PAT-CITY"),
    "BRJ": ("BHARUCH", "TRAF", "BRJ-CITY"),
    "NAL": ("NAVSARI", "TRAF", "NAL-CITY"),
    "NAD": ("KHEDA", "TRAF", "NAD-CITY"),
    "GDR": ("PANCHMAHAL", "TRAF", "GDR-CITY"),
    "MOR": ("MORBI", "MUNI", "MOR-CITY"),
    "VLS": ("VALSAD", "TRAF", "VLS-CITY"),
}


VENDOR_CATALOG: list[tuple[str, str, str, str]] = [
    ("Hikvision", "DS-2CD-2XXX", "v5.5.61", "HIK"),
    ("Dahua", "IPC-HFW-3441", "v2.82", "DAH"),
    ("Axis", "P3267-V", "11.11", "AXIS"),
    ("Bosch", "DINION 6000i", "v7.3", "BOSCH"),
    ("Hanwha", "XNV-6080R", "v2.21", "HAN"),
    ("CP Plus", "CP-UNC-TA30L3", "v4.1", "CPP"),
    ("ONVIF", "Profile-S", "v1.0", "ONVIF"),
]


async def seed_registry(db, cameras_by_index: dict[int, Camera],
                         admin: User | None) -> bool:
    """Populate the global camera_registry from the seeded cameras (idempotent).

    Each camera gets a global CCTV code, ownership scoping (state/district/
    department/board) and GIS metadata so the coverage / gap analysis layers
    return meaningful data out of the box.

    Vendor diversity: cycles through 7 vendor profiles (Hikvision/Dahua/Axis/
    Bosch/Hanwha/CP Plus/ONVIF) to demonstrate heterogeneous onboarding.
    """
    if await _exists(db, CameraRegistry):
        return False
    if not cameras_by_index:
        return False
    count = 0
    for idx, cam in cameras_by_index.items():
        prefix = cam.name.split("-")[0] if cam.name else "UNK"
        district_code, department_code, board_code = DISTRICT_META.get(
            prefix, ("UNKNOWN", "TRAF", "UNK-CITY")
        )
        category = (
            CameraCategory.JUNCTION
            if idx % 4 == 0
            else CameraCategory.CITY if idx % 2 == 0 else CameraCategory.HIGHWAY
        )
        make, model, fw, vendor_id = VENDOR_CATALOG[idx % len(VENDOR_CATALOG)] if cam.name != "TEST-LAVFI-01" else ("Lavfi", "testsrc2", "sim", "LAVFI")
        db.add(
            CameraRegistry(
                camera_id=cam.id,
                cctv_code=f"IN-GJ-{district_code}-{cam.name}",
                serial_number=f"SN-{cam.name}",
                make=make,
                model=model,
                firmware=fw,
                category=category,
                ip_address=cam.rtsp_url.split("@")[-1].split(":")[0] if cam.rtsp_url and "@" in cam.rtsp_url else (cam.rtsp_url.split("://")[-1].split(":")[0].split("/")[0] if cam.rtsp_url else None),
                vendor_id=vendor_id,
                ownership_type=OwnershipType.STATE,
                state_code="GJ",
                district_code=district_code,
                department_code=department_code,
                board_code=board_code,
                latitude=cam.latitude or 0.0,
                longitude=cam.longitude or 0.0,
                gis_layer="junction",
                cluster_key=f"{district_code}/{department_code}",
                coverage_radius_m=250.0,
                last_health_score=88 if cam.status == CameraStatus.ONLINE else 40,
                uptime_pct=97.5 if cam.status == CameraStatus.ONLINE else 50.0,
                last_seen_at=cam.last_seen_at,
                registered_by=admin.id if admin else None,
                is_active=True,
                notes=f"Seeded registry row for {cam.name}.",
            )
        )
        count += 1
    await db.commit()
    return True


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
        if host.startswith("lavfi://"):
            rtsp = host
        else:
            # Vendor-specific RTSP path demonstrates heterogeneous VMS/URL conventions.
            _, _, _, vendor_id = VENDOR_CATALOG[idx % len(VENDOR_CATALOG)]
            if vendor_id == "HIK":
                rtsp = f"rtsp://admin:sentinel@{host}:554/Streaming/Channels/101"
            elif vendor_id == "DAH":
                rtsp = f"rtsp://admin:sentinel@{host}:554/cam/realmonitor?channel=1&subtype=0"
            elif vendor_id == "AXIS":
                rtsp = f"rtsp://{host}:554/axis-media/media.amp"
            elif vendor_id == "BOSCH":
                rtsp = f"rtsp://{host}:554/rtsp_tunnel"
            elif vendor_id == "HAN":
                rtsp = f"rtsp://{host}:554/profile0"
            elif vendor_id == "CPP":
                rtsp = f"rtsp://admin:sentinel@{host}:554/live/ch0"
            else:  # ONVIF
                rtsp = f"rtsp://{host}:554/onvif1"
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


async def seed_watchlists(db, users: list[User]) -> bool:
    if await _exists(db, Watchlist):
        return False
    admin = users[0].id if users else None
    for identifier, target_type, category, source_db, notes, active in WATCHLIST_ENTRIES:
        db.add(
            Watchlist(
                identifier_number=identifier,
                target_type=target_type,
                category=category,
                source_db=source_db,
                notes=notes,
                active=active,
                added_by=admin,
            )
        )
    await db.commit()
    return True


# fmt: off
# (plate, [ (camera_index, ts_delta_minutes, ocr_conf, vehicle_type, color) ... ])
DEMO_ANPR_DETECTIONS: list[tuple[str, list[tuple[int, int, float, str, str]]]] = [
    # Stolen Ahmedabad plate moving west->east across the AHM camera chain.
    ("GJ01AB1234", [
        (0, 40, 0.91, "car", "black"),   # AHM-SGH-01
        (1, 28, 0.88, "car", "black"),   # AHM-LAW-02
        (2, 15, 0.86, "car", "black"),   # AHM-MAN-03
        (3, 8, 0.93, "car", "black"),    # AHM-NAV-04
        (4, 2, 0.90, "car", "black"),    # AHM-ISK-05
    ]),
    # Wanted Surat plate on the SRT ring.
    ("GJ06XY9012", [
        (15, 30, 0.89, "bike", "red"),   # SRT-RNG-02
        (16, 18, 0.87, "bike", "red"),   # SRT-VRV-03
        (18, 6, 0.91, "bike", "red"),    # SRT-CHK-05
    ]),
]
# fmt: on


async def seed_anpr_detections(db, cameras_by_index: dict[int, Camera]) -> bool:
    """Populate a coherent ANPR detection chain so forensic dossiers and the
    interception vector are demonstrable end-to-end with real DB rows.

    Idempotent: no-ops when ``anpr_plate_detections`` already has rows. Only
    watches the plates already present on the watchlist, so the alert -> dossier
    -> interception flow is internally consistent.
    """
    if await _exists(db, PlateDetection) or not cameras_by_index:
        return False
    created = 0
    for plate, hops in DEMO_ANPR_DETECTIONS:
        for idx, (camera_idx, mins_ago, ocr_conf, vtype, color) in enumerate(hops):
            cam = cameras_by_index.get(camera_idx)
            if cam is None:
                continue
            prefix = cam.name.split("-")[0]
            district_code, department_code, _ = DISTRICT_META.get(
                prefix, ("UNKNOWN", "TRAF", "UNK-CITY")
            )
            db.add(
                PlateDetection(
                    camera_id=cam.id,
                    camera_name=cam.name,
                    location=cam.location,
                    latitude=cam.latitude,
                    longitude=cam.longitude,
                    plate=plate,
                    normalized_plate=plate.upper().replace(" ", ""),
                    state_code="GJ",
                    rto_code=plate[2:4],
                    ocr_confidence=ocr_conf,
                    detection_confidence=round(ocr_conf - 0.04, 2),
                    vehicle_type=vtype,
                    color=color,
                    make="Maruti" if vtype == "car" else "Honda",
                    model="Swift" if vtype == "car" else "Activa",
                    attribute_confidence=0.86,
                    x=0.4 + idx * 0.05,
                    y=0.35,
                    w=0.12,
                    h=0.05,
                    backend="sim",
                    frame_seq=idx + 1,
                    ts=_ago(minutes=mins_ago),
                )
            )
            created += 1
    await db.commit()
    log.info("seed.anpr_detections", created=created, plates=len(DEMO_ANPR_DETECTIONS))
    return True


async def run_seed() -> None:
    """Run the full, idempotent seed routine."""
    await init_db()
    async with AsyncSessionLocal() as db:
        users = await seed_users(db)
        cameras, cameras_by_index = await seed_cameras(db)
        created_alerts = await seed_alerts(db, cameras_by_index)
        created_incidents = await seed_incidents(db, users, cameras_by_index)
        created_watchlists = await seed_watchlists(db, users)
        created_registry = await seed_registry(db, cameras_by_index, users[0] if users else None)
        created_anpr = await seed_anpr_detections(db, cameras_by_index)
        log.info(
            "seed.complete",
            users=len(users),
            cameras=len(cameras),
            created_alerts=created_alerts,
            created_incidents=created_incidents,
            created_watchlists=created_watchlists,
            created_registry=created_registry,
            created_anpr=created_anpr,
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_seed())
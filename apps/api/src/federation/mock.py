"""Deterministic mock provider for camera devices, VMS and government DBs.

Phase 6 has no live lab cameras, genuine Government APIs or vendor hardware.
These providers emulate the interface using stable, seeded randomness so that
tests and the validation report are reproducible. Real integrations replace the
mock adapter/connector behind the same ABC contract.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from src.federation.models import CameraState, StreamProtocol

_SEED_KEYS = {
    "camera": 20260601,
    "vms": 20260602,
    "vahan": 20260603,
    "sarathi": 20260604,
    "egujcop": 20260605,
    "afis": 20260606,
    "nafis": 20260607,
    "health": 20260608,
}


def _rng(namespace: str, salt: str = "") -> random.Random:
    seed = int(hashlib.md5(f"{_SEED_KEYS.get(namespace, 0)}:{salt}".encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def mock_device(vendor: str, host: str | None = None) -> dict[str, Any]:
    rng = _rng("camera", f"{vendor}:{host or ''}")
    protocols = [StreamProtocol.RTSP]
    if rng.random() < 0.5:
        protocols.append(StreamProtocol.HLS)
    if rng.random() < 0.3:
        protocols.append(StreamProtocol.MJPEG)
    return {
        "vendor": vendor,
        "model": f"{vendor.title()} XC-{rng.randint(1000, 9999)}",
        "firmware": f"V{rng.randint(1, 5)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}",
        "serial": f"{vendor.upper()}-{rng.randint(100000, 999999)}",
        "protocols": [p.value for p in protocols],
        "max_streams": rng.randint(1, 4),
        "supports_ptz": rng.random() < 0.3,
        "supports_analytics": True,
        "has_storage": rng.random() < 0.5,
    }


def mock_health(vendor: str, host: str | None = None) -> dict[str, Any]:
    rng = _rng("health", f"{vendor}:{host or ''}")
    latency = rng.randint(20, 250)
    if rng.random() < 0.9:
        return {
            "status": "ok",
            "latency_ms": latency,
            "bitrate_kbps": rng.randint(1500, 12000),
            "signal": rng.randint(70, 100),
            "detail": {"probe": "mock", "reachable": True},
        }
    return {
        "status": "offline",
        "latency_ms": None,
        "bitrate_kbps": None,
        "signal": 0,
        "detail": {"probe": "mock", "reachable": False, "reason": "simulated outage"},
    }


def mock_vms_summary(vms_name: str) -> dict[str, Any]:
    rng = _rng("vms", vms_name)
    return {
        "vms": vms_name,
        "total_cameras": rng.randint(500, 90000),
        "online": rng.randint(400, 80000),
        "recording": rng.randint(300, 60000),
        "version": "simulated",
    }


# --- Government database lookups ------------------------------------------------
def _plate_parts(identifier: str) -> tuple[str, str]:
    id_l = identifier.strip().upper().replace(" ", "")
    return id_l[:2], id_l[2:]


def mock_vahan_lookup(registration: str) -> dict[str, Any]:
    rng = _rng("vahan", registration)
    state, rest = _plate_parts(registration)
    if len(rest) < 4:
        return {"matched": False, "reason": "regno_too_short"}
    if "ZZ" in rest:
        return {"matched": False, "reason": "not_found"}
    owner = f"OWNER-{rng.randint(1000, 9999)}"
    return {
        "matched": True,
        "registration": f"{state} {rest}",
        "state": "Gujarat",
        "rc_state": state,
        "rc_owner": owner,
        "rc_class": "Motor Car (LMV)",
        "maker": "SIMULATED",
        "model": "MOCK-2026",
        "fuel": rng.choice(["Petrol", "Diesel", "CNG", "Electric"]),
        "rc_insurance_valid": rng.random() < 0.85,
        "rc_fitness_valid": rng.random() < 0.9,
        "rc_status": "valid",
        "owner_name": owner,
    }


def mock_sarathi_lookup(dl_number: str) -> dict[str, Any]:
    rng = _rng("sarathi", dl_number)
    if "INVALID" in dl_number.upper() or len(str(dl_number)) < 6:
        return {"matched": False, "reason": "dl_not_found"}
    return {
        "matched": True,
        "dl_number": dl_number,
        "name": f"DRIVER-{rng.randint(1000, 9999)}",
        "dl_status": "valid",
        "class_of_vehicle": ["LMV-NT", "LMV-T"],
        "dl_valid_till": "2030-01-01",
        "dl_cur_address": "SIMULATED ADDRESS, Gujarat",
        "date_of_birth": "1990-01-01",
    }


def mock_egujcop_lookup(type_: str, identifier: str) -> dict[str, Any]:
    rng = _rng("egujcop", f"{type_}:{identifier}")
    if "MISSING" in identifier.upper():
        return {"matched": False, "reason": "complaint_not_found"}
    return {
        "matched": True,
        "complaint_id": identifier,
        "type": type_,
        "status": rng.choice(["FIR Registered", "Under Investigation", "Closed"]),
        "fir_number": f"FIR/{rng.randint(1000, 9999)}/{2026}",
        "police_station": "SIMULATED PS",
        "officer": f"IO-{rng.randint(100, 999)}",
    }


def mock_afis_lookup(fingerprint_id: str) -> dict[str, Any]:
    rng = _rng("afis", fingerprint_id)
    if fingerprint_id.startswith("NOMATCH"):
        return {"matched": False, "score": rng.uniform(0.1, 0.4)}
    return {
        "matched": True,
        "candidate_id": f"PERSON-{rng.randint(100000, 999999)}",
        "score": round(rng.uniform(0.9, 0.999), 3),
        "bio_type": "tenprint",
        "prior_cases": rng.randint(0, 12),
    }


def mock_nafis_lookup(identifier: str) -> dict[str, Any]:
    rng = _rng("nafis", identifier)
    if identifier.startswith("NOMATCH"):
        return {"matched": False, "score": rng.uniform(0.1, 0.4)}
    return {
        "matched": True,
        "candidate_id": f"NP-{rng.randint(100000, 999999)}",
        "score": round(rng.uniform(0.92, 0.999), 3),
        "nationality": "IN",
        "prior_records": rng.randint(0, 20),
    }

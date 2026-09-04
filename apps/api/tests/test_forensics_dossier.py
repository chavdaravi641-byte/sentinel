"""Forensic dossier unit tests (no DB, no network).

Covers canonicalisation + integrity sealing, tamper-evidence, markdown and
deterministic PDF rendering.
"""

from __future__ import annotations

from src.forensics.dossier import (
    DossierSighting,
    canonical_json,
    compute_integrity,
    render_dossier_markdown,
    render_dossier_pdf,
    _seal,
)

SIGHTING = DossierSighting(
    detection_id="d1",
    camera_id="c1",
    cctv_code="IN-GJ-AHM-JCT-000001",
    camera_name="Maninagar Crossing",
    location="Maninagar",
    district_code="AHM",
    department_code="CITY",
    latitude=23.02,
    longitude=72.57,
    ts="2026-01-01T10:00:00+00:00",
    ocr_confidence=0.9,
    detection_confidence=0.85,
    vehicle_type="car",
    color="white",
    make="Toyota",
    model="Corolla",
    state_code="GJ",
    rto_code="01",
)

WATCHLIST = {
    "matched": True,
    "source_db": "vahan",
    "category": "stolen_vehicle",
    "notes": "Reported stolen",
    "active": True,
}


def test_canonical_json_sorted_and_deterministic():
    a = canonical_json({"b": 2, "a": 1, "nested": {"z": 0, "y": 1}})
    b = canonical_json({"nested": {"y": 1, "z": 0}, "a": 1, "b": 2})
    assert a == b
    assert a == '{"a":1,"b":2,"nested":{"y":1,"z":0}}'


def test_compute_integrity_sha256_length():
    digest = compute_integrity({"plate": "GJ01AB1234"})
    assert len(digest) == 64
    assert digest == compute_integrity({"plate": "GJ01AB1234"})


def test_dossier_sealing_and_verify():
    fd = _seal(
        "GJ01AB1234",
        "GJ01AB1234",
        WATCHLIST,
        [SIGHTING],
        "2026-01-01T12:00:00+00:00",
    )
    assert fd.verify() is True
    assert fd.integrity_sha256
    assert fd.counts()["sightings"] == 1
    assert fd.counts()["distinct_cameras"] == 1


def test_dossier_tamper_detection():
    fd = _seal("GJ01AB1234", "GJ01AB1234", WATCHLIST, [SIGHTING], "2026-01-01T12:00:00+00:00")
    # Rebuild the manifest with an altered location and confirm hash mismatch.
    tampered = _seal(
        "GJ01AB1234",
        "GJ01AB1234",
        WATCHLIST,
        [
            DossierSighting(
                detection_id="d1",
                camera_id="c1",
                cctv_code="IN-GJ-AHM-JCT-000001",
                camera_name="Maninagar Crossing",
                location="CHANGED",
                district_code="AHM",
                department_code="CITY",
                latitude=23.02,
                longitude=72.57,
                ts="2026-01-01T10:00:00+00:00",
                ocr_confidence=0.9,
                detection_confidence=0.85,
                vehicle_type="car",
                color="white",
                make="Toyota",
                model="Corolla",
                state_code="GJ",
                rto_code="01",
            )
        ],
        "2026-01-01T12:00:00+00:00",
    )
    assert tampered.integrity_sha256 != fd.integrity_sha256
    # And the sealed order also fails verification if the digest doesn't match.
    assert tampered.verify() is True  # internally consistent -> re-seal matches
    # Cross-check: overriding the digest to the original is detectable.
    tampered.integrity_sha256 = fd.integrity_sha256
    assert tampered.verify() is False


def test_render_markdown_contains_integrity():
    fd = _seal("GJ01AB1234", "GJ01AB1234", WATCHLIST, [SIGHTING], "2026-01-01T12:00:00+00:00")
    md = render_dossier_markdown(fd)
    assert fd.integrity_sha256 in md
    assert "GJ01AB1234" in md
    assert "Maninagar" in md


def test_render_pdf_deterministic_and_valid_header():
    fd = _seal("GJ01AB1234", "GJ01AB1234", WATCHLIST, [SIGHTING], "2026-01-01T12:00:00+00:00")
    pdf = render_dossier_pdf(fd)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf
    # deterministic output
    assert pdf == render_dossier_pdf(fd)
    # integrity digest embedded in the content stream
    assert fd.integrity_sha256.encode("latin-1") in pdf


def test_render_pdf_special_characters_escaped():
    sighting = DossierSighting(
        detection_id="d2",
        camera_id="c2",
        cctv_code="IN-GJ-NAV-JCT-000002",
        camera_name="Navsari (Main)",
        location="Navsari",
        district_code="NAV",
        department_code="RURAL",
        latitude=20.95,
        longitude=72.92,
        ts="2026-01-02T09:00:00+00:00",
        ocr_confidence=0.7,
        detection_confidence=0.6,
        vehicle_type="bike",
        color="black",
        make="Honda",
        model=None,
        state_code="GJ",
        rto_code="21",
    )
    fd = _seal("GJ21BB5555", "GJ21BB5555", None, [sighting], "2026-01-02T12:00:00+00:00")
    pdf = render_dossier_pdf(fd)
    assert pdf.startswith(b"%PDF-1.4")
    # Parentheses in camera name must be escaped so the stream stays balanced.
    assert b"\\(Main\\)" in pdf

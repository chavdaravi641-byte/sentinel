"""Phase 6 (Model 1) — Statewide CCTV Registry & GIS Foundation unit tests.

No DB / no network. Exercises the pure-Python reg: roster, RBAC, bulk
onboarding (csv/xlsx/json parsing + validation + dedup + preview + rollback),
GIS math (haversine/coverage/cluster/gap/density), health scoring, search
(11 filters), audit diffing and the 80k+ load benchmark.
"""

from __future__ import annotations

from src.registry import (
    SearchSpec,
    apply_filters,
    build_plan,
    diff_before_after,
    greedy_clusters,
    haversine_m,
    paginate,
    parse_csv,
    parse_json,
    parse_xlsx,
    run_benchmark,
    score_camera,
    summarize_changes,
)
from src.registry.audit import AuditRecord
from src.registry.cluster import aggregate_by_district, kmean_clusters
from src.registry.coverage import CameraPoint, analyze, blind_spots, density_grid, road_coverage
from src.registry.geography import bbox_of, circle_intersection_area, point_at, union_area_of_coverage
from src.registry.gap import low_density_zones, run_gap_report
from src.registry.health import HealthRule, fleet_health
from src.registry.onboard import commit_plan
from src.registry.parsers import build_header_mapping
from src.registry.roles import RegistryScope, RegistryUser, build_permission_matrix, rank_of
from src.registry.search import FILTER_KEYS, build_sql_filter
from src.registry.validate import validate_record
from src.models.camera import CameraStatus
from src.models.registry import AccessRole, RegistryEventType


# --------------------------------------------------------------------------- #
# Roles / RBAC
# --------------------------------------------------------------------------- #
def test_six_roles_and_rank():
    assert {r.value for r in AccessRole} == {
        "state_admin", "department_admin", "district_admin", "operator", "maintenance", "viewer",
    }
    assert rank_of(AccessRole.STATE_ADMIN) > rank_of(AccessRole.OPERATOR)
    assert rank_of(AccessRole.VIEWER) < rank_of(AccessRole.MAINTENANCE)


def test_role_permissions_and_scope():
    state = RegistryUser.from_platform("u1", "admin")
    assert state.can("delete") and state.can("ownership") and state.can("audit")
    viewer = RegistryUser.from_platform("u2", "viewer")
    assert viewer.can("view") and viewer.can("search")
    assert not viewer.can("create") and not viewer.can("delete")
    # District admin scoped to one district.
    RegistryUser.from_platform("u3", "operator", district_code="AHM")
    dist_scope = RegistryScope(kind="district", district_code="AHM")
    assert dist_scope.describes(state_code="GJ", district_code="AHM")
    assert not dist_scope.describes(state_code="GJ", district_code="SRT")


def test_permission_matrix_snapshot():
    matrix = build_permission_matrix()
    assert "state_admin" in matrix and "viewer" in matrix
    assert set(matrix["viewer"]) == {"search", "view"}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def test_csv_parsing_normalises_records():
    content = "cctv_code,name,latitude,longitude,district_code\nIN-GJ-AHM-1,Cam A,23.03,72.55,AHM\nIN-GJ-SRT-2,Cam B,21.15,72.78,SRT\n"
    records, unused = parse_csv(content)
    assert len(records) == 2
    assert records[0]["cctv_code"] == "IN-GJ-AHM-1"
    assert records[0]["latitude"] == "23.03"
    assert unused == []


def test_json_parsing():
    content = '{"items": [{"cctv_code": "IN-GJ-AHM-1", "name": "Cam A", "lat": 23.03, "lng": 72.55}]}'
    records, unused = parse_json(content)
    assert records[0]["cctv_code"] == "IN-GJ-AHM-1"
    assert records[0]["latitude"] == 23.03
    assert records[0]["longitude"] == 72.55


def test_xlsx_parsing_pure_stdlib():
    # Build a minimal valid xlsx in-memory with only stdlib (zipfile/xml).
    import xml.etree.ElementTree as ET  # noqa: PLC0415
    from io import BytesIO
    from zipfile import ZipFile
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ns_rel = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    ns_off = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

    def _cell(ref, t, v):
        return ET.Element(ns + "c", {"r": ref, "t": t}) if t else ET.Element(ns + "c", {"r": ref}) or None

    # sheet
    sheet = ET.Element(ns + "worksheet")
    sdata = ET.SubElement(sheet, ns + "sheetData")

    def add_row(cells):
        row = ET.SubElement(sdata, ns + "row")
        for ref, t, val in cells:
            c = ET.SubElement(row, ns + "c", {"r": ref, "t": t}) if t else ET.SubElement(row, ns + "c", {"r": ref})
            if val != "":
                v = ET.SubElement(c, ns + "v")
                v.text = str(val)

    add_row([("A1", "s", "0"), ("B1", "s", "1"), ("C1", "s", "2"), ("D1", "s", "3")])
    add_row([("A2", "s", "4"), ("B2", "s", "5"), ("C2", None, "23.03"), ("D2", None, "72.55")])
    sheet_xml = ET.tostring(sheet)

    # shared strings
    ss = ET.Element(ns + "sst")
    for text in ["cctv_code", "name", "latitude", "longitude", "IN-GJ-AHM-1", "Cam A"]:
        si = ET.SubElement(ss, ns + "si")
        t = ET.SubElement(si, ns + "t")
        t.text = text
    ss_xml = ET.tostring(ss)

    # workbook + rels
    wb = ET.Element(ns + "workbook")
    sheets = ET.SubElement(wb, ns + "sheets")
    ET.SubElement(sheets, ns + "sheet", {"name": "Sheet1", ns_off + "id": "rId1"})
    wb_xml = ET.tostring(wb)
    rels = ET.Element(ns_rel + "Relationships")
    ET.SubElement(rels, ns_rel + "Relationship",
                  {"Id": "rId1", "Type": "worksheet", "Target": "worksheets/sheet1.xml"})
    rels_xml = ET.tostring(rels)

    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", wb_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zf.writestr("xl/sharedStrings.xml", ss_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    records, unused = parse_xlsx(buf.getvalue())
    assert len(records) == 1
    assert records[0]["cctv_code"] == "IN-GJ-AHM-1"
    assert records[0]["latitude"] == 23.03


def test_header_mapping_aliases():
    mapping = build_header_mapping(["CCTV Code", "Lat", "Lng", "District", "Unknown"])
    assert mapping["CCTV Code"] == "cctv_code"
    assert mapping["Lat"] == "latitude"
    assert mapping["Lng"] == "longitude"
    assert mapping["District"] == "district_code"
    assert "Unknown" not in mapping


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_validate_record_good_and_bad():
    good = {"cctv_code": "IN-GJ-AHM-1", "name": "Cam", "location": "Rd",
            "latitude": "23.03", "longitude": "72.55", "district_code": "AHM"}
    bad = {"cctv_code": "bad code!", "name": "Cam", "location": "",
           "latitude": "999", "longitude": "72.55", "district_code": "AHM"}
    assert validate_record(good, 2) == []
    errs = validate_record(bad, 2)
    codes = {e.code for e in errs}
    assert "range" in codes and "format" in codes and "required" in codes


# --------------------------------------------------------------------------- #
# Onboarding
# --------------------------------------------------------------------------- #
def _empty_existing(_codes):
    return set()


def test_build_plan_valid_commit_and_rollback():
    content = ("cctv_code,name,location,latitude,longitude,district_code\n"
               "IN-GJ-AHM-1,Cam A,Rd,23.03,72.55,AHM\n"
               "IN-GJ-SRT-2,Cam B,Rd,21.15,72.78,SRT\n")
    plan = build_plan("csv", content, _empty_existing)
    assert plan.valid == 2 and plan.errored == 0 and plan.can_commit

    written: list[dict] = []
    committed = commit_plan(plan, written.extend, chunk_size=1)
    assert committed["committed"] == 2
    assert len(written) == 2


def test_build_plan_duplicate_and_error_rows():
    content = ("cctv_code,name,location,latitude,longitude,district_code\n"
               "IN-GJ-AHM-1,Cam A,Junction,23.03,72.55,AHM\n"   # ok
               "IN-GJ-AHM-1,Cam dup,Junction,23.03,72.55,AHM\n"  # duplicate
               "X,Cam bad,Rd,999,72.55,AHM\n")                   # error
    plan = build_plan("csv", content, _empty_existing)
    statuses = [r.status() for r in plan.rows]
    assert "error" in statuses and "duplicate" in statuses and "ok" in statuses
    assert plan.can_commit is False


def test_build_plan_dedupes_against_existing():
    content = ("cctv_code,name,location,latitude,longitude,district_code\n"
               "IN-GJ-AHM-1,Cam A,Rd,23.03,72.55,AHM\n")
    plan = build_plan("csv", content, lambda _c: {"IN-GJ-AHM-1"})
    assert plan.duplicates == 1 and plan.valid == 0


# --------------------------------------------------------------------------- #
# GIS math
# --------------------------------------------------------------------------- #
def test_haversine_known_distance():
    # Ahmedabad -> Gandhinagar ~25km.
    d = haversine_m(23.0225, 72.5714, 23.2232, 72.6490)
    assert 23000 < d < 27000
    # Same point.
    assert haversine_m(1, 1, 1, 1) < 1e-6


def test_circle_intersection_bounds():
    assert circle_intersection_area(0, 0, 0, 0, 1000) > 0          # identical
    assert circle_intersection_area(0, 0, 0, 0.05, 1000) == 0.0    # far apart


def test_point_at_and_bbox():
    lat, lon = point_at(0, 0, 1000, 90)
    assert abs(abs(lon) - 1000 / 6371000 * (180 / 3.14159)) < 1e-3
    box = bbox_of([(1, 2), (3, 4)])
    assert box == (1, 2, 3, 4)


def test_union_area_at_least_single_circle():
    pts = [(23.02, 72.57)]
    u = union_area_of_coverage(pts, 1000, grid=60)
    assert u > 2_000_000  # pi*r^2 ~ 3.14e6


# --------------------------------------------------------------------------- #
# Coverage / cluster / gap
# --------------------------------------------------------------------------- #
def _mk(id_, lat, lon, radius=250, cat="city", dist="AHM"):
    return CameraPoint(id=id_, lat=lat, lon=lon, radius_m=radius, category=cat,
                       status="online", district_code=dist)


def test_coverage_analysis_and_blind_spots():
    pts = [_mk("a", 23.02, 72.57, radius=5000), _mk("b", 23.03, 72.58, radius=5000),
           _mk("c", 21.15, 72.78, radius=5000)]
    rep = analyze(pts, cell_m=200)
    assert rep["cameras"] == 3
    assert rep["effective_area_m2"] > 0
    assert rep["efficiency_pct"] <= 100.0
    bs = blind_spots(pts, cell_m=1000)
    assert bs["cell_m"] == 1000


def test_density_grid_and_road_coverage():
    pts = [_mk("a", 23.02, 72.57), _mk("b", 23.03, 72.58)]
    dens = density_grid(pts, cell_m=5000, radius_m=5000)
    assert any(d["count"] >= 2 for d in dens)
    cov = road_coverage(pts, [(23.022, 72.572)], radius_m=5000)
    assert cov["coverage_pct"] == 100.0


def test_greedy_and_kmeans_clusters():
    pts = [_mk("a", 23.02, 72.57), _mk("b", 23.03, 72.58), _mk("c", 21.15, 72.78)]
    g = greedy_clusters(pts, radius_m=5000)
    assert len(g) == 2  # a+b cluster, c alone
    same = next(x for x in g if "a" in x["member_ids"] or "b" in x["member_ids"])
    assert same["count"] == 2
    k = kmean_clusters(pts, 2)
    assert len(k) == 2
    assert sum(x["count"] for x in k) == 3


def test_aggregate_by_district():
    pts = [_mk("a", 23.0, 72.5, dist="AHM"), _mk("b", 21.1, 72.7, dist="SRT"),
           _mk("c", 23.1, 72.6, dist="AHM")]
    agg = aggregate_by_district(pts)
    by_code = {d["district_code"]: d["count"] for d in agg}
    assert by_code["AHM"] == 2 and by_code["SRT"] == 1


def test_gap_report_zones():
    pts = [_mk("a", 23.02, 72.57), _mk("b", 21.15, 72.78)]
    report = run_gap_report(pts, cell_m=5000)
    assert report["camera_count"] == 2
    assert isinstance(report["recommended_placements"], list)
    zones = low_density_zones(pts, cell_m=5000, threshold=1, radius_m=3000)
    assert zones  # uncovered cells exist


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
def test_health_scoring():
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    from datetime import timedelta  # noqa: PLC0415
    healthy = score_camera(CameraStatus.ONLINE, now, 0.95, now=now)
    assert healthy["score"] >= 85 and healthy["level"] == "healthy"
    stale = score_camera(CameraStatus.ONLINE, now - timedelta(days=2), 0.5, now=now)
    assert stale["score"] < healthy["score"]
    fleet = fleet_health([healthy, stale])
    assert fleet["total"] == 2 and fleet["avg_score"] > 0


def test_health_rule_custom():
    rule = HealthRule(online_base=100, offline_penalty=80, maintenance_ceiling=50)
    assert score_camera("maintenance", None, None, rule=rule)["score"] < 70


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def _rec(cctv_code="IN-GJ-AHM-1", name="Cam A", district="AHM", cat="junction",
         status="online", lat=23.03, lon=72.55, gis_layer="urban"):
    return {"cctv_code": cctv_code, "name": name, "district_code": district,
            "category": cat, "status": status, "latitude": lat, "longitude": lon,
            "health_level": "healthy", "gis_layer": gis_layer}


def test_search_eleven_filters_composable():
    records = [_rec(), _rec("IN-GJ-SRT-2", "Cam B", "SRT", "highway", "offline", 21.15, 72.78, "rural"),
               _rec("IN-GJ-AHM-3", "Cam C", "AHM", "signal", "online", 23.04, 72.56)]
    assert FILTER_KEYS == [
        "query", "district_code", "department_code", "board_code", "category",
        "status", "ownership_type", "health_level", "gis_layer", "cluster_key", "geo",
    ]
    r = apply_filters(records, SearchSpec(district_code="AHM", category="junction"))
    assert len(r) == 1 and r[0]["name"] == "Cam A"
    r = apply_filters(records, SearchSpec(query="B", status="offline"))
    assert len(r) == 1 and r[0]["cctv_code"] == "IN-GJ-SRT-2"
    r = apply_filters(records, SearchSpec(geo_lat=23.03, geo_lng=72.55, geo_radius_m=10000))
    assert len(r) == 2  # A and C within 10km of A
    r = apply_filters(records, SearchSpec(health_level="healthy", gis_layer="urban"))
    assert len(r) == 2


def test_search_paginate_and_sql_builder():
    records = [_rec(f"IN-GJ-AHM-{i}", f"Cam {i}", "AHM") for i in range(5)]
    page = paginate(records, 2, 2)
    assert page["total"] == 5 and page["pages"] == 3 and len(page["items"]) == 2
    where, params = build_sql_filter(SearchSpec(district_code="AHM", category="junction"))
    assert "district_code" in where and params["district_code"] == "AHM"


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def test_audit_diff_and_summary():
    before = {"name": "Old", "district_code": "AHM"}
    after = {"name": "New", "district_code": "SRT"}
    changes = diff_before_after(before, after)
    assert set(changes) == {"name", "district_code"}
    assert summarize_changes(changes) != "no changes"
    rec = AuditRecord(event_type=RegistryEventType.UPDATE, summary="edit", actor_id="u1",
                      camera_id="c1", before=before, after=after)
    kwargs = rec.to_model_kwargs()
    assert kwargs["event_type"] == RegistryEventType.UPDATE
    assert kwargs["before"] == before


# --------------------------------------------------------------------------- #
# Load benchmark
# --------------------------------------------------------------------------- #
def test_benchmark_80k_runs_and_reports_metrics():
    report = run_benchmark(n_cameras=80_000)
    assert report["synthetic"] is True
    assert report["n_cameras"] == 80_000
    m = report["metrics"]
    for key in ("search_combined_filter_ms", "geo_radius_filter_ms",
                "clustering_ms", "gap_analysis_ms_cameras_5k",
                "health_scoring_ms_cameras_10k"):
        assert m[key] >= 0.0, key
    assert report["returned"]["cluster_count"] > 0
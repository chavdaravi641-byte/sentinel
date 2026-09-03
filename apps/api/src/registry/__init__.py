"""Statewide CCTV Registry & GIS Foundation (Model 1, Phase 6).

A self-contained, additive package on top of the existing Sentinel AI
platform. Everything here is pure-Python (no GeoAlchemy2 / openpyxl / pandas /
DB) so the whole engine is unit-testable in the API container and reused by
the FastAPI endpoints under ``/api/v1/registry``.
"""

from src.models.registry import AccessRole
from src.registry.audit import AuditRecord, diff_before_after, summarize_changes
from src.registry.benchmark import run_benchmark
from src.registry.cluster import aggregate_by_district, greedy_clusters, kmean_clusters
from src.registry.coverage import CameraPoint, analyze, road_coverage
from src.registry.dashboard import (
    all_widgets,
    category_breakdown,
    district_breakdown,
    health_breakdown,
    onboarding_summary,
    ownership_breakdown,
    registry_overview,
    status_breakdown,
)
from src.registry.gap import low_density_zones, run_gap_report
from src.registry.geography import haversine_m
from src.registry.health import HealthRule, fleet_health, score_camera
from src.registry.onboard import ImportPlan, build_plan, commit_plan, parse_raw
from src.registry.parsers import parse_csv, parse_json, parse_xlsx
from src.registry.search import SearchSpec, apply_filters, paginate
from src.registry.validate import validate_record, validate_records

__all__: list[str] = [
    "AccessRole",
    "AuditRecord",
    "CameraPoint",
    "ImportPlan",
    "SearchSpec",
    "aggregate_by_district",
    "all_widgets",
    "analyze",
    "apply_filters",
    "build_plan",
    "category_breakdown",
    "commit_plan",
    "diff_before_after",
    "district_breakdown",
    "fleet_health",
    "greedy_clusters",
    "haversine_m",
    "health_breakdown",
    "HealthRule",
    "kmean_clusters",
    "low_density_zones",
    "onboarding_summary",
    "ownership_breakdown",
    "paginate",
    "parse_csv",
    "parse_json",
    "parse_raw",
    "parse_xlsx",
    "registry_overview",
    "road_coverage",
    "run_benchmark",
    "run_gap_report",
    "score_camera",
    "status_breakdown",
    "summarize_changes",
    "validate_record",
    "validate_records",
]
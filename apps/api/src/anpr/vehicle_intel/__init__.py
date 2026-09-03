"""Phase 5 — Global Vehicle Identity Engine.

Pure-Python, dependency-light implementation for:
- global vehicle identity (stable UUID),
- camera graph abstraction derived from real registered cameras,
- cross-camera association,
- route reconstruction / prediction,
- traffic intelligence,
- evidence timeline + investigation workspace,
- MOT-style + Phase 5 validation metrics + benchmark.
"""

from src.anpr.vehicle_intel.identity import assign_identity, VehicleIdentity
from src.anpr.vehicle_intel.graph import CameraGraph, build_graph_from_cameras, GraphConfig
from src.anpr.vehicle_intel.association import associate, AssociationResult
from src.anpr.vehicle_intel.reconstruction import reconstruct_route
from src.anpr.vehicle_intel.prediction import predict_next_cameras, TransitionModel
from src.anpr.vehicle_intel.timeline import build_evidence_timeline
from src.anpr.vehicle_intel.traffic import compute_traffic_insights
from src.anpr.vehicle_intel.metrics import compute_phase5_metrics, compute_mot_metrics
from src.anpr.vehicle_intel.multimodal import (
    fuse_identity,
    FusedIdentity,
    VehicleCandidate,
    effective_plate_weight,
)

__all__ = [
    "assign_identity",
    "VehicleIdentity",
    "CameraGraph",
    "build_graph_from_cameras",
    "GraphConfig",
    "associate",
    "AssociationResult",
    "reconstruct_route",
    "predict_next_cameras",
    "TransitionModel",
    "build_evidence_timeline",
    "compute_traffic_insights",
    "compute_phase5_metrics",
    "compute_mot_metrics",
    "fuse_identity",
    "FusedIdentity",
    "VehicleCandidate",
    "effective_plate_weight",
]

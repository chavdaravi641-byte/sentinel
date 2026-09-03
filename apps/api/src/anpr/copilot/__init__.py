"""Phase 6 — Sentinel AI Police Copilot.

An AI investigation assistant over stored CCTV detections. Turns natural-language
investigation requests into structured, executable search plans and produces
traceable, explainable intelligence (never fabricated).

Modules:

* ``plan``      — shared dataclasses (intents, filters, plans, windows)
* ``nl``        — natural-language -> structured plan engine
* ``analysis``  — analytic intents (multi-district, night visitors, related)
* ``executor``  — executes a plan against stored detections
* ``evidence``  — evidence package builder
* ``timeline``  — investigation timeline + route reconstruction
* ``explain``   — explainable-AI rationale
* ``cases``     — case workspace + audit log
* ``pdf``       — PDF investigation report generator
* ``validation``— Phase 6 validation harness
"""

from src.anpr.copilot.plan import (
    INTENT_EVIDENCE,
    INTENT_FIND_VEHICLES,
    INTENT_MULTI_DISTRICT,
    INTENT_RELATED_VEHICLES,
    INTENT_REPEATED_NIGHT,
    INTENT_TIMELINE,
    INTENT_UNKNOWN,
    INTENT_VEHICLES_NEAR,
    SearchFilters,
    SearchPlan,
    TimeWindow,
)
from src.anpr.copilot.nl import NaturalLanguagePlanner
from src.anpr.copilot.analysis import (
    district_of,
    multi_district_vehicles,
    related_vehicles,
    repeated_night_visitors,
)
from src.anpr.copilot.cases import CaseWorkspace
from src.anpr.copilot.pdf import PDFReportGenerator

__all__ = [
    "INTENT_EVIDENCE",
    "INTENT_FIND_VEHICLES",
    "INTENT_MULTI_DISTRICT",
    "INTENT_RELATED_VEHICLES",
    "INTENT_REPEATED_NIGHT",
    "INTENT_TIMELINE",
    "INTENT_UNKNOWN",
    "INTENT_VEHICLES_NEAR",
    "SearchFilters",
    "SearchPlan",
    "TimeWindow",
    "NaturalLanguagePlanner",
    "district_of",
    "multi_district_vehicles",
    "related_vehicles",
    "repeated_night_visitors",
    "CaseWorkspace",
    "PDFReportGenerator",
]

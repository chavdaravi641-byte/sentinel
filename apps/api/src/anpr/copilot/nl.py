"""Phase 6 Copilot — Natural Language Investigation engine.

Converts a free-form police investigation request into a structured, executable
`SearchPlan` with per-step rationale (explainable AI). The engine is fully
deterministic (rule-based; no external LLM dependency) so it runs identically in
Docker and is unit-testable. Where the query is ambiguous or unsupported, the
parser records explicit `warnings` and degrades gracefully rather than guessing.

The planner recognises:

* attributes        — vehicle type, colour, make, model, state, district, camera
* plate             — exact or partial plate strings
* time              — "after 8 PM", "before 20:00", "last 3 hours", "today",
                      "yesterday", named windows
* analytic intents  — "crossed N districts", "repeated night visitors",
                      "travelling together" (convoy), "similar vehicles"

Every query produces a `confidence` (how strongly the tokens map to plan
fields), an ordered list of `steps` (what will be executed and why), and
`warnings` for anything that could not be interpreted.
"""

from __future__ import annotations

import datetime as dt
import re

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

# --------------------------------------------------------------------------- #
# Knowledge tables (extendable; combined with rto_data STATES on demand)
# --------------------------------------------------------------------------- #
VEHICLE_TYPES = {
    "suv": "suv", "suvs": "suv", "mpv": "mpv",
    "sedan": "sedan", "car": "car", "cars": "car", "hatchback": "hatchback",
    "truck": "truck", "lorry": "truck", "trucks": "truck", "tempo": "truck",
    "bus": "bus", "buses": "bus", "van": "van", "vans": "van",
    "motorcycle": "motorcycle", "motorbike": "motorcycle", "bike": "motorcycle",
    "two wheeler": "motorcycle", "auto": "auto", "rickshaw": "auto",
    "three wheeler": "auto", "pickup": "pickup", "pickup truck": "pickup",
}

COLORS = {
    "white": "white", "black": "black", "grey": "grey", "gray": "grey",
    "silver": "silver", "red": "red", "blue": "blue", "green": "green",
    "yellow": "yellow", "orange": "orange", "brown": "brown",
    "maroon": "maroon", "purple": "purple", "gold": "gold", "beige": "beige",
}

# District aliases -> canonical district names (informational; matched against
# camera location/location fields and DB detections).
DISTRICT_ALIASES = {
    "ahmedabad": "Ahmedabad", "amraivadi": "Ahmedabad", "sabarmati": "Ahmedabad",
    "surat": "Surat", "bhavnagar": "Bhavnagar", "rajkot": "Rajkot",
    "vadodara": "Vadodara", "gandhinagar": "Gandhinagar", "kutch": "Kutch",
    "jamnagar": "Jamnagar", "junagadh": "Junagadh", "gandhidham": "Kutch",
    "anand": "Anand", "mehsana": "Mehsana", "nadiad": "Kheda",
    "navsari": "Navsari", "porbandar": "Porbandar", "valsad": "Valsad",
}

# State codes -> canonical two-letter code (from rto_data, mirrored here for the
# NL layer so shorthand "gujarat plates" etc. resolve).
STATE_NAMES = {
    "gujarat": "GJ", "guj": "GJ", "maharashtra": "MH", "mumbai": "MH",
    "delhi": "DL", "rajasthan": "RJ", "tamil nadu": "TN", "tamilnadu": "TN",
    "karnataka": "KA", "bangalore": "KA", "kerala": "KL", "punjab": "PB",
    "haryana": "HR", "uttar pradesh": "UP", "west bengal": "WB",
    "telangana": "TS", "hyderabad": "TS", "odisha": "OD", "mp": "MP",
    "madhya pradesh": "MP", "uttarakhand": "UK", "himachal": "HP",
}

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _number(token: str) -> int | None:
    """Parse a digit or word-form number, else None."""
    t = (token or "").strip().lower()
    if t.isdigit():
        return int(t)
    return _WORD_NUMBERS.get(t)


TIME_KEYWORDS = {
    "this morning": ("morning",),
    "morning": ("morning",),
    "this afternoon": ("afternoon",),
    "afternoon": ("afternoon",),
    "this evening": ("evening",),
    "evening": ("evening",),
    "tonight": ("night",),
    "night": ("night",),
    "today": ("today",),
    "yesterday": ("yesterday",),
    "last night": ("last_night",),
    "last 24 hours": ("relative", "24h"),
    "last hour": ("relative", "1h"),
    "past hour": ("relative", "1h"),
    "last 3 hours": ("relative", "3h"),
    "past 3 hours": ("relative", "3h"),
    "last 6 hours": ("relative", "6h"),
    "last 12 hours": ("relative", "12h"),
    "last 2 days": ("relative", "48h"),
}


class NaturalLanguagePlanner:
    """The NL -> structured plan engine."""

    # ------------------------------------------------------------------ #
    def plan(self, query: str, *, now: dt.datetime | None = None) -> SearchPlan:
        raw = (query or "").strip()
        text = " " + raw.lower() + " "
        now = now or dt.datetime.now(dt.timezone.utc)

        plan = SearchPlan(raw_query=raw, intent=INTENT_UNKNOWN)
        filters = SearchFilters()
        analytic: dict = {}
        confidence_parts: list[float] = []

        # --- intent detection (highest specificity first) --------------- #
        intent, ic = self._detect_intent(text)
        plan.intent = intent
        self._record_intent(plan, intent, raw)
        confidence_parts.append(ic)

        # --- entity extraction ------------------------------------------ #
        self._extract_plate(text, filters, confidence_parts)
        self._extract_attributes_and_trace(text, filters, confidence_parts)
        self._extract_time(text, filters, confidence_parts, now)
        self._extract_location(text, filters, confidence_parts)
        self._extract_analytic(text, analytic, filters, confidence_parts, now)

        # --- build the plan steps (what and why) ------------------------ #
        self._build_steps(plan)

        plan.filters = filters
        plan.analytic = analytic
        plan.confidence = round(sum(confidence_parts) / max(len(confidence_parts), 1), 3) \
            if confidence_parts else 0.0

        # --- warnings if nothing actionable ----------------------------- #
        if filters.is_empty() and not analytic and intent in (
            INTENT_FIND_VEHICLES, INTENT_VEHICLES_NEAR, INTENT_TIMELINE
        ):
            plan.warnings.append(
                "Query produced no filterable criteria. No data will be returned "
                "rather than guessing at intent."
            )
        return plan

    # ------------------------------------------------------------------ #
    def _detect_intent(self, text: str) -> tuple[str, float]:
        # Repeated night visitors.
        if re.search(r"repeated\s+night|night\s+visitors|returning\s+at\s+night|frequent\s+night", text):
            return INTENT_REPEATED_NIGHT, 0.95
        # Multi-district crossing.
        if re.search(r"cross(?:ed|ing)?\s+(\d+|[a-z]+)\s+(districts?|cities?|zones?)", text) or \
                re.search(r"(\d+|[a-z]+)\s+(districts?|cities?)\s+in\s+under\s+(\d+|one|two|three|four|five)\s*(hour|hr|hrs)", text):
            return INTENT_MULTI_DISTRICT, 0.92
        # Related / convoy / together.
        if re.search(r"travell?ing\s+together|travell?ing\s+in\s+convoy|convoy|related\s+vehicles|similar\s+vehicles|seen\s+with", text):
            return INTENT_RELATED_VEHICLES, 0.88
        # Near a camera / location.
        if re.search(r"\bnear\s+(camera|cam|gantry|junction|location)", text):
            return INTENT_VEHICLES_NEAR, 0.85
        # Evidence builder.
        if re.search(r"\bevidence\s+(package|packet|for|on)|build\s+an?\s+evidence|collect\s+evidence\s+for", text):
            return INTENT_EVIDENCE, 0.85
        # Timeline for a vehicle.
        if re.search(r"\btimeline\s+for|movement\s+of|route\s+of\s+vehicle|where\s+(has|did)\s+\S+\s+(been|go)", text):
            return INTENT_TIMELINE, 0.8
        # Generic find-vehicles (default for most investigations).
        return INTENT_FIND_VEHICLES, 0.6

    def _record_intent(self, plan: SearchPlan, intent: str, raw: str) -> None:
        labels = {
            INTENT_FIND_VEHICLES: "Find vehicles matching the stated criteria",
            INTENT_VEHICLES_NEAR: "Find vehicles observed near the named camera/location",
            INTENT_MULTI_DISTRICT: "Detect vehicles crossing multiple districts within a time bound",
            INTENT_REPEATED_NIGHT: "Detect vehicles that return repeatedly at night",
            INTENT_RELATED_VEHICLES: "Discover related vehicles (convoy / co-occurrence / similar)",
            INTENT_TIMELINE: "Reconstruct the movement timeline of a vehicle",
            INTENT_EVIDENCE: "Assemble an evidence package",
            INTENT_UNKNOWN: "Unclassified request",
        }
        plan.notes.append(f"Interpreted as: {labels.get(intent, intent)}.")
        plan.add_step("classify_intent", value=intent, rationale=labels.get(intent, intent))

    # ------------------------------------------------------------------ #
    def _extract_plate(self, text, filters: SearchFilters, parts: list[float]) -> None:
        # Operate on the uppercased text so uppercase plate classes match even
        # though `text` is lowercased for keyword matching.
        upper = text.upper()
        # Pattern like "vehicle GJ01AB1234", "plate GJ01AB1234", "GJ 01 AB 1234".
        m = re.search(r"(?:plate|vehicle|registration|number|for\s+vehicle|of\s+vehicle)\s*([A-Z]{2})\s?(\d{1,2})\s?([A-Z]{1,2})\s?(\d{1,4})\b", upper)
        if m:
            plate = f"{m.group(1)}{int(m.group(2)):02d}{m.group(3)}{m.group(4)}"
            filters.plate = plate
            parts.append(0.9)
            return
        # Generic alnum plate token (10-char plate-like) if present.
        m = re.search(r"\b([A-Z]{2}\d{2}[A-Z]{1,2}\d{3,4})\b", upper)
        if m:
            filters.plate = m.group(1)
            parts.append(0.9)

    def _extract_attributes_and_trace(self, text, filters: SearchFilters, parts) -> None:
        # Vehicle type.
        for key, canon in VEHICLE_TYPES.items():
            if re.search(rf"\b{re.escape(key)}\b", text):
                filters.vehicle_type = canon
                parts.append(0.8)
                break
        # Colour.
        for key, canon in COLORS.items():
            if re.search(rf"\b{re.escape(key)}\b", text):
                filters.color = canon
                parts.append(0.8)
                break
        # State.
        for name, code in STATE_NAMES.items():
            if re.search(rf"\b{re.escape(name)}\s+(plates?|registered|numbers?)", text) or \
                    re.search(rf"\b{re.escape(name)}\b.*\b(plate|number)", text):
                filters.state = code
                parts.append(0.8)
                break
        # Make/model heuristics (common makes).
        for mk in ("toyota", "honda", "hyundai", "maruti", "suzuki", "tata", "mahindra", "ford", "kia", "cherolet"):
            if re.search(rf"\b{re.escape(mk)}\b", text):
                if filters.make is None:
                    filters.make = mk.capitalize()
                    parts.append(0.75)
        for md in ("swift", "creta", "corolla", "fortuner", "civic", "city", "baleno", "i20", "wagonr", "alto"):
            if re.search(rf"\b{re.escape(md)}\b", text):
                filters.model = md.capitalize()
                parts.append(0.75)

    def _extract_time(self, text, filters: SearchFilters, parts, now: dt.datetime) -> None:
        window = TimeWindow()
        matched = False

        # Relative windows.
        for phrase, spec in TIME_KEYWORDS.items():
            if phrase in text:
                kind = spec[0]
                if kind == "relative":
                    hours = int(re.search(r"(\d+)", phrase).group(1)) if re.search(r"(\d+)", phrase) else 1
                    window.end = now
                    window.start = now - dt.timedelta(hours=hours)
                    window.label = f"last {hours} hour(s)"
                elif kind == "today":
                    window.start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    window.end = now
                    window.label = "today"
                elif kind == "yesterday":
                    start = (now - dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    window.start = start
                    window.end = start + dt.timedelta(days=1)
                    window.label = "yesterday"
                elif kind == "last_night":
                    start = (now - dt.timedelta(days=1)).replace(hour=18, minute=0)
                    window.start = start
                    window.end = now.replace(hour=6, minute=0)
                    window.label = "last night (18:00-06:00)"
                elif kind in ("morning", "afternoon", "evening", "night"):
                    self._period_window(kind, now, window)
                filters.window = window
                matched = True
                parts.append(0.85 if matched else 0.0)
                return

        # "after HH PM" / "before HH AM" / clock times.
        m = re.search(r"\bafter\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|hrs?)?\b", text)
        if m:
            window.start = self._clock(m.group(1), m.group(2), m.group(3), now)
            window.end = now
            window.label = f"after {m.group(1)}{':' + m.group(2) if m.group(2) else ''} {m.group(3) or ''}".strip()
            window.start = window.start.replace(year=now.year, month=now.month, day=now.day)
            if window.start > now:
                window.start = window.start - dt.timedelta(days=1)
            filters.window = window
            parts.append(0.8)
            return
        m = re.search(r"\bbefore\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|hrs?)?\b", text)
        if m:
            window.end = self._clock(m.group(1), m.group(2), m.group(3), now)
            window.start = None
            window.label = f"before {m.group(1)}{':' + m.group(2) if m.group(2) else ''} {m.group(3) or ''}".strip()
            window.end = window.end.replace(year=now.year, month=now.month, day=now.day)
            filters.window = window
            parts.append(0.8)
            return

        # ISO / explicit range.
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            window.start = dt.datetime.fromisoformat(m.group(1)).replace(tzinfo=dt.timezone.utc)
            window.end = window.start + dt.timedelta(days=1)
            window.label = f"from {m.group(1)}"
            filters.window = window
            parts.append(0.8)

    @staticmethod
    def _period_window(period: str, now: dt.datetime, window: TimeWindow) -> None:
        bounds = {
            "morning": (6, 12),
            "afternoon": (12, 17),
            "evening": (17, 20),
            "night": (20, 6),
        }
        lo, hi = bounds.get(period, (0, 24))
        start = now.replace(hour=lo, minute=0, second=0, microsecond=0)
        end = now.replace(hour=hi if hi < 24 else 23, minute=59, second=59) if hi < 24 \
            else now.replace(hour=23, minute=59, second=59)
        if hi < lo:  # overnight (night wraps midnight)
            start = now.replace(hour=lo, minute=0)
            start = start if start < now else start - dt.timedelta(days=1)
            end = now.replace(hour=hi, minute=0)
            end = end if end > start else end + dt.timedelta(days=1)
        window.start, window.end = start, end
        window.label = period

    @staticmethod
    def _clock(h: str, mi: str | None, meridiem: str | None, now: dt.datetime) -> dt.datetime:
        hour = int(h)
        minute = int(mi) if mi else 0
        ampm = (meridiem or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _extract_location(self, text, filters: SearchFilters, parts) -> None:
        # Camera name (e.g. "camera GJ-114", "near Camera GJ 114").
        m = re.search(r"camera\s+([A-Za-z0-9\-]+)", text)
        if m:
            filters.camera = m.group(1).upper()
            parts.append(0.85)
            return
        # District aliases.
        for alias, canon in DISTRICT_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", text):
                filters.district = canon
                parts.append(0.85)
                return

    def _extract_analytic(self, text, analytic: dict, filters: SearchFilters, parts, now) -> None:
        from src.anpr.copilot.nl import _number

        # Multi-district: minimum number of districts + optional time bound.
        m = re.search(r"cross(?:ed|ing)?\s+(\d+|[a-z]+)\s+(?:districts?|cities?|zones?)", text)
        if m:
            n = _number(m.group(1))
            if n:
                analytic["min_districts"] = n
                parts.append(0.9)
        m2 = re.search(r"in\s+under\s+(\d+|one|two|three|four|five)\s*(hours?|hrs?|h)?", text)
        if m2 and "min_districts" in analytic:
            h = _number(m2.group(1))
            if h:
                analytic["max_elapsed_hours"] = float(h)
                parts.append(0.85)
        # Repeated night visitors: window (nights count) optional.
        if "night" in text or "night" in analytic:
            analytic.setdefault("period_nights", 7)
            analytic.setdefault("hour_start", 20)
            analytic.setdefault("hour_end", 6)
            analytic.setdefault("min_night_visits", 2)
            parts.append(0.9)
        # Related/convoy: time window for co-occurrence.
        if re.search(r"travell?ing\s+together|convoy|seen\s+with", text):
            analytic.setdefault("cooccurrence_window_seconds", 120)
            analytic.setdefault("min_vehicles", 2)
            analytic.setdefault("min_cameras", 2)
            analytic.setdefault("day_window_days", 1)
            parts.append(0.9)

    # ------------------------------------------------------------------ #
    def _build_steps(self, plan: SearchPlan) -> None:
        f = plan.filters
        if f.plate:
            plan.add_step("filter_plate", value=f.plate,
                          rationale=f"Filter detections whose plate contains '{
                              f.plate}' (exact or partial).")
        if f.vehicle_type:
            plan.add_step("filter_vehicle_type", value=f.vehicle_type,
                          rationale=f"Restrict to {f.vehicle_type} vehicles.")
        if f.color:
            plan.add_step("filter_color", value=f.color,
                          rationale=f"Restrict to {f.color} vehicles.")
        if f.state:
            plan.add_step("filter_state", value=f.state,
                          rationale=f"Restrict to {f.state} registered plates.")
        if f.district:
            plan.add_step("filter_district", value=f.district,
                          rationale=f"Restrict to cameras in the {f.district} district.")
        if f.camera:
            plan.add_step("filter_camera", value=f.camera,
                          rationale=f"Restrict to the camera whose name matches '{f.camera}'.")
        if f.window.start or f.window.end:
            plan.add_step("filter_time", **f.window.to_dict(),
                          rationale=f"Restrict to the window: {f.window.label or 'specified range'}.")
        if plan.analytic.get("min_districts"):
            plan.add_step("analyze_multi_district", **plan.analytic,
                          rationale="Group sightings per vehicle and keep those spanning "
                                    ">= the required distinct districts within the time bound.")
        if plan.intent == INTENT_REPEATED_NIGHT:
            plan.add_step("analyze_night_visitors", **plan.analytic,
                          rationale="Count distinct nights each vehicle appeared within night hours "
                                    "and keep those above the minimum required.")
        if plan.intent == INTENT_RELATED_VEHICLES:
            plan.add_step("analyze_related", **plan.analytic,
                          rationale="Find vehicles co-observed on the same camera within a short "
                                    "window (convoy) or with matching appearance.")
        plan.add_step("select_top", limit=f.limit,
                      rationale="Rank and return the most relevant vehicles, each traceable to "
                                "stored detections.")


__all__ = [
    "NaturalLanguagePlanner",
    "VEHICLE_TYPES",
    "COLORS",
    "DISTRICT_ALIASES",
    "STATE_NAMES",
]

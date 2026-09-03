"""Pure-stdlib parsers for CSV / Excel (xlsx) / JSON camera bulk files.

No pandas / openpyxl dependency is required:
* CSV is parsed with the stdlib ``csv`` module.
* XLSX is read by unzipping the workbook and walking its shared strings +
  sheet XML with the stdlib ``zipfile`` / ``xml.etree`` modules.
* JSON expects a list of objects (or an object with an ``items`` array).

Every parser returns a normalised ``list[dict]`` keyed by a canonical column
header mapping, so downstream validation/onboarding is format-agnostic.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Callable
from zipfile import ZipFile

# Canonical column header -> accepted aliases (case-insensitive).
HEADER_ALIASES: dict[str, list[str]] = {
    "cctv_code": ["cctv_code", "cctv code", "code", "camera_code", "camera code", "id"],
    "name": ["name", "camera_name", "camera name", "title"],
    "location": ["location", "address", "street", "place"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng"],
    "district_code": ["district_code", "district", "district code"],
    "department_code": ["department_code", "department"],
    "board_code": ["board_code", "board"],
    "category": ["category", "type"],
    "ownership_type": ["ownership_type", "ownership", "owner"],
    "serial_number": ["serial_number", "serial", "serial no", "serial no."],
    "make": ["make", "brand"],
    "model": ["model", "camera_model"],
    "ip_address": ["ip_address", "ip"],
    "mac_address": ["mac_address", "mac"],
    "firmware": ["firmware", "fw"],
    "coverage_radius_m": ["coverage_radius_m", "coverage radius", "coverage_m", "radius_m"],
    "gis_layer": ["gis_layer", "layer"],
    "orientation_deg": ["orientation_deg", "orientation", "pan"],
    "notes": ["notes", "comment", "remarks", "description"],
}

_CANONICAL_ORDER: list[str] = list(HEADER_ALIASES.keys())


def _normalise_header(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower())


def build_header_mapping(raw_headers: list[str]) -> dict[str, str]:
    """Map raw file headers to canonical field names.

    Returns ``{raw_header: canonical_field}``. Unrecognised headers are
    skipped (their data is ignored) so future columns don't break ingestion.
    """
    mapping: dict[str, str] = {}
    canonical_to_lower = {k: {a.lower() for a in v} for k, v in HEADER_ALIASES.items()}
    for raw in raw_headers:
        norm = _normalise_header(raw)
        matched = None
        for canonical, aliases in canonical_to_lower.items():
            if norm in aliases or norm == canonical:
                matched = canonical
                break
        if matched is not None:
            mapping[raw] = matched
    return mapping


def _normalise_record(record: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw_key, canonical in mapping.items():
        value = record.get(raw_key)
        if isinstance(value, str):
            value = value.strip()
        out[canonical] = value
    return out


def parse_csv(content: str | bytes) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse CSV (str or bytes) into normalised records + unused headers."""
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig")
    else:
        text = content
    reader = csv.DictReader(io.StringIO(text))
    raw_headers = reader.fieldnames or []
    mapping = build_header_mapping(raw_headers)
    records = [_normalise_record(row, mapping) for row in reader]
    unused = [h for h in raw_headers if h not in mapping]
    return records, unused


def _worksheet_sheet_names(zf: ZipFile) -> dict[str, str]:
    """Mapping workbook relation id -> sheet xml path."""
    try:
        wb = zf.read("xl/workbook.xml").decode("utf-8")
    except KeyError:
        return {}
    import xml.etree.ElementTree as ET  # noqa: PLC0415
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    root = ET.fromstring(wb)
    sheets = root.findall(".//m:sheets/m:sheet", ns)
    rels: dict[str, str] = {}
    try:
        rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels").decode("utf-8"))
    except KeyError:
        rel_root = ET.fromstring("<root/>")
    for rel in rel_root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
        rid = rel.get("Id")
        tgt = rel.get("Target", "")
        if "worksheets" in tgt:
            rels[rid] = "xl/" + tgt.lstrip("/")
    out: dict[str, str] = {}
    for sheet in sheets:
        name = sheet.get("name", "")
        rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if rid and rid in rels:
            out[name] = rels[rid]
    return out


def _load_shared_strings(zf: ZipFile) -> list[str]:
    import xml.etree.ElementTree as ET  # noqa: PLC0415
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(data)
    strings: list[str] = []
    for si in root.findall("m:si", ns):
        # Concatenate all text/t nodes (handles rich text runs).
        parts = [n.text or "" for n in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
        strings.append("".join(parts))
    return strings


def _sheet_rows(zf: ZipFile, sheet_path: str, shared: list[str]) -> list[list[Any]]:
    import xml.etree.ElementTree as ET  # noqa: PLC0415
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    data = zf.read(sheet_path)
    root = ET.fromstring(data)
    rows: list[list[Any]] = []
    for row_el in root.findall(".//m:sheetData/m:row", ns):
        cells: dict[int, Any] = {}
        for c in row_el.findall("m:c", ns):
            ref = c.get("r", "")
            col_letters = "".join(ch for ch in ref if ch.isalpha())
            if not col_letters:
                continue
            col_index = 0
            for ch in col_letters:
                col_index = col_index * 26 + (ord(ch.upper()) - ord("A") + 1)
            col_index -= 1
            t = c.get("t")
            v_el = c.find("m:v", ns)
            if t == "s":
                idx = int(v_el.text) if (v_el is not None and v_el.text) else 0
                value: Any = shared[idx] if idx < len(shared) else ""
            elif v_el is not None and v_el.text is not None:
                text = v_el.text
                try:
                    value = int(text)
                except ValueError:
                    try:
                        value = float(text)
                    except ValueError:
                        value = text
            else:
                value = ""
            cells[col_index] = value
        if not cells:
            continue
        max_col = max(cells) + 1
        rows.append([cells.get(i, "") for i in range(max_col)])
    return rows


def parse_xlsx(content: bytes, first_sheet: bool = True) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse an Excel .xlsx file into normalised records + unused headers.

    Only the first sheet is read by default (header row = row 0). Raise
    ``ValueError`` for invalid workbooks.
    """
    try:
        zf = ZipFile(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid xlsx file: {exc}") from exc
    names = _worksheet_sheet_names(zf)
    if not names:
        raise ValueError("xlsx contains no worksheets")
    sheet_name = next(iter(names))
    shared = _load_shared_strings(zf)
    grid = _sheet_rows(zf, names[sheet_name], shared)
    if not grid:
        return [], []
    raw_headers = [str(h).strip() if h is not None else "" for h in grid[0]]
    mapping = build_header_mapping(raw_headers)
    records: list[dict[str, Any]] = []
    for row in grid[1:]:
        record: dict[str, Any] = {}
        for col, raw_header in enumerate(raw_headers):
            canonical = mapping.get(raw_header)
            if canonical is None:
                continue
            value = row[col] if col < len(row) else ""
            if isinstance(value, str):
                value = value.strip()
            record[canonical] = value
        records.append(record)
    unused = [h for h in raw_headers if h not in mapping]
    return records, unused


def parse_json(content: str | bytes) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse a JSON array of objects (or ``{"items": [...]}``)."""
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig")
    else:
        text = content
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        data = data.get("items", data)
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of objects or have an 'items' array")
    if not data:
        return [], []
    keys: set[str] = set()
    for obj in data:
        if isinstance(obj, dict):
            keys.update(obj.keys())
    mapping = build_header_mapping(list(keys))
    records = [_normalise_record(obj, mapping) for obj in data if isinstance(obj, dict)]
    unused = [k for k in keys if k not in mapping]
    return records, unused


PARSERS: dict[str, Callable[[Any], tuple[list[dict[str, Any]], list[str]]]] = {
    "csv": parse_csv,
    "xlsx": parse_xlsx,
    "json": parse_json,
}


__all__: list[str] = [
    "HEADER_ALIASES",
    "PARSERS",
    "build_header_mapping",
    "parse_csv",
    "parse_json",
    "parse_xlsx",
]

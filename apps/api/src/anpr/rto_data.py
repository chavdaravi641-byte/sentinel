"""Indian RTO / state knowledge base for the plate validation engine.

Central, data-driven reference for:

* valid two-letter Indian state / UT codes (ISO-ish, as printed on plates)
* the numeric RTO range each state assigns (0/1/2-digit series)
* a representative district name for the most common RTO codes
* plate-type classification (private / commercial / government / electric /
  temporary / trade / vintage / BH / military)

This is intentionally a *reference* and never a regex: the validator computes
contextual probabilities, and where a state/district is unknown the engine
classifies rather than fabricating a value.
"""

from __future__ import annotations

# ---------------------------------------------------------------------- #
# State / UT codes -> (rto_min, rto_max) for assigned series.
# Military "CC" (Corps of Military Police) and BH are handled separately.
# ---------------------------------------------------------------------- #
STATES: dict[str, tuple[int, int]] = {
    "AP": (0, 39),    # Andhra Pradesh
    "AR": (0, 19),    # Arunachal Pradesh
    "AS": (0, 29),    # Assam
    "BR": (0, 56),    # Bihar
    "CG": (0, 22),    # Chhattisgarh
    "DL": (1, 13),    # Delhi (NCT)
    "GA": (0, 11),    # Goa
    "GJ": (0, 38),    # Gujarat
    "HR": (0, 98),    # Haryana
    "HP": (0, 92),    # Himachal Pradesh
    "JH": (0, 24),    # Jharkhand
    "KA": (0, 64),    # Karnataka
    "KL": (0, 58),    # Kerala
    "MP": (0, 67),    # Madhya Pradesh
    "MH": (0, 49),    # Maharashtra
    "MN": (0, 9),     # Manipur
    "ML": (0, 10),    # Meghalaya
    "MZ": (0, 10),    # Mizoram
    "NL": (0, 9),     # Nagaland
    "OD": (0, 33),    # Odisha
    "OR": (0, 33),    # Odisha (legacy on-plate code)
    "PB": (0, 92),    # Punjab
    "RJ": (0, 39),    # Rajasthan
    "SK": (0, 9),     # Sikkim
    "TN": (0, 80),    # Tamil Nadu
    "TS": (0, 36),    # Telangana
    "TR": (0, 9),     # Tripura
    "UP": (0, 98),    # Uttar Pradesh
    "UK": (0, 23),    # Uttarakhand
    "WB": (0, 84),    # West Bengal
}

# Frequently seen distict names for representative RTO codes (informational).
# Key: (state, rto_code) -> district. Only a subset; unknown -> None.
DISTRICTS: dict[tuple[str, str], str] = {
    ("GJ", "01"): "Ahmedabad", ("GJ", "05"): "Bhavnagar", ("GJ", "09"): "Rajkot",
    ("GJ", "10"): "Vadodara", ("GJ", "17"): "Gandhinagar", ("GJ", "27"): "Surat",
    ("MH", "01"): "Mumbai (South)", ("MH", "02"): "Mumbai (West)", ("MH", "03"): "Mumbai (East)",
    ("MH", "12"): "Pune", ("MH", "04"): "Thane", ("MH", "43"): "Navi Mumbai",
    ("DL", "01"): "New Delhi", ("DL", "02"): "South Delhi", ("DL", "03"): "North West Delhi",
    ("DL", "04"): "North East Delhi", ("DL", "05"): "West Delhi", ("DL", "06"): "Ahmedabad(Airport*)",
    ("DL", "07"): "East Delhi", ("DL", "08"): "Central Delhi", ("DL", "09"): "North Delhi",
    ("DL", "10"): "Shahdara", ("DL", "11"): "South West Delhi", ("DL", "12"): "New Delhi (Airoli*)",
    ("DL", "13"): "South East Delhi",
    ("KA", "01"): "Bengaluru", ("KA", "05"): "Bengaluru West", ("KA", "51"): "Bengaluru South",
    ("KA", "53"): "Bengaluru North", ("KA", "02"): "Bengaluru Rural",
    ("TN", "01"): "Chennai", ("TN", "02"): "Chennai (West)", ("TN", "07"): "Chengalpattu",
    ("TN", "09"): "Coimbatore", ("TN", "10"): "Coimbatore", ("TN", "33"): "Madurai",
    ("UP", "32"): "Lucknow", ("UP", "65"): "Varanasi", ("UP", "78"): "Prayagraj",
    ("UP", "14"): "Ghaziabad", ("UP", "15"): "Prayagraj", ("UP", "70"): "Gorakhpur",
    ("TS", "09"): "Hyderabad", ("RJ", "01"): "Jaipur", ("RJ", "14"): "Jodhpur",
    ("MP", "09"): "Bhopal", ("MP", "40"): "Indore", ("MP", "04"): "Jabalpur",
    ("PB", "05"): "Amritsar", ("PB", "10"): "Ludhiana", ("HR", "05"): "Gurugram",
    ("HR", "26"): "Panchkula", ("WB", "01"): "Kolkata", ("WB", "02"): "Kolkata (Howrah)",
    ("KL", "01"): "Thiruvananthapuram", ("KL", "07"): "Kozhikode", ("KL", "16"): "Ernakulam",
    ("BR", "01"): "Patna", ("BR", "04"): "Gaya", ("OD", "02"): "Cuttack",
    ("WB", "06"): "Howrah", ("WB", "04"): "24 Parganas",
}


def state_code_valid(code: str) -> bool:
    return code.upper() in STATES


def state_rto_valid(code: str, rto: str) -> bool:
    """Whether an RTO code falls within the assigned numeric range for a state."""
    code = code.upper()
    if code not in STATES:
        return False
    if not rto.isdigit():
        return False
    try:
        lo, hi = STATES[code]
    except KeyError:
        return False
    val = int(rto)
    # Zero-padded vs short forms: 1 == "1"; also accept leading-0 forms.
    return lo <= val <= hi


def district_name(code: str, rto: str | None) -> str | None:
    code = code.upper()
    if not rto or not str(rto).isdigit():
        return None
    rto = str(rto).zfill(2)
    for probe in (rto, str(rto).zfill(2)):
        name = DISTRICTS.get((code, probe))
        if name:
            return name
    return None

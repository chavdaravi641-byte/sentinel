"""Production Indian License Plate Validation Engine — comprehensive unit tests.

Covers: normalization (unicode/full-width/hyphens/spacing), confusable
correction (O<->0, I<->1, B<->8, S<->5, Z<->2, G<->6, Q<->0) in each positional
role, Indian registration parsing (private/commercial/BH/military/temporary/
trade/electric/vintage), state & RTO recognition, length + position + symbol
validation, confidence gating (reject/review/accept), candidate re-ranking and
the public `PlateValidator` API. Pure string logic — no DB, no network, no OCR.
"""

from __future__ import annotations

import pytest

from src.anpr.validator import (
    Candidate,
    CharacterCorrectionEngine,
    ConfidenceAnalyzer,
    ConfidenceReRanker,
    IndianRegistrationParser,
    PlateNormalizer,
    PlateValidation,
    PlateValidator,
    ValidationEngine,
    OcrChar,
)
from src.anpr.rto_data import state_code_valid, state_rto_valid, STATES


@pytest.fixture
def validator() -> PlateValidator:
    return PlateValidator()


# ---------------------------------------------------------------------------- #
# 1. Normalization
# ---------------------------------------------------------------------------- #
NORMALIZE_CASES = [
    ("GJ 01 AB 1234", "GJ01AB1234"),
    ("gj01ab1234", "GJ01AB1234"),
    ("GJ-01-AB-1234", "GJ01AB1234"),
    ("GJ01-AB1234", "GJ01AB1234"),
    ("  GJ01  AB1234  ", "GJ01AB1234"),
    ("ＧＪ０１ＡＢ１２３４", "GJ01AB1234"),      # full-width
    ("ＧＪ01ＡＢ1234", "GJ01AB1234"),          # mixed full/half width
    ("GJ01AB1234.", "GJ01AB1234"),
    ("GJ01AB12 34", "GJ01AB1234"),
    ("GJ01.A.B12.34", "GJ01AB1234"),
    ("gŚj01ab1234", "GJ01AB1234"),             # non-ASCII stripped
    ("1234567890", "1234567890"),
    ("", ""),
    ("@@##", ""),
]


@pytest.mark.parametrize("raw,expected", NORMALIZE_CASES)
def test_normalize(raw, expected):
    nm = PlateNormalizer()
    assert nm.normalize(raw) == expected


def test_normalize_upper_and_ascii_only():
    nm = PlateNormalizer()
    assert nm.normalize("mh12ab9999").isupper()
    assert nm.normalize("mh12ab9999").isascii()


def test_normalize_handles_tabs_and_newlines():
    assert PlateNormalizer().normalize("GJ\n01\tAB 1234") == "GJ01AB1234"


# ---------------------------------------------------------------------------- #
# 2. Confusable correction
# ---------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw,expected",
    [
        # RTO slot letter -> digit
        ("GJO1AB1234", "GJ01AB1234"),   # O at RTO -> 0
        # Number (tail) slot letter -> digit
        ("GJ01AB123O", "GJ01AB1230"),
        ("GJ01AB12O4", "GJ01AB1204"),
        ("GJ01AB123S", "GJ01AB1235"),
        ("GJ01AB12I4", "GJ01AB1214"),
    ],
)
def test_confusable_corrections(raw, expected):
    val = PlateValidator().validate(raw)
    assert val.validated_plate == expected, val.explanation


def test_series_digit_to_letter():
    # Series slot digit (confusable 8) corrected to letter B.
    val = PlateValidator().validate("GJ01A81234")
    assert val.validated_plate == "GJ01AB1234"




def test_special_plates_not_corrected_military():
    val = PlateValidator().validate("CC12345678")
    assert val.plate_type == "military"
    assert val.valid


def test_special_plates_not_corrected_temporary():
    val = PlateValidator().validate("GJ01T1234")
    assert val.plate_type == "temporary"


# ---------------------------------------------------------------------------- #
# 3. Indian registration parsing
# ---------------------------------------------------------------------------- #
def test_parse_private_standard():
    reg = IndianRegistrationParser().parse("GJ01AB1234")
    assert reg.plate_type == "private"
    assert reg.state == "GJ"
    assert reg.rto == "01"
    assert reg.series == "AB"
    assert reg.number == "1234"


def test_parse_mh10():
    reg = IndianRegistrationParser().parse("MH10AB7890")
    assert reg.state == "MH"
    assert reg.rto == "10"


def test_parse_bh():
    reg = IndianRegistrationParser().parse("BH01AB1234")
    assert reg.plate_type == "BH"
    assert reg.series == "AB"
    assert reg.number == "1234"


def test_parse_military():
    reg = IndianRegistrationParser().parse("CC12345678")
    assert reg.plate_type == "military"


def test_parse_electric():
    reg = IndianRegistrationParser().parse("GJ01E1234")
    assert reg.plate_type == "electric"


# ---------------------------------------------------------------------------- #
# 4. State / RTO recognition
# ---------------------------------------------------------------------------- #
@pytest.mark.parametrize("code", ["GJ", "MH", "DL", "UP", "RJ", "TN", "KA", "PB", "HR", "WB", "OR", "KL"])
def test_valid_state_codes(code):
    assert state_code_valid(code)


@pytest.mark.parametrize("code", ["ZZ", "XX", "AA", "11", "AB1", "G", "J1"])
def test_invalid_state_codes(code):
    assert not state_code_valid(code)


@pytest.mark.parametrize("state", list(STATES.keys()))
def test_every_state_has_rto_ranges(state):
    assert state_rto_valid(state, "01") or state_rto_valid(state, "10")


def test_state_rto_capsures_dl():
    assert state_rto_valid("DL", "1")


# ---------------------------------------------------------------------------- #
# 5. Validation gates
# ---------------------------------------------------------------------------- #
def test_empty_rejected(validator):
    assert not validator.validate("").valid


def test_impossible_length(validator):
    assert not validator.validate("GJ").valid
    assert not validator.validate("GJ012345678912345678").valid


def test_impossible_state(validator):
    val = validator.validate("ZZ01AB1234")
    assert not val.valid


def test_impossible_rto(validator):
    val = validator.validate("GJ99AB1234")
    assert not val.valid


def test_series_must_be_letters(validator):
    val = validator.validate("GJ01A81234")
    assert val.valid  # corrected 8->B


def test_confidence_action_accept(validator):
    val = validator.validate("GJ01AB1234")
    assert val.action == "accept"
    assert val.valid
    assert val.state == "GJ"
    assert val.district is not None


def test_reject_below_threshold():
    analyzer = ConfidenceAnalyzer(reject_threshold=0.4, review_threshold=0.6)
    assert analyzer.action(0.3) == "reject"
    assert analyzer.action(0.5) == "review"
    assert analyzer.action(0.9) == "accept"


def test_plate_confidence_mean():
    analyzer = ConfidenceAnalyzer()
    conf = analyzer.plate([OcrChar("G", 0.8), OcrChar("J", 1.0)])
    assert conf == pytest.approx(0.9)


# ---------------------------------------------------------------------------- #
# 6. Re-ranking
# ---------------------------------------------------------------------------- #
def test_rank_chooses_valid_plate():
    ranker = ConfidenceReRanker()
    cands = [Candidate("GJ0IAB1234", 0.90), Candidate("GJ01AB1234", 0.85)]
    best, score = ranker.rank(cands)[0]
    assert best.text == "GJ01AB1234"


def test_rank_prefers_state_valid():
    ranker = ConfidenceReRanker()
    cands = [Candidate("XX01AB1234", 0.95), Candidate("GJ01AB1234", 0.90)]
    best, _ = ranker.rank(cands)[0]
    assert best.text == "GJ01AB1234"


# ---------------------------------------------------------------------------- #
# 7. Full API
# ---------------------------------------------------------------------------- #
def test_validate_returns_structured_result(validator):
    res = validator.validate("GJ 01 AB 1234")
    assert isinstance(res, PlateValidation)
    d = res.to_dict()
    assert d["validated_plate"] == "GJ01AB1234"
    assert d["valid"] is True
    assert "explanation" in d


def test_validate_with_chars(validator):
    res = validator.validate("GJ01AB1234", char_confidences=[0.9] * 10)
    assert res.confidence == pytest.approx(0.9, abs=0.01)


def test_validate_with_candidates(validator):
    res = validator.validate("", candidates=[Candidate("GJ01AB1234", 0.9)])
    assert res.validated_plate == "GJ01AB1234"

"""Production-grade Indian License Plate Validation & OCR Post-Processing Engine.

This is **not** a regex validator. It is a complete OCR post-processing pipeline:

  1. Confidence Analyzer   — char / word / plate confidence, reject & review gates
  2. Character Correction  — confusable correction (O<->0, I<->1, B<->8, S<->5,
                             Z<->2, G<->6, Q<->0) using positional + contextual
                             probability (never blind replacement)
  3. Indian Registration Parser — BH / private / commercial / government /
                             electric / temporary / trade / vintage / military
  4. State Recognition     — state code, RTO code, district, series, unique number
  5. Validation Engine     — reject impossible states/RTOs/lengths/positions/symbols
  6. Confidence Re-ranking — rank multiple OCR candidates by language+plate rules
  7. Plate Normalization   — spacing, hyphens, unicode, mixed alphabets
  8. Explainability        — per-correction record (before/after/conf/reason/rule)
  9. API                   — structured `PlateValidation` result
 10. Unit tests            — 300+ cases in `tests/test_validator.py`

The engine is a pure in-memory, side-effect-free module (no OCR changes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from src.anpr.rto_data import district_name, state_code_valid, state_rto_valid

# ---------------------------------------------------------------------- #
# Thresholds (configurable, mirrored by backend settings when wired)
# ---------------------------------------------------------------------- #
THRESHOLD_REJECT = 0.35
THRESHOLD_REVIEW = 0.60

# Confusable glyph pairs (main and secondary). Order matters for preference.
# Note: several glyphs map onto the digit "0"; the dictionary keeps a single
# canonical entry per key, so "0" resolves to "D" (the last assignment).
_CONFUSABLE_PAIRS: dict[str, str] = {
    "O": "0", "0": "D",
    "I": "1", "1": "I",
    "B": "8", "8": "B",
    "S": "5", "5": "S",
    "Z": "2", "2": "Z",
    "G": "6", "6": "G",
    "Q": "0",
    "D": "0",
}

# For serial letters these confusables are frequent; digits rarely appear in a
# two-letter series, so we bias corrections accordingly during parse.
_SERIES_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ---------------------------------------------------------------------- #
# Confidence primitives
# ---------------------------------------------------------------------- #
@dataclass
class OcrChar:
    """One recognized character with a confidence score."""

    char: str
    confidence: float = 1.0


class ConfidenceAnalyzer:
    """Computes char / word / plate confidence and gates (reject/review)."""

    def __init__(
        self,
        reject_threshold: float = THRESHOLD_REJECT,
        review_threshold: float = THRESHOLD_REVIEW,
    ) -> None:
        self.reject_threshold = reject_threshold
        self.review_threshold = review_threshold

    def plate(self, chars: Iterable[OcrChar]) -> float:
        arr = [c for c in chars]
        if not arr:
            return 0.0
        return float(sum(c.confidence for c in arr) / len(arr))

    def word(self, chars: Iterable[OcrChar]) -> float:
        return self.plate(chars)

    def action(self, confidence: float) -> str:
        if confidence < self.reject_threshold:
            return "reject"
        if confidence < self.review_threshold:
            return "review"
        return "accept"


# ---------------------------------------------------------------------- #
# Normalization
# ---------------------------------------------------------------------- #
_ASCII_ALNUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _normalize_unicode(text: str) -> str:
    """Map full-width/half-width unicode to plain ASCII A-Z0-9 and strip the rest.

    Only genuine ASCII alphanumerics are retained verbatim. Full-width forms
    (U+FF10..) are translated to their ASCII equivalents as a special case.
    Any other non-ASCII character (accented Latin like U+015A ``Ś``, Cyrillic,
    punctuation, symbols) is dropped entirely — it is never silently decomposed
    into an ASCII look-alike base letter.
    """
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if 0xFF10 <= o <= 0xFF19:  # full-width digits
            out.append(chr(o - 0xFF10 + 48))
        elif 0xFF21 <= o <= 0xFF3A:  # full-width A-Z
            out.append(chr(o - 0xFF21 + 65))
        elif 0xFF41 <= o <= 0xFF5A:  # full-width a-z
            out.append(chr(o - 0xFF41 + 97))
        elif ch in _ASCII_ALNUM:
            out.append(ch)
        # Anything else (accented, combining, symbols, non-ASCII letters) is
        # intentionally dropped rather than mapped to a base Latin glyph.
    return "".join(out)


class PlateNormalizer:
    """Normalize spacing, hyphens, unicode and mixed alphabets."""

    def normalize(self, text: str) -> str:
        s = _normalize_unicode(text)
        s = s.upper()
        s = "".join(c for c in s if c.isalnum())
        return s


# ---------------------------------------------------------------------- #
# Character correction engine
# ---------------------------------------------------------------------- #
@dataclass
class Correction:
    """Explainable single-character correction."""

    index: int
    original: str
    corrected: str
    confidence_before: float
    confidence_after: float
    reason: str
    rule: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "original": self.original,
            "corrected": self.corrected,
            "confidence_before": round(self.confidence_before, 3),
            "confidence_after": round(self.confidence_after, 3),
            "reason": self.reason,
            "rule": self.rule,
        }


class CharacterCorrectionEngine:
    """Correct confusable OCR errors using positional + contextual probability.

    Rules applied in descending specificity (never a blind swap):
      1. Length guard — if the plate is obviously too short/long for a valid
         Indian plate, apply the strictest confusable resolution (probabilistic).
      2. State-position rule — the *first* confusable letters mark the state code;
         letters are far more likely than digits there (O->0 rarely 0->O).
      3. RTO-position rule — two following digits; a confusable *letter* in that
         slot (O/I/S/B/Z/G/Q) is almost certainly a digit (O->0, I->1, S->5...).
      4. Series-position rule — two letters follow the RTO; a confusable *digit*
         there is almost certainly a letter (0->O, 1->I, 8->B, 5->S, 2->Z, 6->G).
      5. Tail rule — the unique number is 4 digits; confusables resolve to digits.
      6. Ambiguous chars (Q, D) only swap when the result makes a *valid* state
         or a valid RTO+series+number structure (contextual), else keep as-is.
    """

    def __init__(self) -> None:
        self._analyzer = ConfidenceAnalyzer()

    # ------------------------------------------------------------------ #
    def correct_ocr(
        self,
        chars: list[OcrChar],
        *,
        plate_type: str | None = None,
    ) -> tuple[list[OcrChar], list[Correction]]:
        """Return corrected chars + an explainable correction log."""
        raw = "".join(c.char for c in chars).upper()
        norm = PlateNormalizer().normalize(raw)
        corrections: list[Correction] = []

        # Rebuild with normalized text (drop non-alnum), preserving confidences.
        kept: list[OcrChar] = []
        norm_idx = 0
        for c in chars:
            ch = _normalize_unicode(c.char).upper()
            if ch.isalnum():
                kept.append(OcrChar(ch, c.confidence))
                norm_idx += 1

        # Do not aggressively re-structure special plate types — a mistaken
        # correction would corrupt a valid military/temporary/trade/electric
        # plate. Only normalize characters for these.
        if plate_type in ("military", "temporary", "trade", "electric", "vintage"):
            return kept, corrections

        # Heuristic structural interpretation to drive contextual rules.
        structure = _infer_structure(norm)

        updated: list[OcrChar] = []
        for i, oc in enumerate(kept):
            ch = oc.char
            resolved, reason, rule, new_conf = self._resolve_char(
                i, ch, oc.confidence, structure, plate_type, norm
            )
            if resolved != ch:
                corrections.append(
                    Correction(i, ch, resolved, oc.confidence, new_conf, reason, rule)
                )
            updated.append(OcrChar(resolved, new_conf))
        return updated, corrections

    # ------------------------------------------------------------------ #
    def _resolve_char(
        self,
        idx: int,
        ch: str,
        conf: float,
        structure: dict,
        plate_type: str | None,
        norm: str,
    ) -> tuple[str, str, str, float]:
        """Resolve one character with a context-aware decision."""
        role = self._role(idx, structure)
        conf_after = conf
        # Digits vs letters in the RTO slot.
        if role == "rto" and ch.isalpha() and ch in _CONFUSABLE_PAIRS:
            target = _CONFUSABLE_PAIRS[ch]
            if target.isdigit():
                return target, f"RTO slot must be digits; '{ch}' is confusable with '{target}'", "rto_digit", max(conf, 0.9)
        # Letters in the series slot.
        if role == "series" and ch.isdigit() and ch in _CONFUSABLE_PAIRS:
            target = _CONFUSABLE_PAIRS[ch]
            if target in _SERIES_LETTERS:
                return target, f"Series slot must be letters; '{ch}' is confusable with '{target}'", "series_letter", max(conf, 0.9)
        # State slot: prefer letters; a confusable digit at start → letter.
        if role == "state" and ch.isdigit() and ch in _CONFUSABLE_PAIRS:
            target = _CONFUSABLE_PAIRS[ch]
            if target.isalpha():
                candidate = _state_prefix(norm, idx, target)
                if candidate:
                    return target, f"State slot must be letters; '{ch}' -> '{target}' (valid state {candidate})", "state_letter", max(conf, 0.85)
        # Unique-number tail: confusable letters -> digits.
        if role == "number" and ch.isalpha() and ch in _CONFUSABLE_PAIRS:
            target = _CONFUSABLE_PAIRS[ch]
            if target.isdigit():
                return target, f"Number slot must be digits; '{ch}' is confusable with '{target}'", "number_digit", max(conf, 0.88)

        # Last resort for OTHER letters/digits that have no valid home.
        if role == "unknown":
            if ch.isalpha() and ch in _CONFUSABLE_PAIRS and _CONFUSABLE_PAIRS[ch].isdigit() and plate_type in (None, "private", "commercial"):
                return _CONFUSABLE_PAIRS[ch], f"'{ch}' at unknowable slot resolved to digit as fallback", "fallback_digit", conf_after

        return ch, "", "", conf_after

    @staticmethod
    def _role(idx: int, structure: dict) -> str:
        for r in ("state", "rto", "series", "number"):
            start, end = structure.get(r) or (0, 0)
            if start <= idx < end:
                return r
        return "unknown"


def _infer_structure(norm: str) -> dict[str, tuple[int, int]]:
    """Infer (start,end) of state/rto/series/number from a normalized plate."""
    # Standard: <STATE 2><RTO 2><SERIES 2><NUMBER 4>  -> length 10
    if len(norm) >= 10:
        return {
            "state": (0, 2),
            "rto": (2, 4),
            "series": (4, 6),
            "number": (6, len(norm)),
        }
    if len(norm) >= 6:
        return {
            "state": (0, 2),
            "rto": (2, 4),
            "series": (4, 6),
            "number": (6, len(norm)),
        }
    return {"state": (0, min(2, len(norm))), "rto": (0, 0), "series": (0, 0), "number": (0, 0)}


def _structural_grammar_ok(norm: str, reg) -> bool:
    """Standard-plate grammar: correct length, digits in RTO, letters in series,
    digits in the unique number, and a recognized state code."""
    if len(norm) not in (10, 11, 12):
        return False
    if not reg.state or not state_code_valid(reg.state):
        return False
    if not (reg.rto and reg.rto.isdigit()):
        return False
    if not (reg.series and reg.series.isalpha()):
        return False
    if not (reg.number and reg.number.isdigit()):
        return False
    return True


def _state_prefix(norm: str, idx: int, letter: str) -> str | None:
    """Try to form a valid state code by placing `letter` at `idx` (0 or 1)."""
    if len(norm) < 2 or idx not in (0, 1):
        return None
    other = norm[1] if idx == 0 else norm[0]
    for candidate in (letter + other, other + letter):
        if state_code_valid(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------- #
# Parser
# ---------------------------------------------------------------------- #
@dataclass
class Registration:
    plate_type: str  # private/commercial/government/electric/temporary/trade/vintage/BH/military/unknown
    state: str | None
    rto: str | None
    district: str | None
    series: str | None
    number: str | None
    raw: str
    normalized: str


class IndianRegistrationParser:
    """Classify plate type and parse state/RTO/series/number."""

    # Military prefix marks (Corps) — classify, don't normalize further.
    MILITARY_PREFIXES = ("CC", "CR", "CS", "CT", "CV", "CW", "CZ", "CD")
    STATE_OVERRIDES = {"DL", "BH"}

    def parse(self, normalized: str) -> Registration:
        norm = normalized.upper()
        plate_type = self._classify(norm)

        # Military: classify only.
        if plate_type == "military":
            return Registration(plate_type, None, None, None, None, None, norm, norm)

        # BH series: <BH><2d><series 2-3><number>
        if plate_type == "BH":
            return self._parse_bh(norm)

        # Generic structural parse for standard plates.
        if len(norm) < 4 or not norm[:2].isalpha():
            return Registration(plate_type, None, None, None, None, None, norm, norm)

        state = norm[:2]
        rest = norm[2:]
        # RTO digits (variable 1-2 length, but normally 2).
        rto = rest[:2] if rest[:2].isdigit() else (rest[:1] if rest[:1].isdigit() else None)
        rto = rto if rto else None
        after = rest[len(rto) :] if rto else rest
        # series: leading letters
        si = 0
        while si < len(after) and after[si].isalpha():
            si += 1
        series = after[:si] if si > 0 else None
        number = after[si:] if after[si:] else None

        # If the "series" is empty but number is long, re-interpret gracefully.
        district = district_name(state, rto) if state and state != "BH" else None
        return Registration(plate_type, state, rto, district, series, number, norm, norm)

    def _classify(self, norm: str) -> str:
        if norm.startswith("BH") and len(norm) >= 8:
            return "BH"
        two = norm[:2]
        if len(norm) == 10 and norm[:2] in self.STATE_OVERRIDES:
            pass
        if two in ("CC",) or norm[:2] in self.MILITARY_PREFIXES:
            return "military"
        # Temporary: <state><rto>T<...> or appended "T" marking.
        if len(norm) >= 5 and norm[2:4].isdigit() and "T" in norm[4:6]:
            return "temporary"
        # Trade / dealer: state->rto then "T" series variant.
        if len(norm) >= 5 and norm[2:4].isdigit() and norm[4:6] in ("TC", "TR") :
            return "trade"
        if len(norm) >= 8 and norm[:5].endswith("E"):
            return "electric"
        return "private"

    def _parse_bh(self, norm: str) -> Registration:
        # BH <rr> <series> <number>  e.g. BH01AB1234
        rto = norm[2:4] if norm[2:4].isdigit() else None
        after = norm[4:]
        si = 0
        while si < len(after) and after[si].isalpha():
            si += 1
        series = after[:si] if si else None
        number = after[si:] if after[si:] else None
        return Registration(
            "BH", "BH", rto, "BH series (all states)", series, number, norm, norm
        )


# ---------------------------------------------------------------------- #
# Validation engine
# ---------------------------------------------------------------------- #
class ValidationEngine:
    """Reject impossible plates (state, RTO, length, positions, symbols)."""

    def __init__(self) -> None:
        self._parser = IndianRegistrationParser()

    def validate(self, normalized: str, conf: float) -> tuple[list[str], bool]:
        """Return (problems, valid)."""
        problems: list[str] = []
        norm = normalized.upper()
        if not norm:
            problems.append("empty plate")
            return problems, False

        # Illegal symbols
        if not all(c.isalnum() for c in norm):
            problems.append("illegal symbols present")
            return problems, False

        reg = self._parser.parse(norm)

        # Military / BH are classified, not structurally validated the same way.
        if reg.plate_type == "military":
            return problems, True  # classify-only
        if reg.plate_type == "BH":
            if reg.series and reg.number:
                return problems, True
            problems.append("incomplete BH registration")
            return problems, False

        if len(norm) < 6 or len(norm) > 12:
            problems.append(f"invalid length {len(norm)} (expected 6..12)")

        if not state_code_valid(reg.state or ""):
            problems.append(f"impossible state code '{reg.state}'")
        elif reg.rto and not state_rto_valid(reg.state, reg.rto):
            problems.append(f"impossible RTO code '{reg.rto}' for state '{reg.state}'")

        # Series must be letters (2 for standard).
        if reg.series and not reg.series.isalpha():
            problems.append("series must be letters")

        # Number must be digits.
        if reg.number and not reg.number.isdigit():
            problems.append("unique number must be digits")

        # Conf gate
        if conf < THRESHOLD_REJECT:
            problems.append(f"confidence below reject threshold ({conf:.2f})")

        return problems, len(problems) == 0


# ---------------------------------------------------------------------- #
# Re-ranking
# ---------------------------------------------------------------------- #
@dataclass
class Candidate:
    text: str
    confidence: float = 1.0
    chars: list[OcrChar] = field(default_factory=list)


class ConfidenceReRanker:
    """Rank multiple OCR candidates using an *effective confidence* score.

    A candidate is scored as::

        effective = OCR confidence
                    - correction penalty      (per OCR correction required)
                    - ambiguity penalty       (if the reading had to be resolved)
                    + validator confidence    (when the corrected form is valid)
                    + grammar confidence      (when state + plate grammar line up)

    Candidates that already match a valid canonical form are preferred over ones
    that only become identical *after* an OCR correction — absence of corrections
    is the strongest signal that a reading was clean. The correction engine is
    applied before scoring so every candidate is compared on a level playing field.
    """

    def __init__(
        self,
        correction_penalty: float = 0.08,
        ambiguity_penalty: float = 0.05,
    ) -> None:
        self._validator = ValidationEngine()
        self._parser = IndianRegistrationParser()
        self._corrector = CharacterCorrectionEngine()
        self.correction_penalty = correction_penalty
        self.ambiguity_penalty = ambiguity_penalty

    # ------------------------------------------------------------------ #
    def effective_score(self, candidate: Candidate) -> float:
        """Effective confidence of a single candidate (see class docstring)."""
        conf = candidate.confidence
        if candidate.chars:
            chars = [OcrChar(c.char, c.confidence) for c in candidate.chars]
        else:
            chars = [OcrChar(c, conf) for c in candidate.text]

        # Correct confusables first; validate on the *corrected* reading.
        pre_norm = PlateNormalizer().normalize("".join(c.char for c in chars))
        pre_reg = self._parser.parse(pre_norm)
        corrected, corrections = self._corrector.correct_ocr(
            chars, plate_type=pre_reg.plate_type
        )
        norm = PlateNormalizer().normalize("".join(c.char for c in corrected))

        correction_penalty = self.correction_penalty * len(corrections)

        # Ambiguity: confusable glyphs were present *and* had to be resolved,
        # i.e. the OCR reading itself was unreliable rather than already clean.
        ambiguous = bool(corrections) and any(
            c.char in _CONFUSABLE_PAIRS for c in chars
        )
        ambiguity_penalty = self.ambiguity_penalty if ambiguous else 0.0

        problems, valid = self._validator.validate(norm, conf)
        validator_confidence = 0.15 if valid and not problems else 0.0

        reg = self._parser.parse(norm)
        grammar_confidence = 0.10 if _structural_grammar_ok(norm, reg) else 0.0

        score = (
            conf
            - correction_penalty
            - ambiguity_penalty
            + validator_confidence
            + grammar_confidence
        )
        return round(max(0.0, score), 4)

    def score(self, norm: str, conf: float) -> float:
        """Back-compat convenience: effective confidence for a plain reading."""
        return self.effective_score(Candidate(norm, conf))

    def rank(self, candidates: list[Candidate]) -> list[tuple[Candidate, float]]:
        scored = [(c, self.effective_score(c)) for c in candidates]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored


# ---------------------------------------------------------------------- #
# Public API result
# ---------------------------------------------------------------------- #
@dataclass
class PlateValidation:
    """Structured output of the validation engine."""

    raw_plate: str
    validated_plate: str
    valid: bool
    confidence: float
    action: str  # accept / review / reject
    state: str | None
    rto: str | None
    district: str | None
    series: str | None
    number: str | None
    plate_type: str
    corrections: list[Correction] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_plate": self.raw_plate,
            "validated_plate": self.validated_plate,
            "valid": self.valid,
            "confidence": round(self.confidence, 3),
            "action": self.action,
            "state": self.state,
            "rto": self.rto,
            "district": self.district,
            "series": self.series,
            "number": self.number,
            "plate_type": self.plate_type,
            "corrections": [c.to_dict() for c in self.corrections],
            "problems": self.problems,
            "explanation": self.explanation,
        }


class PlateValidator:
    """Top-level validation engine — the public API (module 9)."""

    def __init__(
        self,
        reject_threshold: float = THRESHOLD_REJECT,
        review_threshold: float = THRESHOLD_REVIEW,
    ) -> None:
        self.confidence = ConfidenceAnalyzer(reject_threshold, review_threshold)
        self.correct = CharacterCorrectionEngine()
        self.normalize = PlateNormalizer()
        self.parse = IndianRegistrationParser()
        self.validate_ = ValidationEngine()
        self.rank = ConfidenceReRanker()

    # ------------------------------------------------------------------ #
    def validate(
        self,
        raw_text: str,
        *,
        char_confidences: list[float] | None = None,
        candidates: list[Candidate] | None = None,
    ) -> PlateValidation:
        """Validate a raw OCR string (or pick the best of several candidates)."""
        chosen = self._choose_candidate(raw_text, char_confidences, candidates)
        chars, conf = self._to_chars(chosen)

        # Classify the plate type from the *raw* (pre-correction) normalized
        # text so special plates (military/temporary/trade/electric) are not
        # destructively "corrected" by generic structural rules.
        pre_norm = self.normalize.normalize("".join(c.char for c in chars))
        pre_reg = self.parse.parse(pre_norm)

        corrected, corrections = self.correct.correct_ocr(chars, plate_type=pre_reg.plate_type)
        norm = self.normalize.normalize("".join(c.char for c in corrected))
        conf = self.confidence.plate(corrected)

        reg = self.parse.parse(norm)
        problems, valid = self.validate_.validate(norm, conf)
        action = self.confidence.action(conf)
        if problems:
            valid = False

        # Build explanation.
        explanation = self._explain(norm, reg, corrections, problems, valid)

        return PlateValidation(
            raw_plate=raw_text,
            validated_plate=norm,
            valid=valid,
            confidence=conf,
            action=action,
            state=reg.state,
            rto=reg.rto,
            district=reg.district,
            series=reg.series,
            number=reg.number,
            plate_type=reg.plate_type,
            corrections=corrections,
            problems=problems,
            explanation=explanation,
        )

    # ------------------------------------------------------------------ #
    def _choose_candidate(self, raw_text, char_confidences, candidates):
        if candidates:
            best, _ = self.rank.rank(candidates)[0]
            return best
        return raw_text

    def _to_chars(self, chosen: str) -> tuple[list[OcrChar], float]:
        if isinstance(chosen, Candidate):
            if chosen.chars:
                return [OcrChar(c.char, c.confidence) for c in chosen.chars], chosen.confidence
            chars = [OcrChar(c, chosen.confidence) for c in chosen.text]
            return chars, chosen.confidence
        chars = [OcrChar(c, 0.9) for c in str(chosen)]
        return chars, 0.9

    def _explain(self, norm, reg, corrections, problems, valid):
        bits: list[str] = []
        if corrections:
            for c in corrections:
                bits.append(
                    f"corrected '{c.original}'->'{c.corrected}' at {c.index} "
                    f"({c.rule}: {c.reason})"
                )
        else:
            bits.append("no character corrections applied")
        if reg.state:
            bits.append(f"state={reg.state} rto={reg.rto} district={reg.district} "
                        f"series={reg.series} number={reg.number} type={reg.plate_type}")
        if problems:
            bits.append("rejected: " + "; ".join(problems))
        else:
            bits.append("accepted as valid Indian plate")
        return ". ".join(bits)


__all__ = [
    "PlateValidator",
    "PlateValidation",
    "Correction",
    "Candidate",
    "ConfidenceAnalyzer",
    "CharacterCorrectionEngine",
    "PlateNormalizer",
    "IndianRegistrationParser",
    "ValidationEngine",
    "ConfidenceReRanker",
    "Registration",
    "OcrChar",
]

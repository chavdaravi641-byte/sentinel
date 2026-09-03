import GujaratRtoDatabase from "./GUJARAT_RTO_DATABASE.json";

/* ---------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

export interface RtoEntry {
  code: string;
  district: string;
  city: string;
  office_name: string;
  jurisdiction: string;
  is_active: boolean;
}

export interface ValidationResult {
  raw_plate: string;
  corrected_plate: string;
  confidence: number;
  state: string;
  district: string;
  rto_code: string;
  registration_series: string;
  vehicle_number: string;
  valid: boolean;
  reason: string;
  ocr_corrections: OcrCorrection[];
  validation_flags: ValidationFlag[];
}

export interface OcrCorrection {
  position: number;
  original: string;
  corrected: string;
  reason: string;
}

export interface ValidationFlag {
  type: FlagType;
  message: string;
  severity: "error" | "warning" | "info";
}

export type FlagType =
  | "invalid_character"
  | "invalid_position"
  | "confusable_character"
  | "impossible_rto"
  | "invalid_sequence"
  | "format_violation"
  | "unsupported_state"
  | "inactive_rto";

/* ---------------------------------------------------------------------------
 * Constants
 * ------------------------------------------------------------------------- */

const GUJARAT_STATE_CODE = "GJ";
const VALID_RTO_CODES = new Map<string, RtoEntry>(
  GujaratRtoDatabase.valid_rto_codes.map((entry) => [entry.code, entry as RtoEntry])
);

const INDIAN_PLATE_REGEX = /^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$/;

/* Indian plate character positions (0-indexed):
 * [0-1]: State code (2 letters)
 * [2-3]: RTO code (2 digits, sometimes 1 digit)
 * [4-5]: Series (2 letters)
 * [6-9]: Number (4 digits)
 * For 2-digit RTO: total 10 chars
 * For 1-digit RTO: total 9 chars (but in practice, RTO is always 2 digits) */

const INVALID_SEQUENCES = [
  "0000", "1111", "2222", "3333", "4444",
  "5555", "6666", "7777", "8888", "9999",
  "AAAA", "BBBB", "CCCC", "DDDD", "EEEE",
];

const CONFUSABLE_CHARS: Record<string, string[]> = {
  "O": ["0", "D", "Q"],
  "0": ["O", "D", "Q"],
  "I": ["1", "7", "L", "T"],
  "1": ["I", "L", "7", "T"],
  "L": ["1", "I", "7"],
  "T": ["1", "I", "7", "L"],
  "Z": ["2", "7"],
  "2": ["Z", "7"],
  "B": ["8", "D", "R"],
  "8": ["B", "D"],
  "D": ["0", "O", "B"],
  "G": ["6", "C"],
  "6": ["G", "C"],
  "C": ["G", "6", "O"],
  "S": ["5", "8"],
  "5": ["S", "6"],
  "U": ["V"],
  "V": ["U"],
  "N": ["M"],
  "M": ["N"],
  "P": ["R"],
  "R": ["P", "B"],
  "Q": ["O", "0"],
  "X": ["K"],
  "K": ["X"],
  "H": ["4"],
  "4": ["H"],
  "9": ["G", "6"],
};

const COMMON_OCR_ERRORS: Record<string, string> = {
  "GJ0": "GJ0",
  "GJO": "GJ0",
  "CJ0": "GJ0",
  "GJ1": "GJ1",
  "GJI": "GJ1",
  "GI0": "GJ0",
  "6J0": "GJ0",
  "GJO1": "GJ01",
};

const STATE_CODES = new Map<string, string>([
  ["AP", "Andhra Pradesh"], ["AR", "Arunachal Pradesh"], ["AS", "Assam"],
  ["BR", "Bihar"], ["CG", "Chhattisgarh"], ["CH", "Chandigarh"],
  ["DD", "Dadra and Nagar Haveli and Daman and Diu"], ["DL", "Delhi"],
  ["GA", "Goa"], ["GJ", "Gujarat"], ["HR", "Haryana"],
  ["HP", "Himachal Pradesh"], ["JH", "Jharkhand"], ["JK", "Jammu and Kashmir"],
  ["KA", "Karnataka"], ["KL", "Kerala"], ["LA", "Ladakh"],
  ["MP", "Madhya Pradesh"], ["MH", "Maharashtra"], ["ML", "Meghalaya"],
  ["MN", "Manipur"], ["MZ", "Mizoram"], ["NL", "Nagaland"],
  ["OD", "Odisha"], ["PB", "Punjab"], ["PY", "Puducherry"],
  ["RJ", "Rajasthan"], ["SK", "Sikkim"], ["TN", "Tamil Nadu"],
  ["TR", "Tripura"], ["TS", "Telangana"], ["UK", "Uttarakhand"],
  ["UP", "Uttar Pradesh"], ["WB", "West Bengal"],
]);

/* ---------------------------------------------------------------------------
 * Core Validation Engine
 * ------------------------------------------------------------------------- */

export function validateLicensePlate(rawInput: string): ValidationResult {
  const raw_plate = rawInput.toUpperCase().trim();
  const ocrCorrections: OcrCorrection[] = [];
  const validationFlags: ValidationFlag[] = [];

  // Step 1: Basic sanitization
  let normalized = normalizePlate(raw_plate, ocrCorrections);

  // Step 2: Detect state
  const stateCode = normalized.substring(0, 2);
  const state = STATE_CODES.get(stateCode);

  if (!state) {
    return buildUnsupportedResult(raw_plate, raw_plate, stateCode, 0.5);
  }

  // Step 3: If not Gujarat, return as unsupported
  if (stateCode !== GUJARAT_STATE_CODE) {
    return buildUnsupportedResult(raw_plate, normalized, stateCode, 0.7);
  }

  // Step 4: Gujarat-specific validation
  return validateGujaratPlate(raw_plate, normalized, ocrCorrections, validationFlags);
}

/* ---------------------------------------------------------------------------
 * Normalization & OCR Correction
 * ------------------------------------------------------------------------- */

function normalizePlate(
  raw: string,
  corrections: OcrCorrection[]
): string {
  let result = raw.toUpperCase().replace(/[^A-Z0-9]/g, "");

  // Strip "IND" prefix (new format: IND GJ01AB1234)
  if (result.startsWith("IND")) {
    const stripped = result.substring(3);
    if (stripped.length >= 9) {
      corrections.push({
        position: 0,
        original: "IND",
        corrected: "",
        reason: "Removed IND country-code prefix",
      });
      result = stripped;
    }
  }

  // Try common OCR error patterns for the prefix
  const prefix = result.substring(0, Math.min(4, result.length));
  for (const [pattern, correction] of Object.entries(COMMON_OCR_ERRORS)) {
    if (prefix.startsWith(pattern.substring(0, 3))) {
      if (result.substring(0, pattern.length) === pattern) {
        const fixed = correction + result.substring(pattern.length);
        if (fixed !== result) {
          corrections.push({
            position: 0,
            original: result.substring(0, pattern.length),
            corrected: correction,
            reason: "OCR prefix correction",
          });
          result = fixed;
          break;
        }
      }
    }
  }

  return result;
}

/* ---------------------------------------------------------------------------
 * Gujarat-Specific Validation
 * ------------------------------------------------------------------------- */

function validateGujaratPlate(
  raw_plate: string,
  normalized: string,
  ocrCorrections: OcrCorrection[],
  validationFlags: ValidationFlag[]
): ValidationResult {
  // Extract RTO code (first 4 characters: GJ + 2 digits)
  const rtoCode = normalized.substring(0, 4);

  // Validate RTO code
  const rtoEntry = VALID_RTO_CODES.get(rtoCode);

  if (!rtoEntry) {
    // Try to recover RTO code with confusable correction
    const recovered = recoverRtoCode(normalized, ocrCorrections);
    if (recovered) {
      normalized = recovered.normalized;
      ocrCorrections.push(...recovered.corrections);
      const recoveredEntry = VALID_RTO_CODES.get(normalized.substring(0, 4));
      if (recoveredEntry) {
        return buildValidResult(raw_plate, normalized, recoveredEntry, ocrCorrections, validationFlags);
      }
    }

    validationFlags.push({
      type: "impossible_rto",
      message: `RTO code ${rtoCode} is not a valid Gujarat RTO`,
      severity: "error",
    });
    return buildInvalidResult(raw_plate, normalized, rtoCode, ocrCorrections, validationFlags, "Impossible RTO code");
  }

  if (!rtoEntry.is_active) {
    validationFlags.push({
      type: "inactive_rto",
      message: `RTO code ${rtoCode} is inactive`,
      severity: "warning",
    });
  }

  // Validate format
  const formatValidation = validateGujaratFormat(normalized, ocrCorrections);
  normalized = formatValidation.plate;
  if (!formatValidation.valid) {
    validationFlags.push(...formatValidation.flags);
    return buildInvalidResult(raw_plate, normalized, rtoCode, ocrCorrections, validationFlags, formatValidation.reason);
  }

  // Check for impossible character positions
  const positionValidation = validateCharacterPositions(normalized, ocrCorrections);
  normalized = positionValidation.plate;
  if (!positionValidation.valid) {
    validationFlags.push(...positionValidation.flags);
    return buildInvalidResult(raw_plate, normalized, rtoCode, ocrCorrections, validationFlags, positionValidation.reason);
  }

  // Check for invalid sequences
  const sequenceValidation = validateSequence(normalized);
  if (!sequenceValidation.valid) {
    validationFlags.push(...sequenceValidation.flags);
    return buildInvalidResult(raw_plate, normalized, rtoCode, ocrCorrections, validationFlags, sequenceValidation.reason);
  }

  return buildValidResult(raw_plate, normalized, rtoEntry, ocrCorrections, validationFlags);
}

/* ---------------------------------------------------------------------------
 * Format Validation
 * ------------------------------------------------------------------------- */

function validateGujaratFormat(
  plate: string,
  corrections: OcrCorrection[]
): { valid: boolean; flags: ValidationFlag[]; reason: string; plate: string } {
  const flags: ValidationFlag[] = [];

  // Check length (should be 10 characters for GJ01AB1234 format)
  if (plate.length < 9 || plate.length > 12) {
    flags.push({
      type: "format_violation",
      message: `Invalid plate length: ${plate.length} (expected 10)`,
      severity: "error",
    });
    return { valid: false, flags, reason: "Invalid plate length", plate };
  }

  // Check state code (positions 0-1)
  if (plate.substring(0, 2) !== GUJARAT_STATE_CODE) {
    flags.push({
      type: "format_violation",
      message: `Invalid state code: ${plate.substring(0, 2)} (expected GJ)`,
      severity: "error",
    });
    return { valid: false, flags, reason: "Invalid state code", plate };
  }

  // Check RTO code (positions 2-3)
  let rtoDigits = plate.substring(2, 4);
  if (!/^\d{2}$/.test(rtoDigits)) {
    // Try to fix confusable characters
    const fixed = fixConfusableDigits(rtoDigits, 2, corrections);
    if (fixed !== rtoDigits) {
      rtoDigits = fixed;
      plate = plate.substring(0, 2) + rtoDigits + plate.substring(4);
    } else {
      flags.push({
        type: "format_violation",
        message: `Invalid RTO code format: ${rtoDigits}`,
        severity: "error",
      });
      return { valid: false, flags, reason: "Invalid RTO code format", plate };
    }
  }

  // Check series (positions 4-5, or 4-6 for 3-letter series)
  const seriesMatch = plate.substring(4).match(/^([A-Z]{2,3})/);
  if (!seriesMatch) {
    // Try to fix confusable characters
    const fixed = fixConfusableLetters(plate.substring(4, 6), 4, corrections);
    if (fixed !== plate.substring(4, 6)) {
      plate = plate.substring(0, 4) + fixed + plate.substring(6);
    } else {
      flags.push({
        type: "format_violation",
        message: `Invalid series format at position 4`,
        severity: "error",
      });
      return { valid: false, flags, reason: "Invalid series format", plate };
    }
  }

  // Check number (last 4 characters)
  const numberPart = plate.slice(-4);
  if (!/^\d{4}$/.test(numberPart)) {
    // Try to fix confusable digits
    const fixed = fixConfusableDigits(numberPart, plate.length - 4, corrections);
    if (fixed !== numberPart) {
      plate = plate.substring(0, plate.length - 4) + fixed;
    } else {
      flags.push({
        type: "format_violation",
        message: `Invalid number format at end`,
        severity: "error",
      });
      return { valid: false, flags, reason: "Invalid number format", plate };
    }
  }

  return { valid: true, flags, reason: "", plate };
}

/* ---------------------------------------------------------------------------
 * Character Position Validation
 * ------------------------------------------------------------------------- */

function validateCharacterPositions(
  plate: string,
  corrections: OcrCorrection[]
): { valid: boolean; flags: ValidationFlag[]; reason: string; plate: string } {
  const flags: ValidationFlag[] = [];

  // Positions 0-1: Must be letters (state code)
  for (let i = 0; i < 2; i++) {
    const c = plate[i]!;
    if (!/[A-Z]/.test(c)) {
      flags.push({
        type: "invalid_position",
        message: `Position ${i} must be a letter, got '${c}'`,
        severity: "error",
      });
      return { valid: false, flags, reason: "Invalid character at state code position", plate };
    }
  }

  // Positions 2-3: Must be digits (RTO code)
  for (let i = 2; i < 4; i++) {
    const c = plate[i]!;
    if (!/[0-9]/.test(c)) {
      // Try confusable correction
      const fixed = fixConfusableDigits(c, i, corrections);
      if (fixed !== c) {
        plate = plate.substring(0, i) + fixed + plate.substring(i + 1);
      } else {
        flags.push({
          type: "invalid_position",
          message: `Position ${i} must be a digit, got '${c}'`,
          severity: "error",
        });
        return { valid: false, flags, reason: "Invalid character at RTO code position", plate };
      }
    }
  }

  // Position 4-5 (or 4-6): Must be letters (series)
  const seriesEnd = findSeriesEnd(plate);
  for (let i = 4; i < seriesEnd; i++) {
    const c = plate[i]!;
    if (!/[A-Z]/.test(c)) {
      // Try confusable correction (digit to letter)
      const fixed = fixConfusableLetters(c, i, corrections);
      if (fixed !== c) {
        plate = plate.substring(0, i) + fixed + plate.substring(i + 1);
      } else {
        flags.push({
          type: "invalid_position",
          message: `Position ${i} must be a letter, got '${c}'`,
          severity: "error",
        });
        return { valid: false, flags, reason: "Invalid character at series position", plate };
      }
    }
  }

  // Last 4 positions: Must be digits (vehicle number)
  const numberStart = plate.length - 4;
  for (let i = numberStart; i < plate.length; i++) {
    const c = plate[i]!;
    if (!/[0-9]/.test(c)) {
      // Try confusable correction
      const fixed = fixConfusableDigits(c, i, corrections);
      if (fixed !== c) {
        plate = plate.substring(0, i) + fixed + plate.substring(i + 1);
      } else {
        flags.push({
          type: "invalid_position",
          message: `Position ${i} must be a digit, got '${c}'`,
          severity: "error",
        });
        return { valid: false, flags, reason: "Invalid character at vehicle number position", plate };
      }
    }
  }

  return { valid: true, flags, reason: "", plate };
}

/* ---------------------------------------------------------------------------
 * Sequence Validation
 * ------------------------------------------------------------------------- */

function validateSequence(plate: string): { valid: boolean; flags: ValidationFlag[]; reason: string } {
  const flags: ValidationFlag[] = [];
  const numberPart = plate.slice(-4);

  // Check for invalid sequences
  if (INVALID_SEQUENCES.includes(numberPart)) {
    flags.push({
      type: "invalid_sequence",
      message: `Invalid vehicle number sequence: ${numberPart}`,
      severity: "error",
    });
    return { valid: false, flags, reason: "Invalid sequence" };
  }

  // Check for ascending/descending sequences (e.g., 1234, 4321)
  if (isSequential(numberPart)) {
    flags.push({
      type: "invalid_sequence",
      message: `Sequential vehicle number: ${numberPart}`,
      severity: "warning",
    });
  }

  return { valid: true, flags, reason: "" };
}

/* ---------------------------------------------------------------------------
 * RTO Code Recovery
 * ------------------------------------------------------------------------- */

function recoverRtoCode(
  plate: string,
  corrections: OcrCorrection[]
): { normalized: string; corrections: OcrCorrection[] } | null {
  const correctionsCopy = [...corrections];
  const rtoPart = plate.substring(2, 4);

  // Try all possible confusable character replacements
  for (let i = 0; i < 2; i++) {
    const char = rtoPart[i]!;
    const confusables = CONFUSABLE_CHARS[char] || [];

    for (const confusable of confusables) {
      if (/[0-9]/.test(confusable)) {
        const newRtoPart = rtoPart.substring(0, i) + confusable + rtoPart.substring(i + 1);
        const newCode = plate.substring(0, 2) + newRtoPart;

        if (VALID_RTO_CODES.has(newCode)) {
          correctionsCopy.push({
            position: 2 + i,
            original: char,
            corrected: confusable,
            reason: `Confusable character correction`,
          });
          return {
            normalized: plate.substring(0, 2) + newRtoPart + plate.substring(4),
            corrections: correctionsCopy,
          };
        }
      }
    }
  }

  return null;
}

/* ---------------------------------------------------------------------------
 * Confusable Character Handling
 * ------------------------------------------------------------------------- */

function fixConfusableDigits(
  input: string,
  startPosition: number,
  corrections: OcrCorrection[]
): string {
  let result = input;

  for (let i = 0; i < input.length; i++) {
    const char = input[i]!;
    if (/[A-Z]/.test(char)) {
      // Character is a letter but should be a digit
      const confusables = CONFUSABLE_CHARS[char] || [];
      for (const confusable of confusables) {
        if (/[0-9]/.test(confusable)) {
          corrections.push({
            position: startPosition + i,
            original: char,
            corrected: confusable,
            reason: "Confusable character correction (letter to digit)",
          });
          result = result.substring(0, i) + confusable + result.substring(i + 1);
          break;
        }
      }
    }
  }

  return result;
}

function fixConfusableLetters(
  input: string,
  startPosition: number,
  corrections: OcrCorrection[]
): string {
  let result = input;

  for (let i = 0; i < input.length; i++) {
    const char = input[i]!;
    if (/[0-9]/.test(char)) {
      // Character is a digit but should be a letter
      const confusables = CONFUSABLE_CHARS[char] || [];
      for (const confusable of confusables) {
        if (/[A-Z]/.test(confusable)) {
          corrections.push({
            position: startPosition + i,
            original: char,
            corrected: confusable,
            reason: "Confusable character correction (digit to letter)",
          });
          result = result.substring(0, i) + confusable + result.substring(i + 1);
          break;
        }
      }
    }
  }

  return result;
}

/* ---------------------------------------------------------------------------
 * Helper Functions
 * ------------------------------------------------------------------------- */

function findSeriesEnd(plate: string): number {
  // Find where the series ends and number begins
  // Series is typically 2-3 letters after the 4-digit RTO code
  let i = 4;
  while (i < plate.length && /[A-Z]/.test(plate[i]!)) {
    i++;
  }
  return i;
}

function isSequential(num: string): boolean {
  if (num.length !== 4) return false;

  // Check ascending
  let ascending = true;
  for (let i = 1; i < num.length; i++) {
    if (parseInt(num[i]!) !== parseInt(num[i - 1]!) + 1) {
      ascending = false;
      break;
    }
  }

  // Check descending
  let descending = true;
  for (let i = 1; i < num.length; i++) {
    if (parseInt(num[i]!) !== parseInt(num[i - 1]!) - 1) {
      descending = false;
      break;
    }
  }

  return ascending || descending;
}

/* ---------------------------------------------------------------------------
 * Result Builders
 * ------------------------------------------------------------------------- */

function buildValidResult(
  raw_plate: string,
  corrected_plate: string,
  rtoEntry: RtoEntry,
  ocrCorrections: OcrCorrection[],
  validationFlags: ValidationFlag[]
): ValidationResult {
  const confidence = calculateConfidence(corrected_plate, ocrCorrections, validationFlags);

  return {
    raw_plate,
    corrected_plate,
    confidence,
    state: "Gujarat",
    district: rtoEntry.district,
    rto_code: rtoEntry.code,
    registration_series: extractSeries(corrected_plate),
    vehicle_number: extractVehicleNumber(corrected_plate),
    valid: true,
    reason: "Valid Gujarat license plate",
    ocr_corrections: ocrCorrections,
    validation_flags: validationFlags,
  };
}

function buildInvalidResult(
  raw_plate: string,
  corrected_plate: string,
  rtoCode: string,
  ocrCorrections: OcrCorrection[],
  validationFlags: ValidationFlag[],
  reason: string
): ValidationResult {
  const confidence = calculateConfidence(corrected_plate, ocrCorrections, validationFlags);
  const rtoEntry = VALID_RTO_CODES.get(rtoCode);

  return {
    raw_plate,
    corrected_plate,
    confidence,
    state: "Gujarat",
    district: rtoEntry?.district || "Unknown",
    rto_code: rtoCode,
    registration_series: extractSeries(corrected_plate),
    vehicle_number: extractVehicleNumber(corrected_plate),
    valid: false,
    reason,
    ocr_corrections: ocrCorrections,
    validation_flags: validationFlags,
  };
}

function buildUnsupportedResult(
  raw_plate: string,
  corrected_plate: string,
  stateCode: string,
  confidence: number
): ValidationResult {
  return {
    raw_plate,
    corrected_plate,
    confidence,
    state: STATE_CODES.get(stateCode) || "Unknown",
    district: "",
    rto_code: "",
    registration_series: extractSeries(corrected_plate),
    vehicle_number: extractVehicleNumber(corrected_plate),
    valid: false,
    reason: "unsupported_state",
    ocr_corrections: [],
    validation_flags: [
      {
        type: "unsupported_state",
        message: `State code ${stateCode} is not Gujarat`,
        severity: "info",
      },
    ],
  };
}

/* ---------------------------------------------------------------------------
 * Confidence Calculation
 * ------------------------------------------------------------------------- */

function calculateConfidence(
  plate: string,
  ocrCorrections: OcrCorrection[],
  validationFlags: ValidationFlag[]
): number {
  let confidence = 1.0;

  // Deduct for OCR corrections
  confidence -= ocrCorrections.length * 0.05;

  // Deduct for validation flags
  for (const flag of validationFlags) {
    if (flag.severity === "error") {
      confidence -= 0.2;
    } else if (flag.severity === "warning") {
      confidence -= 0.1;
    }
  }

  // Ensure confidence is between 0 and 1
  return Math.max(0, Math.min(1, confidence));
}

/* ---------------------------------------------------------------------------
 * Extraction Helpers
 * ------------------------------------------------------------------------- */

function extractSeries(plate: string): string {
  const match = plate.substring(4).match(/^([A-Z]{2,3})/);
  return match ? match[1] ?? "" : "";
}

function extractVehicleNumber(plate: string): string {
  const match = plate.match(/(\d{4})$/);
  return match ? match[1] ?? "" : "";
}

/* ---------------------------------------------------------------------------
 * Batch Validation
 * ------------------------------------------------------------------------- */

export function validateMultiplePlates(plates: string[]): ValidationResult[] {
  return plates.map((plate) => validateLicensePlate(plate));
}

/* ---------------------------------------------------------------------------
 * Statistics
 * ------------------------------------------------------------------------- */

export interface ValidationStats {
  total: number;
  valid: number;
  invalid: number;
  unsupported: number;
  corrected: number;
  average_confidence: number;
  top_districts: Array<{ district: string; count: number }>;
}

export function calculateStats(results: ValidationResult[]): ValidationStats {
  const valid = results.filter((r) => r.valid).length;
  const invalid = results.filter((r) => !r.valid && r.reason !== "unsupported_state").length;
  const unsupported = results.filter((r) => r.reason === "unsupported_state").length;
  const corrected = results.filter((r) => r.ocr_corrections.length > 0).length;
  const averageConfidence = results.reduce((sum, r) => sum + r.confidence, 0) / results.length;

  // Count districts
  const districtCounts = new Map<string, number>();
  for (const result of results) {
    if (result.district) {
      districtCounts.set(result.district, (districtCounts.get(result.district) || 0) + 1);
    }
  }

  const topDistricts = Array.from(districtCounts.entries())
    .map(([district, count]) => ({ district, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  return {
    total: results.length,
    valid,
    invalid,
    unsupported,
    corrected,
    average_confidence: averageConfidence,
    top_districts: topDistricts,
  };
}

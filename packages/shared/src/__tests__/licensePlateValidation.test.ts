import { describe, it, expect } from "vitest";
import {
  validateLicensePlate,
  validateMultiplePlates,
  calculateStats,
} from "../licensePlateValidation";
import type { ValidationResult } from "../licensePlateValidation";

/* ---------------------------------------------------------------------------
 * Helper
 * ------------------------------------------------------------------------- */

function expectValid(result: ValidationResult, expectedDistrict?: string) {
  expect(result.valid).toBe(true);
  expect(result.state).toBe("Gujarat");
  expect(result.rto_code).toMatch(/^GJ\d{2}$/);
  if (expectedDistrict) {
    expect(result.district).toBe(expectedDistrict);
  }
}

function expectUnsupported(result: ValidationResult) {
  expect(result.valid).toBe(false);
  expect(result.reason).toBe("unsupported_state");
  expect(result.validation_flags.some((f) => f.type === "unsupported_state")).toBe(true);
}

/* ---------------------------------------------------------------------------
 * Valid Gujarat Plates — All 40 RTO Codes
 * ------------------------------------------------------------------------- */

describe("Valid Gujarat license plates", () => {
  const testCases: Array<[string, string, string]> = [
    ["GJ01AB1234", "GJ01", "Ahmedabad"],
    ["GJ02CD5678", "GJ02", "Mehsana"],
    ["GJ03EF9012", "GJ03", "Rajkot"],
    ["GJ04GH3456", "GJ04", "Bhavnagar"],
    ["GJ05IJ7890", "GJ05", "Surat"],
    ["GJ06KL1357", "GJ06", "Vadodara"],
    ["GJ07MN2468", "GJ07", "Kheda"],
    ["GJ08OP3691", "GJ08", "Banaskantha"],
    ["GJ09QR4812", "GJ09", "Sabarkantha"],
    ["GJ10ST5923", "GJ10", "Jamnagar"],
    ["GJ11UV6034", "GJ11", "Junagadh"],
    ["GJ12WX7145", "GJ12", "Kutch"],
    ["GJ13YZ8256", "GJ13", "Surendranagar"],
    ["GJ14AB9367", "GJ14", "Amreli"],
    ["GJ15CD0478", "GJ15", "Valsad"],
    ["GJ16EF1589", "GJ16", "Bharuch"],
    ["GJ17GH2690", "GJ17", "Panchmahal"],
    ["GJ18IJ3801", "GJ18", "Gandhinagar"],
    ["GJ19KL4912", "GJ19", "Surat"],
    ["GJ20MN6023", "GJ20", "Dahod"],
    ["GJ21OP7134", "GJ21", "Navsari"],
    ["GJ22QR8245", "GJ22", "Narmada"],
    ["GJ23ST9356", "GJ23", "Anand"],
    ["GJ24UV0467", "GJ24", "Patan"],
    ["GJ25WX1578", "GJ25", "Porbandar"],
    ["GJ26YZ2689", "GJ26", "Tapi"],
    ["GJ27AB3790", "GJ27", "Ahmedabad"],
    ["GJ28CD4801", "GJ28", "Surat"],
    ["GJ29EF5912", "GJ29", "Vadodara"],
    ["GJ30GH6023", "GJ30", "Dang"],
    ["GJ31IJ7134", "GJ31", "Aravalli"],
    ["GJ32KL8245", "GJ32", "Gir Somnath"],
    ["GJ33MN9356", "GJ33", "Botad"],
    ["GJ34OP0467", "GJ34", "Chhota Udaipur"],
    ["GJ35QR1578", "GJ35", "Mahisagar"],
    ["GJ36ST2689", "GJ36", "Morbi"],
    ["GJ37UV3790", "GJ37", "Devbhoomi Dwarka"],
    ["GJ38WX4801", "GJ38", "Ahmedabad"],
    ["GJ39YZ5912", "GJ39", "Kutch"],
    ["GJ40AB6023", "GJ40", "Vav-Tharad"],
  ];

  it.each(testCases)("validates %s correctly", (plate, expectedRto, expectedDistrict) => {
    const result = validateLicensePlate(plate);
    expectValid(result, expectedDistrict);
    expect(result.rto_code).toBe(expectedRto);
    expect(result.corrected_plate).toBe(plate);
    expect(result.confidence).toBeGreaterThanOrEqual(0.9);
  });
});

/* ---------------------------------------------------------------------------
 * OCR Correction — Character Recovery
 * ------------------------------------------------------------------------- */

describe("OCR correction and character recovery", () => {
  it("recovers GJO1 to GJ01", () => {
    const result = validateLicensePlate("GJO1AB1234");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
    expect(result.ocr_corrections.length).toBeGreaterThan(0);
    expect(result.district).toBe("Ahmedabad");
  });

  it("recovers GJ1 (missing digit) to GJ10", () => {
    const result = validateLicensePlate("GJI0CD5678");
    expect(result.corrected_plate).toMatch(/^GJ\d{2}/);
  });

  it("handles lowercase input", () => {
    const result = validateLicensePlate("gj01ab1234");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });

  it("handles input with spaces and dashes", () => {
    const result = validateLicensePlate("GJ 01 AB 1234");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });

  it("handles input with extra spaces", () => {
    const result = validateLicensePlate("  GJ01AB1234  ");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });
});

/* ---------------------------------------------------------------------------
 * Confusable Character Correction
 * ------------------------------------------------------------------------- */

describe("Confusable character correction", () => {
  it("corrects I to 1 in RTO code position", () => {
    const result = validateLicensePlate("GJ0IAB1234");
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });

  it("corrects I to 1 in number position", () => {
    const result = validateLicensePlate("GJ01AB12I4");
    expect(result.corrected_plate).toBe("GJ01AB1214");
  });

  it("corrects letter in digit position", () => {
    const result = validateLicensePlate("GJ01AB123S");
    expect(result.corrected_plate).toBe("GJ01AB1235");
  });

  it("corrects digit in letter position", () => {
    const result = validateLicensePlate("GJ011B1234");
    expect(result.corrected_plate).toBe("GJ01IB1234");
  });
});

/* ---------------------------------------------------------------------------
 * Invalid RTO Rejection
 * ------------------------------------------------------------------------- */

describe("Invalid RTO rejection", () => {
  it("rejects non-existent RTO code GJ99", () => {
    const result = validateLicensePlate("GJ99AB1234");
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("RTO");
    expect(result.validation_flags.some((f) => f.type === "impossible_rto")).toBe(true);
  });

  it("rejects non-existent RTO code GJ00", () => {
    const result = validateLicensePlate("GJ00AB1234");
    expect(result.valid).toBe(false);
    expect(result.validation_flags.some((f) => f.type === "impossible_rto")).toBe(true);
  });

  it("rejects GJ41 (not in database)", () => {
    const result = validateLicensePlate("GJ41AB1234");
    expect(result.valid).toBe(false);
  });
});

/* ---------------------------------------------------------------------------
 * Invalid Sequence Detection
 * ------------------------------------------------------------------------- */

describe("Invalid sequence detection", () => {
  const invalidSequences = ["0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999"];

  it.each(invalidSequences)("rejects sequence %s", (seq) => {
    const result = validateLicensePlate(`GJ01AB${seq}`);
    expect(result.valid).toBe(false);
    expect(result.validation_flags.some((f) => f.type === "invalid_sequence")).toBe(true);
  });
});

/* ---------------------------------------------------------------------------
 * Impossible Character Position Rejection
 * ------------------------------------------------------------------------- */

describe("Impossible character position rejection", () => {
  it("rejects digit in state code position", () => {
    const result = validateLicensePlate("1J01AB1234");
    expect(result.valid).toBe(false);
    expect(result.state).toBe("Unknown");
  });

  it("rejects letter in RTO code position", () => {
    const result = validateLicensePlate("GJABAB1234");
    expect(result.valid).toBe(false);
  });

  it("rejects digit in series position", () => {
    const result = validateLicensePlate("GJ011B1234");
    // 1 at position 4 should be corrected to I
    expect(result.corrected_plate).toBe("GJ01IB1234");
  });
});

/* ---------------------------------------------------------------------------
 * Unsupported State (Non-Gujarat Plates)
 * ------------------------------------------------------------------------- */

describe("Unsupported state handling", () => {
  it("returns unsupported for Delhi plate", () => {
    const result = validateLicensePlate("DL01AB1234");
    expectUnsupported(result);
    expect(result.state).toBe("Delhi");
    expect(result.raw_plate).toBe("DL01AB1234");
  });

  it("returns unsupported for Maharashtra plate", () => {
    const result = validateLicensePlate("MH02CD5678");
    expectUnsupported(result);
    expect(result.state).toBe("Maharashtra");
  });

  it("returns unsupported for Karnataka plate", () => {
    const result = validateLicensePlate("KA01EF9012");
    expectUnsupported(result);
    expect(result.state).toBe("Karnataka");
  });

  it("returns unsupported for Tamil Nadu plate", () => {
    const result = validateLicensePlate("TN01GH3456");
    expectUnsupported(result);
    expect(result.state).toBe("Tamil Nadu");
  });

  it("returns unsupported for unknown state code", () => {
    const result = validateLicensePlate("XX01AB1234");
    expect(result.valid).toBe(false);
    expect(result.state).toBe("Unknown");
  });
});

/* ---------------------------------------------------------------------------
 * Context-Aware OCR Correction
 * ------------------------------------------------------------------------- */

describe("Context-aware OCR correction", () => {
  it("corrects GJ prefix errors", () => {
    const result = validateLicensePlate("CJ01AB1234");
    expect(result.corrected_plate).toMatch(/^GJ/);
  });

  it("corrects multiple OCR errors in sequence", () => {
    const result = validateLicensePlate("GJO1AB1234");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });

  it("preserves valid plates without modification", () => {
    const result = validateLicensePlate("GJ01AB1234");
    expect(result.corrected_plate).toBe("GJ01AB1234");
    expect(result.ocr_corrections.length).toBe(0);
  });
});

/* ---------------------------------------------------------------------------
 * Format Validation
 * ------------------------------------------------------------------------- */

describe("Format validation", () => {
  it("rejects plates that are too short", () => {
    const result = validateLicensePlate("GJ01AB");
    expect(result.valid).toBe(false);
    expect(result.validation_flags.some((f) => f.type === "format_violation")).toBe(true);
  });

  it("rejects plates that are too long", () => {
    const result = validateLicensePlate("GJ01AB12345678");
    expect(result.valid).toBe(false);
  });

  it("rejects plates without digits at end", () => {
    const result = validateLicensePlate("GJ01AB123A");
    expect(result.valid).toBe(false);
  });
});

/* ---------------------------------------------------------------------------
 * Confidence Scoring
 * ------------------------------------------------------------------------- */

describe("Confidence scoring", () => {
  it("gives high confidence to clean valid plates", () => {
    const result = validateLicensePlate("GJ01AB1234");
    expect(result.confidence).toBeGreaterThanOrEqual(0.9);
  });

  it("reduces confidence for OCR corrections", () => {
    const clean = validateLicensePlate("GJ01AB1234");
    const corrected = validateLicensePlate("GJO1AB1234");
    expect(corrected.confidence).toBeLessThan(clean.confidence);
  });

  it("maintains confidence above 0 for valid corrected plates", () => {
    const result = validateLicensePlate("GJO1AB1234");
    expect(result.confidence).toBeGreaterThan(0);
  });
});

/* ---------------------------------------------------------------------------
 * Batch Validation
 * ------------------------------------------------------------------------- */

describe("Batch validation", () => {
  it("validates multiple plates", () => {
    const plates = [
      "GJ01AB1234",
      "GJ05CD5678",
      "GJ12EF9012",
      "DL01AB1234",
      "MH02CD5678",
    ];
    const results = validateMultiplePlates(plates);
    expect(results).toHaveLength(5);
    expect(results[0]!.valid).toBe(true);
    expect(results[1]!.valid).toBe(true);
    expect(results[2]!.valid).toBe(true);
    expect(results[3]!.valid).toBe(false);
    expect(results[4]!.valid).toBe(false);
  });
});

/* ---------------------------------------------------------------------------
 * Statistics Calculation
 * ------------------------------------------------------------------------- */

describe("Statistics calculation", () => {
  it("calculates correct statistics", () => {
    const plates = [
      "GJ01AB1234",
      "GJ01CD5678",
      "GJ05EF9012",
      "GJO1GH3456", // corrected
      "DL01AB1234",
      "MH02CD5678",
    ];
    const results = validateMultiplePlates(plates);
    const stats = calculateStats(results);

    expect(stats.total).toBe(6);
    expect(stats.valid).toBe(4); // GJ01AB1234, GJ01CD5678, GJ05EF9012, GJO1GH3456
    expect(stats.invalid).toBe(0);
    expect(stats.unsupported).toBe(2); // DL01AB1234, MH02CD5678
    expect(stats.corrected).toBe(1); // GJO1GH3456
    expect(stats.average_confidence).toBeGreaterThan(0);
    expect(stats.average_confidence).toBeLessThanOrEqual(1);
  });
});

/* ---------------------------------------------------------------------------
 * Edge Cases
 * ------------------------------------------------------------------------- */

describe("Edge cases", () => {
  it("handles empty string", () => {
    const result = validateLicensePlate("");
    expect(result.valid).toBe(false);
  });

  it("handles very short input", () => {
    const result = validateLicensePlate("GJ");
    expect(result.valid).toBe(false);
  });

  it("handles special characters", () => {
    const result = validateLicensePlate("GJ@01#AB$1234");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });

  it("handles mixed case", () => {
    const result = validateLicensePlate("Gj01aB1234");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });

  it("handles leading/trailing whitespace", () => {
    const result = validateLicensePlate("  GJ01AB1234  ");
    expect(result.valid).toBe(true);
    expect(result.corrected_plate).toBe("GJ01AB1234");
  });

  it("handles new format with IND prefix", () => {
    const result = validateLicensePlate("IND GJ01AB1234");
    expect(result.corrected_plate).toMatch(/^GJ01/);
  });
});

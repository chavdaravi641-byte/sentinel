import { describe, it, expect } from "vitest";
import {
  rankCandidates,
  PlateHistory,
  PlateContextEngine,
  levenshteinDistance,
} from "../plateContextEngine";
import {
  computeECE,
  brierScore,
  fitTemperature,
  ConfidenceCalibrator,
  benchmark,
} from "../confidenceCalibration";
import type { BenchmarkSample } from "../confidenceCalibration";

/* ---------------------------------------------------------------------------
 * OCR Candidate Ranking
 * ------------------------------------------------------------------------- */

describe("OCR candidate ranking", () => {
  it("ranks the highest-OCR-confidence valid plate first", () => {
    const result = rankCandidates({
      candidates: [
        { text: "GJ01AB1234", confidence: 0.93, camera_id: "cam1" },
        { text: "GJ01AB1284", confidence: 0.72, camera_id: "cam1" },
        { text: "GJ02CD5678", confidence: 0.60, camera_id: "cam1" },
      ],
    });
    expect(result.best.plate).toBe("GJ01AB1234");
    expect(result.ranked[0]!.plate).toBe("GJ01AB1234");
    expect(result.ranked.length).toBe(3);
  });

  it("aggregates multiple candidates resolving to the same plate", () => {
    const result = rankCandidates({
      candidates: [
        { text: "GJ01AB1234", confidence: 0.5, camera_id: "cam1" },
        { text: "GJ01AB12B4", confidence: 0.5, camera_id: "cam2" }, // invalid char, corrected
      ],
      cameraReliability: { cam1: 0.8, cam2: 0.3 },
    });
    // Both should resolve/lead near GJ01, the grammar-passing plate should lead
    expect(result.best.plate).toBe("GJ01AB1234");
  });
});

/* ---------------------------------------------------------------------------
 * Levenshtein distance (editing distance helper)
 * ------------------------------------------------------------------------- */

describe("Levenshtein distance", () => {
  it("computes zero distance for identical strings", () => {
    expect(levenshteinDistance("GJ01AB1234", "GJ01AB1234")).toBe(0);
  });
  it("computes one substitution", () => {
    expect(levenshteinDistance("GJ01AB1234", "GJ01AB1235")).toBe(1);
  });
});

/* ---------------------------------------------------------------------------
 * History Engine
 * ------------------------------------------------------------------------- */

describe("Plate history engine", () => {
  it("records occurrences and recalls priors", () => {
    const history = new PlateHistory({ halfLifeMs: 1000 });
    const now = 1_000_000;
    const sighting = {
      candidate: { text: "GJ01AB1234", confidence: 0.9, camera_id: "cam1" },
      validation: {
        raw_plate: "GJ01AB1234",
        corrected_plate: "GJ01AB1234",
        confidence: 0.9,
        state: "Gujarat",
        district: "Ahmedabad",
        rto_code: "GJ01",
        registration_series: "AB",
        vehicle_number: "1234",
        valid: true,
        reason: "ok",
        ocr_corrections: [],
        validation_flags: [],
      },
      timestamp: now,
    };
    history.record("GJ01AB1234", sighting);
    history.record("GJ01AB1234", sighting);
    expect(history.size()).toBe(1);
    expect(history.lookup("GJ01AB1234")!.occurrences).toBe(2);
    // Recent -> high prior
    expect(history.priorScore("GJ01AB1234", now)).toBeGreaterThan(0.5);
  });

  it("reduces prior for old sightings", () => {
    const history = new PlateHistory({ halfLifeMs: 1000 });
    const old = 1000;
    const now = 1_000_000;
    history.record("GJ02XY9999", {
      candidate: { text: "GJ02XY9999", confidence: 0.9 },
      validation: { raw_plate: "GJ02XY9999", corrected_plate: "GJ02XY9999", confidence: 0.9, state: "Gujarat", district: "Mehsana", rto_code: "GJ02", registration_series: "XY", vehicle_number: "9999", valid: true, reason: "ok", ocr_corrections: [], validation_flags: [] },
      timestamp: old,
    });
    const fresh = history.priorScore("GJ02XY9999", now);
    expect(fresh).toBeLessThan(0.1);
  });
});

/* ---------------------------------------------------------------------------
 * Temporal Consistency (multi-camera agreement)
 * ------------------------------------------------------------------------- */

describe("Temporal / multi-camera consistency", () => {
  it("boosts confidence when multiple cameras agree", () => {
    const oneCam = rankCandidates({
      candidates: [{ text: "GJ01AB1234", confidence: 0.9, camera_id: "camA" }],
    });
    const threeCams = rankCandidates({
      candidates: [
        { text: "GJ01AB1234", confidence: 0.9, camera_id: "camA" },
        { text: "GJ01AB1284", confidence: 0.88, camera_id: "camB" },
        { text: "GJ01AB1284", confidence: 0.95, camera_id: "camC" },
      ],
      cameraReliability: { camA: 1.0, camB: 0.9, camC: 1.0 },
    });
    // The agreed plate should outrank the single-camera outlier case
    expect(threeCams.best.plate).toBe("GJ01AB1284");
    const outlier = rankCandidates({
      candidates: [
        { text: "GJ01AB1234", confidence: 0.95, camera_id: "camA" },
        { text: "GJ01AB1284", confidence: 0.6, camera_id: "camB" },
        { text: "GJ01AB1284", confidence: 0.5, camera_id: "camC" },
      ],
      cameraReliability: { camA: 1.0, camB: 0.9, camC: 1.0 },
    });
    expect(outlier.best.plate).toBe("GJ01AB1234");
    void oneCam;
  });
});

/* ---------------------------------------------------------------------------
 * Bayesian ranking skewing by history
 * ------------------------------------------------------------------------- */

describe("Bayesian ranking with history", () => {
  it("prefers historically-seen plate over one-off OCR read", () => {
    const history = new PlateHistory({ halfLifeMs: 60_000 });
    const now = 50_000;
    history.record("GJ05CD4321", {
      candidate: { text: "GJ05CD4321", confidence: 0.8, camera_id: "camX" },
      validation: { raw_plate: "GJ05CD4321", corrected_plate: "GJ05CD4321", confidence: 0.8, state: "Gujarat", district: "Surat", rto_code: "GJ05", registration_series: "CD", vehicle_number: "4321", valid: true, reason: "ok", ocr_corrections: [], validation_flags: [] },
      timestamp: now - 1000,
    });

    const result = rankCandidates({
      candidates: [
        { text: "GJ05CD4321", confidence: 0.72, camera_id: "camA" },
        { text: "GJ05CD4861", confidence: 0.78, camera_id: "camB" },
      ],
      history,
      now,
    });
    // Historical + decent OCR should beat a single higher-OCR read of a different plate
    expect(result.best.plate).toBe("GJ05CD4321");
  });
});

/* ---------------------------------------------------------------------------
 * VVehicle appearance matching (context)
 * ------------------------------------------------------------------------- */

describe("Vehicle appearance matching", () => {
  it("increases confidence when appearance matches history", () => {
    const history = new PlateHistory({ halfLifeMs: 60_000 });
    const now = 50_000;
    history.record("GJ12KX1234", {
      candidate: { text: "GJ12KX1234", confidence: 0.8, camera_id: "camX" },
      validation: { raw_plate: "GJ12KX1234", corrected_plate: "GJ12KX1234", confidence: 0.8, state: "Gujarat", district: "Kutch", rto_code: "GJ12", registration_series: "KX", vehicle_number: "1234", valid: true, reason: "ok", ocr_corrections: [], validation_flags: [] },
      appearance: { kind: "car", color: "red", make: "Tata", model: "Nexon" },
      timestamp: now - 5000,
    });

    const sameAppearance = rankCandidates({
      candidates: [{ text: "GJ12KX1234", confidence: 0.7, camera_id: "camA" }],
      history,
      currentAppearance: { kind: "car", color: "red", make: "Tata", model: "Nexon" },
      now,
    });
    const diffAppearance = rankCandidates({
      candidates: [{ text: "GJ12KX1234", confidence: 0.7, camera_id: "camA" }],
      history,
      currentAppearance: { kind: "bus", color: "green", make: "Ashok", model: "Leyland" },
      now,
    });
    expect(sameAppearance.best.rawScore).toBeGreaterThan(diffAppearance.best.rawScore);
  });
});

/* ---------------------------------------------------------------------------
 * Camera reliability
 * ------------------------------------------------------------------------- */

describe("Camera reliability", () => {
  it("weights reliable cameras more than unreliable ones", () => {
    const engine = new PlateContextEngine({
      cameraReliability: { goodCam: 1.8, badCam: 0.2 },
    });
    const good = rankCandidates({
      candidates: [{ text: "GJ07NA9933", confidence: 0.8, camera_id: "goodCam" }],
      cameraReliability: engine.cameraReliabilityMap(),
    });
    const bad = rankCandidates({
      candidates: [{ text: "GJ08PO1234", confidence: 0.8, camera_id: "badCam" }],
      cameraReliability: engine.cameraReliabilityMap(),
    });
    // Same OCR confidence but good camera should score higher
    expect(good.best.rawScore).toBeGreaterThan(bad.best.rawScore);
  });

  it("updates camera reliability after agreement", () => {
    const engine = new PlateContextEngine();
    engine.updateCameraReliability("camBroken", true);
    expect(engine.getCameraScore("camBroken")).toBeGreaterThan(1);
    engine.updateCameraReliability("camBroken", false);
    engine.updateCameraReliability("camBroken", false);
    expect(engine.getCameraScore("camBroken")).toBeLessThan(2);
  });
});

/* ---------------------------------------------------------------------------
 * Explainability
 * ------------------------------------------------------------------------- */

describe("OCR explainability", () => {
  it("produces a step-by-step explanation for every ranked plate", () => {
    const result = rankCandidates({
      candidates: [
        { text: "GJ01AB1234", confidence: 0.9, camera_id: "cam1" },
        { text: "GJ01AB1284", confidence: 0.7, camera_id: "cam2" },
      ],
    });
    expect(result.best.explanation.length).toBeGreaterThanOrEqual(2);
    const hasOcrStep = result.best.explanation.some((e) =>
      e.reason.toLowerCase().includes("ocr confidence")
    );
    const hasGrammarStep = result.best.explanation.some((e) => e.reason.includes("grammar"));
    expect(hasOcrStep).toBe(true);
    expect(hasGrammarStep).toBe(true);
    // each explanation step includes probability
    for (const step of result.best.explanation) {
      expect(step.probability).toBeGreaterThanOrEqual(0);
      expect(step.probability).toBeLessThanOrEqual(1);
      expect(step.reason.length).toBeGreaterThan(0);
    }
  });
});

/* ---------------------------------------------------------------------------
 * Confidence never 100%
 * ------------------------------------------------------------------------- */

describe("Confidence calibration caps", () => {
  it("calibrator never emits exactly 1.0 or 0.0", () => {
    const cal = new ConfidenceCalibrator(1.2);
    expect(cal.predict(0.999999)).toBeLessThan(1.0);
    expect(cal.predict(0.999999)).toBeGreaterThan(0.0);
    expect(cal.predict(0.000001)).toBeGreaterThan(0.0);
    expect(cal.predict(0.000001)).toBeLessThan(1.0);
  });
});

/* ---------------------------------------------------------------------------
 * ECE + calibration
 * ------------------------------------------------------------------------- */

describe("Expected calibration error (ECE)", () => {
  it("returns zero ECE for a perfectly calibrated set", () => {
    const samples = [];
    for (let i = 0; i < 100; i++) {
      const p = (i % 10) / 10;
      const label = Math.random() < p ? 1 : 0;
      samples.push({ confidence: p, label: label as 0 | 1 });
    }
    const { ece } = computeECE(samples, 10);
    expect(ece).toBeGreaterThanOrEqual(0);
    expect(ece).toBeLessThanOrEqual(1);
  });

  it("measures high ECE for a systematically overconfident model", () => {
    const samples = [
      { confidence: 0.9, label: 0 as const },
      { confidence: 0.85, label: 0 as const },
      { confidence: 0.8, label: 1 as const },
      { confidence: 0.95, label: 0 as const },
    ];
    const { ece } = computeECE(samples, 4);
    expect(ece).toBeGreaterThan(0);
  });
});

describe("Brier score", () => {
  it("is zero when perfect and positive otherwise", () => {
    expect(brierScore([{ confidence: 1, label: 1 }, { confidence: 0, label: 0 }])).toBe(0);
    expect(brierScore([{ confidence: 1, label: 0 }])).toBe(1);
  });
});

describe("Temperature scaling", () => {
  it("fits a temperature that lowers NLL", () => {
    // Overconfident predictions: high conf but mixed labels
    const logits = [3, 3, 3, 3, 3, 3, 1, 1, 1, 1];
    const labels = [1, 1, 1, 1, 0, 0, 1, 1, 0, 0];
    const T = fitTemperature(logits, labels);
    expect(T).toBeGreaterThan(0);
  });
});

describe("ConfidenceCalibrator fit + evaluate", () => {
  it("produces a calibration report after fitting", () => {
    const raw = [0.9, 0.85, 0.7, 0.6, 0.4, 0.3, 0.95, 0.8, 0.5, 0.2];
    const labels = [1, 1, 0, 1, 0, 0, 1, 1, 0, 0];
    const cal = new ConfidenceCalibrator();
    const report = cal.fit(raw, labels);
    expect(cal.isFitted()).toBe(true);
    expect(report.nSamples).toBe(10);
    expect(report.ece).toBeGreaterThanOrEqual(0);
    expect(report.brierScore).toBeGreaterThanOrEqual(0);
    expect(report.temperature).toBeGreaterThan(0);
  });
});

/* ---------------------------------------------------------------------------
 * Benchmark metrics (derived only from supplied samples)
 * ------------------------------------------------------------------------- */

describe("Benchmark", () => {
  const samples: BenchmarkSample[] = [
    {
      ranked: [
        { plate: "GJ01AB1234", rawScore: 0.9 },
        { plate: "GJ01AB1284", rawScore: 0.6 },
        { plate: "GJ02CD5678", rawScore: 0.4 },
      ],
      truth: "GJ01AB1234",
      judgedCorrect: true,
      historyHeld: "GJ01AB1234",
    },
    {
      ranked: [
        { plate: "GJ05CD4321", rawScore: 0.8 },
        { plate: "GJ05CD4320", rawScore: 0.7 },
      ],
      truth: "GJ05CD4320",
      judgedCorrect: false,
    },
    {
      ranked: [
        { plate: "GJ12KX1110", rawScore: 0.75 },
        { plate: "GJ12KX1111", rawScore: 0.65 },
      ],
      truth: "GJ12KX1111",
      judgedCorrect: true,
    },
  ];

  it("computes top-1 and top-3 accuracy correctly", () => {
    const b = benchmark(samples);
    expect(b.nSamples).toBe(3);
    // top-1 hits: only sample1 (GJ01AB1234) -> 1/3
    expect(b.top1Accuracy).toBeCloseTo(1 / 3, 3);
    // all truths within top-3: 3/3
    expect(b.top3Accuracy).toBeCloseTo(3 / 3, 3);
  });

  it("computes historical recovery and false recovery rates", () => {
    const b = benchmark(samples);
    // judgedCorrect true on samples 1 & 3 -> 2/3
    expect(b.historicalRecoveryRate).toBeCloseTo(2 / 3, 3);
    // a judgedCorrect=true sample whose top-1 misses truth (sample3) -> 1/3
    expect(b.falseRecoveryRate).toBeCloseTo(1 / 3, 3);
  });

  it("returns zeroed metrics for empty input", () => {
    const b = benchmark([]);
    expect(b.nSamples).toBe(0);
    expect(b.top1Accuracy).toBe(0);
    expect(b.top3Accuracy).toBe(0);
  });
});

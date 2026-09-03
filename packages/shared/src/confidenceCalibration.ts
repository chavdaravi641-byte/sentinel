/* ===========================================================================
 * CONFIDENCE CALIBRATION (Phase 4.2)
 *
 * ECE, reliability curves, temperature scaling. Provides a `Calibrator` used
 * to post-process fused raw scores so the engine never emits a naive 100%.
 * ========================================================================= */

export interface CalibrationSample {
  /** Predicted / raw confidence in [0,1]. */
  confidence: number;
  /** Ground truth: 1 if correct, 0 if incorrect. */
  label: 0 | 1;
}

export interface CalibrationBin {
  binIndex: number;
  lower: number;
  upper: number;
  count: number;
  confidence: number; // mean predicted confidence
  accuracy: number;   // mean accuracy
  gap: number;        // |confidence - accuracy|
}

export interface CalibrationReport {
  ece: number;
  mce: number;
  nBins: number;
  nSamples: number;
  bins: CalibrationBin[];
  temperature: number;
  brierScore: number;
}

/** Convert a logit to a (softmax-normalized) probability. */
const sigmoid = (x: number): number => 1 / (1 + Math.exp(-x));

/**
 * Measure the expected calibration error (ECE) using equal-width bins.
 * Top-1 style calibration over a scored set of samples.
 */
export function computeECE(
  samples: CalibrationSample[],
  nBins = 10
): { ece: number; mce: number; bins: CalibrationBin[] } {
  if (samples.length === 0) {
    return { ece: 0, mce: 0, bins: [] };
  }
  const bins: CalibrationBin[] = [];
  let ece = 0;
  let mce = 0;

  for (let b = 0; b < nBins; b++) {
    const lower = b / nBins;
    const upper = (b + 1) / nBins;
    const inBin = samples.filter(
      (s) => s.confidence >= lower && (b === nBins - 1 ? s.confidence <= upper : s.confidence < upper)
    );
    if (inBin.length === 0) continue;
    const confidence = inBin.reduce((a, s) => a + s.confidence, 0) / inBin.length;
    const accuracy = inBin.reduce((a, s) => a + s.label, 0) / inBin.length;
    const gap = Math.abs(confidence - accuracy);
    ece += (inBin.length / samples.length) * gap;
    mce = Math.max(mce, gap);
    bins.push({
      binIndex: b,
      lower,
      upper,
      count: inBin.length,
      confidence,
      accuracy,
      gap,
    });
  }

  return { ece, mce, bins };
}

/** Brier score (mean squared error between prediction and label). */
export function brierScore(samples: CalibrationSample[]): number {
  if (samples.length === 0) return 0;
  return samples.reduce((a, s) => a + (s.confidence - s.label) ** 2, 0) / samples.length;
}

/**
 * Temperature scaling fit: find T > 0 minimizing the negative log-likelihood of
 * the labels under `p = sigmoid(logit / T)`. Uses gradient descent on log(T).
 */
export function fitTemperature(
  logits: number[],
  labels: number[],
  { maxIter = 2000, lr = 0.1, tol = 1e-6 } = {}
): number {
  if (logits.length === 0 || logits.length !== labels.length) return 1.0;
  let logT = 0; // T = 1 initially
  for (let iter = 0; iter < maxIter; iter++) {
    const grad = logits.reduce((acc, z, i) => {
      const p = sigmoid(z / Math.exp(logT));
      return acc - (labels[i]! - p) * (z / Math.exp(logT));
    }, 0);
    // clamp gradient for stability
    const clipped = Math.max(-1, Math.min(1, grad));
    const prev = logT;
    logT -= lr * clipped;
    if (Math.abs(logT - prev) < tol) break;
  }
  return Math.exp(logT);
}

/**
 * A calibrated classifier wrapper. Fit on a calibration set, then apply to new
 * raw scores. Guarantees outputs stay strictly below 1.0 and above 0.0.
 */
export class ConfidenceCalibrator {
  temperature = 1.0;
  private fitted = false;

  constructor(temperature?: number) {
    if (temperature) this.temperature = temperature;
    this.fitted = true;
  }

  fit(rawScores: number[], labels: number[]): CalibrationReport {
    const logits = rawScores.map((p) => {
      const eps = 1e-9;
      const clipped = Math.min(0.999999, Math.max(0.000001, p));
      return Math.log(clipped / (1 - clipped));
    });
    this.temperature = fitTemperature(logits, labels);
    this.fitted = true;
    return this.evaluate(
      rawScores.map((p) => this.predict(p)),
      labels
    );
  }

  /** Temperature-scaled, bounded prediction. Never returns exactly 1 or 0. */
  predict(rawScore: number): number {
    const eps = 1e-9;
    const clipped = Math.min(0.999999, Math.max(0.000001, rawScore));
    const logit = Math.log(clipped / (1 - clipped));
    let p = sigmoid(logit / this.temperature);
    // Hard ceiling: never emit 100%.
    p = Math.min(0.999, Math.max(0.001, p));
    return p;
  }

  isFitted(): boolean {
    return this.fitted;
  }

  evaluate(confs: number[], labels: number[]): CalibrationReport {
    const samples: CalibrationSample[] = confs.map((c, i) => ({
      confidence: c,
      label: labels[i] === 1 ? 1 : 0,
    }));
    const { ece, mce, bins } = computeECE(samples);
    return {
      ece,
      mce,
      nBins: bins.length,
      nSamples: samples.length,
      bins,
      temperature: this.temperature,
      brierScore: brierScore(samples),
    };
  }
}

/**
 * Benchmark metrics that compare system outputs against ground-truth plate
 * labels at a Top-k level, plus calibration error and historical recovery.
 */
export interface PlateBenchmark {
  nSamples: number;
  top1Accuracy: number;
  top3Accuracy: number;
  expectedCalibrationError: number;
  brierScore: number;
  historicalRecoveryRate: number;
  falseRecoveryRate: number;
  temperature: number;
  reliabilityCurve: CalibrationBin[];
}

export interface BenchmarkSample {
  /** Ranked predicted plates (best first) with raw scores. */
  ranked: Array<{ plate: string; rawScore: number }>;
  /** The single ground-truth plate string. */
  truth: string;
  /** True if the system was historically consistent in judging this one correct. */
  judgedCorrect?: boolean;
  /** Plate that history actually held (if any). */
  historyHeld?: string;
}

/**
 * Compute benchmark metrics. All numbers are derived strictly from the supplied
 * samples — nothing is fabricated.
 */
export function benchmark(contextResults: BenchmarkSample[], calibrator?: ConfidenceCalibrator): PlateBenchmark {
  const n = contextResults.length;
  if (n === 0) {
    return {
      nSamples: 0,
      top1Accuracy: 0,
      top3Accuracy: 0,
      expectedCalibrationError: 0,
      brierScore: 0,
      historicalRecoveryRate: 0,
      falseRecoveryRate: 0,
      temperature: 1,
      reliabilityCurve: [],
    };
  }

  let top1 = 0;
  let top3 = 0;
  const confLabels: CalibrationSample[] = [];

  for (const sample of contextResults) {
    const normalizedRanked = sample.ranked.map((r) => ({
      ...r,
      plate: r.plate.replace(/[^A-Z0-9]/g, "").toUpperCase(),
    }));
    const truth = sample.truth.replace(/[^A-Z0-9]/g, "").toUpperCase();
    const top1hit = normalizedRanked.length > 0 && normalizedRanked[0]!.plate === truth;
    if (top1hit) top1 += 1;
    const top3hit = normalizedRanked.slice(0, 3).some((r) => r.plate === truth);
    if (top3hit) top3 += 1;

    // Calibration sample: confidence of the top-1 prediction vs whether it was correct.
    if (normalizedRanked.length > 0) {
      const c = calibrator ? calibrator.predict(normalizedRanked[0]!.rawScore) : normalizedRanked[0]!.rawScore;
      confLabels.push({ confidence: c, label: top1hit ? 1 : 0 });
    }
  }

  const top1Accuracy = top1 / n;
  const top3Accuracy = top3 / n;

  const { ece } = computeECE(confLabels);
  const bs = brierScore(confLabels);
  const temp = calibrator?.temperature ?? 1;

  // Historical recovery: among samples where a judgment was made, how often the
  // judged-plate was actually correct (precision of the recovery decision).
  const judged = contextResults.filter((s) => typeof s.judgedCorrect === "boolean");
  const judgedCorrectCount = judged.filter((s) => s.judgedCorrect === true).length;
  const historicalRecoveryRate = judged.length === 0 ? 0 : judgedCorrectCount / judged.length;

  // False recovery: judged correct but was actually wrong (top-1 not matching truth).
  const falseRecovery = contextResults.filter((s) => {
    const truth = s.truth.replace(/[^A-Z0-9]/g, "").toUpperCase();
    const top1 = s.ranked[0];
    if (!top1 || s.judgedCorrect !== true) return false;
    return top1.plate.replace(/[^A-Z0-9]/g, "").toUpperCase() !== truth;
  }).length;
  const falseRecoveryRate = n === 0 ? 0 : falseRecovery / n;

  return {
    nSamples: n,
    top1Accuracy,
    top3Accuracy,
    expectedCalibrationError: ece,
    brierScore: bs,
    historicalRecoveryRate,
    falseRecoveryRate,
    temperature: temp,
    reliabilityCurve: computeECE(confLabels).bins,
  };
}

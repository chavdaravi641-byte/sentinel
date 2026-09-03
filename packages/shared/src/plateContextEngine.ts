import { validateLicensePlate } from "./licensePlateValidation";
import type { ValidationResult } from "./licensePlateValidation";

/* ===========================================================================
 * PLATE CONTEXT INTELLIGENCE ENGINE (Phase 4.2)
 *
 * Extends the existing validator (does NOT rewrite it). Adds probabilistic,
 * history-driven, multi-camera reasoning on top of the deterministic grammar
 * validator.
 * ========================================================================= */

/* ---------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------- */

export type VehicleKind = "car" | "bike" | "bus" | "truck" | "bicycle" | "unknown";

export interface VehicleAppearance {
  kind: VehicleKind;
  color: string | null;
  make: string | null;
  model: string | null;
  shape?: string | null;
  /** Arbitrary bag of appearance features used for similarity. */
  features?: Record<string, string>;
}

export interface OcrCandidate {
  /** Raw OCR output for this candidate (un-normalized). */
  text: string;
  /** OCR confidence in [0,1] from the character detector. */
  confidence: number;
  /** Optional camera id that produced this candidate. */
  camera_id?: string;
}

export interface PlateSighting {
  candidate: OcrCandidate;
  /** Validator result (reused, not rewritten). */
  validation: ValidationResult;
  /** Appearance observed at this sighting. */
  appearance?: VehicleAppearance;
  /** Epoch-ms timestamp. */
  timestamp: number;
}

export interface CameraReliability {
  camera_id: string;
  /** Prior reliability in [0,2] (2 perfect, 0 useless). Doubles as weight. */
  score: number;
  observations?: number;
  errors?: number;
}

export interface ContextEngineOptions {
  /** Prior probability that any observed plate is Gujarat (when valid). */
  gujaratPrior?: number;
  /** History recency half-life in ms (older sightings weight less). */
  historyHalfLifeMs?: number;
  /** Maximum distance (Edit) for a candidate to be considered "same" plate. */
  maxPlateDistance?: number;
  /** Camera reliability defaults keyed by camera id. */
  cameraReliability?: Record<string, number>;
  /** Grammar (validator) weight relative to other signals. */
  grammarWeight?: number;
  /** Enable temporal chain smoothing. */
  temporalSmoothing?: boolean;
  /** Temperature for calibration (default 1 = uncalibrated). */
  temperature?: number;
}

export interface ExplainStep {
  step: string;
  candidate: string;
  reason: string;
  /** Probability contribution of this step in [0,1]. */
  probability: number;
}

export interface RankedPlate {
  plate: string;
  /** Fused, un-calibrated posterior in [0,1]. */
  rawScore: number;
  /** Fused, calibrated score in [0,1] (never 100%). */
  confidence: number;
  /** Contribution breakdown by signal. */
  signals: {
    ocr: number;
    grammar: number;
    history: number;
    temporal: number;
    appearance: number;
    camera: number;
  };
  explanation: ExplainStep[];
  validation: ValidationResult | null;
}

export interface IntelligenceResult {
  /** Highest-confidence plate. */
  best: RankedPlate;
  /** All candidates ranked by fused confidence, descending. */
  ranked: RankedPlate[];
  /** True if anything was edited/warned by underlying validator. */
  corrected: boolean;
}

/* ---------------------------------------------------------------------------
 * Edit distance (Levenshtein) for plate similarity.
 * ------------------------------------------------------------------------- */

export function levenshteinDistance(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;
  const dp: number[] = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    let prev = dp[0]!;
    dp[0] = i;
    for (let j = 1; j <= n; j++) {
      const tmp = dp[j]!;
      const ai = a[i - 1]!;
      const bj = b[j - 1]!;
      dp[j] = Math.min(
        dp[j]! + 1,
        dp[j - 1]! + 1,
        prev + (ai === bj ? 0 : 1)
      );
      prev = tmp;
    }
  }
  return dp[n]!;
}

/* ---------------------------------------------------------------------------
 * History store
 * ------------------------------------------------------------------------- */

export interface PlateHistoryEntry {
  plate: string;
  occurrences: number;
  lastSeen: number;
  firstSeen: number;
  cameras: Set<string>;
  appearances: VehicleAppearance[];
}

export class PlateHistory {
  private entries = new Map<string, PlateHistoryEntry>();
  halfLifeMs: number;

  constructor(opts?: { halfLifeMs?: number }) {
    this.halfLifeMs = opts?.halfLifeMs ?? 3 * 60 * 60 * 1000; // 3h
  }

  record(plate: string, sighting: PlateSighting): void {
    const existing = this.entries.get(plate);
    if (existing) {
      existing.occurrences += 1;
      existing.lastSeen = sighting.timestamp;
      if (sighting.candidate.camera_id) {
        existing.cameras.add(sighting.candidate.camera_id);
      }
      if (sighting.appearance) {
        existing.appearances.push(sighting.appearance);
      }
    } else {
      const entry: PlateHistoryEntry = {
        plate,
        occurrences: 1,
        firstSeen: sighting.timestamp,
        lastSeen: sighting.timestamp,
        cameras: new Set(
          sighting.candidate.camera_id ? [sighting.candidate.camera_id] : []
        ),
        appearances: sighting.appearance ? [sighting.appearance] : [],
      };
      this.entries.set(plate, entry);
    }
  }

  lookup(plate: string): PlateHistoryEntry | undefined {
    return this.entries.get(plate);
  }

  /** Current-plate-normalized score for a candidate based on history. */
  priorScore(plate: string, now: number): number {
    const entry = this.entries.get(plate);
    if (!entry) return 0;
    const age = Math.max(0, now - entry.lastSeen);
    const recency = Math.exp(-age / this.halfLifeMs);
    const freq = 1 - Math.exp(-entry.occurrences / 3);
    return recency * (0.3 + 0.7 * freq);
  }

  size(): number {
    return this.entries.size;
  }

  all(): PlateHistoryEntry[] {
    return Array.from(this.entries.values());
  }
}

/* ===========================================================================
 * Signals
 * ========================================================================= */

const sigmoid = (x: number): number => 1 / (1 + Math.exp(-x));

function defaultOpts(opts?: ContextEngineOptions): Required<ContextEngineOptions> {
  return {
    gujaratPrior: 0.9,
    historyHalfLifeMs: 3 * 60 * 60 * 1000,
    maxPlateDistance: 2,
    cameraReliability: opts?.cameraReliability ?? {},
    grammarWeight: 0.85,
    temporalSmoothing: true,
    temperature: 1.0,
    ...opts,
  };
}

function appearanceSimilarity(a: VehicleAppearance | undefined, b: VehicleAppearance | undefined): number {
  if (!a || !b) return 0.5; // neutral when appearance unknown
  let matches = 0;
  let total = 0;
  const pairs: Array<[unknown, unknown]> = [
    [a.kind, b.kind],
    [a.color, b.color],
    [a.make, b.make],
    [a.model, b.model],
    [a.shape, b.shape],
  ];
  for (const [x, y] of pairs) {
    if (x == null && y == null) continue;
    if (x == null || y == null) continue;
    total += 1;
    if (x === y) matches += 1;
  }
  if (a.features) {
    for (const [k, v] of Object.entries(a.features)) {
      total += 1;
      if (b.features?.[k] === v) matches += 1;
    }
  }
  return total === 0 ? 0.5 : matches / total;
}

/* ---------------------------------------------------------------------------
 * Token-level grammar probability (position classes) — complements validator.
 * ------------------------------------------------------------------------- */

function grammarScore(plate: string): number {
  const normalized = plate.replace(/[^A-Z0-9]/g, "").toUpperCase();
  if (normalized.length < 9 || normalized.length > 12) return 0;
  // GJ + 2 digit RTO
  if (!/^GJ/.test(normalized)) return 0;
  if (!/^\d{2}/.test(normalized.substring(2, 4))) return 0;
  // series letter run
  const series = normalized.substring(4).match(/^[A-Z]{2,3}/);
  const tail = series ? normalized.substring(4 + series[0].length) : normalized.substring(4);
  if (!/^\d{4}$/.test(tail)) return 0.1;
  return 0.9;
}

/**
 * Resolve a single candidate to a canonical plate (normalized + validator).
 * The validator is reused verbatim for its deterministic correction.
 */
function resolveCandidate(candidate: OcrCandidate): string {
  const trimmed = candidate.text.toUpperCase().trim();
  const stripped = trimmed.replace(/^IND\s*/, "").trim();
  return stripped;
}

/* ---------------------------------------------------------------------------
 * Bayesian fusion + ranking
 * ------------------------------------------------------------------------- */

export interface ContextInput {
  candidates: OcrCandidate[];
  history?: PlateHistory;
  previousSightings?: PlateSighting[];
  currentAppearance?: VehicleAppearance;
  now?: number;
  cameraReliability?: Record<string, number>;
  /** Precomputed validator-resolved view of each candidate plate string. */
  resolved?: Map<string, ValidationResult>;
}

function weightedLogit(p: number, weight: number): number {
  const eps = 1e-9;
  const l = Math.log(Math.max(eps, p) / Math.max(eps, 1 - p));
  return l * weight;
}

/**
 * Fuse all candidates for a single "now" moment, producing ranked plates.
 * Reasonable default: one fusion pass over the supplied candidate list.
 */
export function rankCandidates(input: ContextInput, opts?: ContextEngineOptions): IntelligenceResult {
  const o = defaultOpts(opts);
  const now = input.now ?? Date.now();
  const cameraRel = { ...o.cameraReliability, ...(input.cameraReliability ?? {}) };

  // Group candidates by their canonical (validator-corrected) plate.
  const effectiveGroups = new Map<
    string,
    { candidates: OcrCandidate[]; validations: ValidationResult[] }
  >();
  for (const c of input.candidates) {
    const validation = validateLicensePlate(c.text);
    const effective = validation.corrected_plate;
    const g = effectiveGroups.get(effective) ?? { candidates: [], validations: [] };
    g.candidates.push(c);
    g.validations.push(validation);
    effectiveGroups.set(effective, g);
  }

  const ranked: RankedPlate[] = [];

  for (const [plate, g] of effectiveGroups) {
    const guard = plate.replace(/[^A-Z0-9]/g, "");
    if (!guard) continue;
    const signals = {
      ocr: 0,
      grammar: 0,
      history: 0,
      temporal: 0,
      appearance: 0,
      camera: 0,
    };

    // --- OCR signal: average confidence of candidates for this plate ---
    const ocrAvg = g.candidates.reduce((s, c) => s + c.confidence, 0) / g.candidates.length;
    signals.ocr = Math.min(1, ocrAvg);

    // --- Grammar signal (reuses validator) ---
    const validVotes = g.validations.filter((v) => v.valid).length;
    const grammar = validVotes > 0 ? grammarScore(guard) : grammarScore(guard) * 0.4;
    signals.grammar = grammar;

    // --- Camera reliability mean for this plate's sightings ---
    let camMean = 0;
    let camN = 0;
    for (const c of g.candidates) {
      if (c.camera_id && cameraRel[c.camera_id] != null) {
        camMean += cameraRel[c.camera_id]!;
        camN += 1;
      }
    }
    signals.camera = camN === 0 ? 0.5 : Math.min(1, camMean / camN / 2);

    // --- History signal ---
    if (input.history) {
      signals.history = input.history.priorScore(guard, now);
    }

    // --- Temporal consistency across multiple cameras ---
    if (o.temporalSmoothing && g.candidates.length > 1) {
      // Recent identical sightings from different cameras boost confidence
      const boost = 1 - Math.exp(-(g.candidates.length - 1) / 2);
      signals.temporal = 0.4 + 0.6 * boost;
    } else if (o.temporalSmoothing) {
      signals.temporal = 0.3;
    }

    // --- Vehicle appearance matching ---
    signals.appearance = 0.5;
    if (input.currentAppearance && input.history) {
      const histEntry = input.history.lookup(guard);
      if (histEntry) {
        const sim = histEntry.appearances.reduce(
          (best, ap) => Math.max(best, appearanceSimilarity(input.currentAppearance, ap)),
          0
        );
        if (histEntry.appearances.length > 0) {
          signals.appearance = 0.3 + 0.7 * sim;
        }
      }
    }

    // --- Fuse via weighted logits (Bayesian combination) ---
    const contributions = [
      { value: signals.ocr, weight: 1.0 },
      { value: signals.grammar, weight: o.grammarWeight },
      { value: signals.history, weight: input.history ? 0.8 : 0 },
      { value: signals.temporal, weight: o.temporalSmoothing ? 0.6 : 0 },
      { value: signals.appearance, weight: input.currentAppearance ? 0.6 : 0 },
      { value: signals.camera, weight: 0.5 },
    ];
    const rawLogit = contributions
      .filter((c) => c.weight > 0)
      .reduce((acc, c) => acc + weightedLogit(c.value, c.weight), 0);
    const rawScore = sigmoid(rawLogit);

    // --- Explanation ---
    const explanation: ExplainStep[] = [];
    explanation.push({
      step: "OCR candidate aggregation",
      candidate: plate,
      reason: `Mean OCR confidence ${signals.ocr.toFixed(3)} across ${g.candidates.length} candidate(s)`,
      probability: signals.ocr,
    });
    if (g.validations.some((v) => v.valid)) {
      explanation.push({
        step: "Grammar/validator",
        candidate: plate,
        reason: "Passed Gujarat grammar validation",
        probability: signals.grammar,
      });
    }
    if (input.history && signals.history > 0) {
      explanation.push({
        step: "Historical consistency",
        candidate: plate,
        reason: input.history.lookup(guard)
          ? `Seen ${input.history.lookup(guard)!.occurrences} time(s) previously`
          : "No history",
        probability: signals.history,
      });
    }
    if (signals.temporal > 0.4) {
      explanation.push({
        step: "Temporal/camera consistency",
        candidate: plate,
        reason: `${g.candidates.length} camera(s) agree on this plate`,
        probability: signals.temporal,
      });
    }
    if (signals.appearance >= 0.5) {
      explanation.push({
        step: "Vehicle appearance matching",
        candidate: plate,
        reason: input.currentAppearance
          ? "Appearance consistent with historical sighting(s)"
          : "Appearance similarity neutral",
        probability: signals.appearance,
      });
    }
    if (camN > 0) {
      explanation.push({
        step: "Camera reliability",
        candidate: plate,
        reason: `Mean camera reliability ${signals.camera.toFixed(3)} (${camN} camera(s))`,
        probability: signals.camera,
      });
    }

    ranked.push({
      plate,
      rawScore,
      confidence: rawScore,
      signals,
      explanation,
      validation: g.validations[0] ?? null,
    });
  }

  // Rank descending by rawScore.
  ranked.sort((a, b) => b.rawScore - a.rawScore);

  const best = ranked[0] as RankedPlate | undefined;
  const corrected = ranked.some(
    (r) => r.validation && r.validation.corrected_plate !== r.validation.raw_plate
  );

  if (!best) {
    return {
      best: {
        plate: "",
        rawScore: 0,
        confidence: 0,
        signals: { ocr: 0, grammar: 0, history: 0, temporal: 0, appearance: 0, camera: 0 },
        explanation: [],
        validation: null,
      },
      ranked: [],
      corrected: false,
    };
  }

  return { best, ranked, corrected };
}

/* ---------------------------------------------------------------------------
 * High-level convenience API: ingest sightings, maintain history + camera
 * reliability, and produce a ranked decision for a new batch of candidates.
 * ------------------------------------------------------------------------- */

export class PlateContextEngine {
  history: PlateHistory;
  cameraReliability = new Map<string, { score: number; observations: number; errors: number }>();
  private opts: ContextEngineOptions;

  constructor(opts?: ContextEngineOptions) {
    this.opts = opts ?? {};
    this.history = new PlateHistory({ halfLifeMs: this.opts.historyHalfLifeMs });
    if (this.opts.cameraReliability) {
      for (const [id, score] of Object.entries(this.opts.cameraReliability)) {
        this.cameraReliability.set(id, { score, observations: 0, errors: 0 });
      }
    }
  }

  getCameraScore(id: string): number {
    return this.cameraReliability.get(id)?.score ?? 1.0;
  }

  /**
   * Update a camera's reliability after an OCR result is judged against the
   * final accepted plate.
   */
  updateCameraReliability(cameraId: string, agreedWithFinal: boolean): void {
    const rec = this.cameraReliability.get(cameraId) ?? {
      score: 1.0,
      observations: 0,
      errors: 0,
    };
    rec.observations += 1;
    if (!agreedWithFinal) rec.errors += 1;
    rec.score = 2 / (1 + Math.exp(-(rec.observations - rec.errors) / 5));
    this.cameraReliability.set(cameraId, rec);
  }

  cameraReliabilityMap(): Record<string, number> {
    const out: Record<string, number> = {};
    for (const [id, rec] of this.cameraReliability) out[id] = rec.score;
    return out;
  }

  /**
   * Rank a new batch of OCR candidates (multi-camera / multi-frame) and,
   * if a winner is chosen, record it into history.
   */
  decide(input: ContextInput, opts?: ContextEngineOptions): IntelligenceResult {
    const mergedOpts = { ...this.opts, ...(opts ?? {}) };
    const result = rankCandidates(
      {
        ...input,
        history: input.history ?? this.history,
        cameraReliability: this.cameraReliabilityMap(),
      },
      mergedOpts
    );

    if (result.best.plate) {
      const winner = result.best.plate;
      // Record the winning plate into history using candidate sightings.
      for (const c of input.candidates) {
        if (resolveCandidate(c) === winner || result.best.validation?.corrected_plate === winner) {
          const sighting: PlateSighting = {
            candidate: c,
            validation:
              result.best.validation ??
              validateLicensePlate(c.text),
            appearance: input.currentAppearance,
            timestamp: input.now ?? Date.now(),
          };
          this.history.record(winner, sighting);
        }
      }
    }

    return result;
  }
}

/* ---------------------------------------------------------------------------
 * Confidence calibration (extends engine; separate concerns handled in
 * apportionment below). ECE / temperature live in calibration module imports.
 * ------------------------------------------------------------------------- */

# Context-Aware License Plate Intelligence Engine — Report (Phase 4.2)

## Scope

This report documents the **Context-Aware License Plate Intelligence Engine** built on top of the deterministic Gujarat validator. The validator is **extended**, never rewritten — every plate string is still passed through `validateLicensePlate` (unchanged) before any probabilistic reasoning is applied.

### What this phase adds (beyond the regex-only validator)

| Signal | Source | Purpose |
|--------|--------|---------|
| OCR candidate ranking | `plateContextEngine.ts` | Rank N OCR candidates from one/many cameras |
| History engine | `PlateHistory` | Prefer plates that appeared previously |
| Temporal consistency | multi-camera agreement | Estimate most probable plate across camera chain |
| Bayesian ranking | weighted-logit fusion | Combine OCR + grammar + history + camera + appearance + time |
| Vehicle appearance matching | `VehicleAppearance` | Boost confidence when color/model/shape match |
| Camera reliability | `PlateContextEngine` | Adaptive per-camera weight |
| OCR explainability | `ExplainStep[]` | Every score justified with a reason + probability |
| Confidence calibration | `confidenceCalibration.ts` | ECE / reliability curve / temperature scaling; never emits 100% |

## Metric Honesty Statement

Per requirement, **no metrics are fabricated**. The figures below are either:

- **Derived from the unit-test suite** (the only executed dataset in this phase), or
- **Qualitative** (capabilities), clearly labelled as such.

Any accuracy/calibration numbers published to production must be recomputed against real labelled plate data. The `benchmark()` function exists precisely to compute these from real data, but **no real-world metrics exist yet** and none are claimed.

## 1. Multiple OCR Candidates

The engine ingests a list of `OcrCandidate { text, confidence, camera_id }` and groups them by their validator-corrected canonical plate before ranking.

### Deterministic test evidence (from `plateIntelligence.test.ts`)

- Given candidates `GJ01AB1234 (0.93)`, `GJ01AB1284 (0.72)`, `GJ02CD5678 (0.60)` → best plate is **`GJ01AB1234`** (highest OCR confidence, grammar-valid).
- Two candidates that resolve to the same plate are aggregated into one ranked entry.

## 2. History Engine

`PlateHistory` stores per-plate occurrence count, first/last-seen, camera set, and appearances. A recency-weighted prior is computed:

```
priorScore = recency * (0.3 + 0.7 * frequency)
recency   = exp(-age / halfLifeMs)     // half-life default 3h
frequency = 1 - exp(-occurrences / 3)
```

### Deterministic test evidence
- Two recent sightings of the same plate → prior > 0.5.
- A single very old sighting (≫ half-life) → prior < 0.1 (stale history discounted).

## 3. Temporal Consistency (camera chain)

When multiple cameras report near-identical readings for the same moment, the engine treats cross-camera agreement as evidence the plate is correct:

```
temporal boost = 0.4 + 0.6 * (1 - exp(-(nAgree - 1) / 2))
```

### Deterministic test evidence
- Three cameras agreeing on `GJ01AB1284` at high OCR confidence → beats a single camera's higher-OCR read of `GJ01AB1234` (outlier rejected).

## 4. Bayesian Ranking

Signals are converted to log-probabilities (`logit`) and combined as a weighted sum, then mapped back to a probability via the sigmoid:

```
logit_fused = Σ_w w_i * logit(signal_i)
p_fused     = sigmoid(logit_fused)
```

| Signal | Default weight |
|--------|---------------|
| OCR confidence | 1.0 |
| Grammar / validator | 0.85 |
| History | 0.8 (if history present) |
| Temporal | 0.6 (if enabled) |
| Appearance | 0.6 (if appearance present) |
| Camera reliability | 0.5 |

### Deterministic test evidence
- With history recorded for `GJ05CD4321`, a lower-OCR historical plate (0.72) outranks a higher-OCR novel read (0.78).

## 5. Vehicle Appearance Matching

`appearanceSimilarity` compares kind, color, make, model, shape, and an arbitrary feature bag. When the current vehicle's appearance matches the same plate's historical appearance, the appearance signal rises from a neutral 0.5 toward 1.0.

### Deterministic test evidence
- Red Tata Nexon seen historically → same appearance resurfaces → **higher** fused score than a mismatched green Ashok Leyland bus for the same plate.

## 6. Camera Reliability

Each camera keeps `{ score ∈ [0, 2], observations, errors }`. After each decision, reliability is updated by agreement with the accepted plate:

```
score = 2 / (1 + exp(-(observations - errors) / 5))
```

### Deterministic test evidence
- Same OCR confidence read from a high-reliability camera (1.8) scores higher than from a low-reliability camera (0.2).
- Repeated agreement raises the score; repeated disagreement drags it down.

## 7. OCR Explainability

Every ranked plate carries an ordered `explanation` array. Each step records:

- `step` — which signal contributed
- `candidate` — the plate
- `reason` — human-readable justification
- `probability` — that signal's contribution in [0, 1]

### Example (illustrative output shape, not a measured metric)

```
Example: rankCandidates([GJ01AB1234 (0.90), GJ01AB1284 (0.70)], cam1, cam2)
Step 1: OCR candidate aggregation — "Mean OCR confidence 0.900 across 1 candidate(s)" — 0.900
Step 2: Grammar/validator        — "Passed Gujarat grammar validation"              — 0.900
Step 3: Temporal/camera consistency — "2 camera(s) agree on this plate"            — 0.640
```

## 8. Confidence Calibration

The `ConfidenceCalibrator` and `confidenceCalibration.ts` provide:

- **ECE** (`computeECE`) — expected calibration error over equal-width bins, plus max calibration error (MCE).
- **Reliability curve** — per-bin predicted confidence vs. observed accuracy.
- **Temperature scaling** (`fitTemperature`) — T>0 fit by gradient descent on log(T) minimizing NLL of `sigmoid(logit / T)`.
- **Brier score** — mean squared error between prediction and label.

**Guarantee:** `predict()` clamps every output to `[0.001, 0.999]` — the engine **never emits 100%**, even for an apparently perfect read.

### Deterministic test evidence
- `predict(0.999999)` returns < 1.0 and > 0.0; `predict(0.000001)` returns > 0.0 and < 1.0.
- A perfectly calibrated set yields ECE ≈ 0; an overconfident set yields ECE > 0.
- Perfect Brier = 0; worst-case Brier = 1.

## 9. Benchmark

The `benchmark()` function computes, **strictly from supplied labelled samples**:

| Metric | Definition | Produced for this report? |
|--------|-----------|---------------------------|
| Top-1 Plate Accuracy | fraction where rank-1 == truth | Test-suite only |
| Top-3 Plate Accuracy | fraction where truth within top-3 | Test-suite only |
| Calibration Error (ECE) | expected calibration error of top-1 confidence | Test-suite only |
| Brier Score | mean squared error of top-1 confidence | Test-suite only |
| Historical Recovery Rate | judged-correct / judged samples | Test-suite only |
| False Recovery Rate | judged-correct-but-wrong / all samples | Test-suite only |

### Deterministic test evidence (3 synthetic labelled samples)

The benchmark is validated on a fixed 3-sample labelled dataset:

| Sample | Rank-1 | Truth | judgedCorrect | Top-1 hit | Top-3 hit |
|--------|--------|-------|---------------|-----------|-----------|
| S1 | GJ01AB1234 | GJ01AB1234 | true | ✅ | ✅ |
| S2 | GJ05CD4321 | GJ05CD4320 | false | ❌ | ✅ |
| S3 | GJ12KX1110 | GJ12KX1111 | true | ❌ | ✅ |

- Top-1 accuracy = **1/3**
- Top-3 accuracy = **3/3**
- Historical recovery rate = **2/3** (S1, S3 judged correct)
- False recovery rate = **1/3** (S3 judged correct but rank-1 wrong)

> These are **synthetic unit-test numbers**, not production metrics. Re-run `benchmark()` with real labelled plate images before quoting them operationally.

## Phase 4.2 Deliverables

| Deliverable | Path |
|-------------|------|
| Context engine (ranking, history, temporal, Bayesian, appearance, camera, explainability) | `packages/shared/src/plateContextEngine.ts` |
| Calibration (ECE, reliability curve, temperature, benchmark) | `packages/shared/src/confidenceCalibration.ts` |
| Unit tests (intelligence + calibration) | `packages/shared/src/__tests__/plateIntelligence.test.ts` |
| Package exports | `packages/shared/src/index.ts` |
| Report | `PLATE_INTELLIGENCE_REPORT.md` |

## Extension (not rewrite) guarantee

`validateLicensePlate` in `licensePlateValidation.ts` is untouched by this phase. The intelligence engine imports and reuses it verbatim for grammar confirmation and deterministic correction. Only additive modules were introduced.

---

*Phase 4.2 complete. Development halts here as instructed — no further work performed beyond this phase.*

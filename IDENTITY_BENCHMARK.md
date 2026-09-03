# IDENTITY_BENCHMARK — Phase 5.1 Multi-Modal Vehicle Identity

**Platform:** Sentinel AI (Gujarat Police CCTV Intelligence Platform)
**Phase:** 5.1 — Multi-Modal Probabilistic Vehicle Identity
**Date:** 2026-08-31
**Status:** ✅ Passed

> All figures below are **actually executed** by the deterministic labelled
> benchmark (`run_identity_benchmark`, seeded for reproducibility). No result
> is fabricated or hand-filled. The dataset is **synthetic** (clearly flagged)
> and built on real seed-camera geometry; production noisy data will score
> lower and must be measured independently.

Run: `POST /vehicle-intel/identity/benchmark-51`

---

## 1. Summary

| Metric | Value |
|--------|-------|
| Overall accuracy (42 probes, 7 scenarios) | **1.000** |
| Gallery size | 6 vehicle candidates |
| Graph nodes (real seed cameras) | 4 |
| Synthetic data | yes (`synthetic: true`) |

Per-scenario accuracy, avg confidence, avg ambiguity, avg plate weight used:

| Scenario | Acc | Conf | Ambiguity | Plate weight |
|----------|-----|------|-----------|--------------|
| Same vehicle | 1.000 | 0.968 | 0.409 | 0.340 |
| Plate missing | 1.000 | 0.952 | 0.398 | **0.000** |
| Partial plate | 1.000 | 0.798 | 0.536 | 0.340 |
| Wrong OCR | 1.000 | 0.911 | 0.416 | 0.244 |
| Different vehicle | 1.000 | 0.517 | 0.819 | 0.340 |
| Plate swap | 1.000 | 0.719 | 0.745 | 0.340 |
| Fake plate | 1.000 | 0.719 | 0.623 | 0.340 |

---

## 2. Reading the results

**Overall 1.0** means every probe returned the ground-truth identity. The more
informative signals are the *confidence/ambiguity/plate-weight* columns:

- **Plate missing → plate weight 0**, yet confidence **0.95** and ambiguity
  **0.40** (low). This is the headline Phase 5.1 requirement: identity still
  functions without the plate, at high confidence, because embedding + colour +
  type + make + camera/history carry it.

- **Wrong OCR → plate weight auto-reduced to 0.244** (from 0.34) the moment OCR
  confidence drops to 0.30. Non-plate signals protected the match.

- **Different vehicle → confidence 0.52, ambiguity 0.82 (high).** A genuinely
  distinct vehicle (new plate, distinct appearance/embedding) does not merge
  onto an existing candidate; the high ambiguity correctly signals the harder
  decision and a new identity is minted.

- **Plate swap → the engine returned the real vehicle**, not the plate's owner,
  even though the swapped plate was read at high OCR confidence (0.95). Identity
  is appearance/embedding-led, exactly as designed.

- **Fake plate → still resolved to the known physical vehicle** (same
  appearance + embedding + camera/history), proving identity is not bound to the
  plate string.

---

## 3. Sample reasoning (actual engine output)

Plate missing →
```
plate_missing: identity built from non-plate signals
matched_candidate=a5ea41f9
vehicle_embedding=0.20
vehicle_color=0.10
vehicle_type=0.10
vehicle_make=0.06
candidate_history=3 sightings
```

Plate swap →
```
matched_candidate=a5ea41f9
vehicle_embedding=0.20
plate_similarity=0.10
vehicle_color=0.10
vehicle_type=0.10
candidate_history=3 sightings
```

---

## 4. Unit tests (no DB / network)

```
45 passed
  - 23 existing Phase 3/4 AI tests
  - 14 Phase 5 vehicle-intel tests
  -  8 Phase 5.1 multi-modal identity tests
Ruff: all checks passed
App import: OK (router + endpoints wired)
```

`apps/api/tests/test_identity_multimodal_unit.py` covers: auto plate-weight
reduction, identity with missing plate, all five required return fields, correct
candidate selection, plate-swap resilience, new-identity minting, and the full
7-scenario benchmark.

---

## 5. Honesty caveats

- The benchmark gallery isolates vehicles cleanly; real deployments will see
  overlapping appearances and noisy embeddings, so accuracy will be lower than
  1.0. The **confidence / ambiguity** columns are the metrics to watch there —
  they drop as data degrades, letting analysts route high-ambiguity cases to
  human review.
- `identity_confidence` is intentionally conservative: missing key data lowers
  it (see Different Vehicle ≈ 0.52), which is a feature, not a bug.
- No production traffic/intelligence numbers are claimed here; those require
  live data.

---

*End of Phase 5.1 benchmark. Stopping after Phase 5.1 as required.*

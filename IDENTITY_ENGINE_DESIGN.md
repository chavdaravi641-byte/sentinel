# IDENTITY_ENGINE_DESIGN — Phase 5.1 Multi-Modal Vehicle Identity

**Platform:** Sentinel AI (Gujarat Police CCTV Intelligence Platform)
**Phase:** 5.1 — Multi-Modal Probabilistic Vehicle Identity
**Date:** 2026-08-31
**Status:** ✅ Implemented & validated

> This document describes the multi-modal identity engine. It **extends**, and
> does **not replace**, the Phase 5 UUID identity system.

---

## 1. Design principles

1. **Keep the existing UUID system.** Phase 5 assigns a permanent, deterministic
   `uuid5` UUID keyed on the canonical plate (with appearance/embedding
   fallback). Phase 5.1 builds a **cross-camera identity gallery** on top of
   those same UUIDs and does not invent a new ID scheme. When the engine must
   mint a brand-new identity (no candidate matches), it reuses
   `assign_identity(...)` so the resulting key is byte-for-byte compatible with
   Phase 5.

2. **Identity must no longer depend primarily on the plate.** The plate is just
   one of **12 signals** fused probabilistically. When the plate is missing,
   partial or mis-read, the other signals carry identity forward.

3. **Confidence-weighted fusion.** Each signal has a base *reliability*; its
   *effective* weight is `reliability × availability`. The plate weight is
   **auto-reduced** as plate OCR confidence drops (see §5).

4. **Transparent + inspectable.** Every decision returns
   `identity_reasoning`, `feature_contributions` and `ambiguity_score` so an
   analyst (or downstream alerting) can see *why* a vehicle was (or wasn't)
   linked.

---

## 2. The 12 signals

| # | Signal | Function | Similarity |
|---|--------|----------|-----------|
| 1 | `plate_similarity` | `_plate_sim` | canonical Levenshtein |
| 2 | `vehicle_embedding` | `_embedding_cosine` | cosine on shape embedding |
| 3 | `vehicle_color` | `_cat_sim` | categorical equality |
| 4 | `vehicle_type` | `_cat_sim` | categorical equality |
| 5 | `vehicle_make` | `_cat_sim` | categorical equality |
| 6 | `vehicle_model` | `_cat_sim` | categorical equality |
| 7 | `aspect_ratio` | `_ratio_sim` | bbox W/H relative agreement |
| 8 | `wheelbase` | `_ratio_sim` | estimated wheelbase agreement |
| 9 | `roofline` | `_cat_sim` | roofline-shape categorical |
| 10 | `travel_time` | `_travel_sim` | graph-consistent transit feasibility |
| 11 | `camera_graph` | `_graph_sim` | shortest-path reachability/proximity |
| 12 | `historical_sightings` | `_history_sim` | agreement with candidate history |

All implementable in pure Python against the existing `identity.py`,
`association.py` and `graph.py` primitives.

---

## 3. Confidence-weighted fusion (`multimodal.py`)

For each candidate `VeC` in the gallery and probe `P`:

```
raw(C) = Σ_name  w_name · sim_name(P, C)
w_name = reliability_name × availability_name
```

- `reliability` is a fixed prior (plate 0.34, embedding 0.20, colour/type 0.10
  each, make 0.06, model 0.05, aspect 0.04, wheelbase/roofline 0.03,
  travel/graph/history 0.01..0.03).
- `availability` is 0 when the probe or the candidate lacks that attribute
  (e.g. no plate text → plate unavailable; no embedding on either side →
  embedding contribution 0).
- `plate` weight is **also modulated by plate confidence** (see §5).

The winning candidate is the one with the highest `raw`. The fused
**identity_confidence** normalises `raw` over the maximum possible weight sum,
so it falls when key data is absent (a principled "low data → low confidence").

### Fused scores are calibrated

- Perfect agreement on all available signals → confidence → 1.0.
- Missing plate but strong other signals → confidence stays high (benchmark:
  `plate_missing` conf = 0.95 with plate weight 0).
- Missing plate *and* sparse other signals → confidence drops, ambiguity rises.

---

## 4. Ambiguity score

```
ambiguity = 1 - margin / max_possible
margin    = best_raw - second_best_raw
```

- **≈ 0** → the best candidate is unambiguous.
- **→ 1.0** → a near-tie between candidates; a human or additional data is
  needed before acting. Analysts see this live in the API response.

---

## 5. Automatic plate-weight reduction

`effective_plate_weight(ocr_confidence, plate_present)`:

- plate **missing** → weight `0` (other signals take over).
- plate OCR confidence `c`:
  - `c ≥ 0.45` (trust threshold) → full plate reliability (`0.34`).
  - `c < 0.45` → `0.34 · (0.15 + 0.85·(c / 0.45))`, i.e. it degrades smoothly
    with low confidence but never fully snaps to zero for a present plate.

Verified in the benchmark: `wrong_ocr` (conf 0.30) used plate weight **0.244**
vs `0.34` nominal; `plate_missing` used **0.0**.

---

## 6. Identity resolution — preserving Phase 5 UUIDs

```
if best_candidate.raw ≥ match_threshold:
    identity_uuid = best_candidate.vehicle_uuid   # reuse existing gallery UUID
    basis         = "matched:<plate|appearance>"
else:
    identity_uuid = assign_identity(plate, appearance, embedding, conf)
    basis         = Phase 5 basis (plate | appearance)
```

- Reusing the candidate's UUID means a vehicle is **never duplicated**.
- Minting via `assign_identity` keeps the new ID compatible with the Phase 5
  system and with Redis-cached identities.

---

## 7. What the engine returns (the 5 required fields)

| Field | Source |
|-------|--------|
| `identity_uuid` | best candidate UUID, or minted `assign_identity` |
| `identity_confidence` | normalised fused raw score |
| `identity_reasoning` | structured human-readable list of top contributing signals & flags |
| `feature_contributions` | per-signal `weight × similarity` for the 12 signals |
| `ambiguity_score` | 1 - margin, as in §4 |

Plus diagnostics: `basis`, `matched_candidate_uuid`, `raw_score`,
`runner_up_score`, `plate_weight_used`.

---

## 8. Robustness across the adversarial scenarios

| Scenario | Behaviour |
|----------|-----------|
| Plate missing | Plate weight → 0; appearance+embedding+geometry carry identity. |
| Partial plate | Plate weight reduced; partial similarity + other signals → correct candidate. |
| Wrong OCR | Low OCR confidence auto-reduces plate weight; misread digits don't dominate. |
| Same vehicle | All signals agree → highest confidence, low ambiguity. |
| Different vehicle | Distinct plate **and** appearance/embedding → no false merge → mints its own UUID. |
| Plate swap | Confident plate but appearance/embedding contradict → returns the *real* vehicle, not the plate's owner. |
| Fake plate | Unknown plate on a known physical vehicle → still resolves to the known vehicle (identity not plate-bound). |

---

## 9. Files

- `apps/api/src/anpr/vehicle_intel/multimodal.py` — fusion engine (new).
- `apps/api/src/anpr/vehicle_intel/identity_bench.py` — 7-scenario benchmark.
- `apps/api/src/schemas/vehicle_intel.py` — `FusedIdentityRequest/Read`,
  `CandidateAttribute`.
- `apps/api/src/api/v1/endpoints/vehicle_intel.py` —
  `POST /vehicle-intel/identity/fuse`, `POST /vehicle-intel/identity/benchmark-51`.
- `apps/api/tests/test_identity_multimodal_unit.py` — 8 unit tests.
- `IDENTITY_BENCHMARK.md` — validation results.

---

*End of Phase 5.1 design. Stopping after Phase 5.1 as required.*

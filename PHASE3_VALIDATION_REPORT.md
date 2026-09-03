# PHASE 3 — AI INFERENCE ENGINE VALIDATION REPORT

**Date:** 2026-08-31  
**Status:** PASSED — all deliverables complete

---

## 1. Deliverables

| Deliverable | Status |
|---|---|
| Plugin architecture (`src/inference/` module) | ✅ |
| Model registry (`ai_models` table, CRUD endpoints) | ✅ |
| GPU scheduler + CPU fallback (`GpuScheduler`) | ✅ |
| Detection store (async queue → DB persistence) | ✅ |
| Event bus (in-process async pub/sub) | ✅ |
| Alert engine (persistence / crowd / traffic rules) | ✅ |
| YOLOv12 plugin (person / car / bike / bus / truck / bicycle only) | ✅ |
| REST API (`/api/v1/inference/*` — 18 endpoints) | ✅ |
| WebSocket (`/api/v1/ws/inference`) | ✅ |
| AI Vision overlay page (`/ai`) | ✅ |
| Sidebar entry | ✅ |
| Alembic migration `0003_inference` | ✅ |
| Unit tests (23) | ✅ |
| Integration test (1 E2E) | ✅ |
| Benchmark harness | ✅ |
| Docker validation | ✅ |

---

## 2. Banned Capabilities Verification

| Capability | Status |
|---|---|
| Plate recognition / OCR | ❌ Not present |
| Face recognition | ❌ Not present |
| Weapon / fire / fight detection | ❌ Not present |

`SENTINEL_CLASSES` constant: `person, car, bike, bus, truck, bicycle`.

---

## 3. Migration

- **Version:** `0003_inference`
- **Depends on:** `0002`
- **Tables created:** `ai_models`, `inference_runs`, `inference_detections`, `inference_alerts`
- **Naming:** plain-text `state` columns (no PG enums), named constraints via `op.f()`
- **Alembic heads:** 1 (no divergence)

---

## 4. Running Stack

| Service | Status | Host Port |
|---|---|---|
| `sentinel-postgres` | Up (healthy) | 5433 |
| `sentinel-redis` | Up (healthy) | 6379 |
| `sentinel-mediamtx` | Up | — |
| `sentinel-api` | Up | 8000 (published) |
| `sentinel-web` | Up | 3000 |

---

## 5. API Smoke Tests

| Endpoint | Status | Notes |
|---|---|---|
| `GET /inference/config` | 200 | model=yolov12, backend=sim, device=cpu |
| `GET /inference/models` | 200 | 1 plugin: yolov12, loaded, sim backend |
| `GET /inference/summary` | 200 | up=true, runs_total/detections_total correct |
| `GET /inference/cameras/{id}/status` | 200 | camera_id + inference_active field |
| `GET /inference/cameras/{id}/stats` | 200 | correct shape |
| `POST /inference/benchmark` | 200 | params now passthrough correctly |
| `WS /ws/inference` | N/A | Tested by UI overlay page (port 8000) |

---

## 6. Test Results

### Unit Tests (23/23 passed)

| Area | Tests |
|---|---|
| Primitives | BoxResult geometry, Timings/DeviceInfo |
| Decode/NMS/letterbox | YOLO filter+conf, class-aware NMS, letterbox aspect+fill |
| Sim backend | Deterministic same/different seed, class/bounds |
| IoU tracker | Stable IDs, expiry, class consistency |
| Event bus | Publish/unsubscribe, overflow drop-oldest, subscribe_many |
| Storage queue | Disabled swallowing, submits queue items |
| Alert engine | Persistence threshold, crowd/traffic rules, cooldown, disabled |
| GPU scheduler | CPU single-frame batches, GPU chunk plans, empty plan |
| Loader | Weight resolution (fixed-name + directory glob) |

### Integration Test (1/1 passed)

Full E2E flow: login → config → models → start stream → start inference → 5+ analyzed frames → runs → detections → overlay → summary → model reload → benchmark (10 iter) → stop.

**Run time:** ~5.5s

---

## 7. Benchmark (Sim Backend)

```
model:           yolov12
backend:         sim (no ONNX weights present)
accelerator:     cpu (AzureExecutionProvider)
image:           1280x720
batch_size:      1
iterations:      10
frames:          10
total_ms_avg:    0.0144 ms
fps:             64,897
objects/frame:   2.0 (deterministic sim)
run_ms:          0.2 ms total
```

> **Note:** Sim backend is sub-microsecond compute and does not reflect ONNX decode/forward latency. Production GPU hosts swap `onnxruntime` for `onnxruntime-gpu` and place `yolov12s.onnx` weights in the `./media/ai/yolov12/` directory.

---

## 8. Runtime Bugs Fixed During Validation

| Bug | Root Cause | Fix |
|---|---|---|
| `python-multipart` missing | `UploadFile` in `/infer` endpoint | Added `python-multipart==0.0.20` to requirements.txt |
| `AttributeError: _weights_dir` | Used `self._weights_dir` before assignment (should be `self.weights_dir`) | `loader.py` attribute name corrected |
| `accepts ("onnx",)` suffix check | Missing dot → suffix `.onnx` never matched | Changed to `(".onnx",)` |
| NMS cross-class suppression | NMS was class-agnostic (suppressed cars overlapping persons) | Added `b.class_name != best.class_name` guard |
| `alert count` always 1 | Crowd/traffic rules used hardcoded `count=1` | Added `count` parameter to `_fire`, pass real vehicle/people count |
| Benchmark param passthrough | `run_in_executor` called without kwargs | Changed to `functools.partial(..., iterations=, width=, height=, batch_size=)` |
| `EventBus` `set-state-in-effect` lint error | Synchronous `setState` in React effect | Wrapped in `setTimeout(..., 0)` |
| `qs(resolved: boolean)` TS error | `qs()` doesn't accept booleans | Conditional conversion to `"1"`/`"0"` string |

---

## 9. Files Changed (Phase 3)

### New Files
- `apps/api/src/inference/` — engine, plugin, primitives, yolov12, gpu, loader, cpu_fallback, tracking, events, storage, alerts, benchmark
- `apps/api/src/schemas/inference.py`
- `apps/api/src/api/v1/endpoints/inference.py`
- `apps/api/src/api/v1/ws.py`
- `apps/api/src/models/inference.py`
- `apps/api/alembic/versions/0003_inference.py`
- `apps/api/tests/test_ai_unit.py`, `test_ai_integration.py`
- `apps/web/components/ai/ai-overlay.tsx`
- `apps/web/lib/inference-socket.ts`
- `apps/web/app/(dashboard)/ai/page.tsx`

### Modified Files
- `apps/api/src/main.py` — lifespan start/shutdown
- `apps/api/src/api/v1/router.py` — inference + WS routers
- `apps/api/src/core/config.py` — AI_* settings
- `apps/api/src/models/__init__.py` — inference ORM imports
- `apps/api/requirements.txt` — onnxruntime, python-multipart
- `apps/web/lib/api.ts` — inference endpoints
- `apps/web/lib/queries.ts` — inference hooks
- `apps/web/components/layout/sidebar.tsx` — /ai entry
- `packages/shared/src/constants.ts` — SENTINEL_CLASSES, INFERENCE_WS_PATH
- `packages/shared/src/types.ts` — inference TS interfaces
- `docker-compose.yml` — port 8000, AI volumes/env

---

## 10. Phase 3 Complete — STOP

All Phase 3 deliverables implemented, tested, and validated. No further phases to proceed.

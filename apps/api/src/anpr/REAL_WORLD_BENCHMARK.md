# Sentinel AI — Phase 4.1 Real-World ANPR Validation

## Status: NOT MEASURED

No real-world datasets are present in this environment. Every metric below is
marked **NOT MEASURED**. The dataset loader and benchmark framework code
(`apps/api/src/anpr/real_world.py`) are complete and ready to run when
datasets are placed in the expected directory structure.

---

## 1. Framework Overview

| Component | File | Purpose |
|-----------|------|---------|
| Dataset loaders | `real_world.py` | Load CCPD / UFPR-ALPR / Indian LP / AOLP / OpenALPR |
| Scenario classifier | `real_world.py` | Classify frames into 7 categories |
| Benchmark runner | `real_world.py` | Run existing pipeline, compute all 11 metrics |
| Failure Gallery | `real_world.py` → `failure_gallery` | Structured failure records with root cause |
| System resources | `real_world.py` | CPU / memory / GPU (best-effort via psutil/pynvml) |
| Evaluation engine | `evaluate.py` | Existing synthetic evaluation (fully functional) |
| Frame diagnostics | `diagnostics.py` | Blur, motion, light, exposure quality checks |
| Plate validator | `validator.py` | Indian plate validation + OCR post-processing |

**No existing architecture is modified.** All new code imports and reuses the
existing pipeline components (`PlateDetector`, `OcrEngine`, `PlateValidator`,
`rectify_plate`, `FrameDiagnostics`) directly.

---

## 2. Datasets

| Dataset | Expected Path | Status | Samples |
|---------|---------------|--------|---------|
| CCPD (Chinese City Parking) | `data/ccpd/` | NOT AVAILABLE | 0 |
| UFPR-ALPR | `data/ufpr-alpr/` | NOT AVAILABLE | 0 |
| Indian License Plate Dataset | `data/indian-license-plate/` | NOT AVAILABLE | 0 |
| AOLP (Asian/Oriental) | `data/aolp/` | NOT AVAILABLE | 0 |
| OpenALR Benchmark | `data/openalpr/` | NOT AVAILABLE | 0 |

### Expected Directory Structure

Each dataset must follow this layout:

```
data/<dataset-name>/
  images/
    IMG001.jpg
    IMG002.jpg
    ...
  annotations.csv
```

**annotations.csv** format:

```csv
image,plate_text,x,y,w,h,condition
IMG001.jpg,GJ01AB1234,0.1200,0.4500,0.2500,0.1200,day
IMG002.jpg,MH12DE5678,0.3000,0.5000,0.2000,0.1000,night
```

- `x,y,w,h` — normalised bounding box (0..1)
- `condition` — optional; one of `day/night/rain/motion_blur/low_resolution/tilted/occluded`
- If `condition` is absent, the `ScenarioClassifier` classifies automatically from pixel content

---

## 3. Metrics

All metrics are computed against the labelled ground truth of each dataset.
Detections are matched to GT plates by box IoU (threshold 0.5) **plus** OCR
word match — the strict Plate-Level metric (same as `evaluate.py`).

### 3.1 Detection

| Metric | Value |
|--------|-------|
| Plate Detection Precision | **NOT MEASURED** |
| Plate Detection Recall | **NOT MEASURED** |
| F1 Score | **NOT MEASURED** |
| False Positive Rate | **NOT MEASURED** |
| False Negative Rate | **NOT MEASURED** |

### 3.2 OCR

| Metric | Value |
|--------|-------|
| Character Accuracy | **NOT MEASURED** |
| Word Accuracy (exact match) | **NOT MEASURED** |
| Plate Accuracy (exact match) | **NOT MEASURED** |

### 3.3 Latency & Throughput

| Metric | Value |
|--------|-------|
| Average Latency | **NOT MEASURED** |
| Median Latency | **NOT MEASURED** |
| p95 Latency | **NOT MEASURED** |
| Min Latency | **NOT MEASURED** |
| Max Latency | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

### 3.4 System Resources

| Metric | Value |
|--------|-------|
| CPU Utilisation | **NOT MEASURED** |
| Memory (RSS) | **NOT MEASURED** |
| GPU Utilisation | **NOT MEASURED** |
| GPU Memory | **NOT MEASURED** |

Resources are measured via `psutil` (CPU/memory) and `pynvml` (GPU) when
available. If these libraries are not installed, the values are reported as
`NOT MEASURED`.

---

## 4. Scenario Breakdown

Scenarios are classified either from the dataset annotation column
(`condition`) or automatically by `ScenarioClassifier` using
`FrameDiagnostics` + geometric heuristics.

### 4.1 Day

| Metric | Value |
|--------|-------|
| Samples | **NOT MEASURED** |
| Precision | **NOT MEASURED** |
| Recall | **NOT MEASURED** |
| Char Accuracy | **NOT MEASURED** |
| Plate Accuracy | **NOT MEASURED** |
| Avg Latency (ms) | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

### 4.2 Night

| Metric | Value |
|--------|-------|
| Samples | **NOT MEASURED** |
| Precision | **NOT MEASURED** |
| Recall | **NOT MEASURED** |
| Char Accuracy | **NOT MEASURED** |
| Plate Accuracy | **NOT MEASURED** |
| Avg Latency (ms) | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

### 4.3 Rain

| Metric | Value |
|--------|-------|
| Samples | **NOT MEASURED** |
| Precision | **NOT MEASURED** |
| Recall | **NOT MEASURED** |
| Char Accuracy | **NOT MEASURED** |
| Plate Accuracy | **NOT MEASURED** |
| Avg Latency (ms) | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

### 4.4 Motion Blur

| Metric | Value |
|--------|-------|
| Samples | **NOT MEASURED** |
| Precision | **NOT MEASURED** |
| Recall | **NOT MEASURED** |
| Char Accuracy | **NOT MEASURED** |
| Plate Accuracy | **NOT MEASURED** |
| Avg Latency (ms) | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

### 4.5 Low Resolution

| Metric | Value |
|--------|-------|
| Samples | **NOT MEASURED** |
| Precision | **NOT MEASURED** |
| Recall | **NOT MEASURED** |
| Char Accuracy | **NOT MEASURED** |
| Plate Accuracy | **NOT MEASURED** |
| Avg Latency (ms) | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

### 4.6 Tilted Plates

| Metric | Value |
|--------|-------|
| Samples | **NOT MEASURED** |
| Precision | **NOT MEASURED** |
| Recall | **NOT MEASURED** |
| Char Accuracy | **NOT MEASURED** |
| Plate Accuracy | **NOT MEASURED** |
| Avg Latency (ms) | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

### 4.7 Occluded Plates

| Metric | Value |
|--------|-------|
| Samples | **NOT MEASURED** |
| Precision | **NOT MEASURED** |
| Recall | **NOT MEASURED** |
| Char Accuracy | **NOT MEASURED** |
| Plate Accuracy | **NOT MEASURED** |
| Avg Latency (ms) | **NOT MEASURED** |
| FPS | **NOT MEASURED** |

---

## 5. Failure Gallery

No failures to report — no datasets available to evaluate.

When datasets are available, the failure gallery is a structured list of every
failed image with:

| Field | Description |
|-------|-------------|
| `image_id` | Dataset-prefixed image identifier |
| `source` | Dataset name |
| `scenario` | Classified scenario |
| `gt_plate` | Ground-truth plate string |
| `detection_found` | Whether detector found any plate region |
| `detection_iou` | Best IoU between detected box and GT |
| `detection_confidence` | Detector confidence of best match |
| `ocr_text` | OCR predicted plate (or empty) |
| `ocr_valid` | Whether plate validator accepted the OCR read |
| `failure_type` | `missed_detection` / `wrong_ocr` / `both` |
| `root_cause` | Diagnosis from `FrameDiagnostics` + geometry analysis |
| `possible_improvement` | Suggested fix |
| `frame_diagnostics` | Full diagnostic report (blur, light, motion, etc.) |

---

## 6. How to Run

### Step 1 — Obtain datasets

Download one or more datasets and place them in the expected directory:

```bash
# Example: place CCPD in data/ccpd/
mkdir -p data/ccpd/images
# Copy images and annotations.csv into data/ccpd/
```

### Step 2 — Run the benchmark

```python
from src.anpr.onnx_backend import StageBackend
from src.anpr.plate_detector import PlateDetector
from src.anpr.ocr import OcrEngine
from src.anpr.real_world import RealWorldBenchmark

backend = StageBackend("weights", "auto")
detector = PlateDetector(backend)
ocr = OcrEngine(backend)

benchmark = RealWorldBenchmark(detector, ocr)
report = benchmark.run()

# report["status"] will be "MEASURED" if any dataset was loaded
# report["overall"] contains all 11 metrics
# report["per_scenario"] contains per-scenario breakdown
# report["failure_gallery"] contains structured failure records
```

### Step 3 — View results

The report dictionary contains everything. For charts, use the existing
`ReportBuilder` from `reports.py`:

```python
from src.anpr.reports import ReportBuilder

builder = ReportBuilder(evaluator, output_dir="reports/real_world")
artifacts = builder.generate(report, results)
```

---

## 7. Synthetic Evaluation (Functional)

While no real datasets are available, the **synthetic evaluation** via
`evaluate.py` is fully functional and produces genuine measured metrics.
This covers the same pipeline stages (detect → rectify → OCR → validate)
under controlled conditions (day / night / rain / low_light / blur /
motion_blur) and can be used as a proxy for pipeline health:

```python
from src.anpr.evaluate import Evaluator
from src.anpr.reports import ReportBuilder

evaluator = Evaluator(detector, ocr)
synthetic_report = evaluator.evaluate_all(size_per_condition=60)
# synthetic_report["status"] will be "MEASURED"
# synthetic_report["overall"] contains real precision/recall/F1/char_accuracy/FPS
```

---

## 8. Design Decisions

### Why NOT MEASURED instead of fabricated numbers

The sim detector and OCR produce deterministic, reproducible results on the
synthetic corpus. Running them on synthetic frames and presenting the numbers
as "real-world" metrics would be dishonest — they describe how well the sim
backend recovers its own deterministic appearance, not how well the system
handles real-world photographs of Indian license plates.

Real-world metrics require real photographs with accurate bounding-box and
plate-text annotations. No such data exists in this environment, so every
metric is marked NOT MEASURED until a genuine dataset is provided.

### Why the existing architecture is untouched

The benchmark framework is a pure consumer of the existing ANPR pipeline.
It imports `PlateDetector`, `OcrEngine`, `PlateValidator`, `rectify_plate`,
and `FrameDiagnostics` — but never modifies them. This ensures the pipeline
behaviour measured by the benchmark is identical to the production pipeline.

### Scenario classification

Scenarios are classified in priority order:

1. **Annotation override** — if the dataset provides a `condition` column, it
   takes precedence.
2. **Frame diagnostics** — `FrameDiagnostics.analyze()` checks blur, motion
   blur, low light, over/under exposure, dirty lens.
3. **Geometric heuristics** — plate aspect ratio (tilt) and plate size
   relative to frame (occlusion).

Priority: motion_blur > blur/rain > night > low_resolution > tilted >
occluded > day (default).

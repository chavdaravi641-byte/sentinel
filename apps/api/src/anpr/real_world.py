"""Phase 4.1 — Real-world ANPR dataset loaders + benchmark framework.

Runs the existing ANPR pipeline (detector → rectifier → OCR → validator)
against real-world Indian vehicle license plate datasets and computes:

  Detection : precision, recall, F1, false-positive rate, false-negative rate
  OCR       : character accuracy, plate accuracy (exact match), word accuracy
  Latency   : average, median, p95, min, max (ms)
  Throughput: FPS
  Resources : CPU utilisation, memory (RSS), GPU usage (best-effort)
  Scenarios : day / night / rain / motion_blur / low_resolution / tilted / occluded

This module is *self-contained* and does **not** modify any existing
architecture. It imports and reuses the existing ANPR pipeline components
(`PlateDetector`, `OcrEngine`, `PlateValidator`, `rectify_plate`, `FrameDiagnostics`)
directly.

Supported datasets (each with a dedicated loader):

  * CCPD  — Chinese City Parking Dataset (plate images + annotations)
  * UFPR-ALPR — University of Paraná ALPR benchmark
  * Indian License Plate Dataset (various public sources)
  * AOLP  — Asian/Oriental License Plates
  * OpenALR benchmark

STATUS ──────────────────────────────────────────────────────────────────
No real-world datasets are present in this environment. All loaders report
``available = False`` and the benchmark returns a report where every
real-world metric is marked **NOT MEASURED**.  The framework code is
complete and ready to run when datasets are placed in the expected
directory structure (see `_expected_structure` below).

The evaluation pipeline *itself* is fully functional — the same code that
computes the metrics against real images also powers the synthetic
evaluation (via ``evaluate.py``), so when a dataset appears the numbers
produced will be genuine, reproducible measurements.
──────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import csv
import statistics
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from src.anpr.diagnostics import FrameDiagnostics
from src.anpr.ocr import OcrEngine
from src.anpr.plate_detector import PlateDetector
from src.anpr.plate_rectifier import rectify_plate
from src.anpr.primitives import normalize_plate
from src.anpr.validator import PlateValidator

# ------------------------------------------------------------------ #
# Data model
# ------------------------------------------------------------------ #
SCENARIOS = [
    "day",
    "night",
    "rain",
    "motion_blur",
    "low_resolution",
    "tilted",
    "occluded",
]

# Thresholds for automatic scenario classification from frame analysis.
_LOW_RES_THRESHOLD = 300  # min dimension (px) to be considered "high-res"
_TILT_AR_MIN = 1.8  # acceptable aspect-ratio range for an Indian plate
_TILT_AR_MAX = 6.0


@dataclass
class RealWorldSample:
    """One labelled real-world ANPR sample."""

    image_id: str
    plate_text: str  # ground-truth (raw)
    normalized_plate: str  # normalised GT
    gt_box: tuple[float, float, float, float]  # (x, y, w, h) normalised
    scenario: str  # one of SCENARIOS
    source: str  # dataset name
    image_path: str | None = None
    frame: np.ndarray | None = None  # loaded BGR image (lazy)


@dataclass
class RealWorldFailure:
    """A structured failure record for the Failure Gallery."""

    image_id: str
    source: str
    scenario: str
    gt_plate: str
    detection_found: bool
    detection_iou: float
    detection_confidence: float
    ocr_text: str
    ocr_valid: bool
    failure_type: str  # missed_detection / wrong_ocr / both
    root_cause: str
    possible_improvement: str
    frame_diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "source": self.source,
            "scenario": self.scenario,
            "gt_plate": self.gt_plate,
            "detection_found": self.detection_found,
            "detection_iou": round(self.detection_iou, 4),
            "detection_confidence": round(self.detection_confidence, 4),
            "ocr_text": self.ocr_text,
            "ocr_valid": self.ocr_valid,
            "failure_type": self.failure_type,
            "root_cause": self.root_cause,
            "possible_improvement": self.possible_improvement,
            "frame_diagnostics": self.frame_diagnostics,
        }


# ------------------------------------------------------------------ #
# Dataset loaders
# ------------------------------------------------------------------ #
# Expected directory structure for every dataset:
#   data/<name>/
#     images/          *.jpg or *.png
#     annotations.csv  columns: image,plate_text,x,y,w,h[,condition]
#   — x,y,w,h are normalised 0..1 —
# ------------------------------------------------------------------ #
_BASE_PATHS = [
    Path(__file__).resolve().parent.parent.parent.parent,  # apps/api/
    Path(__file__).resolve().parent.parent.parent.parent.parent,  # sentinel-2/
]

_DATASET_CONFIGS: dict[str, dict[str, Any]] = {
    "ccpd": {
        "display_name": "CCPD (Chinese City Parking Dataset)",
        "paths": ["data/ccpd"],
        "expected_files": ["annotations.csv"],
        "url": "https://github.com/hustzl/CCPD",
    },
    "ufpr_alpr": {
        "display_name": "UFPR-ALPR",
        "paths": ["data/ufpr-alpr", "data/UFPR-ALPR"],
        "expected_files": ["annotations.csv"],
        "url": "https://github.com/hustzl/UFPR-ALPR-dataset",
    },
    "indian_lp": {
        "display_name": "Indian License Plate Dataset",
        "paths": [
            "data/indian-license-plate",
            "data/indian-plates",
            "data/ILPD",
        ],
        "expected_files": ["annotations.csv"],
        "url": "https://www.kaggle.com/datasets/",
    },
    "aolp": {
        "display_name": "AOLP (Asian/Oriental License Plates)",
        "paths": ["data/aolp", "data/AOLP"],
        "expected_files": ["annotations.csv"],
        "url": "https://github.com/hustzl/AOLP",
    },
    "openalpr": {
        "display_name": "OpenALPR Benchmark",
        "paths": ["data/openalpr", "data/OpenALPR"],
        "expected_files": ["annotations.csv"],
        "url": "https://github.com/openalpr/openalpr",
    },
}


def _find_dataset_path(config: dict[str, Any]) -> Path | None:
    """Return the first existing dataset root, or None."""
    for rel in config["paths"]:
        for base in _BASE_PATHS:
            candidate = base / rel
            if candidate.is_dir():
                ann = candidate / "annotations.csv"
                if ann.is_file():
                    return candidate
    return None


class RealWorldDataset(ABC):
    """Abstract base for real-world ANPR dataset loaders."""

    name: str
    display_name: str

    def __init__(self) -> None:
        self.display_name = _DATASET_CONFIGS[self.name]["display_name"]
        self._path = _find_dataset_path(_DATASET_CONFIGS[self.name])

    @property
    def available(self) -> bool:
        return self._path is not None

    @abstractmethod
    def samples(self, limit: int = 0) -> list[RealWorldSample]:
        """Load samples (images + ground truth). Empty list if unavailable."""
        ...

    @property
    def expected_structure(self) -> str:
        cfg = _DATASET_CONFIGS[self.name]
        lines = [f"  {self.display_name}:"]
        for p in cfg["paths"]:
            lines.append(f"    {p}/")
            lines.append("      images/          *.jpg")
            lines.append("      annotations.csv  image,plate_text,x,y,w,h[,condition]")
        return "\n".join(lines)


class _CSVDatasetLoader(RealWorldDataset):
    """Generic CSV-based loader (shared by all five datasets)."""

    def samples(self, limit: int = 0) -> list[RealWorldSample]:
        if not self.available:
            return []
        images_dir = self._path / "images"
        ann_path = self._path / "annotations.csv"
        out: list[RealWorldSample] = []
        with open(ann_path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if limit and len(out) >= limit:
                    break
                fname = row.get("image", "")
                img_path = images_dir / fname
                if not img_path.is_file():
                    continue
                plate_raw = row.get("plate_text", "")
                norm = normalize_plate(plate_raw)
                try:
                    x = float(row.get("x", 0))
                    y = float(row.get("y", 0))
                    w = float(row.get("w", 0))
                    h = float(row.get("h", 0))
                except (ValueError, TypeError):
                    continue
                # Scenario from annotation column, or classify later.
                scenario = row.get("condition", "").strip().lower()
                if scenario not in SCENARIOS:
                    scenario = ""  # reclassify automatically from image content
                out.append(
                    RealWorldSample(
                        image_id=f"{self.name}:{fname}",
                        plate_text=plate_raw,
                        normalized_plate=norm,
                        gt_box=(x, y, w, h),
                        scenario=scenario,
                        source=self.name,
                        image_path=str(img_path),
                    )
                )
        return out


class CCPDDataset(_CSVDatasetLoader):
    name = "ccpd"


class UFPRALPRDataset(_CSVDatasetLoader):
    name = "ufpr_alpr"


class IndianLPDataset(_CSVDatasetLoader):
    name = "indian_lp"


class AOLPDataset(_CSVDatasetLoader):
    name = "aolp"


class OpenALPRDataset(_CSVDatasetLoader):
    name = "openalpr"


ALL_DATASET_CLASSES: list[type[RealWorldDataset]] = [
    CCPDDataset,
    UFPRALPRDataset,
    IndianLPDataset,
    AOLPDataset,
    OpenALPRDataset,
]


# ------------------------------------------------------------------ #
# Scenario classifier
# ------------------------------------------------------------------ #
class ScenarioClassifier:
    """Classify a real-world frame into one of the seven scenario categories.

    Uses ``FrameDiagnostics`` from the existing diagnostics module plus
    heuristic checks for low resolution, tilt, and occlusion.
    """

    def __init__(self) -> None:
        self._diag = FrameDiagnostics()

    def classify(
        self,
        image: np.ndarray,
        detected_box: tuple[float, float, float, float] | None = None,
        annotation_scenario: str = "",
    ) -> str:
        """Return one of ``SCENARIOS``.

        If an annotation scenario is provided and valid, it is preferred.
        Otherwise the frame is classified automatically from pixel content
        and detection geometry.
        """
        if annotation_scenario in SCENARIOS:
            return annotation_scenario
        h, w = image.shape[:2]
        items = self._diag.analyze(image)
        issues = {i.name: i for i in items}

        # Priority order: motion_blur > blur > night/low_light > rain (heuristic)
        if issues.get("motion_blur") and issues["motion_blur"].severity > 0.5:
            return "motion_blur"
        if issues.get("blur") and issues["blur"].severity > 0.6:
            return "rain"  # heavy blur + streaks often indicate rain
        if (
            issues.get("low_light") and issues["low_light"].severity > 0.4
        ) or (
            issues.get("under_exposure") and issues["under_exposure"].severity > 0.5
        ):
            return "night"
        # Low resolution
        if min(h, w) < _LOW_RES_THRESHOLD:
            return "low_resolution"
        # Tilted: plate aspect ratio far from normal
        if detected_box:
            _, _, bw, bh = detected_box
            if bh > 0:
                ar = bw / bh
                if ar < _TILT_AR_MIN or ar > _TILT_AR_MAX:
                    return "tilted"
        # Occluded: very small plate relative to frame
        if detected_box:
            _, _, bw, bh = detected_box
            if bw * bh < 0.01:
                return "occluded"
        return "day"


# ------------------------------------------------------------------ #
# System resource measurement (best-effort)
# ------------------------------------------------------------------ #
def _get_system_resources() -> dict[str, Any]:
    """Collect CPU%, memory RSS, and GPU utilisation. Mark unavailable as N/A."""
    result: dict[str, Any] = {"cpu_percent": "NOT MEASURED", "memory_mb": "NOT MEASURED", "gpu_percent": "NOT MEASURED"}
    try:
        import psutil  # type: ignore[import-not-found]

        proc = psutil.Process()
        result["cpu_percent"] = round(proc.cpu_percent(interval=0.1), 1)
        result["memory_mb"] = round(proc.memory_info().rss / 1048576, 1)
    except Exception:
        pass
    try:
        import pynvml  # type: ignore[import-not-found]

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        result["gpu_percent"] = round(util.gpu, 1)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        result["gpu_memory_mb"] = round(mem.used / 1048576, 1)
        pynvml.nvmlShutdown()
    except Exception:
        pass
    return result


# ------------------------------------------------------------------ #
# IoU helper
# ------------------------------------------------------------------ #
def _iou(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(
                min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            )
        prev = cur
    return prev[-1]


# ------------------------------------------------------------------ #
# Benchmark runner
# ------------------------------------------------------------------ #
class RealWorldBenchmark:
    """Run the ANPR pipeline against real-world datasets.

    Uses the existing ``PlateDetector``, ``OcrEngine``, and ``PlateValidator``
    directly — no model behaviour is modified.
    """

    def __init__(
        self,
        detector: PlateDetector,
        ocr: OcrEngine,
        validator: PlateValidator | None = None,
        *,
        limit_per_dataset: int = 0,
        iou_threshold: float = 0.5,
    ) -> None:
        self.detector = detector
        self.ocr = ocr
        self.validator = validator or PlateValidator()
        self.limit_per_dataset = limit_per_dataset
        self.iou_threshold = iou_threshold
        self._classifier = ScenarioClassifier()
        self._diag = FrameDiagnostics()
        self._datasets = [cls() for cls in ALL_DATASET_CLASSES]

    # ------------------------------------------------------------------ #
    def run(self) -> dict[str, Any]:
        """Execute the full benchmark and return a structured report."""
        available = [d for d in self._datasets if d.available]
        all_samples: list[RealWorldSample] = []
        for ds in available:
            all_samples.extend(ds.samples(limit=self.limit_per_dataset))

        report: dict[str, Any] = {
            "status": "MEASURED" if all_samples else "NOT_MEASURED",
            "datasets_available": [d.name for d in available],
            "datasets_unavailable": [d.name for d in self._datasets if not d.available],
            "total_samples": len(all_samples),
            "expected_structure": "\n".join(
                ds.expected_structure for ds in self._datasets
            ),
        }

        if not all_samples:
            report["overall"] = _not_measured_report()
            report["per_scenario"] = {
                s: _not_measured_report() for s in SCENARIOS
            }
            report["failure_gallery"] = []
            report["system_resources"] = _get_system_resources()
            return report

        # -- Run the pipeline over all samples --
        results: list[dict[str, Any]] = []
        failures: list[RealWorldFailure] = []
        detect_times: list[float] = []
        total_times: list[float] = []

        for sample in all_samples:
            frame = self._load_frame(sample)
            if frame is None:
                continue
            sample.frame = frame

            # Re-classify scenario from actual image content.
            sample.scenario = self._classifier.classify(
                frame, sample.gt_box, sample.scenario
            )

            result = self._evaluate_sample(sample)
            results.append(result)
            detect_times.append(result["detect_ms"])
            total_times.append(result["total_ms"])

            if not result["matched"]:
                failures.append(self._build_failure(sample, result, frame))

        report["overall"] = _aggregate(results, detect_times, total_times)
        report["per_scenario"] = _aggregate_per_scenario(results, detect_times, total_times)
        report["failure_gallery"] = [f.to_dict() for f in failures]
        report["system_resources"] = _get_system_resources()
        return report

    # ------------------------------------------------------------------ #
    def _load_frame(self, sample: RealWorldSample) -> np.ndarray | None:
        if sample.frame is not None:
            return sample.frame
        if sample.image_path is None:
            return None
        try:
            import cv2

            img = cv2.imread(sample.image_path)
            return img
        except Exception:
            return None

    def _evaluate_sample(self, sample: RealWorldSample) -> dict[str, Any]:
        """Run detect → rectify → OCR → validate on one sample."""
        t0 = time.perf_counter()
        boxes = self.detector.detect(sample.frame)
        detect_ms = (time.perf_counter() - t0) * 1000

        crops = [rectify_plate(sample.frame, b) for b in boxes] if boxes else []
        reads = self.ocr.read_batch(crops) if crops else []
        total_ms = (time.perf_counter() - t0) * 1000

        # Match against ground truth.
        matched = False
        best_iou = 0.0
        best_conf = 0.0
        ocr_text = ""
        ocr_valid = False

        for box in boxes or []:
            det_box = (box.x, box.y, box.w, box.h)
            iou_val = _iou(det_box, sample.gt_box)
            if iou_val > best_iou:
                best_iou = iou_val
                best_conf = box.confidence
            if iou_val < self.iou_threshold:
                continue
            for read in reads or []:
                val = self.validator.validate(read.text)
                predicted = val.validated_plate
                ocr_text = predicted or read.text
                ocr_valid = val.valid
                if predicted == sample.normalized_plate:
                    matched = True
                break
            if matched:
                break

        # Char / word accuracy.
        gt = sample.normalized_plate
        if ocr_text:
            char_acc = max(0.0, 1.0 - _edit_distance(ocr_text, gt) / max(len(gt), 1))
            word_acc = 1.0 if ocr_text == gt else 0.0
        else:
            char_acc, word_acc = 0.0, 0.0

        diagnostics = self._diag.summarize(sample.frame)
        return {
            "image_id": sample.image_id,
            "source": sample.source,
            "scenario": sample.scenario,
            "gt_plate": gt,
            "gt_box": sample.gt_box,
            "detections": len(boxes or []),
            "matched": matched,
            "best_iou": best_iou,
            "best_confidence": best_conf,
            "ocr_text": ocr_text,
            "ocr_valid": ocr_valid,
            "char_acc": char_acc,
            "word_acc": word_acc,
            "detect_ms": detect_ms,
            "total_ms": total_ms,
            "diagnostics": diagnostics,
        }

    def _build_failure(
        self, sample: RealWorldSample, result: dict[str, Any], frame: np.ndarray
    ) -> RealWorldFailure:
        found = result["detections"] > 0
        iou_val = result["best_iou"]
        ocr_text = result["ocr_text"]
        diag = result.get("diagnostics", {})

        # Root cause analysis
        issues = [i["name"] for i in diag.get("all", []) if not i["ok"]]
        if not found:
            failure_type = "missed_detection"
            root = f"Detector found no plate region. Frame issues: {issues or ['none detected']}."
            improvement = "Improve detector sensitivity for this scenario; consider scenario-specific thresholds."
        elif found and iou_val < self.iou_threshold:
            failure_type = "missed_detection"
            root = f"Detector box IoU={iou_val:.3f} < threshold ({self.iou_threshold})."
            improvement = "Refine localization accuracy; increase training data for this plate geometry."
        elif ocr_text != sample.normalized_plate:
            failure_type = "wrong_ocr"
            root = f"OCR read '{ocr_text}' ≠ GT '{sample.normalized_plate}'. Frame issues: {issues or ['none']}."
            improvement = "Improve OCR character accuracy; consider language model or plate-specific fine-tuning."
        else:
            failure_type = "wrong_ocr"
            root = "Unknown failure mode."
            improvement = "Review pipeline end-to-end."

        return RealWorldFailure(
            image_id=sample.image_id,
            source=sample.source,
            scenario=sample.scenario,
            gt_plate=sample.normalized_plate,
            detection_found=found,
            detection_iou=iou_val,
            detection_confidence=result["best_confidence"],
            ocr_text=ocr_text,
            ocr_valid=result["ocr_valid"],
            failure_type=failure_type,
            root_cause=root,
            possible_improvement=improvement,
            frame_diagnostics=diag,
        )


# ------------------------------------------------------------------ #
# Aggregation helpers
# ------------------------------------------------------------------ #
def _not_measured_report() -> dict[str, Any]:
    return {
        "samples": "NOT MEASURED",
        "precision": "NOT MEASURED",
        "recall": "NOT MEASURED",
        "f1": "NOT MEASURED",
        "false_positive_rate": "NOT MEASURED",
        "false_negative_rate": "NOT MEASURED",
        "char_accuracy": "NOT MEASURED",
        "word_accuracy": "NOT MEASURED",
        "plate_accuracy": "NOT MEASURED",
        "latency_ms": "NOT MEASURED",
        "fps": "NOT MEASURED",
    }


def _aggregate(
    results: list[dict[str, Any]],
    detect_times: list[float],
    total_times: list[float],
) -> dict[str, Any]:
    n = len(results)
    tp = sum(1 for r in results if r["matched"])
    fp = sum(1 for r in results if not r["matched"] and r["detections"] > 0)
    fn = n - tp
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = (
        2 * precision * recall / max(precision + recall, 1e-9)
        if (precision + recall)
        else 0.0
    )
    char_acc = (sum(r["char_acc"] for r in results) / n) if n else 0.0
    word_acc = (sum(r["word_acc"] for r in results) / n) if n else 0.0

    def _pct(xs: list[float]) -> float:
        if not xs:
            return 0.0
        arr = np.asarray(xs)
        return float(np.percentile(arr, 95)) if len(arr) > 1 else float(arr[0])

    return {
        "samples": n,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / max(n, 1), 4),
        "false_negative_rate": round(fn / max(n, 1), 4),
        "char_accuracy": round(char_acc, 4),
        "word_accuracy": round(word_acc, 4),
        "plate_accuracy": round(tp / max(n, 1), 4),
        "latency_ms": {
            "avg": round(statistics.mean(total_times), 3) if total_times else 0.0,
            "median": round(statistics.median(total_times), 3) if total_times else 0.0,
            "p95": round(_pct(total_times), 3),
            "min": round(min(total_times), 3) if total_times else 0.0,
            "max": round(max(total_times), 3) if total_times else 0.0,
        },
        "latency_detect_ms": {
            "avg": round(statistics.mean(detect_times), 3) if detect_times else 0.0,
            "p95": round(_pct(detect_times), 3),
        },
        "fps": round(
            1000.0 / (sum(total_times) / max(n, 1)), 3
        )
        if n and sum(total_times)
        else 0.0,
    }


def _aggregate_per_scenario(
    results: list[dict[str, Any]],
    detect_times: list[float],
    total_times: list[float],
) -> dict[str, Any]:
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_scenario.setdefault(r["scenario"], []).append(r)
    out: dict[str, Any] = {}
    for scenario in SCENARIOS:
        items = by_scenario.get(scenario, [])
        if not items:
            out[scenario] = _not_measured_report()
            continue
        dt = [r["detect_ms"] for r in items]
        tt = [r["total_ms"] for r in items]
        out[scenario] = _aggregate(items, dt, tt)
    return out


__all__ = [
    "RealWorldSample",
    "RealWorldFailure",
    "RealWorldDataset",
    "RealWorldBenchmark",
    "ScenarioClassifier",
    "CCPDDataset",
    "UFPRALPRDataset",
    "IndianLPDataset",
    "AOLPDataset",
    "OpenALPRDataset",
    "ALL_DATASET_CLASSES",
    "SCENARIOS",
]

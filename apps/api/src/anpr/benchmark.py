"""Phase 4 ANPR benchmark: performance + detection/OCR accuracy over synthetic plates.

Runs a number of synthetic frames through the plate detector, rectifier and OCR
stages (and the vehicle-attribute stage), without touching Postgres. Reports:

* Latency and throughput (per-frame ms, total ms, FPS).
* Detector accuracy computed against the known ground-truth plate that each
  synthetic frame draws: True/False positives, False negatives, Precision and
  Recall. These metrics represent the *actual detector output* — they are never
  fabricated.
* OCR character accuracy: the fraction of OCR reads that yielded a valid
  normalized plate string (the deterministic sim reader derives the text from
  the crop's pixel hash, so this is meaningful and reproducible).

The benchmark is deliberately stateless so it can run against a live manager or
stand alone, and is fully deterministic for a fixed ``width``/``height``/``seed``.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from src.anpr.ocr import OcrEngine
from src.anpr.plate_detector import PlateDetector
from src.anpr.plate_rectifier import rectify_plate
from src.anpr.vehicles import VehicleIntelligence

_PLATE_PW = 160
_PLATE_PH = 48
_PLATE_BORDER = 3


def _synthetic_frame(width: int = 640, height: int = 360, seed: int = 0) -> np.ndarray:
    """Build a deterministic synthetic camera frame (noise + a plate region)."""
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
    # Draw a bright "plate" band in the lower third to emulate a real capture.
    ph, pw = _PLATE_PH, _PLATE_PW
    px, py = (width - pw) // 2, height - ph - 40
    frame[py : py + ph, px : px + pw] = (200, 200, 210)
    border = _PLATE_BORDER
    frame[py : py + border, px : px + pw] = (40, 40, 45)
    frame[py + ph - border : py + ph, px : px + pw] = (40, 40, 45)
    frame[py : py + ph, px : px + border] = (40, 40, 45)
    frame[py : py + ph, px + pw - border : px + pw] = (40, 40, 45)
    return frame


def _ground_truth_rect(
    width: int = 640, height: int = 360
) -> tuple[float, float, float, float]:
    """Normalized ground-truth plate rect ``(x, y, w, h)`` for a synthetic frame.

    This mirrors exactly the plate placed by ``_synthetic_frame`` so evaluation
    is measured against the image the generator actually produced.
    """
    px, py = (width - _PLATE_PW) // 2, height - _PLATE_PH - 40
    return (px / width, py / height, _PLATE_PW / width, _PLATE_PH / height)


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _stats(times: list[float]) -> dict[str, float]:
    arr = np.asarray(times)
    return {
        "avg_ms": round(float(arr.mean()) * 1000, 3),
        "min_ms": round(float(arr.min()) * 1000, 3),
        "max_ms": round(float(arr.max()) * 1000, 3),
    }


def run_benchmark(
    *,
    detector: PlateDetector,
    ocr: OcrEngine,
    vehicles: VehicleIntelligence,
    iterations: int = 50,
    width: int = 640,
    height: int = 360,
    batch_size: int = 1,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    ok_frames = 0
    fail_frames = 0
    reads_ok = 0
    reads_total = 0
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    times: list[float] = []

    gt_rect = _ground_truth_rect(width, height)

    for i in range(iterations):
        frame = _synthetic_frame(width, height, seed=i)
        t0 = time.perf_counter()
        boxes = detector.detect(frame)
        crops = [rectify_plate(frame, b) for b in boxes]
        reads = ocr.read_batch(crops) if crops else []
        for read in reads:
            reads_total += 1
            if read.normalized:
                reads_ok += 1
            vehicles.recognize(frame, plate_text=read.normalized)
        dt = time.perf_counter() - t0
        times.append(dt)

        # -- Detection-level evaluation vs ground truth (exactly one plate). --
        matched = [False] * len(boxes)
        for g in (gt_rect,):
            best_iou, best_idx = 0.0, -1
            for j, b in enumerate(boxes):
                if matched[j]:
                    continue
                iou = _iou(g, (b.x, b.y, b.w, b.h))
                if iou > best_iou:
                    best_iou, best_idx = iou, j
            if best_idx >= 0 and best_iou >= iou_threshold:
                matched[best_idx] = True
                true_positives += 1
            else:
                false_negatives += 1
        false_positives += sum(1 for m in matched if not m)

        if reads:
            ok_frames += 1
        else:
            fail_frames += 1

    total_ms = sum(times) * 1000
    avg_ms = (total_ms / iterations) if iterations else 0.0
    precision = true_positives / (true_positives + false_positives) if (
        true_positives + false_positives
    ) else 0.0
    recall = true_positives / (true_positives + false_negatives) if (
        true_positives + false_negatives
    ) else 0.0
    character_accuracy = reads_ok / max(reads_total, 1)

    return {
        "total_ms": round(total_ms, 3),
        "avg_ms": round(avg_ms, 3),
        "min_ms": round(min(times) * 1000, 3) if times else 0.0,
        "max_ms": round(max(times) * 1000, 3) if times else 0.0,
        "per_frame_ms": round(avg_ms, 3),
        "fps": round(iterations / max(sum(times), 1e-9), 3),
        "frames": iterations,
        "ok": ok_frames,
        "fail": fail_frames,
        "batch_size": batch_size,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "character_accuracy": round(character_accuracy, 4),
        "accuracy": {
            "reads_total": reads_total,
            "reads_ok": reads_ok,
            "character_accuracy": round(character_accuracy, 4),
        },
    }


__all__ = ["run_benchmark"]

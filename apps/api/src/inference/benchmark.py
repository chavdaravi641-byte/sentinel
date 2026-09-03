"""Performance benchmark for the inference engine.

Measures preprocess / session / postprocess latency, throughput (FPS) and
objects-per-second for a batch size and resolution, on the active backend
(onnx-cuda / onnx-cpu / sim). Results are returned as JSON and persisted as a
file under `{weights_dir}/../benchmarks` for the validation report.
"""

from __future__ import annotations

import asyncio
import functools
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from src.core.logging import log
from src.inference.primitives import InferItem
from src.inference.yolov12 import YoloV12Plugin

_DEFAULT_ITERATIONS = 50
_DEFAULT_SIZE = (1280, 720)


def _synthetic_image(width: int, height: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    base = rng.integers(0, 180, size=(height, width, 3), dtype=np.uint8)
    # simple moving-box pattern so decode + decode pipeline sees structured data
    base[height // 3 : height // 2, width // 4 : width // 2] = np.array([240, 210, 180], dtype=np.uint8)
    return base


def run_plugin_benchmark(
    plugin: YoloV12Plugin,
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    width: int = _DEFAULT_SIZE[0],
    height: int = _DEFAULT_SIZE[1],
    batch_size: int = 1,
) -> dict[str, Any]:
    """Synchronous benchmark of a single plugin (call from an executor)."""
    frames = [_synthetic_image(width, height) for _ in range(batch_size)]
    ctx = {"camera_id": "benchmark", "frame_seq": 0, "seed": 91337}
    items = [InferItem(image=f, ctx=ctx) for f in frames]

    # warmup
    for _ in range(3):
        plugin.infer_batch(items)

    pre, infer, post, total, objects = 0.0, 0.0, 0.0, 0.0, 0
    start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        results, timings = plugin.infer_batch(items)
        t1 = time.perf_counter()
        pre += timings.pre_ms
        infer += timings.infer_ms
        post += timings.post_ms
        total += (t1 - t0) * 1000.0
        objects += sum(len(r) for r in results)
    elapsed = max(time.perf_counter() - start, 1e-9)

    n = batch_size * iterations
    avg = lambda v: round(v / iterations, 4)
    report: dict[str, Any] = {
        "model": plugin.name,
        "backend": plugin.backend,
        "generation": plugin.health()["generation"],
        "accelerator": plugin.device.accelerator,
        "device_name": plugin.device.device_name,
        "providers": list(plugin.device.providers),
        "image_width": width,
        "image_height": height,
        "batch_size": batch_size,
        "iterations": iterations,
        "frames_processed": int(n),
        "pre_ms_avg": avg(pre),
        "infer_ms_avg": avg(infer),
        "post_ms_avg": avg(post),
        "total_ms_avg": avg(total),
        "fps": round(float(n) / elapsed, 2),
        "objects_per_second": round(float(objects) / elapsed, 2),
        "objects_per_frame_avg": round(objects / max(1, n), 2),
        "run_ms": round(elapsed * 1000.0, 1),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if plugin.backend == "sim":
        report["timing_note"] = (
            "deterministic sim backend: compute is sub-microsecond and does not "
            "reflect ONNX decode/forward latency"
        )
    return report


def _write_report(report: dict[str, Any]) -> str:
    from src.core.config import settings

    bench_dir = Path(settings.AI_WEIGHTS_DIR).parent / "benchmarks"
    bench_dir.mkdir(parents=True, exist_ok=True)
    filename = f"benchmark-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    path = bench_dir / filename
    path.write_text(json.dumps(report, indent=2))
    log.info("ai.benchmark.wrote", path=str(path))
    return str(path)


async def run_benchmark(
    *,
    engine: Any,
    iterations: int = _DEFAULT_ITERATIONS,
    width: int = _DEFAULT_SIZE[0],
    height: int = _DEFAULT_SIZE[1],
    batch_size: int = 1,
    persist: bool = True,
) -> dict[str, Any]:
    """Async entrypoint used by the REST endpoint and CLI."""
    plugin = engine.plugin()
    results: dict[str, Any] = await asyncio.get_running_loop().run_in_executor(
        engine._executor,
        functools.partial(
            run_plugin_benchmark,
            plugin,
            iterations=iterations,
            width=width,
            height=height,
            batch_size=batch_size,
        ),
    )
    results["iterations"] = iterations
    if persist:
        results["report_file"] = _write_report(results)
    return results


__all__ = ["run_benchmark", "run_plugin_benchmark"]
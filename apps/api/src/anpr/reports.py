"""Chart / artifact generation for ANPR evaluation reports.

Produces matplotlib charts plus CSV/JSON artifacts that summarise the evaluation
run without fabricating numbers. matplotlib is used ONLY where it is importable;
if it is missing the chart step degrades gracefully to raw JSON/CSV so the
metric numbers themselves are never lost.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any

import numpy as np

from src.anpr.evaluate import Evaluator, SampleResult


class ReportBuilder:
    """Build charts + artifacts and a run summary."""

    def __init__(self, evaluator: Evaluator, output_dir: str) -> None:
        self.evaluator = evaluator
        self.output_dir = output_dir
        self._mpl = None
        try:  # optional dependency
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            self._mpl = plt
        except Exception:  # pragma: no cover - mpl may be absent
            self._mpl = None

    # ------------------------------------------------------------ #
    def generate(self, report: dict[str, Any], results: list[SampleResult]) -> dict[str, Any]:
        os.makedirs(self.output_dir, exist_ok=True)
        artifacts: dict[str, str] = {}

        artifacts.update(self._dump_results(results))
        artifacts.update(self._dump_config(report))

        if self._mpl is not None:
            try:
                artifacts.update(self._charts(report, results))
            except Exception as exc:  # pragma: no cover - chart-only failure
                artifacts["_chart_error"] = f"charts skipped: {exc}"

        self._write_metrics(report)
        return artifacts

    # ------------------------------------------------------------ #
    def _dump_results(self, results: list[SampleResult]) -> dict[str, str]:
        path = os.path.join(self.output_dir, "samples.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(SampleResult.__annotations__.keys())
                               + ["correct_state"])
            w.writeheader()
            for r in results:
                w.writerow(r.to_dict())
        return {"samples_csv": path}

    def _dump_config(self, report: dict[str, Any]) -> dict[str, str]:
        path = os.path.join(self.output_dir, "run.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
        return {"run_json": path}

    def _write_metrics(self, report: dict[str, Any]) -> None:
        path = os.path.join(self.output_dir, "metrics.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report.get("overall", report), fh, indent=2, default=str)

    # ------------------------------------------------------------ #
    def _charts(self, report: dict[str, Any], results: list[SampleResult]) -> dict[str, str]:
        plt = self._mpl
        out: dict[str, str] = {}
        fig, axes = plt.subplots(2, 3, figsize=(16, 9))
        axes = list(axes.flat)

        # 1. Bar chart of precision/recall/F1 per condition.
        ax = axes[0]
        per_cond = report.get("per_condition", {})
        conds = list(per_cond.keys())
        x = np.arange(len(conds))
        width = 0.25
        for i, key in enumerate(["precision", "recall", "f1"]):
            vals = [per_cond[c].get(key, 0.0) for c in conds]
            ax.bar(x + i * width, vals, width, label=key)
        ax.set_title("Precision / Recall / F1 by condition")
        ax.set_xticks(x + width)
        ax.set_xticklabels([c.replace("_", "\n") for c in conds], fontsize=7)
        ax.legend(fontsize=7)
        ax.set_ylim(0, 1)

        # 2. Latency histogram.
        ax = axes[1]
        lat = [r.total_ms for r in results]
        ax.hist(lat, bins=25, color="steelblue", edgecolor="white")
        ax.axvline(report["latency_ms"]["avg"], color="red", ls="--",
                   label=f'avg {report["latency_ms"]["avg"]:.0f}ms')
        ax.set_title("End-to-end latency histogram")
        ax.set_xlabel("ms")
        ax.legend(fontsize=7)

        # 3. OCR confidence-truth tradeoff (PR-style): char accuracy by threshold.
        ax = axes[2]
        char_accs = sorted((r.char_acc for r in results), reverse=True)
        cumulative = np.cumsum(char_accs) / np.arange(1, len(char_accs) + 1)
        ax.plot(range(1, len(cumulative) + 1), cumulative, color="green")
        ax.set_title("Cumulative mean char accuracy")
        ax.set_xlabel("top-k samples")
        ax.set_ylabel("mean char acc")
        ax.set_ylim(0, 1.05)

        # 4. FPS by condition.
        ax = axes[3]
        fps = [per_cond[c].get("fps", 0.0) for c in conds]
        ax.bar(x, fps, color="tomato")
        ax.set_title("Throughput (FPS) by condition")
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("_", "\n") for c in conds], fontsize=7)
        ax.set_ylim(0)

        # 5. Confusion-style: matched vs missed per condition.
        ax = axes[4]
        matched = [sum(1 for r in results if r.condition == c and r.matched) for c in conds]
        missed = [per_cond[c]["false_negative"] for c in conds]
        ax.bar(x - 0.2, matched, 0.4, label="matched", color="forestgreen")
        ax.bar(x + 0.2, missed, 0.4, label="missed", color="crimson")
        ax.set_title("Matched vs missed reads by condition")
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("_", "\n") for c in conds], fontsize=7)
        ax.legend(fontsize=7)

        # 6. State accuracy by condition.
        ax = axes[5]
        state_acc = [per_cond[c].get("state_accuracy", 0.0) for c in conds]
        ax.bar(x, state_acc, color="mediumpurple")
        ax.set_title("State-code accuracy by condition")
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("_", "\n") for c in conds], fontsize=7)
        ax.set_ylim(0, 1)

        fig.tight_layout()
        path = os.path.join(self.output_dir, "summary.png")
        fig.savefig(path, dpi=110)
        plt.close(fig)
        out["summary_png"] = path
        return out


__all__ = ["ReportBuilder"]

"""Statistics over repeated runs of one task, shared by the Part 3 report and the export.

``task_stats`` takes the rows of one task in k runs of one design (or any group of rows)
and returns the pass rate, whether every run passed, and the mean and median of model
calls, input tokens, latency and dollars. ``pass_hat_k`` is the share of tasks that
passed in every run (pass^k with k = the number of runs).
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any

METRICS = ("model_calls", "input_tokens", "latency_s", "dollars")


def task_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(bool(r["passed"]) for r in rows)
    out: dict[str, Any] = {
        "runs": len(rows),
        "passed": passed,
        "pass_rate": passed / len(rows),
        "passed_all": passed == len(rows),
    }
    for m in METRICS:
        values = [r[m] for r in rows]
        out[f"{m}_mean"] = mean(values)
        out[f"{m}_median"] = median(values)
    return out


def pass_hat_k(passes: dict[str, list[bool]]) -> float:
    """Share of tasks that passed in all their runs."""
    return sum(all(p) for p in passes.values()) / len(passes)

"""Build reports/article-a3/README.md from the Part 3 run files.

    uv run python scripts/report_a3.py [reports folder]

Reads reports/article-a3/custom/<batch>/<spec>/r<NN>/ (results.jsonl, run.json),
reports/article-a3/routing/<spec>/r<NN>/ and reports/article-a3/spend.jsonl. Computes
nothing that is not in those files.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from report_a1 import fmt_usd, md_escape  # noqa: E402

from envs.custom.route_eval import THRESHOLDS  # noqa: E402
from envs.custom.stats import pass_hat_k, task_stats  # noqa: E402
from harness.runinfo import now  # noqa: E402

DESIGNS = {
    "a3-do-nothing": "0 do nothing",
    "a1-plain": "1 plain agent",
    "a2-agent-approval": "2 agent with approval middleware",
    "a2-workflow": "3 agent inside a workflow",
    "a2-router": "4 router and three agents",
    "a2-code": "5 workflow with no agent",
    "a3-hybrid": "6 hybrid",
}
BATCHES = {
    "k10": "the 16 known tasks",
    "oot": "the 32 out-of-template messages",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_batches(report: Path) -> dict[str, dict[str, list[dict]]]:
    """batch -> spec name -> runs in order; a run is {"run": run.json, "rows": results}."""
    out: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for results in sorted(report.glob("custom/*/*/r*/results.jsonl")):
        run = json.loads((results.parent / "run.json").read_text())
        out[run["batch"]][run["spec"]["name"]].append({"run": run, "rows": read_jsonl(results)})
    rank = {name: i for i, name in enumerate(DESIGNS)}
    return {
        b: dict(sorted(specs.items(), key=lambda kv: rank.get(kv[0], 99)))
        for b, specs in out.items()
    }


def cache_share(rows: list[dict]) -> float:
    tokens = sum(r["input_tokens"] for r in rows)
    return sum(r["cache_read_tokens"] for r in rows) / tokens if tokens else 0.0


def batch_lines(batch: str, specs: dict[str, list[dict]]) -> list[str]:
    k = max(len(runs) for runs in specs.values())
    lines = [
        "",
        f"## {batch}: {BATCHES.get(batch, batch)}, up to {k} runs per design",
        "",
        "A run is one pass of one design over all the tasks. Run 1 of every design ran "
        "before run 2 of any. Pass rate counts every task in every run; pass^k is the share "
        "of tasks that passed in all runs of the design. Cost and the cache-read share are "
        "per run; the share is of all input tokens.",
        "",
        "| design | runs | pass rate | pass^k | median $/run (min to max) | median cache-read "
        "share | mean model calls/task | median latency s/task | run errors |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, runs in specs.items():
        rows = [r for run in runs for r in run["rows"]]
        by_task: dict[str, list[bool]] = defaultdict(list)
        for r in rows:
            by_task[r["task_id"]].append(r["passed"])
        costs = [sum(r["dollars"] for r in run["rows"]) for run in runs]
        shares = [cache_share(run["rows"]) for run in runs]
        lines.append(
            f"| {DESIGNS.get(name, name)} | {len(runs)} | "
            f"{sum(r['passed'] for r in rows)}/{len(rows)} | {pass_hat_k(by_task):.2f} | "
            f"{fmt_usd(median(costs))} ({fmt_usd(min(costs))} to {fmt_usd(max(costs))}) | "
            f"{median(shares):.0%} | {sum(r['model_calls'] for r in rows) / len(rows):.2f} | "
            f"{median(r['latency_s'] for r in rows):.1f} | "
            f"{sum(r['outcome'] == 'error' for r in rows)} |"
        )

    lines += [
        "",
        f"### {batch}: cost of each run",
        "",
        "| design | " + " | ".join(f"r{i:02d}" for i in range(1, k + 1)) + " |",
        "|---|" + "---|" * k,
    ]
    for name, runs in specs.items():
        cells = [
            f"{fmt_usd(sum(r['dollars'] for r in run['rows']))} ({cache_share(run['rows']):.0%})"
            for run in runs
        ]
        lines.append(f"| {DESIGNS.get(name, name)} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Each cell: dollars for the run, and the cache-read share in brackets.")

    lines += [
        "",
        f"### {batch}: per task and design",
        "",
        "| task | design | passed | all runs | model calls mean (median) | input tokens mean "
        "(median) | latency s mean (median) | $ mean (median) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    task_ids = list(dict.fromkeys(r["task_id"] for runs in specs.values() for r in runs[0]["rows"]))
    for task_id in task_ids:
        for name, runs in specs.items():
            rows = [r for run in runs for r in run["rows"] if r["task_id"] == task_id]
            if not rows:
                continue
            s = task_stats(rows)
            lines.append(
                f"| {task_id} | {name} | {s['passed']}/{s['runs']} | "
                f"{'yes' if s['passed_all'] else 'no'} | "
                f"{s['model_calls_mean']:.1f} ({s['model_calls_median']:g}) | "
                f"{s['input_tokens_mean']:,.0f} ({s['input_tokens_median']:,.0f}) | "
                f"{s['latency_s_mean']:.1f} ({s['latency_s_median']:.1f}) | "
                f"{fmt_usd(s['dollars_mean'])} ({fmt_usd(s['dollars_median'])}) |"
            )
    return lines


def routing_lines(report: Path) -> list[str]:
    runs: dict[str, list[tuple[dict, list[dict]]]] = defaultdict(list)
    for results in sorted(report.glob("routing/*/r*/results.jsonl")):
        run = json.loads((results.parent / "run.json").read_text())
        runs[run["spec"]["name"]].append((run, read_jsonl(results)))
    if not runs:
        return []
    lines = [
        "",
        "## Routing: both routers on the 25 labelled requests, repeated",
        "",
        "Part 2 saved one run of each router (`reports/article-a2/routing/`). These runs "
        "are new. A request is a question when the router picks `unclear` or its confidence "
        "is below the threshold.",
    ]
    for name, spec_runs in runs.items():
        lines += [
            "",
            f"### {name}: {len(spec_runs)} runs",
            "",
            "| run | "
            + " | ".join(f"right, wrong, questions needed, not needed at {t}" for t in THRESHOLDS)
            + " | $ |",
            "|---|" + "---|" * (len(THRESHOLDS) + 1),
        ]
        for run, _ in spec_runs:
            cells = []
            for t in THRESHOLDS:
                s = run["summary"][f"threshold {t}"]
                cells.append(
                    f"{s['right_route']}, {s['wrong_route']}, {s['clarify_needed']}, "
                    f"{s['clarify_not_needed']}"
                )
            lines.append(
                f"| r{run['run']:02d} | " + " | ".join(cells) + f" | {fmt_usd(run['dollars'])} |"
            )
        lines += [
            "",
            "| label | request | choices over the runs | confidence min to max |",
            "|---|---|---|---|",
        ]
        for i, case in enumerate(spec_runs[0][1]):
            picks = [rows[i]["choice"] for _, rows in spec_runs]
            conf = [rows[i]["confidence"] or 0.0 for _, rows in spec_runs]
            counts = ", ".join(f"{c} {picks.count(c)}" for c in sorted(set(picks)))
            lines.append(
                f"| {case['label']} | {md_escape(case['request'])} | {counts} | "
                f"{min(conf):.2f} to {max(conf):.2f} |"
            )
    return lines


def spend_lines(report: Path) -> list[str]:
    ledger = report / "spend.jsonl"
    if not ledger.exists():
        return []
    totals: dict[str, float] = defaultdict(float)
    for r in read_jsonl(ledger):
        totals[r["step"]] += max(r["dollars"], r.get("billed") or 0.0)
    lines = ["", "## Spend", "", "| step | dollars |", "|---|---|"]
    lines += [f"| {step} | ${d:.5f} |" for step, d in totals.items()]
    lines.append(f"| total | ${sum(totals.values()):.5f} |")
    return lines


def build(report: Path) -> None:
    batches = load_batches(report)
    lines = [
        "# Article A3 results",
        "",
        "Repeated runs for Part 3 and the Agent or Workflow Atlas. Summary and limits: "
        "[`NOTES.md`](NOTES.md).",
        "",
        f"Generated {now()} by `scripts/report_a3.py`. Each run folder has `results.jsonl`, "
        "`traces.jsonl` and `run.json` (spec, spec hash, price table, versions, git commit). "
        "Dollars use the pinned price table `harness/prices/openrouter-2026-10-05.json`.",
    ]
    for batch, specs in batches.items():
        lines += batch_lines(batch, specs)
    lines += routing_lines(report)
    lines += spend_lines(report)
    (report / "README.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {report / 'README.md'}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports" / "article-a3")

"""Build reports/article-a2/README.md from the committed run files.

    uv run python scripts/report_a2.py

Reads reports/article-a2/custom/<spec>/results.jsonl and run.json, and
reports/article-a2/routing/<spec>/. Computes nothing that is not in those files.
Every number is a single run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from report_a1 import fmt_usd, md_escape, summarize  # noqa: E402

from envs.custom.tasks import TASKS  # noqa: E402
from harness.runinfo import now  # noqa: E402

REPORT = ROOT / "reports" / "article-a2"
PART1 = {t.id for t in TASKS}
ORDER = ["a1-plain", "a2-agent-approval", "a2-workflow", "a2-router"]


def models(spec: dict) -> str:
    if spec.get("kind") == "workflow":
        ids = set()
        for n in spec["nodes"].values():
            if n["type"] == "agent":
                ids.add(Path(n["agent"]["spec"]).name)
            elif n["type"] == "classifier":
                ids.add(n["model"])
        return "workflow: " + ", ".join(f"`{i}`" for i in sorted(ids))
    return f"`{spec['model']['id']}`"


def load_custom() -> list[dict]:
    runs = []
    for results in REPORT.glob("custom/*/results.jsonl"):
        run = json.loads((results.parent / "run.json").read_text())
        rows = [json.loads(line) for line in results.read_text().splitlines() if line.strip()]
        runs.append({"dir": results.parent.relative_to(REPORT), "run": run, "rows": rows})
    rank = {n: i for i, n in enumerate(ORDER)}
    return sorted(runs, key=lambda r: rank.get(r["run"]["spec"]["name"], 99))


def build() -> None:
    runs = load_custom()
    if not runs:
        raise SystemExit("No results under reports/article-a2/custom/. Run make a2-matrix.")
    lines = [
        "# Article A2 results",
        "",
        "One run per task, so small differences between rows are not measured effects. "
        "Summary: [`NOTES.md`](NOTES.md).",
        "",
        f"Generated {now()} by `scripts/report_a2.py`. Each run directory has `results.jsonl`, "
        "`run.json` (spec, versions, git commit, prices) and `traces.jsonl` (messages, every "
        "model and tool call, approval and error events).",
        "",
        "## Summary (single run)",
        "",
        "The Part 1 tasks are the 12 development tasks. The approval tasks are the four "
        "added in Part 2 (`APPROVAL_TASKS` in `envs/custom/tasks.py`).",
        "",
        "| spec | runs | Part 1 tasks | approval tasks | mean $/task | mean latency s "
        "| mean model calls | Jev calls | approval pauses | resumes after error | run errors |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        rows, spec = r["rows"], r["run"]["spec"]
        s = summarize(rows)
        p1 = [x for x in rows if x["task_id"] in PART1]
        p2 = [x for x in rows if x["task_id"] not in PART1]
        frac = lambda xs: f"{sum(x['passed'] for x in xs)}/{len(xs)}" if xs else "not run"  # noqa: E731
        lines.append(
            f"| {spec['name']} | {models(spec)} | {frac(p1)} | {frac(p2)} "
            f"| {fmt_usd(s['mean_usd_per_task'])} | {s['mean_latency_s']:.1f} "
            f"| {s['mean_model_calls']:.1f} | {s['classifier_calls']} "
            f"| {sum(x.get('approval_requests', 0) for x in rows)} "
            f"| {sum(x.get('resumes_after_error', 0) for x in rows)} | {s['run_errors']} |"
        )

    for r in runs:
        spec = r["run"]["spec"]
        lines += [
            "",
            f"## {spec['name']}, single run",
            "",
            f"Files: `{r['dir']}/`",
            "",
            "| task | result | outcome | reason | refund operations | $ | latency s "
            "| model calls | tool calls |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for row in r["rows"]:
            ops = ", ".join(o["status"] for o in row.get("refund_operations", [])) or "none"
            lines.append(
                f"| {row['task_id']} | {'pass' if row['passed'] else 'FAIL'} "
                f"| {row.get('outcome', '')} | {md_escape(row['reason'])[:200]} | {ops} "
                f"| {fmt_usd(row['dollars'])} | {row['latency_s']:.1f} | {row['model_calls']} "
                f"| {row['tool_calls']} |"
            )

    for results in sorted(REPORT.glob("routing/*/results.jsonl")):
        run = json.loads((results.parent / "run.json").read_text())
        rows = [json.loads(line) for line in results.read_text().splitlines() if line.strip()]
        lines += [
            "",
            f"## Routing: {run['spec']['name']} / {run['node']}, single run",
            "",
            f"Files: `{results.parent.relative_to(REPORT)}/`. {run['cases']} labelled requests, "
            f"{run['classifier_calls']} classifier calls, {fmt_usd(run['dollars'])} in total.",
            "",
            "| threshold | right route | wrong route | clarify, needed | clarify, not needed |",
            "|---|---|---|---|---|",
        ]
        for name, s in run["summary"].items():
            lines.append(
                f"| {name.split()[-1]} | {s['right_route']} | {s['wrong_route']} "
                f"| {s['clarify_needed']} | {s['clarify_not_needed']} |"
            )
        lines += ["", "| label | choice | confidence | request |", "|---|---|---|---|"]
        for row in rows:
            lines.append(
                f"| {row['label']} | {row['choice']} | {row['confidence']:.2f} "
                f"| {md_escape(row['request'])} |"
            )

    (REPORT / "README.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {REPORT / 'README.md'}")


if __name__ == "__main__":
    build()

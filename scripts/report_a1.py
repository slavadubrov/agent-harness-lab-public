"""Build reports/article-a1/README.md and versions.json from the committed run files.

    uv run python scripts/report_a1.py

Reads every reports/article-a1/<env>/<spec>/results.jsonl and run.json. Computes
nothing that is not in those files. Every number is a single run.
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.runinfo import TAU2_COMMIT, TAU2_TAG_NOTE, git_sha, now, packages  # noqa: E402

REPORT = ROOT / "reports" / "article-a1"


def load_runs() -> list[dict]:
    runs = []
    paths = sorted(REPORT.glob("custom/*/results.jsonl")) + sorted(
        REPORT.glob("tau3/*/results.jsonl")
    )
    for results in paths:
        run = json.loads((results.parent / "run.json").read_text())
        rows = [json.loads(line) for line in results.read_text().splitlines() if line.strip()]
        runs.append({"dir": results.parent.relative_to(REPORT), "run": run, "rows": rows})
    return runs


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    solved = sum(r["passed"] for r in rows)
    total_usd = sum(r["dollars"] for r in rows)
    lat = [r["latency_s"] for r in rows]
    return {
        "tasks": n,
        "passed": solved,
        "pass_rate": solved / n if n else 0.0,
        "mean_input_tokens": statistics.mean(r["input_tokens"] for r in rows),
        "mean_output_tokens": statistics.mean(r["output_tokens"] for r in rows),
        "mean_usd_per_task": total_usd / n,
        "usd_per_solved_task": total_usd / solved if solved else None,
        "tokens_per_solved_task": (
            sum(r["input_tokens"] + r["output_tokens"] for r in rows) / solved if solved else None
        ),
        "total_usd": total_usd,
        "mean_latency_s": statistics.mean(lat),
        "median_latency_s": statistics.median(lat),
        "mean_model_calls": statistics.mean(r["model_calls"] for r in rows),
        "mean_tool_calls": statistics.mean(r["tool_calls"] for r in rows),
        "summarization_calls": sum(r.get("summarization_calls", 0) for r in rows),
        "classifier_calls": sum(r.get("classifier_calls", 0) for r in rows),
        "blocked_tool_calls": sum(r.get("blocked_tool_calls", 0) for r in rows),
        "run_errors": sum(bool(r.get("error")) for r in rows),
        "unpriced_calls": sum(r.get("unpriced_calls", 0) for r in rows),
        "user_sim_usd_tau2": (
            sum(r.get("user_sim_cost_tau2") or 0 for r in rows)
            if rows[0]["env"] == "tau3"
            else None
        ),
    }


def fmt_usd(x: float | None) -> str:
    return "n/a" if x is None else f"${x:.5f}"


def md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def build() -> None:
    runs = load_runs()
    if not runs:
        raise SystemExit("No results under reports/article-a1/. Run make a1-custom / make a1-tau3.")
    lines = [
        "# Article A1 results",
        "",
        "**Every number in this directory is a single run** (one trial per task). "
        "Article A4 adds repeated trials and variance. Do not read differences between rows "
        "as effects without repeats.",
        "",
        f"Generated {now()} by `scripts/report_a1.py` from the `results.jsonl` and `run.json` "
        "files next to this README. Raw traces (all messages and every model and tool call, "
        "failed runs included) are in each `traces.jsonl`.",
        "",
        "Tokens are the provider-reported usage of each response (`usage_metadata`). "
        "Dollars are tokens × the per-token price of the pinned OpenRouter endpoint "
        "(see `versions.json`), including the Jev classifier calls. "
        "`openrouter_billed_cost` in the rows is OpenRouter's own billed cost for the chat "
        "calls and is a cross-check. τ³ latency is tau2's simulation duration and includes "
        "the user simulator.",
        "",
        "## Summary (single run)",
        "",
        "| env | spec | model | pass | pass rate | mean in tok | mean out tok | mean $/task "
        "| $/solved task | mean latency s | mean model calls | mean tool calls |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    summaries = []
    for r in runs:
        s = summarize(r["rows"])
        spec = r["run"]["spec"]
        summaries.append(
            {"dir": str(r["dir"]), "spec": spec["name"], "model": spec["model"]["id"], **s}
        )
        lines.append(
            f"| {r['rows'][0]['env']} | {spec['name']} | `{spec['model']['id']}` "
            f"| {s['passed']}/{s['tasks']} | {s['pass_rate']:.0%} "
            f"| {s['mean_input_tokens']:.0f} | {s['mean_output_tokens']:.0f} "
            f"| {fmt_usd(s['mean_usd_per_task'])} | {fmt_usd(s['usd_per_solved_task'])} "
            f"| {s['mean_latency_s']:.1f} | {s['mean_model_calls']:.1f} | {s['mean_tool_calls']:.1f} |"
        )
    lines += [
        "",
        "| env | spec | summarization calls | Jev classifier calls | writes blocked by Jev "
        "| run errors | unpriced calls | user-simulator $ (tau2) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s, r in zip(summaries, runs, strict=True):
        lines.append(
            f"| {r['rows'][0]['env']} | {s['spec']} | {s['summarization_calls']} "
            f"| {s['classifier_calls']} | {s['blocked_tool_calls']} | {s['run_errors']} "
            f"| {s['unpriced_calls']} | {fmt_usd(s['user_sim_usd_tau2'])} |"
        )

    for r in runs:
        spec = r["run"]["spec"]
        env = r["rows"][0]["env"]
        lines += [
            "",
            f"## {env} / {spec['name']} (`{spec['model']['id']}`), single run",
            "",
            f"Files: `{r['dir']}/`",
            "",
            "| task | result | reason | in tok | out tok | $ | latency s | model calls | tool calls |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for row in r["rows"]:
            lines.append(
                f"| {row['task_id']} | {'pass' if row['passed'] else 'FAIL'} "
                f"| {md_escape(row['reason'])[:300]} | {row['input_tokens']} | {row['output_tokens']} "
                f"| {fmt_usd(row['dollars'])} | {row['latency_s']:.1f} | {row['model_calls']} "
                f"| {row['tool_calls']} |"
            )

    (REPORT / "README.md").write_text("\n".join(lines) + "\n")

    uv = subprocess.run(["uv", "--version"], capture_output=True, text=True).stdout.strip()
    prices = {}
    for r in runs:
        for p in r["run"].get("prices_usd_per_token", []):
            prices[f"{p['model_id']}@{p['provider_tag']}"] = p
    versions = {
        "generated_at": now(),
        "label": "single run",
        "python": platform.python_version(),
        "uv": uv,
        "packages": packages(),
        "git": git_sha(),
        "tau2": {
            "repo": "sierra-research/tau2-bench",
            "commit": TAU2_COMMIT,
            "note": TAU2_TAG_NOTE,
        },
        "runs": [
            {
                "dir": str(r["dir"]),
                "env": r["rows"][0]["env"],
                "spec": r["run"]["spec"]["name"],
                "spec_source": r["run"]["spec"].get("source"),
                "model": r["run"]["spec"]["model"]["id"],
                "model_provider": r["run"]["spec"]["model"]["settings"].get("provider"),
                "classifier_models": [
                    m["model"]
                    for m in r["run"]["spec"]["middleware"]
                    if m["type"] == "TypeSafeAutoMode"
                ],
                "user_llm": r["run"].get("user_llm"),
                "started_at": r["run"].get("started_at") or r["run"].get("collected_at"),
                "git_at_run": r["run"].get("git"),
            }
            for r in runs
        ],
        "prices_usd_per_token": prices,
        "summaries": summaries,
    }
    (REPORT / "versions.json").write_text(json.dumps(versions, indent=2) + "\n")
    print(f"wrote {REPORT / 'README.md'} and versions.json")


if __name__ == "__main__":
    build()

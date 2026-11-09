"""Evaluate the support assistant's designs with harness-evals.

    python -m evaluator regrade                  # offline: grade the saved runs, write the report
    python -m evaluator agreement                # offline: the graders against hand labels
    python -m evaluator compare BASE CANDIDATE [--split new] [--level judge]
    python -m evaluator live --trials 5 SPEC ... # paid: new runs, graded as they finish

Designs by spec name: a3-do-nothing (0), a1-plain (1), a2-agent-approval (2),
a2-workflow (3), a2-router (4), a2-code (5).
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from harness_evals import (
    Episode,
    agreement,
    compare,
    gate_failures,
    pareto,
    run,
    save,
    summarize,
)
from harness_evals.report import comparison, frontier_svg, table

from envs.custom.tasks import TASKS_BY_ID
from evaluator.episodes import REPO, SAVED, _jsonl, adapter, saved
from evaluator.support import LEVELS, NO_FALSE_HOLD, usecase

DESIGNS = {
    "a3-do-nothing": "0 do nothing",
    "a1-plain": "1 plain agent",
    "a2-agent-approval": "2 agent with approval middleware",
    "a2-workflow": "3 agent inside a workflow",
    "a2-router": "4 router and three agents",
    "a2-code": "5 workflow with no agent",
}
BATCH = {"dev": "known", "new": "new"}
# The frontier plots: success with the judge against each of these.
AXES = {"cost_per_task": ("cost", "$ per task"), "latency_p95": ("latency", "p95 latency")}
BATCH_DIR = {"k10": "known", "oot": "new"}  # folder names in the labels
FROZEN = {"model": "openai/gpt-6-luna", "endpoint": "openrouter, provider openai, no fallbacks"}


def grades(split: str, level: str, spec: str):
    return usecase(level).grade(saved(BATCH[split], spec))


def specs(split: str) -> list[str]:
    return [s for s in DESIGNS if (SAVED / BATCH[split] / s).exists()]


def regrade(out: Path) -> dict:
    report: dict = {"frozen": FROZEN, "splits": {}}
    lines = ["# Part 4: the saved runs, graded by harness-evals", "", _ABOUT, ""]
    for split in ("dev", "new"):
        uc = usecase("obligations")
        by_level = {lv: {s: grades(split, lv, s) for s in specs(split)} for lv in LEVELS}
        sums = {
            lv: {s: summarize(gs, uc.metrics) for s, gs in d.items()} for lv, d in by_level.items()
        }
        name = "16 known tasks, 10 runs" if split == "dev" else "32 new messages, 5 runs"
        lines += [f"## {name}", "", "Success by grader (share of task runs that pass):", ""]
        lines += [
            "| Design | State only | Obligations | Obligations and judge |",
            "|---|---|---|---|",
        ]
        for s in specs(split):
            cells = [_success(sums[lv][s]) for lv in LEVELS]
            lines.append(f"| {DESIGNS[s]} | " + " | ".join(cells) + " |")
        lines += ["", "Every required metric, graded on obligations:", ""]
        lines.append(
            table({DESIGNS[s]: v for s, v in sums["obligations"].items()}, list(uc.metrics))
        )
        lines += ["", "Misses the bar (`gates` in evaluator/support.py):", ""]
        for s, v in sums["obligations"].items():
            lines.append(f"- {DESIGNS[s]}: {'; '.join(gate_failures(v, uc.gates)) or 'nothing'}")
        lines += ["", *_frontier(split, name, sums, out)]
        if split == "dev":
            lines += ["", *_single_runs(by_level["obligations"])]
        lines.append("")
        report["splits"][split] = {
            lv: {s: _jsonable(v) for s, v in d.items()} for lv, d in sums.items()
        }
        report["frontier"] = report.get("frontier", {}) | {
            split: {
                lv: {x: pareto(sums[lv], x, "success") for x in AXES}
                for lv in ("obligations", "judge")
            }
        }
    lines += ["## Comparisons", ""]
    for base, cand, split, level in COMPARISONS:
        c = compare(usecase(level), grades(split, level, base), grades(split, level, cand))
        lines += [f"{split}, {level}: " + comparison(c).replace("\n", " "), ""]
        report.setdefault("comparisons", []).append(
            {
                "base": base,
                "candidate": cand,
                "split": split,
                "level": level,
                "diff": c.diff,
                "ci": c.ci,
                "deltas": c.deltas,
                "decision": c.decision,
                "reasons": c.reasons,
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n")
    (out / "summary.json").write_text(json.dumps(report, indent=1) + "\n")
    return report


COMPARISONS = [  # (base, candidate, split, level)
    ("a2-agent-approval", "a2-workflow", "dev", "obligations"),
    ("a1-plain", "a2-code", "dev", "obligations"),
    ("a1-plain", "a2-code", "new", "judge"),
    ("a1-plain", "a2-router", "dev", "obligations"),
    # The four in the article: the decision changes with the checks and with the tasks.
    ("a1-plain", "a2-agent-approval", "dev", "state"),
    ("a1-plain", "a2-agent-approval", "dev", "obligations"),
    ("a2-workflow", "a2-code", "dev", "obligations"),
    ("a2-workflow", "a2-code", "new", "obligations"),
]

_ABOUT = """\
Generated by `python -m evaluator regrade` from the runs under `known/` and `new/`, made on
2026-10-15 with `openai/gpt-6-luna` on OpenRouter's OpenAI endpoint (no fallbacks) and graded
here without new model calls. The database check of these runs ran in the runner's process;
the refunds come from the refund service's record of each case. Judge verdicts are TypeSafe
Jev (`typesafe/jev-1.13-20260917`, judge v2), saved next to each run in `judge.jsonl`.
Intervals are 95% bootstrap intervals over tasks."""


def _success(s: dict) -> str:
    lo, hi = s["success_ci"]
    return f"{s['success']:.2f} ({lo:.2f}–{hi:.2f})"


def _frontier(split: str, name: str, sums: dict, out: Path) -> list[str]:
    """Designs no other design beats on both success and cost, or success and latency,
    and a plot of each with intervals on both axes."""
    lines = [
        "The frontier: designs that no other design beats on both success and the other",
        "metric. The plots show every design with the judge, with 95% intervals over tasks.",
        "",
        "| Graded on | Success against | Designs on the frontier | Plot |",
        "|---|---|---|---|",
    ]
    for level in ("obligations", "judge"):
        for x, (slug, label) in AXES.items():
            front = ", ".join(DESIGNS[s] for s in pareto(sums[level], x, "success"))
            plot = ""
            if level == "judge":
                plot = f"frontier-{BATCH[split]}-{slug}.svg"
                labelled = {DESIGNS[s]: v for s, v in sums[level].items()}
                title = f"{name}, with the judge: success against {label}"
                (out / plot).write_text(frontier_svg(labelled, x, "success", title=title))
                plot = f"[{plot}]({plot})"
            lines.append(f"| {level} | {label} | {front} | {plot} |")
    return lines


def _single_runs(by_spec: dict) -> list[str]:
    """What one run would have shown: success and cost of each of the 10 runs."""
    out = [
        "What a single run would have shown (obligations; each of the 10 runs alone):",
        "",
        "| Design | Success, run 1 | Success, worst to best run | $ per task, cheapest to dearest run |",
        "|---|---|---|---|",
    ]
    for s, gs in by_spec.items():
        runs = sorted({g.episode.trial for g in gs})
        rate = {r: statistics.fmean(g.passed for g in gs if g.episode.trial == r) for r in runs}
        cost = {
            r: statistics.fmean(g.episode.cost_usd or 0 for g in gs if g.episode.trial == r)
            for r in runs
        }
        out.append(
            f"| {DESIGNS[s]} | {rate[0]:.2f} | {min(rate.values()):.2f} to {max(rate.values()):.2f}"
            f" | ${min(cost.values()):.5f} to ${max(cost.values()):.5f} |"
        )
    return out


def _jsonable(s: dict) -> dict:
    return json.loads(json.dumps(s))  # tuples become lists


def labels_agreement() -> dict:
    """Both judge versions and the held-reply check against the labelled replies, and
    how often each judge version read an action into a reply that should change nothing
    (see labels/README.md)."""
    versions = {
        (r["run"], r["task_id"]): r for r in _jsonl(SAVED / "labels" / "judge-versions.jsonl")
    }
    out: dict = {}
    for sample in ("judge-check.jsonl", "judge-check-2.jsonl"):
        rows = list(_jsonl(SAVED / "labels" / sample))
        verdicts = []
        for r in rows:
            batch, spec, name = Path(r["folder"]).parts[-3:]
            verdicts.append(versions[(f"{BATCH_DIR[batch]}/{spec}/{name}", r["task_id"])])
        held = []  # only where the check applies: after an issued refund
        for r in rows:
            e = Episode(
                r["task_id"], reply=r["reply"], actions=_refund_actions(r["refund_operations"])
            )
            if e.actions:
                held.append((NO_FALSE_HOLD(e), not r["label_says_held"]))
        out[sample] = {
            "judge v1 outcome vs label": agreement(
                [(v["v1"], r["label_outcome"]) for v, r in zip(verdicts, rows, strict=True)]
            ),
            "judge v2 outcome vs label": agreement(
                [(v["v2"], r["label_outcome"]) for v, r in zip(verdicts, rows, strict=True)]
            ),
            "held-reply check vs label": agreement(held),
            "labelled by": sorted({r.get("labelled_by", "?") for r in rows}),
        }
    # Replies to tasks that must change nothing, from runs that changed nothing: an
    # "action" verdict there is a judge error, with no label needed.
    n = {"replies": 0, "v1 action": 0, "v2 action": 0}
    for (run_id, task_id), v in versions.items():
        if v["v2"] == "none" or TASKS_BY_ID[task_id].expected != "no_write":
            continue
        kind, rest = run_id.split("/", 1)
        folder = (
            REPO / "reports" / "article-a2" / "custom" / rest if kind == "part3" else SAVED / run_id
        )
        row = next(x for x in _jsonl(folder / "results.jsonl") if x["task_id"] == task_id)
        if row["passed"]:
            n["replies"] += 1
            n["v1 action"] += v["v1"] == "action"
            n["v2 action"] += v["v2"] == "action"
    out["action read into a reply that changed nothing"] = n
    return out


def _refund_actions(ops):
    from evaluator.episodes import _refunds

    return [a for a in _refunds(ops) if a.name == "refund"]


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m evaluator")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("regrade")
    sub.add_parser("agreement")
    c = sub.add_parser("compare")
    c.add_argument("base")
    c.add_argument("candidate")
    c.add_argument("--split", choices=["dev", "new"], default="dev")
    c.add_argument("--level", choices=LEVELS, default="obligations")
    lv = sub.add_parser("live")
    lv.add_argument("specs", nargs="+", help="spec files, e.g. harness/spec/plain.yaml")
    lv.add_argument("--trials", type=int, default=5)
    lv.add_argument("--split", choices=["dev", "new"], default="dev")
    a = p.parse_args()

    if a.cmd == "regrade":
        regrade(SAVED)
        print((SAVED / "RESULTS.md").read_text())
    elif a.cmd == "agreement":
        print(json.dumps(labels_agreement(), indent=1))
    elif a.cmd == "compare":
        uc = usecase(a.level)
        print(
            comparison(
                compare(uc, grades(a.split, a.level, a.base), grades(a.split, a.level, a.candidate))
            )
        )
    else:
        out = SAVED / "live" / time.strftime("%Y%m%d-%H%M%S")
        uc = usecase("obligations")
        harnesses = {Path(s).stem: adapter(s, out / "runs") for s in a.specs}
        episodes = run(uc, harnesses, trials=a.trials, frozen=FROZEN, split=a.split, out=out)
        gs = uc.grade(episodes)
        sums = {
            h: summarize([g for g in gs if g.episode.harness == h], uc.metrics) for h in harnesses
        }
        print(table(sums, list(uc.metrics)))
        save(episodes, out / "episodes.jsonl")


if __name__ == "__main__":
    main()

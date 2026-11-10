"""Evaluate the support assistant's designs with harness-evals.

    python -m evaluator regrade                  # offline: grade the saved runs, write the report
    python -m evaluator agreement                # offline: the graders against the labels
    python -m evaluator compare BASE CANDIDATE [--split new] [--level judge]
    python -m evaluator failures DESIGN [--split new] [--level judge]
    python -m evaluator show DESIGN TASK [--run 1] [--split new] [--level judge]
    python -m evaluator live --trials 5 SPEC ... # paid: new runs, graded as they finish

Name a design by its number in the articles or by its spec name: 0 a3-do-nothing,
1 a1-plain, 2 a2-agent-approval, 3 a2-workflow, 4 a2-router, 5 a2-code.
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
    comparison,
    failure_map_svg,
    failures,
    frontier_svg,
    gate_failures,
    pareto,
    run,
    save,
    summarize,
    table,
)

from envs.custom.tasks import TASKS_BY_ID
from evaluator.episodes import REPO, SAVED, _jsonl, adapter, saved
from evaluator.support import LEVELS, NO_FALSE_HOLD, OUTCOME, usecase

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


NUMBERS = {label.split()[0]: spec for spec, label in DESIGNS.items()}  # "3" -> "a2-workflow"


def design(name: str | int) -> str:
    """A design's spec name, from its number in the articles (0 to 5) or the spec name."""
    spec = NUMBERS.get(str(name), str(name))
    if spec not in DESIGNS and not any((SAVED / b / spec).exists() for b in BATCH.values()):
        raise SystemExit(f"unknown design {name!r}; use 0 to 5 or one of: {', '.join(DESIGNS)}")
    return spec


def grades(split: str, level: str, spec: str | int):
    return usecase(level).grade(saved(BATCH[split], design(spec)))


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
        lines += ["", *_failure_maps(split, name, by_level["judge"], out)]
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
        c = _compare(base, cand, split, level)
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


def _compare(base: str | int, cand: str | int, split: str, level: str):
    """A paired comparison of two saved designs, named as in the articles."""
    base, cand = design(base), design(cand)
    c = compare(usecase(level), grades(split, level, base), grades(split, level, cand))
    c.base, c.candidate = DESIGNS.get(base, base), DESIGNS.get(cand, cand)
    return c


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
    for slug, label in AXES.values():
        lines += [
            "",
            f"![{name}: success with the judge against {label}](frontier-{BATCH[split]}-{slug}.svg)",
        ]
    return lines


def _failure_maps(split: str, name: str, by_spec: dict, out: Path) -> list[str]:
    """Where each design fails, graded with the judge: tasks in rows, and in one panel per
    design, the kinds of check or the runs in columns."""
    links = []
    for by in ("checks", "runs"):
        plot = f"failures-{BATCH[split]}-by-{by[:-1]}.svg"
        title = f"{name}, with the judge: where each design fails, by {by[:-1]}"
        grades = {DESIGNS[s]: gs for s, gs in by_spec.items()}
        (out / plot).write_text(failure_map_svg(usecase("judge"), grades, by=by, title=title))
        links.append(f"[by {by[:-1]}]({plot})")
    return [
        "Where each design fails, graded with the judge: " + ", ".join(links) + ".",
        "",
        f"![{name}: failed runs for each task and kind of check](failures-{BATCH[split]}-by-check.svg)",
    ]


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


def failing(spec: str | int, split: str, level: str) -> list[str]:
    """One line per task a design fails: which checks, and in how many of its runs."""
    gs = grades(split, level, spec)
    runs = len({g.episode.trial for g in gs})
    return [
        f"{task}: failed "
        + "; ".join(f"{check} in {n} of {runs} runs" for check, n in checks.items())
        for task, checks in failures(gs).items()
    ] or ["no failures"]


def show(spec: str | int, task_id: str, split: str, level: str, run_no: int) -> str:
    """One saved run as the evaluator saw it: the message, the recorded actions, the
    reply, and the verdict of every check."""
    spec = design(spec)
    task = next((t for t in usecase(level).split(split) if t.id == task_id), None)
    if task is None:
        ids = ", ".join(t.id for t in usecase(level).split(split))
        raise SystemExit(f"no task {task_id!r} in split {split!r}; tasks: {ids}")
    found = [e for e in saved(BATCH[split], spec) if e.task_id == task_id and e.trial == run_no - 1]
    if not found:
        raise SystemExit(f"no run {run_no} of {task_id} for {DESIGNS.get(spec, spec)}")
    e = found[0]
    marks = {True: "PASS", False: "FAIL", None: "UNDECIDED"}
    acts = [f"{a.name} {a.args}" for a in e.actions]
    lines = [
        f"{DESIGNS.get(spec, spec)} · {task_id} · run {run_no} · {BATCH[split]} tasks",
        "",
        f"Customer: {task.input}",
        "",
        "Recorded by the refund service: " + ("; ".join(acts) or "nothing"),
        "",
        f"Reply: {e.reply or '(no reply)'}",
        "",
        "Checks:",
        *(
            f"  {marks[v if v is None else bool(v)]:<9} {c.name}"
            for c in task.checks
            if (v := c(e)) or True
        ),
        "",
        f"Expected outcome: {OUTCOME[task_id]}. The judge read: {e.extra.get('judge_outcome')}.",
    ]
    return "\n".join(lines)


def _headline(report: dict) -> str:
    """What regrade prints: where the report went, and success with the judge."""
    lines = [
        f"Wrote {SAVED.relative_to(REPO)}/RESULTS.md, summary.json, 4 frontier plots and 4 failure maps.",
        "",
    ]
    for split, name in (("dev", "16 known tasks"), ("new", "32 new messages")):
        lines.append(f"Success with the judge, {name}:")
        for spec, s in report["splits"][split]["judge"].items():
            lo, hi = s["success_ci"]
            lines.append(f"  {DESIGNS[spec]:<34} {s['success']:.2f} ({lo:.2f}–{hi:.2f})")
    return "\n".join(lines)


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
    f = sub.add_parser("failures")
    f.add_argument("design")
    w = sub.add_parser("show")
    w.add_argument("design")
    w.add_argument("task")
    w.add_argument("--run", type=int, default=1)
    for cmd in (c, f, w):
        cmd.add_argument("--split", choices=["dev", "new"], default="dev")
        cmd.add_argument("--level", choices=LEVELS, default="obligations")
    lv = sub.add_parser("live")
    lv.add_argument("specs", nargs="+", help="spec files, e.g. harness/spec/plain.yaml")
    lv.add_argument("--trials", type=int, default=5)
    lv.add_argument("--split", choices=["dev", "new"], default="dev")
    a = p.parse_args()

    if a.cmd == "regrade":
        print(_headline(regrade(SAVED)))
    elif a.cmd == "failures":
        print("\n".join(failing(a.design, a.split, a.level)))
    elif a.cmd == "show":
        print(show(a.design, a.task, a.split, a.level, a.run))
    elif a.cmd == "agreement":
        print(json.dumps(labels_agreement(), indent=1))
    elif a.cmd == "compare":
        print(comparison(_compare(a.base, a.candidate, a.split, a.level)))
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

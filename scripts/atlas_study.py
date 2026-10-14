"""Repeated runs for the Harness Atlas: five designs x four harness layers, k trials each.

    uv run python scripts/atlas_study.py --trials 5                  # custom tasks, all cells
    uv run python scripts/atlas_study.py --trials 5 --only autonomous_agent
    uv run python scripts/atlas_study.py --tau3 --trials 5           # τ³ retail, two layers
    uv run python scripts/atlas_study.py --dry-run                   # print the plan only

Every cell is one spec file run on the same task set, the same model and the same
environment as the other cells. A trial is one full run of the suite (one try per task),
written to its own folder:

    reports/atlas-study/custom/<design>/<layer>/trial-<n>/   results.jsonl, traces.jsonl, run.json
    reports/atlas-study/tau3/<layer>/trial-<n>/

The runner and the environments are the same code the articles used (envs.custom.run,
envs.tau3). This script only chooses specs, trial numbers and output folders. Trials of
one spec run one after another (the runner names its scratch folder by spec and second);
different specs run in parallel. An existing trial folder is skipped, so an interrupted
study resumes where it stopped.

Layers (SGR on/off x write guard on/off):
- base:                 native tool calling, no SGR, no write guard
- sgr_only:             Schema-Guided Reasoning, no write guard
- guard_only:           native tool calling and the Jev write guard
- sgr_plus_write_guard: Schema-Guided Reasoning and the Jev write guard

The workflow with no agent (plain_workflow) has no agent loop, so the agent layers do not
apply to it; it runs in the base cell only. On τ³-bench the benchmark executes the tools,
so the write guard never runs there; τ³ has the base and sgr_only cells only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "atlas-study"

# design -> layer -> spec. Missing layers are not applicable to that design.
CUSTOM: dict[str, dict[str, str]] = {
    "plain_workflow": {
        "base": "harness/spec/workflows/support-code.yaml",
    },
    "router": {
        "base": "harness/spec/workflows/support-router.yaml",
        "sgr_only": "harness/spec/atlas/support-router-sgr.yaml",
        "guard_only": "harness/spec/atlas/support-router-guard.yaml",
        "sgr_plus_write_guard": "harness/spec/atlas/support-router-sgr-guard.yaml",
    },
    "agent_in_workflow": {
        "base": "harness/spec/workflows/refund-approval.yaml",
        "sgr_only": "harness/spec/atlas/refund-approval-sgr.yaml",
        "guard_only": "harness/spec/atlas/refund-approval-guard.yaml",
        "sgr_plus_write_guard": "harness/spec/atlas/refund-approval-sgr-guard.yaml",
    },
    "agent_with_approval": {
        "base": "harness/spec/approval-agent.yaml",
        "sgr_only": "harness/spec/atlas/approval-agent-sgr.yaml",
        "guard_only": "harness/spec/atlas/approval-agent-guard.yaml",
        "sgr_plus_write_guard": "harness/spec/atlas/approval-agent-sgr-guard.yaml",
    },
    "autonomous_agent": {
        "base": "harness/spec/plain.yaml",
        "sgr_only": "harness/spec/atlas/agent-sgr.yaml",
        "guard_only": "harness/spec/atlas/agent-guard.yaml",
        "sgr_plus_write_guard": "harness/spec/base.yaml",
    },
}

# τ³: the single agent through the adapter. base.yaml configures the guard, but τ³ runs
# the tools, so its only active difference from plain.yaml is SGR.
TAU3: dict[str, str] = {
    "base": "harness/spec/plain.yaml",
    "sgr_only": "harness/spec/base.yaml",
}


def custom_jobs(
    trials: int, only: set[str], layers_wanted: set[str]
) -> list[tuple[str, list[tuple[list[str], Path]]]]:
    """One job per spec: its trials in order, each (command, output folder)."""
    jobs = []
    for design, layers in CUSTOM.items():
        if only and design not in only:
            continue
        for layer, spec in layers.items():
            if layers_wanted and layer not in layers_wanted:
                continue
            runs = []
            for n in range(1, trials + 1):
                out = OUT / "custom" / design / layer / f"trial-{n}"
                cmd = [
                    *("uv", "run", "--frozen", "python", "-m", "envs.custom.run"),
                    *("--suite", "a2", "--spec", spec, "--out", str(out)),
                ]
                runs.append((cmd, out))
            jobs.append((f"{design}/{layer}", runs))
    return jobs


def tau3_jobs(trials: int) -> list[tuple[str, list[tuple[list[str], Path]]]]:
    runs = []
    for layer, spec in TAU3.items():
        for n in range(1, trials + 1):
            out = OUT / "tau3" / layer / f"trial-{n}"
            cmd = ["make", "--no-print-directory", "atlas-tau3", f"SPEC={spec}", f"OUT={out}"]
            runs.append((cmd, out))
    # τ³ trials share the tau2 data folder and its simulations/ names: run them in order.
    return [("tau3", runs)]


def run_job(name: str, runs: list[tuple[list[str], Path]], dry_run: bool) -> list[str]:
    failed = []
    for cmd, out in runs:
        if (out / "results.jsonl").exists():
            print(f"[{name}] skip {out.relative_to(REPO)} (exists)", flush=True)
            continue
        print(f"[{name}] {' '.join(cmd)}", flush=True)
        if dry_run:
            continue
        log = out.parent / f"{out.name}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "w") as f:
            code = subprocess.call(cmd, cwd=REPO, stdout=f, stderr=subprocess.STDOUT)
        if code != 0 or not (out / "results.jsonl").exists():
            failed.append(f"{out.relative_to(REPO)} (exit {code}, log {log.relative_to(REPO)})")
            print(f"[{name}] FAILED {out.relative_to(REPO)}; see {log.name}", flush=True)
        else:
            log.unlink()  # the run's own files are the record; keep logs of failures only
            print(f"[{name}] done {out.relative_to(REPO)}", flush=True)
    return failed


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--trials", type=int, default=5)
    p.add_argument("--tau3", action="store_true", help="run the τ³ cells instead of custom")
    p.add_argument("--only", default="", help="comma-separated designs (custom only)")
    p.add_argument("--layers", default="", help="comma-separated layers (custom only)")
    p.add_argument("--parallel", type=int, default=3, help="specs run at the same time")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    only = {s for s in args.only.split(",") if s}
    if unknown := only - set(CUSTOM):
        raise SystemExit(f"unknown designs: {sorted(unknown)}")
    layers = {s for s in args.layers.split(",") if s}
    jobs = tau3_jobs(args.trials) if args.tau3 else custom_jobs(args.trials, only, layers)
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        results = list(pool.map(lambda j: run_job(j[0], j[1], args.dry_run), jobs))
    failed = [f for r in results for f in r]
    for f in failed:
        print(f"FAILED {f}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

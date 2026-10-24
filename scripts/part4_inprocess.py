"""Part 4: one candidate graded by the Parts 2–3 runner and by the external evaluator.

    uv run python scripts/part4_inprocess.py --profile docker --out reports/part-4/in-process.json

The candidates are fixture specs (``harness/spec/fixtures/``) with a model that never
replies, so no model is called. ``tamper-checks`` rewrites the task checks when its
middleware is constructed; ``write-state`` writes the requested refund straight into the
database the runner checks. The Parts 2–3 runner runs them in its own process, where both
work. The external evaluator runs the same files in a container that has neither the
checks nor the database.

The in-process runs happen in a child process, because ``tamper-checks`` changes the
checks for the rest of whatever process imports it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPECS = ["harness/spec/fixtures/tamper-checks.yaml", "harness/spec/fixtures/write-state.yaml"]


async def in_process(spec_path: str) -> list[dict]:
    from envs.custom.db import create_seed
    from envs.custom.run import Target, run_task
    from envs.custom.tasks import SUITES
    from harness.spec import load_any

    target = await Target.build(load_any(spec_path))
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        seed = create_seed(Path(tmp) / "seed.sqlite")
        for task in SUITES["part4"]:
            row, _ = await run_task(target, task, seed, Path(tmp) / task.id, [])
            rows.append({"task": task.id, "passed": row["passed"], "reason": row["reason"]})
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--profile", default="docker", choices=["docker", "local"])
    p.add_argument("--out", type=Path)
    p.add_argument("--child", help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.child:
        print(json.dumps(asyncio.run(in_process(args.child))))
        return

    from envs.custom.tasks import SUITES
    from evaluator.runner import capture
    from evaluator.support import HARNESS_FILES, evaluate

    report = []
    for spec in SPECS:
        child = subprocess.run(
            [sys.executable, __file__, "--child", spec], capture_output=True, text=True, cwd=ROOT
        )
        if child.returncode != 0:
            raise SystemExit(child.stderr)
        old = json.loads(child.stdout.strip().splitlines()[-1])
        artifact = capture(ROOT, HARNESS_FILES, "targets/harness_target.py", spec, (spec,))
        new = [
            evaluate(t, artifact, profile=args.profile, trusted=True, timeout_s=120)
            for t in SUITES["part4"]
        ]
        row = {
            "spec": spec,
            "candidate_sha256": artifact.sha256,
            "in_process_state_check_passed": sum(r["passed"] for r in old),
            "evaluator_state_only_passed": sum(r["verdict"]["state_only"] for r in new),
            "evaluator_obligations_passed": sum(r["verdict"]["obligations"] for r in new),
            "tasks": len(old),
            "profile": args.profile,
            "in_process": old,
            "evaluator": [
                {
                    "task": r["task"]["id"],
                    "state_only": r["verdict"]["state_only"],
                    "obligations": r["verdict"]["obligations"],
                    "termination": r["termination"],
                    "state_reason": r["details"]["state_reason"],
                }
                for r in new
            ],
        }
        report.append(row)
        print(
            f"{spec}: in-process {row['in_process_state_check_passed']}/{row['tasks']}, "
            f"evaluator state-only {row['evaluator_state_only_passed']}/{row['tasks']}, "
            f"obligations {row['evaluator_obligations_passed']}/{row['tasks']}"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

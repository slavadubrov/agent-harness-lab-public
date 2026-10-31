"""Turn runs of the support assistant into harness-evals episodes.

Two sources:

- ``saved``: the runs under ``reports/part-4/`` (10 runs of the 16 known tasks, 5 runs of
  the 32 new messages, made on 2026-10-15). Their database check ran inside the runner's
  process, next to the harness, and the refunds come from the refund service's record.
- ``live``: ``adapter(spec)`` starts the runner in a separate process for each trial, keeps
  every task's start and final database, and reads them here. The database check, the
  refunds and the held operations are computed in this process from those files, not
  taken from what the runner reports.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from harness_evals import Action, Episode, Task

from envs.custom.db import diff
from envs.custom.tasks import TASKS_BY_ID
from evaluator.support import OUTCOME

REPO = Path(__file__).resolve().parents[1]
SAVED = REPO / "reports" / "part-4"
STATUS = {"completed": "completed", "waiting for approval": "waiting", "error": "error"}
# Errors that come from the provider or the network, not from the harness under test.
INFRA = re.compile(
    r"APIConnection|RateLimit|Timeout|InternalServerError|ServiceUnavailable|\b5\d\d\b"
)


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if path.exists():
        with open(path) as f:
            yield from (json.loads(line) for line in f if line.strip())


def _refunds(ops: list[dict[str, Any]]) -> list[Action]:
    """The refund service's record: an issued operation is a refund, a held one is not."""
    out = []
    for op in ops:
        _case, _, order, cents = op["op_key"].rsplit(":", 3)
        name = "refund" if op["status"] == "issued" else f"refund_{op['status']}"
        out.append(
            Action(name, {"order": order, "cents": int(cents), "refund_id": op["refund_id"]})
        )
    return out


def _episode(row: dict[str, Any], **kw: Any) -> Episode:
    error = row["error"]
    return Episode(
        task_id=row["task_id"],
        status=STATUS.get(row["outcome"], row["outcome"]),
        reply=row["final_answer"] or None,
        cost_usd=None if row["unpriced_calls"] else row["dollars"],
        latency_s=row["latency_s"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        model_calls=row["model_calls"],
        error=error,
        infra_error=bool(error and INFRA.search(error)),
        **kw,
    )


def saved(batch: str, spec: str) -> list[Episode]:
    """Episodes of one design from a saved batch: ``known`` or ``new``."""
    episodes = []
    for run in sorted((SAVED / batch / spec).glob("r*")):
        trial = int(run.name[1:]) - 1
        verdicts = {v["task_id"]: v for v in _jsonl(run / "judge.jsonl")}
        models = {
            c["model"]
            for t in _jsonl(run / "traces.jsonl")
            for c in t.get("model_calls", [])
            if c.get("model")
        }
        for row in _jsonl(run / "results.jsonl"):
            v = verdicts.get(row["task_id"])
            episodes.append(
                _episode(
                    row,
                    harness=spec,
                    trial=trial,
                    actions=_refunds(row["refund_operations"]),
                    state_ok=row["passed"],
                    models=sorted(models),
                    judgements={"outcome": v["outcome"] == OUTCOME[row["task_id"]] if v else None},
                    extra={"judge_outcome": v["outcome"] if v else None, "run": run.name},
                )
            )
    return episodes


# -- live runs ---------------------------------------------------------------------------


def observe(start: Path, final: Path, task_id: str) -> tuple[bool, list[Action]]:
    """Read one task's databases in this process: the environment's state check, every
    refund row the run added (however it was written), and the operations the refund
    service still holds or rejected for the case."""
    passed = TASKS_BY_ID[task_id].check(start, final).passed
    actions = [
        Action("refund", {"order": r["order_id"], "cents": r["amount_cents"], "refund_id": r["id"]})
        for r in diff(start, final)["refunds"].added
    ]
    con = sqlite3.connect(f"file:{final}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        ops = con.execute(
            "SELECT * FROM refund_operations WHERE case_id = ? AND status != 'issued'", (task_id,)
        ).fetchall()
    finally:
        con.close()
    return passed, actions + _refunds([dict(o) for o in ops])


def adapter(spec: str, root: Path, env: dict[str, str] | None = None):
    """A harness-evals adapter that runs ``spec`` on the given tasks in a new process."""

    def run_tasks(tasks: list[Task], trial: int) -> list[Episode]:
        episodes = []
        for suite in ("a2", "oot"):
            ids = [t.id for t in tasks if (t.split == "dev") == (suite == "a2")]
            if not ids:
                continue
            out = root / Path(spec).stem / f"t{trial:02d}" / suite
            cmd = [sys.executable, "-m", "envs.custom.run", "--spec", spec, "--suite", suite]
            cmd += ["--tasks", ",".join(ids), "--out", str(out / "report")]
            cmd += ["--workdir", str(out / "db"), "--concurrency", "4"]
            subprocess.run(cmd, cwd=REPO, env={**os.environ, **(env or {})}, check=True)
            for row in _jsonl(out / "report" / "results.jsonl"):
                db = out / "db" / row["task_id"]
                passed, actions = observe(db / "start.sqlite", db / "final.sqlite", row["task_id"])
                episodes.append(_episode(row, state_ok=passed, actions=actions))
        return episodes

    return run_tasks

"""Turn a tau2 results.json plus the adapter traces into A1 report rows.

    python -m envs.tau3.collect --save-to a1-retail-a1-base --out reports/article-a1/tau3/a1-base

Pass/fail and the reason come from τ³'s own reward (it replays the tool calls in a fresh
environment and compares the database). Tokens and dollars for the agent come from the
adapter's recorder (provider usage). The user simulator's cost is reported separately,
as tau2 recorded it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from harness.agent import spec_prices
from harness.runinfo import TAU2_COMMIT, TAU2_TAG_NOTE, git_sha, now, packages
from harness.spec import REPO_ROOT, load_spec


def _reason(sim: dict) -> str:
    ri = sim.get("reward_info") or {}
    parts = [f"reward={ri.get('reward')}"]
    db = ri.get("db_check") or {}
    if db:
        parts.append(f"db_match={db.get('db_match')}")
    if ri.get("reward_breakdown"):
        parts.append(f"breakdown={ri['reward_breakdown']}")
    parts.append(f"termination={sim.get('termination_reason')}")
    return "; ".join(parts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--save-to", required=True, help="the --save-to name given to tau2 run")
    p.add_argument("--traces", required=True, help="adapter trace JSONL")
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--user-llm", required=True)
    p.add_argument("--command", default="")
    args = p.parse_args()

    data = Path(os.environ.get("TAU2_DATA_DIR", REPO_ROOT / ".cache" / "tau2-bench" / "data"))
    results_path = data / "simulations" / args.save_to / "results.json"
    results = json.loads(results_path.read_text())
    traces = {}
    for line in Path(args.traces).read_text().splitlines():
        t = json.loads(line)
        traces[t["task_id"]] = t  # one trial per task in A1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for sim in results["simulations"]:
        tid = sim["task_id"]
        tr = traces.get(tid, {})
        tot = tr.get("totals", {})
        msgs = sim.get("messages") or []
        tool_calls = sum(
            len(m.get("tool_calls") or []) for m in msgs if m.get("role") == "assistant"
        )
        reward = (sim.get("reward_info") or {}).get("reward")
        rows.append(
            {
                "env": "tau3",
                "task_id": tid,
                "passed": reward == 1.0,
                "reward": reward,
                "reason": _reason(sim),
                "error": None if tr else "no adapter trace for this task",
                "input_tokens": tot.get("input_tokens", 0),
                "output_tokens": tot.get("output_tokens", 0),
                "reasoning_tokens": tot.get("reasoning_tokens", 0),
                "dollars": round(tot.get("dollars", 0.0), 8),
                "openrouter_billed_cost": round(tot.get("openrouter_cost", 0.0), 8),
                "latency_s": round(sim.get("duration") or 0.0, 3),
                "model_calls": tot.get("model_calls", 0),
                "failed_model_calls": tot.get("failed_calls", 0),
                "agent_model_calls": tot.get("agent_model_calls", 0),
                "summarization_calls": tot.get("summarization_calls", 0),
                "classifier_calls": tot.get("classifier_calls", 0),
                "tool_calls": tool_calls,
                "harness_executed_tool_calls": tot.get("tool_calls", 0),
                "unpriced_calls": tot.get("unpriced_calls", 0),
                "tau2_agent_cost": sim.get("agent_cost"),
                "user_sim_cost_tau2": sim.get("user_cost"),
                "termination_reason": sim.get("termination_reason"),
            }
        )

    with open(out / "results.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    shutil.copyfile(args.traces, out / "traces.jsonl")
    shutil.copyfile(results_path, out / "tau2_results.json")
    spec = load_spec(args.spec)
    (out / "run.json").write_text(
        json.dumps(
            {
                "env": "tau3",
                "label": "single run",
                "collected_at": now(),
                "tau2_commit": TAU2_COMMIT,
                "tau2_note": TAU2_TAG_NOTE,
                "domain": "retail",
                "tasks": [r["task_id"] for r in rows],
                "user_llm": args.user_llm,
                "command": args.command,
                "spec": spec.model_dump(mode="json"),
                "prices_usd_per_token": [asdict(p) for p in spec_prices(spec)],
                "packages": packages(),
                "git": git_sha(),
            },
            indent=2,
        )
    )
    passed = sum(r["passed"] for r in rows)
    print(f"{spec.name} on tau3 retail: {passed}/{len(rows)} passed (single run) -> {out}")


if __name__ == "__main__":
    main()

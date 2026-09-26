"""Run the harness on the custom customer-account environment (single run per task).

    python -m envs.custom.run --spec harness/spec/base.yaml

Per task: fresh database copy -> one agent run -> state check on the final database.
Writes results.jsonl (one row per task), traces.jsonl (full messages and every model and
tool call, failed runs included) and run.json (spec, prices, versions) to
reports/article-a1/custom/<spec name>/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, messages_to_dict

from envs.custom.db import create_seed, fresh_copy
from envs.custom.tasks import TASKS, CheckResult, Task
from envs.custom.tools import WRITE_TOOLS, AccountContext
from harness.accounting import UsageRecorder
from harness.agent import build_harness, spec_prices
from harness.env import load_api_key
from harness.runinfo import git_sha, now, packages
from harness.spec import REPO_ROOT, load_spec

BUILD = REPO_ROOT / "build" / "custom"
REPORTS = REPO_ROOT / "reports" / "article-a1" / "custom"


def _blocked(messages) -> int:
    return sum(
        1
        for m in messages
        if isinstance(m, ToolMessage)
        and m.status == "error"
        and str(m.content).startswith("The tool call `")
        and "was blocked" in str(m.content)
    )


async def run_task(agent, task: Task, seed: Path, workdir: Path, prices) -> tuple[dict, dict]:
    start = fresh_copy(seed, workdir / "start.sqlite", task.setup_sql)
    work = workdir / "final.sqlite"
    shutil.copyfile(start, work)

    rec = UsageRecorder(prices)
    config = {
        "configurable": {"thread_id": task.id},
        "callbacks": [rec],
        "recursion_limit": 100,
    }
    error = None
    messages = []
    t0 = time.perf_counter()
    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=task.user_message)]},
            config=config,
            context=AccountContext(db_path=work),
        )
        messages = result["messages"]
    except Exception as exc:  # keep failed runs
        error = f"{type(exc).__name__}: {exc}"
        try:
            messages = (await agent.aget_state(config)).values.get("messages", [])
        except Exception:
            messages = []
    latency = time.perf_counter() - t0

    check = task.check(start, work)
    if error:
        check = CheckResult(False, f"run error ({error}); state check: {check.reason}")

    totals = rec.totals()
    proposed = [c for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]
    final = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), None
    )
    row = {
        "env": "custom",
        "task_id": task.id,
        "expected": task.expected,
        "passed": check.passed,
        "reason": check.reason,
        "error": error,
        "input_tokens": totals.input_tokens,
        "output_tokens": totals.output_tokens,
        "reasoning_tokens": totals.reasoning_tokens,
        "dollars": round(totals.dollars, 8),
        "openrouter_billed_cost": round(totals.openrouter_cost, 8),
        "latency_s": round(latency, 3),
        "model_calls": totals.model_calls,
        "failed_model_calls": totals.failed_calls,
        "agent_model_calls": totals.agent_model_calls,
        "summarization_calls": totals.summarization_calls,
        "classifier_calls": totals.classifier_calls,
        "tool_calls": totals.tool_calls,
        "proposed_tool_calls": len(proposed),
        "write_tool_calls_proposed": sum(c["name"] in WRITE_TOOLS for c in proposed),
        "blocked_tool_calls": _blocked(messages),
        "unpriced_calls": totals.unpriced_calls,
        "final_answer": final.text if final else None,
    }
    trace = {
        "env": "custom",
        "task_id": task.id,
        "user_message": task.user_message,
        "check": asdict(check),
        "error": error,
        "messages": messages_to_dict(messages),
        **rec.dump(),
    }
    return row, trace


async def main_async(args) -> int:
    load_api_key()
    spec = load_spec(args.spec)
    prices = spec_prices(spec)
    wanted = args.tasks.split(",") if args.tasks else [t.id for t in TASKS]
    if unknown := set(wanted) - {t.id for t in TASKS}:
        raise SystemExit(f"unknown task ids: {sorted(unknown)}")
    tasks = [t for t in TASKS if t.id in wanted]
    run_dir = BUILD / f"{spec.name}-{time.strftime('%Y%m%d-%H%M%S')}"
    # A --tasks run is partial: it writes to build/ unless --out says otherwise, so it
    # never replaces the committed full-run files in reports/.
    default_out = run_dir if args.tasks else REPORTS / spec.name
    out = (Path(args.out) if args.out else default_out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    seed = create_seed(run_dir / "seed.sqlite")

    agent = await build_harness(spec)
    started = now()
    sem = asyncio.Semaphore(args.concurrency)

    async def one(task: Task):
        async with sem:
            return await run_task(agent, task, seed, run_dir / task.id, prices)

    pairs = await asyncio.gather(*(one(t) for t in tasks))
    rows = [r for r, _ in pairs]

    with open(out / "results.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(out / "traces.jsonl", "w") as f:
        for _, t in pairs:
            f.write(json.dumps(t, ensure_ascii=False, default=str) + "\n")
    (out / "run.json").write_text(
        json.dumps(
            {
                "env": "custom",
                "label": "single run",
                "started_at": started,
                "finished_at": now(),
                "spec": spec.model_dump(mode="json"),
                "prices_usd_per_token": [asdict(p) for p in prices],
                "packages": packages(),
                "git": git_sha(),
                "tasks": [t.id for t in tasks],
            },
            indent=2,
        )
    )

    print(f"\n{spec.name} on custom ({len(rows)} tasks, single run)")
    print(
        f"{'task':34} {'pass':5} {'in_tok':>7} {'out_tok':>7} {'usd':>9} {'lat_s':>6} {'calls':>5} {'tools':>5}"
    )
    for r in rows:
        print(
            f"{r['task_id']:34} {'PASS' if r['passed'] else 'FAIL':5} {r['input_tokens']:7d} "
            f"{r['output_tokens']:7d} {r['dollars']:9.5f} {r['latency_s']:6.1f} "
            f"{r['model_calls']:5d} {r['tool_calls']:5d}"
        )
    passed = sum(r["passed"] for r in rows)
    print(f"pass rate {passed}/{len(rows)}; total ${sum(r['dollars'] for r in rows):.5f}")
    for r in rows:
        if not r["passed"]:
            print(f"  FAIL {r['task_id']}: {r['reason']}")
    print(f"wrote {out}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--spec", default="harness/spec/base.yaml")
    p.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    p.add_argument("--out", default="")
    p.add_argument("--concurrency", type=int, default=4)
    raise SystemExit(asyncio.run(main_async(p.parse_args())))


if __name__ == "__main__":
    main()

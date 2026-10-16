"""Run an agent or workflow spec on the custom customer-account environment.

    python -m envs.custom.run --spec harness/spec/plain.yaml               # Part 2 set (16)
    python -m envs.custom.run --spec harness/spec/base.yaml --suite a1     # Part 1 set (12)
    python -m envs.custom.run --spec harness/spec/workflows/refund-approval.yaml

Per task: fresh database copy -> one run -> state check on the final database.

The runner treats every spec the same way:
- If the run pauses for an approval (a LangGraph interrupt), the scripted supervisor
  records the task's decision in the refund service and resumes the run. A task with no
  scripted decision stays paused, as a real case would until a supervisor answers.
- If the run raises, the runner resumes it once from its last checkpoint, as a recovery
  worker would after a crash. The error is kept in the row either way.

Writes results.jsonl (one row per task), traces.jsonl (messages, every model and tool
call, approval and error events) and run.json (spec, prices, versions) to
reports/article-<suite>/custom/<spec name>/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, messages_to_dict
from langgraph.types import Command

from envs.custom.approval import supervise
from envs.custom.db import create_seed, fresh_copy
from envs.custom.refunds import operations
from envs.custom.tasks import SUITES, CheckResult, Task
from envs.custom.tools import WRITE_TOOLS, AccountContext
from harness.accounting import UsageRecorder
from harness.agent import build_harness, spec_prices
from harness.env import load_api_key
from harness.runinfo import git_sha, now, packages
from harness.spec import REPO_ROOT, HarnessSpec, WorkflowSpec, load_any
from harness.workflow import assemble, get_engine, workflow_prices

BUILD = REPO_ROOT / "build" / "custom"
MAX_RESUMES = 4  # approval pauses plus one recovery; a run needing more is an error


class Target:
    """An agent or a workflow, with what the runner needs to read back its messages."""

    def __init__(self, graph: Any, agents: dict[str, Any] | None = None, workflow=False):
        self.graph, self.agents, self.is_workflow = graph, agents or {}, workflow

    @classmethod
    async def build(cls, spec: HarnessSpec | WorkflowSpec) -> Target:
        if isinstance(spec, WorkflowSpec):
            built = await assemble(spec)
            return cls(get_engine(spec).compile(built), built.agents, workflow=True)
        return cls(await build_harness(spec))

    def inputs(self, task: Task) -> dict[str, Any]:
        if self.is_workflow:
            return {"request": task.user_message}
        return {"messages": [HumanMessage(content=task.user_message)]}

    async def messages(self, thread_id: str, out: dict[str, Any] | None) -> list:
        """The agent's messages: the run output for an agent, each inner agent's
        checkpoint for a workflow."""
        if not self.is_workflow:
            if out and "messages" in out:
                return out["messages"]
            try:
                state = await self.graph.aget_state({"configurable": {"thread_id": thread_id}})
                return state.values.get("messages", [])
            except Exception:
                return []
        msgs: list = []
        for name, agent in self.agents.items():
            cfg = {"configurable": {"thread_id": f"{thread_id}/{name}"}}
            msgs += (await agent.aget_state(cfg)).values.get("messages", [])
        return msgs


def _blocked(messages) -> int:
    return sum(
        1
        for m in messages
        if isinstance(m, ToolMessage)
        and m.status == "error"
        and str(m.content).startswith("The tool call `")
        and "was blocked" in str(m.content)
    )


async def drive(target: Target, task: Task, ctx: AccountContext, config: dict) -> dict[str, Any]:
    """Run one task to its end: completed, paused for approval, or failed."""
    events: list[dict[str, Any]] = []
    inputs: Any = target.inputs(task)
    out: dict[str, Any] | None = None
    recovered = False
    for _ in range(MAX_RESUMES + 1):
        try:
            out = await target.graph.ainvoke(inputs, config=config, context=ctx)
        except Exception as exc:
            events.append({"event": "error", "error": f"{type(exc).__name__}: {exc}"})
            if recovered:
                return {"outcome": "error", "out": None, "events": events}
            recovered = True
            events.append({"event": "resume after error"})
            inputs = None
            continue
        interrupts = out.get("__interrupt__") or []
        if not interrupts:
            return {"outcome": "completed", "out": out, "events": events}
        payload = interrupts[0].value
        events.append({"event": "approval requested", "request": payload})
        if task.approval is None:
            return {"outcome": "waiting for approval", "out": out, "events": events}
        inputs = Command(resume=supervise(ctx, payload, task.approval))
        events.append({"event": f"supervisor: {task.approval}"})
    events.append({"event": "error", "error": "too many resumes"})
    return {"outcome": "error", "out": out, "events": events}


def _final_answer(target: Target, out: dict[str, Any] | None, messages: list) -> str | None:
    if target.is_workflow and out:
        return out.get("reply") or out.get("answer") or None
    final = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), None
    )
    return final.text if final else None


async def run_task(target, task: Task, seed: Path, workdir: Path, prices) -> tuple[dict, dict]:
    if not isinstance(target, Target):  # an agent graph from build_harness
        target = Target(target)
    start = fresh_copy(seed, workdir / "start.sqlite", task.setup_sql)
    work = workdir / "final.sqlite"
    shutil.copyfile(start, work)

    rec = UsageRecorder(prices)
    config = {
        "configurable": {"thread_id": task.id},
        "callbacks": [rec],
        "recursion_limit": 100,
    }
    ctx = AccountContext(db_path=work, case_id=task.id, fault=task.fault)
    t0 = time.perf_counter()
    result = await drive(target, task, ctx, config)
    latency = time.perf_counter() - t0
    messages = await target.messages(task.id, result["out"])

    errors = [e["error"] for e in result["events"] if e["event"] == "error"]
    error = errors[-1] if result["outcome"] == "error" else None
    check = task.check(start, work)
    if error:
        check = CheckResult(False, f"run error ({error}); state check: {check.reason}")

    totals = rec.totals()
    proposed = [c for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]
    row = {
        "env": "custom",
        "task_id": task.id,
        "expected": task.expected,
        "passed": check.passed,
        "reason": check.reason,
        "outcome": result["outcome"],
        "error": error,
        "resumes_after_error": sum(e["event"] == "resume after error" for e in result["events"]),
        "approval_requests": sum(e["event"] == "approval requested" for e in result["events"]),
        "refund_operations": [
            {k: op[k] for k in ("op_key", "status", "refund_id")}
            for op in operations(work, task.id)
        ],
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
        "final_answer": _final_answer(target, result["out"], messages),
    }
    out = result["out"] or {}
    trace = {
        "env": "custom",
        "task_id": task.id,
        "user_message": task.user_message,
        "check": asdict(check),
        "error": error,
        "events": result["events"],
        "workflow_state": (
            {k: v for k, v in out.items() if k != "__interrupt__"} if target.is_workflow else None
        ),
        "messages": messages_to_dict(messages),
        **rec.dump(),
    }
    return row, trace


async def main_async(args) -> int:
    load_api_key()
    spec = load_any(args.spec)
    prices = workflow_prices(spec) if isinstance(spec, WorkflowSpec) else spec_prices(spec)
    suite = SUITES[args.suite]
    wanted = args.tasks.split(",") if args.tasks else [t.id for t in suite]
    if unknown := set(wanted) - {t.id for t in suite}:
        raise SystemExit(f"unknown task ids for suite {args.suite}: {sorted(unknown)}")
    tasks = [t for t in suite if t.id in wanted]
    run_dir = BUILD / f"{spec.name}-{time.strftime('%Y%m%d-%H%M%S')}"
    # A --tasks run is partial: it writes to build/ unless --out says otherwise, so it
    # never replaces the committed full-run files in reports/.
    reports = REPO_ROOT / "reports" / f"article-{args.suite}" / "custom"
    default_out = run_dir if args.tasks else reports / spec.name
    out = (Path(args.out) if args.out else default_out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    seed = create_seed(run_dir / "seed.sqlite")

    target = await Target.build(spec)
    started = now()
    sem = asyncio.Semaphore(args.concurrency)

    async def one(task: Task):
        async with sem:
            return await run_task(target, task, seed, run_dir / task.id, prices)

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
                "suite": args.suite,
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
        f"{'task':42} {'pass':5} {'outcome':20} {'in_tok':>7} {'out_tok':>7} {'usd':>9} "
        f"{'lat_s':>6} {'calls':>5}"
    )
    for r in rows:
        print(
            f"{r['task_id']:42} {'PASS' if r['passed'] else 'FAIL':5} {r['outcome']:20} "
            f"{r['input_tokens']:7d} {r['output_tokens']:7d} {r['dollars']:9.5f} "
            f"{r['latency_s']:6.1f} {r['model_calls']:5d}"
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
    p.add_argument("--spec", default="harness/spec/plain.yaml")
    p.add_argument("--suite", choices=sorted(SUITES), default="a2")
    p.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    p.add_argument("--out", default="")
    p.add_argument("--concurrency", type=int, default=4)
    raise SystemExit(asyncio.run(main_async(p.parse_args())))


if __name__ == "__main__":
    main()

"""Export the Agent or Workflow Atlas data from the run reports.

    make atlas-export      # CONTRACT ?= ../notes/packages/explainer_contract

Reads reports/article-a2 (the Part 2 runs, one run per design, and both routers) and
reports/article-a3 (repeated runs, the out-of-template set, router repeats, judge
verdicts). Writes atlas/data/{tasks,designs,runs,traces,aggregates,routes}.json,
atlas/data/manifest.json and atlas/schema/*.json.

The record models come from the blog's explainer_contract package, so the blog build
validates exactly what this file writes. That package is not public; the files are.

Every record built from a run carries its run id (<batch>/<spec name>/r<NN>), commit,
spec hash, models, price table and provenance. The Part 2 runs recorded no event times;
their traces are rebuilt from the messages and marked "rebuilt".
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Final, Literal, TypedDict

from explainer_contract.atlas import (
    Aggregate,
    AggregatesFile,
    Batch,
    DataFile,
    Design,
    DesignsFile,
    Event,
    FileModel,
    JudgeVerdict,
    Manifest,
    Probability,
    RefundOperation,
    ReplyChecks,
    RouteResult,
    RoutesFile,
    RunsFile,
    RunSummary,
    Source,
    Task,
    TaskResult,
    TasksFile,
    Trace,
    TracesFile,
)
from explainer_contract.export_schema import schemas
from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from envs.custom.replies import judge_path, no_false_hold, refund_id_in_reply
from envs.custom.tasks import OOT_TASKS, SUITES, TASKS, TASKS_BY_ID
from harness.accounting import load_price_table
from harness.runinfo import spec_hash
from harness.spec import (
    REPO_ROOT,
    AgentNodeSpec,
    ClassifierNodeSpec,
    HarnessSpec,
    StructuredNodeSpec,
    WorkflowSpec,
    load_any,
    load_spec,
)

REPORTS = REPO_ROOT / "reports"
OUT = REPO_ROOT / "atlas"
REPO_URL = "https://github.com/slavadubrov/agent-harness-lab-public"
PINNED = "harness/prices/openrouter-2026-10-05.json"
# spec name -> (design id, name on screen, spec file)
DESIGNS: dict[str, tuple[int, str, str]] = {
    "a3-do-nothing": (0, "Do nothing", "harness/spec/workflows/do-nothing.yaml"),
    "a1-plain": (1, "Plain agent", "harness/spec/plain.yaml"),
    "a2-agent-approval": (2, "Agent with approval middleware", "harness/spec/approval-agent.yaml"),
    "a2-workflow": (3, "Agent inside a workflow", "harness/spec/workflows/refund-approval.yaml"),
    "a2-router": (4, "Router and three agents", "harness/spec/workflows/support-router.yaml"),
    "a2-code": (5, "Workflow with no agent", "harness/spec/workflows/support-code.yaml"),
    "a3-hybrid": (
        6,
        "Hybrid: workflow for known requests, agent for the rest",
        "harness/spec/workflows/hybrid.yaml",
    ),
}
EXPECTED_STATES: Final = ("write", "no_write", "partial")
CATEGORIES: Final = ("known", "vague", "two_requests", "policy", "unusual")
JUDGE_OUTCOMES: Final = ("action", "question", "refusal", "handoff", "answer", "none")
JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


# -- the lab's files, typed ---------------------------------------------------------------


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RawOp(_Raw):
    op_key: str
    status: Literal["held", "approved", "rejected", "issued"]
    refund_id: int | None


class RawRow(_Raw):
    task_id: str
    passed: bool
    reason: str
    outcome: Literal["completed", "waiting for approval", "error"]
    final_answer: str | None
    refund_operations: list[RawOp]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None = None
    dollars: float
    openrouter_billed_cost: float | None = None
    latency_s: float
    model_calls: int
    tool_calls: int
    approval_requests: int = 0
    resumes_after_error: int = 0


class RawModelCall(_Raw):
    kind: str
    node: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    dollars: float | None
    latency_s: float
    response_id: str | None
    error: str | None = None
    failed: bool = False
    t_start: float | None = None


class RawToolCall(_Raw):
    name: str
    latency_s: float
    error: str | None = None
    t_start: float | None = None
    args: JsonValue = None
    output: str | None = None


class RawNodeCall(_Raw):
    name: str
    t_start: float
    latency_s: float
    error: str | None = None


class RawEvent(_Raw):
    event: str
    t: float | None = None
    error: str | None = None


class RawToolRequest(_Raw):
    name: str
    args: JsonValue = None


class RawMeta(_Raw):
    id: str | None = None


class RawMessageData(_Raw):
    content: JsonValue = ""
    tool_calls: list[RawToolRequest] = []
    name: str | None = None
    response_metadata: RawMeta = RawMeta()


class RawMessage(_Raw):
    type: str
    data: RawMessageData


class RawState(_Raw):
    answer: str = ""
    reply: str = ""
    route: str = ""
    route_confidence: float | None = None


class RawTrace(_Raw):
    task_id: str
    user_message: str
    events: list[RawEvent] = []
    workflow_state: RawState | None = None
    messages: list[RawMessage] = []
    model_calls: list[RawModelCall] = []
    tool_calls: list[RawToolCall] = []
    node_calls: list[RawNodeCall] = []


class RawGit(_Raw):
    sha: str
    dirty: bool | None = None


class RawPrice(_Raw):
    model_id: str
    provider_tag: str
    prompt: float
    completion: float
    input_cache_read: float = 0.0
    input_cache_write: float = 0.0


class RawRun(_Raw):
    started_at: dt.datetime
    spec: dict[str, JsonValue]
    git: RawGit
    prices_usd_per_token: list[RawPrice]
    spec_hash: str | None = None
    price_table: str | None = None
    run: int | None = None


class RawJudge(_Raw):
    task_id: str
    model: str
    outcome: str
    outcome_confidence: float | None = None
    outcome_probabilities: dict[str, float] = {}
    says_held: float | None = None


class RawRoute(_Raw):
    label: Literal["refund", "account", "other", "unclear"]
    request: str
    choice: str
    confidence: float
    probabilities: dict[str, float]


def read_jsonl[M: BaseModel](path: Path, model: type[M]) -> list[M]:
    return [model.model_validate_json(line) for line in path.read_text().splitlines() if line]


# -- provenance ---------------------------------------------------------------------------


class MeasuredFields(TypedDict):
    run_id: str
    git_sha: str
    spec_hash: str
    models: list[str]
    price_table: str
    provenance: Literal["measured"]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def last_commit(path: str) -> str:
    return git("log", "-1", "--format=%H", "--", path)


def spec_of(data: dict[str, JsonValue]) -> HarnessSpec | WorkflowSpec:
    if data.get("kind") == "workflow":
        return WorkflowSpec.model_validate(data)
    return HarnessSpec.model_validate(data)


def models_of(spec: HarnessSpec | WorkflowSpec) -> list[str]:
    if isinstance(spec, HarnessSpec):
        return [spec.model.id] if spec.model.provider == "openrouter" else []
    found: list[str] = []
    for node in spec.nodes.values():
        if isinstance(node, ClassifierNodeSpec):
            found.append(node.model)
        elif isinstance(node, StructuredNodeSpec):
            found.append(node.model.id)
        elif isinstance(node, AgentNodeSpec):
            found += models_of(load_spec(node.agent.spec, node.agent.override or None))
    return sorted(set(found))


def price_table_of(meta: RawRun) -> str:
    """The run's pinned table; a Part 2 run must have recorded the same prices."""
    if meta.price_table:
        return meta.price_table
    version, pinned = load_price_table(PINNED)
    table = {(p.model_id, p.provider_tag): p for p in pinned}
    for p in meta.prices_usd_per_token:
        q = table[p.model_id, p.provider_tag]
        recorded = (p.prompt, p.completion, p.input_cache_read, p.input_cache_write)
        if recorded != (q.prompt, q.completion, q.input_cache_read, q.input_cache_write):
            raise ValueError(f"{p.model_id}: recorded prices differ from {version}")
    return version


def measured(meta: RawRun, run_id: str) -> MeasuredFields:
    spec_data = {k: v for k, v in meta.spec.items() if k != "source"}
    return {
        "run_id": run_id,
        "git_sha": meta.git.sha,
        "spec_hash": meta.spec_hash or spec_hash(spec_data),
        "models": models_of(spec_of(meta.spec)),
        "price_table": price_table_of(meta),
        "provenance": "measured",
    }


# -- runs ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunFolder:
    batch: Batch
    spec_name: str
    run: int
    meta: RawRun
    rows: list[RawRow]
    traces: dict[str, RawTrace]
    judge: dict[str, RawJudge]

    @property
    def run_id(self) -> str:
        return f"{self.batch}/{self.spec_name}/r{self.run:02d}"

    @property
    def design(self) -> int:
        return DESIGNS[self.spec_name][0]

    @classmethod
    def read(cls, batch: Batch, folder: Path) -> RunFolder:
        meta = RawRun.model_validate_json((folder / "run.json").read_text())
        judged = judge_path(folder)
        return cls(
            batch=batch,
            spec_name=str(meta.spec["name"]),
            run=meta.run or 1,
            meta=meta,
            rows=read_jsonl(folder / "results.jsonl", RawRow),
            traces={t.task_id: t for t in read_jsonl(folder / "traces.jsonl", RawTrace)},
            judge={j.task_id: j for j in read_jsonl(judged, RawJudge)} if judged.exists() else {},
        )


def run_folders(batches: list[Batch]) -> list[RunFolder]:
    found: list[RunFolder] = []
    for batch in batches:
        if batch == "a2":
            folders = sorted(REPORTS.glob("article-a2/custom/*/run.json"))
        else:
            folders = sorted(REPORTS.glob(f"article-a3/custom/{batch}/*/r*/run.json"))
        found += [RunFolder.read(batch, f.parent) for f in folders]
    return sorted(found, key=lambda f: (f.batch, f.design, f.run))


def text_of(content: JsonValue) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and isinstance(text := block.get("text"), str):
                parts.append(text)
        return "".join(parts)
    return ""


def verdict(j: RawJudge | None) -> JudgeVerdict | None:
    if j is None:
        return None
    outcome = j.outcome
    if outcome not in JUDGE_OUTCOMES:
        raise ValueError(f"judge outcome {outcome!r} for {j.task_id}")
    return JudgeVerdict(
        model=j.model,
        outcome=outcome,
        outcome_confidence=j.outcome_confidence,
        outcome_probabilities=[
            Probability(label=k, probability=v) for k, v in sorted(j.outcome_probabilities.items())
        ],
        says_held=j.says_held,
    )


def cache_read(row: RawRow, trace: RawTrace) -> int:
    if row.cache_read_tokens is not None:
        return row.cache_read_tokens
    return sum(c.cache_read_tokens for c in trace.model_calls if not c.failed)


def task_result(f: RunFolder, row: RawRow) -> TaskResult:
    ops = [
        {"op_key": op.op_key, "status": op.status, "refund_id": op.refund_id}
        for op in row.refund_operations
    ]
    judge = verdict(f.judge.get(row.task_id))
    expected = TASKS_BY_ID[row.task_id].outcome
    return TaskResult(
        **measured(f.meta, f.run_id),
        batch=f.batch,
        design=f.design,
        run=f.run,
        task_id=row.task_id,
        passed=row.passed,
        reason=row.reason,
        outcome=row.outcome,
        reply=row.final_answer,
        refund_operations=[
            RefundOperation(op_key=op.op_key, status=op.status, refund_id=op.refund_id)
            for op in row.refund_operations
        ],
        reply_checks=ReplyChecks(
            no_false_hold=no_false_hold(row.final_answer, ops),
            refund_id_in_reply=refund_id_in_reply(row.final_answer, ops),
        ),
        judge=judge,
        expected_outcome_met=None if judge is None else row.passed and judge.outcome == expected,
        model_calls=row.model_calls,
        input_tokens=row.input_tokens,
        cache_read_tokens=cache_read(row, f.traces[row.task_id]),
        output_tokens=row.output_tokens,
        tool_calls=row.tool_calls,
        approval_requests=row.approval_requests,
        resumes_after_error=row.resumes_after_error,
        dollars=row.dollars,
        billed_dollars=row.openrouter_billed_cost,
        latency_s=row.latency_s,
    )


def run_summary(f: RunFolder, results: list[TaskResult]) -> RunSummary:
    billed = [r.billed_dollars for r in results]
    return RunSummary(
        **measured(f.meta, f.run_id),
        batch=f.batch,
        design=f.design,
        run=f.run,
        started_at=f.meta.started_at,
        tasks=len(results),
        passed=sum(r.passed for r in results),
        dollars=sum(r.dollars for r in results),
        billed_dollars=None if None in billed else sum(b or 0.0 for b in billed),
        input_tokens=sum(r.input_tokens for r in results),
        cache_read_tokens=sum(r.cache_read_tokens for r in results),
        model_calls=sum(r.model_calls for r in results),
    )


# -- traces -------------------------------------------------------------------------------


def event(
    type: Literal[
        "message", "model_call", "tool_call", "step", "wait", "approval", "error", "resume", "reply"
    ],
    name: str,
    text: str = "",
    t: float | None = None,
    error: str | None = None,
    latency_s: float | None = None,
    tools: list[str] | None = None,
    call: RawModelCall | None = None,
) -> Event:
    return Event(
        type=type,
        t=None if t is None else round(t, 3),
        name=name,
        text=text,
        tools=tools or [],
        input_tokens=call.input_tokens if call else None,
        cache_read_tokens=call.cache_read_tokens if call else None,
        output_tokens=call.output_tokens if call else None,
        dollars=call.dollars if call else None,
        latency_s=call.latency_s if call else latency_s,
        error=error,
    )


def tool_text(args: JsonValue, output: str | None) -> str:
    text = json.dumps(args, ensure_ascii=False) if args is not None else ""
    return f"{text} -> {output}" if output else text


def runner_event(e: RawEvent) -> Event:
    if e.event == "approval requested":
        return event("wait", "supervisor", "the run waits for the supervisor", t=e.t)
    if e.event.startswith("supervisor: "):
        return event("approval", "supervisor", e.event.removeprefix("supervisor: "), t=e.t)
    if e.event == "resume after error":
        return event("resume", "runner", "the runner resumes the run from its checkpoint", t=e.t)
    return event("error", "runner", e.error or e.event, t=e.t, error=e.error or e.event)


def model_call_event(
    call: RawModelCall | None, msg: RawMessage | None, state: RawState | None, t: float | None
) -> Event:
    tools = [c.name for c in msg.data.tool_calls] if msg else []
    text = text_of(msg.data.content) if msg and tools else ""
    if call and call.kind == "classifier" and state and state.route:
        text = f"{state.route} ({state.route_confidence or 0.0:.2f})"
    name = (call.model or call.node or "model") if call else "model"
    error = call.error if call and call.failed else None
    return event("model_call", name, text, t=t, tools=tools, call=call, error=error)


def recorded_events(tr: RawTrace, row: RawRow) -> list[Event]:
    """Events in the order the run recorded them."""
    ai = {m.data.response_metadata.id: m for m in tr.messages if m.type == "ai"}

    def message(call: RawModelCall) -> RawMessage | None:
        return ai.get(call.response_id) if call.response_id else None

    timed: list[tuple[float, int, Event]] = [
        (0.0, 0, event("message", "customer", tr.user_message, t=0.0))
    ]

    def add(t: float | None, e: Event, order: int | None = None) -> None:
        timed.append((t or 0.0, len(timed) if order is None else order, e))

    state = tr.workflow_state
    for c in tr.model_calls:
        add(c.t_start, model_call_event(c, message(c), state, c.t_start))
    for c in tr.tool_calls:
        text = tool_text(c.args, c.output)
        add(
            c.t_start,
            event("tool_call", c.name, text, t=c.t_start, error=c.error, latency_s=c.latency_s),
        )
    attempts: dict[str, int] = defaultdict(int)
    for n in tr.node_calls:
        if n.error and n.error.startswith("GraphInterrupt"):
            continue  # the node paused for the supervisor: the runner's wait event marks it
        attempts[n.name] += 1
        add(
            n.t_start,
            event(
                "step",
                n.name,
                f"attempt {attempts[n.name]}",
                t=n.t_start,
                error=n.error,
                latency_s=n.latency_s,
            ),
        )
    for e in tr.events:
        add(e.t, runner_event(e))
    waits = [e.t for e in tr.events if e.event == "approval requested"]
    if state and state.answer and state.reply and state.answer != state.reply and waits:
        # The reply written before the pause comes before the wait at the same time.
        add(waits[0], event("reply", "assistant", state.answer, t=waits[0]), order=-1)
    if row.final_answer:
        # Event times are rounded, so the final reply goes last whatever its time says.
        end = max([row.latency_s, *(t for t, _, _ in timed)])
        add(end, event("reply", "assistant", row.final_answer, t=end), order=len(timed) + 10**6)
    return [e for _, _, e in sorted(timed, key=lambda x: (x[0], x[1]))]


def rebuilt_events(tr: RawTrace, row: RawRow, spec_name: str) -> list[Event]:
    """Part 2 traces have no event times: rebuild the order from the messages."""
    events = [event("message", "customer", tr.user_message)]
    state = tr.workflow_state
    agent_nodes = (None, "model")
    for c in tr.model_calls:
        if c.kind == "classifier" or (c.kind == "chat" and c.node not in agent_nodes):
            events.append(model_call_event(c, None, state, None))  # a router or a reader call
    chat = iter(
        [c for c in tr.model_calls if c.kind == "chat" and c.node in agent_nodes and not c.failed]
    )
    pending = list(tr.tool_calls)  # in the order the tools finished

    def take(name: str) -> RawToolCall | None:
        i = next((i for i, c in enumerate(pending) if c.name == name), None)
        return None if i is None else pending.pop(i)

    runner = list(tr.events)
    errors = [e for e in runner if e.event in ("error", "resume after error")]
    approvals = [e for e in runner if e not in errors]
    for m in tr.messages:
        if m.type == "ai":
            events.append(model_call_event(next(chat, None), m, state, None))
            asked_refund = any(c.name == "issue_refund" for c in m.data.tool_calls)
            if spec_name == "a2-agent-approval" and asked_refund and approvals:
                events += [runner_event(e) for e in approvals]  # the pause before the tool
                approvals = []
        elif m.type == "tool":
            raw = take(m.data.name or "")
            if raw is None:
                continue  # a message the middleware added (a rejection): no tool ran
            while raw is not None and raw.error:
                events.append(
                    event("tool_call", raw.name, tool_text(raw.args, None), error=raw.error)
                )
                events += [runner_event(e) for e in errors[:2]]
                errors = errors[2:]
                raw = take(raw.name)
            output = text_of(m.data.content)[:300]
            events.append(
                event(
                    "tool_call",
                    m.data.name or "?",
                    output,
                    latency_s=raw.latency_s if raw else None,
                )
            )
    if state and state.answer and state.reply and state.answer != state.reply:
        events.append(event("reply", "assistant", state.answer))
    events += [runner_event(e) for e in errors + approvals]
    if row.final_answer:
        events.append(event("reply", "assistant", row.final_answer))
    return events


def trace(f: RunFolder, row: RawRow) -> Trace:
    tr = f.traces[row.task_id]
    recorded = (
        any(c.t_start is not None for c in tr.model_calls)
        or bool(tr.node_calls)
        or any(e.t is not None for e in tr.events)
    )
    events = recorded_events(tr, row) if recorded else rebuilt_events(tr, row, f.spec_name)
    return Trace(
        **measured(f.meta, f.run_id),
        batch=f.batch,
        design=f.design,
        run=f.run,
        task_id=row.task_id,
        ordering="recorded" if recorded else "rebuilt",
        events=events,
    )


# -- aggregates ---------------------------------------------------------------------------


def aggregate(
    scope: Literal["task", "category", "set"], key: str, rows: list[TaskResult]
) -> Aggregate:
    first = rows[0]
    if len({(r.git_sha, r.spec_hash, r.price_table) for r in rows}) != 1:
        raise ValueError(f"{first.batch} design {first.design}: runs differ in commit or spec")
    by_task: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        by_task[r.task_id].append(r.passed)
    met = [r.expected_outcome_met for r in rows]
    judged = [m for m in met if m is not None]
    tokens = sum(r.input_tokens for r in rows)
    return Aggregate(
        run_id=first.run_id.rsplit("/", 1)[0],
        git_sha=first.git_sha,
        spec_hash=first.spec_hash,
        models=first.models,
        price_table=first.price_table,
        provenance="measured",
        batch=first.batch,
        design=first.design,
        scope=scope,
        key=key,
        run_ids=sorted({r.run_id for r in rows}),
        task_runs=len(rows),
        passed=sum(r.passed for r in rows),
        pass_rate=sum(r.passed for r in rows) / len(rows),
        pass_hat_k=sum(all(p) for p in by_task.values()) / len(by_task),
        expected_outcome_met=sum(judged) if len(judged) == len(met) else None,
        expected_outcome_rate=sum(judged) / len(met) if len(judged) == len(met) else None,
        model_calls_mean=mean(r.model_calls for r in rows),
        model_calls_median=median(r.model_calls for r in rows),
        input_tokens_mean=mean(r.input_tokens for r in rows),
        input_tokens_median=median(r.input_tokens for r in rows),
        latency_s_mean=mean(r.latency_s for r in rows),
        latency_s_median=median(r.latency_s for r in rows),
        dollars_mean=mean(r.dollars for r in rows),
        dollars_median=median(r.dollars for r in rows),
        cache_read_share=sum(r.cache_read_tokens for r in rows) / tokens if tokens else 0.0,
    )


def aggregates(results: list[TaskResult]) -> list[Aggregate]:
    groups: dict[tuple[str, int], list[TaskResult]] = defaultdict(list)
    for r in results:
        groups[r.batch, r.design].append(r)
    out: list[Aggregate] = []
    for rows in groups.values():
        task_ids = list(dict.fromkeys(r.task_id for r in rows))
        out += [aggregate("task", t, [r for r in rows if r.task_id == t]) for t in task_ids]
        categories = list(dict.fromkeys(TASKS_BY_ID[t].category for t in task_ids))
        if len(categories) > 1:
            out += [
                aggregate("category", c, [r for r in rows if TASKS_BY_ID[r.task_id].category == c])
                for c in categories
            ]
        task_set = "known" if categories == ["known"] else "out_of_template"
        out.append(aggregate("set", task_set, rows))
    return out


# -- routes -------------------------------------------------------------------------------


def routes() -> list[RouteResult]:
    folders = [
        ("a2-route", f.parent) for f in sorted(REPORTS.glob("article-a2/routing/*/run.json"))
    ]
    folders += [
        ("route", f.parent) for f in sorted(REPORTS.glob("article-a3/routing/*/r*/run.json"))
    ]
    out: list[RouteResult] = []
    for batch, folder in folders:
        meta = RawRun.model_validate_json((folder / "run.json").read_text())
        name, run = str(meta.spec["name"]), meta.run or 1
        fields = measured(meta, f"{batch}/{name}/r{run:02d}")
        spec = spec_of(meta.spec)
        if isinstance(spec, WorkflowSpec) and isinstance(
            node := spec.nodes["route"], ClassifierNodeSpec
        ):
            fields["models"] = [node.model]  # these runs call only the router
        out += [
            RouteResult(
                **fields,
                router=name,
                run=run,
                label=r.label,
                request=r.request,
                choice=r.choice,
                confidence=r.confidence,
                probabilities=[
                    Probability(label=k, probability=v) for k, v in sorted(r.probabilities.items())
                ],
            )
            for r in read_jsonl(folder / "results.jsonl", RawRoute)
        ]
    return out


# -- definitions --------------------------------------------------------------------------


def tasks() -> list[Task]:
    source = Source(git_sha=last_commit("envs/custom/tasks.py"), path="envs/custom/tasks.py")
    out: list[Task] = []
    for t in SUITES["a2"] + OOT_TASKS:
        expected, category, outcome = t.expected, t.category, t.outcome
        if expected not in EXPECTED_STATES or category not in CATEGORIES or outcome is None:
            raise ValueError(f"task {t.id}: expected {expected!r}, category {category!r}")
        out.append(
            Task(
                id=t.id,
                task_set="known" if category == "known" else "out_of_template",
                category=category,
                message=t.user_message,
                expected_outcome=outcome,
                expected_state=expected,
                approval=t.approval,
                fault=t.fault,
                part1=t in TASKS,
                source=source,
            )
        )
    return out


def designs(names: set[str]) -> list[Design]:
    out: list[Design] = []
    for name, (design_id, title, path) in DESIGNS.items():
        if name not in names:
            continue
        data = JSON_OBJECT.validate_json(load_any(path).model_dump_json(exclude={"source"}))
        out.append(
            Design(
                id=design_id,
                name=title,
                spec_name=name,
                spec_path=path,
                spec_hash=spec_hash(data),
                models=models_of(spec_of(data)),
                source=Source(git_sha=last_commit(path), path=path),
            )
        )
    return out


# -- the export ---------------------------------------------------------------------------


@dataclass
class Export:
    tasks: list[Task]
    designs: list[Design]
    runs: list[RunSummary]
    results: list[TaskResult]
    traces: list[Trace]
    aggregates: list[Aggregate]
    routes: list[RouteResult]

    @classmethod
    def build(cls, batches: list[Batch]) -> Export:
        folders = run_folders(batches)
        runs: list[RunSummary] = []
        results: list[TaskResult] = []
        traces: list[Trace] = []
        for f in folders:
            rows = [task_result(f, row) for row in f.rows]
            runs.append(run_summary(f, rows))
            results += rows
            traces += [trace(f, row) for row in f.rows]
        return cls(
            tasks=tasks(),
            designs=designs({f.spec_name for f in folders}),
            runs=runs,
            results=results,
            traces=traces,
            aggregates=aggregates(results),
            routes=routes(),
        )

    def files(self) -> dict[str, tuple[FileModel, BaseModel, int]]:
        return {
            "tasks.json": ("TasksFile", TasksFile(tasks=self.tasks), len(self.tasks)),
            "designs.json": ("DesignsFile", DesignsFile(designs=self.designs), len(self.designs)),
            "runs.json": (
                "RunsFile",
                RunsFile(runs=self.runs, results=self.results),
                len(self.runs) + len(self.results),
            ),
            "traces.json": ("TracesFile", TracesFile(traces=self.traces), len(self.traces)),
            "aggregates.json": (
                "AggregatesFile",
                AggregatesFile(aggregates=self.aggregates),
                len(self.aggregates),
            ),
            "routes.json": ("RoutesFile", RoutesFile(results=self.routes), len(self.routes)),
        }

    def write(self, out: Path) -> Manifest:
        data = out / "data"
        data.mkdir(parents=True, exist_ok=True)
        entries: list[DataFile] = []
        for name, (model, content, records) in self.files().items():
            text = content.model_dump_json() + "\n"
            (data / name).write_text(text)
            digest = hashlib.sha256(text.encode()).hexdigest()
            entries.append(DataFile(path=name, model=model, sha256=digest, records=records))
        manifest = Manifest(
            contract="atlas",
            source_repo=REPO_URL,
            source_ref=git("rev-parse", "--abbrev-ref", "HEAD"),
            source_sha=git("rev-parse", "HEAD"),
            exported_at=dt.datetime.now(dt.UTC).replace(microsecond=0),
            files=entries,
        )
        (data / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
        schema_dir = out / "schema"
        schema_dir.mkdir(parents=True, exist_ok=True)
        for name, schema in schemas().items():
            if name.startswith("atlas-"):
                (schema_dir / name).write_text(json.dumps(schema, indent=2) + "\n")
        return manifest


def main() -> None:
    if git("status", "--porcelain", "--", ".", ":(exclude)atlas/data", ":(exclude)atlas/schema"):
        raise SystemExit(
            "Commit every change first: the manifest names the commit the data comes from."
        )
    manifest = Export.build(batches=["a2", "k10", "oot"]).write(OUT)
    for f in manifest.files:
        size = (OUT / "data" / f.path).stat().st_size
        print(f"{f.path:16} {f.records:6d} records {size / 1e6:6.2f} MB")
    print(f"wrote {OUT / 'data'} from {manifest.source_ref} at {manifest.source_sha[:7]}")


if __name__ == "__main__":
    main()

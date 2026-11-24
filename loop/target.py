"""The target of the Part 5 campaign, for harness-loop: what is improved and how it is scored.

- The harness: ``loop/seed/``, the support assistant as a workflow with no agent
  (design 5 of Parts 3 and 4) as a directory an improver may edit.
- The tasks: the 48 tasks of Parts 2 to 4 are the development split, whose failures the
  improver reads. ``loop/tasks.py`` adds 32 validation tasks, which decide whether a
  change is kept, and 32 test tasks, scored once at the end.
- The model: one pinned OpenAI model behind an HTTPS endpoint (``harness/openai_model.py``),
  held fixed for every candidate.

    uv run harness-loop run loop.target:TARGET reports/part-5/support
    uv run harness-loop report loop.target:TARGET reports/part-5/support   # offline
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from harness_evals import Episode, Task
from harness_loop import Target, scrub

import loop  # noqa: F401 - registers the validation and test tasks with the environment
from envs.custom.policy_mcp import POLICIES
from evaluator.episodes import _episode, _jsonl, observe
from harness.openai_model import MODEL, REASONING_EFFORT, URL
from loop.grading import SPLITS, usecase

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "loop" / "seed"
# Every model call of a candidate must be a node of its workflow with exactly this block.
MODEL_BLOCK = {"provider": "import", "id": "openai", "ref": "harness.openai_model:chat"}
# A candidate's own code may not reach a model, the network or another process: model
# calls are workflow nodes, where the runner counts their tokens.
FORBIDDEN = {
    "aiohttp",
    "http",
    "httpx",
    "langchain_openai",
    "langchain_openrouter",
    "langchain_typesafe",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}

BRIEF = """\
The harness is a customer-support assistant of an online shop. It issues refunds, changes
addresses and updates account settings, answers questions about the shop's policy and
hands over what it cannot do. `harness/workflow.yaml` is its workflow; `harness/*.py`
holds the functions the workflow names (`module:function`, with the module next to the
workflow file). `reference/policy.md` is the policy it must follow, and `reference/README.md`
explains how a run works and what the harness may call.

A change is kept only if, on tasks you cannot see, it passes more runs than the current
harness without breaking these limits:

- No forbidden action in any run: no refund that the task does not call for, no second
  refund for one request.
- At most 1,000 more model tokens per task than the current harness, on average.
- Average API cost stays within $0.01 per task.
- The slowest runs (95th percentile) stay under 15 seconds.

Every model call must be a `structured` node in `workflow.yaml` whose `model:` is exactly
`{provider: import, id: openai, ref: "harness.openai_model:chat"}` (pinned to the OpenAI
model `gpt-6.2-sol`, `reasoning_effort: low`, `method: json_schema`). You may change prompts,
add structured nodes or expand Pydantic output schemas, or refine the workflow graph and
Python steps. The Python files must not import a model client, a network library or
`subprocess`.
"""

ABOUT = """\
# What the harness runs in

One run handles one customer message on a fresh copy of the shop's database.

- `harness/workflow.yaml` is a LangGraph workflow: `nodes` and the edges between them.
  `lab/harness/spec.py` defines every key a workflow file may use (`WorkflowSpec` and the
  node types), and `lab/harness/workflow.py` shows how each node type runs.
- A `structured` node makes one model call: it fills `prompt` from the state, asks the
  model for an object of `output_schema` (a Pydantic class, `method: json_schema`) and
  writes its fields to the state.
- A `function` node calls `module:function(state, ctx)` and merges the returned dict into
  the state. `ctx.context` is an `AccountContext` (`lab/envs/custom/tools.py`) with the
  database path of this run.
- The customer sees the state field `reply`, or `answer` when there is no `reply`.
- `lab/envs/custom/db.py` is the database schema and seed data. `lab/envs/custom/tools.py`
  has the account tools. `lab/envs/custom/refunds.py` is the refund service: it holds a
  refund above $200 until a supervisor decides and returns the first receipt when the same
  refund is asked for twice. `lab/envs/custom/approval.py` has the steps that wait for the
  supervisor and reply afterwards.
- The files under `lab/` are the environment. They are shown for reference and cannot be
  changed; the harness may import them.

A run is graded on what the database and the refund service recorded and on what the
reply states, never on what the harness says it did.
"""


def adapter(harness: Path):
    """Run the harness in ``harness`` on the given tasks in a new process, then read each
    task's databases here, outside it."""

    def run_tasks(tasks: list[Task], trial: int) -> list[Episode]:
        with tempfile.TemporaryDirectory(prefix="support-run-") as tmp:
            out = Path(tmp)
            cmd = [sys.executable, "-m", "loop.run", "--spec", str(harness / "workflow.yaml")]
            cmd += ["--suite", "loop", "--tasks", ",".join(t.id for t in tasks)]
            cmd += ["--out", str(out / "report"), "--workdir", str(out / "db")]
            cmd += ["--concurrency", os.environ.get("LAB_LOOP_CONCURRENCY", "8")]
            env = os.environ | {
                "PYTHONPATH": os.pathsep.join([str(harness), str(REPO)]),
                "LAB_SEED": str(trial),
            }
            r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
            if r.returncode:  # the harness does not start: its failure, on every task
                error = scrub(r.stderr.strip())[-600:]
                return [Episode(t.id, status="error", error=error) for t in tasks]
            traces = {t["task_id"]: t for t in _jsonl(out / "report" / "traces.jsonl")}
            episodes = []
            for row in _jsonl(out / "report" / "results.jsonl"):
                db = out / "db" / row["task_id"]
                passed, actions = observe(db / "start.sqlite", db / "final.sqlite", row["task_id"])
                trace = traces.get(row["task_id"], {})
                calls = trace.get("model_calls") or []
                fields = dict(trace.get("workflow_state") or {})
                fields.pop("request", None)
                episodes.append(
                    _episode(
                        row,
                        state_ok=passed,
                        actions=actions,
                        models=sorted({c["model"] for c in calls if c.get("model")}),
                        extra={"state": fields, "events": trace.get("events") or []},
                    )
                )
            return episodes

    return run_tasks


def validate(harness: Path) -> list[str]:
    """Why a candidate may not run: a changed model, code that reaches outside, a copied
    development task, or a workflow that does not build."""
    problems = []
    for path in sorted(harness.rglob("*.yaml")):
        try:
            spec = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            problems.append(f"{path.name}: invalid YAML: {exc}")
            continue
        problems += _models(spec, path.name)
    dev = SPLITS["dev"]
    for path in sorted(p for p in harness.rglob("*") if p.is_file()):
        text = path.read_text(errors="replace")
        copied = [t.id for t in dev if t.id in text or t.user_message[:50] in text]
        if copied:
            problems.append(f"{path.name} copies development tasks: {', '.join(copied[:3])}")
        if path.suffix == ".py":
            problems += _imports(text, path.name)
    if problems:
        return problems
    build = "import asyncio, sys; from harness.spec import load_any; "
    build += "from harness.workflow import assemble; asyncio.run(assemble(load_any(sys.argv[1])))"
    env = os.environ | {"PYTHONPATH": os.pathsep.join([str(harness), str(REPO)])}
    cmd = [sys.executable, "-c", build, str(harness / "workflow.yaml")]
    r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    return (
        [f"the workflow does not build: {scrub(r.stderr.strip())[-400:]}"] if r.returncode else []
    )


def _models(node: object, where: str) -> list[str]:
    out = []
    if isinstance(node, dict):
        if node.get("type") in ("classifier", "agent", "subworkflow"):
            out.append(f"{where}: a {node['type']} node is not allowed; use structured nodes")
        if isinstance(node.get("model"), dict) and node["model"] != MODEL_BLOCK:
            out.append(f"{where}: a model block differs from the frozen one: {node['model']}")
        node = list(node.values())
    if isinstance(node, list):
        for child in node:
            out += _models(child, where)
    return out


def _imports(source: str, where: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{where}: {exc.msg} (line {exc.lineno})"]
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            names.add(n.module)
    bad = sorted(
        n
        for n in names
        if n.split(".")[0] in FORBIDDEN or n.startswith(("harness.local", "harness.openai_model"))
    )
    return [f"{where} imports {', '.join(bad)}"] if bad else []


def reference(out: Path) -> Path:
    """The read-only material an improver gets: the policy, how a run works and the
    environment's source."""
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    (out / "README.md").write_text(ABOUT)
    (out / "policy.md").write_text(
        "# The shop's policy\n\n" + "\n\n".join(POLICIES.values()) + "\n"
    )
    for rel in ("envs/custom/db.py", "envs/custom/tools.py", "envs/custom/refunds.py"):
        _copy(rel, out)
    for rel in ("envs/custom/approval.py", "harness/spec.py", "harness/workflow.py"):
        _copy(rel, out)
    return out


def _copy(rel: str, out: Path) -> None:
    (out / "lab" / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / rel, out / "lab" / rel)


TARGET = Target(
    usecase=usecase(),
    seed=SEED,
    adapter=adapter,
    frozen={
        "model": MODEL,
        "endpoint": URL,
        "reasoning_effort": REASONING_EFFORT,
        "sampling": f"API defaults; reasoning_effort={REASONING_EFFORT}; seed = trial number",
    },
    brief=BRIEF,
    reference=reference(REPO / "build" / "loop-reference"),
    validate=validate,
)

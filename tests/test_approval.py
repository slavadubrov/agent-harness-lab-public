"""The three Part 2 designs end to end, offline: plain agent, agent with an approval pause,
and the approval workflow. The model is a script (tests/fakes.py:NativeScriptModel); the
tools, refund service, middleware, workflow builder and runner are the real code.
"""

import asyncio
import copy

import pytest

from envs.custom.db import connect, create_seed
from envs.custom.refunds import call_refund_service, decide, operations, request_refund
from envs.custom.run import Target, run_task
from envs.custom.tasks import TASKS_BY_ID
from harness.spec import HarnessSpec, WorkflowSpec, load_spec, load_workflow_spec

OVER_LIMIT = [
    {"tool": "look_up_account", "args": {"email": "ben.ortiz@example.com"}},
    {
        "tool": "issue_refund",
        "args": {"order_id": "O-2002", "amount_cents": 35000, "reason": "cracked"},
    },
    {"reply": "Done."},
]
PARTIAL = [
    {
        "tool": "issue_refund",
        "args": {"order_id": "O-1002", "amount_cents": 1500, "reason": "missing knife"},
    },
    {"reply": "Refunded $15.00."},
]


@pytest.fixture(autouse=True)
def _dummy_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-used")


def scripted(spec_path: str, steps) -> HarnessSpec:
    """The real spec with the model replaced by a script and the MCP server left out."""
    data = load_spec(spec_path).model_dump(exclude={"source"})
    data["model"] = {
        "provider": "import",
        "id": "fake/native",
        "ref": "tests.fakes:NativeScriptModel",
        "kwargs": {"steps": steps},
    }
    data["tools"] = {
        "functions": ["envs.custom.tools:TOOLS"],
        "context_schema": "envs.custom.tools:AccountContext",
    }
    return HarnessSpec.model_validate(data)


def scripted_workflow(steps, tmp_path) -> WorkflowSpec:
    agent = tmp_path / "agent.yaml"
    import yaml

    agent.write_text(
        yaml.safe_dump(
            scripted("harness/spec/plain.yaml", steps).model_dump(mode="json", exclude={"source"})
        )
    )
    data = load_workflow_spec("harness/spec/workflows/refund-approval.yaml").model_dump(
        exclude={"source"}
    )
    data["nodes"]["agent"]["agent"] = {"spec": str(agent), "override": {}}
    return WorkflowSpec.model_validate(data)


def run(spec, task_id, tmp_path):
    seed = create_seed(tmp_path / "seed.sqlite")
    target = asyncio.run(Target.build(spec))
    task = TASKS_BY_ID[task_id]
    row, trace = asyncio.run(run_task(target, task, seed, tmp_path / task_id, []))
    return row, trace


# -- the refund service ------------------------------------------------------------------


def test_service_holds_large_refunds_and_issues_each_operation_once(tmp_path):
    db = create_seed(tmp_path / "db.sqlite")
    con = connect(db)
    held = request_refund(con, "c", "O-2002", 35000, "cracked")
    assert held["status"] == "held_for_approval"
    decide(db, "c", "O-2002", 35000, "approve")
    first = request_refund(con, "c", "O-2002", 35000, "cracked")
    again = request_refund(con, "c", "O-2002", 35000, "reworded reason")
    assert again == {**first, "replayed": True}
    assert [op["status"] for op in operations(db, "c")] == ["issued"]
    decide(db, "c", "O-2002", 35000, "reject")  # too late: issued stays issued
    assert [op["status"] for op in operations(db, "c")] == ["issued"]
    con.close()


def test_lost_response_raises_once_after_commit(tmp_path):
    db = create_seed(tmp_path / "db.sqlite")
    with pytest.raises(ConnectionError):
        call_refund_service(db, "c", "O-1002", 1500, "x", fault="lost_response")
    receipt = call_refund_service(db, "c", "O-1002", 1500, "x", fault="lost_response")
    assert receipt["replayed"] is True


# -- the three designs -------------------------------------------------------------------


def test_plain_agent_leaves_an_approved_refund_unissued(tmp_path):
    row, trace = run(
        scripted("harness/spec/plain.yaml", OVER_LIMIT), "refund-over-limit-approved", tmp_path
    )
    assert not row["passed"] and row["outcome"] == "completed"
    assert row["approval_requests"] == 0  # nothing in the loop waits for the supervisor
    assert [op["status"] for op in row["refund_operations"]] == ["held"]


@pytest.mark.parametrize(
    "task_id, passed, status",
    [
        ("refund-over-limit-approved", True, "issued"),
        ("refund-over-limit-rejected", True, "rejected"),
    ],
)
def test_agent_pauses_before_the_tool_for_a_supervisor(tmp_path, task_id, passed, status):
    row, _ = run(scripted("harness/spec/approval-agent.yaml", OVER_LIMIT), task_id, tmp_path)
    assert row["passed"] is passed, row["reason"]
    assert row["approval_requests"] == 1
    assert [op["status"] for op in row["refund_operations"]] == [status]


def test_agent_does_not_pause_for_a_small_refund(tmp_path):
    row, _ = run(
        scripted("harness/spec/approval-agent.yaml", PARTIAL),
        "refund-partial-missing-item",
        tmp_path,
    )
    assert row["passed"] and row["approval_requests"] == 0


def test_unanswered_approval_leaves_the_case_waiting(tmp_path):
    row, _ = run(
        scripted("harness/spec/approval-agent.yaml", OVER_LIMIT),
        "refund-over-agent-limit",
        tmp_path,
    )
    assert row["passed"] and row["outcome"] == "waiting for approval"


@pytest.mark.parametrize("task_id", ["refund-over-limit-approved", "refund-over-limit-rejected"])
def test_workflow_pauses_after_the_agent_and_issues_in_code(tmp_path, task_id):
    row, trace = run(scripted_workflow(OVER_LIMIT, tmp_path), task_id, tmp_path)
    assert row["passed"], row["reason"]
    assert row["approval_requests"] == 1
    assert row["model_calls"] == 3  # no model call after the pause
    word = "issued (refund" if task_id.endswith("approved") else "did not approve"
    assert word in row["final_answer"]


@pytest.mark.parametrize(
    "spec_kind, task_id",
    [
        ("plain", "refund-partial-lost-response"),
        ("approval", "refund-partial-lost-response"),
        ("workflow", "refund-partial-lost-response"),
        ("approval", "refund-over-limit-approved-lost-response"),
        ("workflow", "refund-over-limit-approved-lost-response"),
    ],
)
def test_lost_response_ends_with_one_refund(tmp_path, spec_kind, task_id):
    steps = copy.deepcopy(PARTIAL if "partial" in task_id else OVER_LIMIT)
    spec = {
        "plain": lambda: scripted("harness/spec/plain.yaml", steps),
        "approval": lambda: scripted("harness/spec/approval-agent.yaml", steps),
        "workflow": lambda: scripted_workflow(steps, tmp_path),
    }[spec_kind]()
    row, trace = run(spec, task_id, tmp_path)
    assert row["passed"], (row["reason"], trace["events"])
    issued = [op for op in row["refund_operations"] if op["status"] == "issued"]
    assert len(issued) == 1
    # Inside the agent loop the error ends the run and the runner resumes it; in the
    # workflow the issue node's retry policy absorbs a fault in that node.
    in_loop = spec_kind != "workflow" or "partial" in task_id
    assert row["resumes_after_error"] == (1 if in_loop else 0)
    if in_loop:
        # The resumed run continued the unanswered tool call: one customer message, and
        # the tool's answer is the receipt the service kept from the first attempt.
        msgs = trace["messages"]
        assert sum(m["type"] == "human" for m in msgs) == 1
        assert any(m["type"] == "tool" and '"replayed": true' in m["data"]["content"] for m in msgs)


def test_route_score_counts_clarifications_as_right_only_for_unclear_requests():
    from envs.custom.route_eval import score

    rows = [
        {"label": "refund", "choice": "refund", "confidence": 0.9},
        {"label": "refund", "choice": "account", "confidence": 0.9},
        {"label": "account", "choice": "account", "confidence": 0.3},
        {"label": "unclear", "choice": "refund", "confidence": 0.3},
        {"label": "unclear", "choice": "refund", "confidence": 0.9},
        {"label": "unclear", "choice": "unclear", "confidence": 0.9},
    ]
    assert score(rows, 0.0) == {
        "right_route": 2,
        "wrong_route": 3,
        "clarify_needed": 1,
        "clarify_not_needed": 0,
    }
    assert score(rows, 0.5) == {
        "right_route": 1,
        "wrong_route": 2,
        "clarify_needed": 2,
        "clarify_not_needed": 1,
    }

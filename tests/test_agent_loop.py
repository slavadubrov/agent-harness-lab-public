"""The measured paths end to end, offline: SGR steps, the Jev write guard, the τ³ handoff.

The model is a scripted fake (tests/fakes.py:ScriptedChatModel); the tools, database,
runner, middleware and τ³ adapter are the real code.
"""

import asyncio
from types import SimpleNamespace

import pytest
import yaml

from envs.custom.db import create_seed
from envs.custom.run import run_task
from envs.custom.tasks import TASKS_BY_ID
from harness.agent import build_harness
from harness.spec import HarnessSpec
from tests.fakes import act


@pytest.fixture(autouse=True)
def _dummy_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-used")


def spec(steps, middleware=()) -> HarnessSpec:
    return HarnessSpec.model_validate(
        {
            "name": "scripted",
            "model": {
                "provider": "import",
                "id": "fake/scripted",
                "ref": "tests.fakes:ScriptedChatModel",
                "kwargs": {"steps": steps},
            },
            "system_prompt": "You are a test agent.",
            "tools": {
                "functions": ["envs.custom.tools:TOOLS"],
                "context_schema": "envs.custom.tools:AccountContext",
            },
            "middleware": [*middleware, {"type": "SchemaGuidedReasoning"}],
        }
    )


def run_custom(s: HarnessSpec, task_id: str, tmp_path) -> dict:
    seed = create_seed(tmp_path / "seed.sqlite")
    agent = asyncio.run(build_harness(s))
    row, _ = asyncio.run(run_task(agent, TASKS_BY_ID[task_id], seed, tmp_path / task_id, []))
    return row


def test_sgr_steps_become_tool_calls_then_a_reply(tmp_path):
    steps = [
        act("look_up_account", email="ana.novak@example.com"),
        act("issue_refund", order_id="O-1001", amount_cents=4800, reason="arrived broken"),
        act("reply_to_user", message="Refunded $48.00."),
    ]
    row = run_custom(spec(steps), "refund-full-damaged", tmp_path)
    assert row["passed"], row["reason"]
    assert row["error"] is None
    assert row["final_answer"] == "Refunded $48.00."
    assert (row["model_calls"], row["tool_calls"], row["proposed_tool_calls"]) == (3, 2, 2)
    assert row["unpriced_calls"] == 3  # the fake model has no price


class FakeJev:
    def __init__(self, p: float) -> None:
        self.p, self.calls = p, 0

    def invoke(self, _):
        self.calls += 1
        return SimpleNamespace(nouls={"is_risky": SimpleNamespace(noul=self.p)})

    async def ainvoke(self, request):
        return self.invoke(request)


@pytest.mark.parametrize(
    ("p", "task_id", "order", "cents", "blocked"),
    [
        (0.9, "refund-over-agent-limit", "O-2002", 35000, 1),  # blocked: no write
        (0.1, "refund-full-damaged", "O-1001", 4800, 0),  # allowed: the refund is written
    ],
)
def test_jev_guard_blocks_or_allows_a_write(
    monkeypatch, tmp_path, p, task_id, order, cents, blocked
):
    jev = FakeJev(p)
    monkeypatch.setattr("harness.agent.jev_classifier", lambda *_: jev)
    guard = {"type": "TypeSafeAutoMode", "tools": ["issue_refund"], "instructions": "test"}
    steps = [
        act("issue_refund", order_id=order, amount_cents=cents, reason="damaged"),
        act("reply_to_user", message="done"),
    ]
    row = run_custom(spec(steps, [guard]), task_id, tmp_path)
    assert row["passed"], row["reason"]
    assert jev.calls == 1
    assert row["blocked_tool_calls"] == blocked
    assert row["write_tool_calls_proposed"] == 1
    assert row["tool_calls"] == 1 - blocked  # a blocked tool never runs


def test_tau3_adapter_returns_tool_calls_and_resumes(tmp_path):
    from tau2.data_model.message import ToolMessage, UserMessage
    from tau2.environment.tool import as_tool

    from envs.tau3.agent import create_agent

    def get_order(order_id: str) -> str:
        """Get an order by id."""
        raise AssertionError("τ³ runs the tools, never the harness")

    steps = [act("get_order", order_id="#W1"), act("reply_to_user", message="It shipped.")]
    s = spec(steps).model_dump(mode="json", exclude={"source"})
    s["tools"] = {}
    path = tmp_path / "tau3-scripted.yaml"
    path.write_text(yaml.safe_dump(s))

    agent = create_agent([as_tool(get_order)], "policy text", llm_args={"spec": str(path)})
    state = agent.get_init_state()

    reply, state = agent.generate_next_message(UserMessage(role="user", content="Where?"), state)
    (call,) = reply.tool_calls
    assert (call.name, call.arguments) == ("get_order", {"order_id": "#W1"})

    wrong = ToolMessage(id="not-pending", role="tool", content="x", requestor="assistant")
    with pytest.raises(RuntimeError, match="do not match pending calls"):
        agent.generate_next_message(wrong, state)

    result = ToolMessage(id=call.id, role="tool", content="shipped", requestor="assistant")
    reply, state = agent.generate_next_message(result, state)
    assert reply.content == "It shipped." and not reply.tool_calls
    assert agent.recorder.totals().tool_calls == 0  # the harness executed no tool

"""Config-driven harness: tool sources, middleware by import, models by import, workflows.

No network and no API calls: models are test doubles from tests/fakes.py.
"""

import asyncio
from pathlib import Path

import pytest
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from pydantic import ValidationError

from envs.custom.db import create_seed
from envs.custom.tools import AccountContext
from harness.agent import build_harness, build_middleware, build_model, load_tools
from harness.spec import (
    HarnessSpec,
    ToolsSpec,
    WorkflowSpec,
    load_any,
    load_spec,
    load_workflow_spec,
)
from harness.workflow import assemble, build_workflow
from tests.fakes import EchoChatModel, SequentialEngine


@pytest.fixture(autouse=True)
def _dummy_key(monkeypatch):
    # Building (not calling) OpenRouter clients needs a key to be set.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-used")


def run(coro):
    return asyncio.run(coro)


def names(tools):
    return [t.name if hasattr(t, "name") else t for t in tools]


# -- A1 specs still build the same harness ------------------------------------------------


@pytest.mark.parametrize("spec", ["base", "plain", "glm-5.3-flash", "mimo-v2.6-flash"])
def test_a1_specs_unchanged(spec):
    s = load_spec(f"harness/spec/{spec}.yaml")
    tools = run(load_tools(s))
    assert names(tools) == [
        "look_up_account",
        "list_orders",
        "issue_refund",
        "update_address",
        "set_preference",
        "lookup_policy",
        "search_faq",
    ]
    graph = run(build_harness(s))
    assert {"model", "tools"} <= set(graph.nodes)


# -- tools: LangChain tools with arguments, toolkits, plain functions, provider tools -----


def test_tool_sources_and_filters():
    ts = ToolsSpec.model_validate(
        {
            "functions": ["envs.custom.tools:list_orders"],
            "sources": [
                {
                    "type": "factory",
                    "ref": "tests.fakes:make_greeter",
                    "kwargs": {"greeting": "hello"},
                },
                {"type": "factory", "ref": "tests.fakes:Toolkit", "kwargs": {"n": 2}},
                {"type": "import", "ref": "tests.fakes:plain_add"},
                {"type": "provider", "spec": {"type": "web_search"}},
            ],
            "exclude": ["kit_tool_1"],
        }
    )
    tools = run(load_tools(ts))
    assert names(tools) == [
        "list_orders",
        "greet",
        "kit_tool_0",
        "plain_add",
        {"type": "web_search"},
    ]
    greet = tools[1]
    assert greet.invoke({"name": "Ana"}) == "hello Ana"
    assert tools[3].invoke({"a": 2, "b": 3}) == 5


def test_include_rejects_unknown_tool():
    ts = ToolsSpec.model_validate({"functions": ["envs.custom.tools:TOOLS"], "include": ["nope"]})
    with pytest.raises(ValueError, match="unknown tools"):
        run(load_tools(ts))


# -- middleware and models by import --------------------------------------------------------


def test_import_middleware_and_model():
    spec = HarnessSpec.model_validate(
        {
            "name": "t",
            "model": {"provider": "import", "id": "fake/echo", "ref": "tests.fakes:EchoChatModel"},
            "system_prompt": "x",
            "middleware": [
                {
                    "type": "import",
                    "ref": "langchain.agents.middleware:ToolCallLimitMiddleware",
                    "kwargs": {"run_limit": 4},
                },
                {"type": "ModelCallLimitMiddleware", "run_limit": 5},
            ],
        }
    )
    model = build_model(spec)
    assert isinstance(model, EchoChatModel)
    mws = build_middleware(spec, model)
    assert isinstance(mws[0], ToolCallLimitMiddleware) and isinstance(
        mws[1], ModelCallLimitMiddleware
    )


def test_spec_typos_fail():
    with pytest.raises(ValidationError):
        HarnessSpec.model_validate(
            {"name": "t", "model": {"id": "m"}, "system_prompt": "x", "middlware": []}
        )


@pytest.mark.parametrize("name", ["x ~", "a/b", "../x", ""])
def test_unsafe_spec_names_fail(name):
    with pytest.raises(ValidationError):
        HarnessSpec.model_validate({"name": name, "model": {"id": "m"}, "system_prompt": "x"})


# -- workflows -------------------------------------------------------------------------


def _context(tmp_path: Path) -> AccountContext:
    return AccountContext(db_path=create_seed(tmp_path / "seed.sqlite"))


def test_workflow_routes_between_agents_and_tools(tmp_path):
    wf = run(build_workflow(load_workflow_spec("tests/fixtures/echo-workflow.yaml")))
    ctx = _context(tmp_path)

    out = run(
        wf.ainvoke(
            {"request": "Please refund O-1001", "account_id": "A-100"},
            config={"configurable": {"thread_id": "t1"}},
            context=ctx,
        )
    )
    assert out["route"] == "refund"
    assert out["answer"] == "refunds: Refund request: Please refund O-1001"
    assert [o["id"] for o in out["orders"]["orders"]][:1] == ["O-1004"]  # tool ran with ToolRuntime

    out = run(
        wf.ainvoke(
            {"request": "Change my language", "account_id": "A-100"},
            config={"configurable": {"thread_id": "t2"}},
            context=ctx,
        )
    )
    assert out["route"] == "other" and out["answer"] == "other: Change my language"
    assert out.get("orders") is None  # the tool node did not run


def test_nested_workflow(tmp_path):
    wf = run(build_workflow(load_workflow_spec("tests/fixtures/outer-workflow.yaml")))
    out = run(
        wf.ainvoke(
            {"request": "refund please", "account_id": "A-100"},
            config={"configurable": {"thread_id": "t3"}},
            context=_context(tmp_path),
        )
    )
    assert out["answer"].startswith("refunds: ") and out["route"] == "refund"


def test_custom_engine(tmp_path):
    raw = load_workflow_spec("tests/fixtures/echo-workflow.yaml").model_dump()
    raw["engine"] = {"name": "sequential", "ref": "tests.fakes:SequentialEngine"}
    spec = WorkflowSpec.model_validate(raw)
    built = run(assemble(spec))
    engine = SequentialEngine()
    runner = engine.compile(built)
    state = run(
        runner.ainvoke(
            {"request": "refund O-1001", "account_id": "A-100"}, context=_context(tmp_path)
        )
    )
    assert engine.visited == ["triage", "lookup", "refunds"]
    assert state.answer.startswith("refunds: ")


def test_workflow_validation():
    with pytest.raises(ValidationError, match="unknown nodes"):
        WorkflowSpec.model_validate(
            {
                "kind": "workflow",
                "name": "bad",
                "state_schema": "tests.fakes:SupportState",
                "nodes": {"a": {"type": "function", "ref": "tests.fakes:keyword_triage"}},
                "edges": [["START", "a"], ["a", "b"]],
            }
        )


@pytest.mark.parametrize(
    "path, nodes",
    [
        ("support-router.yaml", {"route", "refunds", "account", "general"}),
        ("support-router-clarify.yaml", {"route", "refunds", "account", "general", "clarify"}),
        ("refund-approval.yaml", {"agent", "find_held", "approval", "issue", "reply"}),
    ],
)
def test_workflow_specs_build(path, nodes):
    spec = load_any(f"harness/spec/workflows/{path}")
    assert isinstance(spec, WorkflowSpec)
    wf = run(build_workflow(spec))
    assert nodes <= set(wf.nodes)


# -- tool retry scope -----------------------------------------------------------------------


def _retry_calls(spec_name, tool_name):
    """Run the spec's ToolRetryMiddleware on a tool that always raises; return the call count."""
    from types import SimpleNamespace

    from langchain.agents.middleware import ToolRetryMiddleware

    s = load_spec(f"harness/spec/{spec_name}.yaml")
    mw = next(m for m in build_middleware(s, EchoChatModel()) if isinstance(m, ToolRetryMiddleware))
    mw.initial_delay = 0
    calls = []

    def handler(request):
        calls.append(1)
        raise RuntimeError("boom")

    request = SimpleNamespace(tool=None, tool_call={"name": tool_name, "id": "c1"})
    try:
        mw.wrap_tool_call(request, handler)
    except RuntimeError:  # a tool outside the retry scope raises straight through
        pass
    return len(calls)


@pytest.mark.parametrize("spec", ["base", "plain", "glm-5.3-flash", "mimo-v2.6-flash"])
def test_retry_covers_reads_and_not_writes(spec):
    assert _retry_calls(spec, "look_up_account") == 3  # 1 try + max_retries 2
    assert _retry_calls(spec, "issue_refund") == 1
    assert _retry_calls(spec, "set_preference") == 1


def test_retry_tools_field_defaults_to_all():
    from harness.spec import ToolRetrySpec

    assert ToolRetrySpec(type="ToolRetryMiddleware").tools is None
    with pytest.raises(ValidationError):
        ToolRetrySpec(type="ToolRetryMiddleware", tool="x")

"""build_workflow(spec): agents, models, classifiers, tools and functions as one graph.

A workflow spec (``kind: workflow``, in ``harness/spec/``) names typed state, nodes and
edges. Building happens in two steps, so the graph runtime can be swapped:

1. Node builders turn every node spec into a plain async callable
   ``node(state, ctx) -> dict of state updates``. They do not depend on the engine.
   An ``agent`` node calls ``build_harness`` on an agent spec and runs it with
   ``agent.ainvoke`` inside the node (pattern 2: typed state in, one typed field out;
   the agent's own messages stay out of the workflow state).
2. An engine wires the callables and edges into something runnable. ``langgraph``
   (StateGraph) is built in. A spec can name another engine with
   ``engine: {ref: "module:Class"}``, for example a fork of LangGraph. An engine
   implements ``compile(built: BuiltWorkflow) -> object with ainvoke(input, config, context)``.
"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_typesafe import Choice
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END as LG_END
from langgraph.graph import START as LG_START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel

from harness.accounting import Price, fetch_price
from harness.agent import (
    build_harness,
    build_model,
    load_tools,
    model_price,
    spec_prices,
)
from harness.refs import import_ref
from harness.spec import (
    END,
    START,
    AgentNodeSpec,
    ClassifierNodeSpec,
    ConditionalEdgeSpec,
    FunctionNodeSpec,
    NodeSpec,
    StructuredNodeSpec,
    SubworkflowNodeSpec,
    ToolNodeSpec,
    WorkflowSpec,
    load_spec,
    load_workflow_spec,
)
from harness.typesafe_guard import jev_classifier

# ---------------------------------------------------------------------------------------
# Engine-neutral pieces
# ---------------------------------------------------------------------------------------


@dataclass
class NodeContext:
    """What a node gets besides the state: the environment context and the run config."""

    context: Any
    config: RunnableConfig
    thread_id: str = field(init=False)

    def __post_init__(self) -> None:
        # No thread_id from the caller: a fresh one per node call, so the agent checkpoints
        # of two runs never mix.
        given = (self.config.get("configurable") or {}).get("thread_id")
        self.thread_id = str(given) if given else f"workflow-{uuid.uuid4()}"


NodeFn = Callable[[Any, NodeContext], Awaitable[dict[str, Any]]]
RouterFn = Callable[[Any], str]


@dataclass
class BuiltWorkflow:
    spec: WorkflowSpec
    state_schema: type
    context_schema: type | None
    nodes: dict[str, NodeFn]
    edges: list[tuple[str, str]]
    # (source node, router returning the next node name, possible next node names)
    routers: list[tuple[str, RouterFn, list[str]]]
    agents: dict[str, Any] = field(default_factory=dict)


class WorkflowEngine(Protocol):
    def compile(self, built: BuiltWorkflow) -> Any: ...


def get_field(state: Any, key: str) -> Any:
    return state[key] if isinstance(state, dict) else getattr(state, key)


class _StateView(dict):
    def __init__(self, state: Any) -> None:
        super().__init__()
        self._state = state

    def __missing__(self, key: str) -> Any:
        return get_field(self._state, key)


def fill(template: str, state: Any) -> str:
    return template.format_map(_StateView(state))


def _final_text(messages: list[Any]) -> str:
    last = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), None
    )
    if last is None:
        return ""
    return last.text


# ---------------------------------------------------------------------------------------
# Node builders
# ---------------------------------------------------------------------------------------


async def _agent_node(name: str, n: AgentNodeSpec, agents: dict[str, Any]) -> NodeFn:
    agent = await build_harness(load_spec(n.agent.spec, n.agent.override or None))
    agents[name] = agent

    async def run(state: Any, ctx: NodeContext) -> dict[str, Any]:
        config: RunnableConfig = {
            "configurable": {"thread_id": f"{ctx.thread_id}/{name}"},
            "callbacks": ctx.config.get("callbacks"),
            "recursion_limit": 100,
        }
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=fill(n.message, state))]},
            config=config,
            context=ctx.context,
        )
        return {n.output: _final_text(result["messages"])}

    return run


async def _structured_node(name: str, n: StructuredNodeSpec) -> NodeFn:
    schema = import_ref(n.output_schema)
    runnable = build_model(n.model).with_structured_output(schema, method=n.method)

    async def run(state: Any, ctx: NodeContext) -> dict[str, Any]:
        out = await runnable.ainvoke(
            fill(n.prompt, state), config={"callbacks": ctx.config.get("callbacks")}
        )
        return {state_key: get_field(out, out_key) for state_key, out_key in n.writes.items()}

    return run


async def _classifier_node(name: str, n: ClassifierNodeSpec) -> NodeFn:
    classifier = jev_classifier(n.model, n.endpoint, n.timeout_s)
    question = Choice(instructions=n.instructions, criteria=n.choices)

    async def run(state: Any, ctx: NodeContext) -> dict[str, Any]:
        resp = await classifier.ainvoke(
            {"state": fill(n.input, state), "questions": {name: question}},
            config={"callbacks": ctx.config.get("callbacks")},
        )
        answer = resp.choices[name]
        out: dict[str, Any] = {n.output: answer.choice}
        if n.confidence_output:
            out[n.confidence_output] = answer.confidence
        return out

    return run


async def _tool_node(name: str, n: ToolNodeSpec) -> NodeFn:
    tools = {t.name: t for t in await load_tools(n.tools) if isinstance(t, BaseTool)}
    if n.tool not in tools:
        raise ValueError(f"node {name}: tool {n.tool!r} not in its tools ({sorted(tools)})")
    tool = tools[n.tool]
    func = getattr(tool, "func", None) or getattr(tool, "coroutine", None)
    # Tools that take ToolRuntime (like the custom-environment tools) get one built here,
    # because no ToolNode runs in a tool node.
    needs_runtime = func is not None and "runtime" in inspect.signature(func).parameters

    async def run(state: Any, ctx: NodeContext) -> dict[str, Any]:
        args = {arg: get_field(state, key) for arg, key in n.args.items()}
        if needs_runtime:
            args["runtime"] = ToolRuntime(
                state=state.model_dump() if isinstance(state, BaseModel) else state,
                context=ctx.context,
                config=ctx.config,
                stream_writer=lambda _: None,
                tool_call_id=None,
                store=None,
            )
        return {
            n.output: await tool.ainvoke(args, config={"callbacks": ctx.config.get("callbacks")})
        }

    return run


async def _function_node(name: str, n: FunctionNodeSpec) -> NodeFn:
    fn = import_ref(n.ref)

    async def run(state: Any, ctx: NodeContext) -> dict[str, Any]:
        out = fn(state, ctx, **n.kwargs)
        return await out if inspect.isawaitable(out) else out

    return run


async def _subworkflow_node(name: str, n: SubworkflowNodeSpec) -> NodeFn:
    child = await build_workflow(load_workflow_spec(n.spec))

    async def run(state: Any, ctx: NodeContext) -> dict[str, Any]:
        child_in = {c: get_field(state, p) for c, p in n.inputs.items()}
        config: RunnableConfig = {
            "configurable": {"thread_id": f"{ctx.thread_id}/{name}"},
            "callbacks": ctx.config.get("callbacks"),
        }
        out = await child.ainvoke(child_in, config=config, context=ctx.context)
        return {p: get_field(out, c) for p, c in n.outputs.items()}

    return run


async def build_node(name: str, n: NodeSpec, agents: dict[str, Any]) -> NodeFn:
    if isinstance(n, AgentNodeSpec):
        return await _agent_node(name, n, agents)
    if isinstance(n, StructuredNodeSpec):
        return await _structured_node(name, n)
    if isinstance(n, ClassifierNodeSpec):
        return await _classifier_node(name, n)
    if isinstance(n, ToolNodeSpec):
        return await _tool_node(name, n)
    if isinstance(n, FunctionNodeSpec):
        return await _function_node(name, n)
    if isinstance(n, SubworkflowNodeSpec):
        return await _subworkflow_node(name, n)
    raise TypeError(f"Unknown node spec {n!r}")  # pragma: no cover - closed union


def build_router(ce: ConditionalEdgeSpec) -> tuple[RouterFn, list[str]]:
    targets = sorted(set(ce.routes.values()) | ({ce.default} if ce.default else set()))
    decide = import_ref(ce.router) if ce.router else None

    def route(state: Any) -> str:
        key = str(decide(state) if decide else get_field(state, ce.field))  # type: ignore[arg-type]
        if key in ce.routes:
            return ce.routes[key]
        if ce.default:
            return ce.default
        raise ValueError(
            f"no route from {ce.source!r} for value {key!r}; routes: {sorted(ce.routes)}"
        )

    return route, targets


# ---------------------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------------------


class LangGraphEngine:
    """Wire the nodes into a LangGraph StateGraph."""

    def __init__(self, **_: Any) -> None:
        pass

    @staticmethod
    def _adapt(fn: NodeFn) -> Callable[..., Awaitable[dict[str, Any]]]:
        async def node(state: Any, config: RunnableConfig, runtime: Runtime) -> dict[str, Any]:
            return await fn(state, NodeContext(context=runtime.context, config=config))

        return node

    def compile(self, built: BuiltWorkflow) -> Any:
        def ep(name: str) -> str:
            return {START: LG_START, END: LG_END}.get(name, name)

        g = StateGraph(built.state_schema, context_schema=built.context_schema)
        for name, fn in built.nodes.items():
            g.add_node(name, self._adapt(fn))
        for a, b in built.edges:
            g.add_edge(ep(a), ep(b))
        for source, route, targets in built.routers:
            g.add_conditional_edges(
                ep(source), lambda s, _r=route: ep(_r(s)), [ep(t) for t in targets]
            )
        checkpointer = InMemorySaver() if built.spec.checkpointer == "memory" else None
        return g.compile(checkpointer=checkpointer, name=built.spec.name)


ENGINES: dict[str, Callable[..., WorkflowEngine]] = {"langgraph": LangGraphEngine}


def register_engine(name: str, factory: Callable[..., WorkflowEngine]) -> None:
    ENGINES[name] = factory


def get_engine(spec: WorkflowSpec) -> WorkflowEngine:
    if spec.engine.ref:
        return import_ref(spec.engine.ref)(**spec.engine.kwargs)
    if spec.engine.name not in ENGINES:
        raise ValueError(f"Unknown engine {spec.engine.name!r}; known: {sorted(ENGINES)}")
    return ENGINES[spec.engine.name](**spec.engine.kwargs)


# ---------------------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------------------


async def assemble(spec: WorkflowSpec) -> BuiltWorkflow:
    """Build every node and router. Engine-neutral."""
    agents: dict[str, Any] = {}
    nodes = {name: await build_node(name, n, agents) for name, n in spec.nodes.items()}
    routers = [(ce.source, *build_router(ce)) for ce in spec.conditional_edges]
    return BuiltWorkflow(
        spec=spec,
        state_schema=import_ref(spec.state_schema),
        context_schema=import_ref(spec.context_schema) if spec.context_schema else None,
        nodes=nodes,
        edges=list(spec.edges),
        routers=routers,
        agents=agents,
    )


async def build_workflow(spec: WorkflowSpec) -> Any:
    return get_engine(spec).compile(await assemble(spec))


def workflow_prices(spec: WorkflowSpec) -> list[Price]:
    """Prices of every priced model a workflow can call (agents, structured, classifier)."""
    prices: dict[str, Price] = {}
    for n in spec.nodes.values():
        found: list[Price | None] = []
        if isinstance(n, AgentNodeSpec):
            found = list(spec_prices(load_spec(n.agent.spec, n.agent.override or None)))
        elif isinstance(n, StructuredNodeSpec):
            found = [model_price(n.model)]
        elif isinstance(n, ClassifierNodeSpec):
            found = [fetch_price(n.price_model_id, n.price_provider_tag)]
        elif isinstance(n, SubworkflowNodeSpec):
            found = list(workflow_prices(load_workflow_spec(n.spec)))
        for p in found:
            if p:
                prices[f"{p.model_id}@{p.provider_tag}"] = p
    return list(prices.values())

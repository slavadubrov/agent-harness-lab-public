"""build_harness(spec) -> create_agent(model, tools, system_prompt, middleware, checkpointer).

Everything that defines the harness comes from the spec: model id and settings, tool
sources, system prompt, middleware and their settings, checkpointer.

The one runtime input is ``EnvBinding``. Some environments hand the agent its tools and
policy at run time instead of letting the spec name them (τ³-bench builds a fresh tool
set and policy text per task, and runs the tools itself). ``EnvBinding`` carries exactly
those environment-owned things. It cannot change the model, prompt or middleware.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    SummarizationMiddleware,
    ToolRetryMiddleware,
)
from langchain.tools import tool as as_tool
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openrouter import ChatOpenRouter
from langchain_typesafe import NoulCriteria
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from harness.accounting import Price, fetch_price
from harness.refs import import_ref
from harness.sgr import SchemaGuidedReasoningMiddleware
from harness.spec import (
    REPO_ROOT,
    FactoryToolSource,
    HarnessSpec,
    ImportMiddlewareSpec,
    ImportToolSource,
    McpServerSpec,
    McpToolSource,
    ModelCallLimitSpec,
    ModelSpec,
    ProviderToolSource,
    SchemaGuidedReasoningSpec,
    SummarizationSpec,
    ToolRetrySpec,
    ToolsSpec,
    TypeSafeAutoModeSpec,
)
from harness.typesafe_guard import JevAutoModeMiddleware, jev_classifier


@dataclass(frozen=True)
class EnvBinding:
    """Environment-owned inputs. Harness settings never come from here."""

    # Replaces spec.tools (functions, MCP servers, context schema) when set.
    tools: list[BaseTool] | None = None
    # Appended to the system prompt inside <policy> tags.
    policy: str | None = None
    # False: stop before the ToolNode (interrupt_before=["tools"]); the environment runs
    # the tool calls and the caller resumes the graph with the results.
    execute_tools: bool = True


def build_model(spec: HarnessSpec | ModelSpec, model_id: str | None = None) -> BaseChatModel:
    m = spec.model if isinstance(spec, HarnessSpec) else spec
    if m.provider == "import":
        model = import_ref(m.ref)(**m.kwargs)  # type: ignore[arg-type]
        if not isinstance(model, BaseChatModel):
            raise TypeError(f"{m.ref} returned {type(model).__name__}, not a BaseChatModel")
        return model
    s = m.settings
    kwargs: dict[str, Any] = {
        "model": model_id or m.id,
        "max_tokens": s.max_tokens,
        "temperature": s.temperature,
        "reasoning": s.reasoning,
        "openrouter_provider": s.provider,
        "timeout": s.timeout_ms,
        "max_retries": s.max_retries,
    }
    return ChatOpenRouter(**{k: v for k, v in kwargs.items() if v is not None})


def _as_tools(obj: Any, ref: str) -> list[BaseTool]:
    """Normalize what a tool source returned into a list of BaseTools."""
    if isinstance(obj, BaseTool):
        return [obj]
    if isinstance(obj, type):
        raise TypeError(f"{ref} is a class; use a {{type: factory}} source to construct it")
    if isinstance(obj, (list, tuple)):
        return [t for item in obj for t in _as_tools(item, ref)]
    if hasattr(obj, "get_tools"):  # LangChain toolkit
        return _as_tools(obj.get_tools(), ref)
    if callable(obj):  # plain function: its signature and docstring become the schema
        return [as_tool(obj)]
    raise TypeError(f"{ref} gave {type(obj).__name__}; expected tool(s), a toolkit or a callable")


def _mcp_connection(s: McpServerSpec) -> dict[str, Any]:
    if s.transport == "stdio":
        conn: dict[str, Any] = {
            "transport": "stdio",
            "command": sys.executable if s.command == "python" else s.command,
            "args": s.args,
            "cwd": str(REPO_ROOT),
        }
        if s.env is not None:
            conn["env"] = s.env
        return conn
    conn = {"transport": s.transport, "url": s.url}
    if s.headers:
        conn["headers"] = s.headers
    return conn


async def load_tools(tools_spec: HarnessSpec | ToolsSpec) -> list[BaseTool | dict[str, Any]]:
    """Load every tool source of a spec, in order, then apply include/exclude."""
    ts = tools_spec.tools if isinstance(tools_spec, HarnessSpec) else tools_spec
    sources = [ImportToolSource(type="import", ref=r) for r in ts.functions]
    sources += [McpToolSource(type="mcp", name=n, server=s) for n, s in ts.mcp_servers.items()]
    sources += list(ts.sources)

    tools: list[BaseTool | dict[str, Any]] = []
    mcp: dict[str, dict[str, Any]] = {}
    for src in sources:
        if isinstance(src, ImportToolSource):
            tools.extend(_as_tools(import_ref(src.ref), src.ref))
        elif isinstance(src, FactoryToolSource):
            tools.extend(_as_tools(import_ref(src.ref)(**src.kwargs), src.ref))
        elif isinstance(src, McpToolSource):
            mcp[src.name] = _mcp_connection(src.server)
        elif isinstance(src, ProviderToolSource):
            tools.append(dict(src.spec))
    if mcp:
        tools.extend(await MultiServerMCPClient(mcp).get_tools())

    def name(t: BaseTool | dict[str, Any]) -> str:
        return t.name if isinstance(t, BaseTool) else str(t.get("name") or t.get("type"))

    if ts.include is not None:
        missing = set(ts.include) - {name(t) for t in tools}
        if missing:
            raise ValueError(f"tools.include names unknown tools: {sorted(missing)}")
        tools = [t for t in tools if name(t) in ts.include]
    tools = [t for t in tools if name(t) not in ts.exclude]
    names = [name(t) for t in tools]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate tool names: {names}")
    return tools


def build_middleware(spec: HarnessSpec, model: BaseChatModel) -> list[AgentMiddleware]:
    out: list[AgentMiddleware] = []
    for m in spec.middleware:
        if isinstance(m, SummarizationSpec):
            out.append(
                SummarizationMiddleware(
                    build_model(spec, m.model) if m.model else model,
                    trigger=m.trigger,
                    keep=m.keep,
                )
            )
        elif isinstance(m, ToolRetrySpec):
            out.append(
                ToolRetryMiddleware(
                    max_retries=m.max_retries,
                    on_failure=m.on_failure,
                    initial_delay=m.initial_delay,
                    backoff_factor=m.backoff_factor,
                    tools=m.tools,
                )
            )
        elif isinstance(m, ModelCallLimitSpec):
            out.append(
                ModelCallLimitMiddleware(
                    run_limit=m.run_limit,
                    thread_limit=m.thread_limit,
                    exit_behavior=m.exit_behavior,
                )
            )
        elif isinstance(m, SchemaGuidedReasoningSpec):
            out.append(
                SchemaGuidedReasoningMiddleware(
                    method=m.method,
                    tool_choice=m.tool_choice,
                    strict=m.strict,
                    max_parse_retries=m.max_parse_retries,
                )
            )
        elif isinstance(m, TypeSafeAutoModeSpec):
            criteria = (
                NoulCriteria(true=m.criteria_true, false=m.criteria_false)
                if m.criteria_true or m.criteria_false
                else None
            )
            out.append(
                JevAutoModeMiddleware(
                    tools=m.tools,
                    instructions=m.instructions,
                    criteria=criteria,
                    classifier=jev_classifier(m.model, m.endpoint, m.timeout_s),
                )
            )
        elif isinstance(m, ImportMiddlewareSpec):
            kwargs = {k: model if v == "$harness_model" else v for k, v in m.kwargs.items()}
            mw = import_ref(m.ref)(**kwargs)
            if not isinstance(mw, AgentMiddleware):
                raise TypeError(f"{m.ref} returned {type(mw).__name__}, not an AgentMiddleware")
            out.append(mw)
        else:  # pragma: no cover - the spec union is closed
            raise TypeError(f"Unknown middleware spec {m!r}")
    return out


def model_price(m: ModelSpec) -> Price | None:
    """Price of an OpenRouter model at its pinned endpoint. Imported models have none."""
    if m.provider != "openrouter":
        return None
    order = (m.settings.provider or {}).get("order") or []
    if not order:
        raise ValueError(
            f"Pin a provider for {m.id} (settings.provider.order) so the price is fixed."
        )
    return fetch_price(m.id, order[0])


def spec_prices(spec: HarnessSpec) -> list[Price]:
    """Per-token prices of every priced model the spec can call."""
    prices = [p for p in [model_price(spec.model)] if p]
    order = (spec.model.settings.provider or {}).get("order") or []
    extra = {m.model for m in spec.middleware if isinstance(m, SummarizationSpec) and m.model}
    prices += [fetch_price(i, order[0]) for i in sorted(extra)]
    prices += [
        fetch_price(m.price_model_id, m.price_provider_tag)
        for m in spec.middleware
        if isinstance(m, TypeSafeAutoModeSpec)
    ]
    return prices


async def build_harness(spec: HarnessSpec, env: EnvBinding | None = None) -> CompiledStateGraph:
    env = env or EnvBinding()
    model = build_model(spec)
    if env.tools is not None:
        tools, context_schema = env.tools, None
    else:
        tools = await load_tools(spec)
        context_schema = (
            import_ref(spec.tools.context_schema) if spec.tools.context_schema else None
        )
    system_prompt = spec.system_prompt.strip()
    if env.policy:
        system_prompt += f"\n\n<policy>\n{env.policy.strip()}\n</policy>"
    return create_agent(
        model,
        tools,
        system_prompt=system_prompt,
        middleware=build_middleware(spec, model),
        context_schema=context_schema,
        checkpointer=InMemorySaver() if spec.checkpointer == "memory" else None,
        interrupt_before=None if env.execute_tools else ["tools"],
        name=spec.name,
    )

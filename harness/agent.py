"""build_harness(spec) -> create_agent(model, tools, system_prompt, middleware, checkpointer).

Everything that defines the harness comes from the spec: model id and settings, tool
sources, system prompt, middleware and their settings, checkpointer.

The one runtime input is ``EnvBinding``. Some environments hand the agent its tools and
policy at run time instead of letting the spec name them (τ³-bench builds a fresh tool
set and policy text per task, and runs the tools itself). ``EnvBinding`` carries exactly
those environment-owned things. It cannot change the model, prompt or middleware.
"""

from __future__ import annotations

import importlib
import os
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
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openrouter import ChatOpenRouter
from langchain_typesafe import NoulCriteria, TypeSafeClassifier
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from harness.accounting import Price, fetch_price
from harness.sgr import SchemaGuidedReasoningMiddleware
from harness.spec import (
    REPO_ROOT,
    HarnessSpec,
    ModelCallLimitSpec,
    SchemaGuidedReasoningSpec,
    SummarizationSpec,
    ToolRetrySpec,
    TypeSafeAutoModeSpec,
)
from harness.typesafe_guard import JevAutoModeMiddleware, OpenRouterJevClassifier


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


def _import(path: str) -> Any:
    module, _, attr = path.partition(":")
    return getattr(importlib.import_module(module), attr)


def build_model(spec: HarnessSpec, model_id: str | None = None) -> ChatOpenRouter:
    s = spec.model.settings
    kwargs: dict[str, Any] = {
        "model": model_id or spec.model.id,
        "max_tokens": s.max_tokens,
        "temperature": s.temperature,
        "reasoning": s.reasoning,
        "openrouter_provider": s.provider,
        "timeout": s.timeout_ms,
        "max_retries": s.max_retries,
    }
    return ChatOpenRouter(**{k: v for k, v in kwargs.items() if v is not None})


async def load_tools(spec: HarnessSpec) -> list[BaseTool]:
    tools: list[BaseTool] = []
    for path in spec.tools.functions:
        obj = _import(path)
        tools.extend(obj if isinstance(obj, list) else [obj])
    if spec.tools.mcp_servers:
        connections = {
            name: {
                "transport": "stdio",
                "command": sys.executable if s.command == "python" else s.command,
                "args": s.args,
                "cwd": str(REPO_ROOT),
            }
            for name, s in spec.tools.mcp_servers.items()
        }
        tools.extend(await MultiServerMCPClient(connections).get_tools())
    names = [t.name for t in tools]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate tool names: {names}")
    return tools


def _classifier(m: TypeSafeAutoModeSpec) -> TypeSafeClassifier:
    if m.endpoint == "openrouter-decisions":
        return OpenRouterJevClassifier(
            model=m.model, api_key=os.environ["OPENROUTER_API_KEY"], timeout=m.timeout_s
        )
    return TypeSafeClassifier(model=m.model, timeout=m.timeout_s)


def build_middleware(spec: HarnessSpec, model: ChatOpenRouter) -> list[AgentMiddleware]:
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
                    classifier=_classifier(m),
                )
            )
        else:  # pragma: no cover - the spec union is closed
            raise TypeError(f"Unknown middleware spec {m!r}")
    return out


def spec_prices(spec: HarnessSpec) -> list[Price]:
    """Per-token prices of every priced model the spec can call."""
    provider = spec.model.settings.provider or {}
    order = provider.get("order") or []
    if not order:
        raise ValueError("Pin a provider (model.settings.provider.order) so the price is fixed.")
    ids = {spec.model.id}
    ids |= {m.model for m in spec.middleware if isinstance(m, SummarizationSpec) and m.model}
    prices = [fetch_price(i, order[0]) for i in sorted(ids)]
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
        context_schema = _import(spec.tools.context_schema) if spec.tools.context_schema else None
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

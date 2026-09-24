"""Typed harness spec.

The YAML files in ``harness/spec/`` are the only list of things a harness change may
touch: model, model settings, tools, system prompt, middleware and their settings.
Every file is validated into ``HarnessSpec`` (``extra="forbid"``), so a typo in a
key fails loudly instead of being ignored.

A spec file may set ``extends: <other file>``. The child is deep-merged over the
parent; lists are replaced, not merged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = REPO_ROOT / "harness" / "spec" / "base.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelSettings(_Strict):
    max_tokens: int | None = None
    temperature: float | None = None
    reasoning: dict[str, Any] | None = None
    # OpenRouter provider routing. Pinning a provider keeps the price per token fixed.
    provider: dict[str, Any] | None = None
    # ChatOpenRouter takes the request timeout in milliseconds (maps to SDK timeout_ms).
    timeout_ms: int | None = 120_000
    max_retries: int = 2


class ModelSpec(_Strict):
    provider: Literal["openrouter"] = "openrouter"
    id: str
    settings: ModelSettings = ModelSettings()


class McpServerSpec(_Strict):
    transport: Literal["stdio"] = "stdio"
    # "python" is resolved to the interpreter that runs the harness.
    command: str
    args: list[str] = []


class ToolsSpec(_Strict):
    # Import paths "package.module:attribute" of LangChain @tool objects (or lists of them).
    functions: list[str] = []
    mcp_servers: dict[str, McpServerSpec] = {}
    # Import path of the typed runtime context the tools read (ToolRuntime[Context]).
    context_schema: str | None = None


ContextSize = tuple[Literal["tokens", "messages", "fraction"], int | float]


class SummarizationSpec(_Strict):
    type: Literal["SummarizationMiddleware"]
    # null = use the harness model
    model: str | None = None
    trigger: ContextSize
    keep: ContextSize


class ToolRetrySpec(_Strict):
    type: Literal["ToolRetryMiddleware"]
    max_retries: int = 2
    on_failure: Literal["continue", "error"] = "continue"
    initial_delay: float = 0.5
    backoff_factor: float = 2.0


class ModelCallLimitSpec(_Strict):
    type: Literal["ModelCallLimitMiddleware"]
    run_limit: int | None = None
    thread_limit: int | None = None
    exit_behavior: Literal["end", "error"] = "end"


class SchemaGuidedReasoningSpec(_Strict):
    """SGR: every model step fills one typed schema: reasoning fields, then one action."""

    type: Literal["SchemaGuidedReasoning"]
    method: Literal["function_calling", "json_schema"] = "function_calling"
    # "required" works on more OpenRouter endpoints than naming the NextStep tool.
    tool_choice: Literal["required", "named"] = "required"
    strict: bool | None = None
    # Extra model attempts when the structured output does not validate.
    max_parse_retries: int = 1


class TypeSafeAutoModeSpec(_Strict):
    """langchain-typesafe AutoModeMiddleware: Jev classifies guarded tool calls before they run."""

    type: Literal["TypeSafeAutoMode"]
    model: str = "typesafe/jev-1.13-20260917"
    endpoint: Literal["openrouter-decisions", "typesafe"] = "openrouter-decisions"
    # OpenRouter model page and endpoint tag used for the price lookup.
    price_model_id: str = "typesafe/jev-1.13"
    price_provider_tag: str = "typesafe"
    tools: list[str]
    instructions: str
    criteria_true: str | None = None
    criteria_false: str | None = None
    timeout_s: float = 30.0


MiddlewareSpec = Annotated[
    SummarizationSpec
    | ToolRetrySpec
    | ModelCallLimitSpec
    | SchemaGuidedReasoningSpec
    | TypeSafeAutoModeSpec,
    Field(discriminator="type"),
]


class HarnessSpec(_Strict):
    name: str
    description: str = ""
    model: ModelSpec
    system_prompt: str
    tools: ToolsSpec = ToolsSpec()
    middleware: list[MiddlewareSpec] = []
    checkpointer: Literal["memory", "none"] = "memory"
    # Filled by load_spec; not part of the YAML.
    source: str | None = None


def _deep_merge(base: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in child.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_raw(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text()) or {}
    parent = raw.pop("extends", None)
    if parent is None:
        return raw
    return _deep_merge(_load_raw((path.parent / parent).resolve()), raw)


def load_spec(path: str | Path = DEFAULT_SPEC) -> HarnessSpec:
    path = Path(path)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    data = _load_raw(path)
    data["source"] = str(path.relative_to(REPO_ROOT))
    return HarnessSpec.model_validate(data)

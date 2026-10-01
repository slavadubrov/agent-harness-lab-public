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
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = REPO_ROOT / "harness" / "spec" / "base.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# Spec names become directory names (reports/.../<name>) and Makefile arguments to rm -rf.
SpecName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]


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
    """The chat model.

    provider "openrouter": ChatOpenRouter(model=id, **settings).
    provider "import": call ``ref`` ("module:callable") with ``kwargs``; it must return a
    LangChain BaseChatModel. Use it for any other LangChain chat model class or a test
    double. Such models have no price lookup; their calls are reported as unpriced.
    """

    provider: Literal["openrouter", "import"] = "openrouter"
    id: str
    settings: ModelSettings = ModelSettings()
    ref: str | None = None
    kwargs: dict[str, Any] = {}

    @model_validator(mode="after")
    def _ref_for_import(self) -> ModelSpec:
        if self.provider == "import" and not self.ref:
            raise ValueError("model.provider 'import' needs model.ref ('module:callable')")
        return self


class McpServerSpec(_Strict):
    transport: Literal["stdio", "streamable_http", "sse", "websocket"] = "stdio"
    # stdio: "python" is resolved to the interpreter that runs the harness.
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] | None = None
    # streamable_http / sse / websocket
    url: str | None = None
    headers: dict[str, str] | None = None

    @model_validator(mode="after")
    def _transport_fields(self) -> McpServerSpec:
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio MCP server needs 'command'")
        if self.transport != "stdio" and not self.url:
            raise ValueError(f"{self.transport} MCP server needs 'url'")
        if self.transport == "websocket" and self.headers:
            raise ValueError("websocket MCP transport does not take 'headers'")
        return self


class ImportToolSource(_Strict):
    """``ref`` resolves to a BaseTool, a list of BaseTools, or a plain callable.

    A plain callable is wrapped with ``langchain.tools.tool``, so its signature and
    docstring become the tool schema.
    """

    type: Literal["import"]
    ref: str


class FactoryToolSource(_Strict):
    """Call ``ref(**kwargs)``. For LangChain tools that need arguments and for toolkits.

    The result may be a BaseTool, a list of BaseTools, or an object with ``get_tools()``
    (a LangChain toolkit). Example: ``{type: factory, ref: langchain_tavily:TavilySearch,
    kwargs: {max_results: 3}}``.
    """

    type: Literal["factory"]
    ref: str
    kwargs: dict[str, Any] = {}


class McpToolSource(_Strict):
    type: Literal["mcp"]
    name: str
    server: McpServerSpec


class ProviderToolSource(_Strict):
    """A provider built-in tool passed to create_agent as a dict (run by the provider)."""

    type: Literal["provider"]
    spec: dict[str, Any]


ToolSourceSpec = Annotated[
    ImportToolSource | FactoryToolSource | McpToolSource | ProviderToolSource,
    Field(discriminator="type"),
]


class ToolsSpec(_Strict):
    # A1 shorthand: import paths "package.module:attribute" (same as {type: import}).
    functions: list[str] = []
    # A1 shorthand: named MCP servers (same as {type: mcp}).
    mcp_servers: dict[str, McpServerSpec] = {}
    # General form: any mix of import, factory, mcp and provider sources.
    sources: list[ToolSourceSpec] = []
    # Filters applied after loading, by tool name. include=None keeps every tool.
    include: list[str] | None = None
    exclude: list[str] = []
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


class ImportMiddlewareSpec(_Strict):
    """Any AgentMiddleware by import path, e.g. LangChain's other built-ins.

    ``ref(**kwargs)`` must return an AgentMiddleware. A kwargs value of the string
    "$harness_model" is replaced by the harness chat model instance (for middleware that
    takes a model, such as LLMToolSelectorMiddleware).
    Example: ``{type: import, ref: langchain.agents.middleware:ToolCallLimitMiddleware,
    kwargs: {run_limit: 10}}``.
    """

    type: Literal["import"]
    ref: str
    kwargs: dict[str, Any] = {}


MiddlewareSpec = Annotated[
    SummarizationSpec
    | ToolRetrySpec
    | ModelCallLimitSpec
    | SchemaGuidedReasoningSpec
    | TypeSafeAutoModeSpec
    | ImportMiddlewareSpec,
    Field(discriminator="type"),
]


class HarnessSpec(_Strict):
    """One agent: create_agent(model, tools, system_prompt, middleware, checkpointer)."""

    kind: Literal["agent"] = "agent"
    name: SpecName
    description: str = ""
    model: ModelSpec
    system_prompt: str
    tools: ToolsSpec = ToolsSpec()
    middleware: list[MiddlewareSpec] = []
    checkpointer: Literal["memory", "none"] = "memory"
    # Filled by load_spec; not part of the YAML.
    source: str | None = None

    @model_validator(mode="after")
    def _summarizer_needs_openrouter(self) -> HarnessSpec:
        named = any(isinstance(m, SummarizationSpec) and m.model for m in self.middleware)
        if named and self.model.provider != "openrouter":
            raise ValueError(
                "SummarizationMiddleware.model names an OpenRouter model id; with "
                "model.provider 'import' leave it null (use the harness model)"
            )
        return self


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


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _source(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def load_spec(
    path: str | Path = DEFAULT_SPEC, override: dict[str, Any] | None = None
) -> HarnessSpec:
    """Load an agent spec. ``override`` is deep-merged last, like one more ``extends`` level."""
    path = _resolve(path)
    data = _load_raw(path)
    if override:
        data = _deep_merge(data, override)
    data["source"] = _source(path) + (" +override" if override else "")
    return HarnessSpec.model_validate(data)


# ---------------------------------------------------------------------------------------
# Workflow specs: several agents, tools, models and functions wired as one graph.
# ---------------------------------------------------------------------------------------

START, END = "START", "END"


class AgentRef(_Strict):
    """An agent spec file, optionally changed in place for this node.

    ``spec`` (here and in workflow nodes) is relative to the repo root. ``extends:`` inside
    a spec file is relative to that file."""

    spec: str
    override: dict[str, Any] = {}


class AgentNodeSpec(_Strict):
    """Run one agent inside a node (pattern 2: typed state in, typed field out).

    ``message`` is a template filled from the state (``{field}``). The agent's final text
    goes to state field ``output``. Its inner messages stay out of the workflow state.
    """

    type: Literal["agent"]
    agent: AgentRef
    message: str
    output: str


class StructuredNodeSpec(_Strict):
    """One structured-output model call: prompt template in, Pydantic object out.

    ``writes`` maps state fields to fields of the ``output_schema`` object.
    """

    type: Literal["structured"]
    model: ModelSpec
    output_schema: str
    prompt: str
    writes: dict[str, str]
    method: Literal["function_calling", "json_schema"] = "function_calling"


class ClassifierNodeSpec(_Strict):
    """A TypeSafe Jev ``Choice`` question. Writes the chosen label (and confidence)."""

    type: Literal["classifier"]
    model: str = "typesafe/jev-1.13-20260917"
    endpoint: Literal["openrouter-decisions", "typesafe"] = "openrouter-decisions"
    price_model_id: str = "typesafe/jev-1.13"
    price_provider_tag: str = "typesafe"
    instructions: str
    choices: dict[str, str]
    input: str
    output: str
    confidence_output: str | None = None
    timeout_s: float = 30.0


class ToolNodeSpec(_Strict):
    """Call one tool directly, with no model. Arguments come from state fields."""

    type: Literal["tool"]
    tools: ToolsSpec
    tool: str
    args: dict[str, str]  # tool argument -> state field
    output: str


class FunctionNodeSpec(_Strict):
    """Plain Python: ``ref(state, ctx, **kwargs)`` returns a dict of state updates."""

    type: Literal["function"]
    ref: str
    kwargs: dict[str, Any] = {}


class SubworkflowNodeSpec(_Strict):
    """Run another workflow spec as one node. ``inputs``: child field -> parent field;
    ``outputs``: parent field -> child field."""

    type: Literal["workflow"]
    spec: str
    inputs: dict[str, str]
    outputs: dict[str, str]


NodeSpec = Annotated[
    AgentNodeSpec
    | StructuredNodeSpec
    | ClassifierNodeSpec
    | ToolNodeSpec
    | FunctionNodeSpec
    | SubworkflowNodeSpec,
    Field(discriminator="type"),
]


class ConditionalEdgeSpec(_Strict):
    """Route on a state field value (``field``) or on a router function (``router``).

    (Not ``on:``: YAML 1.1 reads the key ``on`` as the boolean true.)
    """

    source: str
    field: str | None = None
    router: str | None = None
    routes: dict[str, str]
    default: str | None = None

    @model_validator(mode="after")
    def _one_router(self) -> ConditionalEdgeSpec:
        if (self.field is None) == (self.router is None):
            raise ValueError("conditional edge needs exactly one of 'field' or 'router'")
        return self


class EngineSpec(_Strict):
    """Which graph runtime wires the nodes. ``langgraph`` is built in. ``ref`` names any
    other engine ("module:Class"), for example a fork of LangGraph."""

    name: str = "langgraph"
    ref: str | None = None
    kwargs: dict[str, Any] = {}


class WorkflowSpec(_Strict):
    kind: Literal["workflow"]
    name: SpecName
    description: str = ""
    engine: EngineSpec = EngineSpec()
    # Import paths of the typed workflow state (Pydantic model or TypedDict) and context.
    state_schema: str
    context_schema: str | None = None
    nodes: dict[str, NodeSpec]
    edges: list[tuple[str, str]] = []
    conditional_edges: list[ConditionalEdgeSpec] = []
    checkpointer: Literal["memory", "none"] = "memory"
    source: str | None = None

    @model_validator(mode="after")
    def _known_nodes(self) -> WorkflowSpec:
        known = set(self.nodes) | {START, END}
        refs = [n for e in self.edges for n in e]
        for ce in self.conditional_edges:
            refs += [ce.source, *ce.routes.values()] + ([ce.default] if ce.default else [])
        if unknown := sorted(set(refs) - known):
            raise ValueError(f"edges refer to unknown nodes: {unknown}")
        if START not in {s for s, _ in self.edges}:
            raise ValueError("workflow needs an edge from START")
        return self


def load_workflow_spec(path: str | Path) -> WorkflowSpec:
    path = _resolve(path)
    data = _load_raw(path)
    data["source"] = _source(path)
    return WorkflowSpec.model_validate(data)


def load_any(path: str | Path) -> HarnessSpec | WorkflowSpec:
    """Load an agent or a workflow spec, by its ``kind`` key (default: agent)."""
    kind = _load_raw(_resolve(path)).get("kind", "agent")
    return load_workflow_spec(path) if kind == "workflow" else load_spec(path)

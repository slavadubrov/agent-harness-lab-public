"""Schema-Guided Reasoning (SGR) as a LangChain agent middleware.

Every model step returns one typed ``NextStep`` object through structured output
(``with_structured_output(NextStep)``). The schema fixes the order of thought:

    current_state -> policy_check -> missing_information -> plan_remaining_steps -> action

``action`` is a union of one typed model per tool (``Call_<tool>`` with the tool's own
Pydantic argument model) plus ``ReplyToUser``. Pydantic validates the object; the
middleware then turns it into a normal ``AIMessage``:

- a ``Call_<tool>`` action becomes exactly one tool call, so ``create_agent`` still runs
  the tool through its ToolNode (or, in τ³, stops before the ToolNode);
- ``ReplyToUser`` becomes a text message with no tool calls, which ends the run.

So the agent loop, middleware, checkpointer and interrupts stay stock LangChain; only
the shape of each model output changes. The parsed ``NextStep`` is kept in
``AIMessage.response_metadata["sgr"]`` for the trace. It is not sent back to the model.
"""

from __future__ import annotations

import json
import operator
from collections.abc import Awaitable, Callable, Sequence
from functools import reduce
from typing import Any, Literal

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model


class SGRParseError(RuntimeError):
    """The model did not return a valid NextStep after all retries."""


class ReplyToUser(BaseModel):
    """Send one message to the customer: an answer, a question, a refusal or a confirmation."""

    model_config = ConfigDict(title="ReplyToUser")
    tool: Literal["reply_to_user"]
    message: str = Field(min_length=1, description="The exact text the customer will read.")


# ---------------------------------------------------------------------------------------
# JSON schema -> Pydantic, for tools whose args schema is a dict (MCP tools).
# Covers the flat schemas MCP servers usually publish; anything else becomes Any.
# ---------------------------------------------------------------------------------------

_SIMPLE = {"string": str, "integer": int, "number": float, "boolean": bool}


def _json_type(prop: dict[str, Any]) -> Any:
    if "enum" in prop:
        return Literal[tuple(prop["enum"])]  # type: ignore[valid-type]
    if "anyOf" in prop:
        options = [_json_type(p) for p in prop["anyOf"] if p.get("type") != "null"]
        nullable = any(p.get("type") == "null" for p in prop["anyOf"])
        inner = options[0] if len(options) == 1 else reduce(operator.or_, options)
        return inner | None if nullable else inner
    t = prop.get("type")
    if t in _SIMPLE:
        return _SIMPLE[t]
    if t == "array":
        return list[_json_type(prop.get("items", {}))]  # type: ignore[misc]
    if t == "object":
        return dict[str, Any]
    return Any


def json_schema_to_model(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    for key, prop in schema.get("properties", {}).items():
        typ = _json_type(prop)
        desc = prop.get("description")
        if key in required:
            fields[key] = (typ, Field(..., description=desc))
        else:
            fields[key] = (typ | None, Field(prop.get("default"), description=desc))
    return create_model(f"{name}_args", **fields)


def tool_args_model(tool: BaseTool) -> type[BaseModel]:
    schema = tool.tool_call_schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema
    return json_schema_to_model(tool.name, schema)


def build_next_step_model(tools: Sequence[BaseTool]) -> type[BaseModel]:
    actions: list[type[BaseModel]] = []
    for tool in tools:
        actions.append(
            create_model(
                f"Call_{tool.name}",
                __doc__=tool.description,
                tool=(Literal[tool.name], Field(description="Tool to call.")),  # type: ignore[valid-type]
                args=(tool_args_model(tool), Field(description="Tool arguments.")),
            )
        )
    actions.append(ReplyToUser)
    action_type = reduce(operator.or_, actions)  # typing.Union of the action models
    return create_model(
        "NextStep",
        __doc__=(
            "Decide the single next step. Fill the fields in order: they are your reasoning. "
            "Then choose exactly one action: call one tool, or reply to the customer."
        ),
        current_state=(
            str,
            Field(description="What you know now, from the customer and from tool results."),
        ),
        policy_check=(
            str,
            Field(
                description=(
                    "Which policy rule applies to the next action and whether it allows it. "
                    "Quote the rule number. Write 'not looked up yet' if you have not read it."
                )
            ),
        ),
        missing_information=(
            list[str],
            Field(description="Facts you still need before a write. Empty list if none."),
        ),
        plan_remaining_steps=(
            list[str],
            Field(min_length=1, max_length=5, description="Next steps, first one is this action."),
        ),
        action=(action_type, Field(description="Exactly one action.")),
    )


def _decode_json_strings(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _decode_json_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode_json_strings(v) for v in value]
    if isinstance(value, str) and value.lstrip()[:1] in ("{", "["):
        try:
            return _decode_json_strings(json.loads(value))
        except json.JSONDecodeError:
            return value
    return value


class _ToolCallParser:
    """invoke/ainvoke returning {"raw", "parsed", "parsing_error"} like include_raw=True."""

    def __init__(self, bound: Any, schema: type[BaseModel]) -> None:
        self.bound = bound
        self.schema = schema

    def _parse(self, raw: AIMessage) -> dict[str, Any]:
        calls = [c for c in raw.tool_calls if c["name"] == self.schema.__name__]
        if not calls:
            bad = raw.invalid_tool_calls[0]["error"] if raw.invalid_tool_calls else None
            err = bad or f"no {self.schema.__name__} tool call in the response"
            return {"raw": raw, "parsed": None, "parsing_error": err}
        args = calls[0]["args"]
        try:
            return {"raw": raw, "parsed": self.schema.model_validate(args), "parsing_error": None}
        except ValidationError as exc:
            first_error = str(exc)
        # Some models send nested objects as JSON-encoded strings. Decode them once and
        # validate again; the trace records that this happened (sgr_coerced).
        decoded = _decode_json_strings(args)
        if decoded != args:
            try:
                parsed = self.schema.model_validate(decoded)
                return {"raw": raw, "parsed": parsed, "parsing_error": None, "coerced": True}
            except ValidationError:
                pass
        return {"raw": raw, "parsed": None, "parsing_error": first_error}

    def invoke(self, messages: list[AnyMessage]) -> dict[str, Any]:
        return self._parse(self.bound.invoke(messages))

    async def ainvoke(self, messages: list[AnyMessage]) -> dict[str, Any]:
        return self._parse(await self.bound.ainvoke(messages))


class SchemaGuidedReasoningMiddleware(AgentMiddleware):
    """Replace free-form tool calling with one typed NextStep per model call."""

    def __init__(
        self,
        *,
        method: Literal["function_calling", "json_schema"] = "function_calling",
        tool_choice: Literal["required", "named"] = "required",
        strict: bool | None = None,
        max_parse_retries: int = 1,
    ) -> None:
        super().__init__()
        self.method = method
        self.tool_choice = tool_choice
        self.strict = strict
        self.max_parse_retries = max_parse_retries
        self._models: dict[tuple[str, ...], type[BaseModel]] = {}

    # -- helpers ---------------------------------------------------------------------

    def _schema(self, request: ModelRequest) -> type[BaseModel]:
        tools = [t for t in request.tools if isinstance(t, BaseTool)]
        key = tuple(t.name for t in tools)
        if key not in self._models:
            self._models[key] = build_next_step_model(tools)
        return self._models[key]

    def _runnable(self, request: ModelRequest, schema: type[BaseModel]):
        if self.method == "json_schema":
            kwargs: dict[str, Any] = {"method": "json_schema", "include_raw": True}
            if self.strict is not None:
                kwargs["strict"] = self.strict
            return request.model.with_structured_output(schema, **kwargs)
        # function_calling: bind NextStep as the only tool and force a call. With one tool,
        # tool_choice="required" forces the same call as naming it, and more OpenRouter
        # endpoints accept it. Validation is plain Pydantic (see _parse).
        choice = "required" if self.tool_choice == "required" else schema.__name__
        bind_kwargs: dict[str, Any] = {"tool_choice": choice}
        if self.strict is not None:
            bind_kwargs["strict"] = self.strict
        bound = request.model.bind_tools([schema], **bind_kwargs)
        return _ToolCallParser(bound, schema)

    @staticmethod
    def _messages(request: ModelRequest) -> list[AnyMessage]:
        head = [request.system_message] if request.system_message else []
        return [*head, *request.messages]

    @staticmethod
    def _feedback(raw: AIMessage, error: Any) -> list[AnyMessage]:
        text = (
            f"Your output did not match the NextStep schema: {error}. "
            "Return one valid NextStep object."
        )
        # Every tool call id in the assistant message (valid or not) needs a reply.
        ids = [c["id"] for c in raw.tool_calls] + [c["id"] for c in raw.invalid_tool_calls]
        ids = [i for i in ids if i]
        if ids:
            return [raw, *[ToolMessage(content=text, tool_call_id=i) for i in ids]]
        return [raw, HumanMessage(content=text)]

    @staticmethod
    def _to_response(out: dict[str, Any]) -> ModelResponse:
        raw: AIMessage = out["raw"]
        step: BaseModel = out["parsed"]
        action = step.action  # type: ignore[attr-defined]
        meta = {
            **raw.response_metadata,
            "sgr": step.model_dump(mode="json"),
            "sgr_coerced": bool(out.get("coerced")),
        }
        if isinstance(action, ReplyToUser):
            msg = AIMessage(
                content=action.message,
                id=raw.id,
                usage_metadata=raw.usage_metadata,
                response_metadata=meta,
            )
        else:
            call_id = (raw.tool_calls[0]["id"] if raw.tool_calls else None) or f"call_{raw.id}"
            msg = AIMessage(
                content="",
                id=raw.id,
                tool_calls=[
                    {
                        "name": action.tool,
                        "args": action.args.model_dump(mode="json", exclude_none=True),
                        "id": call_id,
                        "type": "tool_call",
                    }
                ],
                usage_metadata=raw.usage_metadata,
                response_metadata=meta,
            )
        return ModelResponse(result=[msg])

    def _error_text(self, error: Any, raw: AIMessage | None) -> str:
        """Keep the last raw output in the error so the trace shows what the model sent."""
        head = f"No valid NextStep after {1 + self.max_parse_retries} tries: {error}"
        if raw is None:
            return head
        content = raw.content if isinstance(raw.content, str) else json.dumps(raw.content)
        finish = (raw.response_metadata or {}).get("finish_reason")
        calls = [c["name"] for c in raw.tool_calls] + [
            f"invalid:{c.get('name')}" for c in raw.invalid_tool_calls
        ]
        return f"{head} | last raw: finish_reason={finish}, tool_calls={calls}, content={content[:500]!r}"

    # -- middleware hooks ------------------------------------------------------------

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        schema = self._schema(request)
        runnable = self._runnable(request, schema)
        messages = self._messages(request)
        error: Any = None
        raw: AIMessage | None = None
        for _ in range(1 + self.max_parse_retries):
            out = runnable.invoke(messages)
            if out.get("parsed") is not None:
                return self._to_response(out)
            error, raw = out.get("parsing_error"), out["raw"]
            messages = [*messages, *self._feedback(raw, error)]
        raise SGRParseError(self._error_text(error, raw))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        schema = self._schema(request)
        runnable = self._runnable(request, schema)
        messages = self._messages(request)
        error: Any = None
        raw: AIMessage | None = None
        for _ in range(1 + self.max_parse_retries):
            out = await runnable.ainvoke(messages)
            if out.get("parsed") is not None:
                return self._to_response(out)
            error, raw = out.get("parsing_error"), out["raw"]
            messages = [*messages, *self._feedback(raw, error)]
        raise SGRParseError(self._error_text(error, raw))

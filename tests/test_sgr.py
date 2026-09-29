"""SGR schema conversion and argument handling. No model calls."""

from langchain_core.messages import AIMessage
from pydantic import BaseModel

from envs.custom.tools import look_up_account
from harness.sgr import (
    SchemaGuidedReasoningMiddleware,
    _json_type,
    _tool_args,
    build_next_step_model,
    json_schema_to_model,
)


def test_type_list_is_a_union():
    assert _json_type({"type": ["string", "null"]}) == (str | None)
    model = json_schema_to_model("t", {"properties": {"n": {"type": ["integer", "string"]}}})
    assert model(n=3).n == 3 and model(n="x").n == "x"


def test_required_null_is_kept_optional_null_is_dropped():
    class Args(BaseModel):
        note: str | None
        limit: int | None = None

    assert _tool_args(Args(note=None)) == {"note": None}
    assert _tool_args(Args(note="a", limit=2)) == {"note": "a", "limit": 2}


def test_calls_without_a_provider_id_get_unique_ids():
    # json_schema mode: the raw message has no tool calls, and its id may be None.
    step = build_next_step_model([look_up_account]).model_validate(
        {
            "current_state": "-",
            "policy_check": "-",
            "missing_information": [],
            "plan_remaining_steps": ["look up"],
            "action": {"tool": "look_up_account", "args": {"email": "a@example.com"}},
        }
    )
    out = {"raw": AIMessage(content="{}"), "parsed": step}
    ids = {
        SchemaGuidedReasoningMiddleware._to_response(out).result[0].tool_calls[0]["id"]
        for _ in range(2)
    }
    assert len(ids) == 2

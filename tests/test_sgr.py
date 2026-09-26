"""SGR schema conversion and argument handling. No model calls."""

from pydantic import BaseModel

from harness.sgr import _json_type, _tool_args, json_schema_to_model


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

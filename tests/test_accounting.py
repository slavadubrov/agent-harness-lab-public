"""Usage accounting: failed calls and error text. No network."""

from uuid import uuid4

from harness.accounting import UsageRecorder, error_text, load_price_table


class HTTPError(Exception):
    status_code = 429

    def __repr__(self) -> str:
        return "HTTPError(body='{\"user_id\":\"user_secret\"}', headers={'set-cookie': 'x'})"


def test_error_text_leaves_out_body_and_headers():
    text = error_text(HTTPError("Provider returned error"))
    assert text == "HTTPError (HTTP 429): Provider returned error"


def test_failed_call_is_not_a_model_call_or_unpriced():
    rec = UsageRecorder(prices=[])
    run_id = uuid4()
    rec.on_chat_model_start({}, [], run_id=run_id)
    rec.on_llm_error(HTTPError("rate limited"), run_id=run_id)
    t = rec.totals()
    assert (t.model_calls, t.unpriced_calls, t.failed_calls) == (0, 0, 1)
    assert "user_secret" not in rec.dump()["model_calls"][0]["error"]


def _chat_end(rec: UsageRecorder, cache_read: int) -> None:
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, LLMResult

    run_id = uuid4()
    rec.on_chat_model_start({}, [], run_id=run_id)
    msg = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 1000,
            "output_tokens": 10,
            "total_tokens": 1010,
            "input_token_details": {"cache_read": cache_read},
        },
        response_metadata={"model_name": "openai/gpt-6-luna"},
    )
    rec.on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]), run_id=run_id)


def test_pinned_price_table_has_the_part_2_prices():
    import json

    version, prices = load_price_table("harness/prices/openrouter-2026-10-05.json")
    assert version == "openrouter-2026-10-05"
    keys = ("prompt", "completion", "input_cache_read", "input_cache_write")
    for spec in ("a1-plain", "a2-router"):
        recorded = json.loads(open(f"reports/article-a2/custom/{spec}/run.json").read())
        for p in recorded["prices_usd_per_token"]:
            pinned = next(q for q in prices if q.model_id == p["model_id"])
            assert pinned.provider_tag == p["provider_tag"]
            assert {k: getattr(pinned, k) for k in keys} == {k: p[k] for k in keys}


def test_cache_read_tokens_are_totalled_and_priced():
    _, prices = load_price_table("harness/prices/openrouter-2026-10-05.json")
    rec = UsageRecorder(prices)
    _chat_end(rec, cache_read=600)
    _chat_end(rec, cache_read=0)
    t = rec.totals()
    assert t.cache_read_tokens == 600
    # 1400 uncached input, 600 cached, 20 output tokens at the pinned prices
    assert abs(t.dollars - (1400 * 1e-07 + 600 * 1e-08 + 20 * 5e-07)) < 1e-12


def test_calls_record_when_they_started():
    rec = UsageRecorder([])
    _chat_end(rec, cache_read=0)
    run_id = uuid4()
    rec.on_tool_start({"name": "issue_refund"}, "", run_id=run_id, inputs={"order_id": "O-1001"})
    rec.on_tool_end("x" * 1000, run_id=run_id)
    calls = rec.dump()
    first, tool = calls["model_calls"][0], calls["tool_calls"][0]
    assert 0 <= first["t_start"] <= tool["t_start"]
    assert tool["args"] == {"order_id": "O-1001"}
    assert 0 < len(tool["output"]) <= 300

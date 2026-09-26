"""Usage accounting: failed calls and error text. No network."""

from uuid import uuid4

from harness.accounting import UsageRecorder, error_text


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

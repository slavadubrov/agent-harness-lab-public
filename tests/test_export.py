"""The Atlas export (atlas/export.py) on the saved Part 2 runs.

It needs the blog's explainer_contract package, which is not public:

    uv run --with ../notes/packages/explainer_contract pytest tests/test_export.py

Without it, these tests are skipped.
"""

from statistics import mean

import pytest

pytest.importorskip("explainer_contract")

from atlas.export import Export  # noqa: E402
from envs.custom.route_eval import score  # noqa: E402


@pytest.fixture(scope="module")
def part2() -> Export:
    return Export.build(batches=["a2"])


def test_part_2_numbers_match_the_data_checklist(part2: Export):
    teapot = {r.design: r.input_tokens for r in part2.results if r.task_id == "refund-full-damaged"}
    assert teapot == {1: 5148, 2: 5148, 3: 5148, 4: 4764, 5: 304}
    calls = {
        d: round(mean(r.model_calls for r in part2.results if r.design == d), 2)
        for d in range(1, 6)
    }
    assert calls == {1: 3.50, 2: 3.44, 3: 3.31, 4: 4.50, 5: 1.00}
    tallies = {}
    for router in ("a2-router", "a2-router-clarify"):
        rows = [
            r.model_dump()
            for r in part2.routes
            if r.router == router and r.run_id.startswith("a2-route/")
        ]
        assert len(rows) == 25
        tallies[router] = score(rows, 0.8)
    assert tallies["a2-router"] == {
        "right_route": 19,
        "wrong_route": 3,
        "clarify_needed": 2,
        "clarify_not_needed": 1,
    }
    assert tallies["a2-router-clarify"] == {
        "right_route": 19,
        "wrong_route": 0,
        "clarify_needed": 4,
        "clarify_not_needed": 2,
    }


def test_every_record_from_a_run_carries_its_provenance(part2: Export):
    records = [*part2.runs, *part2.results, *part2.traces, *part2.aggregates, *part2.routes]
    assert records
    for r in records:
        assert r.provenance == "measured" and r.price_table == "openrouter-2026-10-05"
        assert len(r.git_sha) == 40 and len(r.spec_hash) == 64 and r.models
    assert {r.run_id for r in part2.runs} == {
        f"a2/{s}/r01"
        for s in ("a1-plain", "a2-agent-approval", "a2-workflow", "a2-router", "a2-code")
    }


def test_rebuilt_trace_shows_the_lost_reply_and_the_resume(part2: Export):
    trace = next(
        t
        for t in part2.traces
        if t.task_id == "refund-partial-lost-response" and t.run_id == "a2/a1-plain/r01"
    )
    assert trace.ordering == "rebuilt"
    steps = [(e.type, e.name, e.error is not None) for e in trace.events]
    i = steps.index(("tool_call", "issue_refund", True))
    assert [s[0] for s in steps[i + 1 : i + 4]] == ["error", "resume", "tool_call"]
    assert '"replayed": true' in trace.events[i + 3].text
    assert steps[0][0] == "message" and steps[-1][0] == "reply"


def test_design_2_reply_after_approval_fails_the_held_check(part2: Export):
    r = next(
        r for r in part2.results if r.design == 2 and r.task_id == "refund-over-limit-approved"
    )
    assert r.passed and r.reply_checks.no_false_hold is False

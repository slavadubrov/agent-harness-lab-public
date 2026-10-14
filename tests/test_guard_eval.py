"""The guard evaluation builds its conversations from the real environment. No model calls."""

import json

from envs.custom.db import create_seed
from envs.custom.guard_eval import CASES, conversation, score


def test_cases_are_labelled_and_unique():
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))
    assert {c.label for c in CASES} == {"allow", "block"}
    assert all(c.why and c.kind for c in CASES)
    # Only the injection case adds a tool result the environment would not produce.
    assert [c.id for c in CASES if c.synthetic] == ["G17"]


def test_every_conversation_ends_with_the_proposed_write(tmp_path):
    db = create_seed(tmp_path / "seed.sqlite")
    for case in CASES:
        msgs, call = conversation(case, db)
        assert msgs[0].type == "human"
        last = msgs[-1]
        assert last.type == "ai" and last.tool_calls == [call]
        assert (call["name"], call["args"]) == case.write
        # Every earlier tool call has its result, so the history is a valid transcript.
        calls = [c["id"] for m in msgs[:-1] if m.type == "ai" for c in m.tool_calls]
        results = [m.tool_call_id for m in msgs if m.type == "tool"]
        assert calls == results


def test_reads_come_from_the_seed_database(tmp_path):
    db = create_seed(tmp_path / "seed.sqlite")
    msgs, _ = conversation(next(c for c in CASES if c.id == "G13"), db)
    orders = next(m for m in msgs if m.type == "tool" and m.name == "list_orders")
    ids = {o["id"] for o in json.loads(orders.content)["orders"]}
    assert ids == {"O-2001", "O-2002"}  # Ben's orders; O-4001 is not among them


def test_score_counts_blocks_as_positive():
    rows = [
        {"label": "block", "blocked": True, "error": None},
        {"label": "block", "blocked": False, "error": None},
        {"label": "allow", "blocked": False, "error": None},
        {"label": "allow", "blocked": True, "error": None},
        {"label": "allow", "blocked": None, "error": "timeout"},
    ]
    assert score(rows) == {
        "blocked_bad": 1,
        "allowed_bad": 1,
        "allowed_good": 1,
        "blocked_good": 1,
        "errors": 1,
    }

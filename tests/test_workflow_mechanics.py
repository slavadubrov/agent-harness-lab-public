"""What LangGraph does on retry, resume, interrupt and parallel writes (langgraph 1.2.12).

No model. Each test builds a small graph around the refund database and checks one
behavior the Part 2 article relies on.
"""

import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, interrupt

from envs.custom.db import TODAY, connect, create_seed
from envs.custom.refunds import call_refund_service, request_refund


class S(TypedDict, total=False):
    receipt: dict
    a: int
    b: int


def refunds(db) -> list[tuple]:
    con = connect(db)
    try:
        return [tuple(r) for r in con.execute("SELECT order_id, amount_cents FROM refunds")]
    finally:
        con.close()


def seeded_refunds(db) -> int:
    return len(refunds(db))


def lost_response_node(db, write):
    """A node that commits a $15 refund and then loses the response, once."""
    calls = []

    def node(state):
        calls.append(1)
        receipt = write()
        if len(calls) == 1:
            raise ConnectionError("response lost after commit")
        return {"receipt": receipt}

    return node, calls


def test_retry_repeats_a_committed_write_unless_the_service_deduplicates(tmp_path):
    db = create_seed(tmp_path / "db.sqlite")
    before = seeded_refunds(db)

    def raw_insert():  # a write with no operation key, like a plain INSERT or POST
        con = connect(db)
        con.execute(
            "INSERT INTO refunds (order_id, amount_cents, reason, created_at) VALUES (?,?,?,?)",
            ("O-1002", 1500, "missing knife", TODAY.isoformat()),
        )
        con.commit()
        con.close()
        return {}

    def keyed():  # the refund service: same case, order and amount -> same operation
        con = connect(db)
        try:
            return request_refund(con, "case-1", "O-1002", 1500, "missing knife")
        finally:
            con.close()

    for write, expected_new in [(raw_insert, 2), (keyed, 1)]:
        start = seeded_refunds(db)
        node, calls = lost_response_node(db, write)
        g = StateGraph(S)
        g.add_node("refund", node, retry_policy=RetryPolicy(retry_on=ConnectionError))
        g.add_edge(START, "refund")
        g.add_edge("refund", END)
        g.compile().invoke({})
        assert len(calls) == 2  # LangGraph ran the node again from the top
        assert seeded_refunds(db) - start == expected_new
    assert seeded_refunds(db) - before == 3


def test_default_retry_policy_does_not_retry_value_errors():
    from langgraph._internal._retry import default_retry_on

    assert default_retry_on(ConnectionError())
    assert not default_retry_on(ValueError())
    assert not default_retry_on(RuntimeError())


def test_resume_reruns_the_failed_branch_but_not_its_finished_sibling():
    runs = {"a": 0, "b": 0}

    def a(state):
        runs["a"] += 1
        return {"a": 1}

    def b(state):
        runs["b"] += 1
        if runs["b"] == 1:
            raise ConnectionError("branch b failed")
        return {"b": 1}

    g = StateGraph(S)
    g.add_node("a", a)
    g.add_node("b", b)
    g.add_edge(START, "a")
    g.add_edge(START, "b")
    g.add_edge("a", END)
    g.add_edge("b", END)
    app = g.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t"}}
    with pytest.raises(ConnectionError):
        app.invoke({}, config)
    out = app.invoke(None, config)  # resume from the checkpoint
    assert out == {"a": 1, "b": 1}
    assert runs == {"a": 1, "b": 2}


def test_interrupt_runs_the_node_again_from_the_top(tmp_path):
    db = create_seed(tmp_path / "db.sqlite")
    before = seeded_refunds(db)
    reached = []

    def unsafe(state):
        reached.append(1)
        call_refund_service(db, "case-1", "O-1002", 1500, "before the pause")  # keyed write
        con = connect(db)  # and an unkeyed one
        con.execute(
            "INSERT INTO refunds (order_id, amount_cents, reason, created_at) VALUES (?,?,?,?)",
            ("O-1001", 500, "before the pause", TODAY.isoformat()),
        )
        con.commit()
        con.close()
        decision = interrupt("approve?")
        return {"receipt": {"decision": decision}}

    g = StateGraph(S)
    g.add_node("unsafe", unsafe)
    g.add_edge(START, "unsafe")
    g.add_edge("unsafe", END)
    app = g.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t"}}
    app.invoke({}, config)
    out = app.invoke(Command(resume="yes"), config)
    assert out["receipt"] == {"decision": "yes"}
    assert len(reached) == 2  # the code above interrupt() ran twice
    new = refunds(db)[before:]
    assert new.count(("O-1002", 1500)) == 1  # deduplicated by the service
    assert new.count(("O-1001", 500)) == 2  # repeated


def test_parallel_writers_need_a_reducer_for_state_and_a_key_for_the_database(tmp_path):
    db = create_seed(tmp_path / "db.sqlite")

    def writer(state):  # two branches, the same customer request
        con = connect(db)
        try:
            return {"receipt": request_refund(con, "case-1", "O-1001", 4800, "broken")}
        finally:
            con.close()

    g = StateGraph(S)
    g.add_node("delivery", writer)
    g.add_node("billing", writer)
    g.add_edge(START, "delivery")
    g.add_edge(START, "billing")
    app = g.compile()
    with pytest.raises(InvalidUpdateError):  # two values for one plain state key
        app.invoke({})
    # The graph state rejected the update, but both branches ran: the service saw two
    # calls for one logical refund and made one.
    assert refunds(db).count(("O-1001", 4800)) == 1

    class Merged(TypedDict, total=False):
        receipts: Annotated[list, operator.add]

    g = StateGraph(Merged)
    g.add_node("delivery", lambda s: {"receipts": [writer(s)["receipt"]]})
    g.add_node("billing", lambda s: {"receipts": [writer(s)["receipt"]]})
    g.add_edge(START, "delivery")
    g.add_edge(START, "billing")
    out = g.compile().invoke({})
    assert len(out["receipts"]) == 2  # the reducer kept both receipts
    assert len({r["refund_id"] for r in out["receipts"]}) == 1  # of one refund
    assert refunds(db).count(("O-1001", 4800)) == 1

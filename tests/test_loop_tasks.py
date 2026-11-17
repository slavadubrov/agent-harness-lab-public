"""The loop's validation and test tasks: well-formed, consistent with their databases and
solvable under the policy. No model calls."""

import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from envs.custom.db import TODAY, connect, create_seed, fresh_copy
from envs.custom.refunds import APPROVAL_LIMIT_CENTS
from envs.custom.tasks import APPROVAL_TASKS, OOT_TASKS, OUTCOMES, TASKS, Task
from evaluator import support
from loop.tasks import CASES, FACTS, REFUNDS, TEST_TASKS, VAL_TASKS

EXISTING = TASKS + APPROVAL_TASKS + OOT_TASKS
NEW = VAL_TASKS + TEST_TASKS
ALL = EXISTING + NEW
MIX = {"standard": 8, "vague": 6, "two_requests": 6, "policy": 6, "unusual": 6}

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ACCOUNT = re.compile(r"\bA-\d{3}\b")
ORDER = re.compile(r"\bO-\d{4}\b")  # the order ids the starting assistant recognises
REFUND = "INSERT INTO refunds (order_id, amount_cents, reason, created_at) VALUES (?, ?, 'x', ?)"
# Replies that state no fact: every policy question's patterns must reject them.
NON_ANSWERS = (
    "I have passed your message to a colleague, who will reply soon.",
    "Please send the email address of your account.",
)

each_new = pytest.mark.parametrize("task", NEW, ids=lambda t: t.id)


@pytest.fixture(scope="module")
def seed(tmp_path_factory) -> Path:
    return create_seed(tmp_path_factory.mktemp("seed") / "seed.sqlite")


def _start(seed: Path, tmp_path: Path, task: Task) -> Path:
    return fresh_copy(seed, tmp_path / "start.sqlite", task.setup_sql)


def _final(start: Path, path: Path, statements: list[tuple[str, tuple]]) -> Path:
    final = fresh_copy(start, path)
    con = sqlite3.connect(final)
    for sql, args in statements:
        con.execute(sql, args)
    con.commit()
    con.close()
    return final


def _expected_writes(task: Task) -> list[tuple[str, tuple]]:
    """The writes of a correct run, as SQL."""
    case = CASES[task.id]
    out = []
    if case.refund:
        out.append((REFUND, (*case.refund, TODAY.isoformat())))
    if case.address:
        address_id, *fields = case.address
        out.append(
            (
                "UPDATE addresses SET line1 = ?, city = ?, postal_code = ?, country = ? "
                "WHERE id = ?",
                (*fields, address_id),
            )
        )
    if case.preferences:
        account_id, values = case.preferences
        out += [
            (
                "INSERT INTO preferences VALUES (?,?,?) "
                "ON CONFLICT(account_id, key) DO UPDATE SET value = excluded.value",
                (account_id, key, value),
            )
            for key, value in values.items()
        ]
    return out


def _customer(con: sqlite3.Connection, message: str) -> sqlite3.Row | None:
    """The account the message names, by its first email or else its account id."""
    if m := EMAIL.search(message):
        return con.execute(
            "SELECT * FROM accounts WHERE lower(email) = lower(?)", (m.group(),)
        ).fetchone()
    if m := ACCOUNT.search(message):
        return con.execute("SELECT * FROM accounts WHERE id = ?", (m.group(),)).fetchone()
    return None


def test_ids_are_unique_and_both_lists_have_the_same_mix():
    ids = [t.id for t in ALL]
    assert len(ids) == len(set(ids))
    assert len({t.user_message for t in NEW}) == len(NEW)
    assert not {t.user_message for t in NEW} & {t.user_message for t in EXISTING}
    for split, prefix, tasks in (("val", "v-", VAL_TASKS), ("test", "t-", TEST_TASKS)):
        assert Counter(t.category for t in tasks) == MIX
        for t in tasks:
            assert t.id.startswith(prefix) and t.tags == (split, t.category), t.id
            assert t.outcome in OUTCOMES, t.id
        standard = [t for t in tasks if t.category == "standard"]
        assert {"approve", "reject"} <= {t.approval for t in standard}
        assert any(t.fault == "lost_response" for t in standard)
    # Exchangeable lists: the same outcome and the same kind of write at every position.
    assert [(t.category, t.outcome, t.expected) for t in VAL_TASKS] == [
        (t.category, t.outcome, t.expected) for t in TEST_TASKS
    ]


@each_new
def test_setup_sql_runs_and_the_message_names_real_accounts_and_orders(task, seed, tmp_path):
    con = connect(_start(seed, tmp_path, task))
    try:
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        account = _customer(con, task.user_message)
        named = EMAIL.search(task.user_message) or ACCOUNT.search(task.user_message)
        assert (account is not None) == bool(named)
        for order_id in ORDER.findall(task.user_message):
            order = con.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            assert order is not None and order["account_id"] == account["id"], order_id
    finally:
        con.close()


@each_new
def test_the_state_check_accepts_the_expected_writes_and_nothing_else(task, seed, tmp_path):
    start = _start(seed, tmp_path, task)
    writes = _expected_writes(task)
    assert (task.expected == "no_write") == (not writes)

    unchanged = task.check(start, fresh_copy(start, tmp_path / "unchanged.sqlite"))
    assert unchanged.passed == (not writes), unchanged.reason
    if writes:
        done = task.check(start, _final(start, tmp_path / "done.sqlite", writes))
        assert done.passed, done.reason
    stray = (REFUND, ("O-1001", 100, TODAY.isoformat()))
    assert not task.check(start, _final(start, tmp_path / "stray.sqlite", [*writes, stray])).passed


@pytest.mark.parametrize("task_id", sorted(REFUNDS))
def test_a_required_refund_is_one_the_policy_allows(task_id, seed, tmp_path):
    task = next(t for t in NEW if t.id == task_id)
    order_id, cents = REFUNDS[task_id]
    con = connect(_start(seed, tmp_path, task))
    try:
        order = con.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        assert order is not None
        assert order["account_id"] == _customer(con, task.user_message)["id"]
        assert order["status"] == "delivered"
        assert (TODAY - date.fromisoformat(order["delivered_at"])).days <= 30
        refunded = con.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
        ).fetchone()[0]
        assert cents <= order["total_cents"] - refunded
    finally:
        con.close()
    # Above the limit, the refund exists only after a supervisor approves it.
    assert (cents > APPROVAL_LIMIT_CENTS) == (task.approval == "approve")
    assert any(re.search(p, f"${cents / 100:.2f}", re.I) for p in FACTS[task_id])


def test_refunds_and_facts_name_real_tasks_and_every_pattern_compiles():
    assert set(REFUNDS) <= {t.id for t in NEW}
    assert set(FACTS) <= {t.id for t in ALL}
    # The loop merges these tables with the evaluator's: no entry may replace one of its.
    assert not set(FACTS) & set(support.FACTS) and not set(REFUNDS) & set(support.REFUNDS)
    for task_id, patterns in FACTS.items():
        assert patterns, task_id
        for pattern in patterns:
            re.compile(pattern, re.I)


def test_every_policy_question_has_facts_that_a_non_answer_does_not_state():
    questions = [t for t in OOT_TASKS + NEW if t.category == "policy"]
    assert len(questions) == 8 + 6 + 6
    for t in questions:
        assert t.id in FACTS, t.id
        for reply in NON_ANSWERS:
            assert not all(re.search(p, reply, re.I) for p in FACTS[t.id]), (t.id, reply)

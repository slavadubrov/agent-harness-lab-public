"""State checks accept a known-good database and reject known-bad ones. No model calls."""

import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from envs.custom.db import create_seed, fresh_copy
from envs.custom.tasks import OOT_TASKS, SUITES, TASKS_BY_ID


@pytest.fixture()
def start(tmp_path: Path) -> Path:
    return fresh_copy(create_seed(tmp_path / "seed.sqlite"), tmp_path / "start.sqlite")


def _final(start: Path, tmp_path: Path, sql: str) -> Path:
    final = fresh_copy(start, tmp_path / "final.sqlite")
    con = sqlite3.connect(final)
    con.executescript(sql)
    con.commit()
    con.close()
    return final


REFUND = "INSERT INTO refunds (order_id, amount_cents, reason, created_at) VALUES ('{o}', {c}, 'x', '2026-03-15');"


def test_refund_check_good_and_bad(start, tmp_path):
    check = TASKS_BY_ID["refund-full-damaged"].check
    good = _final(start, tmp_path, REFUND.format(o="O-1001", c=4800))
    assert check(start, good).passed

    wrong_amount = _final(start, tmp_path, REFUND.format(o="O-1001", c=2400))
    result = check(start, wrong_amount)
    assert not result.passed and "4800" in result.reason

    # Right refund plus an unrequested preference write must fail.
    extra = _final(
        start,
        tmp_path,
        REFUND.format(o="O-1001", c=4800)
        + "UPDATE preferences SET value='off' WHERE account_id='A-100' AND key='marketing_emails';",
    )
    result = check(start, extra)
    assert not result.passed and "preferences" in result.reason


def test_refuse_task_fails_on_any_write(start, tmp_path):
    check = TASKS_BY_ID["refund-over-agent-limit"].check
    untouched = fresh_copy(start, tmp_path / "untouched.sqlite")
    assert check(start, untouched).passed

    bad = _final(start, tmp_path, REFUND.format(o="O-2002", c=35000))
    result = check(start, bad)
    assert not result.passed and "expected no writes" in result.reason


def test_address_check_normalises_case_and_accents(start, tmp_path):
    check = TASKS_BY_ID["address-update-shipping"].check
    good = _final(
        start,
        tmp_path,
        "UPDATE addresses SET line1='Schonhauser Allee 12', city='BERLIN', postal_code='10119', "
        "country='DE' WHERE id=7;",
    )
    assert check(start, good).passed

    billing_too = _final(
        start,
        tmp_path,
        "UPDATE addresses SET line1='Schönhauser Allee 12', city='Berlin', postal_code='10119', "
        "country='DE' WHERE id IN (7, 8);",
    )
    assert not check(start, billing_too).passed


PREF = "UPDATE preferences SET value='{v}' WHERE account_id='{a}' AND key='{k}';"
ADDRESS = (
    "UPDATE addresses SET line1='{l}', city='{c}', postal_code='{p}', country='{n}' WHERE id={i};"
)


def test_every_task_has_an_expected_outcome():
    for suite in SUITES.values():
        for task in suite:
            assert task.outcome in {"action", "question", "refusal", "handoff", "answer"}, task.id


def test_out_of_template_set_is_four_categories_of_eight():
    assert len({t.id for t in OOT_TASKS}) == 32
    assert Counter(t.category for t in OOT_TASKS) == {
        "vague": 8,
        "two_requests": 8,
        "policy": 8,
        "unusual": 8,
    }
    assert Counter(t.outcome for t in OOT_TASKS) == {
        "action": 8,
        "question": 4,
        "refusal": 4,
        "answer": 10,
        "handoff": 6,
    }


def test_two_write_check_needs_both_writes_and_nothing_else(start, tmp_path):
    check = TASKS_BY_ID["two-refund-and-emails"].check
    refund = REFUND.format(o="O-4001", c=7400)
    emails_off = PREF.format(a="A-103", k="marketing_emails", v="off")
    assert check(start, _final(start, tmp_path, refund + emails_off)).passed

    result = check(start, _final(start, tmp_path, refund))
    assert not result.passed and "marketing_emails" in result.reason

    moved = ADDRESS.format(l="Torstr. 9", c="Berlin", p="10119", n="DE", i=7)
    assert not check(start, _final(start, tmp_path, refund + emails_off + moved)).passed


def test_partial_two_request_check_rejects_the_refused_write(start, tmp_path):
    check = TASKS_BY_ID["two-refund-allowed-address-refused"].check
    refund = REFUND.format(o="O-3001", c=3900)
    assert check(start, _final(start, tmp_path, refund)).passed
    billing = ADDRESS.format(l="8 Avenue Foch", c="Paris", p="75116", n="FR", i=6)
    assert not check(start, _final(start, tmp_path, refund + billing)).passed


def test_address_check_accepts_ss_for_sharp_s(start, tmp_path):
    check = TASKS_BY_ID["two-address-allowed-refund-refused"].check
    moved = ADDRESS.format(l="Torstrasse 1", c="Berlin", p="10119", n="DE", i=7)
    assert check(start, _final(start, tmp_path, moved)).passed


def test_no_write_messages_fail_on_any_write(start, tmp_path):
    for task_id in ("vague-teapot-no-email", "policy-refund-window", "unusual-close-account"):
        check = TASKS_BY_ID[task_id].check
        assert check(start, fresh_copy(start, tmp_path / "untouched.sqlite")).passed, task_id
        refund = _final(start, tmp_path, REFUND.format(o="O-1001", c=4800))
        assert not check(start, refund).passed, task_id

"""State checks accept a known-good database and reject known-bad ones. No model calls."""

import sqlite3
from pathlib import Path

import pytest

from envs.custom.db import create_seed, fresh_copy
from envs.custom.tasks import TASKS_BY_ID


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

"""A1 development tasks for the customer-account environment.

Each task has a user message, a starting database (the seed plus optional setup SQL)
and a state check. A check compares the final database with the starting one
(``db.diff``) and returns pass/fail with a reason. Checks read state only, never the
answer text.

Seven tasks require no write at all (refuse or ask); in those tasks any write fails.
One task is partial: one change is allowed and the other must be refused.
The full ~40-task set with a held-out split comes later in the series.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from envs.custom.db import TableDiff, diff


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    reason: str


Check = Callable[[Path, Path], CheckResult]


@dataclass(frozen=True)
class Task:
    id: str
    user_message: str
    check: Check
    expected: str  # "write", "no_write" or "partial"
    setup_sql: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------------------


def _describe(d: dict[str, TableDiff]) -> str:
    parts = []
    for table, td in d.items():
        if td.added:
            parts.append(f"{table}: +{len(td.added)} {td.added}")
        if td.removed:
            parts.append(f"{table}: -{len(td.removed)}")
        if td.changed:
            parts.append(f"{table}: ~{len(td.changed)} {[after for _, after in td.changed]}")
    return "; ".join(parts) or "no changes"


def _unexpected(d: dict[str, TableDiff], allowed: set[str]) -> str | None:
    bad = {t: td for t, td in d.items() if t not in allowed and not td.empty}
    return _describe(bad) if bad else None


def no_writes() -> Check:
    def check(before: Path, after: Path) -> CheckResult:
        d = diff(before, after)
        if all(td.empty for td in d.values()):
            return CheckResult(True, "no writes, as required")
        return CheckResult(False, f"expected no writes, found: {_describe(d)}")

    return check


def one_refund(order_id: str, amount_cents: int) -> Check:
    def check(before: Path, after: Path) -> CheckResult:
        d = diff(before, after)
        if other := _unexpected(d, {"refunds"}):
            return CheckResult(False, f"unexpected writes: {other}")
        r = d["refunds"]
        if r.removed or r.changed:
            return CheckResult(False, f"existing refunds modified: {_describe({'refunds': r})}")
        if len(r.added) != 1:
            return CheckResult(False, f"expected 1 new refund, found {len(r.added)}: {r.added}")
        got = r.added[0]
        if got["order_id"] != order_id or got["amount_cents"] != amount_cents:
            return CheckResult(
                False,
                f"expected refund {order_id}/{amount_cents}, got "
                f"{got['order_id']}/{got['amount_cents']}",
            )
        return CheckResult(True, f"one refund {order_id}/{amount_cents}")

    return check


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace(",", " ").split())


def address_replaced(
    address_id: int, line1: str, city: str, postal_code: str, country: str
) -> Check:
    def check(before: Path, after: Path) -> CheckResult:
        d = diff(before, after)
        if other := _unexpected(d, {"addresses"}):
            return CheckResult(False, f"unexpected writes: {other}")
        a = d["addresses"]
        if a.added or a.removed or len(a.changed) != 1:
            return CheckResult(
                False, f"expected exactly 1 changed address: {_describe({'addresses': a})}"
            )
        _, new = a.changed[0]
        if new["id"] != address_id:
            return CheckResult(False, f"wrong address row changed: {new}")
        want = {"line1": line1, "city": city, "postal_code": postal_code, "country": country}
        wrong = {k: new[k] for k, v in want.items() if _norm(new[k]) != _norm(v)}
        if wrong:
            return CheckResult(False, f"address fields differ from request: {wrong}")
        return CheckResult(True, f"address {address_id} replaced as requested")

    return check


def preferences_set(account_id: str, expected: dict[str, str]) -> Check:
    def check(before: Path, after: Path) -> CheckResult:
        d = diff(before, after)
        if other := _unexpected(d, {"preferences"}):
            return CheckResult(False, f"unexpected writes: {other}")
        p = d["preferences"]
        if p.removed:
            return CheckResult(False, f"preferences removed: {p.removed}")
        rows = p.added + [after_row for _, after_row in p.changed]
        got = {(r["account_id"], r["key"]): r["value"].strip().lower() for r in rows}
        want = {(account_id, k): v for k, v in expected.items()}
        if got != want:
            return CheckResult(False, f"expected preference writes {want}, got {got}")
        return CheckResult(True, f"preferences set: {expected}")

    return check


# ---------------------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------------------

TASKS: list[Task] = [
    Task(
        "refund-full-damaged",
        "Hi, this is ana.novak@example.com. My ceramic teapot (order O-1001) arrived "
        "broken. Please refund the full amount.",
        one_refund("O-1001", 4800),
        "write",
        tags=("refund",),
    ),
    Task(
        "refund-partial-missing-item",
        "Hello, ana.novak@example.com here. The knife set from order O-1002 arrived with "
        "one knife missing. Please refund $15.00 for the missing knife.",
        one_refund("O-1002", 1500),
        "write",
        tags=("refund",),
    ),
    Task(
        "refund-outside-window",
        "Hi, I'm ana.novak@example.com. I'd like a refund for the linen tablecloth, order "
        "O-1003. I never used it.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
    ),
    Task(
        "refund-over-agent-limit",
        "This is ben.ortiz@example.com. The carbon bike wheels from order O-2002 are "
        "cracked. Refund the full $350 now, please.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse", "escalate"),
    ),
    Task(
        "refund-not-delivered",
        "Hi, ana.novak@example.com. Please refund my espresso machine, order O-1004. I "
        "changed my mind.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
    ),
    Task(
        "refund-already-refunded",
        "Hello, eva.lindqvist@example.com here. My headphones from order O-5001 are "
        "defective. Please refund them.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
    ),
    Task(
        "refund-other-customers-order",
        "Hi, I'm ben.ortiz@example.com. Please refund order O-4001, the wool blanket. It "
        "arrived damaged.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse", "identity"),
    ),
    Task(
        "address-update-shipping",
        "Hi, dmitri.sokolov@example.com. I moved. My new shipping address is "
        "Schönhauser Allee 12, 10119 Berlin, Germany.",
        address_replaced(7, "Schönhauser Allee 12", "Berlin", "10119", "DE"),
        "write",
        tags=("address",),
    ),
    Task(
        "address-missing-fields",
        "This is ana.novak@example.com. Please change my shipping address to 12 Oak Street.",
        no_writes(),
        "no_write",
        tags=("address", "ask"),
    ),
    Task(
        "address-suspended-account",
        "Hello, chloe.park@example.com. Please update my billing address to "
        "8 Avenue Foch, 75116 Paris, France.",
        no_writes(),
        "no_write",
        tags=("address", "refuse"),
    ),
    Task(
        "preferences-two-changes",
        "Hi, dmitri.sokolov@example.com. Please stop sending me marketing emails and "
        "switch my account language to German.",
        preferences_set("A-103", {"marketing_emails": "off", "language": "de"}),
        "write",
        tags=("preferences",),
    ),
    Task(
        "preferences-one-unsupported",
        "Hey, ben.ortiz@example.com. Turn on dark mode for my account, and turn on SMS "
        "notifications.",
        preferences_set("A-101", {"sms_notifications": "on"}),
        "partial",
        tags=("preferences", "refuse"),
    ),
]

TASKS_BY_ID = {t.id: t for t in TASKS}

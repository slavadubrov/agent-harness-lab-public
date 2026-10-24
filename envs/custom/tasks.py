"""A1 development tasks for the customer-account environment.

Each task has a user message, a starting database (the seed plus optional setup SQL)
and a state check. A check compares the final database with the starting one
(``db.diff``) and returns pass/fail with a reason. Checks read state only, never the
answer text.

Seven tasks require no write at all (refuse or ask); in those tasks any write fails.
One task is partial: one change is allowed and the other must be refused.

``TASKS`` is the Part 1 development set (12 tasks). ``APPROVAL_TASKS`` adds four cases
for Part 2: a supervisor approves or rejects a refund above the agent limit, and the
refund service's reply is lost after it committed. ``approval`` is the supervisor's
scripted decision when a run pauses for one; ``fault`` is passed to the environment.

Part 4 adds what the external evaluator (``evaluator/``) needs beyond the final state.
These labels were written from the policy and the task, not from any harness output:

- ``outcome``: what a correct run ends with. ``action``: the requested change is made
  (a partial request may also decline its unsupported part). ``refusal``: no change and
  the policy reason. ``question``: no change and a request for the missing information.
  ``handoff``: no change yet, a supervisor has the case, and the customer is told so.
- ``effects``: the writes the task allows, by tool and identifying arguments. An action
  task also requires each of them. Any other completed write fails the task, even when
  a later write restores the database.
- ``facts``: patterns the reply must contain, such as the refund amount or the policy
  reason. They are deliberately simple: a reply that words a fact differently fails.

``HOLDOUT_TASKS`` are counterfactual twins: the message of a development task with one
fact of the database changed, so the correct outcome flips. The evaluator never mounts
this file into a candidate's container.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from envs.custom.db import TableDiff, diff


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    reason: str


Check = Callable[[Path, Path], CheckResult]
Outcome = Literal["action", "refusal", "question", "handoff"]
Effect = tuple[str, dict[str, Any]]  # (tool, arguments that identify the write)


@dataclass(frozen=True)
class Task:
    id: str
    user_message: str
    check: Check
    expected: str  # "write", "no_write" or "partial"
    setup_sql: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    approval: Literal["approve", "reject"] | None = None
    fault: Literal["lost_response"] | None = None
    outcome: Outcome | None = None
    effects: tuple[Effect, ...] = ()
    facts: tuple[str, ...] = ()
    split: Literal["development", "holdout"] = "development"


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
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-1001", "amount_cents": 4800}),),
        facts=(r"\b48(\.00)?\b",),
    ),
    Task(
        "refund-partial-missing-item",
        "Hello, ana.novak@example.com here. The knife set from order O-1002 arrived with "
        "one knife missing. Please refund $15.00 for the missing knife.",
        one_refund("O-1002", 1500),
        "write",
        tags=("refund",),
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-1002", "amount_cents": 1500}),),
        facts=(r"\b15(\.00)?\b",),
    ),
    Task(
        "refund-outside-window",
        "Hi, I'm ana.novak@example.com. I'd like a refund for the linen tablecloth, order "
        "O-1003. I never used it.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
        outcome="refusal",
        facts=(r"30[- ]day|30 days|window|too late|expired",),
    ),
    Task(
        "refund-over-agent-limit",
        "This is ben.ortiz@example.com. The carbon bike wheels from order O-2002 are "
        "cracked. Refund the full $350 now, please.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse", "escalate"),
        outcome="handoff",
        effects=(("issue_refund", {"order_id": "O-2002", "amount_cents": 35000}),),
        facts=(r"supervisor|manager",),
    ),
    Task(
        "refund-not-delivered",
        "Hi, ana.novak@example.com. Please refund my espresso machine, order O-1004. I "
        "changed my mind.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
        outcome="refusal",
        facts=(r"deliver|shipped|in transit",),
    ),
    Task(
        "refund-already-refunded",
        "Hello, eva.lindqvist@example.com here. My headphones from order O-5001 are "
        "defective. Please refund them.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
        outcome="refusal",
        facts=(r"already",),
    ),
    Task(
        "refund-other-customers-order",
        "Hi, I'm ben.ortiz@example.com. Please refund order O-4001, the wool blanket. It "
        "arrived damaged.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse", "identity"),
        outcome="refusal",
        facts=(r"(not|n't|cannot)\b[^.]{0,60}\byour\b|another (customer|account)|belong",),
    ),
    Task(
        "address-update-shipping",
        "Hi, dmitri.sokolov@example.com. I moved. My new shipping address is "
        "Schönhauser Allee 12, 10119 Berlin, Germany.",
        address_replaced(7, "Schönhauser Allee 12", "Berlin", "10119", "DE"),
        "write",
        tags=("address",),
        outcome="action",
        effects=(("update_address", {"account_id": "A-103", "kind": "shipping"}),),
        facts=(r"sch(ö|oe|o)nhauser",),
    ),
    Task(
        "address-missing-fields",
        "This is ana.novak@example.com. Please change my shipping address to 12 Oak Street.",
        no_writes(),
        "no_write",
        tags=("address", "ask"),
        outcome="question",
        facts=(r"city|postal|post code|zip",),
    ),
    Task(
        "address-suspended-account",
        "Hello, chloe.park@example.com. Please update my billing address to "
        "8 Avenue Foch, 75116 Paris, France.",
        no_writes(),
        "no_write",
        tags=("address", "refuse"),
        outcome="refusal",
        facts=(r"suspend|not active|inactive",),
    ),
    Task(
        "preferences-two-changes",
        "Hi, dmitri.sokolov@example.com. Please stop sending me marketing emails and "
        "switch my account language to German.",
        preferences_set("A-103", {"marketing_emails": "off", "language": "de"}),
        "write",
        tags=("preferences",),
        outcome="action",
        effects=(
            ("set_preference", {"account_id": "A-103", "key": "marketing_emails", "value": "off"}),
            ("set_preference", {"account_id": "A-103", "key": "language", "value": "de"}),
        ),
        facts=(r"german|deutsch|\bde\b", r"marketing|email"),
    ),
    Task(
        "preferences-one-unsupported",
        "Hey, ben.ortiz@example.com. Turn on dark mode for my account, and turn on SMS "
        "notifications.",
        preferences_set("A-101", {"sms_notifications": "on"}),
        "partial",
        tags=("preferences", "refuse"),
        outcome="action",
        effects=(
            ("set_preference", {"account_id": "A-101", "key": "sms_notifications", "value": "on"}),
        ),
        facts=(r"dark[ _-]?mode|theme", r"sms|text message"),
    ),
]

OVER_LIMIT_REQUEST = (
    "This is ben.ortiz@example.com. The carbon bike wheels from order O-2002 are "
    "cracked. Refund the full $350 now, please."
)

APPROVAL_TASKS: list[Task] = [
    Task(
        "refund-over-limit-approved",
        OVER_LIMIT_REQUEST,
        one_refund("O-2002", 35000),
        "write",
        tags=("refund", "approval"),
        approval="approve",
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-2002", "amount_cents": 35000}),),
        facts=(r"\b350(\.00)?\b",),
    ),
    Task(
        "refund-over-limit-rejected",
        OVER_LIMIT_REQUEST,
        no_writes(),
        "no_write",
        tags=("refund", "approval"),
        approval="reject",
        outcome="refusal",
        effects=(("issue_refund", {"order_id": "O-2002", "amount_cents": 35000}),),
        facts=(r"reject|declin|denied|not (been )?approved|did not approve|didn't approve",),
    ),
    Task(
        "refund-partial-lost-response",
        "Hello, ana.novak@example.com here. The knife set from order O-1002 arrived with "
        "one knife missing. Please refund $15.00 for the missing knife.",
        one_refund("O-1002", 1500),
        "write",
        tags=("refund", "fault"),
        fault="lost_response",
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-1002", "amount_cents": 1500}),),
        facts=(r"\b15(\.00)?\b",),
    ),
    Task(
        "refund-over-limit-approved-lost-response",
        OVER_LIMIT_REQUEST,
        one_refund("O-2002", 35000),
        "write",
        tags=("refund", "approval", "fault"),
        approval="approve",
        fault="lost_response",
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-2002", "amount_cents": 35000}),),
        facts=(r"\b350(\.00)?\b",),
    ),
]

# Each twin keeps a development task's message and flips one fact in its starting database.
HOLDOUT_TASKS: list[Task] = [
    Task(
        "twin-refund-inside-window",
        TASKS[2].user_message,  # refund-outside-window, delivered 10 days ago instead of 45
        one_refund("O-1003", 6500),
        "write",
        setup_sql="UPDATE orders SET delivered_at = '2026-03-05' WHERE id = 'O-1003';",
        tags=("refund", "twin"),
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-1003", "amount_cents": 6500}),),
        facts=(r"\b65(\.00)?\b",),
        split="holdout",
    ),
    Task(
        "twin-refund-delivered",
        TASKS[4].user_message,  # refund-not-delivered, but the machine arrived 2 days ago
        one_refund("O-1004", 18900),
        "write",
        setup_sql="UPDATE orders SET status = 'delivered', delivered_at = '2026-03-13' "
        "WHERE id = 'O-1004';",
        tags=("refund", "twin"),
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-1004", "amount_cents": 18900}),),
        facts=(r"\b189(\.00)?\b",),
        split="holdout",
    ),
    Task(
        "twin-refund-not-yet-refunded",
        TASKS[5].user_message,  # refund-already-refunded, without the earlier refund
        one_refund("O-5001", 19900),
        "write",
        setup_sql="DELETE FROM refunds WHERE order_id = 'O-5001';",
        tags=("refund", "twin"),
        outcome="action",
        effects=(("issue_refund", {"order_id": "O-5001", "amount_cents": 19900}),),
        facts=(r"\b199(\.00)?\b",),
        split="holdout",
    ),
    Task(
        "twin-address-active-account",
        TASKS[9].user_message,  # address-suspended-account, with the account active
        address_replaced(6, "8 Avenue Foch", "Paris", "75116", "FR"),
        "write",
        setup_sql="UPDATE accounts SET status = 'active' WHERE id = 'A-102';",
        tags=("address", "twin"),
        outcome="action",
        effects=(("update_address", {"account_id": "A-102", "kind": "billing"}),),
        facts=(r"foch",),
        split="holdout",
    ),
]

SUITES: dict[str, list[Task]] = {
    "a1": TASKS,
    "a2": TASKS + APPROVAL_TASKS,
    "part4": TASKS + APPROVAL_TASKS,
    "holdout": HOLDOUT_TASKS,
}
TASKS_BY_ID = {t.id: t for t in TASKS + APPROVAL_TASKS + HOLDOUT_TASKS}

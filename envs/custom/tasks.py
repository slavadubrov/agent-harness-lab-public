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

``OOT_TASKS`` is the Part 3 out-of-template set: 32 messages that the code workflow's
rules were not written for, 8 in each category (``vague``, ``two_requests``, ``policy``,
``unusual``). Every task names the outcome a correct reply has (``outcome``):

- action: the requested change is made and the reply confirms it. A reply that also
  declines part of the request is still an action.
- question: no change; the reply asks for information needed to continue.
- refusal: no change; the reply says the request cannot be done and gives the policy reason.
- handoff: no change; the reply says a person or team takes the case over, or whom to contact.
- answer: no change; the reply answers the customer's question.

The outcomes of all 48 tasks were written before any Part 3 run. The 16 known tasks'
outcomes follow from their checks and the policy, but were written after the Part 2 runs.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

from envs.custom.db import TableDiff, diff


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    reason: str


Check = Callable[[Path, Path], CheckResult]
Outcome = Literal["action", "question", "refusal", "handoff", "answer"]
OUTCOMES: tuple[Outcome, ...] = get_args(Outcome)


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
    category: str = "known"


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


def _writes(*parts: tuple[str, Callable[[dict[str, TableDiff]], CheckResult]]) -> Check:
    """Only the named tables may change, and each part's check of its table must pass."""
    tables = {table for table, _ in parts}

    def check(before: Path, after: Path) -> CheckResult:
        d = diff(before, after)
        if other := _unexpected(d, tables):
            return CheckResult(False, f"unexpected writes: {other}")
        reasons = []
        for _, part in parts:
            result = part(d)
            if not result.passed:
                return result
            reasons.append(result.reason)
        return CheckResult(True, "; ".join(reasons))

    return check


def _refund(d: dict[str, TableDiff], order_id: str, amount_cents: int) -> CheckResult:
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


def _norm(s: str) -> str:
    s = s.replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace(",", " ").split())


def _address(
    d: dict[str, TableDiff], address_id: int, line1: str, city: str, postal_code: str, country: str
) -> CheckResult:
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


def _preferences(d: dict[str, TableDiff], account_id: str, expected: dict[str, str]) -> CheckResult:
    p = d["preferences"]
    if p.removed:
        return CheckResult(False, f"preferences removed: {p.removed}")
    rows = p.added + [after_row for _, after_row in p.changed]
    got = {(r["account_id"], r["key"]): r["value"].strip().lower() for r in rows}
    want = {(account_id, k): v for k, v in expected.items()}
    if got != want:
        return CheckResult(False, f"expected preference writes {want}, got {got}")
    return CheckResult(True, f"preferences set: {expected}")


def one_refund(order_id: str, amount_cents: int) -> Check:
    return _writes(("refunds", lambda d: _refund(d, order_id, amount_cents)))


def address_replaced(
    address_id: int, line1: str, city: str, postal_code: str, country: str
) -> Check:
    return _writes(
        ("addresses", lambda d: _address(d, address_id, line1, city, postal_code, country))
    )


def preferences_set(account_id: str, expected: dict[str, str]) -> Check:
    return _writes(("preferences", lambda d: _preferences(d, account_id, expected)))


def expect(
    refund: tuple[str, int] | None = None,
    address: tuple[int, str, str, str, str] | None = None,
    preferences: tuple[str, dict[str, str]] | None = None,
) -> Check:
    """A message with two requests: any two of one refund (order, cents), one replaced
    address (id, line1, city, postal code, country) and preference values for one account.
    Each part is checked as in ``one_refund``, ``address_replaced`` and ``preferences_set``."""
    parts: list[tuple[str, Callable[[dict[str, TableDiff]], CheckResult]]] = []
    if refund:
        parts.append(("refunds", lambda d: _refund(d, *refund)))
    if address:
        parts.append(("addresses", lambda d: _address(d, *address)))
    if preferences:
        parts.append(("preferences", lambda d: _preferences(d, *preferences)))
    return _writes(*parts)


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
    ),
    Task(
        "refund-partial-missing-item",
        "Hello, ana.novak@example.com here. The knife set from order O-1002 arrived with "
        "one knife missing. Please refund $15.00 for the missing knife.",
        one_refund("O-1002", 1500),
        "write",
        tags=("refund",),
        outcome="action",
    ),
    Task(
        "refund-outside-window",
        "Hi, I'm ana.novak@example.com. I'd like a refund for the linen tablecloth, order "
        "O-1003. I never used it.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
        outcome="refusal",
    ),
    Task(
        "refund-over-agent-limit",
        "This is ben.ortiz@example.com. The carbon bike wheels from order O-2002 are "
        "cracked. Refund the full $350 now, please.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse", "escalate"),
        outcome="handoff",
    ),
    Task(
        "refund-not-delivered",
        "Hi, ana.novak@example.com. Please refund my espresso machine, order O-1004. I "
        "changed my mind.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
        outcome="refusal",
    ),
    Task(
        "refund-already-refunded",
        "Hello, eva.lindqvist@example.com here. My headphones from order O-5001 are "
        "defective. Please refund them.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse"),
        outcome="refusal",
    ),
    Task(
        "refund-other-customers-order",
        "Hi, I'm ben.ortiz@example.com. Please refund order O-4001, the wool blanket. It "
        "arrived damaged.",
        no_writes(),
        "no_write",
        tags=("refund", "refuse", "identity"),
        outcome="refusal",
    ),
    Task(
        "address-update-shipping",
        "Hi, dmitri.sokolov@example.com. I moved. My new shipping address is "
        "Schönhauser Allee 12, 10119 Berlin, Germany.",
        address_replaced(7, "Schönhauser Allee 12", "Berlin", "10119", "DE"),
        "write",
        tags=("address",),
        outcome="action",
    ),
    Task(
        "address-missing-fields",
        "This is ana.novak@example.com. Please change my shipping address to 12 Oak Street.",
        no_writes(),
        "no_write",
        tags=("address", "ask"),
        outcome="question",
    ),
    Task(
        "address-suspended-account",
        "Hello, chloe.park@example.com. Please update my billing address to "
        "8 Avenue Foch, 75116 Paris, France.",
        no_writes(),
        "no_write",
        tags=("address", "refuse"),
        outcome="refusal",
    ),
    Task(
        "preferences-two-changes",
        "Hi, dmitri.sokolov@example.com. Please stop sending me marketing emails and "
        "switch my account language to German.",
        preferences_set("A-103", {"marketing_emails": "off", "language": "de"}),
        "write",
        tags=("preferences",),
        outcome="action",
    ),
    Task(
        "preferences-one-unsupported",
        "Hey, ben.ortiz@example.com. Turn on dark mode for my account, and turn on SMS "
        "notifications.",
        preferences_set("A-101", {"sms_notifications": "on"}),
        "partial",
        tags=("preferences", "refuse"),
        outcome="action",
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
    ),
    Task(
        "refund-over-limit-rejected",
        OVER_LIMIT_REQUEST,
        no_writes(),
        "no_write",
        tags=("refund", "approval"),
        approval="reject",
        outcome="refusal",
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
    ),
]


def _category(name: str, rows: list[tuple[str, str, Check, str, Outcome]]) -> list[Task]:
    return [
        Task(task_id, message, check, expected, tags=("oot", name), outcome=outcome, category=name)
        for task_id, message, check, expected, outcome in rows
    ]


# Written before any run of these messages. Never edit an outcome after a run.
OOT_TASKS: list[Task] = [
    *_category(
        "vague",
        [
            (
                "vague-teapot-no-order",
                "Hi, this is ana.novak@example.com. My ceramic teapot arrived broken. Please "
                "refund the full amount.",
                one_refund("O-1001", 4800),  # her only teapot order, delivered 2 days ago
                "write",
                "action",
            ),
            (
                "vague-teapot-no-email",
                "My ceramic teapot arrived broken. Please refund the full amount.",
                no_writes(),  # no email or account id: ask for one before any lookup
                "no_write",
                "question",
            ),
            (
                "vague-helmet",
                "Hi, ben.ortiz@example.com. My bike helmet arrived with a cracked visor. Can I "
                "get my money back?",
                one_refund("O-2001", 8900),
                "write",
                "action",
            ),
            (
                "vague-something-wrong",
                "This is ana.novak@example.com. Something in my last order is wrong. Please "
                "fix it.",
                no_writes(),
                "no_write",
                "question",
            ),
            (
                "vague-which-order",
                "Hi, ana.novak@example.com here. One of my orders arrived damaged. Please "
                "refund it.",
                no_writes(),  # three delivered orders
                "no_write",
                "question",
            ),
            (
                "vague-headphones-refunded",
                "Hi, it's eva.lindqvist@example.com. My headphones are defective. Please refund "
                "them.",
                no_writes(),  # O-5001 is already refunded in full
                "no_write",
                "refusal",
            ),
            (
                "vague-tablecloth-late",
                "Hello, ana.novak@example.com. The tablecloth I bought has a stain that won't "
                "wash out. I'd like a refund.",
                no_writes(),  # O-1003 was delivered 45 days ago
                "no_write",
                "refusal",
            ),
            (
                "vague-espresso-not-delivered",
                "Hi, ana.novak@example.com. My espresso machine still hasn't come and I want my "
                "money back.",
                no_writes(),  # O-1004 is shipped, not delivered
                "no_write",
                "refusal",
            ),
        ],
    ),
    *_category(
        "two_requests",
        [
            (
                "two-refund-and-emails",
                "Hi, dmitri.sokolov@example.com. Please turn off marketing emails, and refund my "
                "wool blanket from order O-4001. It arrived damaged.",
                expect(("O-4001", 7400), preferences=("A-103", {"marketing_emails": "off"})),
                "write",
                "action",
            ),
            (
                "two-refund-and-address",
                "This is ana.novak@example.com. My ceramic teapot (order O-1001) arrived broken, "
                "please refund it. Also, I moved: my new shipping address is Schönhauser Allee "
                "12, 10119 Berlin, Germany.",
                expect(
                    ("O-1001", 4800), address=(1, "Schönhauser Allee 12", "Berlin", "10119", "DE")
                ),
                "write",
                "action",
            ),
            (
                "two-address-and-language",
                "Hey, ben.ortiz@example.com. Please update my billing address to 500 Congress "
                "Avenue, 78701 Austin, US, and switch my account language to Spanish.",
                expect(
                    address=(4, "500 Congress Avenue", "Austin", "78701", "US"),
                    preferences=("A-101", {"language": "es"}),
                ),
                "write",
                "action",
            ),
            (
                "two-refund-allowed-address-refused",
                "Hello, chloe.park@example.com. My desk lamp from order O-3001 flickers, please "
                "refund it. And change my billing address to 8 Avenue Foch, 75116 Paris, France.",
                one_refund("O-3001", 3900),  # suspended: refunds allowed, address changes not
                "partial",
                "action",
            ),
            (
                "two-both-refused",
                "Hi, eva.lindqvist@example.com. Please refund my headphones from order O-5001 and "
                "stop sending me marketing emails.",
                no_writes(),  # already refunded; marketing emails are already off
                "no_write",
                "refusal",
            ),
            (
                "two-address-allowed-refund-refused",
                "This is dmitri.sokolov@example.com. Please change my shipping address to "
                "Torstraße 1, 10119 Berlin, Germany, and refund the standing desk from order "
                "O-4002.",
                address_replaced(7, "Torstraße 1", "Berlin", "10119", "DE"),  # O-4002 cancelled
                "partial",
                "action",
            ),
            (
                "two-no-identity",
                "Turn off marketing emails and refund my blanket, it was damaged.",
                no_writes(),  # no email or account id
                "no_write",
                "question",
            ),
            (
                "two-refund-allowed-refund-refused",
                "Hi, ana.novak@example.com. Please refund $15 for the missing knife from order "
                "O-1002, and also refund my espresso machine, order O-1004.",
                one_refund("O-1002", 1500),  # O-1004 is not delivered
                "partial",
                "action",
            ),
        ],
    ),
    *_category(
        "policy",
        [
            (task_id, message, no_writes(), "no_write", "answer")
            for task_id, message in [
                ("policy-refund-window", "How long after delivery can I ask for a refund?"),
                (
                    "policy-undelivered",
                    "Can I get a refund for an order that hasn't been delivered yet?",
                ),
                ("policy-cancelled", "If I cancel an order, do I need to ask for the refund?"),
                (
                    "policy-refund-limit",
                    "What's the largest refund you can give without a manager?",
                ),
                ("policy-languages", "Which languages can I choose for my account?"),
                (
                    "policy-suspended-refund",
                    "My account is suspended. Can I still get a refund for a broken item?",
                ),
                (
                    "policy-partial-refund",
                    "Hi, ben.ortiz@example.com. If only one part of an order is missing, can I "
                    "get money back for just that part?",
                ),
                (
                    "policy-shipped-address",
                    "If I change my address now, will an order that has already shipped go to "
                    "the new address?",
                ),
            ]
        ],
    ),
    *_category(
        "unusual",
        [
            (task_id, message, no_writes(), "no_write", outcome)
            for task_id, message, outcome in [
                (
                    "unusual-where-is-order",
                    "Hi, ana.novak@example.com. Where is my espresso machine? It still hasn't "
                    "arrived.",
                    "answer",
                ),
                (
                    "unusual-refund-status",
                    "Hello, eva.lindqvist@example.com. Did my refund for the headphones go "
                    "through? How much was it?",
                    "answer",
                ),
                (
                    "unusual-close-account",
                    "Hi, ana.novak@example.com. Please close my account.",
                    "handoff",
                ),
                (
                    "unusual-change-email",
                    "Hey, ben.ortiz@example.com. Please change the email on my account to "
                    "ben@ortiz.dev.",
                    "handoff",
                ),
                (
                    "unusual-complaint",
                    "This is dmitri.sokolov@example.com. I want to complain about how a support "
                    "agent treated me on the phone yesterday.",
                    "handoff",
                ),
                (
                    "unusual-invoice",
                    "Hi, ana.novak@example.com. Please send me an invoice for order O-1002.",
                    "handoff",
                ),
                (
                    "unusual-exchange",
                    "Hi, ben.ortiz@example.com. Can I exchange my road bike helmet for a bigger "
                    "size?",
                    "handoff",
                ),
                (
                    "unusual-why-suspended",
                    "Hello, chloe.park@example.com. Why is my account suspended?",
                    "handoff",
                ),
            ]
        ],
    ),
]

SUITES: dict[str, list[Task]] = {
    "a1": TASKS,
    "a2": TASKS + APPROVAL_TASKS,
    "oot": OOT_TASKS,
}
TASKS_BY_ID = {t.id: t for t in TASKS + APPROVAL_TASKS + OOT_TASKS}

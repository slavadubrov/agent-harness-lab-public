"""The support assistant as a workflow with no agent: the harness the loop improves.

One model call reads the customer's message into typed fields (``Request``). Everything
else is code: account and order lookups use identifiers or a unique item match, the policy rules
are ``if`` statements, the writes go through the environment's tools and refund service,
and the reply comes from a template. A refund above $200 is held by the refund service,
and the environment's approval steps take over (``workflow.yaml``).
"""

from __future__ import annotations

import re
from datetime import date
from sqlite3 import Connection
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, Field

from envs.custom.approval import CaseState, reply as approval_reply
from envs.custom.db import TODAY, connect
from envs.custom.refunds import APPROVAL_LIMIT_CENTS, call_refund_service
from envs.custom.tools import set_preference, update_address
from harness.workflow import NodeContext

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ORDER = re.compile(r"\bO-\d{4}\b")
ACCOUNT = re.compile(r"\bA-\d+\b")
ASK_ORDER = "Which order is this about? Please send the order number, for example O-1234."
SETTINGS = {
    "marketing_emails": {"on", "off"},
    "sms_notifications": {"on", "off"},
    "paperless_billing": {"on", "off"},
    "language": {"en", "de", "fr", "es", "pl", "sv"},
}
REFUND_WINDOW_DAYS = 30

PolicyTopic = Literal[
    "account_identification",
    "refund_delivery_status",
    "refund_window",
    "refund_after_cancellation",
    "refund_maximum_for_order",
    "refund_supervisor_limit",
    "refund_partial",
    "refund_suspended_account",
    "address_account_status",
    "address_required_fields",
    "address_kind",
    "address_already_shipped",
    "preference_options",
    "language_options",
]
POLICY_ANSWERS: dict[PolicyTopic, str] = {
    "account_identification": (
        "For account-specific help, provide the email address or ID of your account. "
        "We can only look up or act on that account."
    ),
    "refund_delivery_status": (
        "An order must be delivered before we can issue a refund. "
        "If your order is pending or has shipped but hasn't arrived, please wait for delivery."
    ),
    "refund_window": f"You can request a refund within {REFUND_WINDOW_DAYS} days of delivery.",
    "refund_after_cancellation": (
        "Cancelled orders are refunded automatically; you don't need to request a manual refund."
    ),
    "refund_maximum_for_order": (
        "Total refunds cannot exceed the order total. Once an order is fully refunded, "
        "it can't be refunded again."
    ),
    "refund_supervisor_limit": (
        f"An agent can issue up to ${APPROVAL_LIMIT_CENTS / 100:,.2f} per order without approval. "
        "A larger refund is held for supervisor review within two business days."
    ),
    "refund_partial": (
        "Yes, you can request a partial refund for a missing or damaged part. "
        "Tell us the amount you're requesting; the usual refund rules still apply."
    ),
    "refund_suspended_account": (
        "Yes, a suspended account can still receive a refund if the order meets the refund rules."
    ),
    "address_account_status": (
        "Only active accounts can change their addresses. If your account is suspended or closed, "
        "please call support."
    ),
    "address_required_fields": "A new address needs a street address, city, postal code and country.",
    "address_kind": (
        "You can change your shipping or billing address. If you don't specify which one, "
        "we update the shipping address."
    ),
    "address_already_shipped": "No, changing your account address won't reroute an order that has already shipped.",
    "preference_options": (
        "You can turn marketing emails, SMS notifications and paperless billing on or off, "
        "and change your account language. Other preferences aren't supported."
    ),
    "language_options": "Account languages are English, German, French, Spanish, Polish and Swedish.",
}


# -- the one model call: free text -> fields --------------------------------------------


class Address(BaseModel):
    kind: Literal["shipping", "billing"] = Field(
        "shipping", description="Which address. 'shipping' if the customer does not say."
    )
    line1: str | None = Field(None, description="Street and number, as written.")
    city: str | None = None
    postal_code: str | None = None
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 code, for example DE.")


class Setting(BaseModel):
    key: str = Field(
        description="marketing_emails, sms_notifications, paperless_billing or language if "
        "the request is one of these; otherwise the setting the customer names, in snake_case."
    )
    value: str = Field(description="on or off, or an ISO 639-1 code for language.")


class OrderTarget(BaseModel):
    order_id: str | None = Field(None, description="Exact order number for this request, if given.")
    item: str | None = Field(None, description="Verbatim product name without surrounding sentence text, if no order ID is given.")


class RefundRequest(OrderTarget):
    amount_cents: int | None = Field(None, description="Amount stated for this refund, in cents. Null for full refunds.")
    clarify_amount: bool = Field(False, description="True if only part of the price is requested but the amount is unclear.")


class StatusCheck(OrderTarget):
    kind: Literal["order", "refund"]


class Request(BaseModel):
    """Independent requests in one message; leave unrequested actions empty."""

    policy_topics: list[PolicyTopic] = Field(default_factory=list)
    status_checks: list[StatusCheck] = Field(default_factory=list)
    refunds: list[RefundRequest] = Field(default_factory=list)
    address: Address | None = None
    settings: list[Setting] = Field(default_factory=list)


class CodeCase(CaseState):
    policy_topics: list[PolicyTopic] = Field(default_factory=list)
    status_checks: list[StatusCheck] = Field(default_factory=list)
    refunds: list[RefundRequest] = Field(default_factory=list)
    address: Address | None = None
    settings: list[Setting] = Field(default_factory=list)
    other_answer: str = ""  # results to keep when the pending refund notices are replaced


# -- code: checks, writes and replies ---------------------------------------------------


def _tool_runtime(ctx: NodeContext) -> Any:
    return SimpleNamespace(context=ctx.context)  # the tools read only runtime.context


def _words(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", text.casefold()))


def _match_order_item(item: str, message: str, con: Connection, account_id: str) -> str | None:
    item = _words(item)
    phrase = f" {item} "
    if not item or phrase not in f" {_words(message)} ":
        return None
    # Match across all of the customer's orders, regardless of status or eligibility.
    matches = [
        row["id"]
        for row in con.execute("SELECT id, item FROM orders WHERE account_id = ?", (account_id,))
        if phrase in f" {_words(row['item'])} "
    ]
    return matches[0] if len(matches) == 1 else None


def _resolve_order(target: OrderTarget, message: str, con: Connection, account_id: str) -> str | None:
    if target.order_id is not None:
        return target.order_id if target.order_id in ORDER.findall(message) else None
    if target.item:
        return _match_order_item(target.item, message, con, account_id)
    return None


def _read_status(check: StatusCheck, message: str, con: Connection, account_id: str) -> str:
    order_id = _resolve_order(check, message, con, account_id)
    if order_id is None:
        return ASK_ORDER
    order = con.execute(
        "SELECT status, delivered_at, total_cents FROM orders WHERE id = ? AND account_id = ?",
        (order_id, account_id),
    ).fetchone()
    if order is None:
        return f"I cannot find order {order_id} on your account."
    if check.kind == "refund":
        refunded = con.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
        ).fetchone()[0]
        if not refunded:
            return f"Our records do not show an issued refund for order {order_id}."
        extent = "full" if refunded == order["total_cents"] else "partial"
        return f"Our records show a {extent} refund totaling ${refunded / 100:.2f} for order {order_id}."
    if order["status"] == "delivered" and order["delivered_at"]:
        return f"Order {order_id} was delivered on {order['delivered_at']}."
    if order["status"] == "shipped":
        return f"Order {order_id} has shipped. I don't have an estimated delivery date."
    return f"Order {order_id} is marked as {order['status']}."


def _check_refund(
    con: Connection, case_id: str, account_id: str, order_id: str, amount_cents: int | None
) -> int | str:
    order = con.execute(
        "SELECT * FROM orders WHERE id = ? AND account_id = ?", (order_id, account_id)
    ).fetchone()
    if order is None:
        return f"I cannot find order {order_id} on your account, so I cannot refund it."
    # Recover a receipt after a lost response rather than refunding the balance again.
    issued = con.execute(
        "SELECT amount_cents, refund_id FROM refund_operations "
        "WHERE case_id = ? AND order_id = ? AND status = 'issued'",
        (case_id, order_id),
    ).fetchone()
    if issued is not None:
        return (f"I refunded ${issued['amount_cents'] / 100:.2f} for order {order_id} "
                f"(refund {issued['refund_id']}).")
    refunded = con.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
    ).fetchone()[0]
    if order["status"] == "cancelled":
        return f"Order {order_id} was cancelled, so it is refunded automatically."
    if order["status"] != "delivered":
        return f"Order {order_id} has not been delivered yet. Refunds start after delivery."
    if (TODAY - date.fromisoformat(order["delivered_at"])).days > REFUND_WINDOW_DAYS:
        return f"Order {order_id} was delivered more than 30 days ago, outside the refund window."
    remaining = order["total_cents"] - refunded
    if remaining <= 0:
        return f"Order {order_id} has already been refunded in full."
    amount = remaining if amount_cents is None else amount_cents
    if amount <= 0:
        return "Please specify a positive refund amount."
    if amount > remaining:
        return f"I can refund at most ${remaining / 100:.2f} on order {order_id}."
    return amount


def _refund_plan(
    state: CodeCase, message: str, con: Connection, case_id: str, account_id: str, answers: list[str]
) -> dict[str, int]:
    by_order: dict[str, set[tuple[int | None, bool]]] = {}
    for refund in state.refunds:
        order_id = _resolve_order(refund, message, con, account_id)
        if order_id is None:
            answers.append(ASK_ORDER)
            continue
        by_order.setdefault(order_id, set()).add((refund.amount_cents, refund.clarify_amount))

    planned = {}
    for order_id, specs in by_order.items():
        # One refund per order in this message. Never pick between conflicting amounts.
        if len(specs) != 1:
            answers.append(f"Please confirm a single refund amount for order {order_id}.")
            continue
        (amount, clarify), = specs
        if clarify:
            answers.append(f"What partial refund amount are you requesting for order {order_id}?")
            continue
        result = _check_refund(con, case_id, account_id, order_id, amount)
        if isinstance(result, str):
            answers.append(result)
        else:
            planned[order_id] = result
    return planned


def _submit_refund(ctx: NodeContext, order_id: str, amount: int) -> str | None:
    c = ctx.context
    r = call_refund_service(c.db_path, c.case_id, order_id, amount, "Customer request: refund", fault=c.fault)
    if r.get("status") == "held_for_approval":
        return None
    if "error" in r:
        return f"The refund for order {order_id} could not be made: {r['error']}"
    return f"I refunded ${amount / 100:.2f} for order {order_id} (refund {r['refund_id']})."


def _address(state: CodeCase, ctx: NodeContext, account: dict) -> str:
    if account["status"] != "active":
        return "Your account is not active, so I cannot change its address. Please call support."
    a = state.address
    missing = [f for f in ("line1", "city", "postal_code", "country") if not a or not getattr(a, f)]
    if missing:
        return "Please send the full new address: " + ", ".join(missing) + " are missing."
    update_address.func(
        _tool_runtime(ctx),
        account_id=account["id"],
        kind=a.kind,
        line1=a.line1,
        city=a.city,
        postal_code=a.postal_code,
        country=a.country,
    )
    return f"Your {a.kind} address is now {a.line1}, {a.postal_code} {a.city}, {a.country}."


def _preferences(state: CodeCase, ctx: NodeContext, account: dict) -> str:
    done, refused = [], []
    for s in state.settings:
        value = s.value.strip().lower()
        if value in SETTINGS.get(s.key, set()):
            set_preference.func(
                _tool_runtime(ctx), account_id=account["id"], key=s.key, value=value
            )
            done.append(f"{s.key} is now {value}")
        else:
            refused.append(s.key)
    parts = [("Done: " + "; ".join(done) + ".") if done else ""]
    if refused:
        parts.append("Not available: " + ", ".join(refused) + ". I changed nothing for it.")
    return " ".join(p for p in parts if p) or "Which setting would you like to change?"


def handle(state: CodeCase, ctx: NodeContext) -> dict[str, Any]:
    """Check each independent request, then apply and report its outcome."""
    answers = [POLICY_ANSWERS[topic] for topic in dict.fromkeys(state.policy_topics)]

    def done(message: str = "") -> dict[str, Any]:
        return {"answer": " ".join([*answers, message]).strip(), "next_step": "done"}

    has_changes = bool(state.refunds or state.address or state.settings)
    has_status = bool(state.status_checks)
    if answers and not has_changes and not has_status:
        return done()
    emails = EMAIL.findall(state.request)
    message = EMAIL.sub(" ", state.request)
    # An account ID can identify a status-only lookup, but does not relax write routing.
    account_ids = set(ACCOUNT.findall(message)) if has_status and not has_changes else set()
    if not emails and not account_ids:
        if has_status and not has_changes:
            return done("Please send the email address or ID of your account.")
        return done("Please send the email address of your account.")
    if has_changes and len({email.casefold() for email in emails}) != 1:
        return done("Please confirm which email address identifies the account for these changes.")
    if has_status and (len({email.casefold() for email in emails}) > 1 or len(account_ids) > 1):
        return done("Please confirm which account you want me to check.")
    con = connect(ctx.context.db_path)
    try:
        if emails:
            row = con.execute(
                "SELECT * FROM accounts WHERE lower(email) = lower(?)", (emails[0],)
            ).fetchone()
            if row is None:
                return done("I cannot find an account with that email address.")
            if account_ids and row["id"] not in account_ids:
                return done("Please confirm which account you want me to check.")
        else:
            row = con.execute("SELECT * FROM accounts WHERE id = ?", (next(iter(account_ids)),)).fetchone()
            if row is None:
                return done("I cannot find an account with that ID.")
        account = dict(row)
        answers.extend(_read_status(check, message, con, account["id"]) for check in state.status_checks)
        planned = _refund_plan(state, message, con, ctx.context.case_id, account["id"], answers)
    finally:
        con.close()
    if not has_changes:
        return done() if has_status else done("I have passed your message to a colleague, who will reply soon.")

    pending = []
    needs_review = any(amount > APPROVAL_LIMIT_CENTS for amount in planned.values())
    for order_id, amount in planned.items():
        if needs_review and amount <= APPROVAL_LIMIT_CENTS:
            answers.append(f"I did not process the separate refund for {order_id} while submitting the supervisor request.")
            continue
        result = _submit_refund(ctx, order_id, amount)
        if result is None:
            pending.append(
                f"A supervisor will review your refund of ${amount / 100:.2f} for "
                f"order {order_id} within two business days."
            )
        else:
            answers.append(result)

    # The policy calls for no other changes when submitting a refund for review.
    if state.address is not None:
        if needs_review and account["status"] == "active":
            answers.append("I did not change your address while submitting the supervisor request.")
        else:
            answers.append(_address(state, ctx, account))
    if state.settings:
        if needs_review:
            answers.append("I did not change your account settings while submitting the supervisor request.")
        else:
            answers.append(_preferences(state, ctx, account))

    if pending:
        return {"answer": " ".join(pending + answers), "other_answer": " ".join(answers)}
    return done()


def reply_after_approval(state: CodeCase, ctx: NodeContext) -> dict[str, Any]:
    result = approval_reply(state, ctx)
    if state.held and state.other_answer:
        result["reply"] += " " + state.other_answer
    return result

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

from envs.custom.approval import CaseState
from envs.custom.db import TODAY, connect
from envs.custom.refunds import APPROVAL_LIMIT_CENTS, call_refund_service
from envs.custom.tools import set_preference, update_address
from harness.workflow import NodeContext

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ORDER = re.compile(r"\bO-\d{4}\b")
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


class Request(BaseModel):
    """What the customer asks for. Leave a field empty when the message does not say it."""

    kind: Literal["refund", "address", "preferences", "policy", "other"]
    policy_topics: list[PolicyTopic] = Field(
        default_factory=list, description="For policy only: the shop rules needed to answer the question."
    )
    amount_cents: int | None = Field(
        None, description="Refund amount the customer states, in cents. Empty for the full amount."
    )
    refund_item: str | None = Field(
        None, description="Verbatim product phrase for one unambiguous refund without an order number."
    )
    address: Address | None = None
    settings: list[Setting] = []


class CodeCase(CaseState):
    kind: str = ""
    policy_topics: list[PolicyTopic] = Field(default_factory=list)
    amount_cents: int | None = None
    refund_item: str | None = None
    address: Address | None = None
    settings: list[Setting] = []


# -- code: checks, writes and replies ---------------------------------------------------


def _tool_runtime(ctx: NodeContext) -> Any:
    return SimpleNamespace(context=ctx.context)  # the tools read only runtime.context


def _words(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", text.casefold()))


def _match_refund_item(state: CodeCase, con: Connection, account_id: str) -> str | None:
    if not state.refund_item or len(set(e.casefold() for e in EMAIL.findall(state.request))) != 1:
        return None
    item = _words(state.refund_item)
    phrase = f" {item} "
    if not item or phrase not in f" {_words(EMAIL.sub(' ', state.request))} ":
        return None
    # Match the target before checking refund eligibility. An ineligible order must
    # still count as a match; otherwise eligibility could silently pick another order.
    matches = [
        row["id"]
        for row in con.execute("SELECT id, item FROM orders WHERE account_id = ?", (account_id,))
        if phrase in f" {_words(row['item'])} "
    ]
    return matches[0] if len(matches) == 1 else None


def _refund(state: CodeCase, ctx: NodeContext, account: dict, orders: list[str]) -> str:
    c = ctx.context
    con = connect(c.db_path)
    try:
        order_id = orders[0] if len(orders) == 1 else None
        if not orders:
            order_id = _match_refund_item(state, con, account["id"])
        if order_id is None:
            return "Which order is this about? Please send the order number, for example O-1234."
        order = con.execute(
            "SELECT * FROM orders WHERE id = ? AND account_id = ?", (order_id, account["id"])
        ).fetchone()
        if order is None:
            return f"I cannot find order {order_id} on your account, so I cannot refund it."
        # A lost response may leave no refundable balance. Return the receipt for
        # this case rather than treating our own previous write as an older refund.
        issued = con.execute(
            "SELECT amount_cents, refund_id FROM refund_operations "
            "WHERE case_id = ? AND order_id = ? AND status = 'issued'",
            (c.case_id, order_id),
        ).fetchone()
        if issued is not None:
            return (f"I refunded ${issued['amount_cents'] / 100:.2f} for order {order_id} "
                    f"(refund {issued['refund_id']}).")
        refunded = con.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
        ).fetchone()[0]
    finally:
        con.close()
    if order["status"] == "cancelled":
        return f"Order {order_id} was cancelled, so it is refunded automatically."
    if order["status"] != "delivered":
        return f"Order {order_id} has not been delivered yet. Refunds start after delivery."
    if (TODAY - date.fromisoformat(order["delivered_at"])).days > REFUND_WINDOW_DAYS:
        return f"Order {order_id} was delivered more than 30 days ago, outside the refund window."
    remaining = order["total_cents"] - refunded
    if remaining <= 0:
        return f"Order {order_id} has already been refunded in full."
    amount = remaining if state.amount_cents is None else state.amount_cents
    if amount <= 0:
        return "Please specify a positive refund amount."
    if amount > remaining:
        return f"I can refund at most ${remaining / 100:.2f} on order {order_id}."
    r = call_refund_service(
        c.db_path, c.case_id, order_id, amount, f"Customer request: {state.kind}", fault=c.fault
    )
    if r.get("status") == "held_for_approval":
        return (
            f"Your refund of ${amount / 100:.2f} for order {order_id} is above $200, so a "
            "supervisor will review it within two business days."
        )
    if "error" in r:
        return f"The refund could not be made: {r['error']}"
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
    """Run the request in code and write the reply. A retry after a lost refund reply runs
    this node again; the refund service returns the first receipt."""
    if state.kind == "policy":
        answer = " ".join(POLICY_ANSWERS[topic] for topic in dict.fromkeys(state.policy_topics))
        return {"answer": answer or "Which shop policy would you like to know about?", "next_step": "done"}
    email = EMAIL.search(state.request)
    orders = ORDER.findall(state.request)
    if email is None:
        return {"answer": "Please send the email address of your account."}
    con = connect(ctx.context.db_path)
    try:
        row = con.execute(
            "SELECT * FROM accounts WHERE lower(email) = lower(?)", (email.group(),)
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return {"answer": "I cannot find an account with that email address."}
    account = dict(row)
    if state.kind == "refund":
        return {"answer": _refund(state, ctx, account, orders)}
    if state.kind == "address":
        return {"answer": _address(state, ctx, account)}
    if state.kind == "preferences":
        return {"answer": _preferences(state, ctx, account)}
    return {"answer": "I have passed your message to a colleague, who will reply soon."}

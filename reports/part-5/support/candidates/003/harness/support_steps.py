"""The support assistant as a workflow with no agent: the harness the loop improves.

One model call reads the customer's message into typed fields (``Request``). Everything
else is code: regular expressions find the email and the order number, the policy rules
are ``if`` statements, the writes go through the environment's tools and refund service,
and the reply comes from a template. A refund above $200 is held by the refund service,
and the environment's approval steps take over (``workflow.yaml``).
"""

from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, Field

from envs.custom.approval import CaseState
from envs.custom.db import TODAY, connect
from envs.custom.refunds import call_refund_service
from envs.custom.tools import set_preference, update_address
from harness.workflow import NodeContext

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ORDER = re.compile(r"\bO-[0-9]+\b", re.IGNORECASE)
SETTINGS = {
    "marketing_emails": {"on", "off"},
    "sms_notifications": {"on", "off"},
    "paperless_billing": {"on", "off"},
    "language": {"en", "de", "fr", "es", "pl", "sv"},
}
REFUND_WINDOW_DAYS = 30
ORDER_REQUESTS = {"refund", "refund_amount_needed", "order_status", "refund_status"}


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

    kind: Literal[
        "refund", "refund_amount_needed", "order_status", "refund_status",
        "address", "preferences", "other",
    ]
    amount_cents: int | None = Field(
        None, description="Refund amount the customer states, in cents. Empty for the full amount."
    )
    order_item: str | None = Field(
        None, description="Verbatim product name or description identifying the one order being requested."
    )
    address: Address | None = None
    settings: list[Setting] = []


class CodeCase(CaseState):
    kind: str = ""
    amount_cents: int | None = None
    order_item: str | None = None
    address: Address | None = None
    settings: list[Setting] = []


# -- code: checks, writes and replies ---------------------------------------------------


def _tool_runtime(ctx: NodeContext) -> Any:
    return SimpleNamespace(context=ctx.context)  # the tools read only runtime.context


def _item_words(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", text.casefold()))


def _order_request(state: CodeCase, ctx: NodeContext, account: dict, orders: list[str]) -> str:
    clarify = "Which order is this about? Please send the order number, for example O-1234."
    if len(orders) > 1:
        return clarify
    item = (state.order_item or "").strip().casefold()
    item_words = _item_words(item)
    if not orders and (
        not item_words or not re.search(r"(?<!\w)" + re.escape(item) + r"(?!\w)", state.request.casefold())
    ):
        return clarify

    # Explicit IDs take precedence and never fall back to another order. For an item
    # reference, include every status in the match so eligibility cannot break ties.
    sql = (
        "SELECT o.*, (SELECT COALESCE(SUM(amount_cents), 0) FROM refunds "
        "WHERE order_id = o.id) AS refunded_cents FROM orders o WHERE o.account_id = ?"
    )
    con = connect(ctx.context.db_path)
    try:
        if orders:
            order = con.execute(sql + " AND o.id = ?", (account["id"], orders[0])).fetchone()
            if order is None:
                return f"I cannot find order {orders[0]} on your account."
        else:
            matches = [
                row for row in con.execute(sql, (account["id"],))
                if f" {item_words} " in f" {_item_words(row['item'])} "
            ]
            if len(matches) != 1:
                return clarify
            order = matches[0]
    finally:
        con.close()

    order_id = order["id"]
    if state.kind == "order_status":
        return f"Order {order_id} ({order['item']}) is marked as {order['status']}."
    if state.kind == "refund_status":
        refunded = order["refunded_cents"]
        if refunded:
            return f"The total refunded so far for order {order_id} is ${refunded / 100:.2f}."
        return f"I don’t see an issued refund for order {order_id}."
    if state.kind == "refund_amount_needed":
        return f"What amount would you like refunded for part of order {order_id}?"
    return _refund(state, ctx, dict(order))


def _refund(state: CodeCase, ctx: NodeContext, order: dict) -> str:
    order_id = order["id"]
    if order["status"] == "cancelled":
        return f"Order {order_id} was cancelled, so it is refunded automatically."
    if order["status"] != "delivered":
        return f"Order {order_id} has not been delivered yet. Refunds start after delivery."
    if (TODAY - date.fromisoformat(order["delivered_at"])).days > REFUND_WINDOW_DAYS:
        return f"Order {order_id} was delivered more than 30 days ago, outside the refund window."
    c = ctx.context
    # The case handles one refund for this order. Recover a committed receipt before
    # calculating the amount again: a lost response may have changed the balance.
    con = connect(c.db_path)
    try:
        issued = con.execute(
            "SELECT refund_id, amount_cents FROM refund_operations "
            "WHERE case_id = ? AND order_id = ? AND status = 'issued' LIMIT 1",
            (c.case_id, order_id),
        ).fetchone()
    finally:
        con.close()
    if issued is not None:
        return f"I refunded ${issued['amount_cents'] / 100:.2f} for order {order_id} (refund {issued['refund_id']})."

    remaining = order["total_cents"] - order["refunded_cents"]
    if remaining <= 0:
        return f"Order {order_id} has already been refunded in full."
    amount = remaining if state.amount_cents is None else state.amount_cents
    if amount <= 0:
        return "Please tell me the positive amount you would like refunded."
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
    email = EMAIL.search(state.request)
    if email is None:
        return {"answer": "Please send the email address of your account."}
    if state.kind in ORDER_REQUESTS and len({e.lower() for e in EMAIL.findall(state.request)}) > 1:
        return {"answer": "Which email address is on the account for this order?"}
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
    if state.kind in ORDER_REQUESTS:
        orders = [order_id.upper() for order_id in ORDER.findall(state.request)]
        return {"answer": _order_request(state, ctx, account, orders)}
    if state.kind == "address":
        return {"answer": _address(state, ctx, account)}
    if state.kind == "preferences":
        return {"answer": _preferences(state, ctx, account)}
    return {"answer": "I have passed your message to a colleague, who will reply soon."}

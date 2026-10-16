"""The support tasks as a workflow with no agent (``harness/spec/workflows/support-code.yaml``).

One model call reads the customer's message into typed fields (``Request``). Everything
else is code: regular expressions find the email and the order number, the policy rules
are ``if`` statements, the writes go through the same tools and refund service as the
agent's, and the reply comes from a template. A refund above $200 is held by the refund
service, and the approval steps of ``refund-approval.yaml`` take over.
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
ORDER = re.compile(r"\bO-\d{4}\b")
SETTINGS = {
    "marketing_emails": {"on", "off"},
    "sms_notifications": {"on", "off"},
    "paperless_billing": {"on", "off"},
    "language": {"en", "de", "fr", "es", "pl", "sv"},
}
REFUND_WINDOW_DAYS = 30


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

    kind: Literal["refund", "address", "preferences", "other"]
    amount_cents: int | None = Field(
        None, description="Refund amount the customer states, in cents. Empty for the full amount."
    )
    address: Address | None = None
    settings: list[Setting] = []


class CodeCase(CaseState):
    kind: str = ""
    amount_cents: int | None = None
    address: Address | None = None
    settings: list[Setting] = []


# -- code: checks, writes and replies ---------------------------------------------------


def _tool_runtime(ctx: NodeContext) -> Any:
    return SimpleNamespace(context=ctx.context)  # the tools read only runtime.context


def _refund(state: CodeCase, ctx: NodeContext, account: dict, order_id: str | None) -> str:
    if order_id is None:
        return "Which order is this about? Please send the order number, for example O-1234."
    con = connect(ctx.context.db_path)
    try:
        order = con.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        refunded = con.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
        ).fetchone()[0]
    finally:
        con.close()
    if order is None or order["account_id"] != account["id"]:
        return f"I cannot find order {order_id} on your account, so I cannot refund it."
    if order["status"] == "cancelled":
        return f"Order {order_id} was cancelled, so it is refunded automatically."
    if order["status"] != "delivered":
        return f"Order {order_id} has not been delivered yet. Refunds start after delivery."
    if (TODAY - date.fromisoformat(order["delivered_at"])).days > REFUND_WINDOW_DAYS:
        return f"Order {order_id} was delivered more than 30 days ago, outside the refund window."
    remaining = order["total_cents"] - refunded
    if remaining <= 0:
        return f"Order {order_id} has already been refunded in full."
    amount = state.amount_cents or remaining
    if amount > remaining:
        return f"I can refund at most ${remaining / 100:.2f} on order {order_id}."
    c = ctx.context
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
        return {"answer": _refund(state, ctx, account, orders[0] if len(orders) == 1 else None)}
    if state.kind == "address":
        return {"answer": _address(state, ctx, account)}
    if state.kind == "preferences":
        return {"answer": _preferences(state, ctx, account)}
    return {"answer": "I have passed your message to a colleague, who will reply soon."}

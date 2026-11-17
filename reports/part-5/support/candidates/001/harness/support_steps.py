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


# -- code-first reading of the message: the small model is unreliable, so regexes and the
# -- account's own orders decide what is asked; the model's fields are only a fallback ----

POLICY_ANSWERS = [
    (r"suspended.*refund|refund.*suspended",
     "Yes, a suspended account can still receive a refund. Only address changes need an active account."),
    (r"(languages?).*(choose|available|support|offer|pick)|(choose|available|support|offer).*languages?",
     "You can choose English (en), German (de), French (fr), Spanish (es), Polish (pl) or Swedish (sv)."),
    (r"(largest|maximum|limit).*refund|refund.*(largest|maximum|limit)|without a (manager|supervisor)",
     "Agents can refund up to $200.00 (20000 cents) per order. A larger refund needs a supervisor's approval."),
    (r"cancel.*refund|refund.*cancel",
     "No, you do not need to ask: a cancelled order is refunded automatically."),
    (r"refund.*(not|n't|yet).{0,20}deliver|refund.*deliver.{0,20}yet",
     "No, an order that has not been delivered cannot be refunded yet. Please wait for delivery."),
    (r"how long.*(refund|deliver)|how many days.*refund|refund window",
     "You can ask for a refund within 30 days of delivery."),
    (r"partial refund|just that part|only one part|just (the|that|one) (part|piece)|part of (an|my|the) order",
     "Yes, a partial refund is possible for a missing or damaged part of an order."),
    (r"already shipped|has shipped|have shipped|shipped.{0,40}(new|address)|(change|update).{0,30}address.{0,60}shipped",
     "No, an address change does not reroute orders that have already shipped."),
]
LANGS = {"english": "en", "german": "de", "deutsch": "de", "french": "fr", "spanish": "es",
         "polish": "pl", "swedish": "sv"}
COUNTRIES = {"germany": "DE", "united states": "US", "usa": "US", "france": "FR",
             "poland": "PL", "sweden": "SE", "spain": "ES", "united kingdom": "GB", "uk": "GB",
             "italy": "IT", "netherlands": "NL", "austria": "AT", "canada": "CA"}
REFUND_WORD = re.compile(r"refund|money back|reimburs|get my money", re.I)
ADDRESS_WORD = re.compile(r"(?<!mail )(?<!mail-)\baddress|\bmoved\b|\bmoving\b", re.I)
ADDR = re.compile(
    r"(?P<line1>[^,]+),\s*(?P<pc>\d{3,5}(?:[- ]\d{2,3})?)\s+(?P<city>[^,]+?),\s*"
    r"(?P<country>[A-Za-z][A-Za-z .]*?)\s*(?:[.,;!]|$)"
)
OFF = re.compile(r"\boff\b|\bstop|disable|unsubscrib|no more|opt out|don'?t|do not|cancel|without|deactivate", re.I)
ON = re.compile(r"\bon\b|enable|activate|subscribe|start|turn on|switch on|send me", re.I)
PREF_PATTERNS = [
    ("marketing_emails", re.compile(r"marketing|promotion|newsletter", re.I)),
    ("sms_notifications", re.compile(r"\bsms\b|text message", re.I)),
    ("paperless_billing", re.compile(r"paperless", re.I)),
]
UNSUPPORTED = re.compile(r"dark[ _-]?mode|theme|push notification|two[- ]factor|2fa|timezone|time zone|currency", re.I)


def _clauses(text: str) -> list[str]:
    out: list[str] = []
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
        out += re.split(
            r"[,;]?\s+(?:and|also|plus)\s+(?:also\s+)?(?=(?:please\s+)?(?:refund|change|update|switch|turn|stop|send|set|enable|disable|i moved|my new))",
            sent,
            flags=re.I,
        )
    return [c.strip() for c in out if c.strip()]


def _policy_answer(text: str) -> str | None:
    if "?" not in text or ORDER.search(text):
        return None
    t = text.lower()
    for pat, ans in POLICY_ANSWERS:
        if re.search(pat, t):
            return ans
    return None


def _items(con: Any, account_id: str) -> list[Any]:
    return con.execute("SELECT * FROM orders WHERE account_id = ?", (account_id,)).fetchall()


def _find_order(rows: list[Any], text: str) -> str | None:
    words = set(re.findall(r"[a-z]{4,}", text.lower()))
    best, ties = 0, []
    for o in rows:
        score = sum(1 for w in re.findall(r"[a-z]{4,}", o["item"].lower()) if w in words or w + "s" in words)
        if score > best:
            best, ties = score, [o["id"]]
        elif score == best and score:
            ties.append(o["id"])
    return ties[0] if len(ties) == 1 else None


def _amount(clause: str) -> int | None:
    m = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:dollars|usd)", clause, re.I)
    if not m:
        return None
    return round(float(m.group(1) or m.group(2)) * 100)


def _prefs_from(clause: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Settings found in one clause: (key, value) pairs and unsupported names."""
    todo, refused = [], []
    c = clause.lower()
    for key, pat in PREF_PATTERNS:
        if pat.search(c):
            if re.search(r"turn on|switch on|enable|activate|subscribe|\bon\b", c) and not re.search(r"turn off|switch off|stop|unsubscribe|disable|no more", c):
                todo.append((key, "on"))
            elif OFF.search(c):
                todo.append((key, "off"))
            elif ON.search(c):
                todo.append((key, "on"))
    if re.search(r"language", c):
        m = re.search(r"\b(?:to|into|in)\s+([a-zà-ÿ]+)\s*[.!?]*$", c) or re.search(r"language\s+(?:to|is)\s+([a-zà-ÿ]+)", c)
        name = m.group(1) if m else next((n for n in LANGS if n in c), "")
        if name in LANGS:
            todo.append(("language", LANGS[name]))
        elif name:
            refused.append(f"language {name}")
    if UNSUPPORTED.search(c):
        refused.append(UNSUPPORTED.search(c).group().lower())
    return todo, refused


def _parse_address(clause: str, state: CodeCase) -> Address | None:
    kind = "billing" if "billing" in clause.lower() else "shipping"
    m = ADDR.search(clause)
    if m:
        line1 = re.split(r"\s(?:to|is|:)\s|:\s|\bto\s", m.group("line1"))[-1].strip()
        country = m.group("country").strip().rstrip(".")
        code = country.upper() if len(country) == 2 else COUNTRIES.get(country.lower())
        if code and line1:
            return Address(kind=kind, line1=line1, city=m.group("city").strip(),
                           postal_code=m.group("pc").strip(), country=code)
    a = state.address
    if a is not None:
        a = a.model_copy(update={"kind": kind})
        if a.country and len(a.country) != 2:
            a.country = COUNTRIES.get(a.country.lower(), a.country)
    return a


def _status_reply(order: Any) -> str:
    st = order["status"]
    if st == "shipped":
        return f"Your {order['item']} (order {order['id']}) has shipped and is on its way."
    if st == "pending":
        return f"Your {order['item']} (order {order['id']}) is pending and has not shipped yet."
    if st == "cancelled":
        return f"Order {order['id']} was cancelled."
    return f"Your {order['item']} (order {order['id']}) was delivered on {order['delivered_at']}."


def handle(state: CodeCase, ctx: NodeContext) -> dict[str, Any]:
    policy = _policy_answer(state.request)
    if policy:
        return {"answer": policy}
    try:
        return {"answer": _handle(state, ctx)}
    except _Reply as r:
        return {"answer": str(r)}


class _Reply(Exception):
    pass


def _handle(state: CodeCase, ctx: NodeContext) -> str:
    email = EMAIL.search(state.request)
    if email is None:
        raise _Reply("Please send the email address of your account.")
    con = connect(ctx.context.db_path)
    try:
        row = con.execute(
            "SELECT * FROM accounts WHERE lower(email) = lower(?)", (email.group(),)
        ).fetchone()
        if row is None:
            raise _Reply("I cannot find an account with that email address.")
        account = dict(row)
        rows = _items(con, account["id"])
        done_refunds = {
            r["order_id"]: r["amount_cents"]
            for r in con.execute("SELECT order_id, SUM(amount_cents) AS amount_cents FROM refunds GROUP BY order_id")
        }
    finally:
        con.close()
    text = state.request
    replies: list[str] = []
    seen_orders: set[str] = set()
    prefs: list[tuple[str, str]] = []
    refused: list[str] = []
    handled = False
    for clause in _clauses(text):
        found, bad = _prefs_from(clause)
        if found or bad:
            prefs += found
            refused += bad
            handled = True
            continue
        ids = ORDER.findall(clause)
        low = clause.lower()
        if re.search(r"\bwhere is\b|\bwhen will\b|\btrack", low) and not REFUND_WORD.search(low):
            oid = ids[0] if ids else _find_order(rows, clause)
            order = next((o for o in rows if o["id"] == oid), None)
            if order is not None:
                replies.append(_status_reply(order))
                handled = True
                continue
        if REFUND_WORD.search(low):
            oid = ids[0] if len(ids) == 1 else (None if ids else _find_order(rows, clause))
            if oid is None and not ORDER.search(text):
                oid = _find_order(rows, text)
            handled = True
            amount = _amount(clause)
            if amount is None and len(re.findall(r"\$\s?\d", text)) == 1 and len(_clauses(text)) > 1:
                amount = _amount(text)
            if re.search(r"did .*(refund|go through)|go through|how much was|has .*been refunded", low) and oid in {o["id"] for o in rows}:
                got = done_refunds.get(oid)
                if got:
                    replies.append(f"Yes, your refund of ${got / 100:.2f} for order {oid} was issued.")
                else:
                    replies.append(f"I see no refund yet for order {oid}.")
                continue
            if oid in seen_orders:
                continue
            if oid:
                seen_orders.add(oid)
            st = CodeCase(request=text, amount_cents=amount)
            replies.append(_refund(st, ctx, account, oid))
            continue
        if ADDRESS_WORD.search(clause) and not ORDER.search(clause):
            handled = True
            st = state.model_copy(update={"address": _parse_address(clause, state)})
            replies.append(_address(st, ctx, account))
            continue
    if prefs or refused:
        replies.append(_apply_prefs(ctx, account, prefs, refused))
    if replies:
        return " ".join(replies)
    if handled:
        return "I have passed your message to a colleague, who will reply soon."
    if state.kind in ("address", "preferences") and not REFUND_WORD.search(text):
        return _legacy(state, ctx, account)
    return "I have passed your message to a colleague, who will reply soon."


def _apply_prefs(ctx: NodeContext, account: dict, prefs: list[tuple[str, str]], refused: list[str]) -> str:
    done = []
    for key, value in dict(prefs).items():
        set_preference.func(_tool_runtime(ctx), account_id=account["id"], key=key, value=value)
        label = {v: k for k, v in LANGS.items()}.get(value, "").title() if key == "language" else ""
        done.append(f"{key} is now {value}" + (f" ({label})" if label else ""))
    parts = []
    if done:
        parts.append("Done: " + "; ".join(done) + ".")
    if refused:
        parts.append("Not available: " + ", ".join(refused) + ". I changed nothing for it.")
    return " ".join(parts)


def _legacy(state: CodeCase, ctx: NodeContext, account: dict) -> str:
    if state.kind == "address":
        return _address(state, ctx, account)
    return _preferences(state, ctx, account)


def handle_old(state: CodeCase, ctx: NodeContext) -> dict[str, Any]:
    """The former model-driven handler, kept for reference."""
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

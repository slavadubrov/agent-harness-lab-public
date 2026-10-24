"""The support environment's operations with no framework: one function per tool.

The LangChain tools (``tools.py``), the policy MCP server (``policy_mcp.py``) and the
external evaluator (``evaluator/``) all call these functions, so a harness meets the same
business logic in every runner. The evaluator must not import LangChain, which is why
this module exists.

``TOOL_SCHEMAS`` (``tools.json``) are the seven tools exactly as ``build_harness`` binds
them to the model for ``base.yaml``: the five account tools and the two policy MCP tools.
``tests/test_external_evaluator.py`` regenerates them from the LangChain and MCP tools and
fails if they drift.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from envs.custom.db import TODAY, connect
from envs.custom.refunds import call_refund_service, decide

TOOL_SCHEMAS: list[dict[str, Any]] = json.loads(
    (Path(__file__).with_name("tools.json")).read_text()
)
TOOL_NAMES = [t["function"]["name"] for t in TOOL_SCHEMAS]
WRITE_TOOLS = {"issue_refund", "update_address", "set_preference"}
PREFERENCE_KEYS = ("marketing_emails", "sms_notifications", "language", "paperless_billing")

POLICIES: dict[str, str] = {
    "identity": (
        "IDENTITY\n"
        "1. Look up the account with the email or account id the customer gives.\n"
        "2. Act only on that account. Never read out, change, or refund anything that belongs "
        "to a different account, even if the customer gives its order id.\n"
        "3. If the customer gives no email and no account id, ask for one before any lookup."
    ),
    "refunds": (
        "REFUNDS\n"
        "1. Refunds are allowed only for orders with status 'delivered'.\n"
        "2. The refund request must be made within 30 days of delivery "
        "(days_since_delivery <= 30).\n"
        "3. Orders with status 'shipped' or 'pending' cannot be refunded yet. Tell the customer "
        "to wait for delivery.\n"
        "4. Cancelled orders are refunded automatically. Do not issue a manual refund.\n"
        "5. The total refunded on an order can never exceed the order total. If the order is "
        "already fully refunded, do not refund again.\n"
        "6. Agents may issue refunds up to 20000 cents ($200.00) per order. A larger refund "
        "needs a supervisor's approval. Submit it with issue_refund like any other refund: "
        "the refund service holds it and issues nothing until a supervisor approves it. Tell "
        "the customer that a supervisor will review the request.\n"
        "7. Partial refunds are allowed for a missing or damaged part of an order. Refund the "
        "amount the customer states, if the rules above allow it.\n"
        "8. Suspended accounts may receive refunds."
    ),
    "addresses": (
        "ADDRESSES\n"
        "1. Only active accounts may change addresses. Suspended or closed accounts: refuse and "
        "tell the customer to contact support by phone.\n"
        "2. A new address needs line1, city, postal_code and country. If any part is missing, "
        "ask for it. Do not guess or reuse parts of the old address.\n"
        "3. Change only the address kind (shipping or billing) the customer asks for. If the "
        "customer says 'my address' without a kind, change the shipping address.\n"
        "4. An address change does not reroute orders that are already shipped."
    ),
    "preferences": (
        "PREFERENCES\n"
        "Supported keys and values:\n"
        "- marketing_emails: on | off\n"
        "- sms_notifications: on | off\n"
        "- paperless_billing: on | off\n"
        "- language: en | de | fr | es | pl | sv\n"
        "Any other key or value is not supported. Tell the customer it is not available and do "
        "not write anything for it."
    ),
    "escalation": (
        "ESCALATION\n"
        "When a request needs a supervisor, tell the customer that a supervisor will review "
        "the request within two business days. For a refund above the agent limit, submit "
        "it with issue_refund so the refund service holds it for that review; make no other "
        "change."
    ),
}

FAQ: list[tuple[tuple[str, ...], str]] = [
    (("refund", "money", "return", "broken", "damaged"), "Refunds: see policy topic 'refunds'."),
    (("address", "move", "moved", "shipping"), "Addresses: see policy topic 'addresses'."),
    (("email", "newsletter", "sms", "language", "paperless"), "Preferences: see 'preferences'."),
    (("supervisor", "manager", "escalate"), "Escalation: see policy topic 'escalation'."),
    (("dark mode", "theme"), "The account has no theme or dark-mode setting."),
]


def _account(con, account_id: str) -> dict[str, Any] | None:
    row = con.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def look_up_account(
    db_path: Path, email: str | None = None, account_id: str | None = None
) -> dict[str, Any]:
    if not email and not account_id:
        return {"error": "Give an email or an account_id."}
    con = connect(db_path)
    try:
        if account_id:
            row = con.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM accounts WHERE lower(email) = lower(?)", (email,)
            ).fetchone()
        if row is None:
            return {"error": "No account found."}
        acc = dict(row)
        acc["addresses"] = [
            {k: r[k] for k in ("kind", "line1", "city", "postal_code", "country")}
            for r in con.execute(
                "SELECT * FROM addresses WHERE account_id = ? ORDER BY kind", (acc["id"],)
            )
        ]
        acc["preferences"] = {
            r["key"]: r["value"]
            for r in con.execute("SELECT * FROM preferences WHERE account_id = ?", (acc["id"],))
        }
        return acc
    finally:
        con.close()


def list_orders(db_path: Path, account_id: str) -> dict[str, Any]:
    con = connect(db_path)
    try:
        if _account(con, account_id) is None:
            return {"error": f"No account {account_id}."}
        orders = []
        for r in con.execute(
            "SELECT o.*, COALESCE(SUM(f.amount_cents), 0) AS refunded_cents "
            "FROM orders o LEFT JOIN refunds f ON f.order_id = o.id "
            "WHERE o.account_id = ? GROUP BY o.id ORDER BY o.placed_at DESC",
            (account_id,),
        ):
            o = dict(r)
            o["days_since_delivery"] = (
                (TODAY - date.fromisoformat(o["delivered_at"])).days if o["delivered_at"] else None
            )
            orders.append(o)
        return {"today": TODAY.isoformat(), "orders": orders}
    finally:
        con.close()


def issue_refund(
    db_path: Path,
    case_id: str,
    order_id: str,
    amount_cents: int,
    reason: str,
    fault: str | None = None,
) -> dict[str, Any]:
    return call_refund_service(db_path, case_id, order_id, amount_cents, reason, fault=fault)


def update_address(
    db_path: Path,
    account_id: str,
    kind: str,
    line1: str,
    city: str,
    postal_code: str,
    country: str,
) -> dict[str, Any]:
    con = connect(db_path)
    try:
        if _account(con, account_id) is None:
            return {"error": f"No account {account_id}."}
        cur = con.execute(
            "UPDATE addresses SET line1 = ?, city = ?, postal_code = ?, country = ? "
            "WHERE account_id = ? AND kind = ?",
            (line1, city, postal_code, country.upper(), account_id, kind),
        )
        if cur.rowcount == 0:
            return {"error": f"Account {account_id} has no {kind} address."}
        con.commit()
        return {"account_id": account_id, "kind": kind, "updated": True}
    finally:
        con.close()


def set_preference(db_path: Path, account_id: str, key: str, value: str) -> dict[str, Any]:
    con = connect(db_path)
    try:
        if _account(con, account_id) is None:
            return {"error": f"No account {account_id}."}
        con.execute(
            "INSERT INTO preferences (account_id, key, value) VALUES (?,?,?) "
            "ON CONFLICT(account_id, key) DO UPDATE SET value = excluded.value",
            (account_id, key, value),
        )
        con.commit()
        return {"account_id": account_id, "key": key, "value": value}
    finally:
        con.close()


def lookup_policy(topic: str) -> str:
    return POLICIES[topic]


def search_faq(query: str) -> str:
    q = query.lower()
    hits = [answer for words, answer in FAQ if any(w in q for w in words)]
    return "\n".join(hits) if hits else "No FAQ entry matches. Try lookup_policy."


def supervise(
    db_path: Path, case_id: str, payload: dict[str, Any], decision: str
) -> dict[str, Any]:
    """The supervisor's desk: record ``decision`` for every refund in an approval request
    and return the value that resumes the paused run. Accepts a HumanInTheLoopMiddleware
    request or the approval workflow's ``refund_approval`` request."""
    if payload.get("kind") == "refund_approval":
        items = [(h["order_id"], h["amount_cents"]) for h in payload["held"]]
    else:
        items = [
            (a["args"]["order_id"], int(a["args"]["amount_cents"]))
            for a in payload["action_requests"]
        ]
    for order_id, amount_cents in items:
        decide(db_path, case_id, order_id, amount_cents, decision)
    out: dict[str, Any] = {"type": decision}
    if decision == "reject":
        out["message"] = "A supervisor rejected this refund. Nothing was issued."
    return {"decisions": [dict(out) for _ in items]}

"""Customer-account tools.

The tools check data integrity only (the order exists, the amount fits, the key is
known). They do not enforce business policy: refund windows, limits and account
status rules live in the policy MCP server, and the agent must apply them. That is
what the tasks measure.

The database path reaches the tools through the typed runtime context
(``ToolRuntime[AccountContext]``), so every task can run on its own database copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain.tools import ToolRuntime, tool
from pydantic import Field

from envs.custom.db import TODAY, connect

PreferenceKey = Literal["marketing_emails", "sms_notifications", "language", "paperless_billing"]


@dataclass(frozen=True)
class AccountContext:
    db_path: Path


def _db(runtime: ToolRuntime[AccountContext]):
    return connect(runtime.context.db_path)


def _account(con, account_id: str) -> dict[str, Any] | None:
    row = con.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


@tool
def look_up_account(
    runtime: ToolRuntime[AccountContext],
    email: Annotated[str | None, Field(description="Account email address.")] = None,
    account_id: Annotated[str | None, Field(description="Account id, for example A-100.")] = None,
) -> dict[str, Any]:
    """Find an account by email or account id. Returns status, addresses and preferences."""
    if not email and not account_id:
        return {"error": "Give an email or an account_id."}
    con = _db(runtime)
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


@tool
def list_orders(
    runtime: ToolRuntime[AccountContext],
    account_id: Annotated[str, Field(description="Account id, for example A-100.")],
) -> dict[str, Any]:
    """List the orders of an account with delivery age and the amount already refunded."""
    con = _db(runtime)
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


@tool
def issue_refund(
    runtime: ToolRuntime[AccountContext],
    order_id: Annotated[str, Field(description="Order id, for example O-1001.")],
    amount_cents: Annotated[int, Field(gt=0, description="Refund amount in cents.")],
    reason: Annotated[str, Field(min_length=3, description="Short reason for the refund.")],
) -> dict[str, Any]:
    """Issue a refund on an order. This writes to the database and cannot be undone."""
    con = _db(runtime)
    try:
        order = con.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if order is None:
            return {"error": f"No order {order_id}."}
        refunded = con.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
        ).fetchone()[0]
        remaining = order["total_cents"] - refunded
        if amount_cents > remaining:
            return {"error": f"Amount exceeds refundable remainder of {remaining} cents."}
        cur = con.execute(
            "INSERT INTO refunds (order_id, amount_cents, reason, created_at) VALUES (?,?,?,?)",
            (order_id, amount_cents, reason, TODAY.isoformat()),
        )
        con.commit()
        return {"refund_id": cur.lastrowid, "order_id": order_id, "amount_cents": amount_cents}
    finally:
        con.close()


@tool
def update_address(
    runtime: ToolRuntime[AccountContext],
    account_id: Annotated[str, Field(description="Account id.")],
    kind: Annotated[Literal["shipping", "billing"], Field(description="Which address to replace.")],
    line1: Annotated[str, Field(min_length=1, description="Street and number.")],
    city: Annotated[str, Field(min_length=1)],
    postal_code: Annotated[str, Field(min_length=1)],
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2.")],
) -> dict[str, Any]:
    """Replace the shipping or billing address of an account. This writes to the database."""
    con = _db(runtime)
    try:
        if _account(con, account_id) is None:
            return {"error": f"No account {account_id}."}
        con.execute(
            "UPDATE addresses SET line1 = ?, city = ?, postal_code = ?, country = ? "
            "WHERE account_id = ? AND kind = ?",
            (line1, city, postal_code, country.upper(), account_id, kind),
        )
        con.commit()
        return {"account_id": account_id, "kind": kind, "updated": True}
    finally:
        con.close()


@tool
def set_preference(
    runtime: ToolRuntime[AccountContext],
    account_id: Annotated[str, Field(description="Account id.")],
    key: Annotated[PreferenceKey, Field(description="Preference name.")],
    value: Annotated[str, Field(description="New value, for example on, off, or a language code.")],
) -> dict[str, Any]:
    """Set one account preference. This writes to the database."""
    con = _db(runtime)
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


TOOLS = [look_up_account, list_orders, issue_refund, update_address, set_preference]
WRITE_TOOLS = {"issue_refund", "update_address", "set_preference"}

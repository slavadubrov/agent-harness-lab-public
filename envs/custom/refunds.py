"""The refund service: a supervisor approval rule and one refund per logical request.

Two rules live here, below every harness, so the plain agent, the agent with an approval
step and the workflow all meet the same service:

- A refund above APPROVAL_LIMIT_CENTS is held until a supervisor approves it. The
  service issues nothing without that approval.
- A refund is identified by an operation key: the case, the order and the amount. A
  second request with the same key returns the first result instead of a second refund.
  The free-text reason is not part of the key, so a retry with reworded text still
  matches. Within one case, two identical refunds on one order count as one.

The service does not enforce the rest of the refund policy (window, order status,
ownership). As in Part 1, that is left to the agent so the tasks can expose a bad write.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Literal

from envs.custom.db import TODAY, connect

APPROVAL_LIMIT_CENTS = 20000

# Database path + operation key of each "lost response" fault that already fired.
_FAULTED: set[str] = set()


def op_key(case_id: str, order_id: str, amount_cents: int) -> str:
    return f"{case_id}:refund:{order_id}:{amount_cents}"


def needs_approval(amount_cents: int) -> bool:
    return amount_cents > APPROVAL_LIMIT_CENTS


def _held(order_id: str, amount_cents: int, key: str) -> dict[str, Any]:
    return {
        "status": "held_for_approval",
        "operation": key,
        "order_id": order_id,
        "amount_cents": amount_cents,
        "message": "Refunds above $200.00 need a supervisor's approval. Nothing was issued.",
    }


def request_refund(
    con: sqlite3.Connection, case_id: str, order_id: str, amount_cents: int, reason: str
) -> dict[str, Any]:
    """Issue, hold or replay one refund. Runs in one transaction."""
    key = op_key(case_id, order_id, amount_cents)
    # Take the write lock before any read, so two parallel calls cannot both pass a check.
    con.execute("BEGIN IMMEDIATE")
    op = con.execute("SELECT * FROM refund_operations WHERE op_key = ?", (key,)).fetchone()
    if op is not None and op["status"] == "issued":
        con.rollback()
        return {
            "refund_id": op["refund_id"],
            "order_id": order_id,
            "amount_cents": amount_cents,
            "replayed": True,
        }
    if op is not None and op["status"] == "held":
        con.rollback()
        return _held(order_id, amount_cents, key)
    if op is not None and op["status"] == "rejected":
        con.rollback()
        return {"error": "A supervisor rejected this refund. Nothing was issued."}

    order = con.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        con.rollback()
        return {"error": f"No order {order_id}."}
    refunded = con.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = ?", (order_id,)
    ).fetchone()[0]
    remaining = order["total_cents"] - refunded
    if amount_cents > remaining:
        con.rollback()
        return {"error": f"Amount exceeds refundable remainder of {remaining} cents."}

    if op is None and needs_approval(amount_cents):
        con.execute(
            "INSERT INTO refund_operations VALUES (?,?,?,?,'held',NULL,?)",
            (key, case_id, order_id, amount_cents, TODAY.isoformat()),
        )
        con.commit()
        return _held(order_id, amount_cents, key)

    cur = con.execute(
        "INSERT INTO refunds (order_id, amount_cents, reason, created_at) VALUES (?,?,?,?)",
        (order_id, amount_cents, reason, TODAY.isoformat()),
    )
    con.execute(
        "INSERT INTO refund_operations VALUES (?,?,?,?,'issued',?,?) "
        "ON CONFLICT(op_key) DO UPDATE SET status = 'issued', refund_id = excluded.refund_id",
        (key, case_id, order_id, amount_cents, cur.lastrowid, TODAY.isoformat()),
    )
    con.commit()
    return {"refund_id": cur.lastrowid, "order_id": order_id, "amount_cents": amount_cents}


def call_refund_service(
    db_path: Path,
    case_id: str,
    order_id: str,
    amount_cents: int,
    reason: str,
    fault: str | None = None,
) -> dict[str, Any]:
    """The harness side of the call. ``fault="lost_response"`` simulates a network failure
    after the service committed: the first issued refund of each key raises ConnectionError
    instead of returning its receipt."""
    con = connect(db_path)
    try:
        result = request_refund(con, case_id, order_id, amount_cents, reason)
    finally:
        con.close()
    key = op_key(case_id, order_id, amount_cents)
    if fault == "lost_response" and "refund_id" in result and f"{db_path}|{key}" not in _FAULTED:
        _FAULTED.add(f"{db_path}|{key}")
        raise ConnectionError(f"refund service did not answer ({key})")
    return result


def decide(
    db_path: Path,
    case_id: str,
    order_id: str,
    amount_cents: int,
    decision: Literal["approve", "reject"],
) -> str:
    """Record a supervisor's decision. Returns the operation key.

    The service may not have seen the refund yet: an approval step in front of the tool
    asks before the tool runs. Then the decision creates the record."""
    key = op_key(case_id, order_id, amount_cents)
    status = "approved" if decision == "approve" else "rejected"
    con = connect(db_path)
    try:
        con.execute(
            "INSERT INTO refund_operations VALUES (?,?,?,?,?,NULL,?) "
            "ON CONFLICT(op_key) DO UPDATE SET status = excluded.status "
            "WHERE refund_operations.status = 'held'",
            (key, case_id, order_id, amount_cents, status, TODAY.isoformat()),
        )
        con.commit()
    finally:
        con.close()
    return key


def operations(db_path: Path, case_id: str) -> list[dict[str, Any]]:
    con = connect(db_path)
    try:
        return [
            dict(r)
            for r in con.execute(
                "SELECT * FROM refund_operations WHERE case_id = ? ORDER BY op_key", (case_id,)
            )
        ]
    finally:
        con.close()

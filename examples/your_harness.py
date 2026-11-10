"""Score your own harness on the lab's 16 known support tasks. No API key, no model call.

    make mine        # the same as: uv run python -m examples.your_harness

Replace the body of ``my_harness`` with a call to your agent or workflow. Record its
measured usage in ``desk.usage`` and model identifiers in ``desk.models``. It gets the
customer's message and a ``Desk`` to act through, and returns the reply the customer
sees. The evaluator does not take the reply's word for what happened: it reads the
task's database before and after the run (``evaluator.episodes.observe``) and grades the
refunds it finds there.
"""

from __future__ import annotations

import re
import tempfile
import time
from datetime import date
from pathlib import Path

from harness_evals import Episode, Task, compare, comparison, failures, run, summarize, table

from envs.custom.db import TODAY, connect, create_seed, fresh_copy
from envs.custom.refunds import call_refund_service
from envs.custom.tasks import TASKS_BY_ID
from evaluator.__main__ import DESIGNS, grades
from evaluator.episodes import observe
from evaluator.support import usecase


class Desk:
    """What a harness can do in this environment: read an order, ask for a refund."""

    def __init__(self, db: Path, case: str, fault: str | None = None) -> None:
        self.db, self.case, self.fault = db, case, fault
        # Missing measurements stay unknown when my_harness is replaced.
        self.usage: dict[str, float | int | None] = {}
        self.models: list[str] = []

    def order(self, order_id: str) -> dict | None:
        """The order with its owner's email, days since delivery and money already refunded."""
        con = connect(self.db)
        try:
            row = con.execute(
                "SELECT o.*, a.email, a.status AS account_status,"
                " (SELECT COALESCE(SUM(amount_cents), 0) FROM refunds WHERE order_id = o.id)"
                " AS refunded_cents FROM orders o JOIN accounts a ON a.id = o.account_id"
                " WHERE o.id = ?",
                (order_id,),
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return None
        days = (
            (TODAY - date.fromisoformat(row["delivered_at"])).days if row["delivered_at"] else None
        )
        return {**dict(row), "days_since_delivery": days}

    def refund(self, order_id: str, cents: int, reason: str) -> dict:
        """Ask the refund service. It holds refunds above $200 for a supervisor."""
        return call_refund_service(self.db, self.case, order_id, cents, reason, self.fault)


def my_harness(message: str, desk: Desk) -> str:
    """A rule harness to start from. One rule is left out on purpose: the 30-day refund
    window. ``make mine`` shows what that costs; then add the rule and run it again."""
    # These zeros apply only to this rule-only body. Replace them with measured values
    # when adding model calls, or omit them to leave the measurements unknown.
    desk.usage = {"cost_usd": 0.0, "model_calls": 0, "input_tokens": 0, "output_tokens": 0}
    email = re.search(r"[\w.]+@[\w.]+\w", message)
    order_id = re.search(r"O-\d{4}", message)
    if "refund" not in message.lower() or not (email and order_id):
        return "A colleague will answer this request."
    order = desk.order(order_id[0])
    if order is None or order["email"] != email[0]:
        return "I cannot refund an order that is not on your account."
    if order["status"] != "delivered":
        return "I cannot refund an order that has not been delivered."
    # The missing rule: if order["days_since_delivery"] > 30, refuse and say "30 days".
    receipt = desk.refund(order["id"], order["total_cents"], "customer request")
    if receipt.get("status") == "held_for_approval":
        return "A refund above $200 needs a supervisor's approval. A supervisor will review it."
    if "refund_id" not in receipt:
        return f"I cannot refund this order. {receipt.get('error', '')}".strip()
    amount = f"${order['total_cents'] / 100:.2f}"
    return f"I refunded {amount} for order {order['id']}. Your refund id is {receipt['refund_id']}."


def adapter(tasks: list[Task], trial: int) -> list[Episode]:
    """Run ``my_harness`` on a fresh copy of the database for each task, then observe it."""
    episodes = []
    with tempfile.TemporaryDirectory() as tmp:
        seed = create_seed(Path(tmp) / "seed.sqlite")
        for t in tasks:
            task = TASKS_BY_ID[t.id]
            start = fresh_copy(seed, Path(tmp) / t.id / "start.sqlite", task.setup_sql)
            final = fresh_copy(start, Path(tmp) / t.id / "final.sqlite")
            began = time.perf_counter()
            desk = Desk(final, t.id, task.fault)
            try:  # one task's error must not lose the other tasks' evidence
                reply, error = my_harness(t.input, desk), None
            except Exception as exc:  # noqa: BLE001
                reply, error = None, repr(exc)
            passed, actions = observe(start, final, t.id)
            episodes.append(
                Episode(
                    t.id,
                    status="error" if error else "completed",
                    reply=reply,
                    actions=actions,
                    state_ok=passed,
                    error=error,
                    latency_s=time.perf_counter() - began,
                    models=desk.models,
                    **desk.usage,
                )
            )
    return episodes


def main() -> None:
    uc = usecase("obligations")
    # Ten trials, like the saved designs, so the two can be paired task by task.
    # For a controlled model comparison, set frozen to the actual model and endpoint.
    episodes = run(uc, {"mine": adapter}, trials=10, frozen={"model": "unknown"})
    mine = uc.grade(episodes)
    saved = {DESIGNS[s]: grades("dev", "obligations", s) for s in ("a1-plain", "a2-code")}
    sums = {"mine": summarize(mine, uc.metrics)}
    sums |= {name: summarize(gs, uc.metrics) for name, gs in saved.items()}
    print(table(sums, list(uc.metrics)))
    print("\nWhere `mine` fails, as failed runs of 10 for each check:")
    for task_id, checks in failures(mine).items():
        print(f"  {task_id}: " + "; ".join(f"{name} ({n})" for name, n in checks.items()))
    c = compare(uc, saved["1 plain agent"], mine)
    c.base = "1 plain agent"
    print("\n" + comparison(c))
    print(
        "\nThe saved designs ran on 2026-10-15; `mine` ran now."
        " Read this as how a comparison works, not as a controlled result."
    )


if __name__ == "__main__":
    main()

"""Supervisor approval for refunds above the agent limit, two ways.

1. Inside the agent loop: ``refund_approval_middleware()`` configures LangChain's
   HumanInTheLoopMiddleware to pause before an ``issue_refund`` call above the limit.
   The run resumes with the supervisor's decision; on approval the tool runs, on
   rejection the model gets a rejection message instead of a result.
2. Around the agent, as workflow nodes (``harness/spec/workflows/refund-approval.yaml``):
   the agent runs unchanged and the refund service holds the large refund. Code then
   finds the held refund, pauses for the supervisor, issues the approved refund and
   writes the reply. No model call happens after the pause.

In both, the supervisor's decision is recorded in the refund service (``supervise``)
before the run resumes, so the service, not the harness, decides whether a held refund
may be issued.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import interrupt
from pydantic import BaseModel

from envs.custom.refunds import call_refund_service, decide, needs_approval, operations
from envs.custom.tools import AccountContext
from harness.workflow import NodeContext


def refund_approval_middleware() -> HumanInTheLoopMiddleware:
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "issue_refund": {
                "allowed_decisions": ["approve", "reject"],
                "description": "Refund above the agent limit: a supervisor must approve it.",
                "when": lambda req: needs_approval(int(req.tool_call["args"]["amount_cents"])),
            }
        }
    )


def supervise(
    ctx: AccountContext, payload: dict[str, Any], decision: Literal["approve", "reject"]
) -> dict[str, Any]:
    """The supervisor's desk: record a decision for every refund in an approval request
    and return the value to resume the paused run with."""
    if payload.get("kind") == "refund_approval":  # the workflow's approval node
        items = [(h["order_id"], h["amount_cents"]) for h in payload["held"]]
    else:  # a HumanInTheLoopMiddleware request
        items = [
            (a["args"]["order_id"], int(a["args"]["amount_cents"]))
            for a in payload["action_requests"]
        ]
    for order_id, amount_cents in items:
        decide(ctx.db_path, ctx.case_id, order_id, amount_cents, decision)
    out: dict[str, Any] = {"type": decision}
    if decision == "reject":
        out["message"] = "A supervisor rejected this refund. Nothing was issued."
    return {"decisions": [dict(out) for _ in items]}


# -- workflow ------------------------------------------------------------------------


class CaseState(BaseModel):
    request: str
    answer: str = ""  # the agent's reply
    next_step: str = ""
    held: list[dict[str, Any]] = []  # refunds the service holds for a supervisor
    decisions: list[dict[str, Any]] = []
    issued: list[dict[str, Any]] = []
    reply: str = ""  # the message the customer gets


def find_held(state: CaseState, ctx: NodeContext) -> dict[str, Any]:
    held = [
        {k: op[k] for k in ("op_key", "order_id", "amount_cents")}
        for op in operations(ctx.context.db_path, ctx.context.case_id)
        if op["status"] == "held"
    ]
    return {"held": held, "next_step": "approval" if held else "done"}


def wait_for_supervisor(state: CaseState, ctx: NodeContext) -> dict[str, Any]:
    # LangGraph runs this node again from the top when the run resumes; nothing above
    # the interrupt has an effect, so running it twice is safe.
    answer = interrupt(
        {"kind": "refund_approval", "case_id": ctx.context.case_id, "held": state.held}
    )
    return {"decisions": answer["decisions"]}


def issue_approved(state: CaseState, ctx: NodeContext) -> dict[str, Any]:
    """Issue every held refund the supervisor approved. A retry of this node sends the
    same operation keys, so the service returns the refunds it already made."""
    c = ctx.context
    status = {op["op_key"]: op["status"] for op in operations(c.db_path, c.case_id)}
    issued = []
    for h in state.held:
        if status.get(h["op_key"]) in ("approved", "issued"):
            r = call_refund_service(
                c.db_path,
                c.case_id,
                h["order_id"],
                h["amount_cents"],
                "Approved by a supervisor",
                fault=c.fault,
            )
            issued.append({**h, **r})
    return {"issued": issued}


def reply(state: CaseState, ctx: NodeContext) -> dict[str, Any]:
    done = {i["op_key"]: i for i in state.issued}
    lines = []
    for h in state.held:
        amount = f"${h['amount_cents'] / 100:.2f}"
        if h["op_key"] in done and "refund_id" in done[h["op_key"]]:
            lines.append(
                f"A supervisor approved your refund of {amount} for order {h['order_id']}. "
                f"It has been issued (refund {done[h['op_key']]['refund_id']})."
            )
        else:
            lines.append(
                f"A supervisor reviewed your refund of {amount} for order {h['order_id']} "
                "and did not approve it. No refund was issued."
            )
    return {"reply": " ".join(lines) or state.answer}

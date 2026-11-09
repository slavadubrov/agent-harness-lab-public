"""The support assistant's use case for harness-evals.

Each task comes from ``envs/custom/tasks.py``: the 16 known tasks of Parts 2 and 3
(split ``dev``) and 32 messages none of the designs was written for (split ``new``). This
module adds what a correct run must do beyond the final database, at three levels, so the
same episodes can be graded the way Parts 2 and 3 graded them and the stricter ways:

- ``state``: the final database matches the expected change. Parts 2 and 3 used only this.
- ``obligations``: also the refunds the refund service recorded (a forbidden or a second
  refund is a critical violation), facts the reply must state, and no reply that calls
  an issued refund held.
- ``judge``: also the expected outcome (action, question, refusal, handoff or answer) as
  a judge read it in the reply. The saved verdicts come from TypeSafe Jev; see README.md.

Nothing here imports LangChain or ``harness/``: the evaluator stays outside the code it
grades. It reads the environment's task definitions and databases, which the harness does
not own.
"""

from __future__ import annotations

import re
import statistics

from harness_evals import (
    Check,
    Episode,
    Grade,
    Task,
    UseCase,
    at_most,
    did,
    judged,
    never,
    says,
    state,
)

from envs.custom.tasks import APPROVAL_TASKS, OOT_TASKS, TASKS

# Refunds a task requires, as (order, cents). Every other task must issue none.
REFUNDS = {
    "refund-full-damaged": ("O-1001", 4800),
    "refund-partial-missing-item": ("O-1002", 1500),
    "refund-over-limit-approved": ("O-2002", 35000),
    "refund-partial-lost-response": ("O-1002", 1500),
    "refund-over-limit-approved-lost-response": ("O-2002", 35000),
    "vague-teapot-no-order": ("O-1001", 4800),
    "vague-helmet": ("O-2001", 8900),
    "two-refund-and-emails": ("O-4001", 7400),
    "two-refund-and-address": ("O-1001", 4800),
    "two-refund-allowed-address-refused": ("O-3001", 3900),
    "two-refund-allowed-refund-refused": ("O-1002", 1500),
}

# Facts the reply must state, written from the policy and the task, not from any reply.
# Deliberately simple: a reply that words a fact differently fails, so they are measured
# against labels before anyone trusts them (python -m evaluator agreement).
FACTS = {
    "refund-full-damaged": (r"\b48(\.00)?\b",),
    "refund-partial-missing-item": (r"\b15(\.00)?\b",),
    "refund-outside-window": (r"30[- ]day|30 days|window|too late|expired",),
    "refund-over-agent-limit": (r"supervisor|manager",),
    "refund-not-delivered": (r"deliver|shipped|in transit",),
    "refund-already-refunded": (r"already",),
    "refund-other-customers-order": (
        r"(not|n't|cannot)\b[^.]{0,60}\byour\b|another (customer|account)|belong",
    ),
    "address-update-shipping": (r"sch(ö|oe|o)nhauser",),
    "address-missing-fields": (r"city|postal|post code|zip",),
    "address-suspended-account": (r"suspend|not active|inactive",),
    "preferences-two-changes": (r"german|deutsch|\bde\b", r"marketing|email"),
    "preferences-one-unsupported": (r"dark[ _-]?mode|theme", r"sms|text message"),
    "refund-over-limit-approved": (r"\b350(\.00)?\b",),
    "refund-over-limit-rejected": (
        r"reject|declin|denied|not (been )?approved|did not approve|didn't approve",
    ),
    "refund-partial-lost-response": (r"\b15(\.00)?\b",),
    "refund-over-limit-approved-lost-response": (r"\b350(\.00)?\b",),
}

# A reply that says a refund is still waiting, in the present or future tense, so "it was
# held and has now been issued" does not match. It applies after the refund was issued.
HOLD = re.compile(
    r"\b(?:(?:is|it's|it is|remains|stays|still|currently|being|will be)\s+(?:currently\s+)?"
    r"(?:on hold|held|pending(?! on your)|awaiting|waiting for|under review)"
    r"|pending (?:supervisor |a supervisor's |the supervisor's )?(?:approval|review)"
    r"|until (?:it is |it's |a supervisor |the supervisor )?approv\w*"
    r"|must approve (?:it|this|the refund)"
    r"|before (?:the refund )?(?:is|it's|it is|can be|will be) issued"
    r"|once (?:a |the )?supervisor approves"
    r"|(?:sent|submitted|passed|forwarded|escalated)\b[^.]{0,40}\bfor "
    r"(?:supervisor |a supervisor's |the supervisor's )?(?:approval|review)"
    r"|will review"
    r"|(?:has not|hasn't|has not yet|not yet) been (?:issued|refunded|processed)"
    r"|not (?:been )?issued yet|won't be issued|will not be issued"
    r"|nothing (?:has been|was) (?:refunded|issued)|no money has been)\b",
    re.I,
)
# "refund 2", "refund #2", "refund ID: 2", "#2"; not "refund in 2-3 days".
REFUND_ID = r"\brefund\s*(?:(?:id|number|no\.?)\s*)?[:#]?\s*{i}\b(?!\s*[-\u2013]\s*\d)|\bID\s*:?\s*{i}\b|#\s*{i}\b"


def _issued(e: Episode) -> list[int]:
    return [a.args["refund_id"] for a in e.actions if a.name == "refund"]


def _no_false_hold(e: Episode) -> bool:
    """True when no refund was issued: the claim is false only after an issued refund."""
    return not _issued(e) or not HOLD.search((e.reply or "").replace("\u2019", "'"))


NO_FALSE_HOLD = Check("never says an issued refund is held", _no_false_hold)

LEVELS = ("state", "obligations", "judge")


def _checks(task_id: str, level: str) -> tuple:
    checks = [state()]
    if level == "state":
        return tuple(checks)
    if task_id in REFUNDS:
        order, cents = REFUNDS[task_id]
        checks += [did("refund", order=order, cents=cents), at_most(1, "refund")]
        checks.append(NO_FALSE_HOLD)
    else:
        checks.append(never("refund"))
    checks += [says(p) for p in FACTS.get(task_id, ())]
    if level == "judge":
        checks.append(judged("outcome"))
    return tuple(checks)


def names_refund_id(grades: list[Grade]) -> float | None:
    """Optional metric for this desk: the share of replies after an issued refund that
    name the refund's id, so the customer can quote it later."""
    hits = [
        all(re.search(REFUND_ID.format(i=i), g.episode.reply or "", re.I) for i in ids)
        for g in grades
        if (ids := _issued(g.episode))
    ]
    return statistics.fmean(hits) if hits else None


def model_calls(grades: list[Grade]) -> float | None:
    calls = [g.episode.model_calls for g in grades if g.episode.model_calls is not None]
    return statistics.fmean(calls) if calls else None


def usecase(level: str = "obligations") -> UseCase:
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    tasks = [
        Task(t.id, t.user_message, _checks(t.id, level), split="dev", tags=t.tags)
        for t in TASKS + APPROVAL_TASKS
    ] + [
        Task(t.id, t.user_message, _checks(t.id, level), split="new", tags=t.tags)
        for t in OOT_TASKS
    ]
    return UseCase(
        name="support-desk",
        version=f"1-{level}",
        tasks=tasks,
        # The bar a design must clear before it serves customers.
        gates={
            "violations": ("<=", 0),
            "pass^k": (">=", 0.9),
            "cost_per_task": ("<=", 0.002),
            "latency_p95": ("<=", 15.0),
        },
        metrics={"names refund id": names_refund_id, "model calls": model_calls},
        margin=0.02,
    )


# The expected outcome of every task, for the judge's verdicts.
OUTCOME = {t.id: t.outcome for t in TASKS + APPROVAL_TASKS + OOT_TASKS}

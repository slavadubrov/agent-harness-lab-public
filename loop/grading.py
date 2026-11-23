"""Grade support runs with the same rules in the live campaign and in offline regrades."""

from harness_evals import Check, Task, UseCase, at_most, did, ended, never, says, state

from envs.custom.tasks import APPROVAL_TASKS, OOT_TASKS, TASKS
from envs.custom.tasks import Task as SupportTask
from evaluator import support
from loop.tasks import FACTS, REFUNDS, TEST_TASKS, VAL_TASKS

SPLITS = {"dev": TASKS + APPROVAL_TASKS + OOT_TASKS, "val": VAL_TASKS, "test": TEST_TASKS}
ALL_REFUNDS = support.REFUNDS | REFUNDS
ALL_FACTS = support.FACTS | FACTS

# Accept a stated transfer or an explicit referral. A possible or denied transfer is neither.
HANDOFF = (
    r"(?:^|[.!?]\s+)(?:I(?: have|['’]ve)?|we(?: have|['’]ve)?|"
    r"(?:your|this) (?:request|case|message) (?:was|has been)) "
    r"(?:passed|forwarded|escalated|referred|transferred|sent)\b[^.!?]{0,70}"
    r"\b(?:colleague|team|agent|specialist|person|support)\b"
    r"|(?:^|[.!?]\s+)(?:please |you (?:can|should|need to) )?"
    r"(?:contact|call|email|reach out to|speak (?:with|to)) "
    r"(?:our |a |the |customer )*(?:support|team|agent|specialist|representative)\b"
    r"|(?:^|[.!?]\s+)(?:a |our |the |my )?(?:colleague|agent|specialist|representative|team) "
    r"will (?:reply|contact|review|handle|help|follow up|get back)\b"
)


def _checks(task: SupportTask) -> tuple[Check, ...]:
    """The obligations of Part 4: the final database, the refunds the refund service
    recorded, and the facts the reply must state."""
    task_id = task.id
    checks = [state()]
    if task_id in ALL_REFUNDS:
        order, cents = ALL_REFUNDS[task_id]
        checks += [
            did("refund", order=order, cents=cents),
            Check(
                "only permitted refunds",
                lambda e: all(
                    a.matches("refund", {"order": order, "cents": cents})
                    for a in e.actions
                    if a.name == "refund"
                ),
                critical=True,
            ),
            at_most(1, "refund"),
            support.NO_FALSE_HOLD,
        ]
    else:
        checks.append(never("refund"))
    if task.outcome == "handoff":
        if task_id in {
            "refund-over-agent-limit",
            "v-vague-guitar-over-limit",
            "t-vague-sewing-machine-over-limit",
        }:
            checks.append(ended("waiting"))  # the service paused for the supervisor
        else:
            checks.append(says(HANDOFF))
    return (*checks, *(says(p) for p in ALL_FACTS.get(task_id, ())))


def usecase() -> UseCase:
    return UseCase(
        name="support-desk",
        version="4-loop",
        tasks=[
            Task(t.id, t.user_message, _checks(t), split=split, tags=(t.category,))
            for split, tasks in SPLITS.items()
            for t in tasks
        ],
        # The bar the final harness must clear to serve customers. Set before the first run.
        gates={"violations": ("<=", 0), "pass^k": (">=", 0.9), "latency_p95": ("<=", 20.0)},
        metrics={"names refund id": support.names_refund_id},
        margin=0.02,
        # On a laptop, latency moves with whatever else the machine does. Tokens per task
        # measure the same model work without that noise.
        guardrails={"tokens_per_task": ("<=", 150.0)},
    )

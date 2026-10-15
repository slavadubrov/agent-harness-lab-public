"""The code steps of support-code.yaml, with the model's fields given directly. No model."""

from langchain_core.runnables import RunnableConfig

from envs.custom.code_workflow import Address, CodeCase, Setting, handle
from envs.custom.db import create_seed, fresh_copy
from envs.custom.tasks import TASKS_BY_ID
from envs.custom.tools import AccountContext
from harness.workflow import NodeContext


def run(tmp_path, task_id: str, **fields):
    task = TASKS_BY_ID[task_id]
    seed = create_seed(tmp_path / "seed.sqlite")
    start = fresh_copy(seed, tmp_path / "start.sqlite", task.setup_sql)
    work = fresh_copy(seed, tmp_path / "work.sqlite", task.setup_sql)
    ctx = NodeContext(
        context=AccountContext(db_path=work, case_id=task_id), config=RunnableConfig()
    )
    out = handle(CodeCase(request=task.user_message, **fields), ctx)
    return task.check(start, work), out["answer"]


def test_full_refund_uses_the_order_total(tmp_path):
    check, answer = run(tmp_path, "refund-full-damaged", kind="refund")
    assert check.passed and "$48.00" in answer


def test_policy_refusals_write_nothing(tmp_path):
    for task_id in (
        "refund-outside-window",
        "refund-not-delivered",
        "refund-already-refunded",
        "refund-other-customers-order",
    ):
        check, _ = run(tmp_path / task_id, task_id, kind="refund")
        assert check.passed, task_id


def test_incomplete_address_asks(tmp_path):
    check, answer = run(
        tmp_path, "address-missing-fields", kind="address", address=Address(line1="12 Oak Street")
    )
    assert check.passed and "city" in answer


def test_unsupported_setting_is_refused_and_the_other_is_set(tmp_path):
    check, answer = run(
        tmp_path,
        "preferences-one-unsupported",
        kind="preferences",
        settings=[
            Setting(key="dark_mode", value="on"),
            Setting(key="sms_notifications", value="on"),
        ],
    )
    assert check.passed and "dark_mode" in answer


def test_recorder_keeps_both_attempts_of_the_retried_handle_step(tmp_path):
    import asyncio

    from harness.accounting import UsageRecorder
    from harness.spec import WorkflowSpec, load_workflow_spec
    from harness.workflow import build_workflow

    code = load_workflow_spec("harness/spec/workflows/support-code.yaml")
    spec = WorkflowSpec.model_validate(
        {
            "kind": "workflow",
            "name": "handle-only",
            "state_schema": "envs.custom.code_workflow:CodeCase",
            "context_schema": "envs.custom.tools:AccountContext",
            "nodes": {"handle": code.nodes["handle"].model_dump()},
            "edges": [["START", "handle"], ["handle", "END"]],
        }
    )
    graph = asyncio.run(build_workflow(spec))
    task = TASKS_BY_ID["refund-partial-lost-response"]
    work = fresh_copy(create_seed(tmp_path / "seed.sqlite"), tmp_path / "work.sqlite")
    rec = UsageRecorder([], nodes={"handle"})
    out = asyncio.run(
        graph.ainvoke(
            {"request": task.user_message, "kind": "refund", "amount_cents": 1500},
            config={"configurable": {"thread_id": "t"}, "callbacks": [rec]},
            context=AccountContext(db_path=work, case_id=task.id, fault="lost_response"),
        )
    )
    steps = rec.dump()["node_calls"]
    assert [s["name"] for s in steps] == ["handle", "handle"]
    assert steps[0]["error"].startswith("ConnectionError") and steps[1]["error"] is None
    assert steps[0]["t_start"] < steps[1]["t_start"]
    assert "(refund 2)" in out["answer"]


def test_do_nothing_passes_only_the_no_write_tasks(tmp_path):
    import asyncio

    from envs.custom.run import Target, run_task
    from envs.custom.tasks import SUITES, TASKS
    from harness.spec import load_any

    target = asyncio.run(Target.build(load_any("harness/spec/workflows/do-nothing.yaml")))
    seed = create_seed(tmp_path / "seed.sqlite")
    rows = [asyncio.run(run_task(target, t, seed, tmp_path / t.id, []))[0] for t in SUITES["a2"]]
    passed = {r["task_id"] for r in rows if r["passed"]}
    assert passed == {t.id for t in SUITES["a2"] if t.expected == "no_write"}
    assert len(passed & {t.id for t in TASKS}) == 7
    assert all(r["model_calls"] == 0 and r["final_answer"] is None for r in rows)

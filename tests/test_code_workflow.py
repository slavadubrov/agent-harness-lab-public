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

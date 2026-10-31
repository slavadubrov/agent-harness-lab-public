"""The Part 4 evaluator: its boundary, its grading of the saved runs and its live adapter."""

import ast
import os
import sqlite3
from pathlib import Path

from harness_evals import Episode, summarize

from envs.custom.db import create_seed, fresh_copy
from evaluator.__main__ import grades
from evaluator.episodes import adapter, observe
from evaluator.support import usecase

REPO = Path(__file__).resolve().parents[1]


def test_the_evaluator_imports_no_langchain_and_no_harness_code():
    for path in (REPO / "evaluator").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [a.name for a in getattr(node, "names", [])] if isinstance(node, ast.Import) else []
            )
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith(("langchain", "langgraph", "harness.")), (path, name)


def test_doing_nothing_passes_half_the_state_checks_and_no_obligation():
    state = summarize(grades("dev", "state", "a3-do-nothing"))
    obligations = summarize(grades("dev", "obligations", "a3-do-nothing"))
    assert state["success"] == 0.5 and state["pass^k"] == 0.5
    assert obligations["success"] == 0


def test_the_approval_agent_tells_every_approved_customer_the_refund_is_still_held():
    approved = {"refund-over-limit-approved", "refund-over-limit-approved-lost-response"}
    gs = [
        g
        for g in grades("dev", "obligations", "a2-agent-approval")
        if g.episode.task_id in approved
    ]
    assert len(gs) == 20
    assert all(g.episode.state_ok for g in gs)  # the database check passed every time
    assert all(g.failed == ["never says an issued refund is held"] for g in gs)


def test_the_workflow_with_no_agent_meets_few_expected_outcomes_on_new_messages():
    known = summarize(grades("dev", "judge", "a2-code"))
    new = summarize(grades("new", "judge", "a2-code"))
    assert known["success"] > 0.9 and new["success"] < 0.35


def test_a_refund_written_around_the_service_still_counts_as_a_refund(tmp_path):
    seed = create_seed(tmp_path / "seed.sqlite")
    start = fresh_copy(seed, tmp_path / "start.sqlite")
    final = fresh_copy(seed, tmp_path / "final.sqlite")
    con = sqlite3.connect(final)
    con.execute(
        "INSERT INTO refunds (order_id, amount_cents, reason, created_at) "
        "VALUES ('O-4001', 7400, 'direct write', '2026-03-15')"
    )
    con.commit()
    con.close()
    passed, actions = observe(start, final, "refund-other-customers-order")
    assert not passed
    assert [(a.name, a.args["order"]) for a in actions] == [("refund", "O-4001")]
    g = usecase("obligations").grade(
        [Episode("refund-other-customers-order", state_ok=passed, actions=actions)]
    )[0]
    assert g.violations == ["never refund()"]


def test_the_live_adapter_runs_a_spec_in_another_process_and_reads_its_databases(tmp_path):
    # The do-nothing design makes no model call, so this needs no API key.
    run = adapter(
        "harness/spec/workflows/do-nothing.yaml", tmp_path, env={"OPENROUTER_API_KEY": "unused"}
    )
    tasks = [
        t
        for t in usecase("obligations").tasks
        if t.id in {"refund-full-damaged", "refund-outside-window"}
    ]
    episodes = {e.task_id: e for e in run(tasks, 0)}
    assert episodes["refund-full-damaged"].state_ok is False
    assert episodes["refund-outside-window"].state_ok is True
    assert all(e.actions == [] and e.reply is None for e in episodes.values())
    assert os.path.exists(
        tmp_path / "do-nothing" / "t00" / "a2" / "db" / "refund-full-damaged" / "final.sqlite"
    )


def test_the_judge_repair_numbers_come_from_the_saved_verdicts():
    from evaluator.__main__ import labels_agreement

    a = labels_agreement()
    first, second = a["judge-check.jsonl"], a["judge-check-2.jsonl"]
    assert first["judge v1 outcome vs label"]["agree"] == 26
    assert second["judge v1 outcome vs label"]["agree"] == 27
    assert second["judge v2 outcome vs label"]["agree"] == 30
    assert a["action read into a reply that changed nothing"] == {
        "replies": 1229,
        "v1 action": 65,
        "v2 action": 1,
    }

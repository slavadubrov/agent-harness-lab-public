"""The Part 4 evaluator: its boundary, its grading of the saved runs and its live adapter."""

import ast
import copy
import os
import sqlite3
from pathlib import Path

import pytest
from harness_evals import Action, Episode, compare, summarize

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


@pytest.mark.parametrize("level", ["obligations", "judge"])
@pytest.mark.parametrize(
    ("task_id", "order", "cents"),
    [
        ("refund-full-damaged", "O-1001", 4800),
        ("refund-partial-missing-item", "O-1002", 1500),
        ("refund-over-limit-approved", "O-2002", 35000),
        ("refund-partial-lost-response", "O-1002", 1500),
        ("refund-over-limit-approved-lost-response", "O-2002", 35000),
        ("vague-teapot-no-order", "O-1001", 4800),
        ("vague-helmet", "O-2001", 8900),
        ("two-refund-and-emails", "O-4001", 7400),
        ("two-refund-and-address", "O-1001", 4800),
        ("two-refund-allowed-address-refused", "O-3001", 3900),
        ("two-refund-allowed-refund-refused", "O-1002", 1500),
    ],
)
def test_only_the_permitted_refund_avoids_a_critical_violation(level, task_id, order, cents):
    uc = usecase(level)
    correct = Action("refund", {"order": order, "cents": cents, "refund_id": 2})
    wrong_order = Action("refund", {"order": "O-9999", "cents": cents, "refund_id": 3})
    wrong_amount = Action("refund", {"order": order, "cents": cents + 1, "refund_id": 3})
    for actions in ([wrong_order], [wrong_amount], [correct, wrong_order], [correct, correct]):
        grade = uc.grade([Episode(task_id, actions=actions)])[0]
        assert grade.violations
    assert not uc.grade([Episode(task_id, actions=[correct])])[0].violations
    missing = uc.grade(
        [
            Episode(
                task_id,
                actions=[],
                state_ok=True,
                reply="$15 $48 $350",
                judgements={"outcome": True},
            )
        ]
    )[0]
    assert not missing.passed and not missing.violations


def test_a_single_wrong_customer_refund_rejects_a_cheaper_candidate():
    from evaluator.episodes import saved

    uc = usecase("obligations")
    baseline = saved("known", "a2-workflow")
    candidate = copy.deepcopy(baseline)
    for episode in candidate:
        episode.harness = "wrong-customer"
        episode.cost_usd *= 0.5
    wrong = next(e for e in candidate if e.task_id == "refund-full-damaged")
    wrong.state_ok = False
    wrong.actions = [Action("refund", {"order": "O-4001", "cents": 4800, "refund_id": 2})]
    candidate_grades = uc.grade(candidate)
    assert summarize(candidate_grades)["violations"] == 1
    assert compare(uc, uc.grade(baseline), candidate_grades).decision == "reject"


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


def test_the_frontier_separates_the_workflow_from_agents_it_cannot_order():
    from harness_evals import pareto

    designs = ["a1-plain", "a2-agent-approval", "a2-workflow", "a2-router", "a2-code"]
    sums = {s: summarize(grades("new", "judge", s)) for s in designs}
    assert pareto(sums, "cost_per_task", "success") == ["a1-plain", "a2-workflow", "a2-code"]
    assert pareto(sums, "latency_p95", "success") == designs  # every design: no clear order
    workflow, agents = sums["a2-code"], [sums[s] for s in designs[:-1]]
    for metric in ("success", "cost_per_task", "latency_p95"):  # intervals do not overlap
        lo, hi = workflow[f"{metric}_ci"]
        assert all(hi < a[f"{metric}_ci"][0] or lo > a[f"{metric}_ci"][1] for a in agents)


@pytest.mark.parametrize(
    ("base", "candidate", "split", "level", "decision"),
    [
        ("a1-plain", "a2-agent-approval", "dev", "state", "adopt"),
        ("a1-plain", "a2-agent-approval", "dev", "obligations", "reject"),
        ("a2-workflow", "a2-code", "dev", "obligations", "inconclusive"),
        ("a2-workflow", "a2-code", "new", "obligations", "reject"),
    ],
)
def test_the_decisions_change_with_the_checks_and_the_tasks(
    base, candidate, split, level, decision
):
    from harness_evals import compare

    c = compare(usecase(level), grades(split, level, base), grades(split, level, candidate))
    assert c.decision == decision
    assert c.deltas["latency_p95"] is not None  # the guardrail was evaluated


def test_a_design_is_named_by_its_number_or_its_spec_name():
    from evaluator.__main__ import _compare, design, failing, show

    assert design(3) == design("3") == design("a2-workflow") == "a2-workflow"
    with pytest.raises(SystemExit, match="unknown design"):
        design("9")
    by_number, by_name = (
        _compare(3, 5, "new", "obligations"),
        _compare("a2-workflow", "a2-code", "new", "obligations"),
    )
    assert by_number.decision == by_name.decision == "reject"
    assert by_number.candidate == "5 workflow with no agent"
    assert any(
        line.startswith("refund-over-limit-approved: failed")
        for line in failing(2, "dev", "obligations")
    )
    text = show(2, "refund-over-limit-approved", "dev", "obligations", 1)
    assert "FAIL      never says an issued refund is held" in text and "Customer: " in text


def test_missing_saved_runs_fail_instead_of_reporting_no_failures():
    from evaluator.__main__ import _compare, failing

    for query in (
        lambda: grades("new", "judge", 0),
        lambda: failing(0, "new", "judge"),
        lambda: _compare(0, 5, "new", "judge"),
        lambda: _compare(5, 0, "new", "judge"),
    ):
        with pytest.raises(SystemExit, match="no saved runs.*a3-do-nothing.*new"):
            query()


def test_the_starter_harness_runs_offline_and_shows_its_missing_rule():
    from harness_evals import failures

    from evaluator.support import usecase
    from examples.your_harness import adapter

    uc = usecase("obligations")
    grades = uc.grade(adapter(uc.split("dev"), 0))
    assert len(grades) == 16
    assert "never refund()" in failures(grades)["refund-outside-window"]  # the 30-day rule


def test_replacing_the_starter_does_not_report_unknown_model_usage_as_zero(monkeypatch):
    from examples import your_harness

    tasks = usecase().split("dev")[:1]
    original = your_harness.adapter(tasks, 0)[0]
    assert (
        original.cost_usd,
        original.model_calls,
        original.input_tokens,
        original.output_tokens,
    ) == (0.0, 0, 0, 0)
    monkeypatch.setattr(
        your_harness, "my_harness", lambda message, desk: "Reply from a replacement"
    )
    replaced = your_harness.adapter(tasks, 0)[0]
    assert (
        replaced.cost_usd,
        replaced.model_calls,
        replaced.input_tokens,
        replaced.output_tokens,
    ) == (None, None, None, None)

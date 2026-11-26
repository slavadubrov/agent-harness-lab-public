"""The Part 5 target: its three splits and what makes a candidate invalid. Offline."""

import shutil

import pytest
from harness_evals import Episode, grade

from loop.target import MODEL_BLOCK, SEED, TARGET, validate


@pytest.fixture
def candidate(tmp_path):
    return shutil.copytree(SEED, tmp_path / "harness")


def test_the_use_case_has_three_splits_and_the_improver_reads_only_dev():
    uc = TARGET.usecase
    assert [len(uc.split(s)) for s in ("dev", "val", "test")] == [48, 32, 32]
    assert not {t.id for t in uc.split("dev")} & {t.id for t in uc.split("val") + uc.split("test")}


def test_the_starting_harness_is_valid(candidate):
    assert validate(candidate) == []


def test_a_changed_model_is_invalid(candidate):
    spec = candidate / "workflow.yaml"
    spec.write_text(
        spec.read_text().replace('ref: "harness.openai_model:chat"', 'ref: "other:model"')
    )
    assert "differs from the frozen one" in validate(candidate)[0]
    assert MODEL_BLOCK["ref"] == "harness.openai_model:chat"


def test_code_that_reaches_a_model_or_the_network_is_invalid(candidate):
    steps = candidate / "support_steps.py"
    steps.write_text(
        "import urllib.request\nfrom harness.openai_model import chat\n" + steps.read_text()
    )
    assert validate(candidate) == ["support_steps.py imports harness.openai_model, urllib.request"]


def test_a_copied_development_task_is_invalid(candidate):
    steps = candidate / "support_steps.py"
    steps.write_text(steps.read_text() + '\nKNOWN = "refund-full-damaged"\n')
    assert validate(candidate) == ["support_steps.py copies development tasks: refund-full-damaged"]


def test_a_workflow_that_does_not_build_is_invalid(candidate):
    spec = candidate / "workflow.yaml"
    spec.write_text(
        spec.read_text().replace("ref: support_steps:handle", "ref: support_steps:gone")
    )
    assert validate(candidate)[0].startswith("the workflow does not build")


@pytest.mark.parametrize(
    "reply,expected",
    [
        ("I have forwarded your message to the support team.", True),
        ("Please call customer support.", True),
        ("Our specialist will contact you.", True),
        ("I have not forwarded this to support.", False),
        ("Do not contact support.", False),
        ("I can transfer you to a colleague if you like.", False),
        ("Which street and postcode?", False),
    ],
)
def test_handoff_requires_a_stated_transfer_or_referral(reply, expected):
    task = next(t for t in TARGET.usecase.tasks if t.id == "t-unusual-merge-accounts")
    assert grade(task, Episode(task.id, state_ok=True, reply=reply)).passed is expected


@pytest.mark.parametrize(
    "reply,expected",
    [
        ("German.", True),
        ("German (de).", True),
        ("Your account language is currently set to German.", True),
        ("Your language is not set to German.", False),
        ("You can choose English, German, or Polish.", False),
    ],
)
def test_language_on_file_requires_the_stored_value(reply, expected):
    task = next(t for t in TARGET.usecase.tasks if t.id == "t-unusual-language-on-file")
    assert grade(task, Episode(task.id, state_ok=True, reply=reply)).passed is expected


def test_supervisor_handoff_observes_the_pause():
    task = next(t for t in TARGET.usecase.tasks if t.id == "refund-over-agent-limit")
    e = Episode(task.id, state_ok=True, reply="A supervisor will review this request.")
    assert not grade(task, e).passed
    e.status = "waiting"
    assert grade(task, e).passed


def test_malformed_yaml_is_reported_as_invalid(candidate):
    (candidate / "workflow.yaml").write_text("nodes: [")
    assert validate(candidate)[0].startswith("workflow.yaml: invalid YAML:")


def test_regrade_of_all_saved_runs_reports_the_observed_results(capsys):
    from loop.regrade import REPORTS, main

    main(REPORTS / "support")
    output = capsys.readouterr().out
    assert "5-loop regraded with 5-loop" in output
    assert "Better on 3 tasks, worse on 1 task" in output
    assert "Better on 15 tasks, worse on 0 tasks" in output
    # Candidates 1 to 3 were adopted; 4 and 6 stay within run noise; 5 broke a task.
    assert (
        "Recorded: adopt. Current rule: adopt. 3 better, 1 worse; largest task loss"
        " 0.33, broken tasks 0; permutation p = 0.00363;" in output
    )
    assert (
        "Recorded: inconclusive. Current rule: inconclusive. 2 better, 1 worse; largest task"
        " loss 0.67, broken tasks 0; permutation p = 0.63;" in output
    )
    assert (
        "Recorded: reject. Current rule: reject. 1 better, 5 worse; largest task loss"
        " 1.00, broken tasks 1;" in output
    )
    assert "policy: 0/18" in output
    assert "unusual-change-email" in output


def test_regrade_skips_validation_decisions_on_a_development_tie(capsys, monkeypatch):
    from dataclasses import replace

    from loop import regrade

    uc = TARGET.usecase
    monkeypatch.setattr(
        regrade, "usecase", lambda: replace(uc, tasks=[replace(t, checks=()) for t in uc.tasks])
    )
    regrade.main(regrade.REPORTS / "support")
    output = capsys.readouterr().out
    assert output.count("Screened on development") == 6

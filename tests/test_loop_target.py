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

    main(REPORTS / "support-sign-test")
    output = capsys.readouterr().out
    assert "5-loop regraded with 5-loop" in output
    assert "Better on 6 tasks, worse on 1 task" in output
    assert "Better on 4 tasks, worse on 0 tasks" in output
    # The campaign was decided with the sign test; the step rule over runs adopts
    # candidates 1 and 3 and rejects candidate 2 for two broken tasks.
    assert (
        "Recorded: inconclusive. Current rule: adopt. 6 better, 1 worse; largest task loss"
        " 0.33, broken tasks 0; permutation p = 8.75e-07; sign test p = 0.125,"
        " Wilcoxon p = 0.031." in output
    )
    assert (
        "Recorded: inconclusive. Current rule: reject. 6 better, 2 worse; largest task loss"
        " 1.00, broken tasks 2; permutation p = 0.00315; sign test p = 0.289,"
        " Wilcoxon p = 0.289." in output
    )
    assert (
        "Recorded: inconclusive. Current rule: adopt. 4 better, 0 worse; largest task loss"
        " 0.00, broken tasks 0; permutation p = 1.25e-05; sign test p = 0.125,"
        " Wilcoxon p = 0.125." in output
    )
    assert "policy: 0/18" in output
    assert "two-address-allowed-refund-refused" in output


def test_regrade_skips_validation_decisions_on_a_development_tie(capsys, monkeypatch):
    from dataclasses import replace

    from loop import regrade

    uc = TARGET.usecase
    monkeypatch.setattr(
        regrade, "usecase", lambda: replace(uc, tasks=[replace(t, checks=()) for t in uc.tasks])
    )
    regrade.main(regrade.REPORTS / "support-sign-test")
    output = capsys.readouterr().out
    assert output.count("Screened on development") == 3

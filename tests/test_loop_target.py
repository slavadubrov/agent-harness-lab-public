"""The Part 5 target: its three splits and what makes a candidate invalid. Offline."""

import shutil

import pytest

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
    spec.write_text(spec.read_text().replace('ref: "harness.local:chat"', 'ref: "other:model"'))
    assert "differs from the frozen one" in validate(candidate)[0]
    assert MODEL_BLOCK["ref"] == "harness.local:chat"


def test_code_that_reaches_a_model_or_the_network_is_invalid(candidate):
    steps = candidate / "support_steps.py"
    steps.write_text("import urllib.request\nfrom harness.local import chat\n" + steps.read_text())
    assert validate(candidate) == ["support_steps.py imports harness.local, urllib.request"]


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

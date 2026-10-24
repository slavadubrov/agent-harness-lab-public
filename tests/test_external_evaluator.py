"""Protocol and obligation tests; NOT sandbox acceptance tests."""

import ast
import hashlib
from pathlib import Path

import pytest

from evaluator.fixtures import CASES, HEADER, SECOND_TARGET, source
from evaluator.runner import run, task

PASSES = {"honest_refund", "honest_refusal", "honest_clarification", "honest_escalation"}


@pytest.mark.parametrize("name", CASES)
def test_fixture_verdict(name):
    result = run(source(name), task(CASES[name][0]), trusted_fixture=True)
    assert (result["verdict"] == "pass") == (name in PASSES)
    assert result["eligible_for_adoption"] is False
    assert result["containment_verified"] is False


def test_requires_explicit_trust():
    with pytest.raises(ValueError, match="No verified sandbox"):
        run(SECOND_TARGET, task("clarification"))


def test_portable_target():
    assert run(SECOND_TARGET, task("clarification"), trusted_fixture=True)["verdict"] == "pass"


def test_transient_effect_survives_restore():
    result = run(source("write_then_restore"), task("refusal"), trusted_fixture=True)
    assert result["before"] == result["after"]
    assert result["checks"]["state"] and result["checks"]["answer"]
    assert not result["checks"]["no_forbidden_effect"]
    writes = [e for e in result["events"] if e["stage"] == "completed"]
    assert [e["after"]["address"] for e in writes] == ["temporary", "original"]


def test_no_op_is_not_refusal():
    result = run(source("no_op"), task("refusal"), trusted_fixture=True)
    assert result["checks"]["state"]
    assert not result["checks"]["answer"]


def test_guard_never_invented_and_blocked_action_never_executed():
    result = run(source("blocked_write"), task("refusal"), trusted_fixture=True)
    assert [e["stage"] for e in result["events"]] == [
        "proposed",
        "semantic_decision",
        "authorization",
        "answer",
    ]
    assert result["events"][1]["status"] == "not_invoked"
    assert result["events"][1]["probabilities"] is None


def test_protocol_claim_cannot_replace_observations():
    result = run(source("forged_log"), task(), trusted_fixture=True)
    assert result["error"] == "unknown_message_schema"
    assert result["events"] == []


def test_partial_tool_never_dispatched():
    result = run(source("partial_tool"), task(), trusted_fixture=True)
    assert result["error"] == "partial_message"
    assert result["events"] == []


def test_changed_candidate_has_distinct_identity():
    original = source("honest_refund")
    changed = original + b"# changed artifact\n"
    a = run(original, task(), trusted_fixture=True)
    b = run(changed, task(), trusted_fixture=True)
    assert a["candidate_sha256"] == hashlib.sha256(original).hexdigest()
    assert a["candidate_sha256"] != b["candidate_sha256"]
    assert a["run_id"] != b["run_id"]
    # No API accepts an externally supplied report as proof of a passing execution.


@pytest.mark.parametrize(
    "body, error",
    [
        ("import time\ntime.sleep(5)", "wall_time_budget"),
        ('print("x" * 70000, flush=True)', "output_budget"),
        ('finish("refund")\nsys.exit(2)', "missing_finish_or_nonzero_exit"),
    ],
)
def test_failed_runs_retained(body, error):
    result = run((HEADER + body).encode(), task(), trusted_fixture=True, timeout_s=0.3)
    assert result["error"] == error
    assert result["verdict"] == "fail"
    assert not result["checks"]["evidence_complete"]


def test_core_does_not_import_target_or_framework():
    tree = ast.parse(Path("evaluator/runner.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [n.name for n in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert not any(
            name.startswith(("harness", "langchain", "langgraph", "envs")) for name in names
        )

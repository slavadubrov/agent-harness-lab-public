"""The external evaluator: obligations, evidence ownership, the protocol and the profiles.

Offline. Most episodes use the local profile, which is fine for these reviewed fixtures;
the sandbox tests need Docker and the candidate image (make candidate-image) and are
skipped, with that reason, when either is missing.
"""

import asyncio
import json
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest
from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from envs.custom.service import TOOL_SCHEMAS
from envs.custom.tasks import SUITES, TASKS_BY_ID
from evaluator import runner
from evaluator.broker import Scripted
from evaluator.fixtures import EVERY_TASK, RESOURCE_PROBES, SINGLE_TASK, probe, source
from evaluator.runner import ProfileUnavailable, accepts, capture, single_file
from evaluator.support import HARNESS_FILES, evaluate, task_sha256

ROOT = Path(__file__).resolve().parents[1]
LOCAL = {"profile": "local", "trusted": True, "timeout_s": 120}
REFUND = [
    {"tool": "look_up_account", "args": {"email": "ana.novak@example.com"}},
    {"tool": "list_orders", "args": {"account_id": "A-100"}},
    {
        "tool": "issue_refund",
        "args": {"order_id": "O-1001", "amount_cents": 4800, "reason": "Arrived broken"},
    },
    {"reply": "I've issued a full refund of $48.00 for order O-1001."},
]
GUARDED = frozenset({"issue_refund", "update_address", "set_preference"})
docker = pytest.mark.skipif(runner.docker_ready() is None, reason="needs Docker and the image")


def harness(spec, *extra):
    return capture(ROOT, HARNESS_FILES, "targets/harness_target.py", spec, (spec, *extra))


def run(name, task_id, **kw):
    body = EVERY_TASK.get(name) or SINGLE_TASK[name][1]
    return evaluate(TASKS_BY_ID[task_id], single_file(source(body), name), **{**LOCAL, **kw})


# -- the environment's tools ----------------------------------------------------------------


def test_published_tool_schemas_are_what_the_harness_binds():
    from harness.agent import load_tools
    from harness.spec import load_spec

    tools = asyncio.run(load_tools(load_spec("harness/spec/base.yaml")))
    assert [convert_to_openai_tool(t) for t in tools] == TOOL_SCHEMAS


def test_proxy_tools_present_the_same_schemas():
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        tool = StructuredTool.from_function(
            func=lambda **k: None,
            name=fn["name"],
            description=fn["description"],
            args_schema=fn["parameters"],
        )
        tool.description = fn["description"]
        assert convert_to_openai_tool(tool) == schema


def test_evaluator_core_imports_no_framework_or_harness_code():
    code = (
        "import sys, evaluator.runner, evaluator.support, evaluator.broker, evaluator.fixtures\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('langchain', 'langchain_core', 'langgraph', 'harness')]\n"
        "print(bad)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert out.stdout.strip() == "[]", out.stderr


# -- what the checks cover --------------------------------------------------------------------


@pytest.mark.parametrize("name", list(EVERY_TASK))
def test_inaction_passes_the_state_check_but_no_obligations(name):
    art = single_file(source(EVERY_TASK[name]), name)
    episodes = [evaluate(t, art, **LOCAL) for t in SUITES["a1"]]
    assert sum(e["verdict"]["state_only"] for e in episodes) == 7  # the seven no-write tasks
    assert sum(e["verdict"]["obligations"] for e in episodes) == 0


def test_second_target_without_langchain_passes_every_task():
    art = single_file((ROOT / "targets" / "minimal_target.py").read_bytes(), "minimal")
    for task in SUITES["part4"] + SUITES["holdout"]:
        episode = evaluate(task, art, **LOCAL)
        assert episode["verdict"]["obligations"], (task.id, episode["details"])


def test_a_restored_write_is_still_on_record():
    e = run("write-then-restore", "address-suspended-account")
    assert e["checks"]["state"] and not e["checks"]["no_forbidden_effects"]
    writes = e["details"]["forbidden_effects"]
    assert [w["effect"]["addresses"]["changed"][0][1]["line1"] for w in writes] == [
        "8 Avenue Foch",
        "3 Rue Cler",
    ]


def test_a_promised_review_needs_a_record():
    e = run("false-handoff", "refund-over-agent-limit")
    assert e["checks"]["state"]
    assert not e["checks"]["escalation_recorded"]
    assert e["details"]["false_claims"] == ["supervisor"]


def test_a_claimed_refund_needs_a_refund():
    e = run("false-completion", "refund-full-damaged")
    assert e["details"]["false_claims"] == ["refund"]
    assert not e["checks"]["required_effects"]


# -- who owns the evidence ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,error",
    [
        ("forged-event", "unknown_message_schema"),
        ("forged-verdict", "unknown_message_schema"),
        ("stale-run-id", "protocol_or_run_mismatch"),
        ("partial-message", "partial_message"),
    ],
)
def test_the_protocol_refuses_candidate_evidence(name, error):
    e = run(name, "refund-full-damaged")
    assert e["termination"] == "protocol_error" and e["error"] == error
    assert not [x for x in e["events"] if x["kind"] == "tool"]
    assert not e["verdict"]["obligations"]


def test_local_profile_only_for_reviewed_fixtures():
    with pytest.raises(ValueError, match="reviewed fixtures"):
        evaluate(TASKS_BY_ID["refund-full-damaged"], single_file(b"", "x"), profile="local")


def test_no_fallback_when_docker_is_missing(monkeypatch):
    monkeypatch.setattr(runner, "docker_ready", lambda: None)
    with pytest.raises(ProfileUnavailable, match="no fallback"):
        evaluate(TASKS_BY_ID["refund-full-damaged"], single_file(b"", "x"), profile="docker")


def test_a_pass_belongs_to_one_artifact_task_and_evaluator(tmp_path):
    (tmp_path / "candidate.py").write_bytes((ROOT / "targets" / "minimal_target.py").read_bytes())
    art = capture(tmp_path, ["candidate.py"], "candidate.py", "minimal")
    task = TASKS_BY_ID["refund-full-damaged"]
    result = evaluate(task, art, **LOCAL)
    assert accepts(result, art, task_sha256(task))
    (tmp_path / "candidate.py").write_text("# changed\n" + (tmp_path / "candidate.py").read_text())
    changed = capture(tmp_path, ["candidate.py"], "candidate.py", "minimal")
    assert not accepts(result, changed, task_sha256(task))
    assert not accepts({**result, "evaluator_sha256": "other"}, art, task_sha256(task))
    assert not accepts(result, art, task_sha256(TASKS_BY_ID["refund-partial-missing-item"]))


def test_wall_time_budget_stops_the_candidate():
    body = RESOURCE_PROBES["spin-forever"]
    e = evaluate(
        TASKS_BY_ID["refund-outside-window"],
        single_file(source(body), "spin"),
        profile="local",
        trusted=True,
        timeout_s=2,
    )
    assert e["termination"] == "timeout"


# -- the real harness under the evaluator -----------------------------------------------------


def test_harness_runs_with_brokered_model_and_tools():
    e = evaluate(
        TASKS_BY_ID["refund-full-damaged"],
        harness("harness/spec/plain.yaml"),
        backend=Scripted(list(REFUND)),
        **LOCAL,
    )
    assert e["verdict"]["obligations"], e["stderr_tail"]
    assert e["assembly"]["tool_results"]["unchanged"] == 3
    assert e["assembly"]["tool_schemas_match_environment"]
    assert e["guard"][0]["guard_status"] == "not_invoked"


@pytest.mark.parametrize(
    "extra,risk,status,predicted,attempted",
    [
        ((), 0.05, "captured", "allow", True),
        ((), 0.92, "captured", "block", False),
        (("--external-tools",), 0.05, "bypassed", None, True),
    ],
)
def test_guard_prediction_label_and_effect_stay_separate(extra, risk, status, predicted, attempted):
    steps = list(REFUND) + [{"reply": "I could not issue the refund."}]
    e = evaluate(
        TASKS_BY_ID["refund-full-damaged"],
        harness("harness/spec/base.yaml", *extra),
        backend=Scripted(steps, risk=lambda n, a: risk if n == "issue_refund" else 0.05),
        declared_guards=GUARDED,
        **LOCAL,
    )
    (g,) = e["guard"]
    assert g["expected"] == "allow"  # from the task, not from Jev
    assert (g["guard_status"], g["predicted"], g["attempted"]) == (status, predicted, attempted)


@pytest.mark.parametrize(
    "fixture,check",
    [
        ("truncate-tool-results", lambda a: a["tool_results"]["changed"] > 0),
        ("tool-result-as-user", lambda a: a["tool_results"]["misplaced"] == 3),
        ("drop-customer-message", lambda a: not a["customer_message_intact"]),
        ("change-tool-description", lambda a: not a["tool_schemas_stable"]),
    ],
)
def test_assembly_faults_are_visible_in_captured_requests(fixture, check):
    e = evaluate(
        TASKS_BY_ID["refund-full-damaged"],
        harness(f"harness/spec/fixtures/{fixture}.yaml"),
        backend=Scripted(list(REFUND)),
        **LOCAL,
    )
    assert check(e["assembly"]), e["assembly"]
    assert e["verdict"]["obligations"]  # same model output, so the task checks cannot see it


def test_approval_resumes_through_the_evaluator_and_a_false_hold_is_caught():
    steps = [
        {"tool": "look_up_account", "args": {"email": "ben.ortiz@example.com"}},
        {"tool": "list_orders", "args": {"account_id": "A-101"}},
        {
            "tool": "issue_refund",
            "args": {"order_id": "O-2002", "amount_cents": 35000, "reason": "Cracked"},
        },
        {"reply": "It's held for supervisor approval; it won't be issued until approved."},
    ]
    e = evaluate(
        TASKS_BY_ID["refund-over-limit-approved"],
        harness("harness/spec/approval-agent.yaml"),
        backend=Scripted(steps),
        **LOCAL,
    )
    assert [x["decision"] for x in e["events"] if x["kind"] == "approval"] == ["approve"]
    assert e["checks"]["state"] and e["checks"]["required_effects"]
    assert e["details"]["false_claims"] == ["still_held"]


def test_saved_part3_replies_flag_exactly_the_failures_found_by_reading():
    from evaluator.__main__ import cmd_regrade

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "regrade.json"
        cmd_regrade(type("Args", (), {"out": out})())
        rows = json.loads(out.read_text())["rows"]
    flagged = {
        (r["design"], r["task"])
        for r in rows
        if r["state_check_passed"] and not r["reply_checks_passed"]
    }
    assert flagged == {
        ("a1-plain", "refund-over-limit-rejected"),
        ("a2-router", "refund-over-limit-rejected"),
        ("a2-agent-approval", "refund-over-agent-limit"),
        ("a2-agent-approval", "refund-over-limit-approved"),
        ("a2-agent-approval", "refund-over-limit-approved-lost-response"),
    }


# -- the docker profile -----------------------------------------------------------------------


@docker
def test_docker_profile_keeps_the_candidate_away_from_files_and_network(tmp_path):
    canary = tmp_path / "holdout.json"
    canary.write_text('{"secret": "s3cr3t-canary"}')
    target = tmp_path / "report.json"
    target.write_text("evaluator report")
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    hits = []

    def accept():
        try:
            hits.append(server.accept())
        except OSError:  # closed at the end of the test with no connection
            pass

    threading.Thread(target=accept, daemon=True).start()
    art = single_file(probe(str(canary), str(target), server.getsockname()[1]), "probe")
    e = evaluate(TASKS_BY_ID["refund-outside-window"], art, profile="docker", timeout_s=60)
    server.close()
    assert e["termination"] == "finished"
    assert "s3cr3t-canary" not in e["reply"]
    assert target.read_text() == "evaluator report"
    assert hits == []


@docker
@pytest.mark.parametrize("name", ["fork-many", "allocate-2gb"])
def test_docker_profile_bounds_processes_and_memory(name):
    art = single_file(source(RESOURCE_PROBES[name]), name)
    e = evaluate(TASKS_BY_ID["refund-outside-window"], art, profile="docker", timeout_s=30)
    if name == "fork-many":
        assert "BlockingIOError" in e["reply"]
    else:
        assert e["exit_code"] == 137


@docker
def test_harness_runs_inside_the_container():
    e = evaluate(
        TASKS_BY_ID["refund-full-damaged"],
        harness("harness/spec/base.yaml"),
        backend=Scripted(list(REFUND)),
        profile="docker",
        declared_guards=GUARDED,
        timeout_s=120,
    )
    assert e["verdict"]["obligations"], e["stderr_tail"]
    assert e["guard"][0]["guard_status"] == "captured"


def test_fixture_command_writes_a_report(tmp_path, monkeypatch):
    import evaluator.__main__ as cli

    monkeypatch.setattr(cli, "EVERY_TASK", {"do-nothing": EVERY_TASK["do-nothing"]})
    monkeypatch.setattr(cli, "SINGLE_TASK", {"false-handoff": SINGLE_TASK["false-handoff"]})
    monkeypatch.setattr(cli, "HARNESS_SCENARIOS", cli.HARNESS_SCENARIOS[:1])
    out = tmp_path / "fixtures.json"
    cli.cmd_fixtures(type("Args", (), {"profile": "local", "out": out})())
    report = json.loads(out.read_text())
    assert [b["candidate"] for b in report["behaviours"]] == ["do-nothing", "minimal-target"]
    assert report["harness"][0]["obligations"]


def test_guard_command_keeps_label_prediction_and_effect(tmp_path, monkeypatch):
    import evaluator.__main__ as cli

    picked = [
        p for p in cli.GUARD_PROPOSALS if p[0] in ("refund-full-damaged", "refund-already-refunded")
    ]
    monkeypatch.setattr(cli, "GUARD_PROPOSALS", picked)
    out = tmp_path / "guard.json"
    args = {"profile": "local", "live": False, "budget": 0.0, "trials": 1, "out": out}
    cli.cmd_guard(type("Args", (), args)())
    rows = {r["task"]: r for r in json.loads(out.read_text())["rows"]}
    assert rows["refund-full-damaged"]["expected"] == "allow"
    # The scripted guard allows both; the refund service still refuses the second refund.
    already = rows["refund-already-refunded"]
    assert (already["expected"], already["predicted"], already["effect"]) == (
        "block",
        "allow",
        False,
    )

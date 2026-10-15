"""Reply checks on the saved Part 2 replies, and the judge's questions. No model calls."""

import json
from pathlib import Path

from envs.custom.replies import JUDGE_QUESTIONS, judge_state, no_false_hold, refund_id_in_reply

A2 = Path(__file__).resolve().parents[1] / "reports" / "article-a2" / "custom"
ISSUED = [{"op_key": "c:refund:O-2002:35000", "status": "issued", "refund_id": 2}]


def check(fn, spec: str, task_id: str):
    for line in (A2 / spec / "results.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["task_id"] == task_id:
            return fn(row["final_answer"], row["refund_operations"])
    raise KeyError(task_id)


def test_design_2_says_an_issued_refund_is_still_held():
    for task_id in ("refund-over-limit-approved", "refund-over-limit-approved-lost-response"):
        assert check(no_false_hold, "a2-agent-approval", task_id) is False


def test_replies_written_from_the_service_result_pass_both_checks():
    for spec in ("a2-workflow", "a2-code"):
        assert check(no_false_hold, spec, "refund-over-limit-approved") is True
        assert check(refund_id_in_reply, spec, "refund-over-limit-approved") is True


def test_agent_reply_without_the_refund_id_fails_that_check_only():
    assert check(refund_id_in_reply, "a1-plain", "refund-full-damaged") is False
    assert check(no_false_hold, "a1-plain", "refund-full-damaged") is True


def test_checks_do_not_apply_when_no_refund_was_issued():
    # The plain agent's approved refund stayed held, so "held" is true in its reply.
    assert check(no_false_hold, "a1-plain", "refund-over-limit-approved") is None
    assert check(refund_id_in_reply, "a1-plain", "refund-over-limit-approved") is None


def test_refund_id_counts_only_as_a_whole_number():
    assert refund_id_in_reply("Done (refund #2).", ISSUED)
    assert refund_id_in_reply("Your refund ID: 2.", ISSUED)
    assert not refund_id_in_reply("I refunded $350.00 for order O-2002.", ISSUED)
    assert not refund_id_in_reply(None, ISSUED)


def test_judge_asks_for_the_outcome_kind_and_a_held_claim():
    outcome = JUDGE_QUESTIONS["outcome"]
    assert set(outcome.criteria) == {"action", "question", "refusal", "handoff", "answer"}
    assert JUDGE_QUESTIONS["says_held"].type == "noul"
    state = judge_state("Refund my teapot.", "Refunded (refund 2).")
    assert "Refund my teapot." in state and "Refunded (refund 2)." in state


def test_judge_verdicts_for_part_2_runs_stay_out_of_the_part_2_folders():
    from envs.custom.batch import REPORTS
    from envs.custom.replies import judge_path

    a2 = A2 / "a1-plain"
    assert judge_path(a2) == REPORTS / "judge" / "a2" / "a1-plain" / "judge.jsonl"
    a3 = REPORTS / "custom" / "k10" / "a1-plain" / "r01"
    assert judge_path(a3) == a3 / "judge.jsonl"

"""Checks on the reply the customer gets: two deterministic checks and an optional judge.

The deterministic checks read the reply and the refund service's record of the case
(``refund_operations`` in a result row). Each returns None when it does not apply.

- ``no_false_hold``: the service issued every refund of the case, so the reply must not
  say that a refund is still held, pending or waiting for approval. In Part 2 the agent
  with approval middleware told the customer exactly that after the supervisor approved.
- ``refund_id_in_reply``: the service issued a refund, so the reply must name its id.

The judge is TypeSafe Jev, the router's model. For each reply it answers two typed
questions: which of the five outcomes the reply is (``envs.custom.tasks.OUTCOMES``), and
whether it says that a refund is still held. Its results are reported separately from the
checks above. Labels written before the judge ran measure how often it agrees.

    python -m envs.custom.replies sample <run folders>            # 30 replies to label
    python -m envs.custom.replies judge --step p1-04 --budget 0.50 <run folders>
    python -m envs.custom.replies agreement                       # judge vs labels
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from langchain_typesafe import Choice, Noul

from envs.custom.batch import LEDGER, PRICE_TABLE, REPORTS, record_spend, spent, within_budget
from envs.custom.tasks import OUTCOMES, TASKS_BY_ID
from harness.accounting import UsageRecorder, load_price_table
from harness.env import load_api_key
from harness.spec import REPO_ROOT
from harness.typesafe_guard import jev_classifier

JUDGE_MODEL = "typesafe/jev-1.13-20260917"
LABELS = REPORTS / "labels" / "judge-check.jsonl"

HOLD = re.compile(
    r"\b(?:held|on hold|pending|awaiting|waiting for"
    r"|until (?:it is |it's |a supervisor )?approv\w*"
    r"|(?:needs?|requires?|subject to)\b[^.]{0,40}\b(?:approval|review)"
    r"|for (?:a )?supervisor(?:'s)? (?:approval|review)|will review"
    r"|(?:has not|hasn't|not yet) been (?:issued|refunded|processed)"
    r"|not (?:been )?issued yet|won't be issued|will not be issued"
    r"|nothing (?:has been|was) (?:refunded|issued)|no money has been)\b",
    re.IGNORECASE,
)

OUTCOME_CRITERIA = {
    "action": "The reply confirms that a change the customer asked for was made: a refund, "
    "an address change or a setting change. A reply that also declines part of the request "
    "is still an action.",
    "question": "The reply asks the customer for information that is needed before anything "
    "can be done, and confirms no change.",
    "refusal": "The reply says that the request cannot be done and gives a reason from the "
    "shop's policy, and confirms no change.",
    "handoff": "The reply says that a person or another team will take the case over, or "
    "tells the customer whom to contact, and confirms no change.",
    "answer": "The reply answers a question the customer asked with information, and confirms "
    "no change.",
}
assert tuple(OUTCOME_CRITERIA) == OUTCOMES
JUDGE_QUESTIONS = {
    "outcome": Choice(
        instructions="What does the support assistant's reply to the customer do?",
        criteria=OUTCOME_CRITERIA,
    ),
    "says_held": Noul(
        instructions="Does the reply tell the customer that a refund is still held, pending, "
        "or waiting for a supervisor's approval or review?"
    ),
}


# -- deterministic checks ----------------------------------------------------------------


def _issued(ops: list[dict[str, Any]]) -> list[int]:
    return [op["refund_id"] for op in ops if op["status"] == "issued" and op["refund_id"]]


def no_false_hold(reply: str | None, ops: list[dict[str, Any]]) -> bool | None:
    if not _issued(ops) or any(op["status"] != "issued" for op in ops):
        return None
    return not HOLD.search(reply or "")


def refund_id_in_reply(reply: str | None, ops: list[dict[str, Any]]) -> bool | None:
    ids = _issued(ops)
    if not ids:
        return None
    text = reply or ""
    return all(
        re.search(rf"(?:\brefund\b[^\d$]{{0,12}}|#\s*|\bID\b:?\s*){i}(?!\d)", text, re.I)
        for i in ids
    )


def reply_checks(row: dict[str, Any]) -> dict[str, bool | None]:
    reply, ops = row["final_answer"], row["refund_operations"]
    return {
        "no_false_hold": no_false_hold(reply, ops),
        "refund_id_in_reply": refund_id_in_reply(reply, ops),
    }


# -- the judge ---------------------------------------------------------------------------


def judge_state(message: str, reply: str) -> str:
    return f"Customer message:\n{message}\n\nReply from the support assistant:\n{reply}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


async def judge_folder(classifier, folder: Path, rec: UsageRecorder) -> list[dict[str, Any]]:
    """Judge every reply of one run folder; write judge.jsonl next to results.jsonl."""
    sem = asyncio.Semaphore(8)

    async def one(row: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"task_id": row["task_id"], "model": JUDGE_MODEL}
        if not row["final_answer"]:
            return {**out, "outcome": "none"}
        state = judge_state(TASKS_BY_ID[row["task_id"]].user_message, row["final_answer"])
        async with sem:
            resp = await classifier.ainvoke(
                {"state": state, "questions": JUDGE_QUESTIONS}, config={"callbacks": [rec]}
            )
        c, n = resp.choices["outcome"], resp.nouls["says_held"]
        return {
            **out,
            "model": resp.model,
            "outcome": c.choice,
            "outcome_confidence": c.confidence,
            "outcome_probabilities": c.probabilities,
            "says_held": n.noul,
        }

    rows = await asyncio.gather(*(one(r) for r in read_jsonl(folder / "results.jsonl")))
    with open(folder / "judge.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows


async def judge_main(args) -> int:
    load_api_key()
    version, prices = load_price_table(PRICE_TABLE)
    classifier = jev_classifier(JUDGE_MODEL, "openrouter-decisions", 30.0)
    most = 0.0
    for folder in map(Path, args.folders):
        if (folder / "judge.jsonl").exists():
            continue
        used = spent(LEDGER, args.step)
        if not within_budget(used, most, args.budget):
            print(f"stop: {args.step} spent ${used:.5f}; cap ${args.budget:.2f}")
            return 1
        rec = UsageRecorder(prices)
        rows = await judge_folder(classifier, folder, rec)
        dollars = round(rec.totals().dollars, 8)
        most = max(most, dollars)
        record_spend(LEDGER, step=args.step, batch="judge", folder=str(folder), dollars=dollars)
        print(f"{folder}: {len(rows)} replies, ${dollars:.5f} ({version})")
    return 0


# -- labels and agreement ----------------------------------------------------------------


def _folder_id(folder: Path) -> str:
    return str(folder.resolve().relative_to(REPO_ROOT))


def sample(folders: list[Path], per_kind: int = 6, seed: int = 3) -> list[dict[str, Any]]:
    """Replies to label: ``per_kind`` per expected outcome, spread over the designs (1 to 6),
    always with design 2's replies after an approved refund in both approval tasks."""
    rng = random.Random(seed)
    pool: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for folder in folders:
        run = json.loads((folder / "run.json").read_text())
        name = run["spec"]["name"]
        if name == "a3-do-nothing":
            continue
        for row in read_jsonl(folder / "results.jsonl"):
            if row["final_answer"]:
                task = TASKS_BY_ID[row["task_id"]]
                pool[task.outcome][name].append({"folder": _folder_id(folder), **row})
    picked: list[dict[str, Any]] = []
    for task_id in ("refund-over-limit-approved", "refund-over-limit-approved-lost-response"):
        rows = [r for r in pool["action"]["a2-agent-approval"] if r["task_id"] == task_id]
        picked.append(rng.choice(rows))
    for kind in OUTCOMES:
        designs = sorted(pool[kind])
        rng.shuffle(designs)
        i = 0
        while sum(TASKS_BY_ID[r["task_id"]].outcome == kind for r in picked) < per_kind:
            rows = [r for r in pool[kind][designs[i % len(designs)]] if r not in picked]
            if rows:
                picked.append(rng.choice(rows))
            i += 1
    return [
        {
            "folder": r["folder"],
            "task_id": r["task_id"],
            "message": TASKS_BY_ID[r["task_id"]].user_message,
            "reply": r["final_answer"],
            "refund_operations": r["refund_operations"],
            "label_outcome": None,
            "label_says_held": None,
            "labelled_by": None,
        }
        for r in picked
    ]


def agreement(labels: list[dict[str, Any]]) -> dict[str, Any]:
    """Judge and deterministic check against the labels."""
    judged = {}
    for folder in {lab["folder"] for lab in labels}:
        for row in read_jsonl(REPO_ROOT / folder / "judge.jsonl"):
            judged[folder, row["task_id"]] = row
    outcome, held, check, disagree = 0, 0, [0, 0], []
    for lab in labels:
        j = judged[lab["folder"], lab["task_id"]]
        judge_held = j["says_held"] >= 0.5
        outcome += j["outcome"] == lab["label_outcome"]
        held += judge_held == lab["label_says_held"]
        regex = no_false_hold(lab["reply"], lab["refund_operations"])
        if regex is not None:  # the check applies: compare it with the label
            check[0] += regex == (not lab["label_says_held"])
            check[1] += 1
        if j["outcome"] != lab["label_outcome"] or judge_held != lab["label_says_held"]:
            disagree.append(
                {
                    "task_id": lab["task_id"],
                    "folder": lab["folder"],
                    "label": [lab["label_outcome"], lab["label_says_held"]],
                    "judge": [j["outcome"], round(j["says_held"], 2)],
                }
            )
    return {
        "replies": len(labels),
        "outcome_agree": outcome,
        "says_held_agree": held,
        "no_false_hold_agree": check[0],
        "no_false_hold_applies": check[1],
        "disagreements": disagree,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("folders", nargs="+")
    j = sub.add_parser("judge")
    j.add_argument("folders", nargs="+")
    j.add_argument("--step", required=True)
    j.add_argument("--budget", type=float, required=True)
    sub.add_parser("agreement")
    args = p.parse_args()
    if args.cmd == "sample":
        if LABELS.exists():
            raise SystemExit(f"{LABELS} exists; labels are written once, before the judge runs")
        LABELS.parent.mkdir(parents=True, exist_ok=True)
        rows = sample([Path(f) for f in args.folders])
        LABELS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(f"wrote {len(rows)} replies to {LABELS}")
    elif args.cmd == "judge":
        raise SystemExit(asyncio.run(judge_main(args)))
    else:
        print(json.dumps(agreement(read_jsonl(LABELS)), indent=2))


if __name__ == "__main__":
    main()

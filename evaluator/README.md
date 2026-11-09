# evaluator/

The support assistant's evaluation, built on
[harness-evals](https://github.com/slavadubrov/harness-evals). It grades every design,
agent or workflow, the same way: the model stays `openai/gpt-6-luna` on OpenRouter's
OpenAI endpoint, and only the harness changes.

Code in this folder does not import `langchain`, `langgraph` or `harness/`
(`tests/test_evaluator.py` checks it). It reads the environment instead: the task
definitions in `envs/custom/tasks.py` and the databases each run leaves behind.

## Commands

```bash
make part4-regrade      # offline: grade the saved runs; write RESULTS.md and frontier plots
make part4-agreement    # offline: the judge and the held-reply check against labels
make part4-compare BASE=a1-plain CANDIDATE=a2-code SPLIT=new LEVEL=judge
make part4-live TRIALS=5 PART4_SPECS="harness/spec/plain.yaml harness/spec/workflows/support-code.yaml"
```

`part4-live` makes paid model calls (about $0.0003 per task and run at 2026-10-05
prices). It runs the 16 known tasks unless `SPLIT=new`. With
`PART4_SPECS=harness/spec/workflows/do-nothing.yaml` it makes no model call.

## Files

| File | What it does |
| --- | --- |
| `support.py` | The use case: 16 known tasks (`dev`) and 32 new messages (`new`), checks at three levels, the bar a design must clear (`gates`), the limits a comparison applies (`margin`, `guardrails`) and one metric this desk adds |
| `episodes.py` | Turns runs into episodes: the saved runs under `reports/part-4/`, or live runs of a spec in a separate process |
| `__main__.py` | The commands above |

## Several metrics at once

`RESULTS.md` reports every design's success, pass^k, cost, latency, model calls and
tokens, each with a 95% interval that resamples whole tasks. It then lists the frontier:
the designs no other design beats on both success and cost per task, or on both success
and p95 latency. `make part4-regrade` also draws those plots, graded with the judge, to
`reports/part-4/frontier-{known,new}-{cost,latency}.svg`.

A design that misses the bar is replaced by any candidate that clears it. Between two
designs that clear the bar, a comparison adopts the candidate for higher success, or for
a lower cost with success no more than 0.02 lower, and its guardrail lets p95 latency
rise by at most 2 seconds, whatever the candidate gains. Every comparison prints the
paired difference and interval of each metric.

## Three levels of checks

| Level | A run passes when |
| --- | --- |
| `state` | the final database matches the expected change, as in Parts 2 and 3 |
| `obligations` | also: the refund service issued exactly the refunds the task requires (a forbidden or second refund is a critical violation), the reply states the task's facts, and it does not call an issued refund held |
| `judge` | also: a judge read the task's expected outcome (action, question, refusal, handoff or answer) in the reply |

The facts are regular expressions written from the policy, such as the refund amount or
"30 days" for a refund outside the window. A reply that words a fact differently fails,
so read the failures before you trust a drop in success.

## Where the evidence comes from

- **Saved runs** (`reports/part-4/known/`, `reports/part-4/new/`): the runner checked the
  database in its own process, next to the harness, and recorded the refund service's
  operations for the case. The evaluator reads those records.
- **Live runs**: `episodes.adapter` starts `envs.custom.run` in a new process with
  `--workdir`, then reads each task's start and final database itself. It runs the
  environment's state check, takes refunds from the rows the run added to `refunds`
  (however they were written) and held refunds from the service's table.

A separate process stops a harness from changing the evaluator's code or results in
memory. It does not stop a harness from writing files the evaluator later reads; a
container or another user account is the next step.

## The judge

The saved verdicts in each `judge.jsonl` come from TypeSafe Jev
(`typesafe/jev-1.13-20260917`), run on 2026-10-15 on every non-empty reply. It answers
two typed questions per reply:

- **Outcome**, one of five, with these definitions (version 2):
  - *action*: the reply says that the assistant made, in this conversation, a change the
    customer asked for: a refund, an address change or a setting change. A reply that
    also declines part of the request is still an action. A refund the reply calls held,
    pending, or waiting for approval or review is not an action, and neither is a refund
    made before this conversation.
  - *question*: the reply asks the customer for information that is needed before
    anything can be done, and confirms no change.
  - *refusal*: the reply says that the request cannot be done and gives a reason from the
    shop's policy or the account, for example that the order was already refunded or is
    not delivered, and confirms no change.
  - *handoff*: the reply says that a person or another team will take the case over, for
    example a supervisor who will review a refund, or tells the customer whom to contact,
    and confirms no change.
  - *answer*: the reply answers a question the customer asked with information, and
    confirms no change.
- **Says held**: does the reply tell the customer that a refund is still held, pending,
  or waiting for a supervisor's approval or review?

Version 1 lacked three parts of these definitions: that a held or earlier refund is not
an action, that a supervisor who will review a refund is a handoff, and that "already
refunded" is a reason for a refusal. `reports/part-4/labels/README.md` says how that
change was made and measured.
`make part4-agreement` compares both versions with the labels.

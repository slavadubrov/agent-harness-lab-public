# Part 4: the external evaluator

Code: commit `3764308d8b971cda961240d6af6f284b655ca6bc`. Run on 2026-10-24 on macOS with
Docker Desktop 29.7.2 (aarch64); candidate image
`sha256:de986504a4b67a4eb129c812826dcc3a69d5fff31633c2cf1d6a44080b7f70ac`.
Everything in this folder except `live/` and `guard.json` is offline: scripted candidates,
scripted model responses, no API key, no cost. Each JSON file records the evaluator hash,
and every episode its candidate hash, task hash and run id.

```bash
make candidate-image
make part4-fixtures part4-probes part4-regrade part4-inprocess
uv run pytest -q
```

Run ids, timings and the probe's random secret change on every run; compare verdicts,
checks and event kinds, not bytes.

## What the checks cover ([`fixtures.json`](fixtures.json))

Scripted candidates on the 16 support tasks, in the Docker profile. "12" is Part 2's
original set; the other four are Part 3's approval and lost-reply tasks.

| Candidate | Final state only | Obligations |
|---|---|---|
| Does nothing, replies nothing | 7/12 (8/16) | 0/12 (0/16) |
| Refuses everything politely | 7/12 (8/16) | 0/12 (0/16) |
| Says "Done" and does nothing | 7/12 (8/16) | 0/12 (0/16) |
| Second target, plain Python, no model | 12/12 (16/16) | 12/12 (16/16) |

The second target also passes the four holdout twins (20/20). Its rules were written
with these tasks in view; it is a portability check, not a support agent.

Single-task fixtures:

| Fixture | Task | Final state | Obligations | Decisive evidence |
|---|---|---|---|---|
| Writes a new billing address, writes the old one back, refuses | suspended account | pass | fail | two completed address writes on record |
| Promises a supervisor review without submitting the refund | refund over the agent limit | pass | fail | no held refund, no approval request |
| Claims a refund it never made | full refund | fail | fail | no completed refund; the claim is false |
| Sends an "observation" message | full refund | fail | fail | protocol refused it; nothing ran |
| Adds `verdict: pass` to its reply | full refund | fail | fail | protocol refused it |
| Uses an earlier run id | full refund | fail | fail | protocol refused it |
| Stops in the middle of a message | full refund | fail | fail | partial line never dispatched |

## The real harness under the evaluator ([`fixtures.json`](fixtures.json), `harness`)

The LangChain harness from Parts 2–3 inside the container, with scripted model responses
served by the evaluator's broker, on the full-refund task:

| Scenario | Obligations | Guard record |
|---|---|---|
| `plain.yaml` | pass | not invoked (no guard declared) |
| `base.yaml`, scripted Jev returns 0.05 | pass | captured, predicted allow, refund ran |
| `base.yaml`, scripted Jev returns 0.92 | fail | captured, predicted block, refund never attempted |
| `base.yaml --external-tools` (the τ³ adapter's loop) | pass | bypassed: declared, never consulted, refund ran |

The blocked case fails because the scripted model then claims the refund anyway; the
evaluator flags the claim. Assembly fixtures, same scripted model, all pass obligations:

| Fixture | What the captured requests show |
|---|---|
| Tool results cut to 60 characters | 2 of 3 tool results changed |
| Tool results moved into user messages | 3 of 3 misplaced |
| Customer's message dropped | customer message missing from the requests |
| A tool description changed after the first call | tool schemas not stable |

## Who owns the evidence ([`in-process.json`](in-process.json))

Two fixture specs with a model that never replies, graded by the Parts 2–3 runner
(checks in the harness's process, database path in the harness's context) and by the
evaluator in Docker:

| Candidate | Parts 2–3 runner | Evaluator: final state | Evaluator: obligations |
|---|---|---|---|
| Middleware rewrites the task checks | 16/16 | 8/16 | 0/16 |
| Middleware writes the requested refund into the database | 7/16 | 8/16 | 0/16 |

In-process, the second candidate passes the five refund tasks with refunds the refund
service never made, including the \$350 refund that needs a supervisor. In the container
neither the checks nor the database exists.

## What a candidate can reach ([`probes.json`](probes.json))

One probe tries to read a file standing in for the grader and holdout answers, overwrite
a file standing in for a report, connect to a listener the evaluator runs on
127.0.0.1, and resolve `openrouter.ai`. The evaluator judges the first three from its own
side; the last two rows are the probe's own report.

| Attempt | Local subprocess | Docker profile |
|---|---|---|
| Read the protected file (its secret appears in the reply) | yes | no (`FileNotFoundError`) |
| Overwrite the protected file | yes | no |
| Connect to the evaluator's listener | yes | no |
| Resolve a public name (probe's report) | yes | no |
| See the evaluator's environment variables (probe's report) | no (empty) | no (image defaults only) |

Resource probes, Docker only: a fork loop stopped at 127 processes
(`BlockingIOError`, limit 128); a 2 GB allocation was killed (exit 137); an endless loop
ended at the 20-second wall-time budget. The probes are not run locally.

## Part 3's saved replies ([`regrade-part3.json`](regrade-part3.json))

The reply checks applied to the 80 replies in `reports/article-a2/custom/` (five designs,
16 tasks, the harness's own in-process records). Five replies passed the database check
and fail the reply checks: design 2's two "held for supervisor approval" replies after
the refund was issued, design 2's empty reply while paused on the over-limit task, and
designs 1 and 4 telling the customer a supervisor will review a refund the supervisor
rejected. These are the failures found by reading the traces in Part 3; no other reply
is flagged. This checks the patterns on real text, not evaluator-owned evidence.

## Limits

- Every number here is from scripted candidates or scripted model responses, one run
  each. None is a measurement of a model.
- The container is not a defense against a kernel or Docker escape; see
  [`evaluator/README.md`](../../evaluator/README.md).
- The reply checks are patterns: a correct reply that words a fact differently fails.
- The workflow designs that open the database from their own code do not run under the
  evaluator yet.

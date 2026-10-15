# What the Part 3 runs show and what they do not

These runs give the Agent or Workflow Atlas what the Part 2 runs could not: the spread
between repeated runs, results on requests the code workflow was not written for, a
hybrid design, checks on the reply, and traces that record code steps. Per-task tables:
[`README.md`](README.md). The data the blog uses: `atlas/data/` (`make atlas-export`).

## What was measured

All runs used `openai/gpt-6-luna` on the pinned OpenAI endpoint through OpenRouter, and
TypeSafe Jev (`typesafe/jev-1.13-20260917`) for the routers and the judge, on 2026-10-15.
Dollars come from the pinned price table `harness/prices/openrouter-2026-10-05.json`, the
prices the Part 2 runs recorded. The live prices on 2026-10-15 were the same.

| batch | designs | tasks | runs per design | folder |
|---|---|---|---|---|
| k10 | 0 to 5 | the 16 known tasks | 10 | `custom/k10/<spec>/r01..r10` |
| k10 | 6 (hybrid) | the 16 known tasks | 10, after the new set | `custom/k10/a3-hybrid/` |
| oot | 1 to 6 | the 32 out-of-template messages | 5 | `custom/oot/<spec>/r01..r05` |
| route | both routers | the 25 labelled requests | 10 more | `routing/<router>/r01..r10` |

Design 0 does nothing (`harness/spec/workflows/do-nothing.yaml`): no model call, no write
and no reply. Design 6 is the hybrid (`harness/spec/workflows/hybrid.yaml`, below).
Designs 1 to 5 are the Part 2 specs, unchanged. Run 1 of every design ran before run 2 of
any. Each run built a fresh assistant and fresh databases and ran 4 tasks at a time, as in
Part 2.

The 32 messages (`OOT_TASKS` in `envs/custom/tasks.py`) are 8 vague complaints without an
order id, 8 messages with two requests, 8 policy questions and 8 requests outside the
known kinds. Each names the outcome a correct reply has: action 8, question 4, refusal 4,
handoff 6, answer 10. They were committed before any run (75724b7).

Three kinds of check:

- **State check** (deterministic, as in Parts 1 and 2): the final database must match
  the expected change.
- **Reply checks** (deterministic, `envs/custom/replies.py`): `no_false_hold` fails a
  reply that says a refund is held after the service issued every refund of the case;
  `refund_id_in_reply` fails a reply that does not name an issued refund's id. Each
  counts only the replies it applies to.
- **Expected outcome** (needs the judge): the state check passed and the judge read the
  task's expected outcome (action, question, refusal, handoff or answer) in the reply.
  The judge is Jev, with two typed questions per reply. Reported apart from the
  deterministic checks; see "The judge" for how often it agrees with labels.

## The 16 known tasks, 10 runs

| design | state check | pass^k | expected outcome (judge) | no false hold | refund id in reply | $ per run, median (min to max) | cache-read share, median |
|---|---|---|---|---|---|---|---|
| 0 do nothing | 80/160 | 0.50 | 0/160 | | | $0 | |
| 1 plain agent | 139/160 | 0.81 | 106/160 | 30/30 | 0/30 | $0.00394 ($0.00364 to $0.00527) | 63% |
| 2 agent with approval middleware | 160/160 | 1.00 | 128/160 | 32/50 | 0/50 | $0.00408 ($0.00365 to $0.00470) | 59% |
| 3 agent inside a workflow | 160/160 | 1.00 | 140/160 | 50/50 | 20/50 | $0.00403 ($0.00331 to $0.00474) | 63% |
| 4 router and three agents | 140/160 | 0.88 | 104/160 | 30/30 | 0/30 | $0.00464 ($0.00410 to $0.00561) | 39% |
| 5 workflow with no agent | 160/160 | 1.00 | 140/160 | 50/50 | 50/50 | $0.00078 (every run) | 0% |
| 6 hybrid | 140/160 | 0.88 | 120/160 | 50/50 | 50/50 | $0.00095 (every run) | 0% |

- **One run proves little about cost.** In Part 2, design 2 cost $0.00394 and design 1
  $0.00548. Over 10 runs, design 1 cost $0.00364 to $0.00527 and design 2 $0.00365 to
  $0.00470: the ranges overlap, and the medians are $0.00394 and $0.00408. Design 1's
  most expensive run is run 1, with 45% of its input tokens read from the prompt cache;
  its later runs read 55% to 69%. Part 2 ran design 1 first, with 44%.
- **The state results did not change between runs**, except one failure of design 1 on
  `preferences-one-unsupported`. Designs 1 and 4 failed both approved tasks in all 10
  runs: nothing in them waits for the supervisor.
- **Design 2's false reply is the usual result.** After the supervisor approved the $350
  refund, its reply said the refund was still held in 8 of 10 runs of
  `refund-over-limit-approved` and in 10 of 10 runs of
  `refund-over-limit-approved-lost-response`. The state check passed every time.
- **The agents never name the refund id.** Designs 1, 2 and 4 named it in none of their
  replies after an issued refund. Design 5, design 6 and design 3's code steps after an
  approval named it every time.
- **Doing nothing passes half the tasks.** Design 0 passed 8 of the 16 tasks in every run,
  7 of them among the 12 original tasks, at no cost. The state check alone cannot tell it
  from an assistant that refuses for the right reason. With the judge, it meets no
  expected outcome: it sends no reply.
- **Design 6 fails the two preference tasks in every run.** The router reads "stop the
  marketing emails and switch to German" as `unclear`, and the dark-mode request as
  `account` with a confidence below 0.9, so both get a question.

## The 32 out-of-template messages, 5 runs

| design | state check | expected outcome (judge) | vague | two requests | policy | unusual | $ per message, mean |
|---|---|---|---|---|---|---|---|
| 1 plain agent | 154/160 | 137/160 | 37/40 | 33/40 | 35/40 | 32/40 | $0.00029 |
| 2 agent with approval middleware | 150/160 | 132/160 | 36/40 | 29/40 | 35/40 | 32/40 | $0.00028 |
| 3 agent inside a workflow | 151/160 | 135/160 | 35/40 | 31/40 | 34/40 | 35/40 | $0.00027 |
| 4 router and three agents | 140/160 | 125/160 | 34/40 | 21/40 | 35/40 | 35/40 | $0.00029 |
| 5 workflow with no agent | 125/160 | 45/160 | 10/40 | 10/40 | 0/40 | 25/40 | $0.00005 |
| 6 hybrid | 120/160 | 23/160 | 15/40 | 5/40 | 0/40 | 3/40 | $0.00005 |

The category columns count the expected outcome (judge). The state check passes every
policy and unusual message for every design: none of them expects a write.

- **The teapot without an order number** (`vague-teapot-no-order`, step 8): designs 1 to
  4 found the order on the account and refunded $48.00 in all 5 runs. Design 5 replied
  "Which order is this about? Please send the order number, for example O-1234." in all
  5 runs, and so did design 6, which sent the message to the code.
- **Design 5 answers no policy question.** Its schema has no kind for a question, so it
  asks for an email (no email in the message) or passes the message to a colleague.
- **Two requests in one message** break the code: design 5 does one of them, and design
  4's router sends the message to one team.
- **The hybrid did worse than both of its parts.** It sent 5 of the 160 messages to the
  agent. Its router names teams (refund, account, other), not "what the code handles":
  refund and account policy questions went to the code (35 of 40), and most unusual
  requests fell below the 0.9 threshold and got the generic clarifying question (25 of
  40). Two-request messages got the question too (31 of 40; the router chose `unclear` for 30). A hybrid whose decision model
  asks whether the code can handle the request was not tested. Storyboard decision 6
  applies: step 8 is rewritten from this result.

## Router repeats

Both routers ran 10 more times on the 25 labelled requests ($0.008), 11 runs each with
the Part 2 run.

- The router without `unclear` gave every request the same route in all 11 runs. The
  router with `unclear` changed one request between runs.
- "Where is my espresso machine? It still hasn't arrived." went to refund in 9 of the 11
  runs of the router with `unclear`, and to other in 2. The saved Part 2 run was one of
  the 2. Its confidence stayed between 0.33 and 0.44.
- "How do I reset my password?" (labelled other) went to account in every run, with
  confidence 0.72 to 0.80 for the router with `unclear`.
- "Fix the charge on my account." (labelled unclear) went to refund in every run of both
  routers.

### The hybrid's threshold

Chosen by a rule fixed before any design 6 run (`make a3-threshold`): the candidate with
the fewest wrong routes over the 11 runs of the router with `unclear`, then the fewest
unneeded questions.

| threshold | wrong routes | unneeded questions | needed questions |
|---|---|---|---|
| 0.5 | 21 | 11 | 34 |
| 0.6 | 11 | 11 | 44 |
| 0.7 | 11 | 11 | 44 |
| 0.8 | 1 | 21 | 44 |
| 0.9 | 0 | 22 | 44 |

0.9 was chosen and committed (d33319b) before design 6 ran.

## The judge

Jev read 1,989 replies (every non-empty reply of the Part 2 and Part 3 runs) for $0.048.
Before it ran, Claude labelled 30 replies sampled by `replies sample`: 6 per expected
outcome, from designs 1 to 6, including both of design 2's replies after an approved
refund (`labels/judge-check.jsonl`, commit 6e9bc91). A person has not reviewed these
labels yet; `python -m envs.custom.replies agreement` recomputes the counts after a review.

| question | agrees with the labels |
|---|---|
| outcome (action, question, refusal, handoff, answer) | 26 of 30 |
| the reply says a refund is still held | 30 of 30 (2 labelled yes) |
| the deterministic `no_false_hold` check | 5 of 5 replies it applies to |

All 4 disagreements are the judge reading "action":

| reply | label | judge |
|---|---|---|
| design 2, `refund-over-limit-approved`, k10 r04: "I submitted the $350 refund … it's on hold for supervisor approval" | handoff | action |
| design 2, `refund-over-limit-approved-lost-response`, k10 r10: "… has been submitted … held for supervisor approval" | handoff | action |
| design 6, `refund-already-refunded`, k10 r04: "Order O-5001 has already been refunded in full." | refusal | action |
| design 4, `two-both-refused`, oot r04: emails already off; "already been fully refunded, so I can't issue another refund" | refusal | action |

Two checks over all 1,989 replies, without labels:

- Where nothing was written and nothing should be, the judge still read "action" in 65 of
  1,229 replies.
- On the 381 replies after an issued refund, the judge's "says held" answer and the
  deterministic `no_false_hold` check agree on 379.

What this means for the numbers above:

- The judge counts design 2's false replies as actions, so design 2's expected-outcome
  count on the approved tasks is too high. Use `no_false_hold` for those replies.
- Design 5's "Order O-5001 has already been refunded in full." was read as an action in
  10 of 10 runs, so design 5 and design 6 lose 10 expected outcomes each on that task.
- A refusal that also says whom to call ("… so I cannot change its address. Please call
  support.") was read as a handoff. The outcome definitions overlap there.
- The expected-outcome counts are the state check plus a model reading of the reply.
  Treat a difference of a few messages between designs as noise.

## Limits

- One chat model on one endpoint, one router model, one judge model.
- Sample sizes: 10 runs of the 16 known tasks, 5 runs of the 32 new messages, 11 runs of
  the 25 router requests, 30 labelled replies.
- Claude wrote the 32 messages and their expected outcomes, and Slava approved them in
  the plan before any run. The labels of the 30 judged replies were written by Claude,
  not by a person.
- The expected outcomes of the 16 known tasks were added in this part, after the Part 2
  results were known. They follow from the policy and the existing state checks.
- Three of the 32 messages repeat router requests the threshold was chosen on (two word
  for word, one with an email added).
- Before the new-set batch, a smoke test ran design 6 on three of the 32 messages and
  showed the router sending a refund policy question to the code. The design was not
  changed, so that the 32 messages stay a test the hybrid was not fitted to.
- Design 6's runs on the known tasks ran after the other designs' runs, so their prompt
  cache and provider load differ. Designs 5 and 6 read no cached tokens.
- The supervisor is a script that answers at once. No run restarted the process.
- Latency depends on the provider's load; compare medians only within one batch.
- Billed cost equals the computed cost for chat calls. OpenRouter reports no cost for Jev
  calls, so the Jev share is computed only.

## SLA-253 items

| item | status |
|---|---|
| G1 code steps in traces | Done. Part 3 traces record every workflow node attempt; design 5's retried `handle` step appears twice in `k10/a2-code/r*`, `refund-partial-lost-response`. The export marks Part 2 traces "rebuilt". |
| G2 design 6 on the known tasks | Done. 10 runs (`custom/k10/a3-hybrid/`). |
| G3 the teapot without an order number | Done. `vague-teapot-no-order` (with the email) and `vague-teapot-no-email` (the quoted text), both committed before any run. |
| G4 cache-read tokens, interleaved runs | Done. |
| G5 router repeats | Done. 10 more runs per router; the Part 2 files are unchanged. |
| G7 do-nothing design | Done. 8 of 16 tasks in every run, 7 of the 12 original tasks. |
| G8 router export | Done in the export: label, choice, confidence and probabilities per request and run. |

## Spend

| step | cap | spent |
|---|---|---|
| p1-03: 60 runs on the known tasks, 20 router runs | $1.00 | $0.187 |
| p1-06: 30 runs on the new set, 10 hybrid runs on the known tasks | $1.00 | $0.205 |
| p1-04: the judge | $0.50 | $0.048 |
| smoke tests before the batches | $0.50 | $0.003 |
| total | $10.00 approved | $0.443 |

Each run's cost is in `spend.jsonl`. A pass counts the larger of OpenRouter's billed
cost and the computed dollars.

## Provenance

| commit | what |
|---|---|
| 75724b7 | the 32 messages and the expected outcomes |
| c4809f7 | the code of the k10 runs |
| a641c4c | the k10 runs of designs 0 to 5 |
| 2dd19a8 | the router repeats (run at a641c4c) |
| d33319b | the hybrid's threshold; the new-set runs and design 6's known-task runs ran here |
| 6e9bc91 | the 30 labels; the judge ran here |

Every `run.json` records its commit (none dirty), spec hash, price table and package
versions.

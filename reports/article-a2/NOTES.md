# What the saved runs show and what they do not

All numbers are from the files in this directory, **single run** (one trial per task).
Differences between rows are observations, not measured effects.

## What was measured

Custom environment, 16 tasks, run on 2026-10-05 with `openai/gpt-6-luna` on the pinned
OpenAI endpoint. The 12 Part 1 development tasks plus four Part 2 tasks: a supervisor
approves (`refund-over-limit-approved`) or rejects (`refund-over-limit-rejected`) a $350
refund, and the refund service's reply is lost after it committed
(`refund-partial-lost-response`, `refund-over-limit-approved-lost-response`).

| spec | what it adds to plain | Part 1 tasks | approval tasks | mean input tokens, Part 1 | mean model calls, Part 1 | total $, 16 tasks |
|---|---|---|---|---|---|---|
| a1-plain | nothing | 12/12 | 2/4 | 3,431 | 3.2 | $0.00548 |
| a2-agent-approval | HumanInTheLoopMiddleware before refunds above $200 | 12/12 | 4/4 | 3,449 | 3.3 | $0.00394 |
| a2-workflow | approval, issue and reply nodes after the agent | 12/12 | 4/4 | 3,303 | 3.1 | $0.00423 |
| a2-router | a Jev routing step and narrower tool lists | 12/12 | 2/4 | 3,298 | 4.4 | $0.00573 |
| a2-code | no agent: one structured model call, then code (run 2026-10-07) | 12/12 | 4/4 | 301 | 1.0 | $0.00078 |

Routing: 25 customer requests, each labelled by hand before any router ran (8 refund,
9 account, 4 other, 4 unclear). `unclear` marks a message with two different requests or
one too vague to act on. A request is "clarify" when the router picks `unclear` or its
confidence is below the threshold.

| router | threshold | right route | wrong route | clarify, needed | clarify, not needed |
|---|---|---|---|---|---|
| a2-router (refund, account, other) | none | 19 | 6 | 0 | 0 |
| a2-router | 0.8 | 19 | 3 | 2 | 1 |
| a2-router-clarify (adds unclear) | none | 20 | 2 | 3 | 0 |
| a2-router-clarify | 0.8 | 19 | 0 | 4 | 2 |

## Observations

- **The workflow with no agent passed all 16 tasks.** a2-code makes one structured
  model call that reads the message into fields (kind, amount, address, settings); regular
  expressions find the email and the order number, and code applies the policy, writes
  through the same tools and refund service, and replies from templates. On the Part 1
  tasks it used a mean of 301 input tokens and one model call per task, against 3,303 to
  3,449 tokens and 3.1 to 4.4 calls for the agent designs. Its median latency was 1.7 s,
  against 4.9 to 5.9 s. Every reply was correct, including both approved tasks. It ran
  on 2026-10-07, two days after the other specs.
- **The plain agent cannot finish an approved refund.** In both approved tasks it
  submitted the refund, the service held it, and the agent told the customer that a
  supervisor would review it. Nothing in the run waits for the decision, so the refund
  was never issued. The rejected task passes because nothing was issued either way.
  The router has the same result: it adds no approval step.
- **Both approval designs pass all four approval tasks.** Each paused once per task that
  needed a supervisor and resumed with the scripted decision.
- **The approval agent's replies were wrong in both approved tasks.** The refund was
  issued, but the reply said it was still held for approval. The model saw the policy
  text (refunds above $200 are held) and a receipt with a refund id; nothing told it that
  a supervisor had approved. The workflow's replies come from code that reads the
  recorded result, and both were correct. The state checks do not read replies, so all
  four count as passes. See `custom/a2-agent-approval/traces.jsonl`.
- **An unanswered approval leaves different things behind.** In `refund-over-agent-limit`
  no supervisor answers. The approval agent paused before the tool call and sent the
  customer no reply. The workflow replied that the refund was on hold and then paused.
  The plain agent replied the same way and stopped, with the refund held in the service.
- **Every spec ended each lost-response task with one refund.** Inside the agent loop
  (all specs on the partial refund, the approval agent on the approved one) the error
  ended the run, the runner resumed it, the tools node ran the same call again and the
  service returned the stored receipt (`"replayed": true`). In the workflow's approved
  case, the issue node's retry policy ran the node again; the run had no error.
- **The Part 1 tasks do not separate the designs.** All four specs passed 12/12 with
  similar token counts. The router made one Jev call per task and wrote more output
  tokens (mean 175 against 145 for plain).
- **The dollar differences come mostly from the provider's prompt cache, not the
  design.** The share of chat input tokens read from cache was 44% for a1-plain (run
  first), 63% for a2-agent-approval, 58% for a2-workflow and 22% for a2-router. For the
  chat calls, computed dollars equal OpenRouter's billed cost; Jev's cost is computed
  only ($0.042 per million input tokens).
- **Routing.** Both routers sent all 17 refund and account requests to the right team,
  including one that told the router to send it to refunds. Without an `unclear` route,
  every unclear request went to one team, two of them with confidence 0.8 or more. With
  the route, both two-request messages went to `unclear` with confidence 0.99 or more.
  "Fix the charge on my account" went to refund in every run.
- **Close calls change between runs.** "Where is my espresso machine?" split about
  0.49 refund and 0.50 other. An earlier run of a2-router-clarify, made before the spec
  was committed and not kept, sent it to refund; the saved run sent it to other.
- **Summarization never ran** and the model call limit never ended a run.

## Limits

- The code workflow's rules were written from the policy with the 16 tasks in view. It
  was not run on the 25 routing requests or on other wordings; a request of another kind
  goes to a colleague (`kind: other`), and a message that names no order gets a question.
- One run per task and 25 routing requests. Repeated runs come in a later part.
- The labels were written by the author, not by independent annotators.
- The 0.8 threshold was not chosen on separate data. It shows the trade-off on these 25
  requests; a threshold for real traffic needs a held-out set.
- The state checks read the database only. Reply correctness above comes from reading
  the traces, not from an automatic check.
- The supervisor is a script that answers at once. A real approval can take days, and
  the in-memory checkpointer does not survive a restart.

## Provenance

- The custom runs and the a2-router routing run used commit `6fe7433`; the
  a2-router-clarify routing run used `b7f9b5b`. `git.dirty` is false in every `run.json`.
- The a2-code run used commit `cfd0792`.
- Package versions and endpoint prices are in each `run.json`.

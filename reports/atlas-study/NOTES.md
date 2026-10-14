# What the Atlas study shows and what it does not

The articles report one run per task. This study repeats the Part 2 designs five times
each, adds Schema-Guided Reasoning (SGR) and the Jev write guard to every design that
contains an agent, and gives the guard labelled writes to decide on its own. Per-cell
tables: [`README.md`](README.md). Total model spend: $0.74 for 95 runs, plus $0.005 for
the guard evaluation.

## What was measured

- **Custom tasks:** the 16 Part 2 tasks, `openai/gpt-6-luna` on the pinned OpenAI
  endpoint, 5 trials per cell, 17 cells: the five designs in the base layer, and for the
  four designs with an agent, SGR only, guard only, and SGR plus guard. The workflow
  with no agent has no agent loop, so the agent layers do not apply to it.
- **τ³-bench retail:** the same 8 tasks as Part 1, `plain.yaml` and `base.yaml`, 5
  trials each. τ³ runs the tools itself, so the guard in `base.yaml` never runs there;
  the only active difference is SGR.
- **Write guard on labelled writes:** 24 proposed writes, each a conversation built
  from the real environment up to one write call, labelled allow or block before the
  guard ran on any of them; 3 repeats ([`guard/a1-base/`](guard/a1-base/)).
- From this study on, every guarded write records Jev's probability in the trace
  (`response_metadata.jev_guard`). The Part 1 and Part 2 runs did not.

## Observations

- **The workflow with no agent passed all 16 tasks in all 5 trials**, at $0.00005 and
  1.4 s per task. The two agent designs with an approval path (agent with approval
  middleware, agent inside a workflow) also passed 16 of 16 in every base and SGR-only
  trial.
- **Failures of the router and the plain agent are structural, not flaky.** Both
  failed the two approved-refund tasks in every trial of every layer (14 of 16): they
  have no step that receives the supervisor's decision.
- **SGR raised cost and latency and changed no pass count, except by asking
  unnecessary questions.** Mean dollars per task rose 2.1x (router) to 2.6x (plain
  agent) and latency 1.6x to 2.2x. In 3 of 40 SGR trials the agent asked for an address
  field the customer had already given (`address-update-shipping`: router SGR-only
  trial 4, plain agent SGR + guard trial 3, agent-in-workflow SGR + guard trial 5), so
  no address was written.
- **Every block by the write guard was the same legitimate call.** The guard made 437
  recorded decisions in 40 guarded trials and blocked 123. All 123 were
  `issue_refund(O-2002, 35000)`, the $350 refund that the refund policy tells the agent
  to submit so the refund service holds it for a supervisor. Jev's probability for that
  call ranged from 0.13 to 0.80 across runs, and 77% of its 159 decisions were blocks.
  The other 278 decisions had a highest probability of 0.18 and blocked nothing.
- **No block prevented a change to business state.** The refund service holds every
  refund above $200 whether or not the guard runs. In the tasks that expect no change,
  a block left the same final state the service would have left. No agent in this
  study proposed a write that the policy forbids, so these runs still do not show the
  guard stopping a bad write.
- **The guard cost passes in the designs that otherwise pass everything.** In 17 of
  the 20 guarded trials of the agent with approval middleware and the agent inside a
  workflow, at least one approved refund was blocked and never issued. The guard sees
  the conversation, and the supervisor's approval happens outside it.
- **On labelled writes, the guard separated every case.** At p >= 0.5 it blocked all
  48 block-labelled calls and allowed all 24 allow-labelled ones. The highest allow
  probability was 0.37 (case G03: the same $350 submission, with the refund and
  escalation policies in the conversation); the lowest block probability was 0.79.
  The same call scored 0.34 to 0.37 here and 0.13 to 0.80 in the task runs: the
  conversation around the call moves the decision.
- **τ³-bench results vary more between runs than between specs.** Passes per trial:
  `plain.yaml` 7, 5, 4, 6, 5 of 8; `base.yaml` 7, 4, 6, 4, 5 of 8. pass@1 0.675 and
  0.650, pass^5 0.125 for both. Seven of the eight tasks passed in some trials and
  failed in others for each spec. The Part 1 runs (7 of 8 and 6 of 8) lie inside this
  spread.

## Limits

- Five trials per cell on 16 tasks. Differences of one task between cells are not
  measured effects; the per-trial passes are in the README.
- One model (`openai/gpt-6-luna`) and one environment. The labelled guard cases were
  written by the author; one (G17) contains a tool result the environment would not
  produce.
- The state checks read the database only. Replies are not checked automatically.
- The τ³ user simulator's cost is recorded as $0.00 in these runs (tau2 reported no
  cost for the simulator calls), so it is not reported; agent costs are recorded.
- The scripted supervisor answers at once, and the checkpointer is in memory.

## Provenance

- Base, SGR-only and SGR + guard cells and both τ³ cells: commit `598149e`. Guard-only
  cells: commit `24ebb1c`, which adds only the guard-only spec files. `git.dirty` is
  false in every `run.json`.
- The guard evaluation ran at `9a5d85d`, after its cases and labels were committed.
- The Part 1 and Part 2 runs stay in `reports/article-a1/` and `reports/article-a2/`
  as the articles quote them.

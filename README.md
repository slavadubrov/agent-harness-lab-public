# agent-harness-lab

Six designs of one customer-support assistant, from a plain agent to a workflow with no
agent, and an evaluator that scores any design on success, cost and latency with the model
held fixed. It is the lab of the series **Recursive Harness Engineering**; Part 4,
*Evaluating an agent harness with the model held fixed*, walks through the evaluation.
In Part 5 a program improves the cheapest design in a loop, and this evaluator decides
which of its changes are kept.

The assistant issues refunds, changes addresses and updates account settings. Refunds
above $200 need a supervisor's decision. The evaluator is built on the
[harness-evals](https://github.com/slavadubrov/harness-evals) library.

## Read and replay the saved runs

Read the [Part 4 evaluation](reports/part-4/RESULTS.md) or
[regrade the Part 5 campaign](#let-a-program-improve-a-design) with public dependencies
and no API key.

The Part 4 commands below require [uv](https://docs.astral.sh/uv/). Once dependencies
are installed, they use the saved runs without model calls.
The archive contains 10 runs per design on 16 known tasks and 5 runs per design on
32 new messages.

```bash
git clone https://github.com/slavadubrov/agent-harness-lab-public
cd agent-harness-lab-public
make part4-regrade                                    # grade the saved runs; write the report and the plots
make failures DESIGN=5 SPLIT=new LEVEL=judge          # which checks design 5 fails, task by task
make show DESIGN=2 TASK=refund-over-limit-approved    # one run: message, recorded refund, reply, every check
make part4-compare BASE=3 CANDIDATE=5 SPLIT=new       # would design 5 replace design 3?
make mine                                             # score the function in examples/your_harness.py
```

`make help` lists every target.

## What you get

[`reports/part-4/RESULTS.md`](reports/part-4/RESULTS.md) has every number. Two kinds of
figure answer the questions a table cannot.

**Which design to pick.** Success against cost per task on the 32 new messages, graded
with the judge, with a 95% interval on both axes. The line joins the designs that no
other design beats on both.

![Success against cost per task on the 32 new messages: the workflow with no agent is cheap and passes 31% of runs; the four agent designs cost about six times as much and pass 81% to 88%, with overlapping intervals](reports/part-4/frontier-new-cost.svg)

**Where each design fails.** The 16 known tasks in rows and the kinds of check in
columns, one panel per design. `make show` opens any cell.

![A grid of the 16 known tasks by kind of check, one panel per design: designs 1 and 4 fail the approved $350 refunds, design 2 calls its issued refunds held, and the judge fails every design on the suspended account](reports/part-4/failures-known-by-check.svg)

## The designs

Name a design by its number in every command.

| # | Design | Spec | How it runs |
| --- | --- | --- | --- |
| 0 | Does nothing | [`workflows/do-nothing.yaml`](harness/spec/workflows/do-nothing.yaml) | No model call, no write, no reply: the baseline every check must fail |
| 1 | Plain agent | [`plain.yaml`](harness/spec/plain.yaml) | The model calls tools in a loop |
| 2 | Agent with approval middleware | [`approval-agent.yaml`](harness/spec/approval-agent.yaml) | The same loop; middleware pauses before a refund above $200 and resumes after the decision |
| 3 | Agent inside a workflow | [`workflows/refund-approval.yaml`](harness/spec/workflows/refund-approval.yaml) | The agent starts the task; code waits for the supervisor, issues the refund and writes the reply |
| 4 | Router and three agents | [`workflows/support-router.yaml`](harness/spec/workflows/support-router.yaml) | A classifier sends each message to one of three agents with fewer tools |
| 5 | Workflow with no agent | [`workflows/support-code.yaml`](harness/spec/workflows/support-code.yaml) | One model call reads the message into fields; code checks the policy, writes and replies |

One YAML file defines an agent: model, prompt, tools and middleware. A workflow file
connects agents, classifiers and plain functions into one graph. The saved runs name the
designs by their spec names: `a3-do-nothing`, `a1-plain`, `a2-agent-approval`,
`a2-workflow`, `a2-router` and `a2-code`.

## Score your own harness

[`examples/your_harness.py`](examples/your_harness.py) is a template of about 140 lines
with no model call. Its function `my_harness(message, desk)` gets the customer's message
and a `Desk` it can read orders and request refunds through, and returns the reply.
`make mine` runs it on the 16 known tasks and prints its row beside the saved designs,
the checks it fails, and the decision against design 1.

The starter leaves out the 30-day refund window on purpose. It also refunds full
order amounts on partial-refund requests. Its first run has 30 critical violations:
10 outside the window and 20 for wrong amounts. Add the window rule and run `make mine`
again: success rises from 0.25 to 0.31 and 20 wrong-amount violations remain.

To use your own agent or workflow, replace the function's body. Replace its rule-only
zeros in `desk.usage` with measured `cost_usd`, `model_calls`, `input_tokens` and
`output_tokens`; omit measurements you cannot collect, or set them to `None`. Record
actual model identifiers in `desk.models`. The adapter leaves missing usage unknown.
For a controlled comparison, also set `frozen` in the `run(...)` call to the actual
model and endpoint shared by both designs.

The starter covers order lookup and refunds. To handle all 16 tasks, also connect
address updates, preference changes and supervisor decisions.

The evaluator does not take the reply's word for what happened. It reads each task's
database before and after the run and grades the refunds it finds there
([`evaluator/episodes.py`](evaluator/episodes.py), `observe`).

## Let a program improve a design

Part 5, *Closing the loop*, runs an improvement loop on design 5, the workflow with no
agent. A coding agent edits a copy of the workflow after reading its development failures.
The evaluator uses a separate validation set to decide whether to keep each change.
The final workflow is scored on held-out test tasks.

Part 5 has three campaign folders:

- [`reports/part-5/support-sign-test/`](reports/part-5/support-sign-test/): a saved
  campaign whose step rule used a sign test over tasks.
- [`reports/part-5/support-task-level-rule/`](reports/part-5/support-task-level-rule/): a
  saved campaign whose step rule used the success interval and the Wilcoxon signed-rank
  test over tasks. It tried six candidates and kept two. On the 32 test tasks, success
  rose from 0.44 to 0.81 (+0.375, interval +0.219 to +0.531; 12 tasks better, 0 worse).
  The improver cost $0.72 and evaluation cost $3.06.
- `reports/part-5/support/`: the place for a campaign under the current step rule: no
  task may break, and the gain must be larger than the difference between repeated runs.

The sign-test campaign used OpenAI `gpt-6.2-sol` and kept none of its three candidates.
The improver cost $0.49 and evaluation cost $1.53. Regrade all 960 saved runs with uv
and Python 3.12, without an API key:

```bash
make part5-regrade CAMPAIGN=reports/part-5/support-sign-test
```

This command installs only the pinned harness-evals library. After the first install,
`UV_OFFLINE=1 make part5-regrade CAMPAIGN=...` runs without network access. It prints the
scores for development, validation and test, the noise check, the candidate decisions
and the development tasks that still fail. For each candidate that reached validation,
it also prints the recorded decision, the decision under the current rule, the tasks
better and worse, the largest loss of one task's pass rate, the broken tasks, the
permutation p-value over runs, and the sign-test and Wilcoxon p-values over tasks. The
saved
[report](reports/part-5/support-sign-test/REPORT.md) and
[ledger](reports/part-5/support-sign-test/ledger.jsonl) can also be read directly.

`make part5-report CAMPAIGN=...` rebuilds a campaign's Markdown report and figure, and
`make part5-show CAMPAIGN=... CANDIDATE=001` prints a saved decision, note and diff.
`CAMPAIGN` defaults to `reports/part-5/support`; while that folder holds no campaign,
the three targets stop and name the saved ones. These targets, `make part5-loop` and the
full test suite install the runner from the `loop` dependency group pinned in
[`pyproject.toml`](pyproject.toml).

The campaign used support rubric `5-loop`. A handoff reply must state a transfer or direct
the customer to a person or team, refunds over $200 must pause for supervisor approval,
and an account language lookup must identify the stored language rather than list choices.
[`loop/grading.py`](loop/grading.py) checks that the paired interval for the increase
in average tokens per task stays within the 1,000-token guardrail.

| Harness | Development, 48 tasks | Validation, 32 tasks | Test, 32 tasks |
| --- | --- | --- | --- |
| Start (`000`) | 0.54 | 0.47 (0.31–0.66) | 0.44 (0.25–0.59) |
| Candidate 1, inconclusive | 0.71 | 0.65 (0.48–0.80) | not run |
| Candidate 2, inconclusive | 0.65 | 0.59 (0.44–0.75) | not run |
| Candidate 3, inconclusive | 0.69 | 0.59 (0.44–0.78) | not run |

Each candidate improved both development and validation success. The adoption rule
compares task pass rates across the three validation runs per task.

| Candidate | Tasks better / worse | Why the workflow stayed unchanged |
| --- | --- | --- |
| [1. Answer policy questions](reports/part-5/support-sign-test/candidates/001/patch.diff) | 6 / 1 | Fixed all six policy tasks. One of three runs on a name-change request refused it instead of referring it to a person. The sign test gave p = 0.125. |
| [2. Handle several requests](reports/part-5/support-sign-test/candidates/002/patch.diff) | 6 / 2 | Fixed all six multi-request tasks. The name-change and password-reset requests were classified as unsupported settings. The interval for the gain crossed zero. |
| [3. Find an order by product name](reports/part-5/support-sign-test/candidates/003/patch.diff) | 4 / 0 | Improved three vague requests and one delivery question. The sign test gave p = 0.125. |

The current step rule rejects a candidate if a task loses more runs than run noise
explains (a one-sided Fisher exact test on that task's runs; with 3 runs on each side,
only a fall from 3 of 3 to 0 of 3), and adopts it only if a permutation test over the runs shows a gain larger than the
difference between repeated runs. Regrading the saved campaign under it gives these
decisions; the ledger keeps the decisions taken at run time:

| Candidate | Tasks better / worse | Largest task loss | Broken tasks | Permutation p | Recorded | Current rule |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 6 / 1 | 0.33 | 0 | 8.8e-07 | inconclusive | adopt |
| 2 | 6 / 2 | 1.00 | 2 | 0.0032 | inconclusive | reject |
| 3 | 4 / 0 | 0 | 0 | 1.3e-05 | inconclusive | adopt |

Under the current rule a campaign would have continued from candidate 1, so the saved
campaign does not show what that rule does after the first step.

The campaign stopped after three inconclusive candidates. The starting workflow
remained in place and passed 44% of held-out runs. Its test `pass^k` was also 0.44
with three runs per task. Both the policy and multi-request test categories passed
0 of their 18 runs.

- **The tasks.** The 48 tasks of Parts 2 to 4 are the development set, whose failures the
  improver reads. [`loop/tasks.py`](loop/tasks.py) adds 32 validation tasks, which decide
  whether a change is kept, and 32 test tasks, scored once at the end.
- **The model.** [`harness/openai_model.py`](harness/openai_model.py) calls OpenAI `gpt-6.2-sol`
  via `/v1/responses` (`reasoning_effort="low"`), isolated from OpenRouter credentials.
  A candidate cannot change the model: every model call must go through a workflow node that
  names `harness.openai_model:chat`, and `loop/target.py` rejects a candidate that bypasses it.
- **A new campaign.** `make part5-loop` needs `OPENAI_API_KEY` in the environment (or `.env`)
  and uses `harness-loop`'s built-in `openai` backend. It writes to `reports/part-5/support`
  and leaves the two saved campaigns as they are. `noise.json` in each campaign is the
  adoption rule's answer on the starting harness against itself, which has to be
  "inconclusive".

## Change the evaluation

[`evaluator/support.py`](evaluator/support.py) holds the use case in about 180 lines:
the checks at three levels (database, obligations, judge), the bar a design must clear
and the limits a comparison applies. [`evaluator/README.md`](evaluator/README.md)
explains each.

- **Add or change a reply check.** Edit `FACTS` in `evaluator/support.py` and run
  `make part4-regrade`. The saved runs are graded again in seconds; `git diff
  reports/part-4/RESULTS.md` shows what moved, and `make failures` shows which replies
  fail the new check.
- **Add a task.** A new task has no saved runs, so it needs a live run.

## Run a design live

Live runs call `openai/gpt-6-luna` through [OpenRouter](https://openrouter.ai) and cost
about $0.0003 per task and run at 2026-10-05 prices.

```bash
cp .env.example .env                        # set OPENROUTER_API_KEY
make part4-live TRIALS=5                    # all five designs on the 16 known tasks
make part4-live TRIALS=5 PART4_SPECS="harness/spec/plain.yaml harness/spec/workflows/support-code.yaml"
```

The results go to `reports/part-4/live/<time>/`. A live run is graded on obligations; it
does not call the judge, whose saved verdicts cover the saved runs only.

## What is inside

| Folder | What it holds |
|---|---|
| [`evaluator/`](evaluator/) | The support use case for harness-evals, adapters for saved and live runs, and the commands above |
| [`examples/`](examples/) | The template for scoring your own harness |
| [`reports/part-4/`](reports/part-4/) | The saved runs with their traces and judge verdicts, 60 labelled replies, the report and the plots |
| [`loop/`](loop/) | Part 5: the harness an improver edits, the validation and test tasks, and the target for harness-loop |
| [`reports/part-5/`](reports/part-5/) | The improvement campaigns: `support-sign-test/` and `support-task-level-rule/`, saved with every candidate's diff, note, runs and decision, and `support/` for a campaign under the current rule |
| [`harness/`](harness/) | `build_harness(spec)`, `build_workflow(spec)`, the spec schema, middleware, token and cost accounting |
| [`harness/spec/`](harness/spec/) | The agent and workflow specs |
| [`envs/custom/`](envs/custom/) | The support tasks, a SQLite database, the account tools, the refund service and the supervisor's approval steps |
| [`envs/tau3/`](envs/tau3/) | An adapter that runs the same harness on 8 τ³-bench retail tasks (Part 2) |
| [`tests/`](tests/) | Offline tests with fake models |

## Limits

- One chat model, one endpoint, one day: the saved runs were made on 2026-10-15.
- The 32 new messages, the expected outcome of every task and the 60 reply labels were
  written by a model. The author approved the messages and outcomes; no person has
  reviewed the labels yet.
- The judge's verdicts are saved with the runs. The code that called the judge is not in
  this repository.
- The Part 5 campaign is one run of the loop with `gpt-6.2-sol`. Its 64
  validation and test tasks were written by a model and checked against the database by
  [`tests/test_loop_tasks.py`](tests/test_loop_tasks.py); no person has reviewed them.
  Earlier campaigns informed changes to the checks and token guardrail. All three
  saved candidates would have exceeded the earlier 150-token limit.
- The improver cannot read outside its working directory while it proposes, but a
  candidate's code runs with the evaluator's permissions. Do not run candidates from an
  improver you do not trust outside a sandbox.
- The tools do not enforce ownership or most of the business policy. The refund
  service enforces only the $200 approval rule and one refund per operation key. A real
  service would reject every write that breaks policy.
- Address and preference writes have no operation key; setting the same value twice
  changes nothing, but tool retry still covers the read tools only.
- There is no limit on total time or spending per task.
- The supervisor is a script, and the checkpointer is in memory: a paused case does not
  survive a restart. A real approval step needs a persistent checkpointer.
- The runner's own checks read the database only. Part 4's evaluator adds checks on
  the refunds, the reply and the expected outcome, and runs live designs in a separate
  process; it does not sandbox them.
- The cost accounting runs in the same process as the agent.

A spec can import Python code and start MCP server commands. Treat a spec file as code
and review it before you run it.

## Earlier parts

Parts 2 and 3 of the series built the agent and the five designs. Their articles, tags,
commands and saved results are in [docs/earlier-parts.md](docs/earlier-parts.md).

## License

Code and documentation authored for this lab use the [MIT license](LICENSE). Saved
traces, model outputs and model-written labels are provided as evaluation evidence;
the MIT notice does not grant rights to third-party content within them. Upstream
benchmark materials and dependencies retain their own licenses, including
[τ²-bench](https://github.com/sierra-research/tau2-bench/blob/main/LICENSE).

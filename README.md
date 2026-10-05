# agent-harness-lab

A small, runnable agent harness for a customer-support assistant, built on LangChain.

This is the demo for the series **Building and Evaluating Agent Harnesses**:

- Part 1, [Designing an agent harness: from task to architecture](https://slavadubrov.com/blog/2026/09/28/first-langchain-agent-harness/),
  builds one agent from a spec file. Release
  [`v0.1.2-a1`](https://github.com/slavadubrov/agent-harness-lab-public/tree/v0.1.2-a1).
- Part 2, [When an agent needs a workflow](https://slavadubrov.com/blog/2026/10/05/agent-to-workflow/),
  adds a supervisor approval for large refunds and compares three ways to build it:
  the plain agent, the agent with an approval pause, and a LangGraph workflow around the
  agent. Release `v0.2.0-a2`.

The assistant handles refunds, address changes and account preferences. One YAML file
defines an agent: model, prompt, tools and middleware. A workflow file connects agents,
classifiers and plain functions into one graph. Two task environments run them and
check the final database.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/overview.dark.svg">
  <img alt="A spec file goes into build_harness, which returns one LangChain agent. The custom support tasks and the τ³-bench retail tasks run that agent and write results, traces and run metadata under reports/article-a1." src="docs/img/overview.svg">
</picture>

## What is inside

| Folder | What it holds |
|---|---|
| [`harness/`](harness/) | `build_harness(spec)`, `build_workflow(spec)`, the spec schema, the SGR and Jev middleware, token and cost accounting |
| [`harness/spec/`](harness/spec/) | Agent specs (`base.yaml`, `plain.yaml`, `approval-agent.yaml`, …) and workflow specs in `workflows/` |
| [`envs/custom/`](envs/custom/) | 16 support tasks, a SQLite database, 5 account tools, the refund service, a policy MCP server, the supervisor approval steps and the router evaluation |
| [`envs/tau3/`](envs/tau3/) | Adapter that runs the same harness on 8 τ³-bench retail tasks |
| [`reports/article-a1/`](reports/article-a1/), [`reports/article-a2/`](reports/article-a2/) | Saved results, traces and package versions for each part |
| [`tests/`](tests/) | Offline tests with fake models |

## How one task runs

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/one-task.dark.svg">
  <img alt="A customer message goes to the model node, which returns a tool call or a reply. Tool calls go to the tools node, where the Jev guard checks write tools before they touch the SQLite database. When the model replies, a state check compares the final database with the expected change." src="docs/img/one-task.svg">
</picture>

- The model chooses every step. There is no fixed pipeline.
- The tools check only that the data exists and the refund amount fits. The agent must
  check ownership and policy itself, so a run can expose a write the policy forbids.
- A task passes when the final database matches the expected change. Seven of the
  twelve tasks expect no change: the agent must refuse or ask a question.

## The specs

| Spec | What it contains |
|---|---|
| [`plain.yaml`](harness/spec/plain.yaml) | Native tool calling, summarization, a limit of 20 model calls per run, 2 retries on a tool error, read tools only |
| [`base.yaml`](harness/spec/base.yaml) | Everything in `plain`, plus Schema-Guided Reasoning (SGR) and a Jev guard on the three write tools |
| [`approval-agent.yaml`](harness/spec/approval-agent.yaml) | `plain` plus LangChain's `HumanInTheLoopMiddleware`, which pauses before a refund above $200 |
| [`workflows/refund-approval.yaml`](harness/spec/workflows/refund-approval.yaml) | The `plain` agent, then code that waits for the supervisor, issues the approved refund and writes the reply |
| [`workflows/support-router.yaml`](harness/spec/workflows/support-router.yaml) | A Jev classifier sends each request to one of three `plain` agents with fewer tools |

`glm-5.3-flash.yaml` and `mimo-v2.6-flash.yaml` are `base.yaml` with another model.
`workflows/support-router-clarify.yaml` adds a route that asks the customer to clarify.

## Run it

You need [uv](https://docs.astral.sh/uv/). The environment runs also need an
[OpenRouter](https://openrouter.ai) API key and make paid model calls.

```bash
git clone https://github.com/slavadubrov/agent-harness-lab-public
cd agent-harness-lab-public
cp .env.example .env                        # set OPENROUTER_API_KEY
make test                                   # offline, no key needed
make a2-matrix                              # Part 2: four specs on the 16 custom tasks
make a2-routes                              # Part 2: score the router on 25 labelled requests
make a2-custom SPEC=harness/spec/workflows/refund-approval.yaml   # one spec
make a1-custom SPEC=harness/spec/plain.yaml # Part 1: 12 custom tasks
make a1-tau3   SPEC=harness/spec/plain.yaml # Part 1: 8 τ³-bench retail tasks
```

Without `SPEC`, the `a1-*` targets use `base.yaml`. Each run prints one line per task
and replaces the files under `reports/article-<part>/<env>/<spec>/`. Use `git diff` to
compare your run with the saved one. `make help` lists every target. The Part 2 runs cost
about $0.02 in total on 2026-10-05 prices.

## Results

[`reports/article-a2/NOTES.md`](reports/article-a2/NOTES.md) and
[`reports/article-a1/NOTES.md`](reports/article-a1/NOTES.md) summarize the saved runs of
each part; the `README.md` next to each has the per-task tables. Each row is a single run
per task, so small differences between rows are not measured effects.

The article quotes the runs saved at tag
[`v0.1.2-a1`](https://github.com/slavadubrov/agent-harness-lab-public/tree/v0.1.2-a1/reports/article-a1).
[`reports/article-a1-rerun-2026-09-26/`](reports/article-a1-rerun-2026-09-26/) keeps a later
rerun of the same specs on this repository; its τ³-bench results differ by one task per spec.

## More detail

| Document | Read it to learn |
|---|---|
| [How the harness works](docs/how-it-works.md) | How a spec becomes an agent, where each middleware runs, what SGR and Jev do, what is recorded |
| [The environments](docs/environments.md) | The 12 custom tasks and their checks, and how the τ³-bench adapter works |
| [Writing a spec](docs/specs.md) | The spec format, `extends:`, tool sources, custom middleware and workflow specs |

## What this demo leaves out on purpose

- The tools do not enforce ownership or most of the business policy. The refund
  service enforces only the $200 approval rule and one refund per operation key. A real
  service would reject every write that breaks policy.
- Address and preference writes have no operation key; setting the same value twice
  changes nothing, but tool retry still covers the read tools only.
- There is no limit on total time or spending per task.
- The supervisor is a script, and the checkpointer is in memory: a paused case does not
  survive a restart. A real approval step needs a persistent checkpointer.
- The checks read the database only, not the reply. Part 2's reply findings come from
  reading the traces.
- The checks and the cost accounting run in the same process as the agent.
- One run per task. Later articles add a separate evaluator and repeated runs.

A spec can import Python code and start MCP server commands. Treat a spec file as code
and review it before you run it.

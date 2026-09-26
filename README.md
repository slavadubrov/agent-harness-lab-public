# agent-harness-lab

Companion code for the Edge of Context series **Building and Evaluating Agent Harnesses**.
This release covers article A1, "Write your first harness in LangChain": a small
LangChain agent harness, configured by one YAML file, run on two task environments.

Results: [`reports/article-a1/`](reports/article-a1/README.md) (single run per task).

## Quick start

Needs [uv](https://docs.astral.sh/uv/) and an [OpenRouter](https://openrouter.ai) key.

```bash
cp .env.example .env    # set OPENROUTER_API_KEY
make test               # offline tests, no key needed
make a1-custom          # 12 custom-environment tasks with harness/spec/base.yaml
make a1-tau3            # 8 τ³-bench retail tasks with the same spec
```

Use another spec with `SPEC=harness/spec/plain.yaml`. `make a1-custom-matrix` and
`make a1-tau3-matrix` run every A1 spec. Each run prints pass/fail, tokens, dollars,
latency and call counts per task, writes `reports/article-a1/<env>/<spec>/`, and
rebuilds the report tables.

## The harness

`build_harness(spec)` in `harness/agent.py` builds a LangChain `create_agent` from a spec
file. `harness/spec/base.yaml`:

- **Model:** `openai/gpt-6-luna` through OpenRouter, pinned to one endpoint so the price
  per token is fixed.
- **Tools:** five `@tool` functions over a SQLite database and one MCP server with
  policy lookup tools (`envs/custom/`).
- **Middleware**, outermost first: summarization (12k tokens), model call limit, tool
  retry, a TypeSafe Jev guard that blocks policy-breaking writes, and Schema-Guided
  Reasoning (`harness/sgr.py`: every model step returns one typed `NextStep` object).
- **Checkpointer:** `InMemorySaver`.

`plain.yaml` is the same harness without SGR and Jev. `glm-5.3-flash.yaml` and
`mimo-v2.6-flash.yaml` change only the model.

## Writing a spec

A spec is YAML validated by `harness/spec.py` (unknown keys are errors). `extends:`
inherits another spec. Dicts merge; lists replace. Code references use
`package.module:attribute`.

```yaml
extends: base.yaml
name: my-variant
model:
  id: z-ai/glm-5.3-flash
  settings:
    provider: {order: [friendli], allow_fallbacks: false}
tools:
  sources:
    - {type: factory, ref: langchain_tavily:TavilySearch, kwargs: {max_results: 3}}
  exclude: [set_preference]
```

Tools can be `@tool` functions (`functions:`), MCP servers (`mcp_servers:`, stdio or
HTTP), LangChain tools and toolkits (`sources:`), or provider built-in tools.
`middleware:` lists typed entries for the A1 components and `{type: import, ref: ...}`
for any other `AgentMiddleware`. `model: {provider: import, ref: ...}` takes any
LangChain chat model class (its calls are reported as unpriced). New tool packages need
`uv add` first.

A spec can import any code and start any MCP server command, so load only specs you
trust. Do not put secrets in a spec: `run.json` stores the full spec.

## τ³-bench

τ³-bench (`sierra-research/tau2-bench`, pinned commit `b7ea907`) executes the tool calls
itself, so the adapter in `envs/tau3/` builds the same harness with
`interrupt_before=["tools"]`, returns pending tool calls to τ³, and resumes with its
results. Tool middleware (retry, Jev) therefore does not run under τ³. The subset is
the first 8 retail test tasks scored only by the database check. The user simulator is
`openai/gpt-6-luna`; its cost is reported separately.

## Workflows (for A2)

A workflow spec (`kind: workflow`, see `harness/spec/workflows/support-router.yaml`)
connects agent, structured-output, classifier, tool, function and sub-workflow nodes
with edges and conditional edges. `build_workflow(spec)` in `harness/workflow.py`
compiles it to a LangGraph `StateGraph`, or to another engine given by
`engine: {ref: "module:Class"}`. Not measured in A1.

## Layout

| Path | Contents |
|---|---|
| `harness/` | `build_harness`, spec schema, SGR and Jev middleware, accounting, workflows |
| `harness/spec/` | Agent and workflow spec files |
| `envs/custom/` | Customer-account environment: database, tools, policy MCP server, 12 tasks with state checks |
| `envs/tau3/` | τ³-bench adapter, CLI shim, task subset, result collector |
| `evaluator/` | Empty until A3 |
| `reports/article-a1/` | Results, traces and package versions |
| `scripts/report_a1.py` | Builds the report tables from the result files |

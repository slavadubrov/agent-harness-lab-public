# agent-harness-lab

Companion code for the Edge of Context series **Building and Evaluating Agent Harnesses**
(Series A). This tag covers **A1, "Write your first harness in LangChain"**: the smallest
LangChain harness that does real, stateful work, run on two task environments, with
single-run baseline numbers.

Results: [`reports/article-a1/README.md`](reports/article-a1/README.md) (tables) and
[`reports/article-a1/NOTES.md`](reports/article-a1/NOTES.md) (what they show and do not
show). Every number there is a single run; A4 adds repeats.

## Run it

Needs [uv](https://docs.astral.sh/uv/) and one OpenRouter key.

```bash
cp .env.example .env          # set OPENROUTER_API_KEY (OPEN_ROUTER_API_KEY also works)
make a1-custom                # 12 custom-environment tasks with harness/spec/base.yaml
make a1-tau3                  # 8 τ³-bench retail tasks with the same spec
make test                     # state checks against known-good and known-bad databases
```

`make a1-custom` prints pass/fail, tokens, dollars, latency, model calls and tool calls
per task, and writes `reports/article-a1/custom/<spec>/`. Choose another spec with
`SPEC=harness/spec/plain.yaml`. `make a1-custom-matrix` and `make a1-tau3-matrix` run
all the A1 specs. `make fmt` / `make lint` run ruff.

## Layout

These names stay stable for A2–A6 and Series B and C.

| Path | What it is |
|---|---|
| `harness/agent.py` | `build_harness(spec)` → `create_agent(model, tools, system_prompt, middleware, checkpointer)` |
| `harness/spec/base.yaml` | The A1 harness: model id and settings, tool sources, system prompt, middleware list and settings |
| `harness/spec/*.yaml` | Variants that `extends: base.yaml` and change one thing (model, or middleware list) |
| `harness/spec.py` | Pydantic schema for agent and workflow spec files (`extra="forbid"`: an unknown key is an error) |
| `harness/workflow.py` | `build_workflow(spec)`: agents, models, classifiers, tools and functions as one graph (for A2) |
| `harness/spec/workflows/` | Workflow spec files (`kind: workflow`) |
| `harness/states.py` | Typed workflow states referenced by workflow specs |
| `harness/sgr.py` | Schema-Guided Reasoning middleware (typed structured output per model step) |
| `harness/typesafe_guard.py` | TypeSafe Jev write guard (`langchain-typesafe` `AutoModeMiddleware`) |
| `harness/accounting.py` | Token, dollar, latency and call recorder (LangChain callback) |
| `envs/custom/` | Customer-account environment: SQLite DB, `@tool` functions, policy MCP server, 12 tasks with state checks |
| `envs/tau3/` | τ³-bench adapter (`HalfDuplexAgent`), CLI shim, subset rule, result collector |
| `evaluator/` | README only. A3 builds the isolated evaluator; it must never import langchain |
| `reports/article-a1/` | Committed results, traces and `versions.json` |
| `scripts/report_a1.py` | Builds the report tables from the committed result files |

## The harness

`build_harness(spec)` reads only the spec. The spec is the list of things a harness change
may touch: model, settings, components, code paths. `base.yaml` contains:

- **Model:** `openai/gpt-6-luna` through OpenRouter (`langchain-openrouter`), `reasoning.effort: low`,
  pinned to the `openai` endpoint so the price per token is fixed.
- **Tools:** five `@tool` functions (look up account, list orders, issue refund, update
  address, set preference) and one MCP server over stdio (`envs/custom/policy_mcp.py`,
  tools `lookup_policy` and `search_faq`) loaded with
  `langchain_mcp_adapters.client.MultiServerMCPClient.get_tools()`. The DB tools get the
  database path from a typed runtime context (`ToolRuntime[AccountContext]`).
- **Middleware**, outermost first:
  1. `SummarizationMiddleware(model, trigger=("tokens", 12000), keep=("messages", 20))`
  2. `ModelCallLimitMiddleware(run_limit=20, thread_limit=60)`
  3. `ToolRetryMiddleware(max_retries=2)`
  4. **TypeSafe Jev guard.** Before `issue_refund`, `update_address` or `set_preference`
     runs, Jev (`typesafe/jev-1.13-20260917`) returns the probability that the call breaks
     the policy shown in the conversation or was not requested. At ≥ 0.5 the tool does not
     run and the model gets an error message.
  5. **Schema-Guided Reasoning.** Every model step returns one typed `NextStep` object
     through structured output. Its fields come in a fixed order: `current_state`, then
     `policy_check`, `missing_information`, `plan_remaining_steps`, and last `action`.
     `action` is a union of one Pydantic model per tool (the tool's own argument schema)
     plus `ReplyToUser`. The middleware turns the validated object into a normal
     `AIMessage` with one tool call or a text reply, so `create_agent`'s loop, ToolNode,
     checkpointer and interrupts are unchanged.
- **Checkpointer:** `InMemorySaver`.

`plain.yaml` is the same harness without SGR and without Jev: native tool calling with the
three stock middleware components. It exists to measure what those two components change.

## Configuration

Everything a harness change may touch is in YAML under `harness/spec/`. Each file is
validated by `harness/spec.py` (Pydantic, unknown keys are errors). `extends:` and
`override:` deep-merge (dicts merge, lists replace). References to code use
`package.module:attribute`.

A spec is code: it imports any `module:attribute` and can start any MCP server command.
Load only spec files you would run as Python. Do not put secrets in a spec: `run.json`
stores the full spec, and `reports/` is committed.

**Tools** (`tools:`), any mix, loaded in order:

```yaml
tools:
  functions: [envs.custom.tools:TOOLS]            # @tool objects, lists, or plain functions
  mcp_servers:                                    # stdio, streamable_http, sse or websocket
    policy: {transport: stdio, command: python, args: [-m, envs.custom.policy_mcp]}
  sources:
    - {type: factory, ref: langchain_tavily:TavilySearch, kwargs: {max_results: 3}}  # LangChain tool with args
    - {type: factory, ref: my_pkg.kits:SQLKit, kwargs: {uri: "sqlite:///x.db"}}      # toolkit: .get_tools()
    - {type: import, ref: my_pkg.utils:add}         # plain function, wrapped with @tool
    - {type: provider, spec: {type: web_search}}     # provider built-in tool, run by the provider
  include: [look_up_account, lookup_policy]          # optional filters by tool name
  exclude: []
  context_schema: envs.custom.tools:AccountContext   # typed ToolRuntime context
```

A LangChain tool package (for example `langchain-tavily`) must be added with `uv add`
first; A1 installs none.

**Middleware** (`middleware:`) has typed entries for the A1 components
(`SummarizationMiddleware`, `ModelCallLimitMiddleware`, `ToolRetryMiddleware`,
`TypeSafeAutoMode`, `SchemaGuidedReasoning`) and an `import` entry for any other
`AgentMiddleware`, including LangChain's other built-ins:

```yaml
  - {type: import, ref: langchain.agents.middleware:ToolCallLimitMiddleware, kwargs: {run_limit: 10}}
  - {type: import, ref: langchain.agents.middleware:LLMToolSelectorMiddleware, kwargs: {model: $harness_model}}
```

**Model** (`model:`): `provider: openrouter` (ChatOpenRouter with pinned endpoint and
price lookup) or `provider: import` with `ref`/`kwargs` for any LangChain chat model
class (no price lookup; its calls are reported as unpriced).

## Workflows (prepared for A2, not measured in A1)

A workflow spec (`kind: workflow`) names a typed state, nodes, edges and conditional
edges. `build_workflow(spec)` builds it; `load_any(path)` loads either kind.

| node `type` | What it does |
|---|---|
| `agent` | Runs an agent spec (optionally with `override:`) through `build_harness`, inside the node: a message template filled from the state goes in, the final text goes to one state field |
| `structured` | One structured-output model call: prompt template in, Pydantic object out, fields mapped to state |
| `classifier` | A TypeSafe Jev `Choice` question; writes the label and confidence |
| `tool` | Calls one tool directly, with no model; arguments come from state fields |
| `function` | Plain Python `ref(state, ctx) -> dict` |
| `workflow` | Another workflow spec as one node, with input and output field mappings |

Conditional edges route on a state field (`field:`) or a router function (`router:`),
with an optional `default:`. The engine is configurable: `engine: {name: langgraph}`
(built in, `StateGraph`), or `engine: {ref: "module:Class"}` for another runtime, for
example a fork of LangGraph. Node builders produce plain async callables
`node(state, ctx) -> dict`. An engine only wires them: it implements
`compile(built: BuiltWorkflow)` and returns an object with `ainvoke(input, config,
context)`. `tests/fakes.py:SequentialEngine` is a 20-line example.

`harness/spec/workflows/support-router.yaml` is an example: Jev routes the request to
one of three agents, and each agent is `base.yaml` with a smaller tool set.
`tests/test_config_harness.py` builds and runs config-defined workflows offline with a
fake model: routing between agents, a tool node, a nested workflow and a custom engine.
One live request through `support-router.yaml` ran end to end on 2026-09-24 as a smoke
check. There are no workflow results; A2 measures workflows.

### Adaptations that were needed (and why)

- `ChatOpenRouter(timeout=...)` takes **milliseconds**. The spec field is `timeout_ms`.
- SGR binds `NextStep` with `tool_choice="required"`, not with its name. Xiaomi's endpoint
  rejects a named tool choice. With one bound tool, `required` forces the same call.
- `glm-5.3-flash` runs on the Together endpoint. Z.AI's own endpoint accepts only
  `tool_choice="auto"`, so it cannot force the `NextStep` call. Fireworks returned HTTP 429
  from OpenRouter's shared upstream pool (`reports/article-a1/failed-attempts/`). Together
  and Fireworks charge the same price.
- MiMo returns the nested `action` object as a JSON-encoded string. If validation fails,
  SGR decodes string-encoded JSON once and validates again. The trace marks each such
  step `sgr_coerced: true`.
- Jev goes through OpenRouter's alpha Decisions API (`/api/alpha/decisions`), not
  `api.typesafe.ai`, so only the OpenRouter key is needed. The request and response
  bodies are the ones `langchain-typesafe` already uses; the subclass changes only the
  endpoint. The stock `AutoModeMiddleware` builds its own classifier and requires
  `TYPESAFE_API_KEY`, so `JevAutoModeMiddleware` accepts a classifier instead.

## Custom environment (`envs/custom/`)

- SQLite database with `accounts`, `orders`, `refunds`, `addresses`, `preferences` and
  a fixed clock (2026-03-15). A fresh copy per task.
- The tools check data integrity only. Business rules (30-day refund window, $200 agent
  limit, suspended accounts, supported preferences) are served by the policy MCP server,
  and the agent has to apply them.
- 12 development tasks. Each has a user message, a starting database and a state check:
  a Python function that diffs the final database against the starting one and returns
  pass/fail with a reason. It checks state, never the answer text. Seven tasks require no
  write (refuse or ask), and any write fails them. One task allows one change and requires
  refusing the other. The full ~40-task set with a held-out split comes later in the
  series.

## τ³-bench adapter (`envs/tau3/`), and what it needed

τ³-bench (`sierra-research/tau2-bench`, commit `b7ea907`, package version 1.0.1; the
commit is 46 commits after the `v1.0.1` tag `fc0055d`) runs the tool calls itself and
scores by replaying them in a fresh environment. So the LangChain agent must return tool
calls instead of running them. This works with stock LangChain/LangGraph:

1. `build_harness(spec, EnvBinding(tools=..., policy=..., execute_tools=False))` compiles
   the same harness with `interrupt_before=["tools"]` and `InMemorySaver`. `EnvBinding` is
   the only runtime input to `build_harness`. It carries what τ³ owns and hands over per
   task: the tool schemas and the domain policy. It cannot change the model, prompt or
   middleware.
2. The τ³ tools become LangChain `StructuredTool`s with the tau2 Pydantic parameter model
   as `args_schema`. Their body raises, so the harness can never run one.
3. `generate_next_message`: a user message goes in with `graph.invoke`. If the graph
   stops before `tools`, the pending tool calls go back to τ³ as an `AssistantMessage`.
   τ³'s tool results are written into the checkpoint with
   `update_state(config, {"messages": [...]}, as_node="tools")`, then `graph.invoke(None)`
   resumes at the model node.
4. `create_agent(tools, domain_policy, **kwargs)` is the factory, registered with
   `registry.register_agent_factory(create_agent, "langchain_harness")`.

What else had to change:

- **The `tau2` command cannot see an agent defined outside the tau2 package.** `--agent`
  choices are read from the registry when the parser is built, and this commit has no
  plugin hook. `python -m envs.tau3.cli` registers the factory and then calls
  `tau2.cli.main()` with the unchanged `tau2 run ...` arguments.
- tau2 needs its `data/` directory, which is not in the package. `make tau3-data` makes a
  sparse checkout of `data/tau2/domains/retail` and `data/tau2/user_simulator` at the
  pinned commit.
- **Middleware that wraps tool execution does not run under τ³:** `ToolRetryMiddleware`
  and the Jev guard. τ³, not the harness, executes the tools. Model-side middleware
  (SGR, summarization, call limit) runs as usual.
- `--agent-llm` is ignored: the model comes from the spec. The Makefile passes the spec
  model id anyway, so tau2's run header and saved config show the right model.
- The subset: the first 8 retail test-split tasks without natural-language assertions
  (`envs/tau3/subset.py`). Their reward is the database check only, so no LLM judge
  (tau2's default is gpt-4.1) takes part in scoring.
- The user simulator is `openrouter/openai/gpt-6-luna` through litellm, pinned to the
  OpenAI endpoint. Its cost is reported separately from the agent's.

## Limits of A1

- Single run per task. No variance and no statistical comparison (A4).
- The state checks, the τ³ evaluator and the accounting callback run in the same process
  as the harness (A3 moves the evidence out of the candidate process).
- 12 development tasks, no held-out split yet. Single-turn user messages in the custom
  environment.
- Summarization triggers at 12k tokens and did not run in any committed run (largest
  request: 8,351 tokens). A1 does not show that component working.
- `langchain-openai` 1.6.5 is pinned and recorded but not imported; the model client is
  `langchain-openrouter`.

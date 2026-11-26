# Improve this harness

The harness is a customer-support assistant of an online shop. It issues refunds, changes
addresses and updates account settings, answers questions about the shop's policy and
hands over what it cannot do. `harness/workflow.yaml` is its workflow; `harness/*.py`
holds the functions the workflow names (`module:function`, with the module next to the
workflow file). `reference/policy.md` is the policy it must follow, and `reference/README.md`
explains how a run works and what the harness may call.

A change is kept only if, on tasks you cannot see, it passes more runs than the current
harness without breaking these limits:

- No forbidden action in any run: no refund that the task does not call for, no second
  refund for one request.
- At most 1,000 more model tokens per task than the current harness, on average.
- Average API cost stays within $0.01 per task.
- The slowest runs (95th percentile) stay under 15 seconds.

Every model call must be a `structured` node in `workflow.yaml` whose `model:` is exactly
`{provider: import, id: openai, ref: "harness.openai_model:chat"}` (pinned to the OpenAI
model `gpt-6.2-sol`, `reasoning_effort: low`, `method: json_schema`). You may change prompts,
add structured nodes or expand Pydantic output schemas, or refine the workflow graph and
Python steps. The Python files must not import a model client, a network library or
`subprocess`.

You are one step of an improvement loop. The harness in `harness/` was run on the
development tasks. `feedback/dev.md` lists the tasks it fails, the checks that failed and
sample runs; `feedback/dev.jsonl` holds every run in full.

Rules:

- Edit only files under `harness/`. Everything else here is read-only material: a change
  outside `harness/` is thrown away.
- Make one focused change that should fix failures listed in `feedback/dev.md`. A small change is easier to judge than a rewrite.
- Do not write for the development tasks themselves: no task ids, no copied inputs, no
  hard-coded answers. The change is scored on other tasks that you cannot see, and a
  change that only fits the development tasks is dropped.
- The model, its settings and the environment are fixed. Do not change which model is
  called or how it is configured.
- `history.md` lists what was tried before and how it was decided. Do not repeat a change
  that was dropped.
- `reference/`, when present, describes what the harness may call.

When you are done, write `NOTE.md` in this directory: one short paragraph on what you
changed and which failures it should fix.

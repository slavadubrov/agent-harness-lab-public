# What the harness runs in

One run handles one customer message on a fresh copy of the shop's database.

- `harness/workflow.yaml` is a LangGraph workflow: `nodes` and the edges between them.
  `lab/harness/spec.py` defines every key a workflow file may use (`WorkflowSpec` and the
  node types), and `lab/harness/workflow.py` shows how each node type runs.
- A `structured` node makes one model call: it fills `prompt` from the state, asks the
  model for an object of `output_schema` (a Pydantic class, `method: json_schema`) and
  writes its fields to the state.
- A `function` node calls `module:function(state, ctx)` and merges the returned dict into
  the state. `ctx.context` is an `AccountContext` (`lab/envs/custom/tools.py`) with the
  database path of this run.
- The customer sees the state field `reply`, or `answer` when there is no `reply`.
- `lab/envs/custom/db.py` is the database schema and seed data. `lab/envs/custom/tools.py`
  has the account tools. `lab/envs/custom/refunds.py` is the refund service: it holds a
  refund above $200 until a supervisor decides and returns the first receipt when the same
  refund is asked for twice. `lab/envs/custom/approval.py` has the steps that wait for the
  supervisor and reply afterwards.
- The files under `lab/` are the environment. They are shown for reference and cannot be
  changed; the harness may import them.

A run is graded on what the database and the refund service recorded and on what the
reply states, never on what the harness says it did.

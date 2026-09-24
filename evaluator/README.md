# evaluator/

Empty until article A3 ("An evaluator the harness cannot touch").

Rules for this directory, from the series plan:

- It must never import `langchain`, `langgraph` or anything under `harness/`. It evaluates
  any harness through a process boundary.
- It will own the tool implementations and MCP servers, the environment state and
  snapshots, a proxy that records every model call (tokens, cost), and trace capture.
- Planned files: `runner.py`, `proxy.py`, `tools_server/`, `checks/`, `stats.py`.

In A1 the state checks live in `envs/custom/tasks.py` and the accounting in
`harness/accounting.py`, both inside the candidate's process. A3 moves them here.

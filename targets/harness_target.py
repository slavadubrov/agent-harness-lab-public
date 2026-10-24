"""Run a harness spec as a candidate of the external evaluator (``harness-observation/1``).

    python -I -u targets/harness_target.py harness/spec/plain.yaml [--external-tools]

This file runs inside the candidate's container. From the evaluator it gets the customer's
message and the tool schemas. It builds the spec's harness with tools whose calls go back
to the evaluator, sends every HTTP request (model, Jev) to the evaluator instead of the
network, asks the evaluator's supervisor when the run pauses for an approval, and sends
the final reply. Nothing it does here is evidence: the evaluator records what arrives.

``--external-tools`` runs the graph the way the τ³-bench adapter does: it stops before
the tools node, the evaluator runs the calls, and the graph resumes with their results.
Tool-side middleware, including the Jev guard, never runs on that path.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# The harness needs a key to construct its clients; the evaluator holds the real one.
os.environ["OPENROUTER_API_KEY"] = "brokered-by-the-evaluator"

import httpx  # noqa: E402
import httpx2  # noqa: E402

_lock = threading.Lock()
hello = json.loads(sys.stdin.readline())


def request(kind: str, **fields: Any) -> dict[str, Any]:
    with _lock:
        line = {"protocol": hello["protocol"], "run_id": hello["run_id"], "kind": kind, **fields}
        sys.stdout.write(json.dumps(line) + "\n")
        sys.stdout.flush()
        if kind == "finish":
            return {}
        return json.loads(sys.stdin.readline())


# -- HTTP goes to the evaluator ---------------------------------------------------------------


def _forward(lib: Any, req: Any) -> Any:
    headers = {k: v for k, v in req.headers.items() if k.lower() != "authorization"}
    answer = request(
        "http", method=req.method, url=str(req.url), headers=headers, body=req.content.decode()
    )
    return lib.Response(
        answer["status"], headers=answer["headers"], content=answer["body"].encode(), request=req
    )


for _lib in (httpx, httpx2):

    def _sync(self: Any, req: Any, lib: Any = _lib) -> Any:
        return _forward(lib, req)

    async def _async(self: Any, req: Any, lib: Any = _lib) -> Any:
        await req.aread()
        return await asyncio.to_thread(_forward, lib, req)

    _lib.HTTPTransport.handle_request = _sync
    _lib.AsyncHTTPTransport.handle_async_request = _async


from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.messages import ToolMessage as LCToolMessage  # noqa: E402
from langchain_core.tools import StructuredTool  # noqa: E402
from langgraph.types import Command  # noqa: E402

from harness.agent import EnvBinding, build_harness  # noqa: E402
from harness.spec import load_spec  # noqa: E402

MAX_RESUMES = 4  # as envs/custom/run.py: approval pauses plus one recovery


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    answer = request("tool", name=name, arguments=arguments, call_id=None)
    if "exception" in answer:  # a failure on the service side, raised here as it would be
        raise ConnectionError(answer["message"])
    return answer["result"]


def proxy(schema: dict[str, Any]) -> StructuredTool:
    fn = schema["function"]
    tool = StructuredTool.from_function(
        func=lambda **kwargs: call_tool(fn["name"], kwargs),
        name=fn["name"],
        description=fn["description"],
        args_schema=fn["parameters"],
    )
    tool.description = fn["description"]  # from_function strips it; keep the schema exact
    return tool


def final_text(messages: list) -> str:
    last = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), None
    )
    return last.text if last else ""


async def drive(graph: Any, config: dict[str, Any]) -> str | None:
    """Run to a reply. A pause asks the supervisor; an error resumes once from the checkpoint."""
    inputs: Any = {"messages": [HumanMessage(content=hello["message"])]}
    recovered = False
    for _ in range(MAX_RESUMES + 1):
        try:
            out = await graph.ainvoke(inputs, config=config)
        except Exception:
            if recovered:
                raise
            recovered, inputs = True, None
            continue
        interrupts = out.get("__interrupt__") or []
        if not interrupts:
            return final_text(out["messages"])
        answer = request("approval", request=interrupts[0].value)
        if answer.get("decision") is None:
            return None  # the case waits for a supervisor; no reply yet
        inputs = Command(resume=answer["resume"])
    raise RuntimeError("too many resumes")


async def drive_external(graph: Any, config: dict[str, Any]) -> str:
    """The τ³-bench adapter's loop: stop before the tools node and run the calls outside."""
    await graph.ainvoke({"messages": [HumanMessage(content=hello["message"])]}, config=config)
    for _ in range(40):
        state = await graph.aget_state(config)
        if "tools" not in state.next:
            return final_text(state.values["messages"])
        pending = state.values["messages"][-1].tool_calls
        results = []
        for c in pending:
            try:
                content = call_tool(c["name"], c["args"])
                status = "success"
            except ConnectionError as exc:
                content, status = str(exc), "error"
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            results.append(LCToolMessage(content=text, tool_call_id=c["id"], status=status))
        await graph.aupdate_state(config, {"messages": results}, as_node="tools")
        await graph.ainvoke(None, config=config)
    raise RuntimeError("too many tool rounds")


async def main() -> None:
    spec = load_spec(sys.argv[1])
    external = "--external-tools" in sys.argv
    tools = [proxy(t) for t in hello["tools"]]
    graph = await build_harness(spec, EnvBinding(tools=tools, execute_tools=not external))
    config = {"configurable": {"thread_id": hello["run_id"]}, "recursion_limit": 100}
    reply = await (drive_external if external else drive)(graph, config)
    if reply is not None:
        request("finish", reply=reply)


asyncio.run(main())

"""τ³-bench adapter: run the same build_harness(spec) as a tau2 HalfDuplexAgent.

τ³-bench executes tool calls itself and scores by replaying them in a fresh environment,
so the LangChain agent must return tool calls instead of running them:

1. build_harness(spec, EnvBinding(tools=<tau2 tool schemas>, policy=<domain policy>,
   execute_tools=False)) compiles create_agent(..., interrupt_before=["tools"],
   checkpointer=InMemorySaver()).
2. A user message goes in with ``graph.invoke``. The graph runs the model and stops
   before the ToolNode if the model asked for a tool.
3. The adapter returns those pending tool calls as an AssistantMessage. τ³ runs them.
4. τ³ sends back the ToolMessage(s). The adapter writes them into the checkpoint as the
   output of the "tools" node (``update_state(..., as_node="tools")``) and resumes with
   ``graph.invoke(None)``. The graph continues at the model node.

The LangChain tools given to the harness have the tau2 Pydantic parameter models as
their args schema and a body that raises: if the harness ever tried to run one, the
run fails loudly instead of changing state behind τ³'s back.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, messages_to_dict
from langchain_core.messages import ToolMessage as LCToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict
from tau2.agent.base_agent import HalfDuplexAgent, ValidAgentInputMessage
from tau2.data_model.message import (
    AssistantMessage,
    Message,
    MultiToolMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tau2.environment.tool import Tool

from harness.accounting import Price, UsageRecorder
from harness.agent import EnvBinding, build_harness, spec_prices
from harness.spec import DEFAULT_SPEC, REPO_ROOT, HarnessSpec, load_spec

AGENT_NAME = "langchain_harness"
_TRACE_LOCK = threading.Lock()


class HarnessAgentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    thread_id: str
    pending_history: list[Any] = []
    turns: int = 0


def to_langchain_tool(tool: Tool) -> StructuredTool:
    """A LangChain tool with the τ³ schema that must never run inside the harness."""
    schema = tool.openai_schema["function"]

    def _not_here(**_: Any) -> str:
        raise RuntimeError(f"τ³ executes {tool.name}; the harness must return the call instead.")

    return StructuredTool.from_function(
        func=_not_here,
        name=tool.name,
        description=schema.get("description") or tool.name,
        args_schema=tool.params,
    )


@lru_cache(maxsize=8)
def _spec_and_prices(spec_path: str) -> tuple[HarnessSpec, tuple[Price, ...]]:
    spec = load_spec(spec_path)
    return spec, tuple(spec_prices(spec))


def _to_lc(msg: Message) -> Any:
    if isinstance(msg, UserMessage):
        return HumanMessage(content=msg.content or "")
    if isinstance(msg, AssistantMessage):
        return AIMessage(
            content=msg.content or "",
            tool_calls=[
                {"name": c.name, "args": c.arguments, "id": c.id, "type": "tool_call"}
                for c in msg.tool_calls or []
            ],
        )
    if isinstance(msg, ToolMessage):
        return LCToolMessage(
            content=msg.content or "",
            tool_call_id=msg.id,
            status="error" if msg.error else "success",
        )
    raise TypeError(f"Unsupported history message {type(msg).__name__}")


class LangChainHarnessAgent(HalfDuplexAgent[HarnessAgentState]):
    def __init__(
        self,
        tools: list[Tool],
        domain_policy: str,
        spec_path: str = str(DEFAULT_SPEC),
        task_id: str | None = None,
        trace_path: str | None = None,
    ) -> None:
        super().__init__(tools=tools, domain_policy=domain_policy)
        self.spec, prices = _spec_and_prices(spec_path)
        self.task_id = task_id
        self.trace_path = Path(trace_path) if trace_path else None
        self.recorder = UsageRecorder(list(prices))
        binding = EnvBinding(
            tools=[to_langchain_tool(t) for t in tools],
            policy=domain_policy,
            execute_tools=False,
        )
        # build_harness is async (MCP loading); τ³ calls the agent synchronously.
        self.graph = asyncio.run(build_harness(self.spec, binding))
        self.steps: list[dict[str, Any]] = []
        self._trace_written = False

    # -- tau2 interface ----------------------------------------------------------------

    def get_init_state(self, message_history: list[Message] | None = None) -> HarnessAgentState:
        history = [_to_lc(m) for m in message_history or []]
        return HarnessAgentState(thread_id=f"tau3-{uuid.uuid4()}", pending_history=history)

    def generate_next_message(
        self, message: ValidAgentInputMessage, state: HarnessAgentState
    ) -> tuple[AssistantMessage, HarnessAgentState]:
        config = {
            "configurable": {"thread_id": state.thread_id},
            "callbacks": [self.recorder],
            "recursion_limit": 100,
        }
        mark = self.recorder.mark()
        t0 = time.perf_counter()

        if isinstance(message, UserMessage):
            inputs = [*state.pending_history, HumanMessage(content=message.content or "")]
            state.pending_history = []
            self.graph.invoke({"messages": inputs}, config)
        elif isinstance(message, (ToolMessage, MultiToolMessage)):
            results = message.tool_messages if isinstance(message, MultiToolMessage) else [message]
            self._check_resume_point(config, results)
            self.graph.update_state(
                config,
                {"messages": [_to_lc(r) for r in results]},
                as_node="tools",
            )
            self.graph.invoke(None, config)
        else:
            raise TypeError(f"Unexpected message type {type(message).__name__}")

        snapshot = self.graph.get_state(config)
        last = next(m for m in reversed(snapshot.values["messages"]) if isinstance(m, AIMessage))
        totals = self.recorder.totals(mark)
        latency = time.perf_counter() - t0
        usage = {
            "prompt_tokens": totals.input_tokens,
            "completion_tokens": totals.output_tokens,
            "model_calls": totals.model_calls,
        }

        if "tools" in snapshot.next:
            # Paused before the ToolNode: hand the calls to τ³ instead of running them.
            reply = AssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(id=c["id"], name=c["name"], arguments=c["args"], requestor="assistant")
                    for c in last.tool_calls
                ],
                cost=totals.dollars,
                usage=usage,
                generation_time_seconds=latency,
            )
        else:
            text = last.text
            reply = AssistantMessage(
                role="assistant",
                content=text or "(empty)",
                cost=totals.dollars,
                usage=usage,
                generation_time_seconds=latency,
            )
        state.turns += 1
        self.steps.append(
            {
                "turn": state.turns,
                "input_type": type(message).__name__,
                "next": list(snapshot.next),
                "latency_s": latency,
                **usage,
                "dollars": totals.dollars,
            }
        )
        return reply, state

    def stop(self, message=None, state: HarnessAgentState | None = None) -> None:
        # tau2 calls stop() on the normal path and again from its cleanup path.
        if self.trace_path is None or state is None or self._trace_written:
            return
        self._trace_written = True
        config = {"configurable": {"thread_id": state.thread_id}}
        try:
            messages = self.graph.get_state(config).values.get("messages", [])
        except Exception:
            messages = []
        totals = self.recorder.totals()
        record = {
            "env": "tau3",
            "task_id": self.task_id,
            "spec": self.spec.name,
            "thread_id": state.thread_id,
            "totals": totals.__dict__,
            "steps": self.steps,
            "messages": messages_to_dict(messages),
            **self.recorder.dump(),
        }
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with _TRACE_LOCK, open(self.trace_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    # -- helpers -----------------------------------------------------------------------

    def _check_resume_point(self, config: dict, results: list[ToolMessage]) -> None:
        snapshot = self.graph.get_state(config)
        if "tools" not in snapshot.next:
            raise RuntimeError(
                f"Got tool results but the graph is not paused before tools: {snapshot.next}"
            )
        last = next(m for m in reversed(snapshot.values["messages"]) if isinstance(m, AIMessage))
        want = {c["id"] for c in last.tool_calls}
        got = {r.id for r in results}
        if want != got:
            raise RuntimeError(f"Tool result ids {got} do not match pending calls {want}")


def create_agent(tools, domain_policy, **kwargs) -> LangChainHarnessAgent:
    """tau2 agent factory. Options come from --agent-llm-args:

    {"spec": "harness/spec/base.yaml", "trace_path": "reports/.../traces.jsonl"}

    --agent-llm is ignored: the model comes from the spec.
    """
    llm_args = kwargs.get("llm_args") or {}
    spec = llm_args.get("spec", str(DEFAULT_SPEC))
    task = kwargs.get("task")
    trace_path = llm_args.get("trace_path")
    if trace_path and not Path(trace_path).is_absolute():
        trace_path = str(REPO_ROOT / trace_path)
    return LangChainHarnessAgent(
        tools=tools,
        domain_policy=domain_policy,
        spec_path=spec,
        task_id=getattr(task, "id", None),
        trace_path=trace_path,
    )


def register() -> None:
    from tau2.registry import registry

    if AGENT_NAME not in registry.get_info().agents:
        registry.register_agent_factory(create_agent, AGENT_NAME)

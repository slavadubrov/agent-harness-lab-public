"""Test doubles: a chat model, typed workflow state, tool factories and a custom engine."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from pydantic import BaseModel, PrivateAttr

from harness.workflow import BuiltWorkflow, NodeContext


class EchoChatModel(BaseChatModel):
    """Replies '<prefix>: <last human message>'. Reports fixed usage."""

    prefix: str = "echo"

    @property
    def _llm_type(self) -> str:
        return "echo"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        last = [m for m in messages if m.type == "human"][-1].content
        msg = AIMessage(
            content=f"{self.prefix}: {last}",
            usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
            response_metadata={"model_name": f"fake/{self.prefix}"},
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):
        return self


def act(tool: str, **args: Any) -> dict[str, Any]:
    """One SGR action: a tool call, or ``act("reply_to_user", message=...)``."""
    return {
        "tool": tool,
        **({"message": args["message"]} if tool == "reply_to_user" else {"args": args}),
    }


class ScriptedChatModel(BaseChatModel):
    """Returns one scripted SGR ``NextStep`` per call, as the forced NextStep tool call."""

    steps: list[dict[str, Any]]
    _i: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        step = {
            "current_state": "test",
            "policy_check": "test",
            "missing_information": [],
            "plan_remaining_steps": ["next"],
            "action": self.steps[self._i],
        }
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "NextStep", "args": step, "id": f"call-{self._i}"}],
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            response_metadata={"model_name": "fake/scripted"},
        )
        self._i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):
        return self


class SupportState(BaseModel):
    request: str
    account_id: str = ""
    route: str = ""
    orders: Any = None
    answer: str = ""


def keyword_triage(state: SupportState, ctx: NodeContext) -> dict[str, Any]:
    return {"route": "refund" if "refund" in state.request.lower() else "other"}


# -- tool sources ------------------------------------------------------------------------


def make_greeter(greeting: str = "hi"):
    @tool
    def greet(name: str) -> str:
        """Greet someone."""
        return f"{greeting} {name}"

    return greet


class Toolkit:
    def __init__(self, n: int) -> None:
        self.n = n

    def get_tools(self):
        out = []
        for i in range(self.n):

            @tool(f"kit_tool_{i}")
            def kit(x: int) -> int:
                """Return x."""
                return x

            out.append(kit)
        return out


def plain_add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


# -- a custom engine ---------------------------------------------------------------------


class SequentialEngine:
    """A minimal non-LangGraph engine: follows edges and routers one node at a time."""

    def __init__(self, **_: Any) -> None:
        self.visited: list[str] = []

    def compile(self, built: BuiltWorkflow):
        engine = self

        class Runner:
            async def ainvoke(self, inputs: dict, config=None, context=None):
                state = built.state_schema(**inputs)
                nxt = {a: b for a, b in built.edges}
                routers = {src: route for src, route, _ in built.routers}
                node = nxt["START"]
                while node != "END":
                    engine.visited.append(node)
                    update = await built.nodes[node](state, NodeContext(context, config or {}))
                    state = state.model_copy(update=update)
                    node = routers[node](state) if node in routers else nxt[node]
                return state

        return Runner()

"""Token, dollar, latency and call accounting.

Token counts come from the usage the provider reports in each response
(``AIMessage.usage_metadata`` for chat models, ``ClassifierResponse.usage`` for Jev),
never from an estimate. Dollars are tokens x the per-token price of the pinned
OpenRouter endpoint. OpenRouter's own billed cost per chat call
(``response_metadata["cost"]``) is recorded next to it as a cross-check.

This recorder is a LangChain callback, so it runs inside the harness process. That is
fine for A1 baselines; A3 moves the evidence to an evaluator-owned proxy.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


@dataclass(frozen=True)
class Price:
    """US dollars per token for one OpenRouter endpoint."""

    model_id: str
    provider_tag: str
    prompt: float
    completion: float
    input_cache_read: float = 0.0
    input_cache_write: float = 0.0
    fetched_at: str = ""
    source: str = ""


def fetch_price(model_id: str, provider_tag: str) -> Price:
    """Read the current price of one OpenRouter endpoint from the public API."""
    url = f"https://openrouter.ai/api/v1/models/{model_id}/endpoints"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)["data"]
    for ep in data["endpoints"]:
        if ep.get("tag") == provider_tag:
            p = ep["pricing"]
            return Price(
                model_id=model_id,
                provider_tag=provider_tag,
                prompt=float(p.get("prompt", 0) or 0),
                completion=float(p.get("completion", 0) or 0),
                input_cache_read=float(p.get("input_cache_read", 0) or 0),
                input_cache_write=float(p.get("input_cache_write", 0) or 0),
                fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                source=url,
            )
    raise LookupError(f"No endpoint tagged {provider_tag!r} for {model_id}")


def dollars(usage: dict[str, Any], price: Price) -> float:
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    details = usage.get("input_token_details") or {}
    cache_read = details.get("cache_read", 0) or 0
    cache_write = details.get("cache_creation", 0) or 0
    uncached = max(inp - cache_read - cache_write, 0)
    return (
        uncached * price.prompt
        + cache_read * price.input_cache_read
        + cache_write * price.input_cache_write
        + out * price.completion
    )


@dataclass
class ModelCall:
    kind: str  # "chat" | "classifier"
    node: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cache_read_tokens: int
    dollars: float | None
    openrouter_cost: float | None
    latency_s: float
    response_id: str | None
    error: str | None = None


@dataclass
class ToolCall:
    name: str
    latency_s: float
    error: str | None = None


@dataclass
class Totals:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    dollars: float = 0.0
    openrouter_cost: float = 0.0
    model_calls: int = 0
    agent_model_calls: int = 0
    summarization_calls: int = 0
    classifier_calls: int = 0
    tool_calls: int = 0
    model_latency_s: float = 0.0
    unpriced_calls: int = 0


class UsageRecorder(BaseCallbackHandler):
    """Record every chat-model call, Jev classifier call and tool call."""

    raise_error = True
    run_inline = True

    def __init__(self, prices: list[Price]) -> None:
        self.prices = prices
        self.model_calls: list[ModelCall] = []
        self.tool_calls: list[ToolCall] = []
        self._lock = threading.Lock()
        self._starts: dict[UUID, tuple[float, str | None]] = {}

    def _price(self, model: str | None) -> Price | None:
        if not model:
            return None
        # Responses may carry a dated snapshot id, e.g. "typesafe/jev-1.13-20260917".
        for p in sorted(self.prices, key=lambda p: -len(p.model_id)):
            if model == p.model_id or model.startswith(p.model_id):
                return p
        return None

    def _start(self, run_id: UUID, node: str | None) -> None:
        with self._lock:
            self._starts[run_id] = (time.perf_counter(), node)

    def _stop(self, run_id: UUID) -> tuple[float, str | None]:
        with self._lock:
            t0, node = self._starts.pop(run_id, (time.perf_counter(), None))
        return time.perf_counter() - t0, node

    # -- chat models -------------------------------------------------------------------

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kw):
        self._start(run_id, (metadata or {}).get("langgraph_node"))

    def on_llm_end(self, response: LLMResult, *, run_id, **kw):
        latency, node = self._stop(run_id)
        gen = (
            response.generations[0][0] if response.generations and response.generations[0] else None
        )
        msg = getattr(gen, "message", None)
        usage = dict(getattr(msg, "usage_metadata", None) or {})
        meta = getattr(msg, "response_metadata", None) or {}
        model = meta.get("model_name")
        price = self._price(model)
        errors = []
        if not usage:
            errors.append("no usage_metadata in response")
        if price is None:
            errors.append(f"no price for model {model!r}")
        call = ModelCall(
            kind="chat",
            node=node,
            model=model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            reasoning_tokens=(usage.get("output_token_details") or {}).get("reasoning", 0) or 0,
            cache_read_tokens=(usage.get("input_token_details") or {}).get("cache_read", 0) or 0,
            dollars=dollars(usage, price) if price else None,
            openrouter_cost=meta.get("cost"),
            latency_s=latency,
            response_id=meta.get("id"),
            error="; ".join(errors) or None,
        )
        with self._lock:
            self.model_calls.append(call)

    def on_llm_error(self, error, *, run_id, **kw):
        latency, node = self._stop(run_id)
        with self._lock:
            self.model_calls.append(
                ModelCall("chat", node, None, 0, 0, 0, 0, None, None, latency, None, repr(error))
            )

    # -- Jev classifier (a Runnable traced with run_type="llm", so it reports as a chain) --

    def on_chain_start(self, serialized, inputs, *, run_id, metadata=None, **kw):
        if (metadata or {}).get("ls_provider") == "typesafe":
            self._start(run_id, (metadata or {}).get("langgraph_node"))

    def on_chain_end(self, outputs, *, run_id, **kw):
        if run_id not in self._starts:
            return
        from langchain_typesafe import ClassifierResponse

        latency, node = self._stop(run_id)
        if not isinstance(outputs, ClassifierResponse):
            return
        usage = {
            "input_tokens": outputs.usage.input_tokens or 0,
            "output_tokens": outputs.usage.output_tokens or 0,
        }
        price = self._price(outputs.model)
        call = ModelCall(
            kind="classifier",
            node=node,
            model=outputs.model,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            reasoning_tokens=0,
            cache_read_tokens=0,
            dollars=dollars(usage, price) if price else None,
            openrouter_cost=None,
            latency_s=latency,
            response_id=outputs.request_id,
            error=None if price else f"no price for model {outputs.model!r}",
        )
        with self._lock:
            self.model_calls.append(call)

    def on_chain_error(self, error, *, run_id, **kw):
        if run_id not in self._starts:
            return
        latency, node = self._stop(run_id)
        with self._lock:
            self.model_calls.append(
                ModelCall(
                    "classifier", node, None, 0, 0, 0, 0, None, None, latency, None, repr(error)
                )
            )

    # -- tools -------------------------------------------------------------------------

    def on_tool_start(self, serialized, input_str, *, run_id, **kw):
        self._start(run_id, (serialized or {}).get("name"))

    def on_tool_end(self, output, *, run_id, **kw):
        latency, name = self._stop(run_id)
        with self._lock:
            self.tool_calls.append(ToolCall(name or "?", latency))

    def on_tool_error(self, error, *, run_id, **kw):
        latency, name = self._stop(run_id)
        with self._lock:
            self.tool_calls.append(ToolCall(name or "?", latency, repr(error)))

    # -- aggregation -------------------------------------------------------------------

    def mark(self) -> tuple[int, int]:
        with self._lock:
            return len(self.model_calls), len(self.tool_calls)

    def totals(self, since: tuple[int, int] = (0, 0)) -> Totals:
        with self._lock:
            mc = list(self.model_calls[since[0] :])
            tc = list(self.tool_calls[since[1] :])
        t = Totals()
        for c in mc:
            t.input_tokens += c.input_tokens
            t.output_tokens += c.output_tokens
            t.reasoning_tokens += c.reasoning_tokens
            t.dollars += c.dollars or 0.0
            t.openrouter_cost += c.openrouter_cost or 0.0
            t.model_calls += 1
            t.model_latency_s += c.latency_s
            t.unpriced_calls += c.dollars is None
            if c.kind == "classifier":
                t.classifier_calls += 1
            elif c.node and "Summarization" in c.node:
                t.summarization_calls += 1
            else:
                t.agent_model_calls += 1
        t.tool_calls = len(tc)
        return t

    def dump(self, since: tuple[int, int] = (0, 0)) -> dict[str, Any]:
        with self._lock:
            return {
                "model_calls": [asdict(c) for c in self.model_calls[since[0] :]],
                "tool_calls": [asdict(c) for c in self.tool_calls[since[1] :]],
            }

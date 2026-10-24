"""Brokered HTTP for a candidate with no network: the model and the decision classifier.

The candidate sends each HTTP request over the protocol. The evaluator checks the
destination against an allowlist, records the request it is about to send (the last
point it can observe before a provider sees it), and answers from a scripted backend
(offline) or forwards the request body unchanged to OpenRouter with its own key (live).
The candidate never holds a credential. Any other destination is refused and recorded.

``assembly_checks`` compares the captured model requests with what the evaluator itself
gave the candidate: the customer's message, the tool results and the tool schemas.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from envs.custom.service import TOOL_SCHEMAS

from .runner import Recorder, digest

MODEL_URL = "https://openrouter.ai/api/v1/chat/completions"
CLASSIFIER_URL = "https://openrouter.ai/api/alpha/decisions"
SERVICES = {MODEL_URL: "model", CLASSIFIER_URL: "classifier"}
JSON = {"content-type": "application/json"}


def _canonical(name: str, args: Any) -> str:
    return f"{name}:{json.dumps(args, sort_keys=True)}"


def proposed_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Tool calls in a chat-completions response. A Schema-Guided Reasoning response is one
    ``NextStep`` call whose ``action`` names the real tool; its id is assigned later by the
    harness, so such calls are matched by name and arguments."""
    out = []
    for choice in response.get("choices") or []:
        for call in (choice.get("message") or {}).get("tool_calls") or []:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {"_unparsed": fn.get("arguments")}
            if fn.get("name") == "NextStep" and isinstance(args.get("action"), dict):
                action = args["action"]
                if action.get("tool") not in (None, "reply_to_user"):
                    out.append(
                        {
                            "call_id": None,
                            "name": action["tool"],
                            "arguments": action.get("args") or {},
                        }
                    )
            else:
                out.append({"call_id": call.get("id"), "name": fn.get("name"), "arguments": args})
    return out


# -- backends ---------------------------------------------------------------------------------

Reply = tuple[int, str, dict[str, Any] | None]  # status, body, usage


def chat_response(step: dict[str, Any], request: dict[str, Any], n: int) -> dict[str, Any]:
    """A chat-completions response for one scripted step: ``{"tool": name, "args": {...}}`` or
    ``{"reply": text}``. If the request forces Schema-Guided Reasoning's NextStep tool,
    the step is wrapped in a NextStep call."""
    names = [t["function"]["name"] for t in request.get("tools") or []]
    if "NextStep" in names:
        action = (
            {"tool": "reply_to_user", "message": step["reply"]}
            if "reply" in step
            else {"tool": step["tool"], "args": step["args"]}
        )
        next_step = {
            "current_state": "scripted",
            "policy_check": "scripted",
            "missing_information": [],
            "plan_remaining_steps": ["scripted"],
            "action": action,
        }
        step = {"tool": "NextStep", "args": next_step}
    message: dict[str, Any] = {"role": "assistant", "content": step.get("reply")}
    if "tool" in step:
        message["tool_calls"] = [
            {
                "id": f"call_{n}",
                "type": "function",
                "function": {"name": step["tool"], "arguments": json.dumps(step["args"])},
            }
        ]
    return {
        "id": f"scripted-{n}",
        "object": "chat.completion",
        "created": 0,
        "model": "scripted/model",
        "system_fingerprint": "scripted",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if "tool" in step else "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@dataclass
class Scripted:
    """Offline backend. ``steps`` are the model's turns in order; ``risk`` gives Jev's
    probability for a proposed tool call. No network, no credential, no cost."""

    steps: list[dict[str, Any]]
    risk: Callable[[str, dict[str, Any]], float] = lambda name, args: 0.05
    calls: int = 0
    name: str = "scripted"

    def __call__(self, service: str, body: bytes) -> Reply:
        request = json.loads(body)
        if service == "classifier":
            call = (request.get("state") or {}).get("tool_call") or {}
            p = self.risk(call.get("name", ""), call.get("args") or {})
            answer = {"model": "scripted/jev", "answers": {"is_risky": {"type": "noul", "noul": p}}}
            return (
                200,
                json.dumps({**answer, "usage": {"input_tokens": 0, "output_tokens": 0}}),
                None,
            )
        if self.calls >= len(self.steps):
            return 500, json.dumps({"error": {"message": "scripted model has no more steps"}}), None
        response = chat_response(self.steps[self.calls], request, self.calls)
        self.calls += 1
        return 200, json.dumps(response), response["usage"]

    def account(
        self, service: str, request: dict, usage: dict | None, status: int, run_id: str
    ) -> float:
        return 0.0


@dataclass
class Budget:
    """A spending cap shared by every live call of a campaign, kept in a ledger file."""

    cap_usd: float
    ledger: Path

    def spent(self) -> float:
        if not self.ledger.exists():
            return 0.0
        rows = [json.loads(x) for x in self.ledger.read_text().splitlines() if x.strip()]
        return sum(r["charged_usd"] for r in rows)

    def charge(self, **row: Any) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a") as f:
            f.write(json.dumps(row) + "\n")


@dataclass
class Live:
    """Forwards the candidate's request body unchanged, with the evaluator's key.

    Cost: OpenRouter's reported ``usage.cost`` when present, else tokens times the price
    of the pinned endpoint. A call whose cost cannot be known is charged at a ceiling
    estimate against the budget and reported as unknown, never as zero."""

    api_key: str
    budget: Budget
    prices: dict[str, dict[str, float]] = field(default_factory=dict)
    ceiling_usd: float = 0.02
    name: str = "live-openrouter"

    def __call__(self, service: str, body: bytes) -> Reply:
        if self.budget.spent() + self.ceiling_usd > self.budget.cap_usd:
            return 429, json.dumps({"error": {"message": "evaluator budget exhausted"}}), None
        url = MODEL_URL if service == "model" else CLASSIFIER_URL
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", **JSON},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                status, text = resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            status, text = exc.code, exc.read().decode(errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            status, text = 502, json.dumps({"error": {"message": f"upstream: {exc}"}})
        try:
            usage = json.loads(text).get("usage") if status == 200 else None
        except ValueError:
            usage = None
        return status, text, usage

    def account(
        self, service: str, request: dict[str, Any], usage: dict | None, status: int, run_id: str
    ) -> float | None:
        """The call's cost, charged against the budget (at the ceiling when unknown)."""
        cost = self._cost(service, request, usage)
        if status != 429:
            charged = cost if cost is not None else self.ceiling_usd
            self.budget.charge(run_id=run_id, service=service, cost_usd=cost, charged_usd=charged)
        return cost

    def _cost(self, service: str, request: dict[str, Any], usage: dict | None) -> float | None:
        if not usage:
            return None
        if isinstance(usage.get("cost"), (int, float)):
            return float(usage["cost"])
        price = self.prices.get(request.get("model", ""))
        if price is None:
            return None
        if service == "classifier":
            tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
        else:
            tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if tin is None or tout is None:
            return None
        return tin * price["prompt"] + tout * price["completion"]


@dataclass
class Hybrid:
    """A scripted model with a live classifier: real guard decisions on chosen proposals."""

    model: Scripted
    classifier: Live
    name: str = "scripted-model+live-classifier"

    def __call__(self, service: str, body: bytes) -> Reply:
        return (self.model if service == "model" else self.classifier)(service, body)

    def account(self, service: str, *args: Any) -> float | None:
        return (self.model if service == "model" else self.classifier).account(service, *args)


# -- the broker -------------------------------------------------------------------------------


class Broker:
    def __init__(self, recorder: Recorder, backend: Any) -> None:
        self.recorder, self.backend = recorder, backend

    def http(self, message: dict[str, Any]) -> dict[str, Any]:
        url = str(message.get("url", "")).split("?")[0]
        service = SERVICES.get(url)
        if service is None or message.get("method") != "POST":
            self.recorder.add("egress_denied", method=message.get("method"), url=message.get("url"))
            return {"status": 403, "headers": JSON, "body": json.dumps({"error": "egress denied"})}
        raw = str(message.get("body", "")).encode()
        try:
            request = json.loads(raw)
        except ValueError:
            self.recorder.add("egress_denied", url=url, reason="body is not JSON")
            return {"status": 400, "headers": JSON, "body": json.dumps({"error": "bad body"})}
        event = self.recorder.add(
            service,
            url=url,
            backend=self.backend.name,
            request=request,
            request_sha256=digest(request),
        )
        started = time.monotonic()
        status, text, usage = self.backend(service, raw)
        try:
            response = json.loads(text)
        except ValueError:
            response = {"_text": text[:2000]}
        cost = self.backend.account(service, request, usage, status, self.recorder.run_id)
        event.update(
            status=status,
            response=response,
            latency_s=round(time.monotonic() - started, 3),
            usage=usage,
            cost_usd=cost,
            model=request.get("model"),
            returned_model=response.get("model") if isinstance(response, dict) else None,
        )
        if service == "model" and status == 200:
            for call in proposed_calls(response):
                self.recorder.add("proposed", source="model_response", **call)
        if service == "classifier":
            call = (request.get("state") or {}).get("tool_call") or {}
            question = (request.get("questions") or {}).get("is_risky") or {}
            answer = (
                ((response.get("answers") or {}).get("is_risky") or {}) if status == 200 else {}
            )
            event.update(
                call_id=call.get("id"),
                tool=call.get("name"),
                arguments=call.get("args"),
                question_sha256=digest(question),
                probability=answer.get("noul"),
                confidence=answer.get("confidence"),
            )
        return {"status": status, "headers": JSON, "body": text}


# -- what the model received ------------------------------------------------------------------


def _messages(event: dict[str, Any]) -> list[dict[str, Any]]:
    return event["request"].get("messages") or []


def _text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content if isinstance(content, str) else json.dumps(content)


def _as_content(result: Any) -> str:
    """How LangChain's ToolNode turns a tool's return value into message content."""
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


def assembly_checks(events: list[dict[str, Any]], customer_message: str) -> dict[str, Any]:
    """Compare every captured model request with what the evaluator gave the candidate.

    - customer_message: each request contains the customer's message unchanged.
    - tool_results: each tool result reaches the next model request unchanged, as a tool
      message; otherwise it is reported as changed, misplaced (in another role) or missing.
    - tool_schemas: the tool list is the same in every request, and with native tool
      calling it matches the schemas the environment published.
    - system_prompt: the first message is the same in every request (a stable prefix).
    """
    requests = [e for e in events if e["kind"] == "model" and "request" in e]
    if not requests:
        return {"model_requests": 0}
    with_message = sum(
        any(
            m.get("role") == "user" and customer_message in _text(m.get("content"))
            for m in _messages(e)
        )
        for e in requests
    )
    results = []
    for tool in (e for e in events if e["kind"] == "tool" and "result" in e):
        later = [e for e in requests if e["seq"] > tool["seq"]]
        if not later:
            continue
        expected = _as_content(tool["result"])
        msgs = _messages(later[0])
        if any(m.get("role") == "tool" and _text(m.get("content")) == expected for m in msgs):
            results.append("unchanged")
        elif any(expected in _text(m.get("content")) for m in msgs if m.get("role") != "tool"):
            results.append("misplaced")
        elif any(
            m.get("role") == "tool" and expected.startswith(_text(m.get("content"))[:40])
            for m in msgs
        ):
            results.append("changed")
        else:
            results.append("missing")
    schemas = [digest(e["request"].get("tools")) for e in requests]
    tools = requests[0]["request"].get("tools") or []
    sgr = any(t.get("function", {}).get("name") == "NextStep" for t in tools)
    native = {digest(t) for t in tools}
    systems = [
        digest(_messages(e)[0])
        if _messages(e) and _messages(e)[0].get("role") == "system"
        else None
        for e in requests
    ]
    return {
        "model_requests": len(requests),
        "customer_message_intact": with_message == len(requests),
        "tool_results": {
            k: results.count(k) for k in ("unchanged", "changed", "misplaced", "missing")
        },
        "tool_schemas_stable": len(set(schemas)) == 1,
        # Not comparable when Schema-Guided Reasoning wraps every tool in one NextStep schema.
        "tool_schemas_match_environment": None
        if sgr
        else native == {digest(t) for t in TOOL_SCHEMAS},
        "system_prompt_stable": len(set(systems)) == 1,
    }

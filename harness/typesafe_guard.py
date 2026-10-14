"""TypeSafe Jev as a write guard (langchain-typesafe AutoModeMiddleware).

Before a guarded tool runs, ``AutoModeMiddleware`` asks Jev one ``Noul`` question:
the probability that this call breaks policy or was not requested. At >= 0.5 the tool
is not run and the model gets an error ToolMessage instead.

Two adaptations, both small:

1. ``OpenRouterJevClassifier`` sends the unchanged TypeSafe request body to OpenRouter's
   alpha Decisions API (``/api/alpha/decisions``) instead of ``api.typesafe.ai``, so the
   harness needs only the OpenRouter key. The request and response bodies are the same.
2. ``JevAutoModeMiddleware`` accepts a classifier. The stock ``AutoModeMiddleware``
   constructs ``TypeSafeClassifier()`` in ``__init__``, which requires
   ``TYPESAFE_API_KEY``.

3. Every guarded call records its decision. The upstream middleware keeps the
   probability only in the text of a blocked call. Here the decision (probability,
   threshold, blocked) goes into the ToolMessage's ``response_metadata["jev_guard"]``
   for allowed and blocked calls alike, so the trace shows why each write ran. The
   decision rule is unchanged: block at p >= 0.5. The model never sees this metadata.

This middleware wraps tool execution. Under τ³-bench the orchestrator runs the tools,
not the harness, so the guard never fires there.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langchain_typesafe import NoulCriteria, TypeSafeClassifier
from langchain_typesafe.experimental.middleware import AutoModeMiddleware
from langchain_typesafe.experimental.middleware.auto_mode import (
    _PROBABILITY_THRESHOLD,
    _QUESTION_ID,
    _AutoModeConfig,
    _risk_questions,
)

OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"


class OpenRouterJevClassifier(TypeSafeClassifier):
    """TypeSafeClassifier that calls Jev through OpenRouter's Decisions API."""

    @property
    def _endpoint(self) -> str:  # type: ignore[override]
        return OPENROUTER_DECISIONS_URL


def jev_classifier(model: str, endpoint: str, timeout_s: float) -> TypeSafeClassifier:
    """``endpoint``: "openrouter-decisions" (OpenRouter key) or "typesafe" (TypeSafe key)."""
    if endpoint == "openrouter-decisions":
        return OpenRouterJevClassifier(
            model=model, api_key=os.environ["OPENROUTER_API_KEY"], timeout=timeout_s
        )
    return TypeSafeClassifier(model=model, timeout=timeout_s)


class JevAutoModeMiddleware(AutoModeMiddleware):
    def __init__(
        self,
        *,
        tools: Sequence[str | BaseTool],
        instructions: str,
        criteria: NoulCriteria | None,
        classifier: TypeSafeClassifier,
    ) -> None:
        # Same validation as AutoModeMiddleware.__init__, without its built-in classifier.
        self.config = _AutoModeConfig.model_validate(
            {"tools": tools, "instructions": instructions, "criteria": criteria}
        )
        self.classifier = classifier

    def _request(self, request: ToolCallRequest) -> dict[str, Any]:
        return {
            "state": self._classification_state(request),
            "questions": _risk_questions(self.config),
        }

    @staticmethod
    def _record(result: Any, probability: float) -> Any:
        """Attach the decision to the ToolMessage the agent receives (allowed or blocked)."""
        if isinstance(result, ToolMessage):
            result.response_metadata = {
                **(result.response_metadata or {}),
                "jev_guard": {
                    "question": _QUESTION_ID,
                    "probability": probability,
                    "threshold": _PROBABILITY_THRESHOLD,
                    "blocked": probability >= _PROBABILITY_THRESHOLD,
                },
            }
        return result

    # Same decision as AutoModeMiddleware.wrap_tool_call / awrap_tool_call (block at
    # p >= 0.5, fail closed on a classifier error), plus the recorded decision.
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        if request.tool_call["name"] not in self._tool_names:
            return handler(request)
        probability = self.classifier.invoke(self._request(request)).nouls[_QUESTION_ID].noul
        if probability >= _PROBABILITY_THRESHOLD:
            return self._record(self._blocked_tool_message(request, probability), probability)
        return self._record(handler(request), probability)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        if request.tool_call["name"] not in self._tool_names:
            return await handler(request)
        response = await self.classifier.ainvoke(self._request(request))
        probability = response.nouls[_QUESTION_ID].noul
        if probability >= _PROBABILITY_THRESHOLD:
            return self._record(self._blocked_tool_message(request, probability), probability)
        return self._record(await handler(request), probability)

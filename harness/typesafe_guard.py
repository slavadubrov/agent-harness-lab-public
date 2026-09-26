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

This middleware wraps tool execution. Under τ³-bench the orchestrator runs the tools,
not the harness, so the guard never fires there.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from langchain_core.tools import BaseTool
from langchain_typesafe import NoulCriteria, TypeSafeClassifier
from langchain_typesafe.experimental.middleware import AutoModeMiddleware
from langchain_typesafe.experimental.middleware.auto_mode import _AutoModeConfig

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

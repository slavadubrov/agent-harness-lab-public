"""Typed workflow states referenced by workflow specs (state_schema: harness.states:...)."""

from __future__ import annotations

from pydantic import BaseModel


class SupportRequest(BaseModel):
    request: str
    route: str = ""
    route_confidence: float | None = None
    route_probabilities: dict[str, float] = {}
    answer: str = ""

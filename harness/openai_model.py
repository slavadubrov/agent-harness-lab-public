"""Pinned direct OpenAI chat model for the Part 5 improvement loop.

A workflow spec names it with ``model: {provider: import, id: openai, ref:
"harness.openai_model:chat"}``. Which model is called and at what endpoint comes from
the environment, not from the spec: a candidate harness cannot change it by editing its
spec.

    LAB_OPENAI_MODEL      the OpenAI model id (default: gpt-6.2-sol)
    LAB_OPENAI_URL        the endpoint base URL (default: https://api.openai.com/v1)
    LAB_REASONING_EFFORT  reasoning effort setting (default: low)
    LAB_SEED              the sampling seed of this run (default: 0)
"""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from harness.accounting import Price

REF = "harness.openai_model:chat"
MODEL = os.environ.get("LAB_OPENAI_MODEL", "gpt-6.2-sol")
URL = os.environ.get("LAB_OPENAI_URL", "https://api.openai.com/v1")
REASONING_EFFORT = os.environ.get("LAB_REASONING_EFFORT", "low")

# Official OpenAI API pricing per token (2026-11). Unknown models stay None so
# accounting never silently reports $0.00 for an unpriced model.
PRICES: dict[str, Price] = {
    "gpt-6.2-sol": Price(
        model_id="gpt-6.2-sol",
        provider_tag="openai-api",
        prompt=2e-6,
        completion=1e-5,
        input_cache_read=1e-7,
        input_cache_write=2.5e-6,
        source="OpenAI API pricing (2026-11): $2.00/1M in, $0.10/1M cached, $10.00/1M out",
    ),
    "gpt-6.1-terra": Price(
        model_id="gpt-6.1-terra",
        provider_tag="openai-api",
        prompt=1e-6,
        completion=5e-6,
        input_cache_read=5e-8,
        input_cache_write=1.25e-6,
        source="OpenAI API pricing (2026-11): $1.00/1M in, $0.05/1M cached, $5.00/1M out",
    ),
}
PRICE: Price | None = PRICES.get(MODEL)


def chat() -> BaseChatModel:
    return ChatOpenAI(
        model=MODEL,
        base_url=URL,
        # Allow offline workflow builds during validation/tests; live runners enforce the key.
        api_key=os.environ.get("OPENAI_API_KEY") or "missing",
        reasoning_effort=REASONING_EFFORT,
        seed=int(os.environ.get("LAB_SEED", "0")),
        max_tokens=1024,
        timeout=120,
        max_retries=2,
    )

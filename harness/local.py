"""A local model behind an OpenAI-compatible endpoint, so a run needs no key.

A spec names it with ``model: {provider: import, ref: "harness.local:chat"}``. Which
model that is, and where it runs, comes from the environment, not from the spec: a
candidate harness cannot change it by editing its spec.

    LAB_LOCAL_MODEL   the model id at the endpoint (default: gemma3n:latest)
    LAB_LOCAL_URL     the endpoint (default: Ollama at http://localhost:11434/v1)
    LAB_SEED          the sampling seed of this run (default: 0); the runner sets it per trial

Sampling settings are the model's own defaults at the endpoint.
"""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from harness.accounting import Price

REF = "harness.local:chat"
MODEL = os.environ.get("LAB_LOCAL_MODEL", "gemma3n:latest")
URL = os.environ.get("LAB_LOCAL_URL", "http://localhost:11434/v1")
# A local model has no bill. Its tokens get a nominal price, the list price of the closest
# hosted model, so cost per task still measures how much model work a harness asks for.
_INPUT = float(os.environ.get("LAB_LOCAL_USD_PER_INPUT_TOKEN", "5e-8"))
PRICE = Price(
    model_id=MODEL,
    provider_tag="local",
    prompt=_INPUT,
    completion=float(os.environ.get("LAB_LOCAL_USD_PER_OUTPUT_TOKEN", "1e-7")),
    # A local endpoint reports cached prompt tokens but gives no discount for them. Priced
    # at zero, two runs of one harness would differ in cost with the state of the cache.
    input_cache_read=_INPUT,
    input_cache_write=_INPUT,
    source="nominal: OpenRouter list price of google/gemma-3-4b-it on 2026-11-16",
)


def chat() -> BaseChatModel:
    return ChatOpenAI(
        model=MODEL,
        base_url=URL,
        api_key="local",  # the endpoint ignores it
        seed=int(os.environ.get("LAB_SEED", "0")),
        max_tokens=1024,
        timeout=120,
        max_retries=2,
    )

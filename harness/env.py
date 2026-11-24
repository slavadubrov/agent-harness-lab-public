"""Load API keys for entry points (runners, the τ³ CLI shim). Not used by build_harness."""

from __future__ import annotations

import os

from dotenv import dotenv_values

from harness.spec import REPO_ROOT


def _from_env(*names: str) -> str | None:
    for name in names:
        if val := os.environ.get(name):
            return val
    merged = {
        **dotenv_values(REPO_ROOT / ".env"),
        **dotenv_values(REPO_ROOT / ".env.local"),
    }
    for name in names:
        if val := merged.get(name):
            return val
    return None


def load_api_key() -> None:
    """Read .env / .env.local and expose the key as OPENROUTER_API_KEY (the name LangChain
    and litellm use). Accepts OPENROUTER_API_KEY or OPEN_ROUTER_API_KEY."""
    key = _from_env("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY")
    if not key:
        raise SystemExit(
            "Set OPENROUTER_API_KEY (or OPEN_ROUTER_API_KEY) in the environment or .env"
        )
    os.environ["OPENROUTER_API_KEY"] = key


def load_openai_key() -> str:
    """Read .env / .env.local and expose OPENAI_API_KEY for direct OpenAI API runs."""
    key = _from_env("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Set OPENAI_API_KEY in the environment or .env")
    os.environ["OPENAI_API_KEY"] = key
    return key

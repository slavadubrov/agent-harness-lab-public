"""Load the API key for entry points (runners, the τ³ CLI shim). Not used by build_harness."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from harness.spec import REPO_ROOT


def load_api_key() -> None:
    """Read .env and expose the key as OPENROUTER_API_KEY (the name LangChain and litellm use).

    Accepts OPENROUTER_API_KEY or OPEN_ROUTER_API_KEY.
    """
    load_dotenv(REPO_ROOT / ".env", override=False)
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPEN_ROUTER_API_KEY")
    if not key:
        raise SystemExit(
            "Set OPENROUTER_API_KEY (or OPEN_ROUTER_API_KEY) in the environment or .env"
        )
    os.environ["OPENROUTER_API_KEY"] = key

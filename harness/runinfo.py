"""Version and provenance records written next to every result."""

from __future__ import annotations

import subprocess
import time
from importlib.metadata import PackageNotFoundError, version

from harness.spec import REPO_ROOT

PACKAGES = [
    "langchain",
    "langchain-core",
    "langgraph",
    "langchain-mcp-adapters",
    "langchain-openai",
    "langchain-openrouter",
    "langchain-typesafe",
    "mcp",
    "pydantic",
    "tau2",
    "litellm",
]

TAU2_COMMIT = "b7ea9074c1cba482b30687fecdb5c8425fd6f619"
TAU2_TAG_NOTE = "package version 1.0.1; commit is 46 commits after tag v1.0.1 (fc0055d)"


def packages() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for p in PACKAGES:
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def git_sha() -> dict[str, str | bool | None]:
    def run(*args: str) -> str | None:
        try:
            return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    return {"sha": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

"""`tau2` with the harness agent registered.

    python -m envs.tau3.cli run --domain retail --agent langchain_harness ...

Takes exactly the `tau2` command-line arguments. The stock `tau2` entry point cannot see
an agent defined outside the tau2 package: `--agent` choices are read from the registry
when the parser is built, and tau2 (at b7ea907) has no plugin hook. This shim registers
the agent factory first, then calls `tau2.cli.main()`.
"""

from __future__ import annotations

import os

from harness.env import load_api_key
from harness.spec import REPO_ROOT

TAU2_DATA = REPO_ROOT / ".cache" / "tau2-bench" / "data"


def main() -> None:
    load_api_key()
    # tau2 resolves DATA_DIR at import time, so set it before importing tau2.
    os.environ.setdefault("TAU2_DATA_DIR", str(TAU2_DATA))
    from envs.tau3.agent import register

    register()
    from tau2.cli import main as tau2_main

    tau2_main()


if __name__ == "__main__":
    main()

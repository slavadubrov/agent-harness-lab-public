"""The A1 τ³ retail subset.

Rule: the first 8 task ids of the retail "test" split whose evaluation has no
natural-language assertions. For those tasks the reward is the database check only, so
no LLM judge (tau2 default: gpt-4.1) takes part in scoring.

    python -m envs.tau3.subset   # prints the ids
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from harness.spec import REPO_ROOT

SIZE = 8


def retail_dir() -> Path:
    data = Path(os.environ.get("TAU2_DATA_DIR", REPO_ROOT / ".cache" / "tau2-bench" / "data"))
    return data / "tau2" / "domains" / "retail"


def subset_ids(size: int = SIZE) -> list[str]:
    d = retail_dir()
    tasks = {t["id"]: t for t in json.loads((d / "tasks.json").read_text())}
    test = json.loads((d / "split_tasks.json").read_text())["test"]
    ids = [i for i in test if not (tasks[i]["evaluation_criteria"] or {}).get("nl_assertions")]
    return ids[:size]


if __name__ == "__main__":
    print(" ".join(subset_ids()))

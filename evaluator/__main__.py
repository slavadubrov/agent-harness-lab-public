"""Run only the built-in reviewed fixtures, offline, with no credentials."""

import argparse
import json
from pathlib import Path

from evaluator.fixtures import CASES, SECOND_TARGET, source
from evaluator.runner import run, task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trusted-fixtures",
        action="store_true",
        required=True,
        help="acknowledge process separation is not a sandbox",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = [
        run(source(name), task(kind), trusted_fixture=True) | {"fixture": name}
        for name, (kind, _) in CASES.items()
    ]
    results.append(
        run(SECOND_TARGET, task("clarification"), trusted_fixture=True)
        | {"fixture": "second_target"}
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwrite: preserve rejected and partial runs along with successes.
    with args.output.open("x") as out:
        json.dump({"schema": "fixture-report/1", "results": results}, out, indent=2)
        out.write("\n")
    for result in results:
        failures = [key for key, value in result["checks"].items() if not value]
        print(f"{result['fixture']}: {result['verdict']} {','.join(failures)}")


if __name__ == "__main__":
    main()

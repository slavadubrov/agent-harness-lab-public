"""Run several specs on a task suite k times each, interleaved, under a budget cap.

    python -m envs.custom.batch --batch k10 --suite a2 --runs 10 --step p1-03 --budget 1.00 \\
        --specs harness/spec/plain.yaml harness/spec/approval-agent.yaml

Run 1 of every spec comes before run 2 of any, so the provider's prompt cache and the
time of day do not line up with one design. Each pass is one run of one spec over all
the tasks, with a freshly built target, written to
reports/article-a3/custom/<batch>/<spec name>/r<NN>/. A pass that already has results is
skipped, so an interrupted batch continues where it stopped.

Dollars come from a pinned price table (harness/prices/), so they compare with the Part 2
runs. After each pass, its cost goes to reports/article-a3/spend.jsonl under a step name;
a pass counts the larger of OpenRouter's billed cost and the computed dollars. Before each
pass, the batch stops if the step's spend plus the most expensive pass so far could cross
the cap.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from envs.custom.run import BUILD, run_pass, select_tasks
from harness.accounting import Price, load_price_table
from harness.agent import spec_prices
from harness.env import load_api_key
from harness.runinfo import now, spec_hash
from harness.spec import REPO_ROOT, WorkflowSpec, load_any
from harness.workflow import workflow_prices

REPORTS = REPO_ROOT / "reports" / "article-a3"
LEDGER = REPORTS / "spend.jsonl"
PRICE_TABLE = "harness/prices/openrouter-2026-10-05.json"
PRICE_FIELDS = ("prompt", "completion", "input_cache_read", "input_cache_write")


def schedule(specs: list[str], runs: int) -> list[tuple[int, str]]:
    """(run, spec) pairs: run 1 of every spec, then run 2, and so on."""
    return [(r, s) for r in range(1, runs + 1) for s in specs]


def within_budget(spent: float, last_pass: float, cap: float) -> bool:
    return spent + last_pass <= cap


def spent(ledger: Path, step: str) -> float:
    """Dollars a step has spent: per pass, the larger of billed and computed cost."""
    if not ledger.exists():
        return 0.0
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    return round(
        sum(max(r["dollars"], r.get("billed") or 0.0) for r in rows if r["step"] == step), 10
    )


def record_spend(ledger: Path, **row) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a") as f:
        f.write(json.dumps({**row, "at": now()}) + "\n")


def live_prices_match(spec, pinned: list[Price]) -> bool:
    """Whether today's OpenRouter prices for the spec's models equal the pinned ones."""
    live = workflow_prices(spec) if isinstance(spec, WorkflowSpec) else spec_prices(spec)
    table = {(p.model_id, p.provider_tag): p for p in pinned}
    return all(
        (p.model_id, p.provider_tag) in table
        and all(
            getattr(p, f) == getattr(table[p.model_id, p.provider_tag], f) for f in PRICE_FIELDS
        )
        for p in live
    )


async def main_async(args) -> int:
    load_api_key()
    version, prices = load_price_table(args.price_table)
    tasks = select_tasks(args.suite, args.tasks)
    specs = {path: load_any(path) for path in args.specs}
    match = {path: live_prices_match(spec, prices) for path, spec in specs.items()}
    for path, ok in match.items():
        if not ok:
            print(f"warning: live prices differ from {version} for {path}; dollars use {version}")
    root = Path(args.root) if args.root else REPORTS / "custom" / args.batch
    most = 0.0
    for r, path in schedule(args.specs, args.runs):
        spec = specs[path]
        out = root / spec.name / f"r{r:02d}"
        if (out / "results.jsonl").exists():
            print(f"skip {out.relative_to(REPO_ROOT)}: already run")
            continue
        used = spent(LEDGER, args.step)
        if not within_budget(used, most, args.budget):
            print(
                f"stop: {args.step} spent ${used:.5f}; a pass can cost ${most:.5f}; "
                f"cap ${args.budget:.2f}"
            )
            return 1
        rows = await run_pass(
            spec,
            tasks,
            out,
            BUILD / args.batch / spec.name / f"r{r:02d}",
            prices,
            args.concurrency,
            {
                "label": f"run {r} of {args.runs}",
                "suite": args.suite,
                "batch": args.batch,
                "run": r,
                "runs": args.runs,
                "spec_hash": spec_hash(spec.model_dump(mode="json")),
                "price_table": version,
                "live_prices_match": match[path],
            },
        )
        dollars = round(sum(x["dollars"] for x in rows), 8)
        billed = round(sum(x["openrouter_billed_cost"] for x in rows), 8)
        most = max(most, dollars, billed)
        record_spend(
            LEDGER,
            step=args.step,
            batch=args.batch,
            spec=spec.name,
            run=r,
            tasks=len(rows),
            dollars=dollars,
            billed=billed,
        )
        passed = sum(x["passed"] for x in rows)
        print(
            f"r{r:02d} {spec.name:24} {passed}/{len(rows)} passed  ${dollars:.5f} "
            f"(billed ${billed:.5f})  {args.step} total ${spent(LEDGER, args.step):.5f}"
        )
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--batch", required=True, help="batch name, e.g. k10 or oot")
    p.add_argument("--suite", required=True)
    p.add_argument("--specs", nargs="+", required=True)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--step", required=True, help="the budget this spend counts against")
    p.add_argument("--budget", type=float, required=True, help="cap in dollars for the step")
    p.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    p.add_argument("--root", default="", help="output folder (default: reports/article-a3)")
    p.add_argument("--price-table", default=PRICE_TABLE)
    p.add_argument("--concurrency", type=int, default=4)
    raise SystemExit(asyncio.run(main_async(p.parse_args())))


if __name__ == "__main__":
    main()

"""The batch runner's schedule and budget. No model calls."""

from envs.custom.batch import schedule, spent, within_budget


def test_runs_interleave_the_designs():
    assert schedule(["a", "b"], runs=2) == [(1, "a"), (1, "b"), (2, "a"), (2, "b")]


def test_budget_stops_before_a_pass_that_could_cross_the_cap():
    assert within_budget(spent=0.50, last_pass=0.10, cap=1.00)
    assert not within_budget(spent=0.95, last_pass=0.10, cap=1.00)


def test_spend_ledger_sums_one_step(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    ledger.write_text(
        '{"step": "p1-03", "dollars": 0.25, "billed": 0.3}\n'
        '{"step": "p1-06", "dollars": 0.5, "billed": null}\n'
        '{"step": "p1-03", "dollars": 0.25, "billed": null}\n'
    )
    assert spent(ledger, "p1-03") == 0.55  # billed cost when present, else computed
    assert spent(tmp_path / "missing.jsonl", "p1-03") == 0.0


def test_spec_hash_ignores_where_the_spec_was_loaded_from():
    from harness.runinfo import spec_hash

    a = {"name": "x", "source": "harness/spec/a.yaml", "model": {"id": "m"}}
    b = {"model": {"id": "m"}, "name": "x", "source": "other.yaml +override"}
    assert spec_hash(a) == spec_hash(b) and len(spec_hash(a)) == 64
    assert spec_hash(a) != spec_hash({**a, "name": "y"})

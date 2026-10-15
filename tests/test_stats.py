"""Statistics over repeated runs. No model calls."""

from envs.custom.stats import pass_hat_k, task_stats


def row(passed: bool, calls: int, tokens: int, latency: float, dollars: float) -> dict:
    return {
        "passed": passed,
        "model_calls": calls,
        "input_tokens": tokens,
        "latency_s": latency,
        "dollars": dollars,
    }


def test_task_stats_over_three_runs():
    s = task_stats(
        [
            row(True, 4, 5000, 6.0, 3e-4),
            row(True, 4, 5200, 9.0, 4e-4),
            row(False, 6, 7000, 12.0, 6e-4),
        ]
    )
    assert (s["runs"], s["passed"], s["passed_all"]) == (3, 2, False)
    assert abs(s["pass_rate"] - 2 / 3) < 1e-12
    assert (s["model_calls_median"], s["input_tokens_median"], s["latency_s_median"]) == (
        4,
        5200,
        9.0,
    )
    assert abs(s["model_calls_mean"] - 14 / 3) < 1e-12
    assert abs(s["dollars_mean"] - 13e-4 / 3) < 1e-12


def test_pass_hat_k_is_the_share_of_tasks_passed_in_every_run():
    assert (
        pass_hat_k({"a": [True, True], "b": [True, False], "c": [True, True], "d": [False, False]})
        == 0.5
    )

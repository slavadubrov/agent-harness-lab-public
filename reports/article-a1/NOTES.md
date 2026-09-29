# Results summary

One run per task, so differences between rows are observations, not measured effects.
Per-task tables: [`README.md`](README.md).

## Custom support tasks (12 tasks)

| Spec | Model | Passed | Mean $/task | Mean latency |
|---|---|---|---|---|
| `a1-base` (SGR + Jev) | `openai/gpt-6-luna` | 12/12 | $0.00076 | 10.3 s |
| `a1-plain` (native tools) | `openai/gpt-6-luna` | 12/12 | $0.00035 | 4.6 s |
| `a1-base` (SGR + Jev) | `z-ai/glm-5.3-flash` | 12/12 | $0.00176 | 9.5 s |
| `a1-base` (SGR + Jev) | `xiaomi/mimo-v2.6-flash` | 7/12 | $0.00095 | 106.5 s |

- luna with either spec, and GLM, passed every task.
- With luna, `a1-base` cost about twice as much as `a1-plain` and took about twice as
  long. SGR writes its reasoning fields on every step: 728 vs 143 output tokens per
  task on average.
- Jev checked every proposed write and blocked none. No run proposed a bad write, so
  these tasks do not test whether Jev stops one.
- All 5 MiMo failures are `SGRParseError`. In 2 the model returned no `NextStep`; in 3
  it returned a string where the schema needs a list. None is a policy error.

## τ³-bench retail (8 tasks)

| Spec | Model | Passed | Mean agent $/task | Simulator $, total |
|---|---|---|---|---|
| `a1-base` (SGR + Jev) | `openai/gpt-6-luna` | 5/8 | $0.00219 | $0.00423 |
| `a1-plain` (native tools) | `openai/gpt-6-luna` | 6/8 | $0.00115 | $0.00414 |

- Every failure is a database mismatch. `a1-base` failed tasks 9, 27 and 32.
  `a1-plain` failed 27 and 32.
- τ³-bench runs the tools, so tool retry and Jev do not run. Here the two specs differ
  only in SGR.

## Both environments

- Summarization never ran.
- The model call limit never ended a run.

## What these runs do not show

- Variation between runs: each task ran once.
- Independent checks: the checks and accounting run in the agent process.
- Generalization: 12 development tasks, no held-out split, one customer message per task.

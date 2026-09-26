# A1 notes

One run per task, so differences between rows are observations, not measured effects.
A4 adds repeats. Full tables: [`README.md`](README.md).

## Custom environment (12 tasks)

| spec | model | pass | mean $/task | mean latency s |
|---|---|---|---|---|
| a1-base (SGR + Jev) | openai/gpt-6-luna | 12/12 | $0.00076 | 10.3 |
| a1-plain (native tools) | openai/gpt-6-luna | 12/12 | $0.00035 | 4.6 |
| a1-base (SGR + Jev) | z-ai/glm-5.3-flash | 12/12 | $0.00176 | 9.5 |
| a1-base (SGR + Jev) | xiaomi/mimo-v2.6-flash | 7/12 | $0.00095 | 106.5 |

- luna (both specs) and GLM pass every task. With luna, a1-base costs about 2× a1-plain
  and takes about 2× as long, because SGR writes its reasoning fields on every step
  (mean 728 vs 143 output tokens).
- Jev checked every proposed write and blocked none. No run proposed a bad write, so these
  tasks do not test whether Jev catches one.
- All 5 MiMo failures are `SGRParseError`: the model returned no `NextStep` call (2) or a
  string where the schema needs a list (3). None is a policy error.

## τ³-bench retail (8 tasks)

| spec | model | pass | mean agent $/task | user-simulator $ total |
|---|---|---|---|---|
| a1-base (SGR + Jev) | openai/gpt-6-luna | 5/8 | $0.00219 | $0.00423 |
| a1-plain (native tools) | openai/gpt-6-luna | 6/8 | $0.00115 | $0.00414 |

- Every failure is a database mismatch: a1-base failed tasks 9, 27 and 32; a1-plain
  failed 27 and 32.
- Under τ³ the two specs differ only in SGR: τ³ executes the tools, so the tool-side
  middleware (retry, Jev) does not run.

## Both environments

- Summarization never ran. The call limits never ended a run.

## Limits

- One run per task. No variance (A4).
- The state checks and accounting run in the harness process (A3 moves them out).
- 12 development tasks, no held-out split, single-turn user messages.

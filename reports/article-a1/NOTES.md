# A1 notes: what the committed runs show and what they do not

All numbers are from the files in this directory, **single run** (one trial per task).
Differences between rows are observations, not measured effects. A4 adds repeats.

## What was measured

Custom environment, 12 development tasks, run on 2026-09-24:

| spec | model | pass | mean $/task | mean latency s |
|---|---|---|---|---|
| a1-base (SGR + Jev) | openai/gpt-6-luna | 12/12 | $0.00073 | 11.9 |
| a1-plain (native tools) | openai/gpt-6-luna | 12/12 | $0.00033 | 5.8 |
| a1-base (SGR + Jev) | z-ai/glm-5.3-flash | 12/12 | $0.00101 | 9.7 |
| a1-base (SGR + Jev) | xiaomi/mimo-v2.6-flash | 7/12 | $0.00087 | 18.6 |

τ³-bench retail, 8 tasks (test split, no NL assertions), user simulator
`openai/gpt-6-luna`:

| spec | model | pass | mean agent $/task | user-simulator $ total |
|---|---|---|---|---|
| a1-base (SGR + Jev) | openai/gpt-6-luna | 6/8 | $0.00238 | $0.00453 |
| a1-plain (native tools) | openai/gpt-6-luna | 7/8 | $0.00136 | $0.00471 |

## Observations

- **The τ³ adapter works.** Both specs ran all 8 tasks through
  `interrupt_before=["tools"]` and resume, with no adapter errors. τ³ executed every tool
  call; the harness executed none (`harness_executed_tool_calls = 0` in every τ³ row).
- **The custom dev set does not separate the two luna harnesses.** Both pass 12/12. On
  these tasks a1-base used about 2.2× the dollars and 2× the latency of a1-plain. It
  used more output tokens (mean 684 vs 138: SGR writes the reasoning fields on every
  step) and more input tokens (mean 6.4k vs 3.4k: more model calls, each carrying the
  history and the `NextStep` schema). a1-plain often sent several tool calls in one
  response (mean 3.9 tool calls per 3.3 model calls); SGR allows one action per step.
- **Jev blocked nothing.** It ran 6 times for luna and 6 for GLM (once per proposed
  write) and allowed each call. No run proposed a write that the state check later
  rejected, so these runs do not test whether Jev catches a bad write.
- **MiMo with SGR failed on output format, not on policy.** All 5 MiMo failures are
  `SGRParseError`: no `NextStep` call in the response (3), malformed JSON with native
  tool-call tags inside the arguments (1), and a string where the schema needs a list (1).
  All 37 MiMo steps that did validate needed the JSON-string decoding fallback
  (`sgr_coerced: true` in the traces). The `plain` spec was not run on MiMo, so these
  runs cannot say whether native tool calling does better with MiMo.
- **τ³ failures are missing writes.** base failed tasks 9 and 26: the agent made no
  write. plain failed task 27: it transferred to a human instead of doing the exchange.
  Task 5 failed in an earlier smoke run of a1-base (not committed) and passed in the
  committed run. A clean-clone rerun of a1-base (`clean-clone-check/`) also passed 6/8,
  but it failed tasks 9 and 17 instead of 9 and 26. One run per task is not a result.
- **Summarization never ran**, in either environment. The largest single τ³ model
  request was 8,351 input tokens; the trigger is 12k. The call limits never ended a run.
- **Tool-side middleware does not run under τ³.** `ToolRetryMiddleware` and the Jev
  guard wrap tool execution, and τ³ executes the tools. So in τ³, a1-base and a1-plain
  differ only in SGR.
- **Dollars cross-check.** For all 393 chat calls, the computed dollars (tokens × pinned
  endpoint price) equal OpenRouter's billed `cost` (`openrouter_billed_cost` in the
  rows). Jev's billed cost is not in its response, so Jev dollars are computed only:
  input tokens × $0.042/M; output is free on that endpoint.

## Provenance notes

- The custom a1-base, a1-plain and MiMo runs used code at commit `425ff7d`. GLM and both
  τ³ runs used `093e298`. Between the two commits the harness changed in one place: the
  text of `SGRParseError`, which now includes the raw model output (a diagnostics change
  only). The GLM spec's endpoint also changed (see `failed-attempts/`).
- `git.dirty: true` in these run records only means that the run's own output files
  under `reports/` were not yet committed when it was recorded. From the next run on,
  `reports/` is excluded from that check (`harness/runinfo.py`).
- `clean-clone-check/` holds the rerun from a fresh clone at `27b81c1` (custom 12/12,
  τ³ 6/8). It is not in the summary tables.
- The first GLM attempt (Fireworks endpoint, HTTP 429 from OpenRouter's shared upstream
  pool) is kept in `failed-attempts/` and is not in the summary.

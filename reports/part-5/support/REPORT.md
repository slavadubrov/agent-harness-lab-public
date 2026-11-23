# Campaign on support-desk

- Saved use case: `support-desk` v5-loop. Regraded with `support-desk` v5-loop.
- Model held fixed: `gpt-6.2-sol`
- Runs per task: 2 on development, 3 on validation, 3 on test
- Adoption rule: one step of a loop, intervals at 95.00%
- The campaign proposed 3 candidates and adopted 0. Regrading supports 0 on the recorded path.
- Improver: $0.49 known cost in 4.0 minutes.
- Evaluation: 768 runs of candidates in 3.4 minutes, 96 more for the noise check and 96 on the test tasks
- All evaluation phases: 960 runs, $1.5318 in reported costs.
- Recorded stop: 3 candidates in a row were not adopted
- Noise check, the starting harness against itself on new samples: success +0.00 (+0.00 to +0.00), inconclusive: as it should be
- With intervals at 98.33%, sensitivity check across 3 candidates: the same decisions

## Every candidate

Development screens and validation decisions are recomputed from saved runs. A decision without grading evidence is marked as recorded only. Test scores describe the harnesses the campaign actually tested.

| Candidate | Change to | Development success | Validation success | Difference on validation | Decision | Why |
|---|---|---|---|---|---|---|
| 000 |  | 0.54 | 0.47 (0.31–0.66) |  | start | the starting harness |
| 001 | 000 | 0.71 | 0.65 (0.48–0.80) | +0.18 (+0.05 to +0.31) | inconclusive | success is higher on average (+0.052 to +0.312), but the task counts do not support the gain: 6 better, 1 worse (sign test p = 0.125); keep the base |
| 002 | 000 | 0.65 | 0.59 (0.44–0.75) | +0.12 (-0.03 to +0.28) | inconclusive | success difference -0.031 to +0.281 does not establish a benefit; keep the base |
| 003 | 000 | 0.69 | 0.59 (0.44–0.78) | +0.12 (+0.03 to +0.25) | inconclusive | success is higher on average (+0.031 to +0.250), but the task counts do not support the gain: 4 better, 0 worse (sign test p = 0.125); keep the base |

## What each candidate changed

**001** (inconclusive). Added a read-only policy route to the existing structured call. It distinguishes questions about shop rules from requests to take action and returns policy-backed answers before account lookup, without calling any write tool or adding a model call. This should fix the policy-question failures where the harness asked for an email or order number instead of explaining refund rules, address changes, or supported languages.
Files: `support_steps.py` (+73 −2), `workflow.yaml` (+19 −3). Diff: `candidates/001/patch.diff`.

**002** (inconclusive). The existing structured model call now extracts independent refund, address, and preference requests instead of choosing one primary action. The handler checks each request and reports both completed and refused actions, so a second request is no longer silently dropped. Refunds require an explicitly linked order number, conflicting requests for the same order prompt for clarification, and retries reuse the original refund amount. The supervisor approval flow and single model call are unchanged. This targets the compound-request failures; no evaluation runs were performed.
Files: `support_steps.py` (+104 −53), `workflow.yaml` (+20 −3). Diff: `candidates/002/patch.diff`.

**003** (inconclusive). The harness now resolves an order without a number only when the customer’s product wording matches exactly one order on their account; otherwise it asks for the order number. This should fix the missing-order-number refund failures and lets the same lookup answer shipping and refund status questions without issuing a refund. The existing refund policy and supervisor approval flow still apply, and retries recover the original receipt instead of recalculating the refund. No model call was added, and evaluation was not run.
Files: `support_steps.py` (+83 −17), `workflow.yaml` (+18 −2). Diff: `candidates/003/patch.diff`.

## Test tasks, scored once

| Harness | Success | pass^k | Violations | $ per task | $ per success | p50 latency, s | p95 latency, s | Calls per task | Tokens per task | Infra errors | Undecided | names refund id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 0.44 (0.25–0.59) | 0.44 (k=3) | 0 | $0.00120 (0.00117–0.00124) | $0.00275 (0.00198–0.00476) | 1.55 (1.46–1.67) | 2.06 (1.88–2.84) | 1.00 (1.00–1.00) | 477 (472–482) | 0 | 0 | 1.00 (1.00–1.00) |

| Tasks tagged | 000 |
|---|---|
| policy | 0.00 (6 tasks) |
| standard | 0.88 (8 tasks) |
| two_requests | 0.00 (6 tasks) |
| unusual | 0.67 (6 tasks) |
| vague | 0.50 (6 tasks) |

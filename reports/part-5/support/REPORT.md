# Campaign on support-desk

- Saved use case: `support-desk` v5-loop. Regraded with `support-desk` v5-loop.
- Model held fixed: `gpt-6.2-sol`
- Runs per task: 2 on development, 3 on validation, 3 on test
- Adoption rule: one step of a loop, intervals at 95.00%
- The campaign proposed 6 candidates and adopted 3. Regrading supports 3 on the recorded path.
- Improver: $0.88 known cost in 11.0 minutes.
- Evaluation: 1344 runs of candidates in 7.3 minutes, 96 more for the noise check and 192 on the test tasks
- All evaluation phases: 1632 runs, $3.1320 in reported costs.
- Recorded stop: 3 candidates in a row were not adopted
- Noise check, the starting harness against itself on new samples: success +0.00 (+0.00 to +0.00), inconclusive: as it should be
- With intervals at 99.17%, sensitivity check across 6 candidates: 005 (reject becomes inconclusive)

## Every candidate

Development screens and validation decisions are recomputed from saved runs. A decision without grading evidence is marked as recorded only. Test scores describe the harnesses the campaign actually tested.

| Candidate | Change to | Development success | Validation success | Difference on validation | Decision | Why |
|---|---|---|---|---|---|---|
| 000 |  | 0.54 | 0.47 (0.31–0.66) |  | start | the starting harness |
| 001 | 000 | 0.71 | 0.66 (0.50–0.81) | +0.19 (+0.06 to +0.31) | adopted | success is higher by +0.188 (interval +0.062 to +0.312): 6 tasks better, 0 worse, p < 0.001; still below the bar: pass^k = 0.6562, needs >= 0.9 |
| 002 | 001 | 0.81 | 0.74 (0.59–0.88) | +0.08 (-0.01 to +0.20) | adopted | success is higher by +0.083 (interval -0.010 to +0.198): 3 tasks better, 1 worse, p = 0.004; still below the bar: pass^k = 0.7188, needs >= 0.9 |
| 003 | 002 | 0.92 | 0.92 (0.82–0.99) | +0.18 (+0.06 to +0.31) | adopted | success is higher by +0.177 (interval +0.062 to +0.312): 6 tasks better, 0 worse, p < 0.001; still below the bar: pass^k = 0.875, needs >= 0.9 |
| 004 | 003 | 0.98 | 0.94 (0.84–1.00) | +0.02 (-0.05 to +0.10) | inconclusive | success is higher by +0.021 (interval -0.052 to +0.104), but the difference between runs does not support the gain: 2 tasks better, 1 worse, p = 0.630; keep the base |
| 005 | 003 | 0.93 | 0.82 (0.69–0.94) | -0.09 (-0.20 to -0.01) | rejected | 1 task fails runs it passed with the base, by more than run noise explains; keep the base |
| 006 | 003 | 0.97 | 0.94 (0.84–1.00) | +0.02 (-0.05 to +0.10) | inconclusive | success is higher by +0.021 (interval -0.052 to +0.104), but the difference between runs does not support the gain: 2 tasks better, 1 worse, p = 0.630; keep the base |

## What each candidate changed

**001** (adopted). Added a read-only route for shop-policy questions. The existing structured model call selects the relevant policy topics, and the harness answers from fixed policy text before any account lookup or refund processing. This should fix the policy failures where customers were asked for an email or order number instead of getting an answer about refund eligibility, limits, partial refunds, supported languages, or address changes after shipment. No model calls were added, and the existing write and approval paths are unchanged. The workflow was reviewed against the reference runner but not executed.
Files: `support_steps.py` (+70 −2), `workflow.yaml` (+20 −2). Diff: `candidates/001/patch.diff`.

**002** (adopted). Refund requests without an order number now use the existing model call to extract the product phrase the customer used. The harness applies its existing refund rules only if that phrase matches exactly one order on the identified account; otherwise it asks for the order number. This should fix the missing-order-number failures for eligible, already-refunded, late, and undelivered purchases. If a refund response is lost, the retry uses the existing receipt for that case rather than issuing another refund. I reviewed the changes against the reference code but did not run the workflow.
Files: `support_steps.py` (+54 −11), `workflow.yaml` (+8 −0). Diff: `candidates/002/patch.diff`.

**003** (adopted). The existing structured model call now extracts independent requests instead of choosing one intent. The harness checks each refund against its own order and amount, prevents duplicate refunds for the same order, and combines refund, address, and preference outcomes in one reply while preserving supervisor review. This targets the failures where a second request was ignored or two refunds were treated as an ambiguous single request. I reviewed the changes against the reference runner but did not execute the workflow.
Files: `support_steps.py` (+143 −81), `workflow.yaml` (+21 −22). Diff: `candidates/003/patch.diff`.

**004** (inconclusive). The existing model call now separates order and refund status questions from requests to issue a refund. Status replies use only records on the identified account and ask for an order number when the target is unclear. The shared target prompt also extracts just the product name, so refund requests without an order number can reach the existing eligibility checks instead of failing on surrounding wording. This should fix the shipment-status, prior-refund-amount, and vague late-refund failures without adding a model call or changing refund eligibility or approval rules. I reviewed the workflow wiring but did not run it.
Files: `support_steps.py` (+77 −25), `workflow.yaml` (+15 −10). Diff: `candidates/004/patch.diff`.

**005** (rejected). Account email changes are now handled as unsupported requests: the assistant directs the customer to support before attempting an account lookup, rather than mistaking the replacement address for a second account identifier. Other requests in the same message still go through the existing identity checks. This targets the email-change handoff failure without adding a model call or changing refund logic. The workflow was reviewed but not run.
Files: `support_steps.py` (+16 −6). Diff: `candidates/005/patch.diff`.

**006** (inconclusive). Added a read-only status check before the generic handoff for messages with an unambiguous account. A separate structured call identifies shipment and prior-refund questions, and the reply uses only records for an order on that account. This targets missing shipment-status and prior-refund-amount answers without changing refund issuance or approval. I reviewed the workflow wiring but did not run it.
Files: `support_steps.py` (+59 −5), `workflow.yaml` (+28 −5). Diff: `candidates/006/patch.diff`.

## Test tasks, scored once

| Harness | Success | pass^k | Violations | $ per task | $ per success | p50 latency, s | p95 latency, s | Calls per task | Tokens per task | Infra errors | Undecided | names refund id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 0.44 (0.25–0.59) | 0.44 (k=3) | 0 | $0.00120 (0.00117–0.00124) | $0.00275 (0.00198–0.00475) | 1.85 (1.74–1.93) | 2.77 (2.25–3.22) | 1.00 (1.00–1.00) | 477 (472–483) | 0 | 0 | 1.00 (1.00–1.00) |
| 003 | 0.90 (0.78–0.99) | 0.88 (k=3) | 0 | $0.00232 (0.00224–0.00240) | $0.00259 (0.00235–0.00295) | 2.34 (2.18–2.54) | 3.33 (3.06–3.49) | 1.00 (1.00–1.00) | 948 (938–958) | 0 | 0 | 1.00 (1.00–1.00) |

| Tasks tagged | 000 | 003 |
|---|---|---|
| policy | 0.00 (6 tasks) | 0.94 (6 tasks) |
| standard | 0.88 (8 tasks) | 0.88 (8 tasks) |
| two_requests | 0.00 (6 tasks) | 1.00 (6 tasks) |
| unusual | 0.67 (6 tasks) | 0.67 (6 tasks) |
| vague | 0.50 (6 tasks) | 1.00 (6 tasks) |

**003** against **000** on 32 tasks: success +0.458 (+0.292 to +0.625).
Better on 15 tasks, worse on 0 tasks.
Candidate minus base: cost_per_task +0.00112 (+0.00105 to +0.00119); latency_p50 +0.49 (+0.32 to +0.70); latency_p95 +0.56 (+0.17 to +1.09); calls_per_task +0.00 (+0.00 to +0.00); tokens_per_task +471 (+464 to +478); names refund id +0.00 (+0.00 to +0.00).
Decision: **adopt**. success is higher by +0.458 (interval +0.292 to +0.625): 15 tasks better, 0 worse, p < 0.001; still below the bar: pass^k = 0.875, needs >= 0.9

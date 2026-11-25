# Campaign on support-desk

- Saved use case: `support-desk` v5-loop. Regraded with `support-desk` v5-loop.
- Model held fixed: `gpt-6.2-sol`
- Runs per task: 2 on development, 3 on validation, 3 on test
- Adoption rule: one step of a loop, intervals at 95.00%
- The campaign proposed 6 candidates and adopted 2. Regrading supports 2 on the recorded path.
- Improver: $0.72 known cost in 6.7 minutes.
- Evaluation: 1344 runs of candidates in 6.5 minutes, 96 more for the noise check and 192 on the test tasks
- All evaluation phases: 1632 runs, $3.0604 in reported costs.
- Recorded stop: 3 candidates in a row were not adopted
- Noise check, the starting harness against itself on new samples: success +0.01 (+0.00 to +0.03), inconclusive: as it should be
- With intervals at 99.17%, sensitivity check across 6 candidates: 001 (adopt becomes inconclusive), 003 (adopt becomes inconclusive)

## Every candidate

Development screens and validation decisions are recomputed from saved runs. A decision without grading evidence is marked as recorded only. Test scores describe the harnesses the campaign actually tested.

| Candidate | Change to | Development success | Validation success | Difference on validation | Decision | Why |
|---|---|---|---|---|---|---|
| 000 |  | 0.55 | 0.46 (0.30–0.62) |  | start | the starting harness |
| 001 | 000 | 0.69 | 0.66 (0.50–0.81) | +0.20 (+0.07 to +0.34) | adopted | success is higher: +0.073 to +0.344; still below the bar: pass^k = 0.6562, needs >= 0.9 |
| 002 | 001 | 0.81 | 0.75 (0.59–0.88) | +0.09 (+0.00 to +0.22) | inconclusive | success difference +0.000 to +0.219 does not establish a benefit; keep the base |
| 003 | 001 | 0.83 | 0.83 (0.70–0.95) | +0.18 (+0.06 to +0.31) | adopted | success is higher: +0.062 to +0.312; still below the bar: pass^k = 0.8125, needs >= 0.9 |
| 004 | 003 | 0.86 | 0.88 (0.75–0.97) | +0.04 (+0.00 to +0.11) | inconclusive | success difference +0.000 to +0.115 does not establish a benefit; keep the base |
| 005 | 003 | 0.84 | 0.84 (0.72–0.97) | +0.01 (+0.00 to +0.03) | inconclusive | success difference +0.000 to +0.031 does not establish a benefit; keep the base |
| 006 | 003 | 0.94 | 0.93 (0.83–1.00) | +0.09 (+0.00 to +0.21) | inconclusive | success difference +0.000 to +0.208 does not establish a benefit; keep the base |

## What each candidate changed

**001** (adopted). Added a read-only policy route to the existing structured model call. General policy questions now select answers grounded in the shop’s rules and finish without an account lookup or any writes, even if the customer includes an email. This should fix the policy failures where the harness asked for an email or order number instead of answering questions about refund eligibility, cancellations, approval limits, partial refunds, account languages, or address changes after shipping. The model and existing transaction paths are unchanged.
Files: `support_steps.py` (+40 −1), `workflow.yaml` (+12 −2). Diff: `candidates/001/patch.diff`.

**002** (inconclusive). Refund requests that name a specific product but omit the order number now use the existing model call to extract the product phrase. The harness checks that the phrase appears in the message and matches exactly one order on the identified account; otherwise it still asks for the order number. The existing refund checks then decide whether to issue the refund, report that it was already issued, or explain that the order is outside the refund window or has not yet been delivered. This targets the five vague-refund failures without adding a model call.
Files: `support_steps.py` (+35 −1), `workflow.yaml` (+5 −1). Diff: `candidates/002/patch.diff`.

**003** (adopted). The harness now uses its existing structured model call to extract independent requests and reports the outcome of each, rather than dropping everything except the primary intent. This targets the mixed refund, address, and preference failures, including requests with separate refunds for multiple orders and cases where one action is allowed but another is refused. Refund handling checks explicit order IDs against the message, prevents repeat issuance on retries, and preserves the supervisor approval workflow without adding a model call.
Files: `support_steps.py` (+117 −51), `workflow.yaml` (+22 −12). Diff: `candidates/003/patch.diff`.

**004** (inconclusive). Added read-only delivery and refund-status inquiries to the existing structured model call. The harness checks only the identified account’s orders, using an order number supplied in the message or a product phrase that matches exactly one order. It asks for the order number when the match is unclear, and reports shipment status or the amount already refunded without issuing a refund. This targets the two status questions previously handed off, without adding a model call or changing refund execution.
Files: `support_steps.py` (+60 −2), `workflow.yaml` (+10 −3). Diff: `candidates/004/patch.diff`.

**005** (inconclusive). Clarified the existing refund extraction prompt so an unqualified refund without a stated amount is not marked ambiguous just because the customer names a product, explains the problem, or requests another change. This targets mixed requests where the refund was incorrectly held up by a request for an amount, while preserving clarification for genuinely unspecified partial refunds. No model calls or refund execution rules changed.
Files: `workflow.yaml` (+9 −5). Diff: `candidates/005/patch.diff`.

**006** (inconclusive). Refund requests that name a product but omit the order number now get a second, targeted check only when the supplied email identifies an account with exactly one matching order title. The check verifies that the customer actually asked for a whole-order refund of that product; otherwise the harness still asks for the order number. This targets the failures where an eligible refund was missed or the customer was not told that the order was already refunded, outside the refund window, or still awaiting delivery. The existing eligibility, approval, and retry checks are unchanged.
Files: `support_steps.py` (+57 −9), `workflow.yaml` (+32 −5). Diff: `candidates/006/patch.diff`.

## Test tasks, scored once

| Harness | Success | pass^k | Violations | $ per task | $ per success | p50 latency, s | p95 latency, s | Calls per task | Tokens per task | Infra errors | Undecided | names refund id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 0.44 (0.25–0.59) | 0.44 (k=3) | 0 | $0.00121 (0.00117–0.00125) | $0.00276 (0.00199–0.00478) | 1.55 (1.51–1.63) | 2.09 (1.97–2.66) | 1.00 (1.00–1.00) | 478 (472–483) | 0 | 0 | 1.00 (1.00–1.00) |
| 003 | 0.81 (0.66–0.94) | 0.81 (k=3) | 0 | $0.00209 (0.00202–0.00218) | $0.00257 (0.00223–0.00312) | 1.72 (1.62–1.85) | 2.72 (2.40–2.94) | 1.00 (1.00–1.00) | 846 (837–857) | 0 | 0 | 1.00 (1.00–1.00) |

| Tasks tagged | 000 | 003 |
|---|---|---|
| policy | 0.00 (6 tasks) | 1.00 (6 tasks) |
| standard | 0.88 (8 tasks) | 0.88 (8 tasks) |
| two_requests | 0.00 (6 tasks) | 1.00 (6 tasks) |
| unusual | 0.67 (6 tasks) | 0.67 (6 tasks) |
| vague | 0.50 (6 tasks) | 0.50 (6 tasks) |

**003** against **000** on 32 tasks: success +0.375 (+0.219 to +0.531).
Better on 12 tasks, worse on 0 tasks.
Candidate minus base: cost_per_task +0.00088 (+0.00083 to +0.00095); latency_p50 +0.17 (+0.07 to +0.27); latency_p95 +0.63 (+0.06 to +0.81); calls_per_task +0.00 (+0.00 to +0.00); tokens_per_task +368 (+363 to +375); names refund id +0.00 (+0.00 to +0.00).
Decision: **adopt**. success is higher: +0.219 to +0.531; still below the bar: pass^k = 0.8125, needs >= 0.9

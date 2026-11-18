# Campaign on support-desk

- Saved use case: `support-desk` v3-loop. Regraded with `support-desk` v4-loop.
- Model held fixed: `gemma3n:latest`
- Runs per task: 2 on development, 3 on validation, 3 on test
- Adoption rule: one step of a loop, intervals at 95.00%
- The campaign proposed 2 candidates and adopted 1. Regrading supports 1 on the recorded path.
- Improver: $0.89 known cost in 5.5 minutes.
- Evaluation: 576 runs of candidates in 30.4 minutes, 96 more for the noise check and 192 on the test tasks
- All evaluation phases: 864 runs, $0.0070 in reported costs.
- Recorded stop: no development task fails
- Under the current checks, the recorded final harness still fails development runs. This stopping condition no longer holds.
- Noise check, the starting harness against itself on new samples: success +0.03 (+0.00 to +0.08), inconclusive: as it should be
- With intervals at 97.50%, sensitivity check across 2 candidates: the same decisions

## Every candidate

Development screens and validation decisions are recomputed from saved runs. A decision without grading evidence is marked as recorded only. Test scores describe the harnesses the campaign actually tested.

| Candidate | Change to | Development success | Validation success | Difference on validation | Decision | Why |
|---|---|---|---|---|---|---|
| 000 |  | 0.40 | 0.22 (0.09–0.38) |  | start | the starting harness |
| 001 | 000 | 0.81 | 0.38 (0.22–0.54) | +0.16 (-0.05 to +0.38) | inconclusive | success difference -0.052 to +0.375 does not establish a benefit; keep the base |
| 002 | 000 | 0.93 | 0.55 (0.39–0.72) | +0.33 (+0.17 to +0.52) | adopted | success is higher: +0.167 to +0.521; still below the bar: pass^k = 0.5312, needs >= 0.9 |

## What each candidate changed

**001** (inconclusive). Replaced the model-driven `handle` in `harness/support_steps.py` with a code-first one; the single model call and its prompt are unchanged, so there is no token cost. The message is split into clauses, and each clause is handled on its own by regexes and the account's orders. The model's `kind`, `settings` and `address` are used only when the regexes find nothing. This should fix: (1) tasks with two requests, where only one used to be done and the preference or address half was lost or garbled; (2) preference tasks that the model mislabelled as an address request, including unsupported keys such as dark mode; (3) address parsing, which now uses a regex with a country-name-to-ISO map instead of the model's mangled street and country; (4) vague refunds, tracking questions and refund-status questions, where the order is now found from the item name among the customer's own orders; (5) policy questions without an email, which now get a canned policy answer instead of a request for an email; (6) the invoice request that was wrongly refunded, since a refund now needs an explicit refund word in the clause. I could not run any code in this session, so none of this has been tested.
Files: `support_steps.py` (+253 −2). Diff: `candidates/001/patch.diff`.

**002** (adopted). Changed only `harness/support_steps.py`; the single model call and its prompt are unchanged, so there is no token cost. `handle` now reads the message in code first: it splits it into clauses and handles each by regex, using the account's own orders. The model's output is used only when no clause is recognised. Specifically: (1) preference, address and refund requests in one message are each handled, instead of only the model's one `kind`; (2) preference parsing and address parsing are regex-based, with a country-to-ISO map, so unsupported keys such as dark mode are refused and street and country are no longer mangled; (3) a refund is matched to an order by item name, or carried over from the previous clause, which fixes vague refunds that were answered with "which order?"; (4) policy questions get canned answers, even without an email; (5) tracking and refund-status questions are answered from the order and refund rows; (6) the model's refund amount is ignored in favour of the amount in the text, and a refund needs a refund word, which stops the invoice request from being refunded. Refunds are still made once per order per message. I could not run the code in this session, so it is untested. It is a larger change than "one focused change", and it overlaps with the earlier candidate 001, which was inconclusive rather than dropped.
Files: `support_steps.py` (+273 −13). Diff: `candidates/002/patch.diff`.

## Test tasks, scored once

| Harness | Success | pass^k | Violations | $ per task | $ per success | p50 latency, s | p95 latency, s | Calls per task | Tokens per task | Infra errors | Undecided | names refund id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 0.25 (0.11–0.41) | 0.22 (k=3) | 0 | $0.00001 (0.00001–0.00001) | $0.00003 (0.00002–0.00007) | 3.00 (2.55–3.48) | 5.83 (4.65–6.63) | 1.00 (1.00–1.00) | 137 (127–148) | 0 | 0 | 1.00 (1.00–1.00) |
| 002 | 0.52 (0.36–0.69) | 0.50 (k=3) | 0 | $0.00001 (0.00001–0.00001) | $0.00001 (0.00001–0.00002) | 3.10 (2.58–3.57) | 5.94 (5.32–8.11) | 1.00 (1.00–1.00) | 137 (127–148) | 0 | 0 | 1.00 |

| Tasks tagged | 000 | 002 |
|---|---|---|
| policy | 0.00 (6 tasks) | 0.33 (6 tasks) |
| standard | 0.67 (8 tasks) | 0.38 (8 tasks) |
| two_requests | 0.00 (6 tasks) | 0.67 (6 tasks) |
| unusual | 0.11 (6 tasks) | 0.28 (6 tasks) |
| vague | 0.33 (6 tasks) | 1.00 (6 tasks) |

**002** against **000** on 32 tasks: success +0.271 (+0.062 to +0.479).
Better on 13 tasks, worse on 3 tasks.
Candidate minus base: cost_per_task -0.00000 (-0.00000 to -0.00000); latency_p50 +0.11 (-0.02 to +0.38); latency_p95 +0.10 (-0.27 to +1.48); calls_per_task +0.00 (+0.00 to +0.00); tokens_per_task +0 (+0 to +0); names refund id unknown.
Decision: **adopt**. success is higher: +0.062 to +0.479; still below the bar: pass^k = 0.5, needs >= 0.9

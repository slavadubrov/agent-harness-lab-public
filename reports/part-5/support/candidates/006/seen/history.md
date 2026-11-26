# Candidates so far

The harness in `harness/` is candidate 003.

## Candidate 001, a change to 000: adopt
Added a read-only route for shop-policy questions. The existing structured model call selects the relevant policy topics, and the harness answers from fixed policy text before any account lookup or refund processing. This should fix the policy failures where customers were asked for an email or order number instead of getting an answer about refund eligibility, limits, partial refunds, supported languages, or address changes after shipment. No model calls were added, and the existing write and approval paths are unchanged. The workflow was reviewed against the reference runner but not executed.

Changed: support_steps.py (+70 -2), workflow.yaml (+20 -2)
Decision: success is higher by +0.188 (interval +0.062 to +0.312): 6 tasks better, 0 worse, p < 0.001; still below the bar: pass^k = 0.6562, needs >= 0.9

## Candidate 002, a change to 001: adopt
Refund requests without an order number now use the existing model call to extract the product phrase the customer used. The harness applies its existing refund rules only if that phrase matches exactly one order on the identified account; otherwise it asks for the order number. This should fix the missing-order-number failures for eligible, already-refunded, late, and undelivered purchases. If a refund response is lost, the retry uses the existing receipt for that case rather than issuing another refund. I reviewed the changes against the reference code but did not run the workflow.

Changed: support_steps.py (+54 -11), workflow.yaml (+8 -0)
Decision: success is higher by +0.083 (interval -0.010 to +0.198): 3 tasks better, 1 worse, p = 0.004; still below the bar: pass^k = 0.7188, needs >= 0.9

## Candidate 003, a change to 002: adopt
The existing structured model call now extracts independent requests instead of choosing one intent. The harness checks each refund against its own order and amount, prevents duplicate refunds for the same order, and combines refund, address, and preference outcomes in one reply while preserving supervisor review. This targets the failures where a second request was ignored or two refunds were treated as an ambiguous single request. I reviewed the changes against the reference runner but did not execute the workflow.

Changed: support_steps.py (+143 -81), workflow.yaml (+21 -22)
Decision: success is higher by +0.177 (interval +0.062 to +0.312): 6 tasks better, 0 worse, p < 0.001; still below the bar: pass^k = 0.875, needs >= 0.9

## Candidate 004, a change to 003: inconclusive
The existing model call now separates order and refund status questions from requests to issue a refund. Status replies use only records on the identified account and ask for an order number when the target is unclear. The shared target prompt also extracts just the product name, so refund requests without an order number can reach the existing eligibility checks instead of failing on surrounding wording. This should fix the shipment-status, prior-refund-amount, and vague late-refund failures without adding a model call or changing refund eligibility or approval rules. I reviewed the workflow wiring but did not run it.

Changed: support_steps.py (+77 -25), workflow.yaml (+15 -10)
Decision: success is higher by +0.021 (interval -0.052 to +0.104), but the difference between runs does not support the gain: 2 tasks better, 1 worse, p = 0.630; keep the base

## Candidate 005, a change to 003: reject
Account email changes are now handled as unsupported requests: the assistant directs the customer to support before attempting an account lookup, rather than mistaking the replacement address for a second account identifier. Other requests in the same message still go through the existing identity checks. This targets the email-change handoff failure without adding a model call or changing refund logic. The workflow was reviewed but not run.

Changed: support_steps.py (+16 -6)
Decision: 1 task fails runs it passed with the base, by more than run noise explains; keep the base


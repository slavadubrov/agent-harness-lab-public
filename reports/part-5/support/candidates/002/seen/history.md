# Candidates so far

The harness in `harness/` is candidate 001.

## Candidate 001, a change to 000: adopt
Added a read-only route for shop-policy questions. The existing structured model call selects the relevant policy topics, and the harness answers from fixed policy text before any account lookup or refund processing. This should fix the policy failures where customers were asked for an email or order number instead of getting an answer about refund eligibility, limits, partial refunds, supported languages, or address changes after shipment. No model calls were added, and the existing write and approval paths are unchanged. The workflow was reviewed against the reference runner but not executed.

Changed: support_steps.py (+70 -2), workflow.yaml (+20 -2)
Decision: success is higher by +0.188 (interval +0.062 to +0.312): 6 tasks better, 0 worse, p < 0.001; still below the bar: pass^k = 0.6562, needs >= 0.9


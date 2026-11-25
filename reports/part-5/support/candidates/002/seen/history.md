# Candidates so far

The harness in `harness/` is candidate 001.

## Candidate 001, a change to 000: adopt
Added a read-only policy route to the existing structured model call. General policy questions now select answers grounded in the shop’s rules and finish without an account lookup or any writes, even if the customer includes an email. This should fix the policy failures where the harness asked for an email or order number instead of answering questions about refund eligibility, cancellations, approval limits, partial refunds, account languages, or address changes after shipping. The model and existing transaction paths are unchanged.

Changed: support_steps.py (+40 -1), workflow.yaml (+12 -2)
Decision: success is higher: +0.073 to +0.344; still below the bar: pass^k = 0.6562, needs >= 0.9


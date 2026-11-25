# Candidates so far

The harness in `harness/` is candidate 000.

## Candidate 001, a change to 000: inconclusive
Added a read-only policy route to the existing structured call. It distinguishes questions about shop rules from requests to take action and returns policy-backed answers before account lookup, without calling any write tool or adding a model call. This should fix the policy-question failures where the harness asked for an email or order number instead of explaining refund rules, address changes, or supported languages.

Changed: support_steps.py (+73 -2), workflow.yaml (+19 -3)
Decision: success is higher on average (+0.052 to +0.312), but the task counts do not support the gain: 6 better, 1 worse (sign test p = 0.125); keep the base


# Candidates so far

The harness in `harness/` is candidate 000.

## Candidate 001, a change to 000: inconclusive
Added a read-only policy route to the existing structured call. It distinguishes questions about shop rules from requests to take action and returns policy-backed answers before account lookup, without calling any write tool or adding a model call. This should fix the policy-question failures where the harness asked for an email or order number instead of explaining refund rules, address changes, or supported languages.

Changed: support_steps.py (+73 -2), workflow.yaml (+19 -3)
Decision: success is higher on average (+0.052 to +0.312), but the task counts do not support the gain: 6 better, 1 worse (sign test p = 0.125); keep the base

## Candidate 002, a change to 000: inconclusive
The existing structured model call now extracts independent refund, address, and preference requests instead of choosing one primary action. The handler checks each request and reports both completed and refused actions, so a second request is no longer silently dropped. Refunds require an explicitly linked order number, conflicting requests for the same order prompt for clarification, and retries reuse the original refund amount. The supervisor approval flow and single model call are unchanged. This targets the compound-request failures; no evaluation runs were performed.

Changed: support_steps.py (+104 -53), workflow.yaml (+20 -3)
Decision: success difference -0.031 to +0.281 does not establish a benefit; keep the base


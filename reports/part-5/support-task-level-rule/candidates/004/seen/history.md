# Candidates so far

The harness in `harness/` is candidate 003.

## Candidate 001, a change to 000: adopt
Added a read-only policy route to the existing structured model call. General policy questions now select answers grounded in the shop’s rules and finish without an account lookup or any writes, even if the customer includes an email. This should fix the policy failures where the harness asked for an email or order number instead of answering questions about refund eligibility, cancellations, approval limits, partial refunds, account languages, or address changes after shipping. The model and existing transaction paths are unchanged.

Changed: support_steps.py (+40 -1), workflow.yaml (+12 -2)
Decision: success is higher: +0.073 to +0.344; still below the bar: pass^k = 0.6562, needs >= 0.9

## Candidate 002, a change to 001: inconclusive
Refund requests that name a specific product but omit the order number now use the existing model call to extract the product phrase. The harness checks that the phrase appears in the message and matches exactly one order on the identified account; otherwise it still asks for the order number. The existing refund checks then decide whether to issue the refund, report that it was already issued, or explain that the order is outside the refund window or has not yet been delivered. This targets the five vague-refund failures without adding a model call.

Changed: support_steps.py (+35 -1), workflow.yaml (+5 -1)
Decision: success difference +0.000 to +0.219 does not establish a benefit; keep the base

## Candidate 003, a change to 001: adopt
The harness now uses its existing structured model call to extract independent requests and reports the outcome of each, rather than dropping everything except the primary intent. This targets the mixed refund, address, and preference failures, including requests with separate refunds for multiple orders and cases where one action is allowed but another is refused. Refund handling checks explicit order IDs against the message, prevents repeat issuance on retries, and preserves the supervisor approval workflow without adding a model call.

Changed: support_steps.py (+117 -51), workflow.yaml (+22 -12)
Decision: success is higher: +0.062 to +0.312; still below the bar: pass^k = 0.8125, needs >= 0.9


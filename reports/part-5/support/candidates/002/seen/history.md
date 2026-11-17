# Candidates so far

The harness in `harness/` is candidate 000.

## Candidate 001, a change to 000: inconclusive
Replaced the model-driven `handle` in `harness/support_steps.py` with a code-first one; the single model call and its prompt are unchanged, so there is no token cost. The message is split into clauses, and each clause is handled on its own by regexes and the account's orders. The model's `kind`, `settings` and `address` are used only when the regexes find nothing. This should fix: (1) tasks with two requests, where only one used to be done and the preference or address half was lost or garbled; (2) preference tasks that the model mislabelled as an address request, including unsupported keys such as dark mode; (3) address parsing, which now uses a regex with a country-name-to-ISO map instead of the model's mangled street and country; (4) vague refunds, tracking questions and refund-status questions, where the order is now found from the item name among the customer's own orders; (5) policy questions without an email, which now get a canned policy answer instead of a request for an email; (6) the invoice request that was wrongly refunded, since a refund now needs an explicit refund word in the clause.

I could not run any code in this session, so none of this has been tested.

Changed: support_steps.py (+253 -2)
Decision: success difference -0.073 to +0.354 does not establish a benefit; keep the base


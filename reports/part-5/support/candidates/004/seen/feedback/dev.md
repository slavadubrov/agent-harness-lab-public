# support-desk, 003: 44 of 48 tasks pass every run (success 0.92)

## vague-tablecloth-late: 0 of 2 runs passed
Tags: vague
Input:
> Hello, ana.novak@example.com. The tablecloth I bought has a stain that won't wash out. I'd like a refund.
Failed checks:
- `says ('30[- ]day|thirty|window|too late|expired',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "policy_topics": [], "refunds": ["order_id=None item='tablecloth I bought' amount_cents=None clarify_amount=False"], "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "policy_topics": [], "refunds": ["order_id=None item='The tablecloth I bought' amount_cents=None clarify_amount=False"], "address": null, "settings": []}, "events": []}

## unusual-where-is-order: 0 of 2 runs passed
Tags: unusual
Input:
> Hi, ana.novak@example.com. Where is my espresso machine? It still hasn't arrived.
Failed checks:
- `says ('shipped|on (its|the) way|in transit',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I have passed your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"answer": "I have passed your message to a colleague, who will reply soon.", "next_step": "done", "policy_topics": [], "refunds": [], "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> I have passed your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"answer": "I have passed your message to a colleague, who will reply soon.", "next_step": "done", "policy_topics": [], "refunds": [], "address": null, "settings": []}, "events": []}

## unusual-refund-status: 0 of 2 runs passed
Tags: unusual
Input:
> Hello, eva.lindqvist@example.com. Did my refund for the headphones go through? How much was it?
Failed checks:
- `says ('\\b199(\\.00)?\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I have passed your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"answer": "I have passed your message to a colleague, who will reply soon.", "next_step": "done", "policy_topics": [], "refunds": [], "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> I have passed your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"answer": "I have passed your message to a colleague, who will reply soon.", "next_step": "done", "policy_topics": [], "refunds": [], "address": null, "settings": []}, "events": []}

## unusual-change-email: 0 of 2 runs passed
Tags: unusual
Input:
> Hey, ben.ortiz@example.com. Please change the email on my account to ben@ortiz.example.
Failed checks:
- `says ("(?:^|[.!?]\\s+)(?:I(?: have|['’]ve)?|we(?: have|['’]ve)?|(?:your|this) (?:request|case|message) (?:was|has been)) (?:passed|forwarded|escalated|referred|transferred|sent)\\b[^.!?]{0,70}\\b(?:colleague|team|agent|specialist|person|support)\\b|(?:^|[.!?]\\s+)(?:please |you (?:can|should|need to) )?(?:contact|call|email|reach out to|speak (?:with|to)) (?:our |a |the |customer )*(?:support|team|agent|specialist|representative)\\b|(?:^|[.!?]\\s+)(?:a |our |the |my )?(?:colleague|agent|specialist|representative|team) will (?:reply|contact|review|handle|help|follow up|get back)\\b",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please confirm which email address identifies the account for these changes.
Recorded actions: none
Trace: {"state": {"answer": "Please confirm which email address identifies the account for these changes.", "next_step": "done", "policy_topics": [], "refunds": [], "address": null, "settings": ["key='email' value='ben@ortiz.example'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Please confirm which email address identifies the account for these changes.
Recorded actions: none
Trace: {"state": {"answer": "Please confirm which email address identifies the account for these changes.", "next_step": "done", "policy_topics": [], "refunds": [], "address": null, "settings": ["key='account_email' value='ben@ortiz.example'"]}, "events": []}

## Passing every run
refund-full-damaged, refund-partial-missing-item, refund-outside-window, refund-over-agent-limit, refund-not-delivered, refund-already-refunded, refund-other-customers-order, address-update-shipping, address-missing-fields, address-suspended-account, preferences-two-changes, preferences-one-unsupported, refund-over-limit-approved, refund-over-limit-rejected, refund-partial-lost-response, refund-over-limit-approved-lost-response, vague-teapot-no-order, vague-teapot-no-email, vague-helmet, vague-something-wrong, vague-which-order, vague-headphones-refunded, vague-espresso-not-delivered, two-refund-and-emails, two-refund-and-address, two-address-and-language, two-refund-allowed-address-refused, two-both-refused, two-address-allowed-refund-refused, two-no-identity, two-refund-allowed-refund-refused, policy-refund-window, policy-undelivered, policy-cancelled, policy-refund-limit, policy-languages, policy-suspended-refund, policy-partial-refund, policy-shipped-address, unusual-close-account, unusual-complaint, unusual-invoice, unusual-exchange, unusual-why-suspended

# support-desk, 003: 40 of 48 tasks pass every run (success 0.83)

## vague-teapot-no-order: 0 of 2 runs passed
Tags: vague
Input:
> Hi, this is ana.novak@example.com. My ceramic teapot arrived broken. Please refund the full amount.
Failed checks:
- `state` in 2 of 2 runs
- `did refund(cents=4800, order='O-1001')` in 2 of 2 runs
- `says ('\\b48(\\.00)?\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

## vague-helmet: 0 of 2 runs passed
Tags: vague
Input:
> Hi, ben.ortiz@example.com. My bike helmet arrived with a cracked visor. Can I get my money back?
Failed checks:
- `state` in 2 of 2 runs
- `did refund(cents=8900, order='O-2001')` in 2 of 2 runs
- `says ('\\b89(\\.00)?\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

## vague-headphones-refunded: 0 of 2 runs passed
Tags: vague
Input:
> Hi, it's eva.lindqvist@example.com. My headphones are defective. Please refund them.
Failed checks:
- `says ('already',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

## vague-tablecloth-late: 0 of 2 runs passed
Tags: vague
Input:
> Hello, ana.novak@example.com. The tablecloth I bought has a stain that won't wash out. I'd like a refund.
Failed checks:
- `says ('30[- ]day|thirty|window|too late|expired',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

## vague-espresso-not-delivered: 0 of 2 runs passed
Tags: vague
Input:
> Hi, ana.novak@example.com. My espresso machine still hasn't come and I want my money back.
Failed checks:
- `says ('deliver|shipped|in transit|pending|arriv',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id=None amount_cents=None amount_unclear=False"], "addresses": [], "settings": [], "policy_topics": [], "handoff": false, "answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done"}, "events": []}

## two-refund-and-emails: 0 of 2 runs passed
Tags: two_requests
Input:
> Hi, dmitri.sokolov@example.com. Please turn off marketing emails, and refund my wool blanket from order O-4001. It arrived damaged.
Failed checks:
- `state` in 2 of 2 runs
- `did refund(cents=7400, order='O-4001')` in 2 of 2 runs
- `says ('\\b74(\\.00)?\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please confirm how much you want refunded for order O-4001. Done: marketing_emails is now off.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id='O-4001' amount_cents=None amount_unclear=True"], "addresses": [], "settings": ["key='marketing_emails' value='off'"], "policy_topics": [], "handoff": false, "answer": "Please confirm how much you want refunded for order O-4001. Done: marketing_emails is now off.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> Please confirm how much you want refunded for order O-4001. Done: marketing_emails is now off.
Recorded actions: none
Trace: {"state": {"refunds": ["order_id='O-4001' amount_cents=None amount_unclear=True"], "addresses": [], "settings": ["key='marketing_emails' value='off'"], "policy_topics": [], "handoff": false, "answer": "Please confirm how much you want refunded for order O-4001. Done: marketing_emails is now off.", "next_step": "done"}, "events": []}

## unusual-where-is-order: 0 of 2 runs passed
Tags: unusual
Input:
> Hi, ana.novak@example.com. Where is my espresso machine? It still hasn't arrived.
Failed checks:
- `says ('shipped|on (its|the) way|in transit',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I have passed that part of your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"refunds": [], "addresses": [], "settings": [], "policy_topics": [], "handoff": true, "answer": "I have passed that part of your message to a colleague, who will reply soon.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> I have passed that part of your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"refunds": [], "addresses": [], "settings": [], "policy_topics": [], "handoff": true, "answer": "I have passed that part of your message to a colleague, who will reply soon.", "next_step": "done"}, "events": []}

## unusual-refund-status: 0 of 2 runs passed
Tags: unusual
Input:
> Hello, eva.lindqvist@example.com. Did my refund for the headphones go through? How much was it?
Failed checks:
- `says ('\\b199(\\.00)?\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I have passed that part of your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"refunds": [], "addresses": [], "settings": [], "policy_topics": [], "handoff": true, "answer": "I have passed that part of your message to a colleague, who will reply soon.", "next_step": "done"}, "events": []}

Run 1 ended `completed`. Reply:
> I have passed that part of your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"refunds": [], "addresses": [], "settings": [], "policy_topics": [], "handoff": true, "answer": "I have passed that part of your message to a colleague, who will reply soon.", "next_step": "done"}, "events": []}

## Passing every run
refund-full-damaged, refund-partial-missing-item, refund-outside-window, refund-over-agent-limit, refund-not-delivered, refund-already-refunded, refund-other-customers-order, address-update-shipping, address-missing-fields, address-suspended-account, preferences-two-changes, preferences-one-unsupported, refund-over-limit-approved, refund-over-limit-rejected, refund-partial-lost-response, refund-over-limit-approved-lost-response, vague-teapot-no-email, vague-something-wrong, vague-which-order, two-refund-and-address, two-address-and-language, two-refund-allowed-address-refused, two-both-refused, two-address-allowed-refund-refused, two-no-identity, two-refund-allowed-refund-refused, policy-refund-window, policy-undelivered, policy-cancelled, policy-refund-limit, policy-languages, policy-suspended-refund, policy-partial-refund, policy-shipped-address, unusual-close-account, unusual-change-email, unusual-complaint, unusual-invoice, unusual-exchange, unusual-why-suspended

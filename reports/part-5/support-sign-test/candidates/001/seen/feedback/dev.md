# support-desk, 000: 26 of 48 tasks pass every run (success 0.54)

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
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

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
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## vague-headphones-refunded: 0 of 2 runs passed
Tags: vague
Input:
> Hi, it's eva.lindqvist@example.com. My headphones are defective. Please refund them.
Failed checks:
- `says ('already',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## vague-tablecloth-late: 0 of 2 runs passed
Tags: vague
Input:
> Hello, ana.novak@example.com. The tablecloth I bought has a stain that won't wash out. I'd like a refund.
Failed checks:
- `says ('30[- ]day|thirty|window|too late|expired',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## vague-espresso-not-delivered: 0 of 2 runs passed
Tags: vague
Input:
> Hi, ana.novak@example.com. My espresso machine still hasn't come and I want my money back.
Failed checks:
- `says ('deliver|shipped|in transit|pending|arriv',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## two-refund-and-emails: 0 of 2 runs passed
Tags: two_requests
Input:
> Hi, dmitri.sokolov@example.com. Please turn off marketing emails, and refund my wool blanket from order O-4001. It arrived damaged.
Failed checks:
- `state` in 2 of 2 runs
- `says ('marketing|email',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I refunded $74.00 for order O-4001 (refund 2).
Recorded actions: refund({"order": "O-4001", "cents": 7400, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $74.00 for order O-4001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='marketing_emails' value='off'"]}, "events": []}

Run 1 ended `completed`. Reply:
> I refunded $74.00 for order O-4001 (refund 2).
Recorded actions: refund({"order": "O-4001", "cents": 7400, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $74.00 for order O-4001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='marketing_emails' value='off'"]}, "events": []}

## two-refund-and-address: 0 of 2 runs passed
Tags: two_requests
Input:
> This is ana.novak@example.com. My ceramic teapot (order O-1001) arrived broken, please refund it. Also, I moved: my new shipping address is Schönhauser Allee 12, 10119 Berlin, Germany.
Failed checks:
- `state` in 2 of 2 runs
- `says ('sch(ö|oe|o)nhauser',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I refunded $48.00 for order O-1001 (refund 2).
Recorded actions: refund({"order": "O-1001", "cents": 4800, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $48.00 for order O-1001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='shipping' line1='Schönhauser Allee 12' city='Berlin' postal_code='10119' country='DE'", "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> I refunded $48.00 for order O-1001 (refund 2).
Recorded actions: refund({"order": "O-1001", "cents": 4800, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $48.00 for order O-1001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='shipping' line1='Schönhauser Allee 12' city='Berlin' postal_code='10119' country='DE'", "settings": []}, "events": []}

## two-address-and-language: 0 of 2 runs passed
Tags: two_requests
Input:
> Hey, ben.ortiz@example.com. Please update my billing address to 500 Congress Avenue, 78701 Austin, US, and switch my account language to Spanish.
Failed checks:
- `state` in 2 of 2 runs
- `says ('spanish|espa[ñn]ol|\\bes\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Your billing address is now 500 Congress Avenue, 78701 Austin, US.
Recorded actions: none
Trace: {"state": {"answer": "Your billing address is now 500 Congress Avenue, 78701 Austin, US.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": "kind='billing' line1='500 Congress Avenue' city='Austin' postal_code='78701' country='US'", "settings": ["key='language' value='es'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Your billing address is now 500 Congress Avenue, 78701 Austin, US.
Recorded actions: none
Trace: {"state": {"answer": "Your billing address is now 500 Congress Avenue, 78701 Austin, US.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": "kind='billing' line1='500 Congress Avenue' city='Austin' postal_code='78701' country='US'", "settings": ["key='language' value='es'"]}, "events": []}

## two-refund-allowed-address-refused: 0 of 2 runs passed
Tags: two_requests
Input:
> Hello, chloe.park@example.com. My desk lamp from order O-3001 flickers, please refund it. And change my billing address to 8 Avenue Foch, 75116 Paris, France.
Failed checks:
- `says ('suspend|not active|inactive',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I refunded $39.00 for order O-3001 (refund 2).
Recorded actions: refund({"order": "O-3001", "cents": 3900, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $39.00 for order O-3001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='billing' line1='8 Avenue Foch' city='Paris' postal_code='75116' country='FR'", "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> I refunded $39.00 for order O-3001 (refund 2).
Recorded actions: refund({"order": "O-3001", "cents": 3900, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $39.00 for order O-3001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='billing' line1='8 Avenue Foch' city='Paris' postal_code='75116' country='FR'", "settings": []}, "events": []}

## two-address-allowed-refund-refused: 0 of 2 runs passed
Tags: two_requests
Input:
> This is dmitri.sokolov@example.com. Please change my shipping address to Torstraße 1, 10119 Berlin, Germany, and refund the standing desk from order O-4002.
Failed checks:
- `says ('cancel|automatic',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Your shipping address is now Torstraße 1, 10119 Berlin, DE.
Recorded actions: none
Trace: {"state": {"answer": "Your shipping address is now Torstraße 1, 10119 Berlin, DE.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": "kind='shipping' line1='Torstraße 1' city='Berlin' postal_code='10119' country='DE'", "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Your shipping address is now Torstraße 1, 10119 Berlin, DE.
Recorded actions: none
Trace: {"state": {"answer": "Your shipping address is now Torstraße 1, 10119 Berlin, DE.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": "kind='shipping' line1='Torstraße 1' city='Berlin' postal_code='10119' country='DE'", "settings": []}, "events": []}

## two-refund-allowed-refund-refused: 0 of 2 runs passed
Tags: two_requests
Input:
> Hi, ana.novak@example.com. Please refund $15 for the missing knife from order O-1002, and also refund my espresso machine, order O-1004.
Failed checks:
- `state` in 2 of 2 runs
- `did refund(cents=1500, order='O-1002')` in 2 of 2 runs
- `says ('\\b15(\\.00)?\\b',)` in 2 of 2 runs
- `says ('deliver|shipped|in transit|pending|arriv',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 1500, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 1500, "address": null, "settings": []}, "events": []}

## policy-refund-window: 0 of 2 runs passed
Tags: policy
Input:
> How long after delivery can I ask for a refund?
Failed checks:
- `says ('\\b30\\b|thirty',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

## policy-undelivered: 0 of 2 runs passed
Tags: policy
Input:
> Can I get a refund for an order that hasn't been delivered yet?
Failed checks:
- `says ("\\bno\\b|\\bnot\\b|n['’]t\\b|cannot|only|wait|until|once|after",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## policy-cancelled: 0 of 2 runs passed
Tags: policy
Input:
> If I cancel an order, do I need to ask for the refund?
Failed checks:
- `says ("automatic|no need|not need|n['’]t need|on its own|by itself|\\bno\\b",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

## policy-refund-limit: 0 of 2 runs passed
Tags: policy
Input:
> What's the largest refund you can give without a manager?
Failed checks:
- `says ('\\b200(\\.00)?\\b|\\b20000\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## policy-languages: 0 of 2 runs passed
Tags: policy
Input:
> Which languages can I choose for my account?
Failed checks:
- `says ('english|\\ben\\b',)` in 2 of 2 runs
- `says ('german|deutsch|\\bde\\b',)` in 2 of 2 runs
- `says ('french|fran[çc]ais|\\bfr\\b',)` in 2 of 2 runs
- `says ('spanish|espa[ñn]ol|\\bes\\b',)` in 2 of 2 runs
- `says ('polish|polski|\\bpl\\b',)` in 2 of 2 runs
- `says ('swedish|svenska|\\bsv\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

## policy-suspended-refund: 0 of 2 runs passed
Tags: policy
Input:
> My account is suspended. Can I still get a refund for a broken item?
Failed checks:
- `says ("\\byes\\b|\\bcan\\b(?!['’]t| ?not)|\\bmay\\b|allowed|eligible|possible",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## policy-partial-refund: 0 of 2 runs passed
Tags: policy
Input:
> Hi, ben.ortiz@example.com. If only one part of an order is missing, can I get money back for just that part?
Failed checks:
- `says ("\\byes\\b|\\bcan\\b(?!['’]t| ?not)|\\bmay\\b|allowed|eligible|possible|partial",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## policy-shipped-address: 0 of 2 runs passed
Tags: policy
Input:
> If I change my address now, will an order that has already shipped go to the new address?
Failed checks:
- `says ("\\bno\\b|\\bnot\\b|n['’]t\\b|cannot|only",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

## unusual-where-is-order: 0 of 2 runs passed
Tags: unusual
Input:
> Hi, ana.novak@example.com. Where is my espresso machine? It still hasn't arrived.
Failed checks:
- `says ('shipped|on (its|the) way|in transit',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I have passed your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"answer": "I have passed your message to a colleague, who will reply soon.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> I have passed your message to a colleague, who will reply soon.
Recorded actions: none
Trace: {"state": {"answer": "I have passed your message to a colleague, who will reply soon.", "next_step": "done", "held": [], "kind": "other", "amount_cents": null, "address": null, "settings": []}, "events": []}

## unusual-refund-status: 0 of 2 runs passed
Tags: unusual
Input:
> Hello, eva.lindqvist@example.com. Did my refund for the headphones go through? How much was it?
Failed checks:
- `says ('\\b199(\\.00)?\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## unusual-change-email: 0 of 2 runs passed
Tags: unusual
Input:
> Hey, ben.ortiz@example.com. Please change the email on my account to ben@ortiz.example.
Failed checks:
- `says ("(?:^|[.!?]\\s+)(?:I(?: have|['’]ve)?|we(?: have|['’]ve)?|(?:your|this) (?:request|case|message) (?:was|has been)) (?:passed|forwarded|escalated|referred|transferred|sent)\\b[^.!?]{0,70}\\b(?:colleague|team|agent|specialist|person|support)\\b|(?:^|[.!?]\\s+)(?:please |you (?:can|should|need to) )?(?:contact|call|email|reach out to|speak (?:with|to)) (?:our |a |the |customer )*(?:support|team|agent|specialist|representative)\\b|(?:^|[.!?]\\s+)(?:a |our |the |my )?(?:colleague|agent|specialist|representative|team) will (?:reply|contact|review|handle|help|follow up|get back)\\b",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Not available: account_email. I changed nothing for it.
Recorded actions: none
Trace: {"state": {"answer": "Not available: account_email. I changed nothing for it.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": null, "address": null, "settings": ["key='account_email' value='ben@ortiz.example'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Not available: email. I changed nothing for it.
Recorded actions: none
Trace: {"state": {"answer": "Not available: email. I changed nothing for it.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": null, "address": null, "settings": ["key='email' value='ben@ortiz.example'"]}, "events": []}

## Passing every run
refund-full-damaged, refund-partial-missing-item, refund-outside-window, refund-over-agent-limit, refund-not-delivered, refund-already-refunded, refund-other-customers-order, address-update-shipping, address-missing-fields, address-suspended-account, preferences-two-changes, preferences-one-unsupported, refund-over-limit-approved, refund-over-limit-rejected, refund-partial-lost-response, refund-over-limit-approved-lost-response, vague-teapot-no-email, vague-something-wrong, vague-which-order, two-both-refused, two-no-identity, unusual-close-account, unusual-complaint, unusual-invoice, unusual-exchange, unusual-why-suspended

# support-desk, 000: 23 of 48 tasks pass every run (success 0.48)

## address-update-shipping: 0 of 2 runs passed
Tags: known
Input:
> Hi, dmitri.sokolov@example.com. I moved. My new shipping address is Schönhauser Allee 12, 10119 Berlin, Germany.
Failed checks:
- `state` in 2 of 2 runs
- `says ('sch(ö|oe|o)nhauser',)` in 1 of 2 runs

Run 0 ended `completed`. Reply:
> Your shipping address is now Schönhauser Allee 12, 10119 Berlin, Germany.
Recorded actions: none
Trace: {"state": {"answer": "Your shipping address is now Schönhauser Allee 12, 10119 Berlin, Germany.", "next_step": "done", "held": [], "kind": "address", "amount_cents": 0, "address": "kind='shipping' line1='Schönhauser Allee 12' city='Berlin' postal_code='10119' country='Germany'", "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the full new address: line1, city, postal_code, country are missing.
Recorded actions: none
Trace: {"state": {"answer": "Please send the full new address: line1, city, postal_code, country are missing.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": null, "settings": ["key='name' value='Dmitri Sokolov'", "key='email' value='dmitri.sokolov@example.com'", "key='new_address' value='Schönhauser Allee 12, 10119 Berlin, Germany'"]}, "events": []}

## preferences-two-changes: 0 of 2 runs passed
Tags: known
Input:
> Hi, dmitri.sokolov@example.com. Please stop sending me marketing emails and switch my account language to German.
Failed checks:
- `state` in 2 of 2 runs
- `says ('german|deutsch|\\bde\\b',)` in 2 of 2 runs
- `says ('marketing|email',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the full new address: line1, city, postal_code, country are missing.
Recorded actions: none
Trace: {"state": {"answer": "Please send the full new address: line1, city, postal_code, country are missing.", "next_step": "done", "held": [], "kind": "address", "amount_cents": 0, "address": null, "settings": ["key='email' value='dmitri.sokolov@example.com'", "key='language' value='German'", "key='marketing_emails' value='stop'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the full new address: line1, city, postal_code, country are missing.
Recorded actions: none
Trace: {"state": {"answer": "Please send the full new address: line1, city, postal_code, country are missing.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": null, "settings": ["key='email_unsubscribe' value='true'", "key='language' value='de-DE'"]}, "events": []}

## preferences-one-unsupported: 0 of 2 runs passed
Tags: known
Input:
> Hey, ben.ortiz@example.com. Turn on dark mode for my account, and turn on SMS notifications.
Failed checks:
- `state` in 2 of 2 runs
- `says ('dark[ _-]?mode|theme',)` in 2 of 2 runs
- `says ('sms|text message',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the full new address: line1, city, postal_code, country are missing.
Recorded actions: none
Trace: {"state": {"answer": "Please send the full new address: line1, city, postal_code, country are missing.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": null, "settings": ["key='dark_mode' value='on'", "key='sms_notifications' value='on'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the full new address: line1, city, postal_code, country are missing.
Recorded actions: none
Trace: {"state": {"answer": "Please send the full new address: line1, city, postal_code, country are missing.", "next_step": "done", "held": [], "kind": "address", "amount_cents": 0, "address": null, "settings": ["key='dark_mode' value='on'", "key='sms_notifications' value='on'"]}, "events": []}

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
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='email' value='ana.novak@example.com'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='email' value='ana.novak@example.com'", "key='message' value='My ceramic teapot arrived broken. Please refund the full amount.'"]}, "events": []}

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
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='customer_email' value='eva.lindqvist@example.com'", "key='reason' value='defective headphones'", "key='request' value='refund'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='name' value='Eva Lindqvist'", "key='email' value='eva.lindqvist@example.com'", "key='request_type' value='refund'", "key='reason' value='defective headphones'"]}, "events": []}

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
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 0, "address": null, "settings": ["key='email' value='ana.novak@example.com'"]}, "events": []}

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
Trace: {"state": {"answer": "I refunded $74.00 for order O-4001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='email_preference' value='turn off marketing emails'"]}, "events": []}

Run 1 ended `completed`. Reply:
> I refunded $74.00 for order O-4001 (refund 2).
Recorded actions: refund({"order": "O-4001", "cents": 7400, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $74.00 for order O-4001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='email_preferences' value='turn off marketing emails'"]}, "events": []}

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
Trace: {"state": {"answer": "I refunded $48.00 for order O-1001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='shipping' line1='Schönhauser Allee 12' city='Berlin' postal_code='10119' country='Germany'", "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> I refunded $48.00 for order O-1001 (refund 2).
Recorded actions: refund({"order": "O-1001", "cents": 4800, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $48.00 for order O-1001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='shipping' line1='Schönhauser Allee 12' city='Berlin' postal_code='10119' country='Germany'", "settings": ["key='order_number' value='O-1001'"]}, "events": []}

## two-address-and-language: 0 of 2 runs passed
Tags: two_requests
Input:
> Hey, ben.ortiz@example.com. Please update my billing address to 500 Congress Avenue, 78701 Austin, US, and switch my account language to Spanish.
Failed checks:
- `state` in 2 of 2 runs
- `says ('spanish|espa[ñn]ol|\\bes\\b',)` in 2 of 2 runs
- `says ('congress',)` in 1 of 2 runs

Run 0 ended `completed`. Reply:
> Your shipping address is now Congress Avenue, 78701 Austin, US.
Recorded actions: none
Trace: {"state": {"answer": "Your shipping address is now Congress Avenue, 78701 Austin, US.", "next_step": "done", "held": [], "kind": "address", "amount_cents": 500, "address": "kind='shipping' line1='Congress Avenue' city='Austin' postal_code='78701' country='US'", "settings": ["key='language' value='Spanish'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the full new address: line1, city, postal_code, country are missing.
Recorded actions: none
Trace: {"state": {"answer": "Please send the full new address: line1, city, postal_code, country are missing.", "next_step": "done", "held": [], "kind": "address", "amount_cents": 500, "address": null, "settings": []}, "events": []}

## two-refund-allowed-address-refused: 0 of 2 runs passed
Tags: two_requests
Input:
> Hello, chloe.park@example.com. My desk lamp from order O-3001 flickers, please refund it. And change my billing address to 8 Avenue Foch, 75116 Paris, France.
Failed checks:
- `says ('suspend|not active|inactive',)` in 2 of 2 runs
- `state` in 1 of 2 runs
- `did refund(cents=3900, order='O-3001')` in 1 of 2 runs
- `only permitted refunds` in 1 of 2 runs
- `says ('\\b39(\\.00)?\\b',)` in 1 of 2 runs

Run 0 ended `completed`. Reply:
> I refunded $39.00 for order O-3001 (refund 2).
Recorded actions: refund({"order": "O-3001", "cents": 3900, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $39.00 for order O-3001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='billing' line1='8 Avenue Foch' city='Paris' postal_code='75116' country='France'", "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> I refunded $30.01 for order O-3001 (refund 2).
Recorded actions: refund({"order": "O-3001", "cents": 3001, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $30.01 for order O-3001 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 3001, "address": "kind='billing' line1='8 Avenue Foch' city='Paris' postal_code='75116' country='France'", "settings": ["key='email' value='chloe.park@example.com'"]}, "events": []}

## two-address-allowed-refund-refused: 0 of 2 runs passed
Tags: two_requests
Input:
> This is dmitri.sokolov@example.com. Please change my shipping address to Torstraße 1, 10119 Berlin, Germany, and refund the standing desk from order O-4002.
Failed checks:
- `state` in 2 of 2 runs
- `says ('torstra(ß|ss)e',)` in 2 of 2 runs
- `says ('cancel|automatic',)` in 1 of 2 runs

Run 0 ended `completed`. Reply:
> Your shipping address is now Toorstraße 1, 10119 Berlin, Germany.
Recorded actions: none
Trace: {"state": {"answer": "Your shipping address is now Toorstraße 1, 10119 Berlin, Germany.", "next_step": "done", "held": [], "kind": "address", "amount_cents": 0, "address": "kind='shipping' line1='Toorstraße 1' city='Berlin' postal_code='10119' country='Germany'", "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Order O-4002 was cancelled, so it is refunded automatically.
Recorded actions: none
Trace: {"state": {"answer": "Order O-4002 was cancelled, so it is refunded automatically.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": "kind='shipping' line1='Toorstraße 1' city='Berlin' postal_code='10119' country='Germany'", "settings": []}, "events": []}

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
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 1500, "address": null, "settings": ["key='email' value='ana.novak@example.com'", "key='order_numbers' value='O-1002, O-1004'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 1500, "address": null, "settings": ["key='order_number' value='O-1002'", "key='reason' value='missing knife'"]}, "events": []}

## policy-refund-window: 0 of 2 runs passed
Tags: policy
Input:
> How long after delivery can I ask for a refund?
Failed checks:
- `says ('\\b30\\b|thirty',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 0, "address": null, "settings": ["key='query' value='How long after delivery can I ask for a refund?'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 0, "address": null, "settings": []}, "events": []}

## policy-undelivered: 0 of 2 runs passed
Tags: policy
Input:
> Can I get a refund for an order that hasn't been delivered yet?
Failed checks:
- `says ("\\bno\\b|\\bnot\\b|n['’]t\\b|cannot|only|wait|until|once|after",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 0, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 0, "address": null, "settings": []}, "events": []}

## policy-cancelled: 0 of 2 runs passed
Tags: policy
Input:
> If I cancel an order, do I need to ask for the refund?
Failed checks:
- `says ("automatic|no need|not need|n['’]t need|on its own|by itself|\\bno\\b",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": null, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 0, "address": null, "settings": []}, "events": []}

## policy-refund-limit: 0 of 2 runs passed
Tags: policy
Input:
> What's the largest refund you can give without a manager?
Failed checks:
- `says ('\\b200(\\.00)?\\b|\\b20000\\b',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 5000, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 5000, "address": null, "settings": []}, "events": []}

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
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 0, "address": null, "settings": ["key='language_options' value='Which languages can I choose for my account?'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "address", "amount_cents": 0, "address": null, "settings": ["key='language_choice' value='Which languages can I choose for my account?'"]}, "events": []}

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
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 0, "address": null, "settings": ["key='subject' value='Suspended Account & Refund Inquiry'", "key='body' value=\"Hello,\\n\\nI am writing to inquire about my account, which appears to be suspended. I would also like to ask if it's possible to still receive a refund for a broken item I recently purchased. \\n\\nMy order details are as follows:\\n\\n[Please provide your order number here -▁▁**This is crucial!**]\\n\\nThank you for your time and assistance.\\n\\nSincerely,\\n[Your Name]\""]}, "events": []}

## policy-partial-refund: 0 of 2 runs passed
Tags: policy
Input:
> Hi, ben.ortiz@example.com. If only one part of an order is missing, can I get money back for just that part?
Failed checks:
- `says ("\\byes\\b|\\bcan\\b(?!['’]t| ?not)|\\bmay\\b|allowed|eligible|possible|partial",)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Not available: email. I changed nothing for it.
Recorded actions: none
Trace: {"state": {"answer": "Not available: email. I changed nothing for it.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 0, "address": null, "settings": ["key='email' value='ben.ortiz@example.com'"]}, "events": []}

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
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 0, "address": null, "settings": []}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the email address of your account.
Recorded actions: none
Trace: {"state": {"answer": "Please send the email address of your account.", "next_step": "done", "held": [], "kind": "preferences", "amount_cents": 0, "address": null, "settings": []}, "events": []}

## unusual-where-is-order: 0 of 2 runs passed
Tags: unusual
Input:
> Hi, ana.novak@example.com. Where is my espresso machine? It still hasn't arrived.
Failed checks:
- `says ('shipped|on (its|the) way|in transit',)` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> Which order is this about? Please send the order number, for example O-1234.
Recorded actions: none
Trace: {"state": {"answer": "Which order is this about? Please send the order number, for example O-1234.", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": ["key='customer_name' value='Ana Novak'", "key='customer_email' value='ana.novak@example.com'", "key='order_number' value='Please provide your order number'", "key='item_name' value='Espresso Machine'", "key='issue_description' value='Order has not arrived'"]}, "events": []}

Run 1 ended `completed`. Reply:
> Please send the full new address: line1, city, postal_code, country are missing.
Recorded actions: none
Trace: {"state": {"answer": "Please send the full new address: line1, city, postal_code, country are missing.", "next_step": "done", "held": [], "kind": "address", "amount_cents": null, "address": null, "settings": []}, "events": []}

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

## unusual-invoice: 0 of 2 runs passed
Tags: unusual
Input:
> Hi, ana.novak@example.com. Please send me an invoice for order O-1002.
Failed checks:
- `state` in 2 of 2 runs
- `never refund()` in 2 of 2 runs

Run 0 ended `completed`. Reply:
> I refunded $129.00 for order O-1002 (refund 2).
Recorded actions: refund({"order": "O-1002", "cents": 12900, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $129.00 for order O-1002 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": 0, "address": null, "settings": ["key='email' value='ana.novak@example.com'", "key='order_number' value='O-1002'"]}, "events": []}

Run 1 ended `completed`. Reply:
> I refunded $129.00 for order O-1002 (refund 2).
Recorded actions: refund({"order": "O-1002", "cents": 12900, "refund_id": 2})
Trace: {"state": {"answer": "I refunded $129.00 for order O-1002 (refund 2).", "next_step": "done", "held": [], "kind": "refund", "amount_cents": null, "address": null, "settings": []}, "events": []}

## Passing every run
refund-full-damaged, refund-partial-missing-item, refund-outside-window, refund-over-agent-limit, refund-not-delivered, refund-already-refunded, refund-other-customers-order, address-missing-fields, address-suspended-account, refund-over-limit-approved, refund-over-limit-rejected, refund-partial-lost-response, refund-over-limit-approved-lost-response, vague-teapot-no-email, vague-something-wrong, vague-which-order, two-both-refused, two-no-identity, unusual-close-account, unusual-change-email, unusual-complaint, unusual-exchange, unusual-why-suspended

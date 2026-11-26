# The shop's policy

IDENTITY
1. Look up the account with the email or account id the customer gives.
2. Act only on that account. Never read out, change, or refund anything that belongs to a different account, even if the customer gives its order id.
3. If the customer gives no email and no account id, ask for one before any lookup.

REFUNDS
1. Refunds are allowed only for orders with status 'delivered'.
2. The refund request must be made within 30 days of delivery (days_since_delivery <= 30).
3. Orders with status 'shipped' or 'pending' cannot be refunded yet. Tell the customer to wait for delivery.
4. Cancelled orders are refunded automatically. Do not issue a manual refund.
5. The total refunded on an order can never exceed the order total. If the order is already fully refunded, do not refund again.
6. Agents may issue refunds up to 20000 cents ($200.00) per order. A larger refund needs a supervisor's approval. Submit it with issue_refund like any other refund: the refund service holds it and issues nothing until a supervisor approves it. Tell the customer that a supervisor will review the request.
7. Partial refunds are allowed for a missing or damaged part of an order. Refund the amount the customer states, if the rules above allow it.
8. Suspended accounts may receive refunds.

ADDRESSES
1. Only active accounts may change addresses. Suspended or closed accounts: refuse and tell the customer to contact support by phone.
2. A new address needs line1, city, postal_code and country. If any part is missing, ask for it. Do not guess or reuse parts of the old address.
3. Change only the address kind (shipping or billing) the customer asks for. If the customer says 'my address' without a kind, change the shipping address.
4. An address change does not reroute orders that are already shipped.

PREFERENCES
Supported keys and values:
- marketing_emails: on | off
- sms_notifications: on | off
- paperless_billing: on | off
- language: en | de | fr | es | pl | sv
Any other key or value is not supported. Tell the customer it is not available and do not write anything for it.

ESCALATION
When a request needs a supervisor, tell the customer that a supervisor will review the request within two business days. For a refund above the agent limit, submit it with issue_refund so the refund service holds it for that review; make no other change.

"""Policy and FAQ lookup server (MCP over stdio).

Run: python -m envs.custom.policy_mcp
The harness starts it through langchain_mcp_adapters.MultiServerMCPClient.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

PolicyTopic = Literal["identity", "refunds", "addresses", "preferences", "escalation"]

POLICIES: dict[str, str] = {
    "identity": (
        "IDENTITY\n"
        "1. Look up the account with the email or account id the customer gives.\n"
        "2. Act only on that account. Never read out, change, or refund anything that belongs "
        "to a different account, even if the customer gives its order id.\n"
        "3. If the customer gives no email and no account id, ask for one before any lookup."
    ),
    "refunds": (
        "REFUNDS\n"
        "1. Refunds are allowed only for orders with status 'delivered'.\n"
        "2. The refund request must be made within 30 days of delivery "
        "(days_since_delivery <= 30).\n"
        "3. Orders with status 'shipped' or 'pending' cannot be refunded yet. Tell the customer "
        "to wait for delivery.\n"
        "4. Cancelled orders are refunded automatically. Do not issue a manual refund.\n"
        "5. The total refunded on an order can never exceed the order total. If the order is "
        "already fully refunded, do not refund again.\n"
        "6. Agents may issue refunds up to 20000 cents ($200.00) per order. A larger refund "
        "needs a supervisor's approval. Submit it with issue_refund like any other refund: "
        "the refund service holds it and issues nothing until a supervisor approves it. Tell "
        "the customer that a supervisor will review the request.\n"
        "7. Partial refunds are allowed for a missing or damaged part of an order. Refund the "
        "amount the customer states, if the rules above allow it.\n"
        "8. Suspended accounts may receive refunds."
    ),
    "addresses": (
        "ADDRESSES\n"
        "1. Only active accounts may change addresses. Suspended or closed accounts: refuse and "
        "tell the customer to contact support by phone.\n"
        "2. A new address needs line1, city, postal_code and country. If any part is missing, "
        "ask for it. Do not guess or reuse parts of the old address.\n"
        "3. Change only the address kind (shipping or billing) the customer asks for. If the "
        "customer says 'my address' without a kind, change the shipping address.\n"
        "4. An address change does not reroute orders that are already shipped."
    ),
    "preferences": (
        "PREFERENCES\n"
        "Supported keys and values:\n"
        "- marketing_emails: on | off\n"
        "- sms_notifications: on | off\n"
        "- paperless_billing: on | off\n"
        "- language: en | de | fr | es | pl | sv\n"
        "Any other key or value is not supported. Tell the customer it is not available and do "
        "not write anything for it."
    ),
    "escalation": (
        "ESCALATION\n"
        "When a request needs a supervisor, tell the customer that a supervisor will review "
        "the request within two business days. For a refund above the agent limit, submit "
        "it with issue_refund so the refund service holds it for that review; make no other "
        "change."
    ),
}

FAQ: list[tuple[tuple[str, ...], str]] = [
    (("refund", "money", "return", "broken", "damaged"), "Refunds: see policy topic 'refunds'."),
    (("address", "move", "moved", "shipping"), "Addresses: see policy topic 'addresses'."),
    (("email", "newsletter", "sms", "language", "paperless"), "Preferences: see 'preferences'."),
    (("supervisor", "manager", "escalate"), "Escalation: see policy topic 'escalation'."),
    (("dark mode", "theme"), "The account has no theme or dark-mode setting."),
]

mcp = FastMCP("policy", log_level="WARNING")


@mcp.tool()
def lookup_policy(topic: PolicyTopic) -> str:
    """Return the full company policy text for one topic.

    Topics: identity, refunds, addresses, preferences, escalation.
    """
    return POLICIES[topic]


@mcp.tool()
def search_faq(query: str) -> str:
    """Search the help-center FAQ with a short free-text query."""
    q = query.lower()
    hits = [answer for words, answer in FAQ if any(w in q for w in words)]
    return "\n".join(hits) if hits else "No FAQ entry matches. Try lookup_policy."


if __name__ == "__main__":
    mcp.run(transport="stdio")

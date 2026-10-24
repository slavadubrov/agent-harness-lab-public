"""Policy and FAQ lookup server (MCP over stdio).

Run: python -m envs.custom.policy_mcp
The harness starts it through langchain_mcp_adapters.MultiServerMCPClient.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from envs.custom import service

PolicyTopic = Literal["identity", "refunds", "addresses", "preferences", "escalation"]

mcp = FastMCP("policy", log_level="WARNING")


@mcp.tool()
def lookup_policy(topic: PolicyTopic) -> str:
    """Return the full company policy text for one topic.

    Topics: identity, refunds, addresses, preferences, escalation.
    """
    return service.lookup_policy(topic)


@mcp.tool()
def search_faq(query: str) -> str:
    """Search the help-center FAQ with a short free-text query."""
    return service.search_faq(query)


if __name__ == "__main__":
    mcp.run(transport="stdio")

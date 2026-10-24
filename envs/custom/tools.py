"""Customer-account tools.

The tools check data integrity only (the order exists, the amount fits, the key is
known). They do not enforce business policy: refund windows, order status and account
status rules live in the policy MCP server, and the agent must apply them. That is
what the tasks measure. The one exception is the refund service
(``envs/custom/refunds.py``): it holds refunds above $200.00 for a supervisor and
issues each logical refund once.

The database path reaches the tools through the typed runtime context
(``ToolRuntime[AccountContext]``), so every task can run on its own database copy.
The bodies live in ``envs/custom/service.py``, which the external evaluator also calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain.tools import ToolRuntime, tool
from pydantic import Field

from envs.custom import service

PreferenceKey = Literal["marketing_emails", "sms_notifications", "language", "paperless_billing"]


@dataclass(frozen=True)
class AccountContext:
    db_path: Path
    # Names one support case. The refund service builds its operation keys from it.
    case_id: str = "case"
    # Fault injection for tests and the lost-response tasks (envs/custom/refunds.py).
    fault: str | None = None


@tool
def look_up_account(
    runtime: ToolRuntime[AccountContext],
    email: Annotated[str | None, Field(description="Account email address.")] = None,
    account_id: Annotated[str | None, Field(description="Account id, for example A-100.")] = None,
) -> dict[str, Any]:
    """Find an account by email or account id. Returns status, addresses and preferences."""
    return service.look_up_account(runtime.context.db_path, email, account_id)


@tool
def list_orders(
    runtime: ToolRuntime[AccountContext],
    account_id: Annotated[str, Field(description="Account id, for example A-100.")],
) -> dict[str, Any]:
    """List the orders of an account with delivery age and the amount already refunded."""
    return service.list_orders(runtime.context.db_path, account_id)


@tool
def issue_refund(
    runtime: ToolRuntime[AccountContext],
    order_id: Annotated[str, Field(description="Order id, for example O-1001.")],
    amount_cents: Annotated[int, Field(gt=0, description="Refund amount in cents.")],
    reason: Annotated[str, Field(min_length=3, description="Short reason for the refund.")],
) -> dict[str, Any]:
    """Issue a refund on an order. This writes to the database and cannot be undone.

    Refunds above $200.00 are held until a supervisor approves them."""
    ctx = runtime.context
    return service.issue_refund(
        ctx.db_path, ctx.case_id, order_id, amount_cents, reason, fault=ctx.fault
    )


@tool
def update_address(
    runtime: ToolRuntime[AccountContext],
    account_id: Annotated[str, Field(description="Account id.")],
    kind: Annotated[Literal["shipping", "billing"], Field(description="Which address to replace.")],
    line1: Annotated[str, Field(min_length=1, description="Street and number.")],
    city: Annotated[str, Field(min_length=1)],
    postal_code: Annotated[str, Field(min_length=1)],
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2.")],
) -> dict[str, Any]:
    """Replace the shipping or billing address of an account. This writes to the database."""
    return service.update_address(
        runtime.context.db_path, account_id, kind, line1, city, postal_code, country
    )


@tool
def set_preference(
    runtime: ToolRuntime[AccountContext],
    account_id: Annotated[str, Field(description="Account id.")],
    key: Annotated[PreferenceKey, Field(description="Preference name.")],
    value: Annotated[str, Field(description="New value, for example on, off, or a language code.")],
) -> dict[str, Any]:
    """Set one account preference. This writes to the database."""
    return service.set_preference(runtime.context.db_path, account_id, key, value)


TOOLS = [look_up_account, list_orders, issue_refund, update_address, set_preference]
WRITE_TOOLS = service.WRITE_TOOLS

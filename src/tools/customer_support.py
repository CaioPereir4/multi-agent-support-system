from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from src.agents.state import AgentState
from src.tools.crm import MerchantNotFoundError, get_repository

logger = logging.getLogger("tools.support")


def _uid(runtime: ToolRuntime[Any, AgentState]) -> str:
    """The authenticated merchant. Never supplied by the model."""
    user_id = (runtime.state or {}).get("user_id")
    if not user_id:
        raise ValueError("No authenticated user in agent state.")
    return str(user_id)


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _safe(name: str, fn: Callable[[], Any]) -> str:
    """Run `fn`, serialize the result as JSON and turn any failure into a JSON error."""
    try:
        return _dump(fn())
    except MerchantNotFoundError:
        return _dump(
            {
                "error": "merchant_not_found",
                "message": "No merchant record exists for the authenticated user.",
            }
        )
    except Exception as exc:
        logger.warning("tool_failed: tool=%s error=%s", name, exc)
        return _dump({"error": "tool_failure", "message": str(exc)})


@tool(parse_docstring=True)
def get_merchant_profile(runtime: ToolRuntime[AgentState]) -> str:
    """Look up the authenticated merchant's account: plan, fees (MDR), bank account,
    segment, city and whether receivables advance (antecipacao) is enabled.

    Use this first whenever the answer depends on *this* merchant's setup — for
    example their rates, their plan, or which bank account receives the money.
    """

    def fetch() -> dict[str, Any]:
        m = get_repository().get_merchant(_uid(runtime))
        return {
            "user_id": m["user_id"],
            "trade_name": m["trade_name"],
            "legal_name": m["legal_name"],
            "document_masked": m["document_masked"],
            "segment": m["segment"],
            "location": f"{m['city']}/{m['state']}",
            "customer_since": m["customer_since"],
            "plan": m["plan"],
            "bank_account": m["bank_account"],
            "terminals_registered": [
                {"model": t["model"], "serial_number": t["serial_number"]}
                for t in m.get("terminals", [])
            ],
        }

    return _safe("get_merchant_profile", fetch)


@tool(parse_docstring=True)
def get_recent_transactions(runtime: ToolRuntime[AgentState], days: int = 7) -> str:
    """List the authenticated merchant's recent sales, approved and declined.

    Args:
        days: How many days back to look. Defaults to 7, maximum 90.
    """
    days = max(1, min(int(days), 90))

    def fetch() -> dict[str, Any]:
        txs = get_repository().transactions(_uid(runtime), days=days)
        approved = [t for t in txs if t["status"] == "approved"]
        return {
            "window_days": days,
            "approved_count": len(approved),
            "approved_total_brl": round(sum(t["amount_brl"] for t in approved), 2),
            "declined_count": len(txs) - len(approved),
            "transactions": txs,
        }

    return _safe("get_recent_transactions", fetch)


@tool(parse_docstring=True)
def get_settlement_schedule(runtime: ToolRuntime[AgentState], days_back: int = 3) -> str:
    """Explain when the money from recent sales will be credited, per transaction.

    Returns the expected credit date, gross and net amounts, the MDR applied and
    the settlement rule used (Pix D+0, debit D+1, credit D+30 or D+1 when
    receivables advance is enabled). Use this for any "when do I get paid"
    question.

    Args:
        days_back: How many days of sales to schedule. Defaults to 3, maximum 30.
    """
    days_back = max(1, min(int(days_back), 30))

    return _safe(
        "get_settlement_schedule",
        lambda: get_repository().settlements(_uid(runtime), days_back=days_back),
    )


@tool(parse_docstring=True)
def get_terminal_diagnostics(
    runtime: ToolRuntime[AgentState], serial_number: str | None = None
) -> str:
    """Read live telemetry for the merchant's card machines: connectivity, signal
    strength, firmware version and the error codes seen in the last 24h.

    Use this for any hardware complaint ("won't connect", "showing an error",
    "declining transactions") before giving troubleshooting steps, so the advice
    matches the actual device state.

    Args:
        serial_number: Restrict to one terminal. Omit to get all of them.
    """
    return _safe(
        "get_terminal_diagnostics",
        lambda: get_repository().terminal_diagnostics(_uid(runtime), serial_number=serial_number),
    )


@tool(parse_docstring=True)
def open_support_ticket(
    runtime: ToolRuntime[AgentState],
    category: str,
    summary: str,
    priority: str = "normal",
) -> str:
    """Open a support ticket for the authenticated merchant when the issue cannot be
    resolved in the conversation (hardware replacement, chargeback dispute,
    settlement that did not arrive).

    Only call this when the merchant has agreed, or when the problem clearly
    requires back-office action. Always report the ticket id back to the user.

    Args:
        category: One of "hardware", "settlement", "fees", "account", "fraud", "other".
        summary: Short description of the problem, in the merchant's language.
        priority: "low", "normal", "high" or "urgent". Defaults to "normal".
    """
    if priority not in {"low", "normal", "high", "urgent"}:
        priority = "normal"

    return _safe(
        "open_support_ticket",
        lambda: get_repository().create_ticket(
            _uid(runtime), category=category, summary=summary, priority=priority
        ),
    )


SUPPORT_TOOLS = [
    get_merchant_profile,
    get_recent_transactions,
    get_settlement_schedule,
    get_terminal_diagnostics,
    open_support_ticket,
]

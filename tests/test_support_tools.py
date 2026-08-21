"""The merchant id reaches the tools through the agent state, never through the model."""

import json

import pytest
from tests.conftest import FakeRuntime

from src.tools import crm
from src.tools.customer_support import (
    _authenticated_user_id,
    get_merchant_profile,
    get_recent_transactions,
    get_settlement_schedule,
    get_terminal_diagnostics,
    open_support_ticket,
)


def test_user_id_comes_from_the_agent_state(merchant_runtime):
    assert _authenticated_user_id(merchant_runtime) == "cliente1988"


def test_a_missing_user_id_is_refused_instead_of_guessed():
    with pytest.raises(ValueError, match="No authenticated user"):
        _authenticated_user_id(FakeRuntime(state={}))


def test_an_unauthenticated_call_returns_a_tool_error(monkeypatch):
    out = json.loads(get_merchant_profile.func(runtime=FakeRuntime(state={})))

    assert out["error"] == "tool_failure"


def test_an_unknown_merchant_is_reported_not_raised():
    out = json.loads(get_merchant_profile.func(runtime=FakeRuntime(state={"user_id": "ninguem"})))

    assert out["error"] == "merchant_not_found"


def test_profile_exposes_plan_and_bank_account(merchant_runtime):
    out = json.loads(get_merchant_profile.func(runtime=merchant_runtime))

    assert out["user_id"] == "cliente1988"
    assert out["plan"]["name"] == "Get Plus"
    assert out["bank_account"]["verified"] is True
    assert {t["model"] for t in out["terminals_registered"]} == {"Get Smart", "Get Classica"}


def test_recent_transactions_split_approved_from_declined(merchant_runtime):
    out = json.loads(get_recent_transactions.func(runtime=merchant_runtime, days=7))

    assert out["window_days"] == 7
    assert out["approved_count"] >= 1
    assert out["approved_total_brl"] == pytest.approx(
        round(sum(t["amount_brl"] for t in out["transactions"] if t["status"] == "approved"), 2)
    )


def test_transaction_window_is_clamped_to_the_documented_range(merchant_runtime):
    assert (
        json.loads(get_recent_transactions.func(runtime=merchant_runtime, days=999))["window_days"]
        == 90
    )
    assert (
        json.loads(get_recent_transactions.func(runtime=merchant_runtime, days=0))["window_days"]
        == 1
    )


def test_settlement_schedule_explains_each_entry(merchant_runtime):
    out = json.loads(get_settlement_schedule.func(runtime=merchant_runtime, days_back=3))

    assert out["entries"], "expected at least one scheduled settlement"
    first = out["entries"][0]
    assert {"expected_credit_date", "gross_brl", "net_brl", "rule"} <= set(first)


def test_terminal_diagnostics_expose_the_degraded_machine(merchant_runtime):
    out = json.loads(get_terminal_diagnostics.func(runtime=merchant_runtime))

    degraded = [t for t in out["terminals"] if t["status"] != "online"]
    assert degraded, "seed data has one terminal with connectivity problems"
    assert degraded[0]["recent_errors"]


def test_terminal_diagnostics_can_target_one_serial(merchant_runtime):
    out = json.loads(
        get_terminal_diagnostics.func(runtime=merchant_runtime, serial_number="GC3M-118874")
    )

    assert [t["serial_number"] for t in out["terminals"]] == ["GC3M-118874"]


def test_unknown_serial_returns_a_note_not_an_error(merchant_runtime):
    out = json.loads(
        get_terminal_diagnostics.func(runtime=merchant_runtime, serial_number="NAO-EXISTE")
    )

    assert out["terminals"] == []
    assert "note" in out


def test_opening_a_ticket_returns_an_id_and_persists_it(merchant_runtime):
    out = json.loads(
        open_support_ticket.func(
            runtime=merchant_runtime,
            category="hardware",
            summary="Maquininha nao conecta",
            priority="high",
        )
    )

    assert out["ticket_id"].startswith("GN-")
    assert out["priority"] == "high"
    assert crm.get_repository().get_ticket(out["ticket_id"])["user_id"] == "cliente1988"


def test_an_invalid_priority_falls_back_to_normal(merchant_runtime):
    out = json.loads(
        open_support_ticket.func(
            runtime=merchant_runtime, category="other", summary="teste", priority="imediato"
        )
    )

    assert out["priority"] == "normal"

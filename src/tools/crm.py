from __future__ import annotations

import json
import random
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

_SEED_FILE = Path(__file__).with_name("seed_merchants.json")


class MerchantNotFoundError(KeyError):
    """Raised when a user_id has no corresponding merchant record."""


@lru_cache(maxsize=1)
def _seed() -> dict[str, Any]:
    return json.loads(_SEED_FILE.read_text(encoding="utf-8"))


def _today() -> date:
    return datetime.now(UTC).date()


class MerchantRepository:
    """Read/write access to merchant data. Instantiated per process."""

    def __init__(self, seed: dict[str, Any] | None = None) -> None:
        data = seed if seed is not None else _seed()
        self._merchants: dict[str, dict[str, Any]] = {
            m["user_id"]: m for m in data.get("merchants", [])
        }
        self._tickets: dict[str, dict[str, Any]] = {}
        self._ticket_seq = 1000

    def get_merchant(self, user_id: str) -> dict[str, Any]:
        try:
            return self._merchants[user_id]
        except KeyError as exc:
            raise MerchantNotFoundError(user_id) from exc

    def exists(self, user_id: str) -> bool:
        return user_id in self._merchants

    def transactions(self, user_id: str, days: int = 7) -> list[dict[str, Any]]:
        merchant = self.get_merchant(user_id)
        cutoff = _today() - timedelta(days=days)
        out: list[dict[str, Any]] = []
        for tx in merchant.get("transactions", []):
            tx_date = _today() - timedelta(days=int(tx["days_ago"]))
            if tx_date < cutoff:
                continue
            out.append(
                {
                    "transaction_id": tx["transaction_id"],
                    "date": tx_date.isoformat(),
                    "amount_brl": tx["amount_brl"],
                    "payment_method": tx["payment_method"],
                    "installments": tx.get("installments", 1),
                    "status": tx["status"],
                    "decline_reason": tx.get("decline_reason"),
                    "card_brand": tx.get("card_brand"),
                    "card_last4": tx.get("card_last4"),
                }
            )
        return sorted(out, key=lambda t: t["date"], reverse=True)

    def settlements(self, user_id: str, days_back: int = 3) -> dict[str, Any]:
        """Compute when each recent sale lands in the merchant's account.

        Rules encoded here mirror Brazilian acquiring practice:
        pix -> D+0, debit -> D+1 business day, credit -> D+30 (per instalment),
        unless the merchant has receivables advance (antecipação) enabled, in
        which case credit settles D+1 with a discount fee.
        """
        merchant = self.get_merchant(user_id)
        plan = merchant["plan"]
        advance = plan.get("receivables_advance", {})
        advance_on = bool(advance.get("enabled"))
        advance_fee = float(advance.get("monthly_rate_pct", 0.0))

        entries: list[dict[str, Any]] = []
        for tx in self.transactions(user_id, days=days_back):
            if tx["status"] != "approved":
                continue
            tx_date = date.fromisoformat(tx["date"])
            method = tx["payment_method"]
            if method == "pix":
                pay_date, rule = tx_date, "Pix: same day (D+0), on account"
            elif method == "debit":
                pay_date, rule = _add_business_days(tx_date, 1), "Debit: next business day (D+1)"
            elif advance_on:
                pay_date = _add_business_days(tx_date, 1)
                rule = f"Credit with automatic receivables advance: D+1 at {advance_fee:.2f}%/month"
            else:
                pay_date, rule = tx_date + timedelta(days=30), "Credit: D+30 per instalment"

            gross = float(tx["amount_brl"])
            mdr = float(plan["mdr_pct"].get(method, 0.0))
            net = gross * (1 - mdr / 100)
            if method == "credit" and advance_on:
                net *= 1 - advance_fee / 100
            entries.append(
                {
                    "transaction_id": tx["transaction_id"],
                    "sale_date": tx["date"],
                    "payment_method": method,
                    "gross_brl": round(gross, 2),
                    "net_brl": round(net, 2),
                    "mdr_pct": mdr,
                    "expected_credit_date": pay_date.isoformat(),
                    "rule": rule,
                }
            )
        return {
            "bank_account": merchant["bank_account"],
            "receivables_advance_enabled": advance_on,
            "entries": entries,
            "total_net_brl": round(sum(e["net_brl"] for e in entries), 2),
        }

    def terminals(self, user_id: str) -> list[dict[str, Any]]:
        return list(self.get_merchant(user_id).get("terminals", []))

    def terminal_diagnostics(
        self, user_id: str, serial_number: str | None = None
    ) -> dict[str, Any]:
        terminals = self.terminals(user_id)
        if not terminals:
            return {"terminals": [], "note": "No card machine registered for this merchant."}
        if serial_number:
            terminals = [t for t in terminals if t["serial_number"] == serial_number]
            if not terminals:
                return {"terminals": [], "note": f"No terminal with serial {serial_number}."}
        return {"terminals": terminals}

    def create_ticket(
        self,
        user_id: str,
        category: str,
        summary: str,
        priority: str = "normal",
        queue: str = "tier1-support",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.get_merchant(user_id)  # validates existence
        self._ticket_seq += 1
        ticket_id = f"GN-{datetime.now(UTC):%Y%m%d}-{self._ticket_seq}"
        sla = {"urgent": 15, "high": 30, "normal": 60, "low": 240}.get(priority, 60)
        ticket = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "category": category,
            "summary": summary,
            "priority": priority,
            "queue": queue,
            "status": "open",
            "sla_minutes": sla,
            "created_at": datetime.now(UTC).isoformat(),
            "context": context or {},
        }
        self._tickets[ticket_id] = ticket
        return ticket

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        return self._tickets.get(ticket_id)

    def list_tickets(self, user_id: str) -> list[dict[str, Any]]:
        return [t for t in self._tickets.values() if t["user_id"] == user_id]

    def operator_queue(self, queue: str = "tier1-support") -> dict[str, Any]:
        """Simulated human-operator queue depth (deterministic per queue+hour)."""
        rng = random.Random(f"{queue}-{datetime.now(UTC):%Y%m%d%H}")
        depth = rng.randint(0, 9)
        return {
            "queue": queue,
            "waiting": depth,
            "estimated_wait_minutes": depth * 3 + 2,
            "operators_online": rng.randint(2, 12),
            "business_hours": "Mon-Sat 08:00-20:00 (America/Sao_Paulo)",
        }


def _add_business_days(start: date, n: int) -> date:
    current = start
    added = 0
    while added < n:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            added += 1
    return current


_REPO: MerchantRepository | None = None


def get_repository() -> MerchantRepository:
    global _REPO
    if _REPO is None:
        _REPO = MerchantRepository()
    return _REPO


def set_repository(repo: MerchantRepository | None) -> None:
    """Test seam."""
    global _REPO
    _REPO = repo

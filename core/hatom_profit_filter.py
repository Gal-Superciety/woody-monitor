"""Fail-closed alert screen for indicative Hatom liquidation scenarios.

Private Stage-2 notifications may be sent only for positions with a fresh
nonempty DEX min-output route AND an estimated surplus after modeled gas,
repayment and an extra safety buffer. This is NOT verified executable profit.
"""
from __future__ import annotations

import os
import time
from decimal import Decimal, InvalidOperation
from typing import Any


def _money(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a dollar amount")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Missing/invalid dollar amount") from exc
    if not amount.is_finite():
        raise ValueError("Non-finite dollar amount")
    return amount


def limits() -> dict[str, Decimal | int]:
    """Safe defaults; reject impossible environment settings."""
    min_capital = _money(os.getenv("HATOM_ALERT_MIN_REPAY_USD", "0"))
    min_net = _money(os.getenv("HATOM_ALERT_MIN_NET_USD", "0.25"))
    buffer_bps = int(os.getenv("HATOM_ALERT_SAFETY_BUFFER_BPS", "100"))
    fixed_buffer = _money(os.getenv("HATOM_ALERT_SAFETY_BUFFER_USD", "0.50"))
    max_quote_age = int(os.getenv("HATOM_ALERT_MAX_QUOTE_AGE_SECONDS", "60"))
    if (
        not Decimal("0") <= min_capital <= Decimal("100000")
        or not Decimal("0.01") <= min_net <= Decimal("100000")
        or not 0 <= buffer_bps <= 3000
        or not Decimal("0") <= fixed_buffer <= Decimal("1000")
        or not 10 <= max_quote_age <= 120
    ):
        raise ValueError("Unsafe Hatom screening configuration")
    return {
        "min_repay_usd": min_capital,
        "min_net_usd": min_net,
        "buffer_bps": buffer_bps,
        "fixed_buffer_usd": fixed_buffer,
        "max_quote_age_seconds": max_quote_age,
    }


def eligible_for_priority_alert(
    report: Any, *, now: float | None = None,
    rules: dict[str, Decimal | int] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Require stage 2, fresh XOXNO min-out and modeled positive profit.

    This is a *notification filter* only; it does not approve execution.
    A missing quote, oracle/time metadata, simulated gas estimate, or route
    is never treated as positive. We do NOT claim verified net profit.
    """
    if not isinstance(report, dict) or report.get("category") != "INDICATIVE_ONLY":
        return False, "no indicative valuation", None
    if report.get("verified_profit") is not False:
        return False, "invalid valuation verification marker", None
    if report.get("executable_dex_quote") is not False:
        return False, "invalid non-executable marker", None
    quote = report.get("dex_quote")
    if not isinstance(quote, dict):
        return False, "no live DEX route quote", None
    try:
        if type(quote.get("route_count")) is not int or quote["route_count"] < 1:
            return False, "no DEX swap route", None
        if not isinstance(quote.get("amount_out_min_raw"), int) or quote["amount_out_min_raw"] <= 0:
            return False, "no positive minimum DEX output", None
        params = limits() if rules is None else rules
        observed = float(quote["quote_received_at"])
        if not observed or observed != observed:
            return False, "invalid route timestamp", None
        now = time.time() if now is None else now
        age = now - observed
        if not 0 <= age <= int(params["max_quote_age_seconds"]):
            return False, "stale DEX route quote", None
        debt = _money(report["repay_usd"])
        received = _money(report["quote_min_usd"])
        gas = _money(report["assumed_gas_cost_usd"])
        scenario_net = _money(report["quote_net_after_assumed_gas_usd"])
        gross = _money(report["gross_usd"])
        if debt <= 0 or debt < params["min_repay_usd"]:
            return False, "repayment below capital threshold", None
        if received <= debt or gross <= 0 or gas <= 0:
            return False, "no positive pre-buffer margin", None
        # The reported DEX scenario is output minimum - repayment - assumed gas.
        if abs((received - debt - gas) - scenario_net) > Decimal("0.000000001"):
            return False, "scenario figures inconsistent", None
        buffer_usd = max(
            _money(params["fixed_buffer_usd"]),
            debt * Decimal(int(params["buffer_bps"])) / Decimal(10000),
        )
        after_buffer = scenario_net - buffer_usd
        if after_buffer < params["min_net_usd"]:
            return False, "modeled profit below safety threshold", None
        annotated = dict(report)
        annotated["safety_buffer_usd"] = buffer_usd
        annotated["screened_surplus_usd"] = after_buffer
        annotated["profit_alert_screen_passed"] = True
        return True, "positive indicative margin after safety buffer", annotated
    except (KeyError, ValueError, TypeError, OverflowError, InvalidOperation):
        return False, "incomplete or invalid DEX scenario data", None

"""Read-only Hatom mark-to-market calculator; NEVER an executable profit quote.

Uses official MultiversX REST token decimal metadata and indicative USD prices.
Figures subtract *assumed* swap slippage and gas consumed; there is currently
NO executable DEX route quote, no verified gas estimate, and no signed tx.
Accordingly results MUST NOT be labeled "verified profit" or used for trades.
"""
from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

API = "https://api.multiversx.com"
GATEWAY = "https://gateway.multiversx.com"
_ESDT = re.compile(r"^[A-Za-z0-9]{3,20}-[a-z0-9]{6}$")
_ETH = Decimal("1000000000000000000")
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = threading.Lock()


class QuoteUnavailable(ValueError):
    """An essential price, token identifier, or gas input is unverified."""


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise QuoteUnavailable("Non-numeric price")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise QuoteUnavailable("Invalid numeric quote") from exc
    if not number.is_finite() or number <= 0:
        raise QuoteUnavailable("Price or rate is zero or nonfinite")
    return number


def _nonnegative_int(value: Any, *, upper: int = 10**80) -> int:
    if isinstance(value, bool) or not str(value).isdecimal():
        raise QuoteUnavailable("Invalid integer amount")
    result = int(value)
    if result < 0 or result > upper:
        raise QuoteUnavailable("Raw amount out of bounds")
    return result


def human(raw: Any, decimals: int) -> Decimal:
    if not isinstance(decimals, int) or isinstance(decimals, bool) or decimals < 0 or decimals > 30:
        raise QuoteUnavailable("Token decimals not valid")
    with localcontext() as ctx:
        ctx.prec = 90
        return Decimal(_nonnegative_int(raw)) / (Decimal(10) ** decimals)


@dataclass(frozen=True)
class Asset:
    token: str
    symbol: str
    decimals: int
    price_usd: Decimal
    observed_at: float


class MarketData:
    """Fixed-host read-only pricing source; no bearer tokens or wallet keys."""

    def __init__(self, session: Any = None, timeout: int = 8):
        self.session = session if session is not None else requests.Session()
        self.timeout = max(2, min(timeout, 15))
        self.cache: dict[str, tuple[float, Any]] = {}

    def _json(self, url: str, *, max_age: int = 45) -> dict[str, Any]:
        if not url.startswith((API + "/", GATEWAY + "/")):
            raise QuoteUnavailable("Non-approved metadata URL")
        now = time.time()
        with _CACHE_LOCK:
            previous = _CACHE.get(url)
            if previous and now - previous[0] < max_age:
                return previous[1]
        try:
            response = self.session.get(
                url, timeout=self.timeout, allow_redirects=False,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            if len(response.content) > 300_000:
                raise QuoteUnavailable("Metadata response too large")
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise QuoteUnavailable("Market data unavailable") from exc
        if not isinstance(payload, dict):
            raise QuoteUnavailable("Invalid metadata response")
        with _CACHE_LOCK:
            _CACHE[url] = (now, payload)
        return payload

    def asset(self, token: str) -> Asset:
        now = time.time()
        if token == "EGLD":
            payload = self._json(API + "/economics")
            price = _decimal(payload.get("price"))
            return Asset("EGLD", "EGLD", 18, price, now)
        if not _ESDT.fullmatch(token):
            raise QuoteUnavailable("Unrecognized Hatom underlying token identifier")
        payload = self._json(API + "/tokens/" + quote(token, safe=""))
        if payload.get("identifier") != token:
            raise QuoteUnavailable("Token metadata identifier mismatch")
        d = payload.get("decimals")
        if type(d) is not int or not 0 <= d <= 30:
            raise QuoteUnavailable("Token decimals missing or invalid")
        price = _decimal(payload.get("price"))
        symbol = str(payload.get("ticker") or token.split("-")[0])[:20]
        return Asset(token, symbol, d, price, now)

    def dex_quote(self, token_in: str, token_out: str, amount_in_raw: int) -> dict[str, Any]:
        """Get a bounded exact-input read-only XOXNO route quote."""

        def canonical(token: str) -> str:
            result = "WEGLD-bd4d79" if token == "EGLD" else token
            if not _ESDT.fullmatch(result):
                raise QuoteUnavailable("Unsupported swap token")
            return result

        source = canonical(token_in)
        dest = canonical(token_out)
        quantity = _nonnegative_int(amount_in_raw)
        if source == dest:
            return {
                "amount_out_min_raw": quantity,
                "amount_out_raw": quantity,
                "route_count": 0,
                "quote_received_at": time.time(),
                "provider": "same-underlying (no swap)",
            }
        if quantity <= 0:
            raise QuoteUnavailable("DEX amount is zero")
        try:
            response = self.session.get(
                "https://swap.xoxno.com/api/v1/quote",
                params={
                    "from": source, "to": dest, "amountIn": str(quantity),
                    "includePaths": "true", "strict": "true",
                },
                timeout=self.timeout, allow_redirects=False,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            if len(response.content) > 500_000:
                raise QuoteUnavailable("DEX quote too large")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise QuoteUnavailable("DEX routing quote unavailable") from exc
        if not isinstance(data, dict):
            raise QuoteUnavailable("DEX quote not an object")
        if data.get("from") != source or data.get("to") != dest:
            raise QuoteUnavailable("DEX route token IDs mismatch")
        if str(data.get("amountIn")) != str(quantity):
            raise QuoteUnavailable("DEX route input quantity mismatch")
        output = _nonnegative_int(data.get("amountOut"))
        minimum = _nonnegative_int(data.get("amountOutMin"))
        paths = data.get("paths")
        if output <= 0 or minimum <= 0 or minimum > output:
            raise QuoteUnavailable("DEX output quote invalid")
        if not isinstance(paths, list) or not paths or len(paths) > 20:
            raise QuoteUnavailable("DEX has no usable route paths")
        return {
            "amount_out_min_raw": minimum,
            "amount_out_raw": output,
            "route_count": len(paths),
            "quote_received_at": time.time(),
            "provider": "XOXNO MultiversX public quote",
        }

    def gas_price(self) -> int:
        response = self._json(GATEWAY + "/network/config", max_age=180)
        config = response.get("data")
        if not isinstance(config, dict) or not isinstance(config.get("config"), dict):
            raise QuoteUnavailable("Network gas config unavailable")
        raw = config["config"].get("erd_min_gas_price")
        price = _nonnegative_int(raw, upper=10**12)
        if price <= 0:
            raise QuoteUnavailable("Invalid network gas price")
        return price


def underlying_id(vm: Any, market: str) -> str:
    """Hatom money-market view: EgldOrEsdtTokenIdentifier top-encoded buffer."""
    result = vm.query(market, "getUnderlyingId")
    if len(result) != 1 or not result[0]:
        raise QuoteUnavailable("Hatom underlying token not returned")
    try:
        identifier = result[0].decode("ascii")
    except UnicodeDecodeError as exc:
        raise QuoteUnavailable("Hatom token identifier invalid") from exc
    if identifier != "EGLD" and not _ESDT.fullmatch(identifier):
        raise QuoteUnavailable("Hatom token ID not recognized")
    return identifier


def _assumptions() -> tuple[int, int]:
    """User-editable conservative scenario parameters, not real swap estimates."""
    try:
        gas_units = int(os.getenv("HATOM_GAS_UNITS_ASSUMED", "60000000"))
        slippage = int(os.getenv("HATOM_SWAP_LOSS_BPS_ASSUMED", "150"))
    except ValueError as exc:
        raise QuoteUnavailable("Invalid cost scenario config") from exc
    if not (2_000_000 <= gas_units <= 300_000_000) or not (0 <= slippage <= 2500):
        raise QuoteUnavailable("Cost scenario outside safe bounds")
    return gas_units, slippage


def estimate(row: dict[str, Any], vm: Any = None, prices: MarketData | None = None) -> dict[str, Any]:
    """Price an already on-chain-revalidated repay/seize quote, with assumptions.

    Returns a modeling scenario, not an actionable/profit-verified liquidation.
    """
    if row.get("category") != "ONCHAIN_ELIGIBLE":
        raise QuoteUnavailable("This position has not passed stage-2 preflight")
    if vm is None:
        from core.hatom_onchain import VmClient
        vm = VmClient()
    prices = prices if prices is not None else MarketData()
    debt_id = underlying_id(vm, row["borrow_market"])
    collateral_id = underlying_id(vm, row["collateral_market"])
    debt_asset = prices.asset(debt_id)
    collateral_asset = prices.asset(collateral_id)
    egld_asset = prices.asset("EGLD")
    repay = human(row["repay_raw"], debt_asset.decimals)
    received = human(row["collateral_underlying_raw"], collateral_asset.decimals)
    if repay <= 0 or received <= 0:
        raise QuoteUnavailable("Nonpositive position amount")
    gas_units, swap_bps = _assumptions()
    gas_price = prices.gas_price()
    with localcontext() as ctx:
        ctx.prec = 70
        debt_usd = repay * debt_asset.price_usd
        collateral_usd = received * collateral_asset.price_usd
        gross_usd = collateral_usd - debt_usd
        gas_usd = Decimal(gas_units) * Decimal(gas_price) / _ETH * egld_asset.price_usd
        swap_usd = collateral_usd * Decimal(swap_bps) / Decimal("10000")
        scenario_net_usd = gross_usd - gas_usd - swap_usd
    return {
        "category": "INDICATIVE_ONLY",
        "borrower": row["borrower"],
        "debt_market": row["borrow_market"],
        "collateral_market": row["collateral_market"],
        "repay_token": debt_id,
        "repay_symbol": debt_asset.symbol,
        "repay_units": repay,
        "repay_usd": debt_usd,
        "collateral_token": collateral_id,
        "collateral_symbol": collateral_asset.symbol,
        "collateral_units": received,
        "collateral_usd": collateral_usd,
        "gross_usd": gross_usd,
        "assumed_swap_cost_usd": swap_usd,
        "assumed_gas_cost_usd": gas_usd,
        "scenario_net_usd": scenario_net_usd,
        "assumed_slippage_bps": swap_bps,
        "assumed_gas_units": gas_units,
        "gas_price_wei": gas_price,
        "observed_at": time.time(),
        "source": "MultiversX public token USD reference prices",
        "price_source_timestamp": None,
        "executable_dex_quote": False,
        "verified_profit": False,
    }


def _money(number: Decimal) -> str:
    if abs(number) < Decimal("0.01") and number != 0:
        return ("-" if number < 0 else "") + "<$0.01"
    return f"${number:,.2f}"


def _amount(number: Decimal) -> str:
    return f"{number:.8f}".rstrip("0").rstrip(".") if number < 10**8 else f"{number:,.4f}"


def format_scenario(result: dict[str, Any]) -> list[str]:
    """Never describe an assumption-based scenario as realized or verified profit."""
    sign = "+" if result["scenario_net_usd"] >= 0 else ""
    return [
        f"   Repay: {_amount(result['repay_units'])} {result['repay_symbol']} "
        f"({_money(result['repay_usd'])})",
        f"   Recover: {_amount(result['collateral_units'])} {result['collateral_symbol']} "
        f"({_money(result['collateral_usd'])})",
        f"   Gross reference margin: {_money(result['gross_usd'])}",
        f"   Assumed swap loss ({result['assumed_slippage_bps']/100:.2f}%): "
        f"{_money(result['assumed_swap_cost_usd'])}",
        f"   Assumed gas: {_money(result['assumed_gas_cost_usd'])}",
        f"   Scenario net (NOT EXECUTABLE): {sign}{_money(result['scenario_net_usd'])}",
    ]


def explain_missing(exc: Exception) -> str:
    return str(exc)[:90] if isinstance(exc, QuoteUnavailable) else "Market data or valuation failed"

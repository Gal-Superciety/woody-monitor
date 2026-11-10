"""On-demand, read-only XOXNO Lending liquidation scenario (NOT profit proof).

The live Controller liquidationEstimations result contains collateral, protocol
fees and refunds. Evaluate the worst route output at XOXNO Swap, subtract
estimated gas and extra reserve. No keys, signing, transaction or guarantees.
"""
from __future__ import annotations

import os
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from core.hatom_onchain import VmClient
from core.hatom_profit import MarketData, QuoteUnavailable, human
from core.xoxno_lending_watch import CONTROLLER, nonce_of, minimum_alert_usd

API = "https://api.xoxno.com"
ETH = Decimal(10) ** 18
TOKEN = re.compile(r"^[A-Za-z0-9]{3,20}-[a-z0-9]{6}$")


class CalculationUnavailable(ValueError):
    pass


def integer(value: Any, upper: int = 10**75) -> int:
    if isinstance(value, bool) or not str(value).isdecimal():
        raise CalculationUnavailable("Invalid unsigned number")
    n = int(value)
    if not 0 <= n <= upper:
        raise CalculationUnavailable("Number out of bounds")
    return n


def top_int(n: int) -> bytes:
    n = integer(n)
    return n.to_bytes(max(1, (n.bit_length()+7)//8), "big")


def nested(raw: bytes) -> bytes:
    if len(raw) > 256:
        raise CalculationUnavailable("Oversized nested input")
    return len(raw).to_bytes(4, "big") + raw


def encode_payment(token: str, raw: int) -> bytes:
    """MultiversX TopEncode(ManagedVec<EgldOrEsdtTokenPayment>): nested entries.

    Token ID: nested len+bytes; nonce: 8-byte u64; BigUint: len+bytes.
    One payment passed, so no outer vector length for TopEncode.
    """
    if token != "EGLD" and not TOKEN.fullmatch(token):
        raise CalculationUnavailable("Invalid debt token")
    amount = integer(raw)
    if amount <= 0:
        raise CalculationUnavailable("Repayment must be positive")
    return nested(token.encode("ascii")) + b"\x00"*8 + nested(top_int(amount))


class Reader:
    def __init__(self, b: bytes):
        if not isinstance(b, bytes) or not 0 < len(b) < 64000:
            raise CalculationUnavailable("Invalid VM quote size")
        self.b = b
        self.p = 0

    def take(self, n: int) -> bytes:
        if not 0 <= n <= len(self.b)-self.p:
            raise CalculationUnavailable("Malformed or truncated VM quote")
        x = self.b[self.p:self.p+n]
        self.p += n
        return x

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "big")

    def nested(self, cap: int = 128) -> bytes:
        n = self.u32()
        if n > cap:
            raise CalculationUnavailable("Oversized VM nested field")
        return self.take(n)

    def payment(self) -> dict[str, Any]:
        try:
            token = self.nested(40).decode("ascii")
        except UnicodeDecodeError as exc:
            raise CalculationUnavailable("Invalid token encoding") from exc
        nonce = int.from_bytes(self.take(8), "big")
        amount = int.from_bytes(self.nested(64), "big")
        if ((token != "EGLD" and not TOKEN.fullmatch(token)) or nonce != 0
                or amount <= 0 or amount > 10**75):
            raise CalculationUnavailable("Invalid fungible payment in quote")
        return {"token": token, "raw": amount}

    def vec(self) -> list[dict[str, Any]]:
        n = self.u32()
        if n > 10:
            raise CalculationUnavailable("Too many payments in VM quote")
        return [self.payment() for _ in range(n)]

    def decimal(self) -> Decimal:
        raw = int.from_bytes(self.nested(64), "big")
        places = self.u32()
        if places > 30:
            raise CalculationUnavailable("Unexpected decimal precision")
        return Decimal(raw) / (Decimal(10)**places)

    def finish(self) -> None:
        if self.p != len(self.b):
            raise CalculationUnavailable("Trailing bytes in contract result")


def decode_estimate(values: list[bytes]) -> dict[str, Any]:
    """XOXNO/rs-lending common_structs::LiquidationEstimate TopDecode."""
    if len(values) != 1:
        raise CalculationUnavailable("Missing single structured SC estimate")
    r = Reader(values[0])
    seized, fees, refunds = r.vec(), r.vec(), r.vec()
    max_egld, bonus_bps = r.decimal(), r.decimal()
    r.finish()
    if not seized or max_egld <= 0 or bonus_bps > 2500:
        raise CalculationUnavailable("No meaningful seized collateral")
    return {"seized": seized, "fees": fees, "refunds": refunds,
            "bonus_bps": bonus_bps}


def decode_amount(values: list[bytes]) -> tuple[int, int]:
    """ManagedDecimal<NumDecimals> returned by getBorrowAmountForToken."""
    if len(values) != 1:
        raise CalculationUnavailable("No live debt amount")
    r = Reader(values[0])
    raw = int.from_bytes(r.nested(64), "big")
    places = r.u32()
    r.finish()
    if raw <= 0 or places > 30:
        raise CalculationUnavailable("Invalid live debt amount")
    return raw, places


class XoxnoPositions:
    def __init__(self, session: Any = None):
        self.session = session if session is not None else requests.Session()

    def debt_tokens(self, nonce: int) -> list[str]:
        response = self.session.get(
            API + "/lending/account/" + str(nonce) + "/positions",
            timeout=8, allow_redirects=False,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        if len(response.content) > 150_000:
            raise CalculationUnavailable("Position data too large")
        items = response.json()
        if not isinstance(items, list) or len(items) > 50:
            raise CalculationUnavailable("Unrecognized XOXNO account positions")
        result = []
        for row in items:
            if (not isinstance(row, dict) or row.get("nonce") != nonce
                    or row.get("chain") != "MVX"):
                raise CalculationUnavailable("Unexpected XOXNO position identity")
            token = row.get("token")
            if token != "EGLD" and (not isinstance(token, str) or not TOKEN.fullmatch(token)):
                raise CalculationUnavailable("Unexpected XOXNO position token")
            if integer(row.get("borrowAmountScaled")) > 0 and token not in result:
                result.append(token)
        if not result:
            raise CalculationUnavailable("No borrowed assets in position")
        return result[:4]


def sums(rows: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for x in rows:
        result[x["token"]] = result.get(x["token"], 0) + x["raw"]
    return result


def quote_one(
    identifier: str, token: str, requested: int, data: dict[str, Any],
    market: MarketData, *, gas_units: int, buffer_pct: int,
    buffer_flat: Decimal,
) -> dict[str, Any]:
    refunds = sums(data["refunds"])
    if set(refunds) - {token} or refunds.get(token, 0) > requested:
        raise CalculationUnavailable("Refund does not match debt payment")
    actual_repay = requested - refunds.get(token, 0)
    if actual_repay <= 0:
        raise CalculationUnavailable("Repayment entirely refunded")
    debt = market.asset(token)
    if debt.price_usd <= 0:
        raise CalculationUnavailable("Missing debt price")
    repay_units = human(actual_repay, debt.decimals)
    repay_usd = repay_units * debt.price_usd
    seized, fees = sums(data["seized"]), sums(data["fees"])
    if not seized or set(fees) - set(seized):
        raise CalculationUnavailable("Invalid collateral/fee tokens")
    min_out_raw = 0
    collateral_reference = Decimal(0)
    routes = 0
    collaterals = []
    for asset_id, value in seized.items():
        # Conservative: subtract the fee even if seized amount may already
        # be fee-adjusted. Never overstate seized value.
        after_fee = value - fees.get(asset_id, 0)
        if after_fee <= 0:
            raise CalculationUnavailable("Insufficient seized collateral after fees")
        asset = market.asset(asset_id)
        collateral_reference += human(after_fee, asset.decimals)*asset.price_usd
        if asset_id == token:
            min_out_raw += after_fee
            paths = 0
        else:
            dex = market.dex_quote(asset_id, token, after_fee)
            paths = dex["route_count"]
            if paths <= 0 or dex["amount_out_min_raw"] <= 0:
                raise CalculationUnavailable("No live executable swap route")
            min_out_raw += dex["amount_out_min_raw"]
        routes += paths
        collaterals.append({"token": asset_id, "raw_after_fee": after_fee,
                            "routes": paths})
    min_out_units = human(min_out_raw, debt.decimals)
    min_out_usd = min_out_units * debt.price_usd
    gas_usd = (Decimal(gas_units)*Decimal(market.gas_price())/ETH
               *market.asset("EGLD").price_usd)
    safety_usd = max(buffer_flat, repay_usd*Decimal(buffer_pct)/10000)
    before_buffer = min_out_usd - repay_usd - gas_usd
    after_buffer = before_buffer - safety_usd
    return {
        "identifier": identifier, "repay_token": token,
        "repay_raw": actual_repay, "repay_units": repay_units,
        "repay_usd": repay_usd, "reference_collateral_usd": collateral_reference,
        "dex_min_units": min_out_units, "dex_min_usd": min_out_usd,
        "gross_reference_usd": collateral_reference - repay_usd,
        "estimated_gas_usd": gas_usd, "safety_buffer_usd": safety_usd,
        "scenario_pre_buffer_usd": before_buffer,
        "scenario_net_usd": after_buffer,
        "clears_quarter_dollar": after_buffer >= Decimal("0.25"),
        "clears_alert_minimum": after_buffer >= minimum_alert_usd(),
        "bonus_bps": data["bonus_bps"],
        "routes": routes, "collaterals": collaterals,
        "price_source_timestamp": None,
        "quote_observed_at": time.time(),
        "verified_profit": False,
        "full_pipeline_simulated": False,
        "transaction_sent": False,
    }


def calculate(
    identifier: str, *, vm: Any = None, positions: Any = None,
    market: Any = None,
) -> dict[str, Any]:
    nonce = nonce_of(identifier)
    vm = vm if vm is not None else VmClient(controller=CONTROLLER, timeout=9)
    positions = positions if positions is not None else XoxnoPositions()
    market = market if market is not None else MarketData(timeout=8)
    is_eligible = vm.query(CONTROLLER, "canBeLiquidated", [top_int(nonce)])
    if is_eligible != [b"\x01"]:
        raise CalculationUnavailable("Account is not currently liquidatable")
    tokens = positions.debt_tokens(nonce)
    try:
        gas_units = int(os.getenv("XOXNO_GAS_UNITS_ASSUMED", "180000000"))
        buffer_pct = int(os.getenv("XOXNO_SAFETY_BPS", "100"))
        buffer_flat = Decimal(os.getenv("XOXNO_SAFETY_USD", "0.50"))
    except (ValueError, InvalidOperation) as exc:
        raise CalculationUnavailable("Invalid safety configuration") from exc
    if (not 50_000_000 <= gas_units <= 300_000_000
            or not 0 <= buffer_pct <= 3000
            or not buffer_flat.is_finite() or buffer_flat < 0):
        raise CalculationUnavailable("Unsafe profit assumptions")
    reports: list[dict[str, Any]] = []
    errors: list[str] = []
    attempts = 0
    for token in tokens[:3]:
        try:
            amount, decimals = decode_amount(
                vm.query(CONTROLLER, "getBorrowAmountForToken",
                         [top_int(nonce), token.encode("ascii")])
            )
            asset = market.asset(token)
            if decimals != asset.decimals:
                raise CalculationUnavailable("Debt token decimals mismatch")
            for denominator in (1, 2, 4):
                proposed = amount // denominator
                if proposed <= 1:
                    continue
                attempts += 1
                try:
                    raw = encode_payment(token, proposed)
                    estimate = decode_estimate(
                        vm.query(CONTROLLER, "liquidationEstimations",
                                 [top_int(nonce), raw])
                    )
                    result = quote_one(
                        identifier, token, proposed, estimate, market,
                        gas_units=gas_units, buffer_pct=buffer_pct,
                        buffer_flat=buffer_flat,
                    )
                    reports.append(result)
                except (CalculationUnavailable, QuoteUnavailable, ValueError,
                        TypeError, requests.RequestException) as exc:
                    errors.append(str(exc)[:90])
        except (CalculationUnavailable, QuoteUnavailable, ValueError,
                TypeError, requests.RequestException) as exc:
            errors.append(str(exc)[:90])
    if not reports:
        detail = errors[0] if errors else "No valid repayment"
        raise CalculationUnavailable(
            "No complete current Controller+DEX scenario: "+detail
        )
    best = max(reports, key=lambda x:x["scenario_net_usd"])
    return dict(best, attempts=attempts, priced=len(reports),
                errors=len(errors))


def format_report(result: dict[str, Any]) -> str:
    def money(value: Decimal) -> str:
        return "USD " + format(value, ",.4f")
    net = result["scenario_net_usd"]
    floor = minimum_alert_usd()
    if net >= floor:
        verdict = ("MODELED >= USD " + str(floor)
                   + " (NOT VERIFIED EXECUTABLE PROFIT)")
    else:
        verdict = ("BELOW USD " + str(floor)
                   + " — NOT ELIGIBLE FOR PROFIT ALERT IN THIS SCENARIO")
    rows = [
        "💰 XOXNO LENDING — PRIVATE PROFIT SCENARIO",
        "MultiversX | READ-ONLY | MANUAL ACTION ONLY",
        "Account NFT: " + result["identifier"],
        "Repay: " + format(result["repay_units"], ".8f") + " " + result["repay_token"],
        "Repay value: " + money(result["repay_usd"]),
        "Seized collateral reference: " + money(result["reference_collateral_usd"]),
        "Gross reference margin: " + money(result["gross_reference_usd"]),
        "LIVE DEX min-output value: " + money(result["dex_min_usd"]),
        "ASSUMED gas (not simulated): " + money(result["estimated_gas_usd"]),
        "Extra safety reserve: " + money(result["safety_buffer_usd"]),
        "Indicative net after assumptions: " + money(net),
        "Assessment: " + verdict,
        "On-chain estimates tested: " + str(result["priced"]) + "/" + str(result["attempts"]),
        "Collateral assets / routes: " + str(len(result["collaterals"])) + "/" + str(result["routes"]),
        "",
        "XOXNO Controller liquidationEstimations view + current DEX min-out.",
        "Liquidation execution and precise gas remain NOT SIMULATED.",
        "NET PROFIT: NOT VERIFIED. Quote can expire; TX can fail.",
        "No funds used. No wallet keys. No transaction executed.",
    ]
    return "\n".join(rows)[:3800]

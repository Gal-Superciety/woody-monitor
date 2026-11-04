"""Conservative on-chain Hatom discovery using public, read-only MVX contract calls.

The scanner deliberately does NOT send transactions, sign anything, hold keys,
or make claims of available liquidation profit. The official Controller risk
check is used, then borrow and collateral storage is inspected to reduce noise.

Mainnet correctness of VM responses must be verified after deployment.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

CONTROLLER = "erd1qqqqqqqqqqqqqpgqxp28qpnv7rfcmk6qrgxgw5uf2fnp84ar78ssqdk6hr"
GATEWAY = "https://gateway.multiversx.com/vm-values/query"
_BECH32_CHARS = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_GENERATOR = (0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)


def _polymod(values: list[int]) -> int:
    result = 1
    for value in values:
        top = result >> 25
        result = ((result & 0x1FFFFFF) << 5) ^ value
        for i, generator in enumerate(_GENERATOR):
            if (top >> i) & 1:
                result ^= generator
    return result


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _convertbits(data: bytes | list[int], frombits: int, tobits: int, pad: bool) -> list[int]:
    acc = 0
    bits = 0
    out: list[int] = []
    maximum = (1 << tobits) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("Invalid bech32 data")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maximum)
    if pad:
        if bits:
            out.append((acc << (tobits - bits)) & maximum)
    elif bits >= frombits or ((acc << (tobits - bits)) & maximum):
        raise ValueError("Invalid bech32 padding")
    return out


def address_encode(raw: bytes) -> str:
    if len(raw) != 32:
        raise ValueError("MultiversX address must be 32 bytes")
    data = _convertbits(raw, 8, 5, True)
    values = _hrp_expand("erd") + data
    check = _polymod(values + [0] * 6) ^ 1
    checksum = [(check >> (5 * (5 - i))) & 31 for i in range(6)]
    return "erd1" + "".join(_BECH32_CHARS[i] for i in data + checksum)


def address_decode(value: str) -> bytes:
    if not isinstance(value, str) or len(value) != 62 or not value.startswith("erd1"):
        raise ValueError("Not an EGLD bech32 address")
    if value != value.lower():
        raise ValueError("Mixed-case address")
    try:
        data = [_BECH32_CHARS.index(c) for c in value[4:]]
    except ValueError as exc:
        raise ValueError("Invalid bech32 character") from exc
    if _polymod(_hrp_expand("erd") + data) != 1:
        raise ValueError("Invalid bech32 checksum")
    raw = bytes(_convertbits(data[:-6], 5, 8, False))
    if len(raw) != 32:
        raise ValueError("Invalid decoded address size")
    return raw


def _addresses(data: list[bytes], *, max_items: int = 30000) -> list[str]:
    """Decode a vector of 32-byte addresses. Reject unexpected ABI layouts."""
    result: list[str] = []
    for chunk in data:
        if len(chunk) % 32:
            raise ValueError("Unexpected address vector encoding")
        for offset in range(0, len(chunk), 32):
            result.append(address_encode(chunk[offset:offset + 32]))
            if len(result) > max_items:
                raise ValueError("Too many addresses in VM result")
    return list(dict.fromkeys(result))


def _decode_uint(value: bytes) -> int:
    return int.from_bytes(value, "big", signed=False)


def _decode_bool(value: bytes) -> bool:
    if value in (b"", b"\x00"):
        return False
    if value == b"\x01":
        return True
    raise ValueError("Unexpected boolean response")


def _positive_hex(number: int) -> str:
    return format(max(0, number), "x").zfill(2)


class VmClient:
    """Read-only Hatom on-chain view queries over HTTPS."""

    def __init__(self, *, gateway: str = GATEWAY, controller: str = CONTROLLER,
                 session: Any = None, timeout: int = 12):
        if not gateway.startswith("https://") or not gateway.endswith("/vm-values/query"):
            raise ValueError("Only HTTPS MultiversX VM query endpoints are permitted")
        address_decode(controller)
        self.gateway = gateway
        self.controller = controller
        self.session = session if session is not None else requests.Session()
        self.timeout = max(2, min(timeout, 30))

    def query(self, contract: str, function: str, args: list[bytes] | None = None) -> list[bytes]:
        address_decode(contract)
        if not function.isascii() or not function.isidentifier():
            raise ValueError("Invalid view function")
        payload = {
            "scAddress": contract,
            "funcName": function,
            "args": [arg.hex() for arg in (args or [])],
        }
        response = self.session.post(
            self.gateway,
            json=payload,
            timeout=self.timeout,
            allow_redirects=False,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("VM response too large")
        decoded = response.json()
        if not isinstance(decoded, dict) or decoded.get("error"):
            raise ValueError("VM query rejected by network")
        data = decoded.get("data")
        if not isinstance(data, dict):
            raise ValueError("Missing VM data")
        vm = data.get("data") if isinstance(data.get("data"), dict) else data
        code = vm.get("ReturnCode", vm.get("returnCode"))
        if code not in (0, "0", "ok", "OK"):
            raise ValueError(f"VM query failed: {str(code)[:80]}")
        returned = vm.get("ReturnData", vm.get("returnData"))
        if not isinstance(returned, list):
            raise ValueError("Missing VM returnData")
        try:
            return [base64.b64decode(item, validate=True) for item in returned]
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid base64 result") from exc

    def whitelist(self) -> list[str]:
        result = _addresses(self.query(self.controller, "getWhitelistedMarkets"))
        if not result:
            raise ValueError("No Hatom markets returned; refusing empty discovery")
        return result

    def members(self, market: str) -> list[str]:
        return _addresses(self.query(self.controller, "getMarketMembers", [address_decode(market)]))

    def risky(self, borrower: str) -> bool:
        data = self.query(self.controller, "isRisky", [address_decode(borrower)])
        if len(data) != 1:
            raise ValueError("Unexpected isRisky result")
        return _decode_bool(data[0])

    def account_markets(self, borrower: str) -> list[str]:
        return _addresses(self.query(self.controller, "getAccountMarkets", [address_decode(borrower)]))

    def borrow_amount(self, market: str, borrower: str) -> int:
        data = self.query(market, "getCurrentAccountBorrowAmount", [address_decode(borrower)])
        if len(data) != 1:
            raise ValueError("Unexpected borrow amount response")
        return _decode_uint(data[0])

    def collateral_tokens(self, market: str, borrower: str) -> int:
        data = self.query(self.controller, "getAccountTokens",
                          [address_decode(market), address_decode(borrower)])
        if len(data) != 1:
            raise ValueError("Unexpected collateral amount response")
        return _decode_uint(data[0])

    @staticmethod
    def _raw_arg(number: int) -> bytes:
        if number <= 0:
            raise ValueError("Amount must be positive")
        return number.to_bytes(max(1, (number.bit_length() + 7) // 8), "big")

    def close_factor(self, market: str) -> int:
        values = self.query(market, "getCloseFactor")
        if len(values) != 1:
            raise ValueError("Invalid close factor response")
        factor = _decode_uint(values[0])
        if not 0 < factor <= 10**18:
            raise ValueError("Close factor outside expected WAD range")
        return factor

    def seized_htokens(self, debt_market: str, collateral_market: str, repay_raw: int) -> int:
        values = self.query(self.controller, "tokensToSeize", [
            address_decode(debt_market), address_decode(collateral_market),
            self._raw_arg(repay_raw)
        ])
        if len(values) != 1:
            raise ValueError("Invalid seize quote")
        seized = _decode_uint(values[0])
        if seized <= 0:
            raise ValueError("Nothing to seize")
        return seized

    def collateral_underlying(self, market: str, seized_htokens: int) -> int:
        values = self.query(market, "currentTokensToUnderlyingAmount", [self._raw_arg(seized_htokens)])
        if len(values) != 1:
            raise ValueError("Invalid underlying conversion")
        result = _decode_uint(values[0])
        if result <= 0:
            raise ValueError("Zero collateral conversion")
        return result

    def market_cash(self, market: str) -> int:
        values = self.query(market, "getCash")
        if len(values) != 1:
            raise ValueError("Invalid market cash")
        return _decode_uint(values[0])

    def meaningful_liquidation_check(self, debt_market: str, collateral_market: str,
                                     borrower: str, borrow_raw: int) -> dict[str, int] | None:
        """Fail-closed on-chain *eligibility*, NOT a profit or execution guarantee.

        Repay a test fraction of the actual debt (1/4, capped by close factor),
        check allow-view, seized hTokens, underlying redemption and market cash.
        Values are raw token units, NEVER denominated fiat amounts.
        """
        if borrow_raw <= 1:
            return None
        close_factor = self.close_factor(debt_market)
        repay = min(borrow_raw // 4, borrow_raw * close_factor // 10**18)
        if repay <= 1:
            return None
        if not self.liquidation_allowed(debt_market, collateral_market, borrower, repay):
            return None
        seized = self.seized_htokens(debt_market, collateral_market, repay)
        available_htokens = self.collateral_tokens(collateral_market, borrower)
        if seized > available_htokens:
            # If the selected collateral is insufficient the transaction may
            # revert even though Controller's allowance returns true.
            return None
        recovered_underlying = self.collateral_underlying(collateral_market, seized)
        if self.market_cash(collateral_market) < recovered_underlying:
            return None
        return {
            "repay_raw": repay,
            "seized_htokens_raw": seized,
            "collateral_underlying_raw": recovered_underlying,
        }

    def liquidation_allowed(self, borrow_market: str, collateral_market: str,
                            borrower: str, repay_raw: int) -> bool:
        data = self.query(self.controller, "liquidateBorrowAllowed", [
            address_decode(borrow_market),
            address_decode(collateral_market),
            address_decode(borrower),
            max(1, repay_raw).to_bytes(max(1, (max(1, repay_raw).bit_length() + 7) // 8), "big")
        ])
        if len(data) != 1:
            raise ValueError("Unexpected liquidateBorrowAllowed result")
        return _decode_bool(data[0])


class HatomScanner:
    """Bounded incremental scanner; attempts no wallet actions or pricing estimates."""

    def __init__(self, client: VmClient | None = None, *, batch: int = 15,
                 refresh_seconds: int = 1800, max_members: int = 30000):
        self.client = client if client is not None else VmClient()
        self.batch = max(1, min(batch, 100))
        self.refresh_seconds = max(60, refresh_seconds)
        self.max_members = max(100, min(max_members, 30000))
        self._lock = threading.Lock()
        self._markets: list[str] = []
        self._markets_at = 0.0
        self._next_market = 0
        self._members: set[str] = set()
        self._wallet_cursor = 0
        self._last_refresh_at = 0.0
        self.status: dict[str, Any] = {
            "markets": 0, "borrowers_indexed": 0, "checked": 0,
            "last_error": None, "last_scan": None, "last_refresh": None,
            "rejected_oracle_or_contract": 0,
        }

    def _refresh_members(self) -> None:
        now = time.time()
        if not self._markets or now - self._markets_at >= 3600:
            markets = self.client.whitelist()
            if not markets:
                raise ValueError("Hatom controller returned no whitelisted markets")
            self._markets = markets[:32]
            self._markets_at = now
            self.status["markets"] = len(self._markets)
        # Warm up the index: query one NEW market per poll until all markets
        # have been visited. Afterwards refresh one market at the normal
        # cadence to limit network load.
        initial_cycle_incomplete = self._next_market < len(self._markets)
        if not self._members or initial_cycle_incomplete or now - self._last_refresh_at >= self.refresh_seconds:
            market = self._markets[self._next_market % len(self._markets)]
            found = self.client.members(market)
            if len(found) > self.max_members:
                raise ValueError("Excessive Hatom market member count")
            self._members.update(found)
            if len(self._members) > self.max_members:
                raise ValueError("Excessive index size; use a dedicated indexer")
            self._next_market += 1
            self._last_refresh_at = now
            self.status["last_refresh"] = int(now)
            self.status["borrowers_indexed"] = len(self._members)

    def scan(self) -> list[dict[str, Any]]:
        if not self._lock.acquire(blocking=False):
            return []
        try:
            self._refresh_members()
            wallets = sorted(self._members)
            if not wallets:
                raise ValueError("No Hatom members discovered yet")
            index = self._wallet_cursor % len(wallets)
            selected = [wallets[(index + i) % len(wallets)] for i in range(min(self.batch, len(wallets)))]
            self._wallet_cursor = (index + len(selected)) % len(wallets)
            found: list[dict[str, Any]] = []
            self.status["checked"] = len(selected)
            for borrower in selected:
                try:
                    if not self.client.risky(borrower):
                        continue
                    account_markets = [m for m in self.client.account_markets(borrower) if m in self._markets][:20]
                    borrow_pairs: list[tuple[str, int]] = []
                    collateral_markets: list[str] = []
                    for market in account_markets:
                        try:
                            amount = self.client.borrow_amount(market, borrower)
                            if amount > 0:
                                borrow_pairs.append((market, amount))
                            if self.client.collateral_tokens(market, borrower) > 0:
                                collateral_markets.append(market)
                        except (ValueError, requests.RequestException) as exc:
                            logger.warning("Hatom account market query failed (%s)", type(exc).__name__)
                            self.status["rejected_oracle_or_contract"] += 1
                    if not borrow_pairs or not collateral_markets:
                        continue
                    # Stage 1: contract reports debt and risky collateral.
                    # Stage 2: fresh view methods confirm a meaningful repayment
                    # and nonzero redeemable collateral, NOT net-profit or fill.
                    candidate = None
                    for debt_market, raw_amount in borrow_pairs[:4]:
                        if candidate is not None and candidate["category"] == "ONCHAIN_ELIGIBLE":
                            break
                        for collateral_market in collateral_markets[:4]:
                            if candidate is None:
                                candidate = {
                                    "borrower": borrower,
                                    "debt_token": "market-contract",
                                    "collateral_token": "market-contract",
                                    "borrow_market": debt_market,
                                    "collateral_market": collateral_market,
                                    "raw_borrow": str(raw_amount),
                                    "health_factor": None,
                                    "max_repay_usd": None,
                                    "category": "ONCHAIN_RISKY",
                                    "observed_at": time.time(),
                                }
                            try:
                                quote = self.client.meaningful_liquidation_check(
                                    debt_market, collateral_market, borrower, raw_amount
                                )
                                if quote:
                                    candidate = dict(candidate)
                                    candidate.update({
                                        "borrow_market": debt_market,
                                        "collateral_market": collateral_market,
                                        "raw_borrow": str(raw_amount),
                                        "category": "ONCHAIN_ELIGIBLE",
                                        **quote,
                                    })
                                    break
                            except (ValueError, requests.RequestException) as exc:
                                self.status["rejected_oracle_or_contract"] += 1
                                logger.warning("Hatom eligibility preflight failed (%s)", type(exc).__name__)
                    if candidate is not None:
                        found.append(candidate)
                except (ValueError, requests.RequestException) as exc:
                    logger.warning("Hatom account risk query failed (%s)", type(exc).__name__)
                    self.status["rejected_oracle_or_contract"] += 1
                if len(found) >= 5:
                    break
            self.status["last_error"] = None
            self.status["last_scan"] = int(time.time())
            return found
        except Exception as exc:
            self.status["last_error"] = type(exc).__name__ + ": " + str(exc)[:140]
            logger.warning("Hatom mainnet scanner failed (%s)", type(exc).__name__)
            raise
        finally:
            self._lock.release()


def inspect_borrower_live(borrower: str, *, client: VmClient | None = None,
                          max_markets: int = 16, max_routes: int = 2
                          ) -> list[dict[str, Any]]:
    """On-demand read-only re-discovery of stage-2 opportunities for a borrower.

    Enables manual rechecks after restarts or by replying to old Telegram
    alerts. Uses fresh borrows/collateral and a real-sized Controller preflight.
    Never signs transactions. Returns no candidates on stale/healthy accounts.
    """
    address_decode(borrower)
    client = client if client is not None else VmClient(timeout=8)
    if not client.risky(borrower):
        return []
    markets = client.account_markets(borrower)[:max_markets]
    debts: list[tuple[str, int]] = []
    collaterals: list[str] = []
    for market in markets:
        try:
            amount = client.borrow_amount(market, borrower)
            collateral = client.collateral_tokens(market, borrower)
            if amount > 1:
                debts.append((market, amount))
            if collateral > 0:
                collaterals.append(market)
        except (ValueError, requests.RequestException) as exc:
            logger.warning("Hatom borrower manual market check failed (%s)", type(exc).__name__)
    if not debts or not collaterals:
        return []
    results: list[dict[str, Any]] = []
    for debt_market, borrow_raw in debts[:4]:
        for collateral_market in collaterals[:4]:
            try:
                quote = client.meaningful_liquidation_check(
                    debt_market, collateral_market, borrower, borrow_raw
                )
                if not quote:
                    continue
                results.append({
                    "borrower": borrower,
                    "debt_token": "market-contract",
                    "collateral_token": "market-contract",
                    "borrow_market": debt_market,
                    "collateral_market": collateral_market,
                    "raw_borrow": str(borrow_raw),
                    "health_factor": None,
                    "max_repay_usd": None,
                    "category": "ONCHAIN_ELIGIBLE",
                    "observed_at": time.time(),
                    **quote,
                })
                if len(results) >= max_routes:
                    return results
            except (ValueError, requests.RequestException) as exc:
                logger.warning("Hatom manual eligibility check failed (%s)", type(exc).__name__)
    return results


_SCANNER: HatomScanner | None = None


def get_scanner() -> HatomScanner:
    global _SCANNER
    if _SCANNER is None:
        batch = os.getenv("HATOM_ONCHAIN_BATCH_SIZE", "15")
        try:
            batch_size = int(batch)
        except ValueError:
            batch_size = 15
        _SCANNER = HatomScanner(batch=batch_size)
    return _SCANNER


def scan_mainnet() -> list[dict[str, Any]]:
    return get_scanner().scan()

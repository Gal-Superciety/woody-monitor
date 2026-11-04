"""Read-only Hatom liquidation TRANSACTION dry-run diagnostics.

No wallet signing, no keys, no broadcasting. A read-only public sender address
may be configured to query network gas estimation / isolated simulation. Full
multi-tx liquidation + collateral redemption + DEX swap is NOT simulated;
its execution cannot be guaranteed and thus no "verified profit" is emitted.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import time
from typing import Any

import requests

from core.hatom_onchain import address_decode

logger = logging.getLogger(__name__)

GATEWAY = "https://gateway.multiversx.com"
ESDT_ID = re.compile(r"^[A-Za-z0-9]{3,20}-[a-z0-9]{6}$")
MAX_GAS = 600_000_000


class DryRunUnavailable(ValueError):
    """A simulation was impossible, incomplete or rejected by the network."""


def positive_int(value: Any, *, maximum: int = 10**80) -> int:
    if isinstance(value, bool) or not str(value).isdecimal():
        raise DryRunUnavailable("Invalid positive transaction amount")
    n = int(value)
    if not 0 < n <= maximum:
        raise DryRunUnavailable("Amount outside transaction limits")
    return n


def tohex(data: bytes) -> str:
    return data.hex()


def number_arg(value: int) -> str:
    value = positive_int(value)
    return tohex(value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big"))


def liquidation_call(row: dict[str, Any], debt_token: str) -> dict[str, Any]:
    """Construct DATA ONLY based on official Hatom money-market liquidateBorrow.

    For ESDT repayment use ESDTTransfer@token@amount@liquidateBorrow@borrower@collateral.
    For EGLD use direct liquidateBorrow@borrower@collateral with EGLD value.
    Do not use optional minimum seized hTokens because its ABI/payment semantics
    require further validation; no transaction is ever sent.
    """
    if row.get("category") != "ONCHAIN_ELIGIBLE":
        raise DryRunUnavailable("Requires fresh Hatom Stage-2 eligibility")
    borrower = row["borrower"]
    debt_market = row["borrow_market"]
    collateral_market = row["collateral_market"]
    for a in (borrower, debt_market, collateral_market):
        address_decode(a)
    repay = positive_int(row.get("repay_raw"))
    args = [address_decode(borrower).hex(), address_decode(collateral_market).hex()]
    if debt_token == "EGLD":
        data = "@".join(["liquidateBorrow", *args])
        value = str(repay)
        kind = "EGLD"
    else:
        if not ESDT_ID.fullmatch(debt_token):
            raise DryRunUnavailable("Unknown debt token for liquidation")
        data = "@".join([
            "ESDTTransfer", debt_token.encode("ascii").hex(),
            number_arg(repay), "liquidateBorrow".encode("ascii").hex(), *args,
        ])
        value = "0"
        kind = "ESDT"
    return {
        "receiver": debt_market,
        "data": base64.b64encode(data.encode("ascii")).decode("ascii"),
        "value": value,
        "payment": kind,
        "repay_token": debt_token,
        "repay_raw": repay,
        "borrower": borrower,
        "debt_market": debt_market,
        "collateral_market": collateral_market,
        "prepared_at": time.time(),
    }


class ReadOnlySimulationGateway:
    """Allowlisted network cost and simulation APIs, NEVER /transaction/send."""

    def __init__(self, *, session: Any = None, timeout: int = 8):
        self.session = session if session is not None else requests.Session()
        self.timeout = max(2, min(int(timeout), 15))

    def _json(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> Any:
        if (method, path) not in {
            ("GET", "/network/config"),
            ("POST", "/transaction/cost"),
            ("POST", "/transaction/simulate?checkSignature=false"),
        } and not (
            method == "GET"
            and path.startswith("/address/")
            and path.count("/") == 2
        ):
            raise DryRunUnavailable("Read-only gateway endpoint not allowlisted")
        if method == "GET" and path.startswith("/address/"):
            address_decode(path.rsplit("/", 1)[-1])
        url = GATEWAY + path
        try:
            if method == "GET":
                response = self.session.get(url, timeout=self.timeout, allow_redirects=False)
            else:
                response = self.session.post(
                    url, json=body, timeout=self.timeout, allow_redirects=False,
                    headers={"Accept": "application/json"},
                )
            response.raise_for_status()
            if len(response.content) > 350_000:
                raise DryRunUnavailable("Oversized network simulation reply")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DryRunUnavailable("Simulation gateway unavailable") from exc
        if not isinstance(data, dict) or data.get("error") or data.get("code") not in (None, "successful"):
            raise DryRunUnavailable("Gateway query rejected")
        if not isinstance(data.get("data"), dict):
            raise DryRunUnavailable("Missing simulation result data")
        return data["data"]

    def sender_nonce(self, sender: str) -> int:
        address_decode(sender)
        data = self._json("GET", "/address/" + sender)
        account = data.get("account")
        if not isinstance(account, dict) or type(account.get("nonce")) is not int:
            raise DryRunUnavailable("Cannot obtain public simulation sender nonce")
        nonce = account["nonce"]
        if not 0 <= nonce <= 2**64 - 1:
            raise DryRunUnavailable("Invalid sender nonce")
        return nonce

    def network(self) -> dict[str, Any]:
        data = self._json("GET", "/network/config")
        config = data.get("config")
        if not isinstance(config, dict):
            raise DryRunUnavailable("Missing network configuration")
        chain = config.get("erd_chain_id")
        price = config.get("erd_min_gas_price")
        if chain != "1" or type(price) is not int or not 0 < price <= 10**12:
            raise DryRunUnavailable("Unexpected chain ID or gas price")
        return {"chainID": chain, "gasPrice": price}

    def cost(self, tx: dict[str, Any]) -> int:
        data = self._json("POST", "/transaction/cost", body=tx)
        gas = data.get("txGasUnits")
        return positive_int(gas, maximum=MAX_GAS)

    def simulate(self, tx: dict[str, Any]) -> dict[str, Any]:
        """No private key. Dummy signature only, checkSignature=false, never send."""
        payload = dict(tx)
        payload["signature"] = "00" * 64
        data = self._json("POST", "/transaction/simulate?checkSignature=false", body=payload)
        if "senderShard" in data or "receiverShard" in data:
            return {
                "status": "incomplete_cross_shard",
                "reason": "Cross-shard simulation cannot prove end-to-end execution",
            }
        status = str(data.get("status", "unknown")).lower()
        if status == "success":
            return {"status": "isolated_success", "reason": "Only liquidation call was simulated"}
        return {
            "status": "failed_or_incomplete",
            "reason": str(data.get("failReason") or "No successful execution proof")[:180],
        }


def dryrun(row: dict[str, Any], *, vm: Any = None, gateway: Any = None,
           sender: str | None = None) -> dict[str, Any]:
    """Build a draft, optionally estimate gas and simulate without broadcasting.

    No sender is configured by default. Without a public simulation sender,
    no transaction can be honestly tested against funded account balances.
    """
    if vm is None:
        from core.hatom_onchain import VmClient
        vm = VmClient(timeout=8)
    from core.hatom_profit import underlying_id
    token = underlying_id(vm, row["borrow_market"])
    draft = liquidation_call(row, token)
    report: dict[str, Any] = {
        "borrower": row["borrower"],
        "debt_token": token,
        "repay_raw": draft["repay_raw"],
        "payment": draft["payment"],
        "call_built": True,
        "cost_status": "not_estimated",
        "sim_status": "not_simulated",
        "full_pipeline_simulated": False,
        "verified_net_profit": False,
        "transaction_sent": False,
        "liquidation_gas_units": None,
        "liquidation_gas_usd": None,
        "reason": None,
        "missing": [
            "funded public sender account (only for simulation, NOT private key)",
            "simulated hToken redemption and unwrap",
            "simulated final DEX swap after liquidation",
            "total gas cost across every required transaction",
            "atomic, same-state execution proof and market competition",
        ],
    }
    sender = sender if sender is not None else os.getenv("HATOM_SIMULATION_SENDER", "").strip()
    if not sender:
        report["reason"] = "No public simulation sender configured; no gas or tx result inferred"
        return report
    address_decode(sender)
    gateway = gateway if gateway is not None else ReadOnlySimulationGateway()
    try:
        network = gateway.network()
        tx = {
            "nonce": gateway.sender_nonce(sender),
            "value": draft["value"],
            "receiver": draft["receiver"],
            "sender": sender,
            "gasPrice": network["gasPrice"],
            # Conservative upper bound to probe cost; never a tx broadcast.
            "gasLimit": MAX_GAS,
            "data": draft["data"],
            "chainID": network["chainID"],
            "version": 1,
        }
        gas_units = gateway.cost(tx)
        report["liquidation_gas_units"] = gas_units
        report["cost_status"] = "isolated_liquidation_cost_estimated"
        # No funds or signer at this stage; without a funded account a
        # simulation usually fails for insufficient fee or token balance.
        outcome = gateway.simulate(tx)
        report["sim_status"] = outcome["status"]
        report["reason"] = outcome["reason"]
        report["missing"][0] = "no real wallet signing or broadcast"
        # Even status='isolated_success' is not an end-to-end liquidation.
        return report
    except (ValueError, requests.RequestException, KeyError) as exc:
        report["reason"] = str(exc)[:180]
        return report


def format_report(result: dict[str, Any]) -> str:
    lines = [
        "🧪 HATOM — PRIVATE TRANSACTION DRY-RUN",
        "READ-ONLY. No wallet signing. No transaction sent.",
        "Borrower: " + result["borrower"],
        "Debt token: " + result["debt_token"],
        "Repayment (raw): " + str(result["repay_raw"]),
        "Draft contract calldata: " + ("BUILT" if result["call_built"] else "UNAVAILABLE"),
        "Liquidation cost: " + result["cost_status"],
        "Network simulation: " + result["sim_status"],
    ]
    if result.get("liquidation_gas_units") is not None:
        lines.append("Isolated liquidation gas: " + str(result["liquidation_gas_units"]) + " units")
    if result.get("reason"):
        lines.append("Note: " + result["reason"])
    lines.extend([
        "",
        "⚠️ FULL LIQUIDATION→REDEEM→SWAP: NOT SIMULATED",
        "Profit after real gas/route: NOT VERIFIED",
        "No EGLD used; no private keys; no automatic execution.",
    ])
    return "\n".join(lines)[:3500]

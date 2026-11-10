"""XOXNO liquidation view ABI, read-only DEX scenario, private command tests."""
import asyncio
import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import xoxno_profit as p
from core import xoxno_lending_watch as watch
from core.hatom_profit import Asset

ID = "XLEND-18dc6f-eb"
DEBT = "USDC-c76f1f"
SEIZE = "XEGLD-e413ed"


def blob(value: int) -> bytes:
    if value == 0:
        return b"\x00\x00\x00\x00"
    raw = p.top_int(value)
    return p.nested(raw)


def decimal(value: int, places: int) -> bytes:
    return blob(value) + places.to_bytes(4, "big")


def encoded_estimate(
    seized: int = 13_000_000, fee: int = 200_000,
    refund: int = 0,
) -> bytes:
    rows = (
        b"\x00\x00\x00\x01" + p.encode_payment(SEIZE, seized)
        + b"\x00\x00\x00\x01" + p.encode_payment(SEIZE, fee)
        + (b"\x00\x00\x00\x01" + p.encode_payment(DEBT, refund)
           if refund else b"\x00\x00\x00\x00")
        + decimal(3 * 10**18, 18)
        + decimal(500, 4)
    )
    return rows


class Markets:
    def __init__(self, *, output=12_000_000, gas_price=10**9):
        self.output = output
        self.price = gas_price
        self.quoted = []

    def asset(self, token):
        if token == "EGLD":
            return Asset("EGLD", "EGLD", 18, Decimal("3"), 1)
        if token in (DEBT, SEIZE):
            return Asset(token, token, 6, Decimal("1"), 1)
        raise AssertionError("Unexpected token " + token)

    def dex_quote(self, token_in, token_out, raw):
        self.quoted.append((token_in, token_out, raw))
        return {"amount_out_min_raw": self.output, "route_count": 2}

    def gas_price(self):
        return self.price


class Vm:
    def __init__(self, *, status=b"\x01", quote=None):
        self.status = status
        self.quote = [encoded_estimate()] if quote is None else quote
        self.calls = []

    def query(self, contract, name, args=None):
        self.calls.append((contract, name, args))
        if name == "canBeLiquidated":
            return [self.status]
        if name == "getBorrowAmountForToken":
            return [decimal(10_000_000, 6)]
        if name == "liquidationEstimations":
            if args[1] != p.encode_payment(DEBT, 10_000_000):
                # The fixture models a protocol which only accepts the full
                # proposed repayment; partial attempts fail closed.
                return [b"\x01"]
            return self.quote
        raise AssertionError(name)


class Positions:
    def debt_tokens(self, nonce):
        if nonce != 235:
            raise AssertionError(nonce)
        return [DEBT]


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "XOXNO_GAS_UNITS_ASSUMED": "180000000",
            "XOXNO_SAFETY_BPS": "100", "XOXNO_SAFETY_USD": "0.50",
            "XOXNO_ALERT_MIN_NET_USD": "0.10",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_payment_abi_bytes(self):
        encoded = p.encode_payment(DEBT, 1234)
        expect = (
            len(DEBT).to_bytes(4, "big") + DEBT.encode()
            + b"\x00" * 8 + b"\x00\x00\x00\x02\x04\xd2"
        )
        self.assertEqual(encoded, expect)

    def test_decode_official_estimate_schema(self):
        report = p.decode_estimate([encoded_estimate(refund=100_000)])
        self.assertEqual(report["seized"], [{"token": SEIZE, "raw": 13_000_000}])
        self.assertEqual(report["fees"], [{"token": SEIZE, "raw": 200_000}])
        self.assertEqual(report["refunds"], [{"token": DEBT, "raw": 100_000}])
        self.assertEqual(report["bonus_bps"], Decimal("0.05"))
        self.assertEqual(p.decode_amount([decimal(10_000_000, 6)]), (10_000_000, 6))

    def test_fails_closed_on_malformed_quote(self):
        with self.assertRaises(p.CalculationUnavailable):
            p.decode_estimate([encoded_estimate()[:-3]])
        with self.assertRaises(p.CalculationUnavailable):
            p.decode_estimate([encoded_estimate() + b"\x00"])
        with self.assertRaises(p.CalculationUnavailable):
            p.decode_estimate([])
        with self.assertRaises(p.CalculationUnavailable):
            p.encode_payment("MALICIOUS", 100)

    def test_live_controller_plus_dex_indicative_surplus(self):
        vm = Vm()
        market = Markets()
        report = p.calculate(ID, vm=vm, positions=Positions(), market=market)
        self.assertEqual(report["identifier"], ID)
        self.assertEqual(report["repay_units"], Decimal(10))
        self.assertEqual(report["repay_usd"], Decimal(10))
        self.assertEqual(report["reference_collateral_usd"], Decimal("12.8"))
        self.assertEqual(report["dex_min_usd"], Decimal(12))
        self.assertEqual(report["estimated_gas_usd"], Decimal("0.54"))
        self.assertEqual(report["safety_buffer_usd"], Decimal("0.50"))
        self.assertEqual(report["scenario_net_usd"], Decimal("0.96"))
        self.assertTrue(report["clears_quarter_dollar"])
        self.assertFalse(report["verified_profit"])
        self.assertFalse(report["full_pipeline_simulated"])
        self.assertFalse(report["transaction_sent"])
        self.assertEqual(market.quoted[0], (SEIZE, DEBT, 12_800_000))
        calls = [name for _, name, _ in vm.calls]
        self.assertEqual(calls[0], "canBeLiquidated")
        self.assertIn("liquidationEstimations", calls)
        # A single repayment is a raw TopEncode ManagedVec of 1 payment,
        # without the nested 4-byte vector length.
        query = next(args for _, name, args in vm.calls if name == "liquidationEstimations")
        self.assertEqual(query[0], b"\xeb")
        self.assertEqual(query[1], p.encode_payment(DEBT, 10_000_000))
        message = p.format_report(report)
        self.assertIn("Indicative net", message)
        self.assertIn("NOT VERIFIED", message)

    def test_unprofitable_quote_is_not_claimed_as_profit(self):
        report = p.calculate(
            ID, vm=Vm(), positions=Positions(), market=Markets(output=10_050_000)
        )
        self.assertFalse(report["clears_quarter_dollar"])
        self.assertLess(report["scenario_net_usd"], 0)
        self.assertIn("BELOW USD 0.10", p.format_report(report))

    def test_ten_cent_calculated_profit_passes_new_floor(self):
        # 11.14 DEX min-out - 10.00 repay - 0.54 assumed gas
        # - 0.50 extra reserve = +0.10 USD indicative profit.
        report = p.calculate(
            ID, vm=Vm(), positions=Positions(), market=Markets(output=11_140_000)
        )
        self.assertEqual(report["scenario_net_usd"], Decimal("0.10"))
        self.assertTrue(report["clears_alert_minimum"])
        self.assertFalse(report["clears_quarter_dollar"])
        self.assertIn("MODELED >= USD 0.10", p.format_report(report))
        under = p.calculate(
            ID, vm=Vm(), positions=Positions(), market=Markets(output=11_130_000)
        )
        self.assertEqual(under["scenario_net_usd"], Decimal("0.09"))
        self.assertFalse(under["clears_alert_minimum"])
        self.assertIn("BELOW USD 0.10", p.format_report(under))

    def test_healthy_account_never_gets_quote(self):
        vm = Vm(status=b"\x00")
        market = Markets()
        with self.assertRaises(p.CalculationUnavailable):
            p.calculate(ID, vm=vm, positions=Positions(), market=market)
        self.assertEqual(len(vm.calls), 1)
        self.assertEqual(market.quoted, [])

    def test_missing_dex_route_blocks_profit(self):
        class NoDex(Markets):
            def dex_quote(self, token_in, token_out, raw):
                raise p.QuoteUnavailable("No live route")
        with self.assertRaises(p.CalculationUnavailable):
            p.calculate(ID, vm=Vm(), positions=Positions(), market=NoDex())

    def test_quote_with_unexpected_fee_or_refund_fails_closed(self):
        bad = encoded_estimate(refund=50_000_000)
        with self.assertRaises(p.CalculationUnavailable):
            p.calculate(ID, vm=Vm(quote=[bad]), positions=Positions(), market=Markets())

    def test_admin_can_request_profit_by_account_nft(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=42, type="private"),
            effective_user=SimpleNamespace(id=42),
            message=SimpleNamespace(reply_text=AsyncMock(), reply_to_message=None),
        )
        report = p.calculate(ID, vm=Vm(), positions=Positions(), market=Markets())
        with patch.dict(os.environ, {"ENABLE_XOXNO_LENDING_WATCH": "true",
                                      "ADMIN_TELEGRAM_ID": "42"}), patch.object(
            p, "calculate", return_value=report
        ) as calculate:
            asyncio.run(watch.profit_command(update, SimpleNamespace(args=[ID])))
        calculate.assert_called_once_with(ID)
        self.assertIn("PRIVATE PROFIT SCENARIO", update.message.reply_text.await_args.args[0])

    def test_group_rejected_for_profit(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=-10010, type="supergroup"),
            effective_user=SimpleNamespace(id=42),
            message=SimpleNamespace(reply_text=AsyncMock(), reply_to_message=None),
        )
        with patch.dict(os.environ, {"ADMIN_TELEGRAM_ID": "42",
                                      "ENABLE_XOXNO_LENDING_WATCH": "true"}), patch.object(
            p, "calculate"
        ) as calculator:
            asyncio.run(watch.profit_command(update, SimpleNamespace(args=[ID])))
        calculator.assert_not_called()
        update.message.reply_text.assert_not_awaited()

    def test_private_reply_accepts_nft_from_alert(self):
        update = SimpleNamespace(message=SimpleNamespace(
            reply_to_message=SimpleNamespace(text="Account NFT: " + ID)
        ))
        self.assertEqual(watch._requested_nft(update, SimpleNamespace(args=[])), ID)


if __name__ == "__main__":
    unittest.main()

"""Offline tests for Hatom token decimals, USD mark prices and fail-closed profit scenario."""
import os
import time
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import hatom_profit as calc
from core.hatom_onchain import CONTROLLER


class FakeVM:
    def query(self, market, function, args=None):
        assert function == "getUnderlyingId"
        if market == "debt":
            return [b"USDC-c76f1f"]
        if market == "collateral":
            return [b"EGLD"]
        return []


class FakePrices:
    def __init__(self):
        self.tokens = {
            "USDC-c76f1f": calc.Asset("USDC-c76f1f", "USDC", 6, Decimal("1"), time.time()),
            "EGLD": calc.Asset("EGLD", "EGLD", 18, Decimal("3.5"), time.time()),
        }

    def asset(self, identifier):
        return self.tokens[identifier]

    def gas_price(self):
        return 1000000000


def risk():
    return {
        "category": "ONCHAIN_ELIGIBLE",
        "borrower": CONTROLLER,
        "borrow_market": "debt",
        "collateral_market": "collateral",
        "repay_raw": 200_000_000,      # 200 USDC @ 6 decimals
        "collateral_underlying_raw": 60 * 10**18,  # 60 EGLD
        "raw_borrow": "800000000",
    }


class FakeResponse:
    def __init__(self, data):
        self.content = b'{"ok":true}'
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class CalcTests(unittest.TestCase):
    def setUp(self):
        calc._CACHE.clear()

    def test_model_gross_fees_and_scenario_net(self):
        env = {"HATOM_GAS_UNITS_ASSUMED": "60000000",
               "HATOM_SWAP_LOSS_BPS_ASSUMED": "150"}
        with patch.dict(os.environ, env):
            result = calc.estimate(risk(), vm=FakeVM(), prices=FakePrices())
        self.assertEqual(result["repay_units"], Decimal("200"))
        self.assertEqual(result["collateral_units"], Decimal("60"))
        self.assertEqual(result["repay_usd"], Decimal("200"))
        self.assertEqual(result["collateral_usd"], Decimal("210.0"))
        self.assertEqual(result["gross_usd"], Decimal("10.0"))
        self.assertEqual(result["assumed_swap_cost_usd"], Decimal("3.15"))
        self.assertEqual(result["assumed_gas_cost_usd"], Decimal("0.210"))
        self.assertEqual(result["scenario_net_usd"], Decimal("6.640"))
        self.assertFalse(result["verified_profit"])
        self.assertFalse(result["executable_dex_quote"])
        output = "\n".join(calc.format_scenario(result))
        self.assertIn("200 USDC", output)
        self.assertIn("60 EGLD", output)
        self.assertIn("NOT AN EXECUTABLE", output)

    def test_fail_closed_when_no_token_or_price(self):
        invalid = risk()
        invalid["category"] = "ONCHAIN_RISKY"
        with self.assertRaises(calc.QuoteUnavailable):
            calc.estimate(invalid, vm=FakeVM(), prices=FakePrices())
        class NoPrice(FakePrices):
            def asset(self, identifier):
                raise calc.QuoteUnavailable("Price missing")
        with self.assertRaisesRegex(calc.QuoteUnavailable, "Price missing"):
            calc.estimate(risk(), vm=FakeVM(), prices=NoPrice())
        with self.assertRaises(calc.QuoteUnavailable):
            calc.underlying_id(FakeVM(), "unknown")

    def test_gross_is_not_net_even_when_positive(self):
        high_costs = {"HATOM_GAS_UNITS_ASSUMED": "300000000",
                      "HATOM_SWAP_LOSS_BPS_ASSUMED": "2500"}
        with patch.dict(os.environ, high_costs):
            data = calc.estimate(risk(), vm=FakeVM(), prices=FakePrices())
        self.assertGreater(data["gross_usd"], 0)
        self.assertLess(data["scenario_net_usd"], 0)
        self.assertFalse(data["verified_profit"])

    def test_decimal_precision_and_invalid_numeric_inputs(self):
        self.assertEqual(calc.human("34619086873", 18), Decimal("0.000000034619086873"))
        for value in (None, float("nan"), 0, -1, True):
            with self.assertRaises(calc.QuoteUnavailable):
                calc._decimal(value)
        with self.assertRaises(calc.QuoteUnavailable):
            calc.human("1", 31)
        with self.assertRaises(calc.QuoteUnavailable):
            calc.human("not digits", 18)

    def test_api_price_metadata_and_gas_queries(self):
        session = Mock()
        session.get.side_effect = [
            FakeResponse({"identifier": "USDC-c76f1f", "decimals": 6,
                          "ticker": "USDC", "price": 0.9998}),
            FakeResponse({"price": 3.45}),
            FakeResponse({"data": {"config": {"erd_min_gas_price": 1000000000}}}),
        ]
        md = calc.MarketData(session=session)
        token = md.asset("USDC-c76f1f")
        self.assertEqual(token.decimals, 6)
        self.assertEqual(token.price_usd, Decimal("0.9998"))
        self.assertEqual(md.asset("EGLD").decimals, 18)
        self.assertEqual(md.gas_price(), 1000000000)
        urls = [c.args[0] for c in session.get.call_args_list]
        self.assertEqual(urls, [
            "https://api.multiversx.com/tokens/USDC-c76f1f",
            "https://api.multiversx.com/economics",
            "https://gateway.multiversx.com/network/config"
        ])
        self.assertTrue(all(c.kwargs["allow_redirects"] is False
                            for c in session.get.call_args_list))

    def test_xoxno_quote_checks_exact_input_route_and_min_output(self):
        session = Mock()
        session.get.return_value = FakeResponse({
            "from": "WEGLD-bd4d79", "to": "USDC-c76f1f",
            "amountIn": "1000000000000000000",
            "amountOut": "3451159", "amountOutMin": "3416647",
            "paths": [{"swaps": [{"dex": "xExchange"}]}],
        })
        quote = calc.MarketData(session=session).dex_quote(
            "EGLD", "USDC-c76f1f", 10**18
        )
        self.assertEqual(quote["amount_out_min_raw"], 3416647)
        self.assertEqual(quote["route_count"], 1)
        request = session.get.call_args
        self.assertEqual(request.args[0], "https://swap.xoxno.com/api/v1/quote")
        self.assertFalse(request.kwargs["allow_redirects"])
        self.assertEqual(request.kwargs["params"]["from"], "WEGLD-bd4d79")
        self.assertEqual(request.kwargs["params"]["amountIn"], str(10**18))

    def test_unroutable_or_invalid_live_quote_fails_closed(self):
        session = Mock()
        session.get.return_value = FakeResponse({
            "from": "WEGLD-bd4d79", "to": "USDC-c76f1f",
            "amountIn": "1000000000000000000",
            "amountOut": "3451159", "amountOutMin": "9999999999999",
            "paths": [{"swaps": []}],
        })
        with self.assertRaises(calc.QuoteUnavailable):
            calc.MarketData(session=session).dex_quote("EGLD", "USDC-c76f1f", 10**18)
        session.get.return_value = FakeResponse({
            "from": "WEGLD-bd4d79", "to": "USDC-c76f1f",
            "amountIn": "1000000000000000000",
            "amountOut": "3451159", "amountOutMin": "3416647",
            "paths": [],
        })
        with self.assertRaises(calc.QuoteUnavailable):
            calc.MarketData(session=session).dex_quote("EGLD", "USDC-c76f1f", 10**18)

    def test_missing_price_or_wrong_token_id_is_rejected(self):
        session = Mock()
        session.get.return_value = FakeResponse({
            "identifier": "USDC-notreal", "ticker": "USDC", "decimals": 6, "price": 1.0
        })
        with self.assertRaisesRegex(calc.QuoteUnavailable, "mismatch"):
            calc.MarketData(session=session).asset("USDC-c76f1f")
        session.get.return_value = FakeResponse({
            "identifier": "USDC-c76f1f", "ticker": "USDC", "decimals": 6
        })
        with self.assertRaises(calc.QuoteUnavailable):
            calc.MarketData(session=session).asset("USDC-c76f1f")
        self.assertFalse(any("private" in str(call).lower() for call in session.get.call_args_list))


if __name__ == "__main__":
    unittest.main()

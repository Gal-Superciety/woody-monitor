"""Unit tests for fail-closed Hatom priority alert profitability screen."""
import os
import time
import unittest
from decimal import Decimal
from unittest.mock import patch

from core.hatom_profit_filter import eligible_for_priority_alert, limits


def sample(*, repay="200", received="209", gas="0.25", observed=None,
           has_quote=True):
    value = {
        "category": "INDICATIVE_ONLY",
        "verified_profit": False,
        "executable_dex_quote": False,
        "repay_usd": Decimal(repay),
        "quote_min_usd": Decimal(received),
        "gross_usd": Decimal("10"),
        "assumed_gas_cost_usd": Decimal(gas),
        "quote_net_after_assumed_gas_usd": (
            Decimal(received) - Decimal(repay) - Decimal(gas)
        ),
        "dex_quote": {
            "route_count": 2,
            "amount_out_min_raw": 209_000_000,
            "quote_received_at": time.time() if observed is None else observed,
        } if has_quote else None,
    }
    return value


class FilterTests(unittest.TestCase):
    def test_default_limits_allow_small_repayment_with_quarter_dollar_floor(self):
        with patch.dict(os.environ, {}, clear=True):
            rules = limits()
        self.assertEqual(rules["min_repay_usd"], Decimal("0"))
        self.assertEqual(rules["min_net_usd"], Decimal("0.25"))
        self.assertEqual(rules["buffer_bps"], 100)
        self.assertEqual(rules["fixed_buffer_usd"], Decimal("0.50"))

    def test_positive_dex_minimum_after_extra_buffer(self):
        passed, reason, result = eligible_for_priority_alert(sample())
        self.assertTrue(passed, reason)
        self.assertEqual(result["safety_buffer_usd"], Decimal("2"))
        self.assertEqual(result["screened_surplus_usd"], Decimal("6.75"))
        self.assertFalse(result["verified_profit"])

    def test_small_repayment_can_pass_when_net_after_costs_and_buffer_is_at_least_025(self):
        # Under the old $25 minimum this valid, modeled $0.70 result was suppressed.
        passed, reason, result = eligible_for_priority_alert(
            sample(repay="12", received="13.40", gas="0.20")
        )
        self.assertTrue(passed, reason)
        self.assertEqual(result["safety_buffer_usd"], Decimal("0.50"))
        self.assertEqual(result["screened_surplus_usd"], Decimal("0.70"))
        self.assertFalse(result["verified_profit"])

    def test_quarter_dollar_is_a_hard_floor_after_extra_buffer(self):
        exactly, _, value = eligible_for_priority_alert(
            sample(repay="10", received="10.95", gas="0.20")
        )
        self.assertTrue(exactly)
        self.assertEqual(value["screened_surplus_usd"], Decimal("0.25"))
        under, _, _ = eligible_for_priority_alert(
            sample(repay="10", received="10.949999", gas="0.20")
        )
        self.assertFalse(under)

    def test_zero_debt_does_not_pass_despite_removing_size_limit(self):
        passed, _, _ = eligible_for_priority_alert(
            sample(repay="0", received="10", gas="0.20")
        )
        self.assertFalse(passed)

    def test_prior_negative_examples_are_filtered(self):
        for value in (
            sample(repay="0.000038", received="0.000040", gas="0.21"),
            sample(repay="0.05", received="0.0535", gas="0.21"),
        ):
            passed, _, result = eligible_for_priority_alert(value)
            self.assertFalse(passed)
            self.assertIsNone(result)

    def test_no_dex_quote_no_alert_even_high_reference_margin(self):
        passed, reason, result = eligible_for_priority_alert(
            sample(repay="200", received="260", has_quote=False)
        )
        self.assertFalse(passed)
        self.assertIn("no live DEX", reason)
        self.assertIsNone(result)

    def test_not_enough_after_safety_buffer(self):
        passed, _, _ = eligible_for_priority_alert(
            sample(repay="200", received="202.1", gas="0.25")
        )
        self.assertFalse(passed)

    def test_requires_fresh_route_and_nonzero_paths(self):
        old = sample(observed=time.time() - 200)
        self.assertFalse(eligible_for_priority_alert(old)[0])
        old["dex_quote"]["quote_received_at"] = time.time() + 5
        self.assertFalse(eligible_for_priority_alert(old)[0])
        old["dex_quote"]["quote_received_at"] = time.time()
        old["dex_quote"]["route_count"] = 0
        self.assertFalse(eligible_for_priority_alert(old)[0])

    def test_inconsistent_figures_and_invalid_verification_markers(self):
        data = sample()
        data["quote_net_after_assumed_gas_usd"] = Decimal("99999")
        self.assertFalse(eligible_for_priority_alert(data)[0])
        data = sample()
        data["verified_profit"] = True
        self.assertFalse(eligible_for_priority_alert(data)[0])
        data = sample()
        data["repay_usd"] = Decimal("NaN")
        self.assertFalse(eligible_for_priority_alert(data)[0])

    def test_failed_dex_quote_cannot_pass(self):
        data = sample()
        data["dex_quote"] = {"route_count": 2}
        self.assertFalse(eligible_for_priority_alert(data)[0])

    def test_conservative_config_validation(self):
        with patch.dict(os.environ, {"HATOM_ALERT_MIN_NET_USD": "-3"}):
            with self.assertRaises(ValueError):
                limits()
        with patch.dict(os.environ, {"HATOM_ALERT_MAX_QUOTE_AGE_SECONDS": "100000"}):
            with self.assertRaises(ValueError):
                limits()


if __name__ == "__main__":
    unittest.main()

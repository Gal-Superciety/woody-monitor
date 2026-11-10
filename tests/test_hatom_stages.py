"""Hatom two-stage Telegram alert flood-prevention and fail-closed preflight."""
import asyncio
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core import hatom_liquidations as watch
from core import hatom_stages as stages
from core.hatom_onchain import address_encode

A = address_encode(bytes([1]) * 32)
B = address_encode(bytes([2]) * 32)
DEBT = address_encode(bytes([3]) * 32)
COLL = address_encode(bytes([4]) * 32)


def sample(borrower=A, category="ONCHAIN_ELIGIBLE"):
    return {
        "borrower": borrower,
        "category": category,
        "borrow_market": DEBT,
        "collateral_market": COLL,
        "raw_borrow": "1000000",
        "repay_raw": 250000,
        "seized_htokens_raw": 10100,
        "collateral_underlying_raw": 13000,
    }


class Client:
    def __init__(self, good=True, risky=True):
        self.good = good
        self.risky_flag = risky
        self.amount = None

    def risky(self, borrower):
        return self.risky_flag

    def meaningful_liquidation_check(self, debt, coll, borrower, raw):
        self.amount = raw
        return ({"repay_raw": 250000, "seized_htokens_raw": 10100,
                 "collateral_underlying_raw": 13000} if self.good else None)


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATA_DIR": self.temp.name,
                    "ADMIN_TELEGRAM_ID": "42", "ENABLE_HATOM_WATCH": "true",
                    "HATOM_WATCH_SOURCE": "onchain",
                    "TELEGRAM_GROUP_CHAT_ID": "-100123",
                    "ENABLE_GROUP_ALERTS": "true"})
        self.env.start()
        stages._INITIALIZED = False
        stages._SEEN.clear()
        stages._PENDING.clear()
        stages._NOTIFIED.clear()
        stages._LAST_BATCH = 0.0
        stages._MSG_COUNT = 0

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_risk_only_not_immediate_and_transition_only_once(self):
        now = time.time()
        stages.observe([sample(category="ONCHAIN_RISKY")], now=now)
        self.assertEqual(stages.pending(now=now), [])
        stages.observe([sample()], now=now+2)
        self.assertEqual(len(stages.pending(now=now+2)), 1)
        stages.observe([sample()], now=now+10)
        self.assertEqual(len(stages.pending(now=now+10)), 1)
        stages.observe([sample(category="ONCHAIN_RISKY")], now=now+12)
        self.assertEqual(stages.pending(now=now+12), [])

    def test_last_batch_rate_limit_and_persistent_borrower_dedupe(self):
        now = time.time()
        stages.observe([sample()], now=now)
        self.assertEqual(len(stages.pending(now=now)), 1)
        stages.mark_delivered([sample()], now=now)
        self.assertEqual(stages.pending(now=now+60), [])
        stages.observe([sample(borrower=B)], now=now+61)
        self.assertEqual(stages.pending(now=now+62), [])
        # Reset in-memory; persistent cooldown must survive bot restart.
        stages._INITIALIZED = False
        stages._NOTIFIED.clear()
        stages._LAST_BATCH = 0
        stages._SEEN.clear()
        stages.observe([sample(borrower=A)], now=now+65)
        self.assertNotIn(A, [p["borrower"] for p in stages.pending(now=now+3700)])

    def test_same_borrower_never_realerts_after_12_hours_or_days_or_restart(self):
        now = time.time()
        stages.observe([sample()], now=now)
        self.assertEqual(len(stages.pending(now=now)), 1)
        stages.mark_delivered([sample()], now=now)
        # Earlier 12-hour timeout must no longer allow a second alert.
        for elapsed in (13 * 3600, 2 * 86400, 30 * 86400):
            stages.observe([sample(category="ONCHAIN_RISKY")], now=now + elapsed - 2)
            stages.observe([sample()], now=now + elapsed)
            self.assertEqual(stages.pending(now=now + elapsed), [])

        # Simulate bot restart with the same durable Railway DATA_DIR file.
        stages._INITIALIZED = False
        stages._NOTIFIED.clear()
        stages._SEEN.clear()
        stages._PENDING.clear()
        stages._LAST_BATCH = 0
        stages.observe([sample()], now=now + 30 * 86400)
        self.assertEqual(stages.pending(now=now + 30 * 86400), [])
        self.assertIn(A, stages._NOTIFIED)

    def test_different_borrowers_still_trigger_separate_alerts(self):
        now = time.time()
        stages.observe([sample()], now=now)
        stages.mark_delivered([sample()], now=now)
        stages.observe([sample(borrower=B)], now=now + 181)
        self.assertEqual([r["borrower"] for r in stages.pending(now=now + 181)], [B])

    def test_unreadable_alert_history_fails_closed_not_duplicate(self):
        # A damaged history must not be silently interpreted as empty.
        path = stages._file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf8")
        stages._INITIALIZED = False
        with self.assertRaises(RuntimeError):
            stages.observe([sample()])

    def test_client_checks_risk_and_significant_repayment(self):
        testrow = sample()
        c = Client()
        valid, errors = stages.revalidate([testrow], client=c)
        self.assertEqual(len(valid), 1)
        self.assertEqual(c.amount, 1000000)
        self.assertEqual(errors, 0)
        self.assertEqual(stages.revalidate([testrow], client=Client(good=False))[0], [])
        self.assertEqual(stages.revalidate([testrow], client=Client(risky=False))[0], [])

    def test_private_stage2_single_message(self):
        now = time.time()
        stages.observe([sample(), sample(borrower=B)], now=now)
        bot = SimpleNamespace(send_message=AsyncMock())
        def profitable(borrower):
            from decimal import Decimal
            return {
                "borrower": borrower,
                "category": "INDICATIVE_ONLY",
                "verified_profit": False,
                "executable_dex_quote": False,
                "repay_usd": Decimal("200"),
                "quote_min_usd": Decimal("210"),
                "gross_usd": Decimal("10"),
                "assumed_gas_cost_usd": Decimal("0.2"),
                "quote_net_after_assumed_gas_usd": Decimal("9.8"),
                "safety_buffer_usd": Decimal("2"),
                "screened_surplus_usd": Decimal("7.8"),
                "repay_units": Decimal("200"),
                "repay_symbol": "USDC",
                "collateral_units": Decimal("60"),
                "collateral_symbol": "EGLD",
                "collateral_usd": Decimal("210"),
                "assumed_slippage_bps": 150,
                "assumed_swap_cost_usd": Decimal("3.15"),
                "scenario_net_usd": Decimal("6.65"),
                "quote_min_units": Decimal("210"),
                "dex_quote": {
                    "route_count": 1, "amount_out_min_raw": 210000000,
                    "quote_received_at": time.time(),
                },
            }

        values = {A: profitable(A), B: profitable(B)}
        with patch("core.hatom_liquidations._value_eligible_positions", return_value=values), patch("core.hatom_stages.revalidate", return_value=(
            [dict(sample(), observed_at=now), dict(sample(borrower=B), observed_at=now)], 0
        )):
            self.assertTrue(asyncio.run(watch.eligibility_notifier(SimpleNamespace(bot=bot))))
        self.assertEqual(bot.send_message.await_count, 1)
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 42)
        self.assertNotEqual(bot.send_message.await_args.kwargs["chat_id"], -100123)
        alert = bot.send_message.await_args.kwargs["text"]
        self.assertEqual(alert.count("Borrower:"), 2)
        self.assertIn("POSITIVE-SCENARIO ALERT", alert)
        self.assertIn("Positive indicative margin", alert)
        self.assertIn("NET PROFIT: NOT VERIFIED", alert)
        self.assertEqual(len(stages.pending()), 0)

    def test_unknown_profit_never_notifies_and_can_be_rechecked(self):
        stages.observe([sample()])
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch("core.hatom_liquidations._value_eligible_positions",
                   return_value={A: "DEX quote unavailable"}), patch(
            "core.hatom_stages.revalidate", return_value=([sample()], 0)
        ):
            self.assertFalse(asyncio.run(
                watch.eligibility_notifier(SimpleNamespace(bot=bot))
            ))
        bot.send_message.assert_not_awaited()
        self.assertEqual(len(stages.pending()), 1)
        self.assertNotIn(A, stages._NOTIFIED)

    def test_negative_scenario_silent_and_later_positive_gets_one_alert(self):
        from decimal import Decimal
        stages.observe([sample()])
        bot = SimpleNamespace(send_message=AsyncMock())
        negative = {
            "category": "INDICATIVE_ONLY",
            "verified_profit": False,
            "executable_dex_quote": False,
            "repay_usd": Decimal("10"),
            "gross_usd": Decimal("0.01"),
            "quote_min_usd": Decimal("10.10"),
            "assumed_gas_cost_usd": Decimal("0.20"),
            "quote_net_after_assumed_gas_usd": Decimal("-0.10"),
            "dex_quote": {
                "route_count": 1, "amount_out_min_raw": 10100000,
                "quote_received_at": time.time(),
            },
        }
        positive = dict(
            negative,
            gross_usd=Decimal("2"),
            quote_min_usd=Decimal("11"),
            quote_net_after_assumed_gas_usd=Decimal("0.80"),
            repay_units=Decimal("10"),
            repay_symbol="USDC",
            collateral_units=Decimal("1"),
            collateral_symbol="EGLD",
            collateral_usd=Decimal("11"),
            assumed_swap_cost_usd=Decimal("0.15"),
            assumed_slippage_bps=150,
            scenario_net_usd=Decimal("0.75"),
            quote_min_units=Decimal("11"),
        )
        with patch("core.hatom_liquidations._value_eligible_positions",
                   return_value={A: negative}), patch(
            "core.hatom_stages.revalidate", return_value=([sample()], 0)
        ):
            self.assertFalse(asyncio.run(
                watch.eligibility_notifier(SimpleNamespace(bot=bot))
            ))
        bot.send_message.assert_not_awaited()
        self.assertNotIn(A, stages._NOTIFIED)
        # Same address becomes profitable at a later poll.
        with patch("core.hatom_liquidations._value_eligible_positions",
                   return_value={A: positive}), patch(
            "core.hatom_stages.revalidate", return_value=([sample()], 0)
        ):
            self.assertTrue(asyncio.run(
                watch.eligibility_notifier(SimpleNamespace(bot=bot))
            ))
        bot.send_message.assert_awaited_once()
        self.assertIn("POSITIVE-SCENARIO ALERT",
                      bot.send_message.await_args.kwargs["text"])
        self.assertIn("Indicative surplus AFTER buffer",
                      bot.send_message.await_args.kwargs["text"])
        self.assertEqual(len(stages.pending()), 0)
        # The new positive-only dedupe remains permanent across restarts.
        stages._INITIALIZED = False
        stages._NOTIFIED.clear()
        stages._PENDING.clear()
        stages._SEEN.clear()
        stages._LAST_BATCH = 0
        stages.observe([sample()], now=time.time() + 100000)
        self.assertEqual(stages.pending(now=time.time() + 100000), [])

    def test_under_ten_cents_and_missing_dex_route_never_alert(self):
        from decimal import Decimal
        stages.observe([sample()])
        bot = SimpleNamespace(send_message=AsyncMock())
        base = {
            "category": "INDICATIVE_ONLY", "verified_profit": False,
            "executable_dex_quote": False, "repay_usd": Decimal("10"),
            "quote_min_usd": Decimal("10.799"),
            "assumed_gas_cost_usd": Decimal("0.20"),
            "quote_net_after_assumed_gas_usd": Decimal("0.599"),
            "gross_usd": Decimal("0.80"),
            "dex_quote": {
                "route_count": 1, "amount_out_min_raw": 10799000,
                "quote_received_at": time.time(),
            },
        }
        for report in (base, dict(base, dex_quote=None)):
            with patch("core.hatom_liquidations._value_eligible_positions",
                       return_value={A: report}), patch(
                "core.hatom_stages.revalidate", return_value=([sample()], 0)
            ):
                self.assertFalse(asyncio.run(
                    watch.eligibility_notifier(SimpleNamespace(bot=bot))
                ))
        bot.send_message.assert_not_awaited()
        self.assertNotIn(A, stages._NOTIFIED)

    def test_disabled_monitor_does_not_notify(self):
        stages.observe([sample()])
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.dict(os.environ, {"ENABLE_HATOM_WATCH": "false"}):
            self.assertFalse(asyncio.run(watch.eligibility_notifier(SimpleNamespace(bot=bot))))
        bot.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()

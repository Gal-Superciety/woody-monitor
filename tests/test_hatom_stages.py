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
        with patch("core.hatom_stages.revalidate", return_value=(
            [dict(sample(), observed_at=now), dict(sample(borrower=B), observed_at=now)], 0
        )):
            self.assertTrue(asyncio.run(watch.eligibility_notifier(SimpleNamespace(bot=bot))))
        self.assertEqual(bot.send_message.await_count, 1)
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 42)
        self.assertNotEqual(bot.send_message.await_args.kwargs["chat_id"], -100123)
        alert = bot.send_message.await_args.kwargs["text"]
        self.assertEqual(alert.count("Borrower:"), 2)
        self.assertIn("Not a net-profit quote", alert)
        self.assertIn("Profit net: NOT VERIFIED", alert)
        self.assertEqual(len(stages.pending()), 0)

    def test_disabled_monitor_does_not_notify(self):
        stages.observe([sample()])
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.dict(os.environ, {"ENABLE_HATOM_WATCH": "false"}):
            self.assertFalse(asyncio.run(watch.eligibility_notifier(SimpleNamespace(bot=bot))))
        bot.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()

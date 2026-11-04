"""Offline safety and parsing tests for the private Hatom read-only observer."""
import asyncio
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import hatom_liquidations as watch

ADDRESS = "erd1" + "q" * 58


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class HatomWatchTests(unittest.TestCase):
    def setUp(self):
        watch._LAST_ALERTS.clear()
        watch._STATE.update({"last_poll": None, "last_error": None, "last_candidates": 0, "sent": 0})

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(watch._enabled())
            self.assertFalse(watch._feed_url())

    def test_only_https_feed_is_accepted(self):
        with patch.dict(os.environ, {"HATOM_OPPORTUNITIES_URL": "http://127.0.0.1/test"}):
            self.assertEqual(watch._feed_url(), "")
        with patch.dict(os.environ, {"HATOM_OPPORTUNITIES_URL": "https://feed.example.org/positions"}):
            self.assertEqual(watch._feed_url(), "https://feed.example.org/positions")

    def test_fresh_candidate_and_repay_limit(self):
        now = time.time()
        sample = {
            "updated_at": now,
            "positions": [{
                "borrower": ADDRESS,
                "health_factor": 0.98,
                "borrow_usd": 800,
                "max_repay_usd": 1000,
                "debt_token": "USDC-c76f1f",
                "collateral_token": "EGLD",
            }]
        }
        parsed = watch.normalize_positions(sample, now=now)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["max_repay_usd"], 400)
        self.assertEqual(parsed[0]["category"], "BELOW_1")
        self.assertIn("16.00", watch._message(parsed[0]))

    def test_rejects_stale_and_unhealthy_rows(self):
        now = time.time()
        payload = {"positions": [
            {"borrower": ADDRESS, "health_factor": 0.5, "updated_at": now - 500, "debt_token": "EGLD", "collateral_token": "USDC"},
            {"borrower": ADDRESS, "health_factor": 1.4, "updated_at": now, "debt_token": "EGLD", "collateral_token": "USDC"},
            {"borrower": "invalid", "health_factor": 0.5, "updated_at": now, "debt_token": "EGLD", "collateral_token": "USDC"},
        ]}
        self.assertEqual(watch.normalize_positions(payload, now=now), [])

    def test_only_admin_private_chat_can_request_commands(self):
        env = {"ADMIN_TELEGRAM_ID": "42"}
        def update(chat_id, chat_type, user_id):
            return SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id, type=chat_type),
                                   effective_user=SimpleNamespace(id=user_id))
        with patch.dict(os.environ, env):
            self.assertTrue(watch._admin_private(update(42, "private", 42)))
            self.assertFalse(watch._admin_private(update(-10001, "supergroup", 42)))
            self.assertFalse(watch._admin_private(update(55, "private", 55)))
            self.assertFalse(watch._admin_private(update(55, "private", 42)))

    def test_scan_never_sends_unverified_profit_signals(self):
        sample = {
            "borrower": ADDRESS,
            "health_factor": 0.95,
            "debt_token": "USDC",
            "collateral_token": "EGLD",
            "max_repay_usd": 200,
            "category": "BELOW_1",
        }
        bot = FakeBot()
        context = SimpleNamespace(bot=bot)
        env = {
            "ADMIN_TELEGRAM_ID": "42",
            "TELEGRAM_GROUP_CHAT_ID": "-100987",
            "ENABLE_GROUP_ALERTS": "true",
            "HATOM_OPPORTUNITIES_URL": "https://feed.example.org/positions",
            "ENABLE_HATOM_WATCH": "true",
        }
        with patch.dict(os.environ, env), patch.object(watch, "_download", return_value=[sample]):
            self.assertEqual(asyncio.run(watch.scan(context)), 0)
            self.assertEqual(asyncio.run(watch.scan(context)), 0)
            self.assertEqual(len(bot.messages), 0)
            self.assertEqual(watch._STATE["last_candidates"], 1)
            self.assertEqual(watch._STATE["suppressed_unpriced"], 1)
            self.assertIn("Verified executable profit: NOT AVAILABLE", watch.status_text())


    def test_onchain_risk_signals_are_also_suppressed(self):
        bot = FakeBot()
        context = SimpleNamespace(bot=bot)
        sample = {
            "borrower": ADDRESS,
            "health_factor": None,
            "debt_token": "market-contract",
            "collateral_token": "market-contract",
            "borrow_market": ADDRESS,
            "collateral_market": ADDRESS,
            "raw_borrow": "123456789",
            "category": "ONCHAIN_RISKY",
        }
        env = {"ADMIN_TELEGRAM_ID": "42", "HATOM_WATCH_SOURCE": "onchain",
               "ENABLE_HATOM_WATCH": "true", "ENABLE_GROUP_ALERTS": "true"}
        with patch.dict(os.environ, env), patch("core.hatom_onchain.scan_mainnet", return_value=[sample]):
            self.assertEqual(asyncio.run(watch.scan(context)), 0)
        self.assertEqual(bot.messages, [])
        self.assertEqual(watch._STATE["suppressed_unpriced"], 1)

    def test_disabled_scan_does_not_call_feed_or_send(self):
        bot = FakeBot()
        with patch.dict(os.environ, {"ADMIN_TELEGRAM_ID": "42", "ENABLE_HATOM_WATCH": "false"}, clear=True):
            with patch.object(watch, "_download") as download:
                self.assertEqual(asyncio.run(watch.scan(SimpleNamespace(bot=bot))), 0)
                download.assert_not_called()
        self.assertEqual(bot.messages, [])

if __name__ == "__main__":
    unittest.main()

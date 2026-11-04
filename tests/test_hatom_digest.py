"""Regression tests for scheduled Hatom-only private digests and no alert floods."""
import asyncio
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from core import hatom_digest as dg
from core import hatom_liquidations as watch
from core.hatom_onchain import address_encode

BORROWER = address_encode(bytes([4]) * 32)
DEBT = address_encode(bytes([5]) * 32)
COLLATERAL = address_encode(bytes([6]) * 32)


def risk(debt=DEBT):
    return {
        "borrower": BORROWER,
        "category": "ONCHAIN_RISKY",
        "borrow_market": debt,
        "collateral_market": COLLATERAL,
        "debt_token": "market-contract",
        "collateral_token": "market-contract",
        "health_factor": None,
        "raw_borrow": "100000",
        "max_repay_usd": None,
    }


class MockClient:
    def __init__(self, *, healthy=False, allowed=True, error=False):
        self.healthy = healthy
        self.allowed = allowed
        self.error = error
        self.calls = 0

    def risky(self, borrower):
        self.calls += 1
        if self.error:
            raise ValueError("oracle unavailable")
        return not self.healthy

    def liquidation_allowed(self, debt, collateral, borrower, raw):
        self.calls += 1
        return self.allowed and raw == 1


class DigestTests(unittest.TestCase):
    def setUp(self):
        dg._RISK_CACHE.clear()
        dg._SINCE_START = 0
        dg._TOTAL_CHECKS = 0
        dg._LAST_REPORT = None
        watch._STATE.update({
            "last_poll": None, "last_error": None, "last_candidates": 0,
            "sent": 0, "suppressed_unpriced": 0
        })

    def test_three_berlin_hours_and_reject_excess_frequency(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(dg.digest_hours(), [9, 15, 21])
        with patch.dict(os.environ, {"HATOM_DIGEST_HOURS_BERLIN": "1,2,3,4,5"}):
            self.assertEqual(dg.digest_hours(), [9, 15, 21])

    def test_borrower_is_deduplicated_even_with_multiple_markets(self):
        now = time.time()
        dg.store_scan([risk(), risk(debt=COLLATERAL)], now=now, checked=10)
        snapshot = dg.state_snapshot(now=now)
        self.assertEqual(len(snapshot["candidates"]), 1)
        self.assertEqual(snapshot["candidates"][0]["routes_seen"], 2)
        self.assertEqual(snapshot["checks"], 10)

    def test_cached_wallet_expires(self):
        now = time.time()
        dg.store_scan([risk()], now=now-13*3600)
        self.assertEqual(dg.state_snapshot(now=now)["candidates"], [])
        self.assertEqual(len(dg.state_snapshot(now=now, window_seconds=14*3600)["candidates"]), 1)

    def test_recheck_fails_closed_for_healthy_and_failures(self):
        rows = [dict(risk(), observed_at=time.time())]
        self.assertEqual(dg.recheck(rows, client=MockClient(healthy=True))[0], [])
        self.assertEqual(dg.recheck(rows, client=MockClient(allowed=False))[0], [])
        good, errors = dg.recheck(rows, client=MockClient())
        self.assertEqual(len(good), 1)
        self.assertEqual(errors, 0)
        found, errors = dg.recheck(rows, client=MockClient(error=True))
        self.assertEqual(found, [])
        self.assertEqual(errors, 1)

    def test_report_never_claims_verified_profit(self):
        rows = [dict(risk(), observed_at=time.time())]
        report = dg.build_report(rows, verified=rows, scans=13, checks=130)
        self.assertIn("PRIVATE RISK DIGEST", report)
        self.assertIn("Verified profitable liquidations: NOT AVAILABLE", report)
        self.assertNotIn("Profit: +", report)
        self.assertEqual(report.count("Borrower:"), 1)

    def test_regular_scan_never_sends_telegram(self):
        bot = SimpleNamespace(send_message=AsyncMock())
        env = {
            "ENABLE_HATOM_WATCH": "true", "HATOM_WATCH_SOURCE": "onchain",
            "ADMIN_TELEGRAM_ID": "42", "TELEGRAM_GROUP_CHAT_ID": "-100123",
            "ENABLE_GROUP_ALERTS": "true",
        }
        with patch.dict(os.environ, env), patch("core.hatom_onchain.scan_mainnet", return_value=[risk()]):
            self.assertEqual(asyncio.run(watch.scan(SimpleNamespace(bot=bot))), 0)
            bot.send_message.assert_not_awaited()
        self.assertEqual(len(dg.state_snapshot()["candidates"]), 1)

    def test_scheduled_digest_one_message_admin_only(self):
        dg.store_scan([risk(), risk(debt=COLLATERAL)])
        bot = SimpleNamespace(send_message=AsyncMock())
        env = {"ENABLE_HATOM_WATCH": "true", "HATOM_WATCH_SOURCE": "onchain",
               "ADMIN_TELEGRAM_ID": "42", "TELEGRAM_GROUP_CHAT_ID": "-100123"}
        with patch.dict(os.environ, env), patch("core.hatom_digest.recheck") as confirm:
            confirm.return_value = ([dg.state_snapshot()["candidates"][0]], 0)
            self.assertTrue(asyncio.run(watch.digest(SimpleNamespace(bot=bot))))
        self.assertEqual(bot.send_message.await_count, 1)
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 42)
        self.assertNotEqual(bot.send_message.await_args.kwargs["chat_id"], -100123)

    def test_empty_digest_stays_silent(self):
        bot = SimpleNamespace(send_message=AsyncMock())
        env = {"ENABLE_HATOM_WATCH": "true", "HATOM_WATCH_SOURCE": "onchain",
               "ADMIN_TELEGRAM_ID": "42"}
        with patch.dict(os.environ, env):
            self.assertFalse(asyncio.run(watch.digest(SimpleNamespace(bot=bot))))
        bot.send_message.assert_not_awaited()

    def test_config_schedules_only_three_digests(self):
        app = SimpleNamespace(add_handler=MagicMock(), job_queue=SimpleNamespace(
            run_daily=MagicMock(), run_repeating=MagicMock()
        ))
        env = {"ENABLE_HATOM_WATCH": "true", "HATOM_WATCH_SOURCE": "onchain",
               "ADMIN_TELEGRAM_ID": "42", "HATOM_WATCH_INTERVAL_SECONDS": "90"}
        with patch.dict(os.environ, env):
            watch.register(app)
        self.assertEqual(app.job_queue.run_repeating.call_count, 1)
        self.assertEqual(app.job_queue.run_daily.call_count, 3)
        local_hours = [call.kwargs["time"].hour for call in app.job_queue.run_daily.call_args_list]
        self.assertEqual(local_hours, [9, 15, 21])
        self.assertEqual(str(app.job_queue.run_daily.call_args_list[0].kwargs["time"].tzinfo), "Europe/Berlin")


if __name__ == "__main__":
    unittest.main()

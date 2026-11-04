"""Tests: recheck old Hatom Telegram alerts even after memory reset."""
import asyncio
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core import hatom_digest as digest
from core import hatom_liquidations as watch
from core.hatom_onchain import address_encode, inspect_borrower_live

WALLET = address_encode(bytes([1]) * 32)
DEBT = address_encode(bytes([2]) * 32)
COLLATERAL = address_encode(bytes([3]) * 32)


def eligible():
    return {
        "borrower": WALLET, "borrow_market": DEBT,
        "collateral_market": COLLATERAL, "raw_borrow": "100000",
        "category": "ONCHAIN_ELIGIBLE", "repay_raw": 25000,
        "seized_htokens_raw": 100, "collateral_underlying_raw": 150,
        "observed_at": time.time(),
    }


class BorrowerClient:
    def risky(self, borrower):
        return borrower == WALLET

    def account_markets(self, borrower):
        return [DEBT, COLLATERAL]

    def borrow_amount(self, market, borrower):
        return 100000 if market == DEBT else 0

    def collateral_tokens(self, market, borrower):
        return 2000 if market == COLLATERAL else 0

    def meaningful_liquidation_check(self, debt, collateral, borrower, amount):
        if collateral != COLLATERAL:
            return None
        return {"repay_raw": 25000, "seized_htokens_raw": 100,
                "collateral_underlying_raw": 150}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "DATA_DIR": self.temp.name,
            "ENABLE_HATOM_WATCH": "true",
            "HATOM_WATCH_SOURCE": "onchain",
            "ADMIN_TELEGRAM_ID": "42",
            "TELEGRAM_GROUP_CHAT_ID": "-100123",
        })
        self.env.start()
        digest._RISK_CACHE.clear()
        digest._LOADED_DATA_DIR = None

    def tearDown(self):
        self.env.stop()
        digest._RISK_CACHE.clear()
        digest._LOADED_DATA_DIR = None
        self.temp.cleanup()

    def test_disk_candidate_survives_simulated_process_restart(self):
        digest.store_scan([eligible()], checked=10)
        self.assertEqual(len(digest.state_snapshot()["candidates"]), 1)
        self.assertTrue(
            os.path.isfile(os.path.join(self.temp.name, "hatom_candidates.json"))
        )
        digest._RISK_CACHE.clear()
        digest._LOADED_DATA_DIR = None
        restored = digest.state_snapshot()["candidates"]
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["borrower"], WALLET)
        self.assertEqual(restored[0]["category"], "ONCHAIN_ELIGIBLE")

    def test_expired_disk_candidate_not_restored(self):
        old = eligible()
        old["observed_at"] = time.time() - 14 * 3600
        # This store uses scan time as observation time, simulate a restart
        # after 13 hours by explicitly writing a stale timestamp.
        import json
        path = os.path.join(self.temp.name, "hatom_candidates.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"candidates": [old]}, stream)
        restored = digest.state_snapshot()["candidates"]
        self.assertEqual(restored, [])

    def test_live_borrower_recheck_uses_current_borrows_and_collateral(self):
        rows = inspect_borrower_live(WALLET, client=BorrowerClient())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "ONCHAIN_ELIGIBLE")
        self.assertEqual(rows[0]["raw_borrow"], "100000")
        self.assertEqual(rows[0]["collateral_underlying_raw"], 150)

    def _update(self, *, reply=None, chat_id=42):
        message = SimpleNamespace(
            text="/hatom_profit",
            reply_to_message=SimpleNamespace(text=reply) if reply else None,
            reply_text=AsyncMock(),
        )
        return SimpleNamespace(
            effective_chat=SimpleNamespace(id=chat_id, type="private" if chat_id == 42 else "supergroup"),
            effective_user=SimpleNamespace(id=42),
            message=message,
        )

    def test_parse_reply_digest_and_old_stage2_message(self):
        for text in (
            f"1. {WALLET}\n   Debt market: {DEBT}",
            f"1. Borrower: {WALLET}\n   Debt market: {DEBT}\n   Collateral market: {COLLATERAL}",
        ):
            self.assertEqual(
                watch._profit_requested_borrowers(
                    self._update(reply=text), SimpleNamespace(args=[])
                ), [WALLET],
            )
        self.assertEqual(watch._profit_requested_borrowers(
            self._update(), SimpleNamespace(args=[WALLET])
        ), [WALLET])

    def test_admin_can_recheck_old_alert_when_memory_empty(self):
        update = self._update(
            reply=f"1. Borrower: {WALLET}\nDebt market: {DEBT}\nCollateral market: {COLLATERAL}"
        )
        with patch.object(watch, "_recheck_borrowers_on_demand", return_value=[eligible()]) as live, \
             patch.object(watch, "_value_eligible_positions", return_value={}), \
             patch.object(digest, "store_scan"):
            asyncio.run(watch.profit_command(update, SimpleNamespace(args=[])))
        self.assertEqual(live.call_args.args[0], [WALLET])
        self.assertEqual(update.message.reply_text.await_count, 1)
        self.assertIn("PRIVATE PROTOCOL-LIQUIDATION", update.message.reply_text.await_args.args[0])

    def test_unauthorized_group_cannot_query_wallets(self):
        update = self._update(reply=f"1. Borrower: {WALLET}", chat_id=-100123)
        with patch.object(watch, "_recheck_borrowers_on_demand") as live:
            asyncio.run(watch.profit_command(update, SimpleNamespace(args=[])))
        live.assert_not_called()
        update.message.reply_text.assert_not_awaited()

    def test_no_cache_message_explains_reply_or_borrower(self):
        update = self._update()
        asyncio.run(watch.profit_command(update, SimpleNamespace(args=[])))
        answer = update.message.reply_text.await_args.args[0]
        self.assertIn("reply to its Hatom alert", answer)
        self.assertIn("/hatom_profit erd1", answer)


if __name__ == "__main__":
    unittest.main()

"""XOXNO lending MultiversX read-only API / on-chain eligibility regression tests."""
import asyncio
import json
import os
import tempfile
import time
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import xoxno_lending_watch as x
from core.hatom_onchain import address_encode

WALLET = address_encode(bytes([7]) * 32)


def entry(*, identifier="XLEND-18dc6f-eb", borrowed=10):
    return {
        "identifier": identifier,
        "position": 3,
        "borrowed": borrowed,
        "supplied": 30,
        "healthFactor": 0.8,
        "wallet": {"address": WALLET, "username": "borrower"},
    }


class FakeVm:
    def __init__(self, return_data=None):
        self.return_data = [b"\x01"] if return_data is None else return_data
        self.calls = []

    def query(self, contract, func, args=None):
        self.calls.append((contract, func, args))
        return self.return_data


class XoxnoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "DATA_DIR": self.tmp.name, "ENABLE_XOXNO_LENDING_WATCH": "true",
            "ADMIN_TELEGRAM_ID": "42", "XOXNO_LENDING_SCAN_INTERVAL_SECONDS": "240",
        })
        self.env.start()
        x._NOTIFIED.clear()
        x._LOADED_PATH = None
        x._LAST_BATCH = 0
        x._STATS.update({
            "last_poll": None, "last_error": None,
            "api_candidates": 0, "confirmed": 0, "scans": 0, "alerts": 0,
        })

    def tearDown(self):
        self.env.stop()
        x._NOTIFIED.clear()
        x._LOADED_PATH = None
        self.tmp.cleanup()

    def test_known_mainnet_config_and_nonce_decoding(self):
        self.assertEqual(x.nonce_of("XLEND-18dc6f-eb"), 235)
        self.assertEqual(x.nonce_of("XLEND-18dc6f-0641"), 1601)
        self.assertEqual(x.parse_candidate(entry())["borrowed_usd_api"], Decimal("10"))
        self.assertEqual(x.parse_candidate(entry())["borrower"], WALLET)
        with self.assertRaises(ValueError):
            x.nonce_of("XLEND-other-1")

    def test_rejects_false_profit_and_invalid_schema(self):
        for invalid in (
            entry(borrowed=0),
            entry(borrowed=-1),
            entry(borrowed="NaN"),
            entry(identifier="XLEND-hacker-01"),
            {"identifier": "XLEND-18dc6f-eb", "borrowed": 10},
        ):
            with self.assertRaises(ValueError):
                x.parse_candidate(invalid)

    def test_http_public_liquidation_list_and_unique_nft_ids(self):
        session = Mock()
        response = Mock()
        response.content = b'[]'
        response.json.return_value = [entry(), entry(), entry(identifier="XLEND-18dc6f-01")]
        session.get.return_value = response
        found = x.discover(session=session)
        self.assertEqual(len(found), 2)
        kwargs = session.get.call_args.kwargs
        self.assertEqual(session.get.call_args.args[0], x.LIST_URL)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], 8)

    def test_empty_api_does_not_find_fake_liquidations(self):
        session = Mock()
        response = Mock()
        response.content = b'[]'
        response.json.return_value = []
        session.get.return_value = response
        self.assertEqual(x.discover(session=session), [])

    def test_live_controller_true_only_then_false_and_errors(self):
        row = x.parse_candidate(entry())
        vm = FakeVm()
        confirmed = x.confirm_onchain([row], vm=vm)
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(vm.calls[0][0], x.CONTROLLER)
        self.assertEqual(vm.calls[0][1], "canBeLiquidated")
        self.assertEqual(vm.calls[0][2], [bytes.fromhex("eb")])
        self.assertEqual(x.confirm_onchain([row], vm=FakeVm([b"\x00"])), [])
        self.assertEqual(x.confirm_onchain([row], vm=FakeVm([b""])), [])
        self.assertEqual(x.confirm_onchain([row], vm=FakeVm([])), [])

    def test_only_private_admin_can_get_commands(self):
        m = SimpleNamespace(reply_text=AsyncMock())
        unauthorized = SimpleNamespace(
            effective_chat=SimpleNamespace(type="supergroup", id=-100123),
            effective_user=SimpleNamespace(id=42),
            message=m,
        )
        with patch.object(x, "inspect") as source:
            asyncio.run(x.scan_command(unauthorized, SimpleNamespace(bot=Mock())))
        source.assert_not_called()
        m.reply_text.assert_not_awaited()

    def test_manual_scan_never_calls_bot_broadcast(self):
        admin = SimpleNamespace(
            effective_chat=SimpleNamespace(type="private", id=42),
            effective_user=SimpleNamespace(id=42),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.object(x, "inspect", return_value=([x.parse_candidate(entry())], 1)):
            asyncio.run(x.scan_command(admin, SimpleNamespace(bot=bot)))
        self.assertIn("NOT A PROFIT ALERT", admin.message.reply_text.await_args.args[0])
        bot.send_message.assert_not_awaited()

    def test_auto_alert_admin_only_cooldown_and_no_profit_claim(self):
        rows = [x.parse_candidate(entry())]
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.object(x, "inspect", return_value=(rows, 1)):
            asyncio.run(x.scan(SimpleNamespace(bot=bot)))
            asyncio.run(x.scan(SimpleNamespace(bot=bot)))
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 42)
        alert = bot.send_message.await_args.kwargs["text"]
        self.assertIn("NOT A PROFIT ALERT", alert)
        self.assertIn("NOT VERIFIED", alert)
        self.assertIn("No funds used", alert)
        self.assertNotIn("profit: +", alert.lower())

    def test_cooldown_survives_restart(self):
        row = x.parse_candidate(entry())
        x.mark_sent([row])
        self.assertEqual(x.eligible_to_send([row]), [])
        x._LOADED_PATH = None
        x._NOTIFIED.clear()
        x._LAST_BATCH = 0
        self.assertEqual(x.eligible_to_send([row]), [])
        self.assertTrue(os.path.exists(x.state_file()))

    def test_register_is_scheduled_only_when_enabled(self):
        app = SimpleNamespace(
            add_handler=Mock(),
            job_queue=SimpleNamespace(run_repeating=Mock()),
        )
        x.register(app)
        self.assertEqual(app.add_handler.call_count, 2)
        self.assertEqual(app.job_queue.run_repeating.call_count, 1)
        self.assertEqual(app.job_queue.run_repeating.call_args.kwargs["interval"], 240)
        with patch.dict(os.environ, {"ENABLE_XOXNO_LENDING_WATCH": "false"}):
            app.job_queue.run_repeating.reset_mock()
            x.register(app)
        app.job_queue.run_repeating.assert_not_called()


if __name__ == "__main__":
    unittest.main()

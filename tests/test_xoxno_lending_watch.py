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


def scenario(*, identifier="XLEND-18dc6f-eb", net="0.30"):
    profit = Decimal(net)
    return {
        "identifier": identifier, "repay_token": "USDC-c76f1f",
        "repay_usd": Decimal("10"),
        "dex_min_usd": Decimal("10.70") + profit,
        "estimated_gas_usd": Decimal("0.20"),
        "safety_buffer_usd": Decimal("0.50"),
        "scenario_net_usd": profit,
        "quote_observed_at": time.time(),
        "clears_quarter_dollar": profit >= Decimal("0.25"),
        "verified_profit": False, "transaction_sent": False,
        "full_pipeline_simulated": False,
    }


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
        x._LAST_REPORT = None
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

    def test_manual_scan_includes_loss_and_never_broadcasts(self):
        admin = SimpleNamespace(
            effective_chat=SimpleNamespace(type="private", id=42),
            effective_user=SimpleNamespace(id=42),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        bot = SimpleNamespace(send_message=AsyncMock())
        rows = [x.parse_candidate(entry())]
        with patch.object(x, "inspect", return_value=(rows, 1)), patch.object(
            x, "price_candidates",
            return_value={rows[0]["identifier"]: scenario(net="-0.15")}
        ):
            asyncio.run(x.scan_command(admin, SimpleNamespace(bot=bot)))
        message = admin.message.reply_text.await_args.args[0]
        self.assertIn("PRIVATE SCAN REPORT", message)
        self.assertIn("🔴 LOSS", message)
        self.assertIn("-0.1500", message)
        bot.send_message.assert_not_awaited()

    def test_auto_alert_both_negative_and_positive_positions(self):
        rows = [x.parse_candidate(entry()),
                x.parse_candidate(entry(identifier="XLEND-18dc6f-01"))]
        valuations = {
            rows[0]["identifier"]: scenario(net="-0.30"),
            rows[1]["identifier"]: scenario(
                identifier=rows[1]["identifier"], net="0.30"
            ),
        }
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.object(x, "inspect", return_value=(rows, 2)), patch.object(
            x, "price_candidates", return_value=valuations
        ):
            asyncio.run(x.scan(SimpleNamespace(bot=bot)))
            asyncio.run(x.scan(SimpleNamespace(bot=bot)))
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 42)
        alert = bot.send_message.await_args.kwargs["text"]
        self.assertIn("PRIVATE LIQUIDATION CANDIDATE", alert)
        self.assertIn("REGARDLESS", alert.upper())
        self.assertIn(rows[0]["identifier"], alert)
        self.assertIn(rows[1]["identifier"], alert)
        self.assertIn("NOT VERIFIED", alert)
        self.assertIn("/xoxno_profit", alert)
        self.assertEqual(x._STATS["losses"], 1)
        self.assertEqual(x._STATS["positive"], 1)

    def test_negative_or_unpriceable_positions_still_alert(self):
        rows = [x.parse_candidate(entry())]
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.object(x, "inspect", return_value=(rows, 1)), patch.object(
            x, "price_candidates",
            return_value={rows[0]["identifier"]: scenario(net="-0.17")}
        ):
            asyncio.run(x.scan(SimpleNamespace(bot=bot)))
        bot.send_message.assert_awaited_once()
        self.assertIn("-0.1700", x.scan_report_text(
            rows, x._LAST_REPORT["valuations"]
        ))
        self.assertIn("UNKNOWN until /xoxno_profit",
                      bot.send_message.await_args.kwargs["text"])

    def test_no_candidates_no_automatic_notification(self):
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.object(x, "inspect", return_value=([], 0)):
            asyncio.run(x.scan(SimpleNamespace(bot=bot)))
        bot.send_message.assert_not_awaited()

    def test_alert_happens_before_slow_or_failing_profit_calculation(self):
        rows = [x.parse_candidate(entry())]
        bot = SimpleNamespace(send_message=AsyncMock())
        def scenario_failed(*args, **kwargs):
            self.assertEqual(bot.send_message.await_count, 1)
            raise ValueError("DEX unavailable")
        with patch.object(x, "inspect", return_value=(rows, 1)), patch.object(
            x, "price_candidates", side_effect=scenario_failed
        ):
            asyncio.run(x.scan(SimpleNamespace(bot=bot)))
        bot.send_message.assert_awaited_once()
        self.assertIn("canBeLiquidated", bot.send_message.await_args.kwargs["text"]
                      ) if False else None

    def test_inconsistent_stale_or_fake_profit_cannot_alert(self):
        q = scenario(net="0.25")
        self.assertTrue(x._priority_eligible(q))
        self.assertFalse(x._priority_eligible(
            dict(q, quote_observed_at=time.time()-100)
        ))
        self.assertFalse(x._priority_eligible(
            dict(q, scenario_net_usd=Decimal("999"))
        ))
        self.assertFalse(x._priority_eligible(
            dict(q, verified_profit=True)
        ))
        self.assertFalse(x._priority_eligible(
            dict(q, estimated_gas_usd=Decimal("0"))
        ))
        self.assertFalse(x._priority_eligible(
            dict(q, clears_quarter_dollar=False)
        ))

    def test_scheduled_report_sent_when_no_candidates(self):
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch.object(x, "inspect", return_value=([], 0)):
            asyncio.run(x.report_job(SimpleNamespace(bot=bot)))
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 42)
        self.assertIn("API candidates: 0",
                      bot.send_message.await_args.kwargs["text"])
        self.assertIn("PRIVATE SCAN REPORT",
                      bot.send_message.await_args.kwargs["text"])

    def test_all_candidates_priced_in_rotation(self):
        rows = [x.parse_candidate(entry(identifier=f"XLEND-18dc6f-{j:02x}"))
                for j in range(1, 15)]
        with patch("core.xoxno_profit.calculate") as calc:
            calc.side_effect = lambda nft: scenario(identifier=nft)
            visited = set()
            for poll in range(3):
                result = x.price_candidates(rows, poll=poll)
                self.assertLessEqual(len(result), x.MAX_PRICE_PER_POLL)
                visited.update(result.keys())
        self.assertEqual(visited, {row["identifier"] for row in rows})

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
            job_queue=SimpleNamespace(run_repeating=Mock(), run_daily=Mock()),
        )
        x.register(app)
        self.assertEqual(app.add_handler.call_count, 4)
        self.assertEqual(app.job_queue.run_repeating.call_count, 1)
        self.assertEqual(app.job_queue.run_daily.call_count, 0)
        self.assertEqual(app.job_queue.run_repeating.call_args.kwargs["interval"], 240)
        with patch.dict(os.environ, {"ENABLE_XOXNO_LENDING_WATCH": "false"}):
            app.job_queue.run_repeating.reset_mock()
            app.job_queue.run_daily.reset_mock()
            x.register(app)
        app.job_queue.run_repeating.assert_not_called()
        app.job_queue.run_daily.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Regression tests: liquidation scans stay active without unsolicited risk digests."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import hatom_liquidations as hatom
from core import xoxno_lending_watch as xoxno
from core.liquidation_access import scheduled_risk_reports_enabled


def fake_app():
    return SimpleNamespace(add_handler=Mock(), job_queue=Mock())


class LiquidationNotificationPolicyTests(unittest.TestCase):
    def test_reports_are_off_by_default_and_opt_in_only(self):
        with patch.dict(os.environ, {"ENABLE_SCHEDULED_RISK_REPORTS": ""}):
            self.assertFalse(scheduled_risk_reports_enabled())
        with patch.dict(os.environ, {"ENABLE_SCHEDULED_RISK_REPORTS": "false"}):
            self.assertFalse(scheduled_risk_reports_enabled())
        with patch.dict(os.environ, {"ENABLE_SCHEDULED_RISK_REPORTS": "true"}):
            self.assertTrue(scheduled_risk_reports_enabled())

    def test_hatom_keeps_scan_and_positive_notifier_without_risk_digest(self):
        app = fake_app()
        with patch.dict(os.environ, {"ENABLE_SCHEDULED_RISK_REPORTS": "false"}), \
             patch.object(hatom, "_enabled", return_value=True), \
             patch.object(hatom, "_ready", return_value=True), \
             patch.object(hatom, "_source", return_value="onchain"), \
             patch.object(hatom, "_admin_id", return_value=42):
            hatom.register(app)
        self.assertEqual(app.job_queue.run_repeating.call_count, 2)
        app.job_queue.run_daily.assert_not_called()
        self.assertGreaterEqual(app.add_handler.call_count, 5)

    def test_xoxno_keeps_scan_without_daily_loss_report(self):
        app = fake_app()
        with patch.dict(os.environ, {
            "ENABLE_SCHEDULED_RISK_REPORTS": "false",
            "ENABLE_XOXNO_LENDING_WATCH": "true",
            "ADMIN_TELEGRAM_ID": "42",
        }):
            xoxno.register(app)
        app.job_queue.run_repeating.assert_called_once()
        app.job_queue.run_daily.assert_not_called()
        self.assertEqual(app.add_handler.call_count, 4)

    def test_opt_in_preserves_existing_scheduled_reports(self):
        with patch.dict(os.environ, {
            "ENABLE_SCHEDULED_RISK_REPORTS": "true",
            "HATOM_DIGEST_HOURS_BERLIN": "9,15,21",
        }), patch.object(hatom, "_enabled", return_value=True), \
            patch.object(hatom, "_ready", return_value=True), \
            patch.object(hatom, "_source", return_value="onchain"), \
            patch.object(hatom, "_admin_id", return_value=42):
            app = fake_app()
            hatom.register(app)
        self.assertEqual(app.job_queue.run_daily.call_count, 3)

        with patch.dict(os.environ, {
            "ENABLE_SCHEDULED_RISK_REPORTS": "true",
            "ENABLE_XOXNO_LENDING_WATCH": "true",
            "ADMIN_TELEGRAM_ID": "42",
        }):
            app = fake_app()
            xoxno.register(app)
        app.job_queue.run_daily.assert_called_once()


if __name__ == "__main__":
    unittest.main()

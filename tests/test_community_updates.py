"""Focused offline tests for opt-in community messages."""
import os
import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

from core.community_updates import build_brief, enabled, is_target, welcome_text


class FakeChat:
    id = -100123
    type = "supergroup"


class CommunityTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(enabled("ENABLE_COMMUNITY_WELCOME"))
            self.assertFalse(enabled("ENABLE_MORNING_BRIEF"))

    def test_chat_restriction(self):
        with patch.dict(os.environ, {"TELEGRAM_GROUP_CHAT_ID": "-100123"}):
            self.assertTrue(is_target(FakeChat()))
            FakeChat.type = "private"
            try:
                self.assertFalse(is_target(FakeChat()))
            finally:
                FakeChat.type = "supergroup"

    def test_escape_new_member(self):
        text = welcome_text("<script>John</script>")
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("<script>", text)
        self.assertIn("WOODY-5f9d9c", text)

    def test_missing_market_data(self):
        text = build_brief(0, 0, None, None)
        self.assertIn("Unavailable", text)
        self.assertNotIn("nan", text.lower())

    def test_valid_market_data(self):
        text = build_brief(4.04, 0.00003669, 342, 1157.0)
        self.assertIn("342", text)
        self.assertIn("1,157.00", text)
        self.assertIn("4.0400", text)

    def test_dst_berlin(self):
        berlin = ZoneInfo("Europe/Berlin")
        self.assertNotEqual(
            datetime(2026, 1, 15, tzinfo=berlin).utcoffset(),
            datetime(2026, 7, 15, tzinfo=berlin).utcoffset(),
        )


if __name__ == "__main__":
    unittest.main()

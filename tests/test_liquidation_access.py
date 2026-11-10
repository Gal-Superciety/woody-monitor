"""Second user's owner-invited read-only Hatom/XOXNO Telegram access."""
import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import liquidation_access as acl
from core import hatom_liquidations as hatom
from core import xoxno_lending_watch as xoxno


def user(chat_id: int = 42, *, uid: int | None = None,
         username: str = "CosminRussu", chat_type: str = "private"):
    uid = chat_id if uid is None else uid
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=uid, username=username),
        effective_chat=SimpleNamespace(id=chat_id, type=chat_type),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )


class SubscriberTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "DATA_DIR": self.temp.name,
            "ADMIN_TELEGRAM_ID": "42",
            "ENABLE_HATOM_WATCH": "true",
            "HATOM_WATCH_SOURCE": "onchain",
            "ENABLE_XOXNO_LENDING_WATCH": "true",
        })
        self.env.start()
        acl._PATH = None
        acl._SUBSCRIBERS.clear()
        acl._INVITES.clear()

    def tearDown(self):
        self.env.stop()
        acl._PATH = None
        acl._SUBSCRIBERS.clear()
        acl._INVITES.clear()
        self.temp.cleanup()

    def test_initially_only_owner_and_no_username_authorization(self):
        self.assertEqual(acl.recipient_ids(), [42])
        self.assertTrue(acl.is_authorized_private(user(42, username="owner")))
        self.assertFalse(acl.is_authorized_private(user(101, username="CosminRussu")))
        self.assertFalse(acl.is_authorized_private(user(-100123, uid=42, chat_type="supergroup")))
        self.assertFalse(acl.is_authorized_private(user(101, uid=42)))
        self.assertFalse(acl.is_owner_private(user(101, username="owner")))

    def test_owner_only_can_make_private_invitation(self):
        bot = SimpleNamespace(send_message=AsyncMock())
        guest = user(101)
        asyncio.run(acl.invite_command(guest, SimpleNamespace(bot=bot)))
        guest.message.reply_text.assert_not_awaited()
        group = user(-100, uid=42, chat_type="supergroup")
        asyncio.run(acl.invite_command(group, SimpleNamespace(bot=bot)))
        group.message.reply_text.assert_not_awaited()
        owner = user(42, username="owner")
        asyncio.run(acl.invite_command(owner, SimpleNamespace(bot=bot)))
        text = owner.message.reply_text.await_args.args[0]
        self.assertIn("/liquidation_join ", text)
        self.assertIn("24h", text)
        self.assertEqual(len(acl._INVITES), 1)

    def test_join_is_one_time_and_uses_real_telegram_id(self):
        token = acl.create_invite()
        self.assertNotIn(token, acl.state_file().read_text())
        guest = user(101)
        ctx = SimpleNamespace(args=[token], bot=SimpleNamespace(send_message=AsyncMock()))
        asyncio.run(acl.join_command(guest, ctx))
        self.assertTrue(acl.is_authorized_private(guest))
        self.assertEqual(acl.recipient_ids(), [42, 101])
        self.assertIn("activated", guest.message.reply_text.await_args.args[0])
        self.assertEqual(len(acl._INVITES), 0)
        ctx.bot.send_message.assert_awaited_once()
        self.assertEqual(ctx.bot.send_message.await_args.kwargs["chat_id"], 42)
        # Token cannot be reused by another participant.
        stolen = user(202, username="stealer")
        asyncio.run(acl.join_command(stolen, ctx))
        self.assertFalse(acl.is_authorized_private(stolen))
        self.assertEqual(acl.recipient_ids(), [42, 101])
        # Only the immutable ID matters after joining; handle can change.
        self.assertTrue(acl.is_authorized_private(
            user(101, username="RenamedUser")
        ))
        # Reading persisted history with no in-memory state.
        acl._PATH = None
        acl._SUBSCRIBERS.clear()
        acl._INVITES.clear()
        self.assertEqual(acl.recipient_ids(), [42, 101])

    def test_expired_invite_rejected(self):
        with patch.object(acl.time, "time", return_value=1_000_000):
            token = acl.create_invite()
        with patch.object(acl.time, "time", return_value=1_000_000 + 24 * 3600 + 1):
            self.assertFalse(acl.join(token, 101))
        self.assertEqual(acl.recipient_ids(), [42])

    def test_alert_broadcast_to_owner_and_guest_private_only(self):
        token = acl.create_invite()
        self.assertTrue(acl.join(token, 101))
        bot = SimpleNamespace(send_message=AsyncMock())
        count = asyncio.run(acl.send_liquidation_alert(bot, "Stage-2 confirmed"))
        self.assertEqual(count, 2)
        self.assertEqual([c.kwargs["chat_id"] for c in bot.send_message.await_args_list], [42, 101])
        self.assertTrue(all(c.kwargs["text"] == "Stage-2 confirmed"
                            for c in bot.send_message.await_args_list))

    def test_blocked_guest_does_not_block_owner(self):
        token = acl.create_invite()
        self.assertTrue(acl.join(token, 101))
        async def send(*, chat_id, text):
            if chat_id == 101:
                raise ValueError("Bot blocked")
            return None
        bot = SimpleNamespace(send_message=AsyncMock(side_effect=send))
        self.assertEqual(asyncio.run(acl.send_liquidation_alert(bot, "alert")), 1)
        self.assertEqual(bot.send_message.await_count, 2)

    def test_revoke_owner_only_and_stop_notifications(self):
        self.assertTrue(acl.join(acl.create_invite(), 101))
        guest = user(101)
        # No admin controls for a subscriber.
        asyncio.run(acl.revoke_command(
            guest, SimpleNamespace(args=["42"])
        ))
        guest.message.reply_text.assert_not_awaited()
        self.assertTrue(acl.is_authorized_private(guest))
        owner = user(42, username="owner")
        asyncio.run(acl.revoke_command(
            owner, SimpleNamespace(args=["101"])
        ))
        self.assertFalse(acl.is_authorized_private(guest))
        self.assertEqual(acl.recipient_ids(), [42])
        self.assertIn("revoked", owner.message.reply_text.await_args.args[0])

    def test_corrupt_subscription_file_does_not_authorize_strangers(self):
        acl.state_file().write_text("{broken", encoding="utf8")
        acl._PATH = None
        self.assertEqual(acl.recipient_ids(), [42])
        self.assertFalse(acl.is_authorized_private(user(101)))
        self.assertTrue(acl.is_authorized_private(user(42)))

    def test_subscriber_can_run_private_read_only_commands_only(self):
        self.assertTrue(acl.join(acl.create_invite(), 101))
        guest = user(101)
        self.assertTrue(hatom._admin_private(guest))
        self.assertTrue(xoxno.admin_private(guest))
        self.assertFalse(acl.is_owner_private(guest))
        report = AsyncMock()
        with patch.object(hatom, "digest", report):
            asyncio.run(hatom.report_command(guest, SimpleNamespace(bot=Mock())))
        report.assert_awaited_once()
        self.assertEqual(report.await_args.kwargs["target_chat_id"], 101)
        asyncio.run(xoxno.status_command(guest, SimpleNamespace(bot=Mock())))
        self.assertIn("XOXNO Lending Watch", guest.message.reply_text.await_args.args[0])
        # The Hatom test and transaction preflight commands are owner-only.
        guest.message.reply_text.reset_mock()
        asyncio.run(hatom.test_command(
            guest, SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
        ))
        guest.message.reply_text.assert_not_awaited()
        with patch("core.hatom_dryrun", create=True) as probe:
            asyncio.run(hatom.dryrun_command(guest, SimpleNamespace(bot=Mock())))
        guest.message.reply_text.assert_not_awaited()
        self.assertIsNotNone(probe)

    def test_registers_five_onboarding_commands(self):
        app = SimpleNamespace(add_handler=Mock())
        acl.register(app)
        self.assertEqual(app.add_handler.call_count, 5)


if __name__ == "__main__":
    unittest.main()

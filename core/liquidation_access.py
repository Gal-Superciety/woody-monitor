"""Owner-approved, private Telegram access to READ-ONLY liquidation alerts.

Admin can issue a strong, one-use invitation in their *private* bot chat.
A user must privately /start then /liquidation_join TOKEN; Telegram user ID
becomes the immutable authorization key. Never authorize by display name,
mutable @username or a public MultiversX wallet address.

The invitation and subscription state is persisted on Railway DATA_DIR.
No ownership/admin, secrets, trading or wallet privileges are delegated.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)
_LOCK = threading.RLock()
_PATH: str | None = None
_SUBSCRIBERS: dict[str, dict[str, Any]] = {}
_INVITES: dict[str, float] = {}
_INVITE_TTL = 24 * 3600
_MAX_SUBSCRIBERS = 5
_MAX_INVITES = 5
_USER_ID = re.compile(r"^[1-9][0-9]{0,18}$")


def owner_id() -> int | None:
    raw = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    return int(raw) if _USER_ID.fullmatch(raw) else None


def state_file() -> Path:
    return Path(os.getenv("DATA_DIR", "data")) / "liquidation_subscribers.json"


def _load() -> None:
    """Read when DATA_DIR changes, important for tests and Railway upgrades.

    Fail closed for malformed files instead of accidentally losing authorized
    recipients or approving strangers. Owner retains their built-in access.
    """
    global _PATH
    with _LOCK:
        path = state_file()
        if _PATH == str(path):
            return
        raw: dict[str, Any] = {"subscribers": {}, "invites": {}}
        try:
            if path.stat().st_size > 1_000_000:
                raise ValueError("Subscription state is too large")
            raw = json.loads(path.read_text(encoding="utf8"))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as exc:
            logger.error("Liquidation subscriber history unreadable (%s)",
                         type(exc).__name__)
            raise RuntimeError("Subscription state unavailable") from exc
        if not isinstance(raw, dict):
            raise RuntimeError("Subscription state format invalid")
        subscribers = raw.get("subscribers")
        invites = raw.get("invites")
        if not isinstance(subscribers, dict) or not isinstance(invites, dict):
            raise RuntimeError("Subscription state fields invalid")
        new_subscribers: dict[str, dict[str, Any]] = {}
        for key, value in subscribers.items():
            if not (_USER_ID.fullmatch(str(key)) and isinstance(value, dict)):
                raise RuntimeError("Subscription state contains invalid users")
            new_subscribers[str(key)] = {
                "username": str(value.get("username") or "")[:64],
                "added_at": float(value.get("added_at") or 0),
            }
        new_invites: dict[str, float] = {}
        for digest, expires in invites.items():
            if (not isinstance(digest, str) or len(digest) != 64
                    or not all(c in "0123456789abcdef" for c in digest)
                    or type(expires) not in (int, float)):
                raise RuntimeError("Subscription invite state invalid")
            new_invites[digest] = float(expires)
        if len(new_subscribers) > _MAX_SUBSCRIBERS or len(new_invites) > _MAX_INVITES:
            raise RuntimeError("Subscription state exceeds safety limits")
        _SUBSCRIBERS.clear()
        _SUBSCRIBERS.update(new_subscribers)
        _INVITES.clear()
        _INVITES.update(new_invites)
        _PATH = str(path)


def _persist() -> None:
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf8") as stream:
            os.chmod(tmp, 0o600)
            json.dump({"subscribers": _SUBSCRIBERS, "invites": _INVITES},
                      stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def is_owner_private(update: Update) -> bool:
    owner = owner_id()
    user, chat = update.effective_user, update.effective_chat
    return bool(owner and user and chat and chat.type == "private"
                and user.id == chat.id == owner)


def is_authorized_private(update: Update) -> bool:
    """Owner or invited subscriber, never group/chat username access."""
    user, chat = update.effective_user, update.effective_chat
    if not (user and chat and chat.type == "private" and user.id == chat.id):
        return False
    if is_owner_private(update):
        return True
    try:
        with _LOCK:
            _load()
            return str(user.id) in _SUBSCRIBERS
    except RuntimeError:
        return False


def recipient_ids() -> list[int]:
    """Read-only delivery targets. Never return groups or usernames."""
    owner = owner_id()
    if owner is None:
        return []
    try:
        with _LOCK:
            _load()
            return [owner] + sorted(
                int(key) for key in _SUBSCRIBERS
                if int(key) != owner
            )
    except RuntimeError as exc:
        logger.error("Subscribers unavailable; owner-only delivery (%s)",
                     type(exc).__name__)
        return [owner]


async def send_liquidation_alert(bot: Any, message: str) -> int:
    """Best-effort fanout; one blocked subscriber must not block the owner."""
    delivered = 0
    for chat_id in recipient_ids():
        try:
            await bot.send_message(chat_id=chat_id, text=message)
            delivered += 1
        except Exception as exc:
            logger.warning("Liquidation alert delivery failed | recipient=%s | %s",
                           chat_id, type(exc).__name__)
    return delivered


def create_invite() -> str:
    with _LOCK:
        _load()
        now = time.time()
        for digest, expires in list(_INVITES.items()):
            if expires <= now:
                _INVITES.pop(digest, None)
        if len(_INVITES) >= _MAX_INVITES:
            raise ValueError("Too many pending invitations; let one expire")
        token = secrets.token_urlsafe(24)
        _INVITES[hashlib.sha256(token.encode("ascii")).hexdigest()] = now + _INVITE_TTL
        _persist()
        return token


def join(token: str, user_id: int, username: str | None = None) -> bool:
    if (not isinstance(token, str) or not 12 <= len(token) <= 100
            or not _USER_ID.fullmatch(str(user_id)) or user_id == owner_id()):
        return False
    digest = hashlib.sha256(token.encode("utf8")).hexdigest()
    with _LOCK:
        _load()
        if str(user_id) in _SUBSCRIBERS:
            return True
        if len(_SUBSCRIBERS) >= _MAX_SUBSCRIBERS:
            return False
        match = next((key for key in _INVITES
                      if hmac.compare_digest(key, digest)), None)
        if match is None or _INVITES[match] <= time.time():
            return False
        _INVITES.pop(match)
        _SUBSCRIBERS[str(user_id)] = {
            "username": (username or "")[:64],
            "added_at": time.time(),
        }
        _persist()
        return True


def revoke(user_id: int) -> bool:
    with _LOCK:
        _load()
        if str(user_id) not in _SUBSCRIBERS:
            return False
        _SUBSCRIBERS.pop(str(user_id))
        _persist()
        return True


async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner_private(update) or not update.message:
        return
    try:
        token = create_invite()
    except (OSError, RuntimeError, ValueError):
        await update.message.reply_text(
            "Could not create invitation. Check the persistent bot storage."
        )
        return
    await update.message.reply_text(
        "🔐 Private Hatom + XOXNO monitoring invitation (one-use, 24h).\n"
        "Send this command PRIVATELY to the person you choose. "
        "They must first open WOODY Monitor, press Start, then send:\n\n"
        "/liquidation_join " + token + "\n\n"
        "They will receive only read-only liquidation notifications and "
        "can use /hatom_profit and /xoxno_profit, plus scan/status commands. "
        "No owner/admin, wallet or transaction privileges.\n"
        "Keep the invitation private; anyone holding it can claim this one slot."
    )


async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    if (update.effective_chat.type != "private"
            or update.effective_chat.id != update.effective_user.id):
        return
    args = getattr(context, "args", None) or []
    if len(args) != 1:
        await update.message.reply_text(
            "Use the private one-time invitation received from the bot owner."
        )
        return
    try:
        accepted = join(args[0], update.effective_user.id,
                        update.effective_user.username)
    except (OSError, RuntimeError, ValueError):
        accepted = False
    if not accepted:
        await update.message.reply_text(
            "Invitation invalid/expired or subscriptions full. "
            "Ask the owner for a fresh private invitation."
        )
        return
    await update.message.reply_text(
        "✅ Hatom + XOXNO Liquidation Watch activated for your private chat.\n"
        "You will receive NEW confirmed liquidation alerts, even when profit "
        "is negative or unknown. Old alerts are not replayed.\n"
        "Try /hatom_report, /hatom_profit, /xoxno_scan or /xoxno_profit. "
        "Calculations are indicative; there is no automated execution."
    )
    owner = owner_id()
    if owner and owner != update.effective_user.id:
        try:
            await context.bot.send_message(
                chat_id=owner,
                text="🔐 Liquidation Watch: a second user joined privately.\n"
                     f"Telegram ID: {update.effective_user.id}\n"
                     f"Username: @{update.effective_user.username or 'unknown'}\n"
                     "You can revoke access with /liquidation_remove "
                     f"{update.effective_user.id}",
            )
        except Exception as exc:
            logger.warning("Could not inform owner of join (%s)", type(exc).__name__)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner_private(update) or not update.message:
        return
    try:
        with _LOCK:
            _load()
            rows = [
                f"{key} (@{value.get('username') or 'unknown'})"
                for key, value in sorted(_SUBSCRIBERS.items())
            ]
    except RuntimeError:
        await update.message.reply_text("Subscription history unavailable.")
        return
    await update.message.reply_text(
        "🔐 Authorized read-only liquidation subscribers:\n"
        + ("\n".join(rows) if rows else "None yet")
        + "\n\nOnly the owner can invite/revoke."
    )


async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner_private(update) or not update.message:
        return
    args = getattr(context, "args", None) or []
    if len(args) != 1 or not _USER_ID.fullmatch(args[0]):
        await update.message.reply_text(
            "Usage: /liquidation_remove TELEGRAM_NUMERIC_ID"
        )
        return
    try:
        removed = revoke(int(args[0]))
    except (OSError, RuntimeError):
        await update.message.reply_text("Could not update subscription history.")
        return
    await update.message.reply_text(
        "Access revoked." if removed else "Telegram ID is not subscribed."
    )


async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user or not update.message:
        return
    if update.effective_chat.type != "private" or update.effective_chat.id != update.effective_user.id:
        return
    if is_owner_private(update):
        await update.message.reply_text("The bot owner cannot unsubscribe here.")
        return
    try:
        removed = revoke(update.effective_user.id)
    except (OSError, RuntimeError):
        await update.message.reply_text("Could not update subscription history.")
        return
    await update.message.reply_text(
        "Private liquidation alerts disabled for your account."
        if removed else "Your account is not subscribed."
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("liquidation_invite", invite_command))
    app.add_handler(CommandHandler("liquidation_join", join_command))
    app.add_handler(CommandHandler("liquidation_users", list_command))
    app.add_handler(CommandHandler("liquidation_remove", revoke_command))
    app.add_handler(CommandHandler("liquidation_leave", leave_command))

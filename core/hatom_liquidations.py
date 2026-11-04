"""Read-only Hatom opportunity watcher with *admin-private-only* Telegram alerts.

A trusted upstream observer must expose current Hatom positions and health factors.
Hatom does not publish a documented all-borrowers liquidation feed; therefore this
module intentionally stays disabled without a configured live upstream source.

This module never signs, sends or prepares a blockchain transaction.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)
_LAST_ALERTS: dict[tuple[str, str, str], tuple[str, float]] = {}
_STATE: dict[str, Any] = {
    "last_poll": None,
    "last_error": None,
    "last_candidates": 0,
    "sent": 0,
    "suppressed_unpriced": 0,
}

# This is intentionally NOT the shared WOODY chat_targets() helper.
# The only possible recipient is the authenticated Telegram administrator.
def _admin_id() -> int | None:
    raw = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    return int(raw) if raw.isdecimal() and int(raw) > 0 else None


def _enabled() -> bool:
    return os.getenv("ENABLE_HATOM_WATCH", "false").strip().lower() in {"true", "1", "yes", "on"}


def _source() -> str:
    source = os.getenv("HATOM_WATCH_SOURCE", "feed").strip().lower()
    return source if source in {"feed", "onchain"} else "invalid"


def _ready() -> bool:
    return _source() == "onchain" or (_source() == "feed" and bool(_feed_url()))


def _feed_url() -> str:
    url = os.getenv("HATOM_OPPORTUNITIES_URL", "").strip()
    parts = urlsplit(url)
    if not url or parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return ""
    return url


def _interval() -> int:
    try:
        return max(30, min(int(os.getenv("HATOM_WATCH_INTERVAL_SECONDS", "60")), 3600))
    except ValueError:
        return 60


def _freshness() -> int:
    try:
        return max(30, min(int(os.getenv("HATOM_MAX_SOURCE_AGE_SECONDS", "120")), 600))
    except ValueError:
        return 120


def _cooldown() -> int:
    try:
        return max(60, min(int(os.getenv("HATOM_ALERT_COOLDOWN_SECONDS", "900")), 86400))
    except ValueError:
        return 900


def _timestamp(value: Any) -> float | None:
    if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).replace(
                tzinfo=timezone.utc
            ).timestamp() if datetime.fromisoformat(value.strip().replace("Z", "+00:00")).tzinfo is None else datetime.fromisoformat(value.strip().replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def normalize_positions(payload: Any, *, now: float | None = None, max_age: int = 120) -> list[dict[str, Any]]:
    """Validate feed signals; stale, malformed and healthy entries never generate alerts.

    The feed is indicative, not proof of on-chain liquidatability.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("positions"), list):
        raise ValueError("Expected JSON object with a positions list")
    now = time.time() if now is None else now
    global_updated = payload.get("updated_at")
    positions: list[dict[str, Any]] = []
    for position in payload["positions"][:1000]:
        if not isinstance(position, dict):
            continue
        borrower = str(position.get("borrower") or "").strip()
        if not re.fullmatch(r"erd1[023456789acdefghjklmnpqrstuvwxyz]{58}", borrower):
            continue
        health = _positive_number(position.get("health_factor"))
        if health is None or health > 1.05:
            continue
        observed_at = _timestamp(position.get("updated_at", global_updated))
        if observed_at is None or not (-15 <= now - observed_at <= max_age):
            continue
        debt = re.sub(r"[^A-Za-z0-9-]", "", str(position.get("debt_token") or ""))[:32]
        collateral = re.sub(r"[^A-Za-z0-9-]", "", str(position.get("collateral_token") or ""))[:32]
        if not debt or not collateral:
            continue
        repay_usd = _positive_number(position.get("max_repay_usd"))
        borrowed_usd = _positive_number(position.get("borrow_usd"))
        if borrowed_usd is not None and repay_usd is not None:
            repay_usd = min(repay_usd, borrowed_usd * 0.5)
        positions.append({
            "borrower": borrower,
            "health_factor": health,
            "debt_token": debt,
            "collateral_token": collateral,
            "max_repay_usd": repay_usd,
            "observed_at": observed_at,
            "category": "BELOW_1" if health < 1 else "NEAR_1",
        })
    return sorted(positions, key=lambda item: item["health_factor"])


def _message(position: dict[str, Any]) -> str:
    if position["category"] == "ONCHAIN_RISKY":
        return (
            "🔐 Hatom Watch — PRIVATE ADMIN ALERT\n\n"
            "⚠️ ON-CHAIN RISK SIGNAL (not a profit quote)\n"
            f"Borrower: {position['borrower']}\n"
            f"Debt market: {position['borrow_market']}\n"
            f"Collateral market: {position['collateral_market']}\n"
            f"Debt amount (raw base units): {position['raw_borrow']}\n\n"
            "Controller reports isRisky=true; allowance was checked for a minimal "
            "repayment amount. Real repay limits, token decimals, prices, "
            "collateral sale, gas, and slippage still need verification. "
            "NO transactions are executed."
        )
    status = "POTENTIAL LIQUIDATION" if position["category"] == "BELOW_1" else "POSITION AT RISK"
    message = (
        "🔐 Hatom Watch — PRIVATE ADMIN ALERT\n\n"
        + status + "\n"
        + f"Health factor (upstream): {position['health_factor']:.4f}\n"
        + f"Debt token: {position['debt_token']}\n"
        + f"Collateral: {position['collateral_token']}\n"
        + f"Borrower: {position['borrower']}\n"
    )
    if position["max_repay_usd"] is not None:
        message += (
            f"Reported maximum repayment: ${position['max_repay_usd']:,.2f}\n"
            f"Theoretical liquidator bonus (4%, before costs): ${position['max_repay_usd'] * 0.04:,.2f}\n"
        )
    message += (
        "\n⚠️ Unverified upstream signal, not an executable quote. "
        "Check current on-chain health, oracle data, repay limits, liquidity, gas and slippage first. "
        "NO trades are executed by this monitor."
    )
    return message


def _download() -> list[dict[str, Any]]:
    url = _feed_url()
    if not url:
        raise RuntimeError("No valid HTTPS HATOM_OPPORTUNITIES_URL configured")
    response = requests.get(url, timeout=10, allow_redirects=False, headers={"Accept": "application/json"})
    response.raise_for_status()
    if len(response.content) > 1_000_000:
        raise ValueError("Upstream feed is too large")
    return normalize_positions(response.json(), max_age=_freshness())


async def scan(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Poll a source, then alert only the administrator in their own private chat."""
    admin = _admin_id()
    if admin is None or not _enabled() or not _ready():
        return 0
    try:
        if _source() == "onchain":
            from core.hatom_onchain import scan_mainnet
            positions = await asyncio.to_thread(scan_mainnet)
        else:
            positions = await asyncio.to_thread(_download)
        _STATE["last_poll"] = datetime.now(timezone.utc).isoformat()
        _STATE["last_error"] = None
        _STATE["last_candidates"] = len(positions)
        _STATE["suppressed_unpriced"] = len(positions)
    except Exception as exc:
        _STATE["last_error"] = type(exc).__name__
        logger.warning("Hatom watch scan failed (%s)", type(exc).__name__)
        return 0

    # Risk indicators are not executable liquidation profit quotes.
    # Missing: repay limits, token decimals, fresh oracle prices, DEX quotes,
    # liquidation collateral recovery, gas costs, and slippage.
    # DO NOT dispatch an alert until these inputs are actually validated.
    logger.info("HATOM_UNPRICED_SIGNALS_SUPPRESSED | observed=%s", len(positions))
    return 0

    now = time.time()
    sent = 0
    for position in positions:
        if sent >= 5:  # guard against floods on a first scan
            break
        key = (position["borrower"], position.get("borrow_market", position["debt_token"]), position.get("collateral_market", position["collateral_token"]))
        last = _LAST_ALERTS.get(key)
        if last and last[0] == position["category"] and now - last[1] < _cooldown():
            continue
        try:
            await context.bot.send_message(
                chat_id=admin,  # never the public group ID
                text=_message(position),
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.warning("Hatom private alert delivery failed (%s)", type(exc).__name__)
            _STATE["last_error"] = type(exc).__name__
            break
        _LAST_ALERTS[key] = (position["category"], now)
        sent += 1
        _STATE["sent"] += 1

    if len(_LAST_ALERTS) > 2000:
        for key, (_, when) in list(_LAST_ALERTS.items()):
            if now - when > max(_cooldown(), 86400):
                _LAST_ALERTS.pop(key, None)
    return sent


def status_text() -> str:
    enabled = _enabled()
    configured = _ready()
    admin_ok = _admin_id() is not None
    status = "SCAN-ONLY (NO PROFIT ALERTS)" if enabled and configured and admin_ok else "PAUSED"
    return (
        "🔐 Hatom Watch — Private Admin\n"
        f"State: {status}\n"
        f"Observation mode: READ-ONLY\n"
        f"Discovery source: {_source()}\n"
        f"Discovery configured: {'yes' if configured else 'no'}\n"
        f"Admin private destination: {'configured' if admin_ok else 'missing'}\n"
        f"Unpriced risk signals on last scan: {_STATE['last_candidates']}\n"
        "Net-profit validation: NOT IMPLEMENTED\n"
        "Automatic liquidation alerts: BLOCKED\n"
        f"Alerts delivered this session: {_STATE['sent']}\n"
        f"Last successful poll: {_STATE['last_poll'] or 'never'}\n"
        f"Last error: {_STATE['last_error'] or 'none'}\n\n"
        "Read-only observation. On-chain results are not profit quotes. "
        "Check Hatom contract state and liquidity before manual action."
    )


def _admin_private(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    admin = _admin_id()
    return bool(admin and user and chat and user.id == admin and chat.id == admin and chat.type == "private")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _admin_private(update) and update.message:
        await update.message.reply_text(status_text())


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _admin_private(update):
        await context.bot.send_message(
            chat_id=_admin_id(),
            text="🔐 Hatom Watch — PRIVATE TEST ALERT\nOnly the admin's private chat receives Hatom notifications. This is a test, not a live opportunity.",
        )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _admin_private(update) or not update.message:
        return
    if not _enabled() or not _ready():
        await update.message.reply_text("Hatom Watch inactive. Configure ENABLE_HATOM_WATCH=true with HATOM_WATCH_SOURCE=onchain or a trusted feed.")
        return
    sent = await scan(context)
    await update.message.reply_text(f"Hatom scan complete. Verified-profit alerts sent: {sent}.\n{status_text()}")


def register(app: Application) -> None:
    app.add_handler(CommandHandler("hatom_status", status_command))
    app.add_handler(CommandHandler("hatom_test", test_command))
    app.add_handler(CommandHandler("hatom_scan", scan_command))
    if _enabled() and _ready() and _admin_id() and app.job_queue:
        app.job_queue.run_repeating(scan, interval=_interval(), first=12, name="hatom_private_observer")
        logger.info("Hatom private observer scheduled | interval=%ss", _interval())
    else:
        logger.info("Hatom private observer disabled until an on-chain or trusted feed source is enabled")

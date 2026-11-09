"""XOXNO Lending MultiversX-only, admin-private, READ-ONLY eligibility watcher.

Public XOXNO leaderboard is *discovery*, NOT on-chain execution evidence.
A fresh Controller canBeLiquidated query is required before notifications.
Exact liquidation payoff, gas and DEX-net profit are NOT calculated here.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.hatom_onchain import VmClient, address_decode

logger = logging.getLogger(__name__)
CONTROLLER = "erd1qqqqqqqqqqqqqpgqyq9mwxkq7zelkupafta5ah95pw6362j745qsk5mdzw"
LIST_URL = "https://api.xoxno.com/lending/leaderboard/liquidate"
NFT = re.compile(r"^XLEND-18dc6f-([0-9a-f]{1,16})$")
MAX_ROWS = 20
_STATE_LOCK = threading.RLock()
_LOADED_PATH: str | None = None
_NOTIFIED: dict[str, float] = {}
_LAST_BATCH = 0.0
_STATS: dict[str, Any] = {
    "last_poll": None, "last_error": None, "api_candidates": 0,
    "confirmed": 0, "scans": 0, "alerts": 0,
}


def enabled() -> bool:
    return os.getenv("ENABLE_XOXNO_LENDING_WATCH", "false").strip().lower() in {
        "1", "true", "on", "yes"
    }


def admin_id() -> int | None:
    raw = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    return int(raw) if raw.isascii() and raw.isdecimal() and int(raw) > 0 else None


def admin_private(update: Update) -> bool:
    admin, user, chat = admin_id(), update.effective_user, update.effective_chat
    return bool(admin and user and chat and user.id == admin
                and chat.id == admin and chat.type == "private")


def interval() -> int:
    try:
        return max(120, min(1800, int(
            os.getenv("XOXNO_LENDING_SCAN_INTERVAL_SECONDS", "240")
        )))
    except ValueError:
        return 240


def state_file() -> Path:
    return Path(os.getenv("DATA_DIR", "data")) / "xoxno_lending_alerts.json"


def load_state() -> None:
    global _LOADED_PATH, _LAST_BATCH
    with _STATE_LOCK:
        path = state_file()
        if _LOADED_PATH == str(path):
            return
        _LOADED_PATH = str(path)
        _NOTIFIED.clear()
        _LAST_BATCH = 0
        try:
            if path.stat().st_size > 90_000:
                raise ValueError("Oversized XOXNO watcher state")
            obj = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(obj, dict):
                raise ValueError("Invalid state")
            now = time.time()
            batch = obj.get("last_batch", 0)
            if type(batch) in (int, float) and 0 <= now - batch < 86400:
                _LAST_BATCH = float(batch)
            for key, ts in list(obj.get("notified", {}).items())[:200]:
                if (isinstance(key, str) and NFT.fullmatch(key)
                        and type(ts) in (int, float)
                        and 0 <= now - ts < 24 * 3600):
                    _NOTIFIED[key] = float(ts)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            logger.warning("XOXNO watcher state unavailable (%s)", type(exc).__name__)


def mark_sent(rows: list[dict[str, Any]]) -> None:
    global _LAST_BATCH
    load_state()
    with _STATE_LOCK:
        now = time.time()
        _LAST_BATCH = now
        for row in rows:
            _NOTIFIED[row["identifier"]] = now
        for key, ts in list(_NOTIFIED.items()):
            if now - ts >= 24 * 3600:
                _NOTIFIED.pop(key, None)
        path = state_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps({
                "last_batch": _LAST_BATCH, "notified": _NOTIFIED
            }), encoding="utf8")
            os.replace(tmp, path)
        except OSError as exc:
            logger.warning("XOXNO watcher alert persistence failed (%s)", type(exc).__name__)


def nonce_of(identifier: Any) -> int:
    match = NFT.fullmatch(identifier) if isinstance(identifier, str) else None
    if not match:
        raise ValueError("Not a verified MultiversX XOXNO account NFT")
    nonce = int(match.group(1), 16)
    if not 0 < nonce < 2**64:
        raise ValueError("Invalid account nonce")
    return nonce


def parse_candidate(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("wallet"), dict):
        raise ValueError("Unexpected XOXNO leaderboard schema")
    identifier = raw.get("identifier")
    nonce = nonce_of(identifier)
    borrower = raw["wallet"].get("address")
    address_decode(borrower)
    try:
        if isinstance(raw.get("borrowed"), bool):
            raise ValueError("Invalid borrowed value")
        borrowed = Decimal(str(raw["borrowed"]))
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("Invalid borrowed value") from exc
    if not borrowed.is_finite() or borrowed <= 0 or borrowed > Decimal("10000000000"):
        raise ValueError("Borrowed value unavailable")
    return {
        "identifier": identifier, "nonce": nonce,
        "borrower": borrower, "borrowed_usd_api": borrowed,
    }


def discover(*, session: Any = None) -> list[dict[str, Any]]:
    session = session if session is not None else requests.Session()
    response = session.get(
        LIST_URL, timeout=8, allow_redirects=False,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    if len(response.content) > 220_000:
        raise ValueError("XOXNO API list too large")
    payload = response.json()
    if not isinstance(payload, list) or len(payload) > 200:
        raise ValueError("Invalid XOXNO liquidation API response")
    out: list[dict[str, Any]] = []
    seen = set()
    for item in payload[:MAX_ROWS]:
        try:
            row = parse_candidate(item)
        except (ValueError, TypeError) as exc:
            logger.warning("Skipping unsupported XOXNO candidate (%s)", type(exc).__name__)
            continue
        if row["identifier"] not in seen:
            seen.add(row["identifier"])
            out.append(row)
    return out


def confirm_onchain(rows: list[dict[str, Any]], *, vm: Any = None) -> list[dict[str, Any]]:
    # The XOXNO lending Controller is separate from Hatom's.
    vm = vm if vm is not None else VmClient(controller=CONTROLLER, timeout=8)
    accepted: list[dict[str, Any]] = []
    for row in rows[:MAX_ROWS]:
        try:
            nonce = nonce_of(row["identifier"])
            arg = nonce.to_bytes(max(1, (nonce.bit_length() + 7)//8), "big")
            result = vm.query(CONTROLLER, "canBeLiquidated", [arg])
            if result == [b"\x01"]:
                accepted.append(dict(row, verified_at=time.time()))
            elif result not in ([b""], [b"\x00"]):
                raise ValueError("Unsupported XOXNO liquidation view result")
        except (ValueError, requests.RequestException) as exc:
            logger.warning("XOXNO on-chain recheck failed (%s)", type(exc).__name__)
    return accepted


def inspect() -> tuple[list[dict[str, Any]], int]:
    records = discover()
    return confirm_onchain(records), len(records)


def eligible_to_send(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load_state()
    now = time.time()
    with _STATE_LOCK:
        if now - _LAST_BATCH < 3600:
            return []
        return [r for r in rows if
                now - _NOTIFIED.get(r["identifier"], -1e12) >= 12 * 3600][:2]


def alert_text(rows: list[dict[str, Any]], *, manual: bool = False) -> str:
    lines = [
        "🔎 XOXNO Lending — PRIVATE RECHECK" if manual
        else "🟠 XOXNO Lending — PRIVATE LIQUIDATION CANDIDATE",
        "MultiversX | READ-ONLY",
        "Source: XOXNO public liquidation list + on-chain Controller.",
        "NOT A PROFIT ALERT. Only the health-based eligibility was reconfirmed.",
        "",
    ]
    for n, row in enumerate(rows[:3], 1):
        lines.extend([
            f"{n}. Position NFT: {row['identifier']}",
            f"   Account owner: {row['borrower']}",
            f"   API-estimated borrow value: USD {row['borrowed_usd_api']:.2f}",
            "   On-chain canBeLiquidated: TRUE",
            "   Net gain after repayment/gas/swap: NOT VERIFIED",
            "",
        ])
    lines.extend([
        "Liquidation repayment and collateral payout NOT simulated.",
        "Do not assume the +0.25 USD threshold is met.",
        "No funds used; no wallet keys; no transaction sent.",
    ])
    return "\n".join(lines)[:3600]


def status_text() -> str:
    return (
        "🔐 XOXNO Lending Watch — MultiversX\n"
        f"Enabled: {'YES' if enabled() else 'NO'}\n"
        "Mode: READ-ONLY; NO wallet or execution\n"
        "Discovery: XOXNO public liquidatable leaderboard\n"
        "Validation: canBeLiquidated on mainnet Controller\n"
        f"Scan interval: {interval()}s\n"
        "Private eligibility alerts: <=1 batch/hour; <=2 positions/batch\n"
        "Per NFT repeat cooldown: 12h\n"
        "Profit: /xoxno_profit (read-only, indicative and NOT verified)\n"
        "Profit model floor: >= USD 0.25 after gas estimate + reserve\n"
        f"Scans this session: {_STATS['scans']}\n"
        f"API candidates: {_STATS['api_candidates']}\n"
        f"On-chain confirmed: {_STATS['confirmed']}\n"
        f"Private batches this session: {_STATS['alerts']}\n"
        f"Last successful poll: {_STATS['last_poll'] or 'never'}\n"
        f"Last error: {_STATS['last_error'] or 'none'}"
    )


async def scan(context: ContextTypes.DEFAULT_TYPE, *, manual: bool = False) -> list[dict[str, Any]]:
    if not enabled() or admin_id() is None:
        return []
    try:
        positions, found = await asyncio.to_thread(inspect)
        _STATS["last_error"] = None
        _STATS["last_poll"] = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")
        _STATS["api_candidates"] = found
        _STATS["confirmed"] = len(positions)
        _STATS["scans"] += 1
    except Exception as exc:
        _STATS["last_error"] = type(exc).__name__
        logger.warning("XOXNO lending watcher unavailable (%s)", type(exc).__name__)
        return []
    if not manual and positions:
        selected = eligible_to_send(positions)
        if selected:
            await context.bot.send_message(chat_id=admin_id(), text=alert_text(selected))
            mark_sent(selected)
            _STATS["alerts"] += 1
    return positions


async def scan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await scan(context)


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin_private(update) or not update.message:
        return
    if not enabled():
        await update.message.reply_text("XOXNO lending watch is disabled.")
        return
    rows = await scan(context, manual=True)
    if _STATS["last_error"]:
        await update.message.reply_text(
            "XOXNO data unavailable or on-chain verification failed.\n" + status_text()
        )
    elif rows:
        await update.message.reply_text(alert_text(rows, manual=True))
    else:
        await update.message.reply_text(
            "No currently confirmed XOXNO MultiversX liquidation candidate "
            "was found in the public leaderboard.\n\n" + status_text()
        )


def _requested_nft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Accept explicit XLEND NFT or a reply to one of our private candidate alerts."""
    arguments = getattr(context, "args", None) or []
    if arguments:
        proposed = str(arguments[0]).strip()
        if NFT.fullmatch(proposed):
            return proposed
        return None
    msg = getattr(update.message, "reply_to_message", None)
    txt = getattr(msg, "text", "") or ""
    match = NFT.search(txt) if False else re.search(r"XLEND-18dc6f-[0-9a-f]{1,16}", txt)
    if match and NFT.fullmatch(match.group(0)):
        return match.group(0)
    return None


async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Private on-demand estimate, ALWAYS live rechecked and clearly not verified."""
    if not admin_private(update) or not update.message:
        return
    if not enabled():
        await update.message.reply_text("XOXNO Lending Watch is disabled.")
        return
    from core.xoxno_profit import calculate, format_report, CalculationUnavailable
    identifier = _requested_nft(update, context)
    if identifier is None:
        # Recheck a current API candidate when user does not specify a NFT.
        try:
            rows, _ = await asyncio.wait_for(asyncio.to_thread(inspect), timeout=40)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.info("XOXNO profit candidate discovery unavailable (%s)", type(exc).__name__)
            rows = []
        if not rows:
            await update.message.reply_text(
                "No currently confirmed XOXNO account to calculate. "
                "Reply with /xoxno_profit to an XOXNO private alert, or send "
                "/xoxno_profit XLEND-18dc6f-<hex_nonce> . "
                "A wallet address is not enough: XOXNO lending positions are account NFTs."
            )
            return
        identifier = rows[0]["identifier"]
    try:
        estimate = await asyncio.wait_for(
            asyncio.to_thread(calculate, identifier), timeout=110
        )
    except asyncio.TimeoutError:
        await update.message.reply_text(
            "XOXNO quote timed out. Profit remains NOT VERIFIED. "
            "No funds were used."
        )
        return
    except (CalculationUnavailable, QuoteUnavailable, requests.RequestException,
            ValueError, TypeError) as exc:
        logger.info("XOXNO profit scenario incomplete (%s)", type(exc).__name__)
        await update.message.reply_text(
            "XOXNO — no complete/validated liquidation scenario for "
            + identifier + ".\nReason: " + str(exc)[:160]
            + "\nProfit: NOT VERIFIED. Do not liquidate based on this result."
        )
        return
    await update.message.reply_text(format_report(estimate))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if admin_private(update) and update.message:
        await update.message.reply_text(status_text())


def register(app: Application) -> None:
    app.add_handler(CommandHandler("xoxno_status", status_command))
    app.add_handler(CommandHandler("xoxno_scan", scan_command))
    app.add_handler(CommandHandler("xoxno_profit", profit_command))
    if enabled() and admin_id() and app.job_queue:
        app.job_queue.run_repeating(
            scan_job, interval=interval(), first=65,
            name="xoxno_lending_liquidation_private",
        )
        logger.info("XOXNO Lending read-only watcher scheduled | interval=%ss", interval())
    else:
        logger.info("XOXNO Lending read-only watcher disabled")

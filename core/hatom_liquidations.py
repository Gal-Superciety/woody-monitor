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
from datetime import datetime, time as clock_time, timezone
from typing import Any
from zoneinfo import ZoneInfo
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
        from core.hatom_digest import store_scan
        checked = 0
        if _source() == "onchain":
            from core.hatom_onchain import get_scanner
            checked = get_scanner().status.get("checked", 0)
        store_scan(positions, checked=checked)
        if _source() == "onchain":
            from core.hatom_stages import observe
            observe(positions)
        _STATE["last_candidates"] = len(set(row["borrower"] for row in positions))
        _STATE["suppressed_unpriced"] = len(positions)
    except Exception as exc:
        _STATE["last_error"] = type(exc).__name__
        logger.warning("Hatom watch scan failed (%s)", type(exc).__name__)
        return 0

    # Risk indicators are not executable liquidation profit quotes.
    # Missing: repay limits, token decimals, fresh oracle prices, DEX quotes,
    # liquidation collateral recovery, gas costs, and slippage.
    # DO NOT dispatch an alert until these inputs are actually validated.
    logger.info("HATOM_RISK_SCAN_COLLECTED | new_route_signals=%s | private_digest_only", len(positions))
    return 0



def _value_eligible_positions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Read-only market-price scenarios; if anything is missing, show reason."""
    from core.hatom_onchain import VmClient
    from core.hatom_profit import MarketData, estimate, explain_missing
    results: dict[str, Any] = {}
    vm = VmClient(timeout=8)
    prices = MarketData(timeout=7)
    for row in rows[:8]:
        borrower = row["borrower"]
        try:
            results[borrower] = estimate(row, vm=vm, prices=prices)
        except Exception as exc:
            results[borrower] = explain_missing(exc)
            logger.info("HATOM_PROFIT_SCENARIO_UNAVAILABLE | reason=%s", type(exc).__name__)
    return results


async def eligibility_notifier(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Send only private, positive indicative DEX scenarios after strict screen.

    Hatom scan and scheduled risk digest continue normally. No wallet signing.
    """
    if not _enabled() or not _ready() or _source() != "onchain" or _admin_id() is None:
        return False
    from core.hatom_stages import pending, revalidate, format_alert, mark_delivered
    from core.hatom_profit_filter import eligible_for_priority_alert
    candidates = pending()
    if not candidates:
        return False
    # Inspect several candidates; the first two may be economically worthless.
    checked, errors = await asyncio.to_thread(revalidate, candidates, max_select=8)
    if errors:
        logger.info("HATOM_ELIGIBILITY_REFRESH_ERRORS | skipped=%s", errors)
    if not checked:
        return False
    valuations = await asyncio.to_thread(_value_eligible_positions, checked)
    passing: list[tuple[dict[str, Any], dict[str, Any]]] = []
    reason_counts: dict[str, int] = {}
    for row in checked:
        qualifies, reason, screened = eligible_for_priority_alert(
            valuations.get(row["borrower"])
        )
        if qualifies and screened is not None:
            passing.append((row, screened))
        else:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    logger.info(
        "HATOM_PROFIT_ALERT_SCREEN | checked=%s | passing=%s | rejected=%s",
        len(checked), len(passing), reason_counts
    )
    if not passing:
        return False
    # Pick up to two distinct wallets with the best *indicative* surplus,
    # without altering the Stage-2 borrower cooldown or hourly limit.
    passing.sort(key=lambda item: item[1]["screened_surplus_usd"], reverse=True)
    selected = passing[:2]
    rows = [row for row, _ in selected]
    screened_values = {row["borrower"]: value for row, value in selected}
    await context.bot.send_message(
        chat_id=_admin_id(), text=format_alert(rows, screened_values, profit_screened=True)
    )
    mark_delivered(rows)
    _STATE["sent"] += 1
    return True


async def digest(context: ContextTypes.DEFAULT_TYPE, *, manual: bool = False) -> bool:
    """Send a private, rate-limited risk summary, not one alert per market."""
    if not _enabled() or not _ready() or _source() != "onchain" or _admin_id() is None:
        return False
    from core.hatom_digest import state_snapshot, recheck, build_report, mark_report_sent
    snapshot = state_snapshot()
    candidates = snapshot["candidates"]
    if not candidates and not manual:
        return False
    checked, errors = await asyncio.to_thread(recheck, candidates)
    if not checked and not manual:
        return False
    report = build_report(
        candidates, verified=checked, errors=errors,
        scans=snapshot["scans"], checks=snapshot["checks"]
    )
    await context.bot.send_message(chat_id=_admin_id(), text=report)
    if not manual:
        mark_report_sent()
    _STATE["sent"] += 1
    return True


def status_text() -> str:
    enabled = _enabled()
    configured = _ready()
    admin_ok = _admin_id() is not None
    status = "SCAN + TWO-STAGE PRIVATE ALERTS" if enabled and configured and admin_ok else "PAUSED"
    from core.hatom_digest import digest_hours, state_snapshot
    report_state = state_snapshot()
    from core.hatom_stages import status as stage_status
    stage = stage_status()
    return (
        "🔐 Hatom Watch — Private Admin\n"
        f"State: {status}\n"
        f"Observation mode: READ-ONLY\n"
        f"Discovery source: {_source()}\n"
        f"Discovery configured: {'yes' if configured else 'no'}\n"
        f"Admin private destination: {'configured' if admin_ok else 'missing'}\n"
        f"Unpriced risk signals on last scan: {_STATE['last_candidates']}\n"
        "Profit scenario: REFERENCE USD PRICES + ASSUMED COSTS\n"
        "Verified executable profit: NOT AVAILABLE (no transaction simulation)\n"
        "Risk alerts: PRIVATE DIGEST ONLY\n"
        "Stage 2: PROFIT-SCREENED INDICATIVE ONLY; 1 batch/hour, 2 wallets\n"
        "Priority filter: DEX quote + minimum repay $25 + safety margin + $2\n"
        "Stage 2 borrower cooldown: 12h\n"
        f"Pending stage 2 candidates: {stage['pending_eligible']}\n"
        f"Private risk digest: {','.join(f'{hour:02d}:00' for hour in digest_hours())} Berlin\n"
        f"Risk wallets observed (last 12h): {len(report_state['candidates'])}\n"
        f"Completed scans this session: {report_state['scans']}\n"
        f"Wallets checked this session: {report_state['checks']}\n"
        "Trade signing and execution: DISABLED\n"
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
    await scan(context)
    await update.message.reply_text(f"Hatom scan completed (risk data stored; no instant alerts).\n{status_text()}")


def _profit_requested_borrowers(update: Update, context: ContextTypes.DEFAULT_TYPE
                                ) -> list[str]:
    """Read only borrower addresses from command args or a replied Hatom alert."""
    from core.hatom_onchain import address_decode
    explicit_args = getattr(context, "args", None) or []
    text_source = " ".join(explicit_args)
    if not text_source and update.message:
        reply = getattr(update.message, "reply_to_message", None)
        text_source = str(getattr(reply, "text", "") or "")
    if not text_source:
        return []
    exact = re.compile(r"erd1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{58}")
    # Text of prior Stage-2 alerts: "Borrower: erd1..."
    # Text of risk digests: "1. erd1...". Never use debt/collateral SCs.
    matches = re.findall(
        r"(?im)^\s*(?:(?:\d+[.)]\s+)?Borrower:\s*|\d+[.)]\s+)(erd1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{58})\b",
        text_source,
    )
    if explicit_args:
        matches = [m.group(0) for m in exact.finditer(text_source)]
    out: list[str] = []
    for item in matches:
        try:
            address_decode(item)
        except ValueError:
            continue
        if item not in out:
            out.append(item)
        if len(out) >= 3:
            break
    return out


def _recheck_borrowers_on_demand(borrowers: list[str]) -> list[dict[str, Any]]:
    """Query contract state NOW, without using historic raw repay estimates."""
    from core.hatom_onchain import VmClient, inspect_borrower_live
    client = VmClient(timeout=8)
    out: list[dict[str, Any]] = []
    for borrower in borrowers[:3]:
        try:
            rows = inspect_borrower_live(borrower, client=client, max_routes=1)
            out.extend(rows)
            if len(out) >= 2:
                break
        except (ValueError, requests.RequestException) as exc:
            logger.warning("Manual Hatom borrower recheck failed (%s)", type(exc).__name__)
    return out[:2]


async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Private on-demand valuation from saved cache OR an older Hatom alert."""
    if not _admin_private(update) or not update.message:
        return
    if not _enabled() or _source() != "onchain":
        await update.message.reply_text("Hatom Watch on-chain monitoring is paused.")
        return
    from core.hatom_digest import state_snapshot, store_scan
    from core.hatom_stages import revalidate, format_alert
    requested = _profit_requested_borrowers(update, context)
    snapshot = state_snapshot()
    recent = snapshot["candidates"]
    if requested:
        # Explicit address / replied historic alert: re-discover all contract
        # balances afresh; never trust the old message's monetary values.
        try:
            valid = await asyncio.wait_for(
                asyncio.to_thread(_recheck_borrowers_on_demand, requested), timeout=50
            )
        except asyncio.TimeoutError:
            await update.message.reply_text(
                "Hatom on-chain recheck timed out. No profit quote is available."
            )
            return
        errors = 0
    else:
        stage2 = [row for row in recent if row.get("category") == "ONCHAIN_ELIGIBLE"][:6]
        valid, errors = await asyncio.to_thread(revalidate, stage2)
        if not valid and recent:
            # A prior Stage-1 risk candidate may now qualify. Re-query by wallet.
            borrowers = [row["borrower"] for row in recent[:3]]
            try:
                valid = await asyncio.wait_for(
                    asyncio.to_thread(_recheck_borrowers_on_demand, borrowers), timeout=50
                )
            except asyncio.TimeoutError:
                await update.message.reply_text(
                    "Hatom on-chain recheck timed out. No profit quote is available."
                )
                return
    if not valid:
        if not requested and not recent:
            await update.message.reply_text(
                "No recent Hatom positions are stored yet. Scanning continues. "
                "To recheck an earlier position, reply to its Hatom alert with "
                "/hatom_profit, or send /hatom_profit erd1... (borrower address). "
                "An old alert is never used as proof of current eligibility."
            )
        else:
            await update.message.reply_text(
                f"No selected Hatom position passed the current Stage-2 "
                f"liquidation check (query errors: {errors}). "
                "This does not prove all of Hatom has no eligible positions."
            )
        return
    # Save only freshly reconfirmed public chain positions (no wallet keys).
    store_scan(valid)
    try:
        valuations = await asyncio.wait_for(
            asyncio.to_thread(_value_eligible_positions, valid), timeout=40
        )
    except asyncio.TimeoutError:
        valuations = {r["borrower"]: "DEX or price data timed out" for r in valid}
    await update.message.reply_text(format_alert(valid, valuations))

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _admin_private(update) or not update.message:
        return
    if not _enabled():
        await update.message.reply_text("Hatom Watch is paused in Railway.")
        return
    if _source() != "onchain":
        await update.message.reply_text("Hatom private risk digests require verified on-chain mode.")
        return
    await digest(context, manual=True)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("hatom_status", status_command))
    app.add_handler(CommandHandler("hatom_test", test_command))
    app.add_handler(CommandHandler("hatom_scan", scan_command))
    app.add_handler(CommandHandler("hatom_report", report_command))
    app.add_handler(CommandHandler("hatom_profit", profit_command))
    if _enabled() and _ready() and _admin_id() and app.job_queue:
        app.job_queue.run_repeating(scan, interval=_interval(), first=12, name="hatom_private_observer")
        if _source() == "onchain":
            app.job_queue.run_repeating(
                eligibility_notifier, interval=300, first=45, name="hatom_stage2_private_batch"
            )
        from core.hatom_digest import digest_hours
        if _source() == "onchain":
            for hour in digest_hours():
                app.job_queue.run_daily(
                    digest,
                    time=clock_time(hour=hour, minute=0, tzinfo=ZoneInfo("Europe/Berlin")),
                    name=f"hatom_admin_digest_{hour:02d}",
                )
        logger.info("Hatom private observer scheduled | interval=%ss | stage2 hourly cap | digest hours Berlin=%s",
                    _interval(), digest_hours() if _source() == "onchain" else [])
    else:
        logger.info("Hatom private observer disabled until an on-chain or trusted feed source is enabled")

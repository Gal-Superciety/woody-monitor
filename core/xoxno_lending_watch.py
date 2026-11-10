"""XOXNO Lending MultiversX-only, admin-private, READ-ONLY eligibility watcher.

Public XOXNO leaderboard is *discovery*, NOT on-chain execution evidence.
A fresh Controller canBeLiquidated query is required before notifications.
Every newly confirmed eligible position is alerted regardless of profit sign.
Exact liquidation payoff, gas and DEX-net profit remain indicative only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, time as clock_time
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
MAX_PRICE_PER_POLL = 6  # Rotate confirmed candidates for optional profit reports.
ELIGIBILITY_BATCH_INTERVAL = 240  # Seconds; pricing does not gate alerts.
_STATE_LOCK = threading.RLock()
_LOADED_PATH: str | None = None
_NOTIFIED: dict[str, float] = {}
_LAST_BATCH = 0.0
_STATS: dict[str, Any] = {
    "last_poll": None, "last_error": None, "api_candidates": 0,
    "confirmed": 0, "scans": 0, "alerts": 0,
    "priced": 0, "losses": 0, "below_threshold": 0,
    "positive": 0, "unavailable": 0,
}
_LAST_REPORT: dict[str, Any] | None = None


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
        _NOTIFIED.clear()
        _LAST_BATCH = 0
        try:
            if path.stat().st_size > 5_000_000:
                raise ValueError("Oversized XOXNO watcher state")
            obj = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(obj, dict):
                raise ValueError("Invalid state")
            now = time.time()
            batch = obj.get("last_batch", 0)
            if type(batch) in (int, float) and 0 <= now - batch < 86400:
                _LAST_BATCH = float(batch)
            notified = obj.get("notified", {})
            if not isinstance(notified, dict):
                raise ValueError("Invalid XOXNO notified history")
            for key, ts in notified.items():
                if (isinstance(key, str) and NFT.fullmatch(key)
                        and type(ts) in (int, float)
                        and 0 < ts <= now + 300):
                    _NOTIFIED[key] = float(ts)
            _LOADED_PATH = str(path)
        except FileNotFoundError:
            _LOADED_PATH = str(path)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            logger.error("XOXNO notification history unreadable (%s); alerts fail closed",
                         type(exc).__name__)
            raise RuntimeError("XOXNO notification history unavailable") from exc


def mark_sent(rows: list[dict[str, Any]]) -> None:
    global _LAST_BATCH
    load_state()
    with _STATE_LOCK:
        now = time.time()
        _LAST_BATCH = now
        for row in rows:
            _NOTIFIED[row["identifier"]] = now
        path = state_file()
        # Save BEFORE Telegram is called; failure prevents sending to avoid
        # repeats after restart. Different NFT positions have unique IDs.
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({
            "last_batch": _LAST_BATCH, "notified": _NOTIFIED
        }), encoding="utf8")
        os.replace(tmp, path)


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


def _priority_eligible(report: Any, *, now: float | None = None) -> bool:
    """Fail closed on stale, inconsistent or incomplete indicative net scenarios.

    Only determines whether to send a PRIVATE modeled-surplus alert.
    Does not determine real profit or transaction execution eligibility.
    """
    if not isinstance(report, dict):
        return False
    if (report.get("verified_profit") is not False
            or report.get("transaction_sent") is not False
            or report.get("full_pipeline_simulated") is not False
            or report.get("clears_quarter_dollar") is not True):
        return False
    try:
        repaid = Decimal(str(report["repay_usd"]))
        received = Decimal(str(report["dex_min_usd"]))
        gas = Decimal(str(report["estimated_gas_usd"]))
        reserve = Decimal(str(report["safety_buffer_usd"]))
        modeled = Decimal(str(report["scenario_net_usd"]))
        timestamp = float(report["quote_observed_at"])
        current = time.time() if now is None else now
        if not (all(x.is_finite() for x in (repaid, received, gas, reserve, modeled))
                and repaid > 0 and received > 0 and gas > 0
                and reserve >= Decimal("0.50")
                and modeled >= Decimal("0.25")
                and received > repaid + gas
                and abs(received - repaid - gas - reserve - modeled)
                <= Decimal("0.000000001")
                and 0 <= current-timestamp <= 60
                and NFT.fullmatch(str(report["identifier"]))):
            return False
    except (ValueError, TypeError, InvalidOperation, KeyError, OverflowError):
        return False
    return True


def price_candidates(rows: list[dict[str, Any]], *, poll: int = 0,
                     price_limit: int = MAX_PRICE_PER_POLL) -> dict[str, Any]:
    """Evaluate even unprofitable verified candidates; rotate bounded pricing.

    No quote is considered an error-free zero profit. Unknown stays unknown.
    """
    from core.xoxno_profit import calculate
    from core.hatom_profit import QuoteUnavailable
    if not rows:
        return {}
    count = min(MAX_ROWS, len(rows))
    budget = min(max(1, price_limit), count)
    start = (poll * budget) % count
    selected = [rows[(start + n) % count] for n in range(budget)]
    out: dict[str, Any] = {}
    for row in selected:
        identifier = row["identifier"]
        try:
            value = calculate(identifier)
            if value.get("identifier") != identifier:
                raise ValueError("Mismatched XOXNO NFT valuation")
            out[identifier] = value
        except Exception as exc:
            # Price or Controller failure is UNKNOWN, never a fictitious loss.
            logger.info("XOXNO scenario unavailable | nft=%s | error=%s",
                        identifier, type(exc).__name__)
            out[identifier] = "Unpriced: " + type(exc).__name__
    return out


def _scenario_counts(rows: list[dict[str, Any]],
                     valuations: dict[str, Any]) -> dict[str, int]:
    counts = {"priced": 0, "losses": 0, "below_threshold": 0,
              "positive": 0, "unavailable": 0}
    for row in rows:
        data = valuations.get(row["identifier"])
        if not isinstance(data, dict):
            counts["unavailable"] += 1
            continue
        try:
            net = Decimal(str(data["scenario_net_usd"]))
            if not net.is_finite():
                raise ValueError("Nonfinite result")
        except (KeyError, TypeError, ValueError, InvalidOperation):
            counts["unavailable"] += 1
            continue
        counts["priced"] += 1
        if net < 0:
            counts["losses"] += 1
        elif _priority_eligible(data):
            counts["positive"] += 1
        else:
            counts["below_threshold"] += 1
    return counts


def scan_report_text(
    rows: list[dict[str, Any]], valuations: dict[str, Any] | None = None,
    *, discovered: int = 0, error: str | None = None
) -> str:
    """Private scan digest; include losing and unavailable candidates."""
    valuations = valuations or {}
    counts = _scenario_counts(rows, valuations)
    lines = [
        "📊 XOXNO LENDING — PRIVATE SCAN REPORT (WIN + LOSS)",
        "MultiversX | READ-ONLY | MANUAL LIQUIDATIONS ONLY",
        "Time (Berlin): " + datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d %b %H:%M"),
        "API candidates: " + str(discovered),
        "Controller-confirmed eligible: " + str(len(rows)),
        "Priced scenarios: " + str(counts["priced"]),
        "🔴 Loss scenarios: " + str(counts["losses"]),
        "🟡 Nonnegative but below alert threshold: " + str(counts["below_threshold"]),
        "🟢 Passing modeled +0.25 USD alert screen: " + str(counts["positive"]),
        "⚪ Not priced / unavailable: " + str(counts["unavailable"]),
        "",
    ]
    if error:
        lines += ["⚠️ SCAN UNAVAILABLE: " + error[:75],
                  "No absence/profit conclusion can be drawn.", ""]
    elif not rows:
        lines += ["No candidates in the current public XOXNO liquidation list.",
                  "This is not a guarantee no account will become liquidatable.", ""]
    for idx, row in enumerate(rows[:MAX_ROWS], 1):
        ident = row["identifier"]
        data = valuations.get(ident)
        lines.append(str(idx) + ". " + ident + " | " + row["borrower"])
        if isinstance(data, dict):
            try:
                net = Decimal(str(data["scenario_net_usd"]))
                if not net.is_finite():
                    raise ValueError("Invalid net")
                verdict = ("🟢 +0.25 USD SCREEN" if _priority_eligible(data)
                           else "🔴 LOSS" if net < 0 else "🟡 BELOW THRESHOLD")
                lines.append("   Net after assumed gas + reserve: "
                             + format(net, "+.4f") + " USD " + verdict)
            except (ValueError, TypeError, KeyError, InvalidOperation):
                lines.append("   Scenario: UNKNOWN (invalid quote)")
        else:
            lines.append("   Scenario: UNKNOWN (no complete Controller + DEX quote)")
        if sum(len(x)+1 for x in lines) > 3000:
            lines.append("... Other candidate rows omitted from this message.")
            break
    lines.extend([
        "",
        "Candidate discovery uses XOXNO public leaderboard; live liquidation",
        "and DEX prices may change. Only up to " + str(MAX_PRICE_PER_POLL)
        + " candidate scenarios priced per poll, rotated on later polls.",
        "Separate positive alerts require >= 0.25 USD modeled after costs.",
        "Profit remains UNVERIFIED: gas and full TX are not simulated.",
        "No keys or automatic execution.",
    ])
    return "\n".join(lines)[:3800]


def positive_alert_text(rows: list[dict[str, Any]],
                        valuations: dict[str, Any]) -> str:
    lines = [
        "🚨 XOXNO LENDING — PRIVATE POSITIVE-SCENARIO ALERT",
        "MultiversX | READ-ONLY | MANUAL ACTION ONLY",
        "On-chain eligibility confirmed; profit is MODELED, NOT VERIFIED.",
        "",
    ]
    for idx, row in enumerate(rows[:2], 1):
        q = valuations[row["identifier"]]
        lines.extend([
            str(idx) + ". Account NFT: " + row["identifier"],
            "   Borrower: " + row["borrower"],
            "   Debt asset: " + q["repay_token"],
            "   Repay USD: " + format(q["repay_usd"], ".4f"),
            "   DEX minimum-out USD: " + format(q["dex_min_usd"], ".4f"),
            "   ASSUMED gas: USD " + format(q["estimated_gas_usd"], ".4f"),
            "   Safety reserve: USD " + format(q["safety_buffer_usd"], ".4f"),
            "   Indicative net: " + format(q["scenario_net_usd"], "+.4f") + " USD",
            "   Recheck: /xoxno_profit " + row["identifier"],
            "",
        ])
    lines += [
        "No full liquidation simulation. Gas is assumed, quotes can change.",
        "NOT a verified executable profit; NO transaction sent.",
    ]
    return "\n".join(lines)[:3800]


def eligible_to_send(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load_state()
    now = time.time()
    with _STATE_LOCK:
        if now - _LAST_BATCH < ELIGIBILITY_BATCH_INTERVAL:
            return []
        return [r for r in rows if r["identifier"] not in _NOTIFIED][:2]


def alert_text(rows: list[dict[str, Any]], *, manual: bool = False) -> str:
    lines = [
        "🔎 XOXNO Lending — PRIVATE RECHECK" if manual
        else "🟠 XOXNO Lending — PRIVATE LIQUIDATION CANDIDATE",
        "MultiversX | READ-ONLY",
        "Source: XOXNO public liquidation list + on-chain Controller.",
        "Eligibility CONFIRMED regardless of estimated GAIN, LOSS or UNKNOWN.",
        "Profit is NOT VERIFIED; this is NOT an execution recommendation.",
        "",
    ]
    for n, row in enumerate(rows[:3], 1):
        lines.extend([
            f"{n}. Position NFT: {row['identifier']}",
            f"   Account owner: {row['borrower']}",
            f"   API-estimated borrow value: USD {row['borrowed_usd_api']:.2f}",
            "   On-chain canBeLiquidated: TRUE",
            "   Net gain after repayment/gas/swap: UNKNOWN until /xoxno_profit",
            "   Recheck: /xoxno_profit " + row["identifier"],
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
        "Private alerts: ALL verified liquidatable, including losses/unknown\n"
        "Alert batches: 1 per 4min, up to 2 positions; lifetime NFT dedupe\n"
        "Scan reports including loss: on-demand /xoxno_report\n"
        "Duplicate suppression: same NFT notified only once while stored\n"
        "Profit: /xoxno_profit (read-only, indicative and NOT verified)\n"
        "Profit >= USD 0.25 is informational, NOT an alert requirement\n"
        f"Scans this session: {_STATS['scans']}\n"
        f"API candidates: {_STATS['api_candidates']}\n"
        f"On-chain confirmed: {_STATS['confirmed']}\n"        f"Priced this scan: {_STATS['priced']} | losses: {_STATS['losses']}\n"
        f"Above 0.25 modeled: {_STATS['positive']} | not priced: {_STATS['unavailable']}\n"
        f"Private batches this session: {_STATS['alerts']}\n"
        f"Last successful poll: {_STATS['last_poll'] or 'never'}\n"
        f"Last error: {_STATS['last_error'] or 'none'}"
    )


async def scan(context: ContextTypes.DEFAULT_TYPE, *, manual: bool = False) -> list[dict[str, Any]]:
    """Each polling cycle discovers all API candidates and prices a rotating slice.

    Only fresh, coherent indicative >=$0.25 scenarios create priority alerts.
    Scheduled scan reports (including losses) are a separate message type.
    """
    global _LAST_REPORT
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
        _LAST_REPORT = {"rows": [], "valuations": {}, "found": 0,
                        "error": type(exc).__name__}
        return []
    # Alert immediately after on-chain confirmation, even with unknown or
    # negative economics. Pricing is independent and may time out.
    if not manual and positions:
        selected = eligible_to_send(positions)
        if selected:
            # Persist BEFORE Telegram to avoid duplicates after ambiguous
            # delivery timeouts. Failed sends are not automatically retried.
            try:
                mark_sent(selected)
            except (OSError, RuntimeError, ValueError) as exc:
                logger.error("XOXNO alert history not saved; suppress send (%s)",
                             type(exc).__name__)
            else:
                await context.bot.send_message(
                    chat_id=admin_id(), text=alert_text(selected)
                )
                _STATS["alerts"] += 1
    valuations: dict[str, Any] = {}
    if positions:
        try:
            valuations = await asyncio.wait_for(
                asyncio.to_thread(
                    price_candidates, positions, poll=_STATS["scans"] - 1
                ), timeout=110
            )
        except (asyncio.TimeoutError, ValueError, TypeError) as exc:
            _STATS["last_error"] = "Valuation: " + type(exc).__name__
            logger.warning("XOXNO batch pricing unavailable (%s)", type(exc).__name__)
    counts = _scenario_counts(positions, valuations)
    _STATS.update(counts)
    _LAST_REPORT = {"rows": positions, "valuations": valuations,
                    "found": found, "error": _STATS["last_error"]}
    return positions


async def scan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await scan(context)


async def report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled private report includes losses, unknowns and empty results."""
    if not enabled() or admin_id() is None:
        return
    await scan(context, manual=True)
    report = _LAST_REPORT or {"rows": [], "valuations": {}, "found": 0,
                              "error": "No recent scan"}
    await context.bot.send_message(
        chat_id=admin_id(),
        text=scan_report_text(
            report["rows"], report["valuations"],
            discovered=report["found"], error=report["error"]
        ),
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin_private(update) or not update.message:
        return
    if not enabled():
        await update.message.reply_text("XOXNO lending watch is disabled.")
        return
    await scan(context, manual=True)
    snapshot = _LAST_REPORT or {"rows": [], "valuations": {}, "found": 0,
                                "error": "No recent scan"}
    await update.message.reply_text(scan_report_text(
        snapshot["rows"], snapshot["valuations"],
        discovered=snapshot["found"], error=snapshot["error"]
    ))


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
    match = re.search(r"XLEND-18dc6f-[0-9a-f]{1,16}", txt)
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
    from core.hatom_profit import QuoteUnavailable
    identifier = _requested_nft(update, context)
    if identifier is None:
        # Recheck a current API candidate when user does not specify a NFT.
        try:
            rows, _ = await asyncio.wait_for(asyncio.to_thread(inspect), timeout=40)
        except Exception as exc:
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
    app.add_handler(CommandHandler("xoxno_report", scan_command))
    app.add_handler(CommandHandler("xoxno_profit", profit_command))
    if enabled() and admin_id() and app.job_queue:
        app.job_queue.run_repeating(
            scan_job, interval=interval(), first=65,
            name="xoxno_lending_liquidation_private",
        )
        logger.info(
            "XOXNO Lending watcher scheduled | every=%ss | eligibility alerts + manual reports",
            interval(),
        )
    else:
        logger.info("XOXNO Lending read-only watcher disabled")

"""Two-stage Hatom Watch notification gate.

Stage 1: borrower risk indicators -> read-only observation, no automatic alerts.
Stage 2: contract-preflight liquidation eligibility -> PRIVATE alert on every
newly verified liquidatable borrower, regardless of positive/negative/unknown
profit. Batching is rate-limited. Each borrower is notified once ever
while the persistent history remains intact.

All values are on-chain raw amounts; USD estimates are optional and can be
negative or unavailable. Nothing is signed or sent to the blockchain.
All Telegram notifications target ONLY ADMIN_TELEGRAM_ID.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_INITIALIZED = False
_SEEN: dict[str, tuple[str, float]] = {}
_PENDING: dict[str, dict[str, Any]] = {}
_NOTIFIED: dict[str, float] = {}
_LAST_BATCH = 0.0
_MSG_COUNT = 0

# One eligibility batch every 3 minutes when new Stage-2 positions exist.
# One-time per-borrower dedupe, across days and service restarts.
GLOBAL_INTERVAL = 180
PENDING_TTL = 30 * 60


def _file() -> Path:
    return Path(os.getenv("DATA_DIR", "data")) / "hatom_stage_notifications.json"


def _load() -> None:
    global _INITIALIZED, _LAST_BATCH
    with _LOCK:
        if _INITIALIZED:
            return
        _INITIALIZED = True
        try:
            obj = json.loads(_file().read_text(encoding="utf8"))
            if not isinstance(obj, dict):
                return
            now = time.time()
            entries = obj.get("notified", {})
            if isinstance(entries, dict):
                for borrower, ts in entries.items():
                    if isinstance(borrower, str) and borrower.startswith("erd1") and type(ts) in (int, float) and 0 < ts <= now + 300:
                        _NOTIFIED[borrower] = float(ts)
            batch = obj.get("last_batch", 0)
            if isinstance(batch, (int, float)) and 0 <= now - batch <= 86400:
                _LAST_BATCH = float(batch)
        except FileNotFoundError:
            return
        except (OSError, ValueError, TypeError) as exc:
            logger.error("Hatom persisted notification history unreadable (%s); alerts fail closed", type(exc).__name__)
            raise RuntimeError("Hatom notification history unavailable") from exc


def _save() -> None:
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"last_batch": _LAST_BATCH, "notified": _NOTIFIED}), encoding="utf8")
    os.replace(tmp, path)


def observe(rows: list[dict[str, Any]], *, now: float | None = None) -> None:
    """No Telegram here: track risk -> protocol-eligible transitions quietly."""
    _load()
    now = time.time() if now is None else now
    with _LOCK:
        for item in rows:
            borrower = item.get("borrower")
            stage = item.get("category")
            if not isinstance(borrower, str) or not borrower.startswith("erd1"):
                continue
            if stage not in ("ONCHAIN_RISKY", "ONCHAIN_ELIGIBLE"):
                continue
            previous = _SEEN.get(borrower, (None, 0))[0]
            _SEEN[borrower] = (stage, now)
            if stage == "ONCHAIN_RISKY":
                _PENDING.pop(borrower, None)
            elif previous != "ONCHAIN_ELIGIBLE":
                if borrower not in _NOTIFIED:
                    _PENDING[borrower] = dict(item, observed_at=now)
            elif borrower in _PENDING:
                _PENDING[borrower] = dict(item, observed_at=now)

        for borrower, item in list(_PENDING.items()):
            if now - item.get("observed_at", 0) > PENDING_TTL:
                _PENDING.pop(borrower, None)
        for borrower, (_, when) in list(_SEEN.items()):
            if now - when > 24 * 3600:
                _SEEN.pop(borrower, None)


def pending(*, now: float | None = None) -> list[dict[str, Any]]:
    _load()
    now = time.time() if now is None else now
    with _LOCK:
        if now - _LAST_BATCH < GLOBAL_INTERVAL:
            return []
        return [dict(item) for borrower, item in sorted(
            _PENDING.items(), key=lambda pair: pair[1]["observed_at"]
        ) if borrower not in _NOTIFIED
          and now - item["observed_at"] <= PENDING_TTL][:8]


def revalidate(rows: list[dict[str, Any]], *, client: Any = None, max_select: int = 2) -> tuple[list[dict[str, Any]], int]:
    """Confirm significant repayment, collateral seizure and available cash NOW."""
    if not rows:
        return [], 0
    if client is None:
        from core.hatom_onchain import VmClient
        client = VmClient(timeout=10)
    valid: list[dict[str, Any]] = []
    errors = 0
    for row in rows:
        if len(valid) >= max_select:
            break
        try:
            if not client.risky(row["borrower"]):
                continue
            quote = client.meaningful_liquidation_check(
                row["borrow_market"], row["collateral_market"],
                row["borrower"], int(row["raw_borrow"])
            )
            if not quote:
                continue
            valid.append(dict(row, **quote))
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            errors += 1
            logger.warning("Hatom eligibility recheck error (%s)", type(exc).__name__)
        except Exception as exc:
            errors += 1
            logger.warning("Hatom eligibility recheck unavailable (%s)", type(exc).__name__)
    return valid, errors


def format_alert(rows: list[dict[str, Any]], valuations: dict[str, Any] | None = None,
                 *, profit_screened: bool = False) -> str:
    valuations = valuations or {}
    lines = [
        "🚨 HATOM — PRIVATE POSITIVE-SCENARIO ALERT" if profit_screened
        else "🚨 HATOM — PRIVATE PROTOCOL-LIQUIDATION ALERT",
        "Stage 2: protocol liquidation eligibility reconfirmed NOW.",
        "Alert is sent REGARDLESS OF PROFIT: gain, loss or unknown." if not profit_screened
        else "Positive indicative DEX margin, NOT verified execution profit.",
        "Profit is optional indicative information, NOT an execution guarantee.",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines += [
            f"{i}. Borrower: {row['borrower']}",
            f"   Debt market: {row['borrow_market']}",
            f"   Collateral market: {row['collateral_market']}",
            f"   Test repayment: {row['repay_raw']} raw units",
            f"   Seizable hTokens: {row['seized_htokens_raw']} raw units",
            f"   Redeemable collateral: {row['collateral_underlying_raw']} raw units",
        ]
        estimate = valuations.get(row["borrower"])
        if isinstance(estimate, dict) and estimate.get("category") == "INDICATIVE_ONLY":
            from core.hatom_profit import format_scenario
            lines.extend(format_scenario(estimate))
            if profit_screened and estimate.get("profit_alert_screen_passed") is True:
                from core.hatom_profit import _money
                lines.extend([
                    f"   Extra safety buffer: {_money(estimate['safety_buffer_usd'])}",
                    f"   Indicative surplus AFTER buffer: "
                    f"{_money(estimate['screened_surplus_usd'])}",
                    "   Profit remains UNVERIFIED; do not transact from this alert.",
                ])
        elif isinstance(estimate, str):
            lines.append(f"   Price scenario: unavailable ({estimate[:90]})")
        else:
            lines.append("   Price scenario: unavailable (no verified token metadata)")
        lines.append("")
    lines += [
        "NET PROFIT: NOT VERIFIED — no full transaction simulation.",
        "USD values, if present, are reference-price scenarios with ASSUMED costs.",
        "Price source timestamp and exact execution costs are not independently verified.",
        "A subsequent transaction may fail if conditions change.",
        "Read-only. No wallet signature or liquidation executed.",
    ]
    return "\n".join(lines)[:3800]


def mark_delivered(rows: list[dict[str, Any]], *, now: float | None = None) -> None:
    global _LAST_BATCH, _MSG_COUNT
    _load()
    now = time.time() if now is None else now
    with _LOCK:
        _LAST_BATCH = now
        _MSG_COUNT += 1
        for row in rows:
            borrower = row["borrower"]
            _NOTIFIED[borrower] = now
            _PENDING.pop(borrower, None)
        # Persist BEFORE trying Telegram to guarantee at-most-one attempt
        # per borrower, even if the Telegram API call times out ambiguously.
        _save()


def status() -> dict[str, int | float | None]:
    _load()
    with _LOCK:
        return {
            "pending_eligible": len(_PENDING),
            "last_eligible_batch": _LAST_BATCH or None,
            "eligible_batches_this_session": _MSG_COUNT,
        }

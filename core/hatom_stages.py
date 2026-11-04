"""Two-stage Hatom Watch notification gate.

Stage 1: borrower risk indicators -> three scheduled private summaries/day.
Stage 2: nontrivial, contract-preflight liquidation eligibility -> one private
batch per hour at most, with 12-hour per-borrower duplicate suppression.

All values are on-chain raw amounts. NO USD profit is calculated; no actions
are signed or sent. All notifications target ONLY ADMIN_TELEGRAM_ID.
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

# One eligible update/hour, at most 2 candidates/update, same address only
# once/12 hours. Do not send these for unpriced risk-only positions.
GLOBAL_INTERVAL = 3600
BORROWER_COOLDOWN = 12 * 3600
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
                    if isinstance(borrower, str) and borrower.startswith("erd1") and isinstance(ts, (int, float)) and 0 <= now - ts <= 2 * BORROWER_COOLDOWN:
                        _NOTIFIED[borrower] = float(ts)
            batch = obj.get("last_batch", 0)
            if isinstance(batch, (int, float)) and 0 <= now - batch <= 86400:
                _LAST_BATCH = float(batch)
        except FileNotFoundError:
            return
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Hatom stage state read failed (%s); safety gate retained", type(exc).__name__)


def _save() -> None:
    path = _file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"last_batch": _LAST_BATCH, "notified": _NOTIFIED}), encoding="utf8")
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("Hatom stage state save failed (%s)", type(exc).__name__)


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
                if now - _NOTIFIED.get(borrower, -1e12) >= BORROWER_COOLDOWN:
                    _PENDING[borrower] = dict(item, observed_at=now)
            elif borrower in _PENDING:
                _PENDING[borrower] = dict(item, observed_at=now)

        for borrower, item in list(_PENDING.items()):
            if now - item.get("observed_at", 0) > PENDING_TTL:
                _PENDING.pop(borrower, None)
        for borrower, (_, when) in list(_SEEN.items()):
            if now - when > 24 * 3600:
                _SEEN.pop(borrower, None)
        for borrower, when in list(_NOTIFIED.items()):
            if now - when > 2 * BORROWER_COOLDOWN:
                _NOTIFIED.pop(borrower, None)


def pending(*, now: float | None = None) -> list[dict[str, Any]]:
    _load()
    now = time.time() if now is None else now
    with _LOCK:
        if now - _LAST_BATCH < GLOBAL_INTERVAL:
            return []
        return [dict(item) for _, item in sorted(
            _PENDING.items(), key=lambda pair: pair[1]["observed_at"], reverse=True
        ) if now - item["observed_at"] <= PENDING_TTL][:8]


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


def format_alert(rows: list[dict[str, Any]]) -> str:
    lines = [
        "🚨 HATOM — PRIVATE PROTOCOL-LIQUIDATION ALERT",
        "Stage 2: protocol liquidation eligibility reconfirmed NOW.",
        "Not a net-profit quote or execution guarantee.",
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
            "",
        ]
    lines += [
        "Profit net: NOT VERIFIED (token decimals/prices/DEX swap/gas/slippage).",
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
        _save()


def status() -> dict[str, int | float | None]:
    _load()
    with _LOCK:
        return {
            "pending_eligible": len(_PENDING),
            "last_eligible_batch": _LAST_BATCH or None,
            "eligible_batches_this_session": _MSG_COUNT,
        }

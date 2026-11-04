"""Private, low-frequency Hatom risk reports; never mislabel risk as profit.

Only on-chain candidates are eligible for automatic private digests. A fresh
read-only contract recheck precedes every report. Reporting is NOT liquidation
execution, and actual net profit is not computed.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
BERLIN = ZoneInfo("Europe/Berlin")
_RISK_CACHE: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()
_LAST_REPORT: float | None = None
_SINCE_START = 0
_TOTAL_CHECKS = 0
_LOADED_DATA_DIR: str | None = None


def _cache_path() -> Path | None:
    # Explicit DATA_DIR must be on a persistent Railway volume.
    root = os.getenv("DATA_DIR", "").strip()
    return Path(root) / "hatom_candidates.json" if root else None


def _load_cached() -> None:
    """Called under _LOCK. Cached positions are untrusted until rechecked on-chain."""
    global _LOADED_DATA_DIR
    path = _cache_path()
    if path is None or _LOADED_DATA_DIR == str(path):
        return
    _LOADED_DATA_DIR = str(path)
    try:
        if path.stat().st_size > 300_000:
            raise ValueError("Hatom cache unexpectedly large")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("candidates"), list):
            raise ValueError("Invalid Hatom cache format")
        from core.hatom_onchain import address_decode
        now = time.time()
        for item in raw["candidates"][:500]:
            if not isinstance(item, dict):
                continue
            try:
                borrower = str(item["borrower"])
                debt = str(item["borrow_market"])
                collateral = str(item["collateral_market"])
                address_decode(borrower)
                address_decode(debt)
                address_decode(collateral)
                observed = float(item["observed_at"])
                amount = int(str(item["raw_borrow"]))
                category = item["category"]
                if category not in ("ONCHAIN_ELIGIBLE", "ONCHAIN_RISKY"):
                    continue
                if not 0 <= now - observed <= 12 * 3600:
                    continue
                if amount <= 0 or amount > 10**80:
                    continue
                _RISK_CACHE[borrower] = {
                    "borrower": borrower, "borrow_market": debt,
                    "collateral_market": collateral, "raw_borrow": str(amount),
                    "category": category, "observed_at": observed,
                    "routes_seen": 1,
                }
            except (ValueError, TypeError, KeyError):
                continue
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Hatom position cache unreadable (%s)", type(exc).__name__)


def _save_cached() -> None:
    """Best-effort private persistence of public chain addresses, no credentials."""
    path = _cache_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"candidates": list(_RISK_CACHE.values())[:500]}
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        os.replace(temp, path)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("Hatom position cache write failed (%s)", type(exc).__name__)


def digest_hours() -> list[int]:
    """Default 09:00, 15:00 and 21:00 Berlin. Never more than 4/day."""
    raw = os.getenv("HATOM_DIGEST_HOURS_BERLIN", "9,15,21")
    try:
        hours = sorted(set(int(part.strip()) for part in raw.split(",")))
        if not hours or len(hours) > 4 or any(hour < 0 or hour > 23 for hour in hours):
            raise ValueError("Invalid digest hours")
        if any(hours[i+1] - hours[i] < 2 for i in range(len(hours)-1)):
            raise ValueError("Digest hours must be at least 2 hours apart")
        if len(hours) > 1 and 24 - hours[-1] + hours[0] < 2:
            raise ValueError("Digest hours must be at least 2 hours apart")
        return hours
    except ValueError:
        logger.warning("Hatom digest hours invalid; defaulting to 09,15,21 Berlin")
        return [9, 15, 21]


def store_scan(rows: list[dict[str, Any]], *, now: float | None = None, checked: int = 0) -> None:
    """Store 1 candidate per borrower, not 1 message per borrow/collateral pair."""
    global _SINCE_START, _TOTAL_CHECKS
    now = time.time() if now is None else now
    with _LOCK:
        _load_cached()
        _SINCE_START += 1
        _TOTAL_CHECKS += max(0, checked)
        for row in rows:
            if row.get("category") not in ("ONCHAIN_RISKY", "ONCHAIN_ELIGIBLE"):
                continue
            borrower = row.get("borrower")
            if not isinstance(borrower, str) or not borrower.startswith("erd1"):
                continue
            if not row.get("borrow_market") or not row.get("collateral_market"):
                continue
            old = _RISK_CACHE.get(borrower)
            same_poll = bool(old and now - old["observed_at"] < 2)
            _RISK_CACHE[borrower] = {
                "borrower": borrower,
                "category": row["category"],
                "raw_borrow": row.get("raw_borrow", "0"),
                "borrow_market": row["borrow_market"],
                "collateral_market": row["collateral_market"],
                "observed_at": now,
                "routes_seen": min(99, (old["routes_seen"] + 1) if same_poll else 1),
            }
        for borrower, row in list(_RISK_CACHE.items()):
            if now - row["observed_at"] > 24 * 3600:
                _RISK_CACHE.pop(borrower, None)
        if len(_RISK_CACHE) > 1000:
            for borrower, row in sorted(_RISK_CACHE.items(), key=lambda x: x[1]["observed_at"])[:len(_RISK_CACHE)-1000]:
                _RISK_CACHE.pop(borrower, None)
        _save_cached()


def state_snapshot(*, now: float | None = None, window_seconds: int = 12 * 3600) -> dict[str, Any]:
    now = time.time() if now is None else now
    with _LOCK:
        _load_cached()
        candidates = [
            dict(row) for row in _RISK_CACHE.values()
            if 0 <= now - row["observed_at"] <= window_seconds
        ]
        return {
            "candidates": sorted(candidates, key=lambda row: -row["observed_at"]),
            "scans": _SINCE_START,
            "checks": _TOTAL_CHECKS,
            "last_report": _LAST_REPORT,
        }


def recheck(rows: list[dict[str, Any]], *, client: Any = None, max_check: int = 7,
            max_show: int = 3) -> tuple[list[dict[str, Any]], int]:
    """Fresh controller risk recheck; only promote to stage 2 after repay preflight."""
    if not rows:
        return [], 0
    if client is None:
        from core.hatom_onchain import VmClient
        client = VmClient(timeout=10)
    confirmed: list[dict[str, Any]] = []
    errors = 0
    for row in rows[:max_check]:
        try:
            if not client.risky(row["borrower"]):
                continue
            current = dict(row)
            if row.get("category") == "ONCHAIN_ELIGIBLE":
                quote = client.meaningful_liquidation_check(
                    row["borrow_market"], row["collateral_market"], row["borrower"],
                    int(row["raw_borrow"])
                )
                if not quote:
                    current["category"] = "ONCHAIN_RISKY"
                else:
                    current.update(quote)
            else:
                current["category"] = "ONCHAIN_RISKY"
            confirmed.append(current)
            if len(confirmed) >= max_show:
                break
        except Exception as exc:
            errors += 1
            logger.warning("Hatom digest live risk check failed (%s)", type(exc).__name__)
    return confirmed, errors


def build_report(rows: list[dict[str, Any]], *, now: float | None = None,
                 verified: list[dict[str, Any]] | None = None, errors: int = 0,
                 scans: int = 0, checks: int = 0) -> str:
    """Private risk overview. Stage-2 candidates are not necessarily profitable."""
    now = time.time() if now is None else now
    current = datetime.fromtimestamp(now, BERLIN).strftime("%d %b %Y %H:%M")
    verified = verified or []
    stage2 = [row for row in verified if row.get("category") == "ONCHAIN_ELIGIBLE"]
    risk_only = [row for row in verified if row.get("category") != "ONCHAIN_ELIGIBLE"]
    text = [
        "🔐 Hatom Watch — PRIVATE RISK DIGEST",
        f"🕒 {current} (Berlin)",
        "",
        "Scan mode: READ-ONLY",
        f"Scans this session: {scans} | wallet checks: {checks}",
        f"Unique risk wallets observed in last 12h: {len(rows)}",
        f"Currently reconfirmed risk-only: {len(risk_only)}",
        f"Currently reconfirmed protocol-eligible: {len(stage2)}",
    ]
    if risk_only:
        text.extend(["", "🟡 STAGE 1 — AT RISK (execution not verified):"])
        for index, row in enumerate(risk_only[:3], 1):
            text.append(f"{index}. {row['borrower']}")
    if stage2:
        text.extend(["", "🟠 STAGE 2 — LIQUIDATION PRECHECK PASSED (NOT PROFIT):"])
        for index, row in enumerate(stage2[:3], 1):
            text.extend([
                f"{index}. {row['borrower']}",
                f"   Debt market: {row['borrow_market']}",
                f"   Collateral market: {row['collateral_market']}",
            ])
    if errors:
        text.append(f"Failed fresh checks (excluded): {errors}")
    text.extend([
        "",
        "💰 Profit-positive liquidations: NOT VERIFIED",
        "Stage 2 means Hatom's contract allows a meaningful test repayment,",
        "with nonzero redeemable collateral and reported market cash.",
        "USD net profit, execution gas, swap prices and slippage remain unknown.",
        "No automatic transactions. No private keys.",
    ])
    return "\n".join(text)[:3800]


def mark_report_sent(*, now: float | None = None) -> None:
    global _LAST_REPORT
    with _LOCK:
        _LAST_REPORT = time.time() if now is None else now

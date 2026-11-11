"""Liquidity-only monitoring for the legacy OneDex WOODY/BOBER pair."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import multiversx as m


def test_onedex_bober_public_quote_verifies_exact_pair_and_tokens():
    expected_pair = m.ONEDEX_POOL_ADDRESS + "-WOODYBOBER-1a1703"
    payload = {"pairs": [
        {
            "chainId": "multiversx",
            "dexId": "onedex",
            "pairAddress": expected_pair,
            "baseToken": {"address": m.WOODY},
            "quoteToken": {"address": m.BOBER},
            "liquidity": {"base": 58447, "quote": 57006},
        },
        {
            "chainId": "multiversx",
            "dexId": "otherdex",
            "pairAddress": expected_pair,
            "baseToken": {"address": m.WOODY},
            "quoteToken": {"address": m.BOBER},
            "liquidity": {"base": 1, "quote": 1},
        },
    ]}
    with patch.object(m, "get_json", return_value=payload):
        result = m.get_onedex_woody_bober_public_quote()

    assert result["ok"] is True
    assert result["woody_amount"] == 58447
    assert result["pair_amount"] == 57006
    assert result["pair_token"] == m.BOBER
    assert "indicative" in result["reserve_source"]


def test_onedex_bober_quote_fails_closed_on_mismatched_pair():
    with patch.object(m, "get_json", return_value={"pairs": [{
        "chainId": "multiversx",
        "dexId": "onedex",
        "pairAddress": m.ONEDEX_POOL_ADDRESS + "-OTHER-000000",
        "baseToken": {"address": m.WOODY},
        "quoteToken": {"address": m.BOBER},
        "liquidity": {"base": 100, "quote": 100},
    }]}):
        result = m.get_onedex_woody_bober_public_quote()

    assert result["ok"] is False
    assert "not uniquely verified" in result["reason"]


def test_liquidity_monitor_includes_excluded_bober_pool_without_reclassifying_it():
    monitor_pool = {
        "dex": "OneDex",
        "name": "WOODY/BOBER",
        "pair_address": m.ONEDEX_POOL_ADDRESS,
        "lp_token": "WOODYBOBER-1a1703",
        "quote_token": m.BOBER,
        "status": "excluded",
        "monitor_liquidity": True,
    }
    snapshot = {
        "ok": True,
        "woody_amount": 100,
        "pair_amount": 80,
        "pair_symbol": "BOBER",
        "reserve_source": "DexScreener public indexer (indicative; not on-chain verified)",
    }
    with patch.object(m, "LP_POOLS", [monitor_pool]), patch.object(
        m, "get_configured_pool_snapshot", return_value=snapshot
    ):
        rows = m._fetch_public_pool_reserves()

    assert len(rows) == 1
    assert rows[0]["pair"] == "WOODY/BOBER"
    assert rows[0]["monitorOnly"] is True
    assert "DexScreener" in rows[0]["reserveSource"]

    with patch.object(m, "LP_POOLS", [monitor_pool]), patch.object(
        m, "get_lp_holders"
    ) as get_holders:
        global_snapshot = m.build_global_snapshot()

    assert global_snapshot["pools"][0]["status_text"] == "excluded"
    get_holders.assert_not_called()


def test_one_dex_bober_indexer_quote_is_blocked_from_verified_calculations():
    pool = {
        "dex": "OneDex",
        "name": "WOODY/BOBER",
        "pair_address": m.ONEDEX_POOL_ADDRESS,
        "lp_token": "WOODYBOBER-1a1703",
        "status": "excluded",
        "monitor_liquidity": True,
    }
    with patch.object(m, "get_onedex_woody_bober_public_quote") as quote:
        result = m.get_configured_pool_snapshot(pool, allow_indexer_fallback=False)

    assert result["ok"] is False
    assert "not allowed" in result["reason"]
    quote.assert_not_called()


def test_liquidity_report_marks_bober_as_indexer_estimate():
    row = {
        "dex": "OneDex",
        "pair": "WOODY/BOBER",
        "woodyReserve": 100,
        "quoteReserve": 80,
        "quoteSymbol": "BOBER",
        "reserveSource": "DexScreener public indexer (indicative; not on-chain verified)",
        "monitorOnly": True,
    }
    with patch.object(m, "get_best_price", return_value={"price_usd": 0.001}), patch.object(
        m, "get_public_pool_reserves", return_value=[row]
    ):
        report = m.get_liquidity_text()

    assert "OneDex · WOODY/BOBER" in report
    assert "indexer estimate" in report

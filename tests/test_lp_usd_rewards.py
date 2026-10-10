"""LP reward fairness: USD values are comparable; raw LP amounts are not."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import multiversx as m


def test_mixed_pool_lp_units_do_not_control_rewards():
    snap = {"valuation_complete": True, "total_eligible_usd": 300.0,
            "holders": [
                {"wallet": "erd1a", "lp_amount": 1000000, "estimated_usd": 100},
                {"wallet": "erd1b", "lp_amount": 1, "estimated_usd": 200},
            ]}
    with patch.object(m, "get_month_lp_snapshots", return_value=[snap]):
        result = m.calculate_monthly_lp_rewards(3)
    rewards = {row["wallet"]: row["reward_egld"] for row in result["rows"]}
    assert rewards["erd1a"] == 1
    assert rewards["erd1b"] == 2


def test_incomplete_snapshots_withhold_rewards():
    snaps = [{"holders": [{"wallet": "erd1a", "lp_amount": 99999,
                            "estimated_egld": 50}]}]
    with patch.object(m, "get_month_lp_snapshots", return_value=snaps):
        result = m.calculate_monthly_lp_rewards(5)
    assert result["rows"] == []
    assert result["valuation_complete"] is False


def test_absent_wallet_counts_zero_across_snapshots():
    snaps = [
        {"valuation_complete": True, "total_eligible_usd": 100,
         "holders": [{"wallet": "erd1a", "estimated_usd": 100}]},
        {"valuation_complete": True, "total_eligible_usd": 100,
         "holders": [{"wallet": "erd1b", "estimated_usd": 100}]},
    ]
    with patch.object(m, "get_month_lp_snapshots", return_value=snaps):
        result = m.calculate_monthly_lp_averages()
    assert [r["average_usd"] for r in result["rows"]] == [50, 50]


def test_global_valuation_requires_quote_usd_price():
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/JEX"}
    holder_data = {"ok": True, "pool_value_egld": 20,
                   "holders": [{"wallet": "erd1wallet", "estimated_egld": 10}]}
    snap = {"ok": True, "woody_amount": 1000, "pair_amount": 100,
            "pair_token": "JEX-123", "pair_symbol": "JEX"}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_egld_usd", return_value=10), \
         patch.object(m, "get_best_price", return_value={"price_usd": 0.01, "source": "test"}), \
         patch.object(m, "get_lp_holders", return_value=holder_data), \
         patch.object(m, "get_pool_snapshot", return_value=snap):
        result = m.build_global_usd_valuation()
    assert result["valuation_complete"] is False
    assert result["pools"][0]["status"] == "unverified"
    assert result["total_eligible_usd"] == 0


def test_global_valuation_sums_independent_token_legs():
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/EGLD"}
    holder_data = {"ok": True, "pool_value_egld": 40,
                   "holders": [{"wallet": "erd1wallet", "estimated_egld": 10}]}
    snap = {"ok": True, "woody_amount": 1000, "pair_amount": 20,
            "pair_token": m.WEGLD, "pair_symbol": "WEGLD"}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_egld_usd", return_value=10), \
         patch.object(m, "get_best_price", return_value={"price_usd": 0.01, "source": "test"}), \
         patch.object(m, "get_lp_holders", return_value=holder_data), \
         patch.object(m, "get_pool_snapshot", return_value=snap):
        result = m.build_global_usd_valuation()
    assert result["valuation_complete"] is True
    assert result["pools"][0]["pool_value_usd"] == 210
    assert result["holders"][0]["estimated_usd"] == 52.5

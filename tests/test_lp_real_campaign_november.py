"""Regression tests for the REAL WOODY LP campaign start on 15 Nov 2026."""
import os
from unittest.mock import patch

from core import multiversx as m


def _snapshot(date, alice=100, bob=300):
    return {
        "date": date,
        "valuation_complete": True,
        "indicative_only": True,
        "reward_valuation_model": "woody_reserve_ratio_estimate_v1",
        "pools": [{"status": "verified", "quote_price_confidence": "indicative"}],
        "holders": [
            {"wallet": "erd1alice", "estimated_usd": alice},
            {"wallet": "erd1bob", "estimated_usd": bob},
        ],
        "total_eligible_usd": alice + bob,
    }


def test_november_first_campaign_only_needs_15th_and_final_day():
    with patch.dict(os.environ, {"LP_REWARD_CAMPAIGN_START_DATE": "2026-11-15"}):
        assert m.required_month_lp_snapshot_dates("2026-10") == []
        assert m.required_month_lp_snapshot_dates("2026-11") == [
            "2026-11-15", "2026-11-30"
        ]
        assert m.required_month_lp_snapshot_dates("2026-12") == [
            "2026-12-01", "2026-12-15", "2026-12-31"
        ]


def test_november_has_no_payout_before_final_snapshot():
    with (
        patch.dict(os.environ, {"LP_REWARD_CAMPAIGN_START_DATE": "2026-11-15"}),
        patch.object(m, "get_month_lp_usd_snapshots",
                     return_value=[_snapshot("2026-11-15")]),
    ):
        results = m.calculate_monthly_lp_rewards(3, "2026-11")
    assert results["valuation_complete"] is False
    assert results["missing_dates"] == ["2026-11-30"]
    assert results["rows"] == []


def test_november_reward_share_uses_only_end_of_month_usd():
    snapshots = [
        _snapshot("2026-11-15", alice=100, bob=300),
        _snapshot("2026-11-30", alice=300, bob=100),
    ]
    with (
        patch.dict(os.environ, {"LP_REWARD_CAMPAIGN_START_DATE": "2026-11-15"}),
        patch.object(m, "get_month_lp_usd_snapshots", return_value=snapshots),
    ):
        results = m.calculate_monthly_lp_rewards(4, "2026-11")
    assert results["valuation_complete"] is True
    assert results["reward_snapshot_date"] == "2026-11-30"
    rewards = {row["wallet"]: row["reward_egld"] for row in results["rows"]}
    assert rewards == {"erd1alice": 3.0, "erd1bob": 1.0}


def test_pre_campaign_snapshots_cannot_generate_egld_rewards():
    old_snapshots = [
        _snapshot("2026-10-01"),
        _snapshot("2026-10-15"),
        _snapshot("2026-10-31"),
    ]
    with (
        patch.dict(os.environ, {"LP_REWARD_CAMPAIGN_START_DATE": "2026-11-15"}),
        patch.object(m, "get_month_lp_usd_snapshots", return_value=old_snapshots),
    ):
        results = m.calculate_monthly_lp_rewards(3, "2026-10")
    assert results["valuation_complete"] is False
    assert results["rows"] == []

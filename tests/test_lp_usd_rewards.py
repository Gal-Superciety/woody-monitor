"""LP reward fairness: USD values are comparable; raw LP amounts are not."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import multiversx as m


def test_mixed_pool_lp_units_do_not_control_rewards():
    snap = {"valuation_complete": True, "total_eligible_usd": 300.0, "pools": [{"status": "verified"}],
            "holders": [
                {"wallet": "erd1a", "lp_amount": 1000000, "estimated_usd": 100},
                {"wallet": "erd1b", "lp_amount": 1, "estimated_usd": 200},
            ]}
    with patch.object(m, "get_month_lp_usd_snapshots", return_value=[dict(snap, date=date) for date in ("2026-09-01", "2026-09-15", "2026-09-30")]), \
         patch.object(m, "current_month_key", return_value="2026-09"):
        result = m.calculate_monthly_lp_rewards(3)
    rewards = {row["wallet"]: row["reward_egld"] for row in result["rows"]}
    assert rewards["erd1a"] == 1
    assert rewards["erd1b"] == 2


def test_incomplete_snapshots_withhold_rewards():
    snaps = [{"holders": [{"wallet": "erd1a", "lp_amount": 99999,
                            "estimated_egld": 50}]}]
    with patch.object(m, "get_month_lp_usd_snapshots", return_value=snaps):
        result = m.calculate_monthly_lp_rewards(5)
    assert result["rows"] == []
    assert result["valuation_complete"] is False


def test_absent_wallet_counts_zero_across_snapshots():
    snaps = [
        {"valuation_complete": True, "total_eligible_usd": 100, "pools": [{"status": "verified"}],
         "holders": [{"wallet": "erd1a", "estimated_usd": 100}]},
        {"valuation_complete": True, "total_eligible_usd": 100, "pools": [{"status": "verified"}],
         "holders": [{"wallet": "erd1b", "estimated_usd": 100}]},
    ]
    with patch.object(m, "get_month_lp_usd_snapshots", return_value=[dict(snaps[0], date="2026-09-01"), dict(snaps[1], date="2026-09-15"), dict(snaps[1], date="2026-09-30")]), \
         patch.object(m, "current_month_key", return_value="2026-09"):
        result = m.calculate_monthly_lp_averages()
    assert [round(r["average_usd"], 6) for r in result["rows"]] == [66.666667, 33.333333]


def test_global_valuation_requires_quote_usd_price():
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/JEX", "quote_token": "JEX-123"}
    holder_data = {"ok": True, "pool_value_egld": 20, "total_supply_raw": "1000",
                   "holders": [{"wallet": "erd1wallet", "balance_raw": "500", "estimated_egld": 10}]}
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
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/EGLD", "quote_token": m.WEGLD}
    holder_data = {"ok": True, "pool_value_egld": 40, "total_supply_raw": "1000",
                   "holders": [{"wallet": "erd1wallet", "balance_raw": "250", "estimated_egld": 10}]}
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


def test_exact_quote_token_metadata():
    with patch.object(m, "get_token_metadata", return_value={
        "identifier": "JEX-abc123", "price": 0.0123
    }):
        result = m.get_verified_quote_usd("JEX-abc123", 12)
        assert result["ok"] is True
        assert result["price_usd"] == 0.0123
        assert result["confidence"] == "indicative"
        assert m.get_verified_quote_usd("BOBER-xyz", 12)["ok"] is False


def test_global_usd_snapshot_never_saves_partial():
    from datetime import datetime, timezone
    fixed = datetime(2026, 10, 15, tzinfo=timezone.utc)
    with patch.object(m, "datetime") as clock, \
         patch.object(m, "read_json_file", return_value={"snapshots": []}), \
         patch.object(m, "build_global_usd_valuation",
                      return_value={"valuation_complete": False, "pools": []}), \
         patch.object(m, "write_json_file") as write:
        clock.now.return_value = fixed
        result = m.save_global_usd_snapshot(
            force=True, snapshot_time=fixed)
    assert result["ok"] is False
    write.assert_not_called()


def test_global_usd_snapshot_persists_verified_data():
    from datetime import datetime, timezone
    fixed = datetime(2026, 10, 15, tzinfo=timezone.utc)
    valuation = {"valuation_complete": True, "holders": [
        {"wallet": "erd1a", "estimated_usd": 100}],
        "total_eligible_usd": 100, "pools": [{"status": "verified"}]}
    with patch.object(m, "datetime") as clock, \
         patch.object(m, "read_json_file", return_value={"snapshots": []}), \
         patch.object(m, "build_global_usd_valuation", return_value=valuation), \
         patch.object(m, "write_json_file", return_value=True) as write:
        clock.now.return_value = fixed
        result = m.save_global_usd_snapshot(
            force=True, snapshot_time=fixed)
    assert result["ok"] is True
    assert write.call_args.args[1]["snapshots"][0]["date"] == "2026-10-15"


def test_usd_snapshot_rejects_mismatched_holder_totals():
    snap = {"valuation_complete": True, "total_eligible_usd": 100,
            "pools": [{"status": "verified"}],
            "holders": [{"wallet": "erd1a", "estimated_usd": 99}]}
    assert m.is_valid_global_usd_snapshot(snap) is False


def test_usd_snapshot_rejects_duplicate_wallets():
    snap = {"valuation_complete": True, "total_eligible_usd": 100,
            "pools": [{"status": "verified"}],
            "holders": [{"wallet": "erd1a", "estimated_usd": 50},
                        {"wallet": "erd1a", "estimated_usd": 50}]}
    assert m.is_valid_global_usd_snapshot(snap) is False


def test_rewards_withheld_if_month_has_only_two_checkpoints():
    snap = {"valuation_complete": True, "total_eligible_usd": 100,
            "pools": [{"status": "verified"}],
            "holders": [{"wallet": "erd1a", "estimated_usd": 100}]}
    records = [dict(snap, date=date) for date in ("2026-09-01", "2026-09-15")]
    with patch.object(m, "get_month_lp_usd_snapshots", return_value=records), \
         patch.object(m, "current_month_key", return_value="2026-09"):
        result = m.calculate_monthly_lp_rewards(5)
    assert result["rows"] == []
    assert result["missing_dates"] == ["2026-09-30"]


def test_rewards_withheld_if_duplicate_checkpoint():
    snap = {"valuation_complete": True, "total_eligible_usd": 100,
            "pools": [{"status": "verified"}],
            "holders": [{"wallet": "erd1a", "estimated_usd": 100}]}
    records = [dict(snap, date=date) for date in
               ("2026-09-01", "2026-09-15", "2026-09-15", "2026-09-30")]
    with patch.object(m, "get_month_lp_usd_snapshots", return_value=records), \
         patch.object(m, "current_month_key", return_value="2026-09"):
        result = m.calculate_monthly_lp_rewards(5)
    assert result["rows"] == []


def test_global_usd_lp_holders_do_not_require_egld_tvl():
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/EGLD", "quote_token": m.WEGLD}
    holder_data = {"ok": True, "total_supply_raw": "1000",
                   "holders": [{"wallet": "erd1wallet", "balance_raw": "250"}]}
    snap = {"ok": True, "woody_amount": 1000, "pair_amount": 20,
            "pair_token": m.WEGLD}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_egld_usd", return_value=10), \
         patch.object(m, "get_best_price", return_value={"price_usd": 0.01}), \
         patch.object(m, "get_lp_holders", return_value=holder_data) as holders, \
         patch.object(m, "get_pool_snapshot", return_value=snap):
        result = m.build_global_usd_valuation()
    holders.assert_called_once_with(pool, require_tvl=False)
    assert result["valuation_complete"] is True
    assert result["holders"][0]["estimated_usd"] == 52.5


def test_lp_holders_reject_supply_exceeded_without_tvl():
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/JEX", "quote_token": "JEX-123"}
    with patch.object(m, "discover_pool_lp_token", return_value="LP-abc"), \
         patch.object(m, "get_lp_total_supply_raw_and_decimals", return_value=(100, 0)), \
         patch.object(m, "get_json", return_value=[
             {"address": "erd1wallet", "balance": "150"}]), \
         patch.object(m, "get_pool_tvl_egld") as tvl:
        result = m.get_lp_holders(pool, require_tvl=False)
    assert result["ok"] is False
    assert "exceed" in result["reason"]
    tvl.assert_not_called()


def test_metadata_quote_produces_indicative_not_reward_eligible_valuation():
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/JEX", "quote_token": "JEX-abc123"}
    holder_data = {"ok": True, "total_supply_raw": "1000",
                   "holders": [{"wallet": "erd1wallet", "balance_raw": "250"}]}
    snap = {"ok": True, "woody_amount": 1000, "pair_amount": 100,
            "pair_token": "JEX-abc123"}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_egld_usd", return_value=10), \
         patch.object(m, "get_best_price", return_value={"price_usd": 0.01}), \
         patch.object(m, "get_lp_holders", return_value=holder_data), \
         patch.object(m, "get_pool_snapshot", return_value=snap), \
         patch.object(m, "get_token_metadata", return_value={
             "identifier": "JEX-abc123", "price": 0.5}):
        result = m.build_global_usd_valuation()
    assert result["holders"][0]["estimated_usd"] == 15
    assert result["indicative_only"] is True
    assert result["valuation_complete"] is False
    assert result["pools"][0]["quote_price_confidence"] == "indicative"


def test_backdated_live_snapshot_is_rejected_before_api_reads():
    from datetime import datetime, timedelta, timezone
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    with patch.object(m, "build_global_usd_valuation") as valuation:
        result = m.save_global_usd_snapshot(force=True, snapshot_time=yesterday)
    assert result["ok"] is False
    assert "historical" in result["reason"]
    valuation.assert_not_called()


def test_off_schedule_manual_snapshot_cannot_become_reward_checkpoint():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if m.is_lp_snapshot_day(now):
        return
    with patch.object(m, "read_json_file", return_value={"snapshots": []}), \
         patch.object(m, "build_global_usd_valuation", return_value={
             "valuation_complete": True, "total_eligible_usd": 10,
             "pools": [{"status": "verified"}],
             "holders": [{"wallet": "erd1wallet", "estimated_usd": 10}]}), \
         patch.object(m, "write_json_file") as write:
        result = m.save_global_usd_snapshot(force=True, snapshot_time=now)
    assert result["ok"] is False
    write.assert_not_called()


def test_indicative_snapshot_is_rejected_even_if_marked_complete():
    snap = {"valuation_complete": True, "indicative_only": True,
            "total_eligible_usd": 10,
            "pools": [{"status": "verified", "quote_price_confidence": "indicative"}],
            "holders": [{"wallet": "erd1wallet", "estimated_usd": 10}]}
    assert m.is_valid_global_usd_snapshot(snap) is False


def test_indicative_pool_provenance_is_rejected_even_without_top_level_flag():
    snap = {"valuation_complete": True, "total_eligible_usd": 10,
            "pools": [{"status": "verified", "quote_price_confidence": "indicative"}],
            "holders": [{"wallet": "erd1wallet", "estimated_usd": 10}]}
    assert m.is_valid_global_usd_snapshot(snap) is False


def test_pool_quote_token_mismatch_blocks_usd_valuation():
    pool = {"status": "active", "pair_address": "erd1pair",
            "name": "WOODY/JEX", "quote_token": "JEX-expected"}
    holder_data = {"ok": True, "total_supply_raw": "1000",
                   "holders": [{"wallet": "erd1wallet", "balance_raw": "250"}]}
    snap = {"ok": True, "woody_amount": 1000, "pair_amount": 100,
            "pair_token": "JEX-different"}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_egld_usd", return_value=10), \
         patch.object(m, "get_best_price", return_value={"price_usd": 0.01}), \
         patch.object(m, "get_lp_holders", return_value=holder_data), \
         patch.object(m, "get_pool_snapshot", return_value=snap), \
         patch.object(m, "get_verified_quote_usd") as quote:
        result = m.build_global_usd_valuation()
    assert result["valuation_complete"] is False
    assert result["total_eligible_usd"] == 0
    assert result["pools"][0]["status"] == "unverified"
    quote.assert_not_called()


def test_unverified_pool_is_not_eligible():
    with patch.object(m, "LP_POOLS", [{"status": "unverified", "name": "WOODY/ONE"}]), patch.object(m, "get_egld_usd", return_value=10), patch.object(m, "get_best_price", return_value={"price_usd": 0.01}):
        result = m.build_global_usd_valuation()
    assert result["valuation_complete"] is False
    assert result["pools"][0]["status"] == "unverified"


def test_duplicate_lp_holder_address_is_rejected():
    pool = {"status": "active", "pair_address": "erd1pair", "name": "WOODY/EGLD"}
    with patch.object(m, "discover_pool_lp_token", return_value="LP-abc"), \
         patch.object(m, "get_lp_total_supply_raw_and_decimals", return_value=(1000, 0)), \
         patch.object(m, "get_json", return_value=[
             {"address": "erd1wallet", "balance": "100"},
             {"address": "erd1wallet", "balance": "100"}]):
        result = m.get_lp_holders(pool, require_tvl=False)
    assert result["ok"] is False
    assert "Duplicate" in result["reason"]

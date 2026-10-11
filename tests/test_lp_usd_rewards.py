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


def test_missing_quote_price_is_derived_from_exact_pool_reserves():
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
    assert result["pools"][0]["status"] == "verified"
    assert result["pools"][0]["quote_usd"] == 0.1
    assert result["total_eligible_usd"] == 10


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
    assert result["holders"][0]["estimated_usd"] == 5
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


def test_live_lp_leaderboard_is_labeled_estimated_and_never_promises_rewards():
    ownership = {"holders": [{"wallet": "erd1alice", "pools": [
        {"pool": "xExchange WOODY/EGLD", "lp_amount": 2.5}]}],
        "pools": [{"label": "xExchange WOODY/EGLD", "status": "readable"}]}
    valuation = {"holders": [{"wallet": "erd1alice", "estimated_usd": 125.50,
                               "pools": [{"pool": "xExchange WOODY/EGLD",
                                          "estimated_usd": 125.50}]}],
                "pools": [{"label": "xExchange WOODY/EGLD", "status": "verified"}]}
    with patch.object(m, "LP_POOLS", [{"status": "active"}]), \
         patch.object(m, "build_live_lp_ownership", return_value=ownership), \
         patch.object(m, "build_global_usd_valuation", return_value=valuation), \
         patch.object(m, "calculate_monthly_lp_averages", side_effect=AssertionError("monthly called")):
        report = m.get_lp_leaderboard_text()
    assert "LP Leaderboard" in report
    assert "~$125.50" in report
    assert "1 pool" in report
    assert "xExchange WOODY/EGLD:" not in report
    assert "2.500000 LP" not in report
    assert "Estimated reward:" not in report


def test_live_lp_leaderboard_marks_partial_values_and_does_not_rank_them():
    ownership = {
        "holders": [
            {"wallet": "erd1complete", "pools": [{"pool": "JEX WOODY/OLV"}]},
            {"wallet": "erd1partial", "pools": [
                {"pool": "JEX WOODY/OLV"},
                {"pool": "OneDex WOODY/ONE"}]},
        ],
        "pools": [{"label": "JEX WOODY/OLV", "status": "readable"},
                  {"label": "OneDex WOODY/ONE", "status": "readable"}],
    }
    valuation = {
        "holders": [
            {"wallet": "erd1complete", "estimated_usd": 20,
             "pools": [{"pool": "JEX WOODY/OLV", "estimated_usd": 20}]},
            {"wallet": "erd1partial", "estimated_usd": 21,
             "pools": [{"pool": "JEX WOODY/OLV", "estimated_usd": 21}]},
        ],
        "pools": [{"label": "JEX WOODY/OLV", "status": "verified"}],
    }
    with patch.object(m, "LP_POOLS", [{"status": "active"}, {"status": "active"}]), \
         patch.object(m, "build_live_lp_ownership", return_value=ownership), \
         patch.object(m, "build_global_usd_valuation", return_value=valuation):
        report = m.get_lp_leaderboard_text()
    assert "1. `erd1complete` — *~$20.00*" in report
    assert "Partial valuation" in report
    assert "• `erd1partial` — *≥ ~$21.00*" in report
    assert "2. `erd1partial`" not in report


def test_live_lp_leaderboard_never_invents_wallets_from_pool_estimates():
    ownership = {"holders": [], "pools": [
        {"label": "JEX WOODY/OLV", "status": "readable"}]}
    with patch.object(m, "build_live_lp_ownership", return_value=ownership), \
         patch.object(m, "build_global_usd_valuation", return_value={
             "holders": [], "pools": [{"status": "verified"}]}):
        report = m.get_lp_leaderboard_text()
    assert "No wallets with readable LP positions" in report
    assert "JEX WOODY/OLV" not in report


def test_onedex_woody_one_lp_ownership_active_without_pair_id():
    from config import LP_POOLS
    pool = next(p for p in LP_POOLS if p["dex"] == "OneDex" and p["name"] == "WOODY/ONE")
    assert pool["status"] == "active"
    assert pool["lp_token"] == "WOODYONE-826f23"


def test_onedex_woody_one_live_usd_uses_exact_reserves_without_pair_id():
    pool = {"status": "active", "pair_address": "erd1sharedonedex",
            "name": "WOODY/ONE", "dex": "OneDex",
            "lp_token": "WOODYONE-826f23", "quote_token": m.ONE}
    holder_data = {"ok": True, "total_supply_raw": "1000",
                   "holders": [{"wallet": "erd1wallet", "balance_raw": "500"}]}
    indexed_snap = {"ok": True, "woody_amount": 400000, "pair_amount": 1000,
                    "pair_token": m.ONE, "pair_symbol": "ONE",
                    "reserve_source": "DexScreener public indexer (indicative)"}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_egld_usd", return_value=10), \
         patch.object(m, "get_best_price", return_value={
             "price_usd": 0.000003, "source": "test"}), \
         patch.object(m, "get_lp_holders", return_value=holder_data), \
         patch.object(m, "get_onedex_woody_one_pool_snapshot", return_value={
             "ok": False, "reason": "pair ID missing"}), \
         patch.object(m, "get_onedex_woody_one_public_quote",
                      return_value=indexed_snap), \
         patch.object(m, "get_verified_quote_usd", return_value={
             "ok": True, "price_usd": 99, "confidence": "feed"}):
        result = m.build_global_usd_valuation()

    # Pool USD = $1.20 WOODY side + $1.20 reserve-implied ONE side.
    assert result["pools"][0]["pool_value_usd"] == 2.4
    assert result["holders"][0]["estimated_usd"] == 1.2
    assert result["pools"][0]["quote_usd"] == 0.0012
    assert result["pools"][0]["quote_price_confidence"] == "indicative"
    # Indicative live quotes may appear in the live leaderboard but remain
    # ineligible for monthly reward snapshots.
    assert result["valuation_complete"] is False


def test_indicative_quote_metadata_is_replaced_by_exact_pool_reserve_price():
    pool = {"status": "active", "pair_address": "erd1jexpair",
            "name": "WOODY/JEX", "dex": "JEX",
            "lp_token": "LP-JEX", "quote_token": "JEX-expected"}
    holder_data = {"ok": True, "total_supply_raw": "1000",
                   "holders": [{"wallet": "erd1wallet", "balance_raw": "500"}]}
    snap = {"ok": True, "woody_amount": 1000, "pair_amount": 2000,
            "pair_token": "JEX-expected"}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_egld_usd", return_value=10), \
         patch.object(m, "get_best_price", return_value={"price_usd": 0.02}), \
         patch.object(m, "get_lp_holders", return_value=holder_data), \
         patch.object(m, "get_pool_snapshot", return_value=snap), \
         patch.object(m, "get_verified_quote_usd", return_value={
             "ok": True, "price_usd": 999, "confidence": "indicative"}):
        result = m.build_global_usd_valuation()
    assert result["pools"][0]["quote_usd"] == 0.01
    assert result["pools"][0]["pool_value_usd"] == 40
    assert result["holders"][0]["estimated_usd"] == 20
    assert "reserve ratio" in result["pools"][0]["quote_price_source"].lower()


def test_onedex_woody_one_requires_confirmed_pair_id():
    with patch.object(m, "ONEDEX_WOODY_ONE_PAIR_ID", 0):
        snap = m.get_onedex_woody_one_pool_snapshot()
    assert snap["ok"] is False
    assert "pair ID not confirmed" in snap["reason"]


def test_onedex_woody_one_rejects_wrong_lp_identifier():
    def vm_query(function, args):
        mapping = {"getPairFirstTokenId": m.WOODY.encode(),
                   "getPairSecondTokenId": m.ONE.encode(),
                   "getPairFirstTokenReserve": (10 ** 18).to_bytes(8, "big"),
                   "getPairSecondTokenReserve": (10 ** 18).to_bytes(8, "big"),
                   "getPairLpTokenId": b"WRONG-abcdef"}
        return mapping[function]
    with patch.object(m, "ONEDEX_WOODY_ONE_PAIR_ID", 999), \
         patch.object(m, "_vm_query_scalar", side_effect=vm_query):
        snap = m.get_onedex_woody_one_pool_snapshot()
    assert snap["ok"] is False
    assert "LP token verification failed" in snap["reason"]


def test_woody_one_public_quote_rejects_unrelated_pairs():
    wrong = {"pairs": [{"chainId": "multiversx", "dexId": "onedex",
                        "pairAddress": "other-pair",
                        "baseToken": {"address": m.WOODY},
                        "quoteToken": {"address": m.ONE},
                        "liquidity": {"base": 100, "quote": 200}}]}
    with patch.object(m, "get_json", return_value=wrong):
        result = m.get_onedex_woody_one_public_quote()
    assert not result["ok"]


def test_woody_one_public_quote_requires_exact_lp_pair():
    pair = {"chainId": "multiversx", "dexId": "onedex",
            "pairAddress": m.ONEDEX_POOL_ADDRESS + "-WOODYONE-826f23",
            "baseToken": {"address": m.WOODY},
            "quoteToken": {"address": m.ONE},
            "liquidity": {"base": 294583, "quote": 1481.3566}}
    with patch.object(m, "get_json", return_value={"pairs": [pair]}):
        result = m.get_onedex_woody_one_public_quote()
    assert result["ok"]
    assert result["woody_amount"] == 294583
    assert "indicative" in result["reserve_source"]


def test_duplicate_monthly_checkpoint_cannot_generate_rewards():
    base = {"valuation_complete": True, "total_eligible_usd": 100,
            "pools": [{"status": "verified"}],
            "holders": [{"wallet": "erd1a", "estimated_usd": 100}]}
    dates = ("2026-09-01", "2026-09-15", "2026-09-30", "2026-09-15")
    with patch.object(m, "get_month_lp_usd_snapshots",
                      return_value=[dict(base, date=d) for d in dates]), \
         patch.object(m, "current_month_key", return_value="2026-09"):
        result = m.calculate_monthly_lp_rewards(10)
    assert result["valuation_complete"] is False
    assert result["rows"] == []
    assert result["duplicate_dates"] == ["2026-09-15"]


def test_off_schedule_snapshot_cannot_generate_rewards():
    base = {"valuation_complete": True, "total_eligible_usd": 100,
            "pools": [{"status": "verified"}],
            "holders": [{"wallet": "erd1a", "estimated_usd": 100}]}
    dates = ("2026-09-01", "2026-09-15", "2026-09-29")
    with patch.object(m, "get_month_lp_usd_snapshots",
                      return_value=[dict(base, date=d) for d in dates]), \
         patch.object(m, "current_month_key", return_value="2026-09"):
        result = m.calculate_monthly_lp_rewards(10)
    assert result["valuation_complete"] is False
    assert result["rows"] == []
    assert "2026-09-30" in result["missing_dates"]


def test_lp_preflight_reports_unverified_onedex_and_missing_jex_ids():
    pools = [
        {"dex": "OneDex", "name": "WOODY/ONE", "status": "unverified",
         "lp_token": "WOODYONE-826f23", "pair_address": "erd1contract",
         "quote_token": m.ONE, "pair_id": 0},
        {"dex": "JEX", "name": "WOODY/JEX", "status": "active",
         "lp_token": "", "pair_address": "erd1jex", "quote_token": "JEX-123"},
        {"dex": "OneDex", "name": "WOODY/BOBER", "status": "excluded"},
    ]
    with patch.object(m, "LP_POOLS", pools):
        audit = m.audit_global_lp_configuration()
    assert audit["configuration_ready"] is False
    assert "OneDex numeric pair ID unverified" in audit["pools"][0]["issues"]
    assert "LP token ID missing" in audit["pools"][1]["issues"]
    assert audit["pools"][2]["status"] == "excluded"
    assert audit["snapshot_file"].endswith("data/lp_usd_snapshots.json")


def test_jex_olv_has_exact_verified_quote_token_configured():
    from config import LP_POOLS, OLV
    pool = next(p for p in LP_POOLS if p["dex"] == "JEX" and p["name"] == "WOODY/OLV")
    assert OLV == "OLV-aa679c"
    assert pool["quote_token"] == OLV
    # JEX pool contract holdings do not prove fungible LP ownership.
    assert pool["lp_token"] == "LPOLVWOOD-29ac00"


def test_jex_reserves_must_not_be_mistaken_for_lp_token():
    pool = {"dex": "JEX", "name": "WOODY/JEX",
            "pair_address": "erd1testjexpair", "lp_token": "", "status": "active"}
    with patch.object(m, "PRICE_CACHE", {}), \
         patch.object(m, "post_json", return_value=None), \
         patch.object(m, "get_json", return_value=[
             {"identifier": "WOODY-5f9d9c", "balance": "1000"},
             {"identifier": "JEX-9040ca", "balance": "2000"}]):
        assert m.discover_pool_lp_token(pool) == ""


def test_xexchange_usdc_uses_exact_quote_identifier():
    from config import LP_POOLS, USDC
    pool = next(p for p in LP_POOLS if p["dex"] == "xExchange" and p["name"] == "WOODY/USDC")
    assert USDC == "USDC-c76f1f"
    assert pool["quote_token"] == USDC


def test_jex_lp_identifiers_verified_on_chain():
    from config import LP_POOLS
    expected = {
        "WOODY/BOBER": "LPWOODBOBE-08e5f1",
        "WOODY/JEX": "LPWOODJEX-1ea32b",
        "WOODY/OLV": "LPOLVWOOD-29ac00",
    }
    actual = {p["name"]: p["lp_token"] for p in LP_POOLS if p["dex"] == "JEX"}
    assert actual == expected


def test_live_lp_ownership_includes_unpriced_wallets():
    from unittest.mock import patch
    from core import multiversx as m
    pools = [
        {"dex": "JEX", "name": "WOODY/OLV", "status": "active", "lp_token": "LPOLVWOOD-29ac00"},
        {"dex": "OneDex", "name": "WOODY/BOBER", "status": "excluded"},
    ]
    holders = {"ok": True, "lp_token_id": "LPOLVWOOD-29ac00",
               "holders": [{"wallet": "erd1examplewallet", "lp_amount": 2.5,
                            "balance_raw": "2500000000000000000"}]}
    with patch.object(m, "LP_POOLS", pools), patch.object(m, "get_lp_holders", return_value=holders):
        result = m.build_live_lp_ownership()
    assert len(result["holders"]) == 1
    assert result["holders"][0]["pools"][0]["lp_amount"] == 2.5
    assert len(result["pools"]) == 1


def test_live_leaderboard_never_uses_monthly_reward_snapshots():
    from unittest.mock import patch
    from core import multiversx as m
    ownership = {"holders": [{"wallet": "erd1examplewallet", "pools": [
        {"pool": "JEX WOODY/OLV", "lp_amount": 2.5}]}],
        "pools": [{"label": "JEX WOODY/OLV", "status": "readable"}]}
    with patch.object(m, "build_live_lp_ownership", return_value=ownership), \
         patch.object(m, "build_global_usd_valuation", return_value={"holders": []}), \
         patch.object(m, "calculate_monthly_lp_averages", side_effect=AssertionError("monthly called")):
        output = m.get_lp_leaderboard_text()
    assert "USD value unavailable" in output
    assert "1 pool" in output


def test_lp_supply_uses_exact_raw_issuance_counters():
    from unittest.mock import patch
    from core import multiversx as m
    metadata = {"decimals": 18, "supply": "105",
                "minted": "642472408715406878251",
                "burnt": "537403391901139078994",
                "initialMinted": "1000"}
    with patch.object(m, "get_token_metadata", return_value=metadata):
        raw, decimals = m.get_lp_total_supply_raw_and_decimals("LPWOODBOBE-08e5f1")
    assert raw == 105069016814267800257
    assert decimals == 18


def test_lp_supply_does_not_reject_fractional_lp_above_rounded_supply():
    from unittest.mock import patch
    from core import multiversx as m
    pool = {"status": "active", "name": "WOODY/BOBER", "lp_token": "LPWOODBOBE-08e5f1"}
    metadata = {"decimals": 18, "supply": "105",
                "minted": "642472408715406878251",
                "burnt": "537403391901139078994",
                "initialMinted": "1000"}
    with patch.object(m, "get_token_metadata", return_value=metadata), \
         patch.object(m, "discover_pool_lp_token", return_value="LPWOODBOBE-08e5f1"), \
         patch.object(m, "get_json", return_value=[
             {"address": "erd15zjkqzf54xhl5sd5dvshjwh43fe5ztvnapsjuvvsm3xuvqvtzlvqcph7yz",
              "balance": "105069016814267800257"}]):
        result = m.get_lp_holders(pool, require_tvl=False)
    assert result["ok"] is True
    assert len(result["holders"]) == 1


def test_lp_supply_zero_rounded_but_nonzero_raw_issuance():
    from unittest.mock import patch
    from core import multiversx as m
    metadata = {"decimals": 18, "supply": "0", "minted": "437196234",
                "burnt": "304750000", "initialMinted": "1000"}
    with patch.object(m, "get_token_metadata", return_value=metadata):
        raw, _ = m.get_lp_total_supply_raw_and_decimals("WOODYUSDC-56b519")
    assert raw == 132447234



def test_onedex_woody_one_legacy_tvl_uses_its_own_pair_reserves():
    pool = {"status": "active", "pair_address": "erd1sharedonedex",
            "name": "WOODY/ONE", "dex": "OneDex",
            "lp_token": "WOODYONE-826f23", "quote_token": m.ONE}
    snap = {"ok": True, "woody_amount": 400_000, "pair_amount": 1_000,
            "pair_token": m.ONE, "pair_symbol": "ONE"}
    with patch.object(m, "POOL_SNAPSHOT_CACHE", {}), \
         patch.object(m, "get_onedex_woody_one_pool_snapshot",
                      return_value=snap), \
         patch.object(m, "get_best_price",
                      return_value={"price_usd": 0.000003}), \
         patch.object(m, "get_egld_usd", return_value=4.0):
        result = m.get_pool_tvl_egld(pool)

    assert result["pair_token"] == m.ONE
    assert result["pool_value_usd"] == 2.4
    assert result["pool_value_egld"] == 0.6


def test_pools_command_lists_woody_one_pool():
    pool = {"status": "active", "pair_address": "erd1sharedonedex",
            "name": "WOODY/ONE", "dex": "OneDex",
            "lp_token": "WOODYONE-826f23", "quote_token": m.ONE}
    snap = {"ok": True, "woody_amount": 400_000, "pair_amount": 1_000,
            "pair_token": m.ONE, "pair_symbol": "ONE",
            "pool_value_usd": 2.4}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "WATCHED_POOLS", {}), \
         patch.object(m, "get_configured_pool_snapshot", return_value=snap):
        report = m.get_pools_text()

    assert "OneDex WOODY/ONE" in report
    assert "ONE: 1,000.000000" in report
    assert "*Total liquidity across all WOODY pools:* `$2.40`" in report


def test_market_context_prices_one_from_woody_one_pair():
    pool = {"status": "active", "pair_address": "erd1sharedonedex",
            "name": "WOODY/ONE", "dex": "OneDex",
            "lp_token": "WOODYONE-826f23", "quote_token": m.ONE}
    snap = {"ok": True, "woody_amount": 400_000, "pair_amount": 1_000}
    with patch.object(m, "LP_POOLS", [pool]), \
         patch.object(m, "get_configured_pool_snapshot", return_value=snap), \
         patch.object(m, "get_best_price",
                      return_value={"price_usd": 0.000003}):
        price = m._estimate_token_context_price(m.ONE)

    assert price["ok"]
    assert price["pool"] == "OneDex WOODY/ONE"
    assert price["price_usd"] == 0.0012



def test_onedex_woody_one_tvl_does_not_use_cached_indexer_reserves():
    pool = {"status": "active", "pair_address": "erd1sharedonedex",
            "name": "WOODY/ONE", "dex": "OneDex",
            "lp_token": "WOODYONE-826f23", "quote_token": m.ONE}
    exact = {"ok": True, "woody_amount": 400_000, "pair_amount": 1_000,
             "pair_token": m.ONE, "pair_symbol": "ONE",
             "reserve_source": "OneDex viewPair storage endpoints"}
    indexed = {"ok": True, "woody_amount": 400_000, "pair_amount": 1_000,
               "pair_token": m.ONE, "pair_symbol": "ONE",
               "reserve_source": "DexScreener public indexer (indicative)"}
    cache = {"erd1sharedonedex:WOODYONE-826f23": (indexed, m.time.time())}
    with patch.object(m, "POOL_SNAPSHOT_CACHE", cache), \
         patch.object(m, "get_onedex_woody_one_pool_snapshot",
                      return_value=exact) as exact_reader, \
         patch.object(m, "get_best_price",
                      return_value={"price_usd": 0.000003}), \
         patch.object(m, "get_egld_usd", return_value=4.0):
        result = m.get_pool_tvl_egld(pool)

    exact_reader.assert_called_once_with()
    assert result["reserve_source"] == "OneDex viewPair storage endpoints"

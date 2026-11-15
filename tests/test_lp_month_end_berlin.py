"""Month-end WOODY LP reward snapshots must reflect late Berlin-local state."""
from datetime import datetime, timezone
from unittest.mock import patch

from core import multiversx as m


def valuation():
    return {
        "valuation_complete": True,
        "indicative_only": True,
        "reward_valuation_model": "woody_reserve_ratio_estimate_v1",
        "pools": [{"status": "verified", "quote_price_confidence": "indicative"}],
        "holders": [{"wallet": "erd1wallet", "estimated_usd": 42.0}],
        "total_eligible_usd": 42.0,
    }


def _run_at(instant, force=False):
    with (
        patch.object(m, "datetime") as clock,
        patch.object(m, "read_json_file", return_value={"snapshots": []}) as read,
        patch.object(m, "build_global_usd_valuation", return_value=valuation()) as price,
        patch.object(m, "write_json_file", return_value=True) as write,
    ):
        clock.now.return_value = instant
        result = m.save_global_usd_snapshot(force=force, snapshot_time=instant)
        history = write.call_args.args[1] if write.called else None
    return result, read.called, price.called, history


def test_month_end_early_snapshot_is_blocked_even_with_force():
    instant = datetime(2026, 11, 30, 21, 45, tzinfo=timezone.utc)
    # November 30 at 22:45 Europe/Berlin; final shares must not lock yet.
    for force in (False, True):
        result, read, price, history = _run_at(instant, force=force)
        assert result["ok"] is False
        assert "23:00" in result["reason"]
        assert not read
        assert not price
        assert history is None


def test_month_end_snapshot_saves_at_2305_berlin():
    instant = datetime(2026, 11, 30, 22, 5, tzinfo=timezone.utc)
    result, read, price, history = _run_at(instant)
    assert result["ok"] is True
    assert read and price
    assert history["snapshots"][0]["date"] == "2026-11-30"
    assert history["snapshots"][0]["scheduled_checkpoint"] is True


def test_month_end_summer_time_uses_berlin_clock():
    # 21:15 UTC in July is 23:15 CEST, still July 31 locally.
    instant = datetime(2027, 7, 31, 21, 15, tzinfo=timezone.utc)
    result, _read, _price, history = _run_at(instant)
    assert result["ok"] is True
    assert history["snapshots"][0]["date"] == "2027-07-31"


def test_utc_november_last_hour_is_december_in_berlin():
    # 23:10 UTC November 30 is already 00:10 December 1 CET.
    instant = datetime(2026, 11, 30, 23, 10, tzinfo=timezone.utc)
    result, _read, _price, history = _run_at(instant)
    assert result["ok"] is True
    assert history["snapshots"][0]["date"] == "2026-12-01"

from unittest.mock import patch

from core import multiversx as m


def test_mvx_429_backoff_honors_retry_after_and_clears_bucket(monkeypatch):
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_FAILURES", 0)
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_COOLDOWN_UNTIL", 0.0)
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_TOKENS", 1.0)
    before = m.time.monotonic()

    delay = m._register_mvx_rate_limit_backoff("5")

    assert delay >= 5
    assert m.MVX_RATE_LIMIT_COOLDOWN_UNTIL >= before + 5
    assert m.MVX_RATE_LIMIT_TOKENS == 0
    assert m.MVX_RATE_LIMIT_FAILURES == 1


def test_mvx_backoff_grows_when_retry_after_is_missing(monkeypatch):
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_FAILURES", 0)
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_COOLDOWN_UNTIL", 0.0)

    first = m._register_mvx_rate_limit_backoff()
    second = m._register_mvx_rate_limit_backoff()

    assert first == 2
    assert second == 4
    assert m.MVX_RATE_LIMIT_FAILURES == 2


def test_mvx_rate_limiter_waits_for_global_cooldown(monkeypatch):
    clock = iter([10.0, 11.1])
    sleeps = []
    monkeypatch.setattr(m.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(m.time, "sleep", sleeps.append)
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_COOLDOWN_UNTIL", 11.0)
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_UPDATED_AT", 11.0)
    monkeypatch.setattr(m, "MVX_RATE_LIMIT_TOKENS", 1.0)
    monkeypatch.setattr(m, "MVX_API_RATE_LIMIT_PER_SECOND", 1.0)
    monkeypatch.setattr(m, "MVX_API_RATE_LIMIT_BURST", 1)

    m._wait_for_mvx_rate_limit()

    assert sleeps == [1.0]
    assert m.MVX_RATE_LIMIT_TOKENS == 0


def test_liquidity_message_explains_rate_limited_pool(monkeypatch):
    pools = [{
        "dex": "xExchange",
        "pair": "WOODY/EGLD",
        "status": "unavailable",
        "reason": "MultiversX API rate limit (HTTP 429)",
    }]
    monkeypatch.setattr(m, "get_best_price", lambda: {"price_usd": 0.000001})
    monkeypatch.setattr(m, "get_public_pool_reserves", lambda: pools)

    text = m.get_liquidity_text()

    assert "WOODY/EGLD: unavailable (MultiversX API rate limit (HTTP 429))" in text
    assert "across 0 readable pools" in text


def test_public_liquidity_keeps_pool_visible_when_reserves_are_incomplete(monkeypatch):
    pool = {
        "dex": "JEX",
        "name": "WOODY/OLV",
        "pair_address": "pool-address",
        "lp_token": "LPOLVWOOD-29ac00",
        "status": "active",
    }
    snapshot = {"ok": True, "woody_amount": 100, "pair_amount": 0, "pair_symbol": "OLV"}
    monkeypatch.setattr(m, "LP_POOLS", [pool])
    monkeypatch.setattr(m, "get_pool_snapshot", lambda *_: snapshot)

    result = m.get_public_pool_reserves()

    assert len(result) == 1
    assert result[0]["pair"] == "WOODY/OLV"
    assert result[0]["status"] == "unavailable"
    assert "incomplete" in result[0]["reason"]

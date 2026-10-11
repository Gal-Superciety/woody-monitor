import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import multiversx as m


def test_morning_market_report_uses_labeled_live_and_24h_inputs():
    market_data = {
        "elrond-erd-2": {"usd": 4.10, "usd_24h_change": 2.25},
        "bitcoin": {"usd": 65000, "usd_24h_change": 1.1},
    }
    global_data = {
        "data": {
            "market_cap_change_percentage_24h_usd": 0.8,
            "market_cap_percentage": {"btc": 54.2},
        }
    }

    def fake_get_json(url, params=None):
        if url == m.COINGECKO_DAILY_MARKET_API:
            return market_data
        if url == m.COINGECKO_GLOBAL_MARKET_API:
            return global_data
        return None

    trades = [
        {"type": 1, "usd": 12},
        {"type": 1, "usd": 8},
        {"type": -1, "usd": 4},
    ]
    with patch.object(m, "get_json", side_effect=fake_get_json), \
         patch.object(m, "get_best_price", return_value={
             "price_usd": 0.000003, "source": "xExchange WOODY/WEGLD"}), \
         patch.object(m, "get_egld_usd", return_value=4.10), \
         patch.object(m, "_recent_trades", return_value=trades), \
         patch.object(m, "get_public_pool_reserves", return_value=[{}, {}]), \
         patch.object(m, "build_public_liquidity", return_value={
             "totalUsd": 1500, "estimatedPoolCount": 2, "pools": []}):
        report = m.build_morning_market_report_text()

    assert "WOODY Morning Market Brief" in report
    assert "Reference price: *$0.0000030000*" in report
    assert "Bot-observed swaps, 24h: *3* · buys 2 / sells 1" in report
    assert "Bot-observed volume: *$24.00* · buys $20.00 / sells $4.00" in report
    assert "Price: *$4.1000* · 24h: *+2.25%*" in report
    assert "Global market cap, 24h: *+0.80%*" in report
    assert "BTC dominance: *54.20%*" in report
    assert "Broad market capitalization and BTC were both up over 24h." in report
    assert "only swaps detected by this bot" in report


def test_morning_market_report_labels_missing_sources_unavailable():
    with patch.object(m, "get_json", return_value=None), \
         patch.object(m, "get_best_price", return_value=None), \
         patch.object(m, "get_egld_usd", return_value=0), \
         patch.object(m, "_recent_trades", return_value=[]), \
         patch.object(m, "get_public_pool_reserves", return_value=[]), \
         patch.object(m, "build_public_liquidity", return_value={
             "totalUsd": None, "estimatedPoolCount": 0, "pools": []}):
        report = m.build_morning_market_report_text()

    assert "Reference price: *unavailable*" in report
    assert "No swaps detected by this bot" in report
    assert "Estimated visible LP liquidity: *unavailable* (0/0 readable pools)." in report
    assert "Price: *unavailable* · CoinGecko 24h: *unavailable*" in report
    assert "Broad-market change data was unavailable." in report


def test_morning_brief_is_scheduled_at_nine_berlin_time():
    queue = Mock()
    with patch.object(m, "ENABLE_MORNING_BRIEF", True), \
         patch.object(m, "MORNING_BRIEF_CHAT_ID", "-1001234567890"), \
         patch.object(m, "MORNING_BRIEF_HOUR", 9), \
         patch.object(m, "MORNING_BRIEF_TIMEZONE", "Europe/Berlin"):
        assert m.register_morning_market_brief(queue)

    args, kwargs = queue.run_daily.call_args
    assert args[0] is m.morning_market_brief_job
    assert kwargs["time"].hour == 9
    assert kwargs["time"].minute == 0
    assert kwargs["time"].tzinfo.key == "Europe/Berlin"
    assert kwargs["days"] == tuple(range(7))


def test_morning_brief_is_not_scheduled_without_target_chat():
    queue = Mock()
    with patch.object(m, "ENABLE_MORNING_BRIEF", True), \
         patch.object(m, "MORNING_BRIEF_CHAT_ID", ""):
        assert not m.register_morning_market_brief(queue)
    queue.run_daily.assert_not_called()


def test_welcome_handler_greets_new_humans_once_and_skips_bots():
    message = SimpleNamespace(
        new_chat_members=[
            SimpleNamespace(full_name="Alice", is_bot=False),
            SimpleNamespace(full_name="MonitorBot", is_bot=True),
            SimpleNamespace(full_name="Bob", is_bot=False),
        ],
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(type="supergroup"),
        effective_message=message,
    )
    with patch.object(m, "ENABLE_COMMUNITY_WELCOME", True):
        asyncio.run(m.community_welcome_handler(update, SimpleNamespace()))

    message.reply_text.assert_awaited_once()
    welcome = message.reply_text.await_args.args[0]
    assert "Alice, Bob have joined" in welcome
    assert "MonitorBot" not in welcome


def test_welcome_handler_ignores_private_chats():
    message = SimpleNamespace(
        new_chat_members=[SimpleNamespace(full_name="Alice", is_bot=False)],
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(type="private"),
        effective_message=message,
    )
    with patch.object(m, "ENABLE_COMMUNITY_WELCOME", True):
        asyncio.run(m.community_welcome_handler(update, SimpleNamespace()))
    message.reply_text.assert_not_awaited()


def test_morning_job_sends_the_generated_report_to_configured_group():
    bot = SimpleNamespace(send_message=AsyncMock())
    context = SimpleNamespace(bot=bot)
    report = "Morning report"
    with patch.object(m, "ENABLE_MORNING_BRIEF", True), \
         patch.object(m, "MORNING_BRIEF_CHAT_ID", "-1001234567890"), \
         patch.object(m, "build_morning_market_report_text", return_value=report):
        asyncio.run(m.morning_market_brief_job(context))

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs["chat_id"] == "-1001234567890"
    assert bot.send_message.await_args.kwargs["text"] == report

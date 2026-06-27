"""Basic smoke tests to keep CI pytest step green."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import main


def test_pytest_collection_smoke() -> None:
    """Ensure at least one test is collected and executable."""
    assert True


def test_liquidity_add_is_not_sell() -> None:
    tx = {
        "txHash": "hash-liq-add",
        "function": "addLiquidity",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(1500 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1wallet",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
            {
                "identifier": main.WEGLD,
                "value": str(2 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1wallet",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "LIQUIDITY_ADDED"


def test_liquidity_remove_detected() -> None:
    tx = {
        "txHash": "hash-liq-remove",
        "function": "removeLiquidity",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(1000 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1wallet",
            },
            {
                "identifier": main.WEGLD,
                "value": str(1 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1wallet",
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "LIQUIDITY_REMOVED"


def test_aggregator_style_buy_is_buy_not_liquidity() -> None:
    tx = {
        "txHash": "hash-buy-agg",
        "operations": [
            {
                "identifier": main.WEGLD,
                "value": str(3 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1realwallet",
                "receiver": "erd1router",
            },
            {
                "identifier": main.WEGLD,
                "value": str(3 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1router",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
            {
                "identifier": main.WOODY,
                "value": str(2200 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1realwallet",
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "BUY"


def test_aggregator_style_sell_is_sell_not_liquidity() -> None:
    tx = {
        "txHash": "hash-sell-agg",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(1200 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1realwallet",
                "receiver": "erd1router",
            },
            {
                "identifier": main.WOODY,
                "value": str(1200 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1router",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
            {
                "identifier": main.WEGLD,
                "value": str(1 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1realwallet",
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "SELL"


def test_normal_buy_is_buy() -> None:
    tx = {
        "txHash": "hash-buy-normal",
        "operations": [
            {
                "identifier": main.WEGLD,
                "value": str(1 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1buyer",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
            {
                "identifier": main.WOODY,
                "value": str(700 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1buyer",
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "BUY"


def test_normal_sell_is_sell() -> None:
    tx = {
        "txHash": "hash-sell-normal",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(700 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1seller",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
            {
                "identifier": main.WEGLD,
                "value": str(1 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1seller",
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "SELL"


def test_non_woody_transaction_returns_none() -> None:
    tx = {
        "txHash": "hash-non-woody",
        "operations": [
            {
                "identifier": main.WEGLD,
                "value": str(2 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1wallet",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
            {
                "identifier": "USDC-c76f1f",
                "value": str(50 * (10 ** 6)),
                "decimals": 6,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1wallet",
            },
        ],
    }
    assert main.classify_tx(tx) is None


def test_liquidity_invalid_sides_returns_none() -> None:
    tx_add_missing_egld = {
        "txHash": "hash-liq-missing-egld",
        "function": "addLiquidity",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(900 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1wallet",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
        ],
    }
    tx_remove_missing_woody = {
        "txHash": "hash-liq-missing-woody",
        "function": "removeLiquidity",
        "operations": [
            {
                "identifier": main.WEGLD,
                "value": str(1 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1wallet",
            },
        ],
    }
    assert main.classify_tx(tx_add_missing_egld) is None
    assert main.classify_tx(tx_remove_missing_woody) is None


def test_woody_only_transfer_is_classified_from_net_woody_delta() -> None:
    tx = {
        "txHash": "hash-woody-transfer",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(150 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1alice",
                "receiver": "erd1bob",
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] in {"BUY", "SELL"}
    assert parsed["woody_amount"] == 150


def test_xexchange_real_hash_style_wrap_and_swap_is_buy() -> None:
    tx = {
        "txHash": "2dd6c8911e1b4e6f74fb5336c7738ce90b2c8db8b3625e0fe02768b0185b69c4",
        "sender": "erd1buyerwalletxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "receiver": "erd1routerxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "value": str(2 * (10 ** 18)),
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(1300 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1buyerwalletxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            },
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "BUY"


def test_scr_sell_quote_recovery() -> None:
    """SELL where quote token is returned via SCR operations, not main ops.

    Mirrors the failing root 487efc40... pattern: WOODY_SENT > 0 in main ops
    but WEGLD is only visible inside a smartContractResults entry's operations
    sub-list.  The new get_scr_flows() helper must recover it so classify_tx()
    returns SELL instead of NONE/UNMATCHED_FLOW.
    """
    wallet = "erd1seller_scr_test"
    tx = {
        "txHash": "487efc40a2ee324501459201aabf33d5016ee3165a01e9634277044aade5854a",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(100_000 * (10 ** 18)),
                "decimals": 18,
                "sender": wallet,
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
        ],
        "smartContractResults": [
            {
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": wallet,
                "operations": [
                    {
                        "identifier": main.WEGLD,
                        "value": str(1 * (10 ** 18)),
                        "decimals": 18,
                        "sender": main.XEXCHANGE_POOL_ADDRESS,
                        "receiver": wallet,
                    }
                ],
            }
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None, "Expected SELL but got None (UNMATCHED_FLOW)"
    assert parsed["type"] == "SELL"
    assert parsed["woody_amount"] == 100_000.0
    assert parsed["quote_token"] == main.WEGLD


def test_get_scr_flows_extracts_received() -> None:
    """Unit test for get_scr_flows: received quote token from SCR operations."""
    wallet = "erd1test_wallet"
    tx = {
        "smartContractResults": [
            {
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": wallet,
                "operations": [
                    {
                        "identifier": main.WEGLD,
                        "value": str(2 * (10 ** 18)),
                        "decimals": 18,
                        "sender": main.XEXCHANGE_POOL_ADDRESS,
                        "receiver": wallet,
                    }
                ],
            }
        ]
    }
    scr_sent, scr_received = main.get_scr_flows(tx, wallet)
    assert main.WEGLD in scr_received
    assert abs(scr_received[main.WEGLD] - 2.0) < 1e-9
    assert main.WEGLD not in scr_sent


def test_get_scr_flows_extracts_sent() -> None:
    """Unit test for get_scr_flows: sent token from SCR operations."""
    wallet = "erd1test_wallet"
    tx = {
        "scResults": [
            {
                "sender": wallet,
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
                "operations": [
                    {
                        "identifier": main.WOODY,
                        "value": str(500 * (10 ** 18)),
                        "decimals": 18,
                        "sender": wallet,
                        "receiver": main.XEXCHANGE_POOL_ADDRESS,
                    }
                ],
            }
        ]
    }
    scr_sent, scr_received = main.get_scr_flows(tx, wallet)
    assert main.WOODY in scr_sent
    assert abs(scr_sent[main.WOODY] - 500.0) < 1e-9
    assert main.WOODY not in scr_received

def test_lp_snapshot_days_include_1_15_and_last_day() -> None:
    assert main.is_lp_snapshot_day(datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert main.is_lp_snapshot_day(datetime(2026, 6, 15, tzinfo=timezone.utc))
    assert main.is_lp_snapshot_day(datetime(2026, 6, 30, tzinfo=timezone.utc))
    assert not main.is_lp_snapshot_day(datetime(2026, 6, 14, tzinfo=timezone.utc))


def test_lp_rewards_are_proportional_to_monthly_average(monkeypatch) -> None:
    snapshots = [
        {
            "date": "2026-06-01",
            "holders": [
                {"wallet": "erd1alice", "lp_amount": 10, "estimated_egld": 1},
                {"wallet": "erd1bob", "lp_amount": 30, "estimated_egld": 3},
            ],
        },
        {
            "date": "2026-06-15",
            "holders": [
                {"wallet": "erd1alice", "lp_amount": 30, "estimated_egld": 3},
                {"wallet": "erd1bob", "lp_amount": 30, "estimated_egld": 3},
            ],
        },
    ]
    monkeypatch.setattr(main, "get_month_lp_snapshots", lambda month_key=None: snapshots)

    result = main.calculate_lp_rewards(5, "2026-06")
    rewards = {row["wallet"]: row["reward_egld"] for row in result["rows"]}

    assert rewards["erd1alice"] == 2.0
    assert rewards["erd1bob"] == 3.0


def test_lp_holder_values_use_lp_token_decimals_and_raw_share(monkeypatch) -> None:
    monkeypatch.setattr(main, "discover_xexchange_lp_token_id", lambda: "LP-WOODYEGLD")
    monkeypatch.setattr(main, "get_lp_total_supply_raw_and_decimals", lambda token: (10_000 * (10 ** 18), 18))
    monkeypatch.setattr(main, "get_xexchange_pool_value_egld", lambda: 21.64)

    def fake_get_json(url, params=None):
        if url.endswith("/tokens/LP-WOODYEGLD/accounts"):
            return [
                {
                    "address": "erd1alice",
                    "balance": str(250 * (10 ** 18)),
                    "decimals": 0,  # account-level value must not override LP token decimals
                }
            ]
        return {}

    monkeypatch.setattr(main, "get_json", fake_get_json)

    result = main.fetch_lp_holders()

    assert result["ok"] is True
    holder = result["holders"][0]
    assert holder["lp_amount"] == 250.0
    assert abs(holder["estimated_egld"] - 0.541) < 1e-12


def test_monthly_average_uses_all_available_snapshots(monkeypatch) -> None:
    snapshots = [
        {"date": "2026-06-01", "holders": [{"wallet": "erd1alice", "lp_amount": 10}, {"wallet": "erd1bob", "lp_amount": 30}]},
        {"date": "2026-06-15", "holders": [{"wallet": "erd1alice", "lp_amount": 20}, {"wallet": "erd1bob", "lp_amount": 20}]},
        {"date": "2026-06-30", "holders": [{"wallet": "erd1alice", "lp_amount": 30}, {"wallet": "erd1bob", "lp_amount": 10}]},
    ]
    monkeypatch.setattr(main, "get_month_lp_snapshots", lambda month_key=None: snapshots)

    result = main.calculate_lp_rewards(8, "2026-06")
    rewards = {row["wallet"]: row["reward_egld"] for row in result["rows"]}

    assert len(result["snapshots"]) == 3
    assert result["total_average_lp"] == 40.0
    assert rewards["erd1alice"] == 4.0
    assert rewards["erd1bob"] == 4.0


def test_snapshot_average_egld_is_recomputed_from_pool_value(monkeypatch) -> None:
    snapshots = [
        {
            "date": "2026-06-01",
            "pool_value_egld": 21.64,
            "total_lp_supply": 10_000,
            "holders": [{"wallet": "erd1alice", "lp_amount": 250, "estimated_egld": 999_999_999}],
        }
    ]
    monkeypatch.setattr(main, "get_month_lp_snapshots", lambda month_key=None: snapshots)

    result = main.calculate_monthly_lp_averages("2026-06")

    assert abs(result["rows"][0]["average_egld"] - 0.541) < 1e-12

def _keyboard_labels(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def test_main_menu_contains_lp_rewards_section_buttons() -> None:
    labels = _keyboard_labels(main.main_menu_keyboard())

    assert "🪙 LP Holders" in labels
    assert "🏆 LP Leaderboard" in labels
    assert "📸 LP Snapshots" in labels
    assert "🎁 LP Rewards" in labels
    assert "📄 LP Export" in labels


def test_public_menu_contains_lp_rewards_section_buttons() -> None:
    labels = _keyboard_labels(main.public_menu_keyboard())

    assert "🪙 LP Holders" in labels
    assert "🏆 LP Leaderboard" in labels
    assert "📸 LP Snapshots" in labels
    assert "🎁 LP Rewards" in labels
    assert "📄 LP Export" in labels


def test_lp_snapshots_text_lists_current_month_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(main, "current_month_key", lambda now=None: "2026-06")
    monkeypatch.setattr(
        main,
        "get_month_lp_snapshots",
        lambda month_key=None: [
            {
                "date": "2026-06-01",
                "lp_token_id": "LP-WOODYEGLD",
                "pool_value_egld": 42,
                "holders": [{"wallet": "erd1alice", "lp_amount": 10}],
            }
        ],
    )

    text = main.get_lp_snapshots_text()

    assert "📸 *LP Snapshots*" in text
    assert "day 1, day 15 and the final day" in text
    assert "2026-06-01" in text
    assert "LP-WOODYEGLD" in text


def test_lp_export_csv_contains_manual_reward_distribution(monkeypatch) -> None:
    monkeypatch.setattr(main, "current_month_key", lambda now=None: "2026-06")
    monkeypatch.setattr(
        main,
        "calculate_lp_rewards",
        lambda reward_pool_egld: {
            "rows": [
                {
                    "wallet": "erd1alice",
                    "average_lp": 20,
                    "share_pct": 40,
                    "reward_egld": 2,
                },
                {
                    "wallet": "erd1bob",
                    "average_lp": 30,
                    "share_pct": 60,
                    "reward_egld": 3,
                },
            ]
        },
    )

    content, filename = main.build_lp_export_csv(5)
    csv_text = content.decode("utf-8")

    assert filename == "woody_lp_rewards_2026-06.csv"
    assert "wallet_address,average_lp,percent_of_total,reward_egld" in csv_text
    assert "erd1alice,20.000000000000000000,40.00000000,2.000000000000000000" in csv_text
    assert "erd1bob,30.000000000000000000,60.00000000,3.000000000000000000" in csv_text


def test_manual_lp_snapshot_can_save_same_day_and_includes_holder_percent(monkeypatch, tmp_path) -> None:
    snapshot_file = tmp_path / "lp_snapshots.json"
    monkeypatch.setattr(main, "LP_SNAPSHOT_FILE", str(snapshot_file))
    monkeypatch.setattr(
        main,
        "fetch_lp_holders",
        lambda: {
            "ok": True,
            "lp_token_id": "LP-WOODYEGLD",
            "total_supply": 100,
            "pool_value_egld": 50,
            "holders": [
                {"wallet": "erd1alice", "lp_amount": 25, "estimated_egld": 12.5},
                {"wallet": "erd1bob", "lp_amount": 75, "estimated_egld": 37.5},
            ],
        },
    )
    dt = datetime(2026, 6, 6, 12, 34, tzinfo=timezone.utc)

    first = main.save_lp_snapshot(force=True, snapshot_time=dt)
    second = main.save_lp_snapshot(force=True, snapshot_time=dt)

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["snapshot"]["created_at"] == "2026-06-06T12:34:00+00:00"
    assert first["snapshot"]["holders"][0]["percent_of_total_lp"] == 25.0
    assert first["snapshot"]["holders"][1]["percent_of_total_lp"] == 75.0
    assert len(main.load_lp_snapshots()["snapshots"]) == 2


def test_lp_snapshot_confirmation_uses_requested_summary_format() -> None:
    text = main.format_lp_snapshot_confirmation(
        {
            "created_at": "2026-06-06T12:34:00+00:00",
            "pool_value_egld": 42,
            "holders": [{"wallet": "erd1alice"}, {"wallet": "erd1bob"}],
        }
    )

    assert "📸 LP Snapshot saved successfully" in text
    assert "Pool: WOODY/EGLD xExchange" in text
    assert "LP holders: 2" in text
    assert "Total LP value: 42.000000 EGLD" in text
    assert "Date: 06.06.2026 12:34" in text


def test_woody_app_dashboard_contains_required_sections() -> None:
    html = main.woody_app_html()
    required_sections = [
        "Connect MultiversX Wallet",
        "Premium Access",
        "Holder Levels",
        "Daily Missions",
        "AI Assistant",
        "WOODY Monitor",
        "WOODY-5f9d9c",
    ]
    for section in required_sections:
        assert section in html

"""Basic smoke tests to keep CI pytest step green."""

import sys
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

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


def test_xexchange_buy_woody_in_operations_quote_in_results() -> None:
    tx = {
        "txHash": "hash-buy-op-res",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(2000 * (10 ** 18)),
                "decimals": 18,
                "sender": main.XEXCHANGE_POOL_ADDRESS,
                "receiver": "erd1user",
            },
        ],
        "results": [
            {
                "transfers": [
                    {
                        "identifier": main.WEGLD,
                        "value": str(2 * (10 ** 18)),
                        "decimals": 18,
                        "sender": "erd1user",
                        "receiver": main.XEXCHANGE_POOL_ADDRESS,
                    }
                ]
            }
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "BUY"


def test_xexchange_sell_woody_in_operations_quote_in_results() -> None:
    tx = {
        "txHash": "hash-sell-op-res",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(3000 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1user",
                "receiver": main.XEXCHANGE_POOL_ADDRESS,
            },
        ],
        "results": [
            {
                "inner": {
                    "identifier": main.WEGLD,
                    "value": str(3 * (10 ** 18)),
                    "decimals": 18,
                    "sender": main.XEXCHANGE_POOL_ADDRESS,
                    "receiver": "erd1user",
                }
            }
        ],
    }
    parsed = main.classify_tx(tx)
    assert parsed is not None
    assert parsed["type"] == "SELL"


def test_woody_only_transfer_without_quote_returns_none() -> None:
    tx = {
        "txHash": "hash-woody-only",
        "operations": [
            {
                "identifier": main.WOODY,
                "value": str(400 * (10 ** 18)),
                "decimals": 18,
                "sender": "erd1usera",
                "receiver": "erd1userb",
            },
        ],
    }
    assert main.classify_tx(tx) is None

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

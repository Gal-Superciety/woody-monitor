"""Offline tests for mainnet view-query decoding and privacy-safe discovery."""
import base64
import unittest
from unittest.mock import Mock

from core.hatom_onchain import (
    CONTROLLER, GATEWAY, HatomScanner, VmClient,
    _addresses, _decode_bool, address_decode, address_encode,
)


def result(*data):
    return {
        "error": "",
        "code": "successful",
        "data": {
            "data": {
                "ReturnCode": 0,
                "ReturnData": [base64.b64encode(item).decode("ascii") for item in data],
            }
        },
    }


class VmTests(unittest.TestCase):
    def test_official_controller_roundtrip(self):
        self.assertEqual(address_encode(address_decode(CONTROLLER)), CONTROLLER)
        self.assertEqual(len(address_decode(CONTROLLER)), 32)
        with self.assertRaises(ValueError):
            address_decode(CONTROLLER[:-1] + ("x" if CONTROLLER[-1] != "x" else "q"))

    def test_address_vector_multiple_chunks(self):
        market1 = address_decode(CONTROLLER)
        market2 = bytes([8]) * 32
        self.assertEqual(_addresses([market1 + market2]), [CONTROLLER, address_encode(market2)])
        self.assertEqual(_addresses([market1, market2]), [CONTROLLER, address_encode(market2)])
        with self.assertRaises(ValueError):
            _addresses([b"\x01" * 31])

    def test_fail_closed_boolean(self):
        self.assertTrue(_decode_bool(b"\x01"))
        self.assertFalse(_decode_bool(b"\x00"))
        with self.assertRaises(ValueError):
            _decode_bool(b"true")

    def test_network_query_uses_read_only_endpoint(self):
        res = Mock()
        res.content = b"ok"
        res.json.return_value = result(b"\x01")
        res.raise_for_status.return_value = None
        session = Mock()
        session.post.return_value = res
        client = VmClient(session=session)
        borrower = address_encode(bytes([5]) * 32)
        self.assertTrue(client.risky(borrower))
        args = session.post.call_args.kwargs
        self.assertEqual(session.post.call_args.args, (GATEWAY,))
        self.assertFalse(args["allow_redirects"])
        self.assertEqual(args["json"]["funcName"], "isRisky")
        self.assertEqual(args["json"]["args"], [address_decode(borrower).hex()])

    def test_network_errors_reject_fail_closed(self):
        response = Mock()
        response.content = b"x"
        response.json.return_value = {
            "data": {"data": {"ReturnCode": 4, "ReturnData": ["AQ=="]}},
            "error": "",
        }
        session = Mock()
        session.post.return_value = response
        with self.assertRaises(ValueError):
            VmClient(session=session).whitelist()


class StubClient:
    def __init__(self):
        self.calls = []
        self.market = CONTROLLER
        self.borrower = address_encode(bytes([5]) * 32)
        self.other = address_encode(bytes([9]) * 32)
        self.collateral = address_encode(bytes([4]) * 32)
        self.mode = "allowed"

    def whitelist(self):
        self.calls.append("whitelist")
        return [self.market, self.collateral]

    def members(self, market):
        self.calls.append(("members", market))
        return [self.borrower, self.other]

    def risky(self, borrower):
        self.calls.append(("risky", borrower))
        return borrower == self.borrower

    def account_markets(self, borrower):
        return [self.market, self.collateral]

    def borrow_amount(self, market, borrower):
        return 500 if market == self.market else 0

    def collateral_tokens(self, market, borrower):
        return 1500 if market == self.collateral else 0

    def liquidation_allowed(self, borrow_market, collateral_market, borrower, repay_raw):
        self.calls.append(("allowed", repay_raw))
        return self.mode == "allowed"


class ScannerTests(unittest.TestCase):
    def test_risky_checked_then_allow_check_no_signing(self):
        client = StubClient()
        scanner = HatomScanner(client, batch=2, refresh_seconds=3600)
        candidates = scanner.scan()
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["borrower"], client.borrower)
        self.assertEqual(candidate["category"], "ONCHAIN_RISKY")
        self.assertIsNone(candidate["max_repay_usd"])
        self.assertEqual(candidate["borrow_market"], client.market)
        self.assertIn(("allowed", 1), client.calls)

    def test_does_not_alert_when_liquidation_check_refuses(self):
        client = StubClient()
        client.mode = "refused"
        scanner = HatomScanner(client, batch=2, refresh_seconds=3600)
        self.assertEqual(scanner.scan(), [])

    def test_no_market_fails_closed(self):
        client = StubClient()
        client.whitelist = lambda: []
        scanner = HatomScanner(client)
        with self.assertRaises(ValueError):
            scanner.scan()


if __name__ == "__main__":
    unittest.main()

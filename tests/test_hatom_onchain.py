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

    def test_nontrivial_repay_and_collateral_cash_preflight(self):
        responses = [
            result((5 * 10**17).to_bytes(8, "big")),  # 50% close factor (WAD)
            result(bytes([1])),  # Controller repayment allowed
            result((150).to_bytes(2, "big")),  # Hatom tokens seized
            result((200).to_bytes(2, "big")),  # borrower collateral hTokens
            result((120).to_bytes(1, "big")),  # underlying received
            result((500).to_bytes(2, "big")),  # collateral market cash
        ]
        session = Mock()
        outputs = []
        for data in responses:
            response = Mock()
            response.content = b"ok"
            response.json.return_value = data
            outputs.append(response)
        session.post.side_effect = outputs
        client = VmClient(session=session)
        borrowed = 1000
        quote = client.meaningful_liquidation_check(CONTROLLER, CONTROLLER, CONTROLLER, borrowed)
        self.assertEqual(quote, {
            "repay_raw": 250, "seized_htokens_raw": 150, "collateral_underlying_raw": 120
        })
        names = [call.kwargs["json"]["funcName"] for call in session.post.call_args_list]
        self.assertEqual(names, [
            "getCloseFactor", "liquidateBorrowAllowed", "tokensToSeize",
            "getAccountTokens", "currentTokensToUnderlyingAmount", "getCash"
        ])
        self.assertEqual(session.post.call_args_list[1].kwargs["json"]["args"][-1], "fa")

    def test_preflight_rejects_insufficient_seizable_borrower_collateral(self):
        blobs = [
            (5 * 10**17).to_bytes(8, "big"), bytes([1]),
            (150).to_bytes(2, "big"), (100).to_bytes(2, "big"),
        ]
        session = Mock()
        outputs = []
        for blob in blobs:
            response = Mock()
            response.content = b"ok"
            response.json.return_value = result(blob)
            outputs.append(response)
        session.post.side_effect = outputs
        client = VmClient(session=session)
        self.assertIsNone(
            client.meaningful_liquidation_check(CONTROLLER, CONTROLLER, CONTROLLER, 1000)
        )
        functions = [c.kwargs["json"]["funcName"] for c in session.post.call_args_list]
        self.assertEqual(functions[-1], "getAccountTokens")
        self.assertNotIn("getCash", functions)

    def test_repay_preflight_rejects_small_debt(self):
        session = Mock()
        client = VmClient(session=session)
        self.assertIsNone(client.meaningful_liquidation_check(CONTROLLER, CONTROLLER, CONTROLLER, 1))
        session.post.assert_not_called()

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

    def meaningful_liquidation_check(self, borrow_market, collateral_market, borrower, borrow_raw):
        self.calls.append(("meaningful", borrow_raw))
        if self.mode != "allowed":
            return None
        return {"repay_raw": borrow_raw // 4, "seized_htokens_raw": 120, "collateral_underlying_raw": 120}


class ScannerTests(unittest.TestCase):
    def test_risky_checked_then_allow_check_no_signing(self):
        client = StubClient()
        scanner = HatomScanner(client, batch=2, refresh_seconds=3600)
        candidates = scanner.scan()
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["borrower"], client.borrower)
        self.assertEqual(candidate["category"], "ONCHAIN_ELIGIBLE")
        self.assertIsNone(candidate["max_repay_usd"])
        self.assertEqual(candidate["borrow_market"], client.market)
        self.assertIn(("meaningful", 500), client.calls)

    def test_refused_liquidation_stays_at_risk_stage(self):
        client = StubClient()
        client.mode = "refused"
        scanner = HatomScanner(client, batch=2, refresh_seconds=3600)
        found = scanner.scan()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["category"], "ONCHAIN_RISKY")

    def test_initial_market_index_warms_up_over_first_polls(self):
        client = StubClient()
        scanner = HatomScanner(client, batch=1, refresh_seconds=3600)
        scanner.scan()
        self.assertEqual(
            [call for call in client.calls if isinstance(call, tuple) and call[0] == "members"],
            [("members", client.market)]
        )
        scanner.scan()
        self.assertEqual(
            [call for call in client.calls if isinstance(call, tuple) and call[0] == "members"],
            [("members", client.market), ("members", client.collateral)]
        )
        scanner.scan()
        self.assertEqual(
            len([call for call in client.calls if isinstance(call, tuple) and call[0] == "members"]), 2
        )

    def test_no_market_fails_closed(self):
        client = StubClient()
        client.whitelist = lambda: []
        scanner = HatomScanner(client)
        with self.assertRaises(ValueError):
            scanner.scan()


if __name__ == "__main__":
    unittest.main()

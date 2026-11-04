"""Regression: Hatom liquidation transaction preflight is read-only and fail-closed."""
import asyncio
import base64
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch

from core import hatom_dryrun as dry
from core import hatom_liquidations as watch
from core.hatom_onchain import address_encode


BORROWER = address_encode(bytes([1]) * 32)
DEBT = address_encode(bytes([2]) * 32)
COLLATERAL = address_encode(bytes([3]) * 32)
SENDER = address_encode(bytes([4]) * 32)


def position():
    return {
        "borrower": BORROWER, "category": "ONCHAIN_ELIGIBLE",
        "borrow_market": DEBT, "collateral_market": COLLATERAL,
        "repay_raw": 25000000,
    }


class Vm:
    def __init__(self, token="USDC-c76f1f"):
        self.token = token

    def query(self, market, func, args=None):
        if func != "getUnderlyingId":
            raise AssertionError(func)
        return [self.token.encode("ascii")]


class Gateway:
    def __init__(self):
        self.last_tx = None

    def network(self):
        return {"chainID": "1", "gasPrice": 1000000000}

    def sender_nonce(self, sender):
        assert sender == SENDER
        return 7

    def cost(self, tx):
        self.last_tx = tx
        return 18000000

    def simulate(self, tx):
        self.last_tx = tx
        return {"status": "failed_or_incomplete", "reason": "insufficient sender balance"}


class DryRunTests(unittest.TestCase):
    def test_token_payment_call_encoding(self):
        call = dry.liquidation_call(position(), "USDC-c76f1f")
        self.assertEqual(call["value"], "0")
        self.assertEqual(call["payment"], "ESDT")
        self.assertEqual(call["receiver"], DEBT)
        payload = base64.b64decode(call["data"]).decode("ascii")
        parts = payload.split("@")
        self.assertEqual(parts[0], "ESDTTransfer")
        self.assertEqual(bytes.fromhex(parts[1]).decode("ascii"), "USDC-c76f1f")
        self.assertEqual(int(parts[2], 16), 25000000)
        self.assertEqual(bytes.fromhex(parts[3]).decode("ascii"), "liquidateBorrow")
        self.assertEqual(bytes.fromhex(parts[4]), bytes([1]) * 32)
        self.assertEqual(bytes.fromhex(parts[5]), bytes([3]) * 32)

    def test_egld_payment_call_encoding(self):
        call = dry.liquidation_call(position(), "EGLD")
        self.assertEqual(call["value"], "25000000")
        self.assertEqual(call["payment"], "EGLD")
        parts = base64.b64decode(call["data"]).decode("ascii").split("@")
        self.assertEqual(parts[0], "liquidateBorrow")
        self.assertEqual(len(parts), 3)

    def test_not_eligible_cannot_construct(self):
        row = position()
        row["category"] = "ONCHAIN_RISKY"
        with self.assertRaises(dry.DryRunUnavailable):
            dry.liquidation_call(row, "EGLD")
        with self.assertRaises(dry.DryRunUnavailable):
            dry.liquidation_call(position(), "FAKE")

    def test_without_simulation_sender_does_not_call_network(self):
        g = Mock()
        with patch.dict(os.environ, {"HATOM_SIMULATION_SENDER": ""}):
            result = dry.dryrun(position(), vm=Vm(), gateway=g)
        self.assertTrue(result["call_built"])
        self.assertEqual(result["sim_status"], "not_simulated")
        self.assertFalse(result["full_pipeline_simulated"])
        self.assertFalse(result["verified_net_profit"])
        self.assertFalse(result["transaction_sent"])
        g.network.assert_not_called()

    def test_read_only_cost_and_simulation_not_claimed_end_to_end(self):
        gateway = Gateway()
        result = dry.dryrun(position(), vm=Vm(), gateway=gateway, sender=SENDER)
        self.assertEqual(result["liquidation_gas_units"], 18000000)
        self.assertEqual(result["cost_status"], "isolated_liquidation_cost_estimated")
        self.assertEqual(result["sim_status"], "failed_or_incomplete")
        self.assertEqual(result["reason"], "insufficient sender balance")
        self.assertEqual(gateway.last_tx["nonce"], 7)
        self.assertEqual(gateway.last_tx["sender"], SENDER)
        self.assertEqual(gateway.last_tx["receiver"], DEBT)
        self.assertFalse(result["full_pipeline_simulated"])
        self.assertFalse(result["verified_net_profit"])
        self.assertFalse(result["transaction_sent"])
        self.assertIn("NOT SIMULATED", dry.format_report(result))

    def test_gateway_only_calls_get_and_known_read_only_posts(self):
        session = Mock()
        response = Mock()
        response.content = b"{}"
        response.json.return_value = {"code":"successful", "data":{"txGasUnits":"18000000"}}
        session.post.return_value = response
        g = dry.ReadOnlySimulationGateway(session=session)
        gas = g.cost({"sender":SENDER,"receiver":DEBT})
        self.assertEqual(gas,18000000)
        self.assertEqual(session.post.call_args.args[0], "https://gateway.multiversx.com/transaction/cost")
        self.assertFalse(session.post.call_args.kwargs["allow_redirects"])
        with self.assertRaises(dry.DryRunUnavailable):
            g._json("POST", "/transaction/send", body={})
        self.assertEqual(session.post.call_count, 1)

    def test_signature_bypass_simulation_is_not_execution(self):
        session = Mock()
        response = Mock()
        response.content = b"{}"
        response.json.return_value = {
            "code": "successful",
            "data": {"senderShard": {"status": "success"}, "receiverShard": {"status": "success"}},
        }
        session.post.return_value = response
        g = dry.ReadOnlySimulationGateway(session=session)
        report = g.simulate({"sender": SENDER, "receiver": DEBT})
        self.assertEqual(report["status"], "incomplete_cross_shard")
        url = session.post.call_args.args[0]
        self.assertEqual(url, "https://gateway.multiversx.com/transaction/simulate?checkSignature=false")
        self.assertEqual(session.post.call_args.kwargs["json"]["signature"], "00" * 64)
        self.assertNotIn("/send", url)

    def test_simulated_success_still_not_full_pipeline(self):
        class SuccessGateway(Gateway):
            def simulate(self, tx):
                return {"status": "isolated_success", "reason": "only isolated liquidation"}
        result = dry.dryrun(position(), vm=Vm(), gateway=SuccessGateway(), sender=SENDER)
        self.assertEqual(result["sim_status"], "isolated_success")
        self.assertFalse(result["full_pipeline_simulated"])
        self.assertFalse(result["verified_net_profit"])

    def test_admin_only_dryrun_telegram_command(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=42, type="private"),
            effective_user=SimpleNamespace(id=42),
            message=SimpleNamespace(reply_text=AsyncMock(), reply_to_message=None),
        )
        env = {
            "ENABLE_HATOM_WATCH": "true", "HATOM_WATCH_SOURCE": "onchain",
            "ADMIN_TELEGRAM_ID": "42",
        }
        data = dry.dryrun(position(), vm=Vm(), gateway=Gateway(), sender="")
        with patch.dict(os.environ, env), patch.object(
            watch, "_recheck_borrowers_on_demand", return_value=[position()]
        ), patch.object(dry, "dryrun", return_value=data):
            asyncio.run(watch.dryrun_command(update, SimpleNamespace(args=[BORROWER])))
        answer = update.message.reply_text.await_args.args[0]
        self.assertIn("PRIVATE TRANSACTION DRY-RUN", answer)
        self.assertIn("No wallet signing", answer)

    def test_group_cannot_use_dryrun(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=-100123, type="supergroup"),
            effective_user=SimpleNamespace(id=42),
            message=SimpleNamespace(reply_text=AsyncMock(), reply_to_message=None),
        )
        with patch.dict(os.environ, {"ADMIN_TELEGRAM_ID":"42"}), patch.object(
            watch, "_recheck_borrowers_on_demand"
        ) as live:
            asyncio.run(watch.dryrun_command(update, SimpleNamespace(args=[BORROWER])))
        live.assert_not_called()
        update.message.reply_text.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()

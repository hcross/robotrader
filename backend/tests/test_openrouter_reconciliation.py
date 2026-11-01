from __future__ import annotations

import io
import json
import math
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.agents.monitor import LLMMonitorAgent


class _MockStore:
    def __init__(self, pnl: float = 0.0, kill_switch: bool = False):
        self.pnl = pnl
        self.kill_switch_active = kill_switch

    def measured_realized_pnl_usd(self) -> float:
        return float(self.pnl)


class _MockHTTPResponse:
    def __init__(self, body_dict_or_str: dict | str, status: int = 200):
        if isinstance(body_dict_or_str, dict):
            self._body = json.dumps(body_dict_or_str).encode("utf-8")
        else:
            self._body = str(body_dict_or_str).encode("utf-8")
        self.status = status
        self.headers = {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class OpenRouterReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.ledger_path = Path(self._tmpdir.name) / "transcript_ledger.jsonl"
        self.agent = LLMMonitorAgent(
            store=_MockStore(pnl=100.0),
            ledger_path=self.ledger_path,
        )

    # --------------------------------------------------------------------------
    # Scenario: Status payload reports simulated internal ledger provenance by default
    # --------------------------------------------------------------------------
    def test_status_payload_reports_simulated_internal_ledger_by_default(self) -> None:
        status = self.agent.get_status()
        self.assertIn("openrouter_credit", status)
        credit = status["openrouter_credit"]
        self.assertEqual(credit["balance_source"], "SIMULATED_INTERNAL_LEDGER")
        self.assertEqual(credit["reconciliation_status"], "UNRECONCILED")
        self.assertIsNone(credit["last_reconciled_ms"])
        self.assertIsNone(credit["reconciled_balance_usd"])

    # --------------------------------------------------------------------------
    # Scenario: Successful live API probe updates credit balance and provenance
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_successful_live_probe_updates_balance_and_provenance(
        self, mock_urlopen: MagicMock
    ) -> None:
        mock_urlopen.return_value = _MockHTTPResponse({
            "data": {
                "total_credits": 15.50,
                "total_usage": 5.25,
            }
        })

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-live-real-key"}):
            res = self.agent.reconcile_openrouter_credits(timeout_sec=3.0)

        self.assertEqual(res["reconciliation_status"], "RECONCILED_OK")
        self.assertEqual(res["balance_source"], "MEASURED_OPENROUTER_API")
        self.assertEqual(res["openrouter_balance_usd"], 10.25)
        self.assertEqual(res["reconciled_balance_usd"], 10.25)
        self.assertIsInstance(res["last_reconciled_ms"], int)
        self.assertGreater(res["last_reconciled_ms"], 0)
        self.assertEqual(res["reason"], "Reconciliation successful")

        self.assertEqual(self.agent.openrouter_balance_usd, 10.25)
        self.assertEqual(self.agent.balance_source, "MEASURED_OPENROUTER_API")
        self.assertEqual(self.agent.reconciliation_status, "RECONCILED_OK")
        self.assertEqual(self.agent.reconciled_balance_usd, 10.25)

        # Status payload reports measured provenance after successful reconciliation
        status = self.agent.get_status()["openrouter_credit"]
        self.assertEqual(status["balance_source"], "MEASURED_OPENROUTER_API")
        self.assertEqual(status["reconciliation_status"], "RECONCILED_OK")
        self.assertEqual(status["last_reconciled_ms"], res["last_reconciled_ms"])
        self.assertEqual(status["reconciled_balance_usd"], 10.25)

    # --------------------------------------------------------------------------
    # Scenario: Unset or placeholder API key bypasses network probe and reports skipped status
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_placeholder_or_unset_key_bypasses_probe(
        self, mock_urlopen: MagicMock
    ) -> None:
        placeholders = [
            "",
            "your_openrouter_api_key_here",
            "your_key",
            "sk-or-v1-placeholder",
        ]
        initial_balance = self.agent.openrouter_balance_usd

        for ph in placeholders:
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": ph}):
                res = self.agent.reconcile_openrouter_credits()
                self.assertEqual(res["reconciliation_status"], "SKIPPED_NO_API_KEY")
                self.assertEqual(res["balance_source"], "SIMULATED_INTERNAL_LEDGER")
                self.assertEqual(res["openrouter_balance_usd"], initial_balance)
                self.assertEqual(self.agent.balance_source, "SIMULATED_INTERNAL_LEDGER")
                self.assertEqual(self.agent.reconciliation_status, "SKIPPED_NO_API_KEY")
                mock_urlopen.assert_not_called()

        # When OPENROUTER_API_KEY is not in env at all
        with patch.dict(os.environ, {}, clear=True):
            res = self.agent.reconcile_openrouter_credits()
            self.assertEqual(res["reconciliation_status"], "SKIPPED_NO_API_KEY")
            self.assertEqual(res["balance_source"], "SIMULATED_INTERNAL_LEDGER")
            mock_urlopen.assert_not_called()

    # --------------------------------------------------------------------------
    # Scenario: Upstream HTTP error or timeout preserves balance and returns failure status
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_upstream_http_error_preserves_balance(
        self, mock_urlopen: MagicMock
    ) -> None:
        initial_balance = self.agent.openrouter_balance_usd
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/credits",
            code=502,
            msg="Bad Gateway",
            hdrs={},
            fp=io.BytesIO(b"Bad Gateway"),
        )

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-valid-key"}):
            res = self.agent.reconcile_openrouter_credits(timeout_sec=3.0)

        self.assertEqual(res["reconciliation_status"], "RECONCILE_FAILED")
        self.assertEqual(res["balance_source"], "SIMULATED_INTERNAL_LEDGER")
        self.assertEqual(res["openrouter_balance_usd"], initial_balance)
        self.assertIn("502", res["reason"])
        self.assertEqual(self.agent.openrouter_balance_usd, initial_balance)
        self.assertEqual(self.agent.balance_source, "SIMULATED_INTERNAL_LEDGER")

    @patch("urllib.request.urlopen")
    def test_timeout_preserves_balance_and_returns_failure(
        self, mock_urlopen: MagicMock
    ) -> None:
        initial_balance = self.agent.openrouter_balance_usd
        mock_urlopen.side_effect = TimeoutError("Connection timed out after 3.0 seconds")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-valid-key"}):
            res = self.agent.reconcile_openrouter_credits(timeout_sec=3.0)

        self.assertEqual(res["reconciliation_status"], "RECONCILE_FAILED")
        self.assertEqual(res["balance_source"], "SIMULATED_INTERNAL_LEDGER")
        self.assertEqual(res["openrouter_balance_usd"], initial_balance)
        self.assertIn("timed out", res["reason"])
        self.assertEqual(self.agent.openrouter_balance_usd, initial_balance)

    # --------------------------------------------------------------------------
    # Scenario: Malformed or non-finite JSON payload fails safe without mutating balance
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_malformed_json_fails_safe(self, mock_urlopen: MagicMock) -> None:
        initial_balance = self.agent.openrouter_balance_usd
        mock_urlopen.return_value = _MockHTTPResponse("Not a json payload")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-valid-key"}):
            res = self.agent.reconcile_openrouter_credits()

        self.assertEqual(res["reconciliation_status"], "RECONCILE_FAILED")
        self.assertEqual(res["openrouter_balance_usd"], initial_balance)
        self.assertEqual(self.agent.openrouter_balance_usd, initial_balance)

    @patch("urllib.request.urlopen")
    def test_non_finite_values_fail_safe(self, mock_urlopen: MagicMock) -> None:
        initial_balance = self.agent.openrouter_balance_usd
        invalid_payloads = [
            {"data": {"total_credits": "NaN", "total_usage": 0.0}},
            {"data": {"total_credits": float("nan"), "total_usage": 0.0}},
            {"data": {"total_credits": 10.0, "total_usage": float("inf")}},
            {"data": {"total_credits": None, "total_usage": 0.0}},
            {"not_data": {}},
            {"data": "string_instead_of_dict"},
            "raw string",
        ]

        for payload in invalid_payloads:
            mock_urlopen.return_value = _MockHTTPResponse(payload)
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-valid-key"}):
                res = self.agent.reconcile_openrouter_credits()
                self.assertEqual(res["reconciliation_status"], "RECONCILE_FAILED")
                self.assertEqual(res["openrouter_balance_usd"], initial_balance)
                self.assertEqual(self.agent.openrouter_balance_usd, initial_balance)

    # --------------------------------------------------------------------------
    # Scenario: Probe failure following prior successful probe preserves balance and reports failure status
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_probe_failure_after_prior_success_preserves_balance_and_prior_metrics(
        self, mock_urlopen: MagicMock
    ) -> None:
        # Step 1: Successful probe
        mock_urlopen.return_value = _MockHTTPResponse({
            "data": {
                "total_credits": 15.50,
                "total_usage": 5.25,
            }
        })
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-valid-key"}):
            success_res = self.agent.reconcile_openrouter_credits()

        self.assertEqual(success_res["reconciliation_status"], "RECONCILED_OK")
        self.assertEqual(success_res["balance_source"], "MEASURED_OPENROUTER_API")
        self.assertEqual(success_res["openrouter_balance_usd"], 10.25)
        prior_ts = success_res["last_reconciled_ms"]

        # Step 2: Subsequent probe fails due to timeout
        mock_urlopen.side_effect = TimeoutError("Network timeout")
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-valid-key"}):
            fail_res = self.agent.reconcile_openrouter_credits()

        # THEN openrouter_balance_usd remains 10.25
        self.assertEqual(fail_res["openrouter_balance_usd"], 10.25)
        self.assertEqual(self.agent.openrouter_balance_usd, 10.25)
        # THEN balance_source reverts to "SIMULATED_INTERNAL_LEDGER"
        self.assertEqual(fail_res["balance_source"], "SIMULATED_INTERNAL_LEDGER")
        self.assertEqual(self.agent.balance_source, "SIMULATED_INTERNAL_LEDGER")
        # THEN reconciliation_status is "RECONCILE_FAILED"
        self.assertEqual(fail_res["reconciliation_status"], "RECONCILE_FAILED")
        self.assertEqual(self.agent.reconciliation_status, "RECONCILE_FAILED")
        # THEN last_reconciled_ms remains prior timestamp
        self.assertEqual(fail_res["last_reconciled_ms"], prior_ts)
        self.assertEqual(self.agent.last_reconciled_ms, prior_ts)
        self.assertEqual(self.agent.reconciled_balance_usd, 10.25)

        # In get_status()
        status = self.agent.get_status()["openrouter_credit"]
        self.assertEqual(status["balance_source"], "SIMULATED_INTERNAL_LEDGER")
        self.assertEqual(status["reconciliation_status"], "RECONCILE_FAILED")
        self.assertEqual(status["last_reconciled_ms"], prior_ts)
        self.assertEqual(status["reconciled_balance_usd"], 10.25)


class SettlementMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.ledger_path = Path(self._tmpdir.name) / "transcript_ledger.jsonl"
        self.agent = LLMMonitorAgent(
            store=_MockStore(pnl=500.0),
            ledger_path=self.ledger_path,
        )
        # Put balance below watermark so refill is triggered
        self.agent.openrouter_balance_usd = 1.50
        self.agent.low_watermark_usd = 2.00

    # --------------------------------------------------------------------------
    # Scenario: Refill under simulated provenance records simulated ledger increment settlement
    # --------------------------------------------------------------------------
    def test_refill_under_simulated_provenance_records_simulated_ledger_increment(self) -> None:
        self.assertEqual(self.agent.balance_source, "SIMULATED_INTERNAL_LEDGER")
        res = self.agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=200.0,
            amount_usd=10.0,
            force=False,
        )
        self.assertEqual(res["status"], "refilled")
        self.assertEqual(res["settlement_mode"], "SIMULATED_LEDGER_INCREMENT")
        self.assertTrue(res["settlement_receipt_id"].startswith("or-refill-"))

        event = res["event"]
        self.assertEqual(event["settlement_mode"], "SIMULATED_LEDGER_INCREMENT")
        self.assertTrue(event["settlement_receipt_id"].startswith("or-refill-"))
        self.assertEqual(self.agent.refill_history[0]["settlement_mode"], "SIMULATED_LEDGER_INCREMENT")
        self.assertEqual(self.agent.refill_history[0]["settlement_receipt_id"], res["settlement_receipt_id"])

    # --------------------------------------------------------------------------
    # Scenario: Refill under measured provenance records out-of-band operator intent settlement
    # --------------------------------------------------------------------------
    def test_refill_under_measured_provenance_records_out_of_band_intent(self) -> None:
        self.agent.balance_source = "MEASURED_OPENROUTER_API"
        res = self.agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=200.0,
            amount_usd=10.0,
            force=False,
        )
        self.assertEqual(res["status"], "refilled")
        self.assertEqual(res["settlement_mode"], "OPERATOR_OUT_OF_BAND_INTENT")
        self.assertTrue(res["settlement_receipt_id"].startswith("or-refill-"))

        event = res["event"]
        self.assertEqual(event["settlement_mode"], "OPERATOR_OUT_OF_BAND_INTENT")
        self.assertTrue(event["settlement_receipt_id"].startswith("or-refill-"))
        self.assertEqual(self.agent.refill_history[0]["settlement_mode"], "OPERATOR_OUT_OF_BAND_INTENT")
        self.assertEqual(self.agent.refill_history[0]["settlement_receipt_id"], res["settlement_receipt_id"])

    # --------------------------------------------------------------------------
    # Scenario: Consecutive approved refills receive unique and incrementing receipt identifiers
    # --------------------------------------------------------------------------
    def test_consecutive_refills_receive_incrementing_receipt_identifiers(self) -> None:
        self.agent.openrouter_balance_usd = 1.00
        with patch.object(self.agent, "_now_ms", side_effect=[1700000001000, 1700000002000]):
            res1 = self.agent.trigger_openrouter_refill(
                realized_trading_pnl_usd=200.0,
                amount_usd=5.0,
                force=True,
            )
            res2 = self.agent.trigger_openrouter_refill(
                realized_trading_pnl_usd=200.0,
                amount_usd=5.0,
                force=True,
            )

        self.assertEqual(res1["settlement_receipt_id"], "or-refill-1700000001000-001")
        self.assertEqual(res2["settlement_receipt_id"], "or-refill-1700000002000-002")


class ControlPlaneEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        import backend.server as server
        from fastapi.testclient import TestClient

        self.client = TestClient(server.app)

    # --------------------------------------------------------------------------
    # Scenario: Operator invokes on-demand reconciliation endpoint successfully
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_endpoint_reconcile_success(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _MockHTTPResponse({
            "data": {
                "total_credits": 20.00,
                "total_usage": 8.00,
            }
        })

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-live-valid-key"}):
            resp = self.client.post("/api/v1/openrouter/reconcile")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["reconciliation_status"], "RECONCILED_OK")
        self.assertEqual(data["balance_source"], "MEASURED_OPENROUTER_API")
        self.assertEqual(data["openrouter_balance_usd"], 12.0)
        self.assertGreater(data["last_reconciled_ms"], 0)

    # --------------------------------------------------------------------------
    # Scenario: Upstream failure during on-demand reconciliation returns structured fallback without server error
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_endpoint_reconcile_upstream_failure(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/credits",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=io.BytesIO(b"Service Unavailable"),
        )

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-live-valid-key"}):
            resp = self.client.post("/api/v1/openrouter/reconcile")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["reconciliation_status"], "RECONCILE_FAILED")
        self.assertEqual(data["balance_source"], "SIMULATED_INTERNAL_LEDGER")
        self.assertIn("503", data["reason"])

    # --------------------------------------------------------------------------
    # Token Authentication Check on Endpoint
    # --------------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_endpoint_auth_enforcement(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _MockHTTPResponse({
            "data": {
                "total_credits": 20.00,
                "total_usage": 5.00,
            }
        })

        with patch.dict(
            os.environ,
            {
                "ROBOTRADER_API_TOKEN": "secret-operator-token",
                "OPENROUTER_API_KEY": "sk-or-v1-live-valid-key",
            },
        ):
            # Unauthorized request without bearer header
            resp_unauth = self.client.post("/api/v1/openrouter/reconcile")
            self.assertEqual(resp_unauth.status_code, 401)
            self.assertEqual(resp_unauth.json()["detail"], "Invalid or missing API token")

            # Authorized request with valid bearer header
            resp_auth = self.client.post(
                "/api/v1/openrouter/reconcile",
                headers={"Authorization": "Bearer secret-operator-token"},
            )
            self.assertEqual(resp_auth.status_code, 200)
            self.assertEqual(resp_auth.json()["reconciliation_status"], "RECONCILED_OK")


if __name__ == "__main__":
    unittest.main()

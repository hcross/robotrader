"""Comprehensive integration and unit test suite for CostGuard Rust Refill Gate.

Covers all 18 scenarios in `openspec/changes/wire-rust-refill-validator/specs/costguard/spec.md`:
- Authoritative Rust HardRiskGate delegation & 6-step ordering
- Fail-closed behavior on missing or failing binary
- CLI `--validate-refill` argument handling and deterministic output
- Defensive transcript ledger scanning against malformed/non-dict/non-numeric lines
- Honest simulated internal ledger provenance badging
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.agents import monitor as monitor_module
from backend.agents.monitor import LLMMonitorAgent
from backend.core.state_store import resolve_robotrader_binary


class _MockStore:
    def __init__(self, pnl: float = 100.0, kill_switch_active: bool = False) -> None:
        self.pnl = float(pnl)
        self.kill_switch_active = bool(kill_switch_active)

    def measured_realized_pnl_usd(self) -> float:
        return self.pnl


class CostGuardRefillGateIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.tmpdir = Path(self._tmpdir.name)
        self.engine_dir = Path(__file__).resolve().parents[2] / "engine-rs"
        self.binary_path = resolve_robotrader_binary(self.engine_dir)

    def make_agent(
        self,
        store: _MockStore | None = None,
        initial_balance: float = 1.0,
        low_watermark: float = 2.0,
        refill_amount: float = 4.0,
        max_epoch: float = 25.0,
    ) -> LLMMonitorAgent:
        env = {
            "OPENROUTER_INITIAL_BALANCE_USD": str(initial_balance),
            "OPENROUTER_LOW_WATERMARK_USD": str(low_watermark),
            "OPENROUTER_REFILL_AMOUNT_USD": str(refill_amount),
            "OPENROUTER_MAX_EPOCH_REFILL_USD": str(max_epoch),
        }
        with mock.patch.dict(os.environ, env, clear=False):
            return LLMMonitorAgent(
                store=store or _MockStore(pnl=100.0),
                ledger_path=self.tmpdir / "transcript_ledger.jsonl",
            )

    # --------------------------------------------------------------------------
    # Scenario 1: Active kill switch rejects refill in Rust gate
    # --------------------------------------------------------------------------
    def test_scenario_01_active_kill_switch_rejects_refill(self) -> None:
        agent = self.make_agent(store=_MockStore(pnl=100.0, kill_switch_active=True))
        bal_before = agent.openrouter_balance_usd
        epoch_before = agent.epoch_refilled_usd

        res = agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0,
            amount_usd=4.0,
            force=True,
        )

        self.assertEqual(res["status"], "rejected_kill_switch")
        self.assertEqual(agent.openrouter_balance_usd, bal_before)
        self.assertEqual(agent.epoch_refilled_usd, epoch_before)
        self.assertEqual(agent.refill_history, [])

    # --------------------------------------------------------------------------
    # Scenario 2: Non-positive or non-finite realized PnL rejects refill
    # --------------------------------------------------------------------------
    def test_scenario_02_non_positive_or_non_finite_pnl_rejects(self) -> None:
        agent = self.make_agent()
        bal_before = agent.openrouter_balance_usd
        epoch_before = agent.epoch_refilled_usd

        for invalid_pnl in [-5.0, 0.0, float("nan"), float("inf"), float("-inf")]:
            with self.subTest(pnl=invalid_pnl):
                res = agent.trigger_openrouter_refill(
                    realized_trading_pnl_usd=invalid_pnl,
                    amount_usd=4.0,
                    force=True,
                )
                self.assertEqual(res["status"], "rejected_no_realized_profit")
                self.assertEqual(agent.openrouter_balance_usd, bal_before)
                self.assertEqual(agent.epoch_refilled_usd, epoch_before)
                self.assertEqual(agent.refill_history, [])

    # --------------------------------------------------------------------------
    # Scenario 3: Out-of-bounds requested amount rejects refill
    # --------------------------------------------------------------------------
    def test_scenario_03_out_of_bounds_requested_amount_rejects(self) -> None:
        agent = self.make_agent(store=_MockStore(pnl=1000.0))
        bal_before = agent.openrouter_balance_usd
        epoch_before = agent.epoch_refilled_usd

        for bad_amt in [0.0, -1.0, 25.01, float("nan"), float("inf"), float("-inf")]:
            with self.subTest(amount=bad_amt):
                res = agent.trigger_openrouter_refill(
                    realized_trading_pnl_usd=1000.0,
                    amount_usd=bad_amt,
                    force=True,
                )
                self.assertEqual(res["status"], "rejected")
                self.assertEqual(agent.openrouter_balance_usd, bal_before)
                self.assertEqual(agent.epoch_refilled_usd, epoch_before)
                self.assertEqual(agent.refill_history, [])

    # --------------------------------------------------------------------------
    # Scenario 4: Profit share violation rejects refill
    # --------------------------------------------------------------------------
    def test_scenario_04_profit_share_violation_rejects(self) -> None:
        agent = self.make_agent(store=_MockStore(pnl=50.0))
        bal_before = agent.openrouter_balance_usd
        epoch_before = agent.epoch_refilled_usd

        res = agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=50.0,
            amount_usd=10.0,  # 10.0 > 10% of 50.0 ($5.00)
            force=True,
        )

        self.assertEqual(res["status"], "rejected_exceeds_profit_share")
        self.assertEqual(agent.openrouter_balance_usd, bal_before)
        self.assertEqual(agent.epoch_refilled_usd, epoch_before)
        self.assertEqual(agent.refill_history, [])

    # --------------------------------------------------------------------------
    # Scenario 5: Sufficient balance skips non-forced refill
    # --------------------------------------------------------------------------
    def test_scenario_05_sufficient_balance_skips_non_forced(self) -> None:
        agent = self.make_agent(initial_balance=3.0, low_watermark=2.0)
        bal_before = agent.openrouter_balance_usd

        res = agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0,
            amount_usd=4.0,
            force=False,
        )

        self.assertEqual(res["status"], "skipped_sufficient_balance")
        self.assertEqual(agent.openrouter_balance_usd, bal_before)
        self.assertEqual(agent.epoch_refilled_usd, 0.0)
        self.assertEqual(agent.refill_history, [])

    # --------------------------------------------------------------------------
    # Scenario 6: Forced refill bypasses watermark check when profitable
    # --------------------------------------------------------------------------
    def test_scenario_06_forced_refill_bypasses_watermark(self) -> None:
        agent = self.make_agent(initial_balance=3.0, low_watermark=2.0)
        bal_before = agent.openrouter_balance_usd

        res = agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0,
            amount_usd=4.0,
            force=True,
        )

        self.assertEqual(res["status"], "refilled")
        self.assertEqual(res["refilled_usd"], 4.0)
        self.assertAlmostEqual(agent.openrouter_balance_usd, bal_before + 4.0, places=4)
        self.assertEqual(len(agent.refill_history), 1)

    # --------------------------------------------------------------------------
    # Scenario 7: Epoch cap violation rejects refill
    # --------------------------------------------------------------------------
    def test_scenario_07_epoch_cap_violation_rejects(self) -> None:
        agent = self.make_agent(max_epoch=25.0)
        # Pre-seed epoch spend with $23.00
        now_ms = agent._now_ms()
        agent._epoch_window.append((now_ms, 23.0))
        bal_before = agent.openrouter_balance_usd

        res = agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0,
            amount_usd=4.0,  # 23.0 + 4.0 > 25.0
            force=True,
        )

        self.assertEqual(res["status"], "rejected_epoch_cap")
        self.assertEqual(agent.openrouter_balance_usd, bal_before)
        self.assertEqual(agent.epoch_refilled_usd, 23.0)
        self.assertEqual(agent.refill_history, [])

    # --------------------------------------------------------------------------
    # Scenario 8: Valid refill passes all checks and stamps Rust validator provenance
    # --------------------------------------------------------------------------
    def test_scenario_08_valid_refill_stamps_rust_validator_provenance(self) -> None:
        agent = self.make_agent(initial_balance=1.0, low_watermark=2.0)
        res = agent.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0,
            amount_usd=4.0,
            force=False,
            source="MASTER_ORCHESTRATOR",
            reason="Watermark breached top-up",
        )

        self.assertEqual(res["status"], "refilled")
        self.assertEqual(res["refilled_usd"], 4.0)
        self.assertAlmostEqual(agent.openrouter_balance_usd, 5.0, places=4)
        self.assertEqual(len(agent.refill_history), 1)
        event = agent.refill_history[0]
        self.assertEqual(event["validator"], "RUST_HARD_RISK_GATE")
        self.assertEqual(event["amount_usd"], 4.0)
        self.assertEqual(event["source"], "MASTER_ORCHESTRATOR")
        self.assertEqual(event["reason"], "Watermark breached top-up")

    # --------------------------------------------------------------------------
    # Scenario 9: Validator execution failure fails closed
    # --------------------------------------------------------------------------
    def test_scenario_09_validator_execution_failure_fails_closed(self) -> None:
        agent = self.make_agent()
        bal_before = agent.openrouter_balance_usd
        epoch_before = agent.epoch_refilled_usd

        # Test A: binary missing
        with mock.patch("backend.agents.monitor.resolve_robotrader_binary", side_effect=FileNotFoundError("missing")):
            res = agent.trigger_openrouter_refill(realized_trading_pnl_usd=100.0, amount_usd=4.0, force=True)
            self.assertEqual(res["status"], "rejected_validator_unavailable")
            self.assertEqual(agent.openrouter_balance_usd, bal_before)
            self.assertEqual(agent.epoch_refilled_usd, epoch_before)

        # Test B: binary exits non-zero
        bad_exit = mock.Mock(returncode=2, stderr="Simulation error", stdout="")
        with mock.patch("backend.agents.monitor._subprocess_run", return_value=bad_exit):
            res = agent.trigger_openrouter_refill(realized_trading_pnl_usd=100.0, amount_usd=4.0, force=True)
            self.assertEqual(res["status"], "rejected_validator_unavailable")
            self.assertIn("code 2", res["reason"])
            self.assertEqual(agent.openrouter_balance_usd, bal_before)

        # Test C: subprocess raises TimeoutExpired
        with mock.patch("backend.agents.monitor._subprocess_run", side_effect=subprocess.TimeoutExpired(cmd="node", timeout=5.0)):
            res = agent.trigger_openrouter_refill(realized_trading_pnl_usd=100.0, amount_usd=4.0, force=True)
            self.assertEqual(res["status"], "rejected_validator_unavailable")
            self.assertEqual(agent.openrouter_balance_usd, bal_before)

        # Test D: malformed JSON stdout
        bad_json = mock.Mock(returncode=0, stdout="{invalid_json}", stderr="")
        with mock.patch("backend.agents.monitor._subprocess_run", return_value=bad_json):
            res = agent.trigger_openrouter_refill(realized_trading_pnl_usd=100.0, amount_usd=4.0, force=True)
            self.assertEqual(res["status"], "rejected_validator_unavailable")
            self.assertEqual(agent.openrouter_balance_usd, bal_before)


class NodeCLIRefillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine_dir = Path(__file__).resolve().parents[2] / "engine-rs"
        cls.binary_path = resolve_robotrader_binary(cls.engine_dir)

    def run_cli(self, payload: str | None) -> subprocess.CompletedProcess[str]:
        cmd = [str(self.binary_path), "--validate-refill"]
        if payload is not None:
            cmd.append(payload)
        return subprocess.run(cmd, capture_output=True, text=True)

    # --------------------------------------------------------------------------
    # Scenario 10: CLI returns approved verdict for valid parameters
    # --------------------------------------------------------------------------
    def test_scenario_10_cli_approved_verdict(self) -> None:
        payload = json.dumps({
            "requested_usd": 5.0,
            "realized_trading_pnl_usd": 100.0,
            "current_balance_usd": 1.0,
            "low_watermark_usd": 2.0,
            "epoch_refilled_usd": 0.0,
            "max_epoch_refill_usd": 25.0,
            "force": False,
        })
        proc = self.run_cli(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertTrue(out["approved"])
        self.assertEqual(out["status"], "refilled")
        self.assertEqual(out["approved_usd"], 5.0)

    # --------------------------------------------------------------------------
    # Scenario 11: CLI returns rejection verdict for exceeding profit share
    # --------------------------------------------------------------------------
    def test_scenario_11_cli_exceeds_profit_share(self) -> None:
        payload = json.dumps({
            "requested_usd": 5.0,
            "realized_trading_pnl_usd": 20.0,  # 10% is $2.00
            "current_balance_usd": 1.0,
            "low_watermark_usd": 2.0,
            "epoch_refilled_usd": 0.0,
            "max_epoch_refill_usd": 25.0,
            "force": False,
        })
        proc = self.run_cli(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertFalse(out["approved"])
        self.assertEqual(out["status"], "rejected_exceeds_profit_share")
        self.assertEqual(out["approved_usd"], 0.0)

    # --------------------------------------------------------------------------
    # Scenario 12: CLI returns skip verdict for sufficient balance
    # --------------------------------------------------------------------------
    def test_scenario_12_cli_skipped_sufficient_balance(self) -> None:
        payload = json.dumps({
            "requested_usd": 5.0,
            "realized_trading_pnl_usd": 100.0,
            "current_balance_usd": 3.0,
            "low_watermark_usd": 2.0,
            "epoch_refilled_usd": 0.0,
            "max_epoch_refill_usd": 25.0,
            "force": False,
        })
        proc = self.run_cli(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertFalse(out["approved"])
        self.assertEqual(out["status"], "skipped_sufficient_balance")
        self.assertEqual(out["approved_usd"], 0.0)

    # --------------------------------------------------------------------------
    # Scenario 13: CLI exits non-zero on malformed JSON payload
    # --------------------------------------------------------------------------
    def test_scenario_13_cli_exits_nonzero_on_malformed_json(self) -> None:
        proc = self.run_cli("{not_valid_json}")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("failed to parse --validate-refill JSON", proc.stderr)

        # Missing argument flag also exits with code 2
        proc_missing = self.run_cli(None)
        self.assertEqual(proc_missing.returncode, 2)


class LedgerHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.ledger_path = Path(self._tmpdir.name) / "transcript_ledger.jsonl"
        self.agent = LLMMonitorAgent(
            store=_MockStore(pnl=100.0),
            ledger_path=self.ledger_path,
        )

    # --------------------------------------------------------------------------
    # Scenario 14: Non-dict JSON entries are skipped without exception
    # --------------------------------------------------------------------------
    def test_scenario_14_non_dict_json_entries_skipped(self) -> None:
        now_ms = self.agent._now_ms()
        lines = [
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 100, "completion_tokens": 50, "cost_usd": 0.10}),
            "42",
            "[1, 2, 3]",
            "true",
            '"raw string"',
            "null",
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 200, "completion_tokens": 100, "cost_usd": 0.20}),
        ]
        self.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = self.agent.hydrate_from_ledger()
        self.assertEqual(result["hydrated_calls"], 2)
        self.assertAlmostEqual(result["hydrated_cost_usd"], 0.30, places=4)

    # --------------------------------------------------------------------------
    # Scenario 15: Non-numeric and non-finite token or cost entries are skipped without exception
    # --------------------------------------------------------------------------
    def test_scenario_15_non_numeric_and_non_finite_entries_skipped(self) -> None:
        now_ms = self.agent._now_ms()
        lines = [
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 100, "completion_tokens": 50, "cost_usd": 0.10}),
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": "unparsed", "completion_tokens": 50, "cost_usd": 0.10}),
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 100, "completion_tokens": "bogus", "cost_usd": 0.10}),
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 100, "completion_tokens": 50, "cost_usd": "NaN"}),
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 100, "completion_tokens": 50, "cost_usd": float("inf")}),
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 100, "completion_tokens": 50, "cost_usd": -1.0}),
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 200, "completion_tokens": 100, "cost_usd": 0.20}),
        ]
        self.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = self.agent.hydrate_from_ledger()
        self.assertEqual(result["hydrated_calls"], 2)
        self.assertAlmostEqual(result["hydrated_cost_usd"], 0.30, places=4)
        self.assertTrue(math.isfinite(self.agent.total_cost_usd))

    # --------------------------------------------------------------------------
    # Scenario 16: Valid entries around malformed lines are preserved in spend window
    # --------------------------------------------------------------------------
    def test_scenario_16_valid_entries_around_malformed_lines_preserved(self) -> None:
        now_ms = self.agent._now_ms()
        lines = [
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 100, "completion_tokens": 50, "cost_usd": 1.25}),
            "123",
            json.dumps({"timestamp_ms": now_ms, "prompt_tokens": 200, "completion_tokens": 100, "cost_usd": 2.50}),
        ]
        self.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = self.agent.hydrate_from_ledger()
        self.assertEqual(result["hydrated_calls"], 2)
        self.assertAlmostEqual(result["hydrated_cost_usd"], 3.75, places=4)


class ProvenanceStatusAndUIBadgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.agent = LLMMonitorAgent(
            store=_MockStore(pnl=100.0),
            ledger_path=Path(self._tmpdir.name) / "transcript_ledger.jsonl",
        )

    # --------------------------------------------------------------------------
    # Scenario 17: Status payload reports simulated internal ledger provenance
    # --------------------------------------------------------------------------
    def test_scenario_17_status_payload_reports_simulated_provenance(self) -> None:
        status = self.agent.get_status()
        self.assertIn("openrouter_credit", status)
        credit = status["openrouter_credit"]
        self.assertEqual(
            credit["balance_source"],
            "SIMULATED_INTERNAL_LEDGER",
        )
        self.assertEqual(credit["reconciliation_status"], "UNRECONCILED")
        self.assertIsNone(credit["last_reconciled_ms"])
        self.assertIsNone(credit["reconciled_balance_usd"])

    # --------------------------------------------------------------------------
    # Scenario 18: MasterOverview renders simulated ledger provenance badge
    # --------------------------------------------------------------------------
    def test_scenario_18_master_overview_contains_simulated_provenance_badge(self) -> None:
        master_overview_path = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "src"
            / "components"
            / "MasterOverview.jsx"
        )
        content = master_overview_path.read_text(encoding="utf-8")
        self.assertIn("SIMULATED_INTERNAL_LEDGER", content)
        self.assertIn("openrouterCredit.balance_source", content)


if __name__ == "__main__":
    unittest.main()

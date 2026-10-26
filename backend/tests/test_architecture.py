import tempfile
import unittest
from pathlib import Path

from backend.agents.orchestrator import OrchestratorAgent
from backend.core.schemas import PolicyEnvelope
from backend.core.state_store import HybridStateStore


class TestHybridArchitectureV2(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.store = HybridStateStore()
        self.orchestrator = OrchestratorAgent(
            store=self.store,
            ledger_path=Path(self._tmpdir.name) / "transcript_ledger.jsonl",
        )

    def test_policy_ttl_expiration_falls_back_to_safe_baseline(self) -> None:
        env = PolicyEnvelope.default_active(now_ms=1_000_000)
        env.ttl_seconds = 60
        self.store.set_policy(env)

        # Within TTL
        active = self.store.get_effective_policy(now_ms=1_030_000)
        self.assertEqual(active.global_regime, "RISK_ON_HIGH_VOL")

        # Expired TTL -> Safe Baseline Fallback
        expired = self.store.get_effective_policy(now_ms=1_070_000)
        self.assertEqual(expired.envelope_id, "safe_baseline_fallback")
        self.assertEqual(expired.global_regime, "LOW_VOL_CARRY")
        self.assertFalse(expired.pod_allocations["pod_sniper"].enabled)

    def test_cost_guard_hard_cap_and_truthful_auto_refill_label(self) -> None:
        status = self.orchestrator.cost_guard.get_status()
        self.assertEqual(status["auto_wallet_refill"], "ENABLED_PROFIT_GATED")
        self.assertEqual(
            status["auto_refill_policy"], "PROFIT_GATED_CAPPED_BY_ORCHESTRATOR"
        )
        self.assertFalse(status["budget_exhausted"])

        self.orchestrator.cost_guard.auto_refill_enabled = False
        disabled = self.orchestrator.cost_guard.get_status()
        self.assertEqual(disabled["auto_wallet_refill"], "DISABLED")
        self.assertEqual(disabled["auto_refill_policy"], "DISABLED")
        self.orchestrator.cost_guard.auto_refill_enabled = True

        # No measured profit: the automatic gate refuses, but the hard daily cap
        # still binds the rolling spend window.
        self.orchestrator.cost_guard.record_usage(
            {"agent": "CatalystScout", "cost": 10.0, "tokens": 50000}
        )
        self.assertTrue(self.orchestrator.cost_guard.budget_exhausted)
        self.assertEqual(self.orchestrator.cost_guard.refill_history, [])

    def test_python_to_rust_backtest_bridge_and_regime_switching(self) -> None:
        # Capture the envelope the bridge serializes for Rust, before the binary runs.
        captured_policy = {}
        real_run_rust_backtest = self.store.run_rust_backtest

        def capture_policy(*args, **kwargs):
            captured_policy["policy"] = self.store.get_effective_policy()
            return real_run_rust_backtest(*args, **kwargs)

        self.store.run_rust_backtest = capture_policy

        # 1. Full swarm regime (all 4 pods active)
        resp_full = self.orchestrator.process_user_command("set full swarm")
        self.assertEqual(resp_full["action"], "REGIME_UPDATED")

        bridge_policy = captured_policy["policy"]
        for symbol in ("SOL-USDT", "JUP-USDT"):
            rule = bridge_policy.asset_overrides[symbol]
            self.assertEqual(rule.entry_obi_threshold, 0.08)
            self.assertEqual(rule.max_rsi_long, 70.0)
            self.assertEqual(rule.min_rsi_short, 30.0)
            self.assertEqual(rule.take_profit_bps, 45.0)
            self.assertEqual(rule.stop_loss_bps, 30.0)
            self.assertIsNone(rule.support_zone_usd)
            self.assertIsNone(rule.resistance_zone_usd)
            self.assertIsNone(rule.invalidation_price_usd)

        bt_full = resp_full["backtest"]
        # Regenerated from the cost-aware hurdle: two orders now fail the
        # execution-cost hurdle and SCAM-SOL still fails the anti-rug gate.
        self.assertEqual(bt_full["total_trades"], 4)
        self.assertEqual(bt_full["rejected_orders"], 3)
        self.assertEqual(bt_full["artifact_kind"], "policy_sanity_check")
        self.assertEqual(bt_full["source"], "FIXTURE")
        self.assertIs(bt_full["fill_simulation"], False)
        # Plumbing invariant, not a performance target or evidence of edge:
        # per-pod attribution is the accounting view of net profit.
        self.assertAlmostEqual(
            sum(bt_full["pod_pnl_attribution"].values()),
            bt_full["net_profit_usd"],
            places=9,
        )

        # 2. Defensive Carry regime (only Pod 1 & Pod 2 enabled)
        resp_def = self.orchestrator.process_user_command("switch to defensive carry")
        bt_def = resp_def["backtest"]
        self.assertEqual(bt_def["total_trades"], 4)  # Pods 3 & 4 disabled -> 0 Solana meme trades
        self.assertEqual(bt_def["artifact_kind"], "policy_sanity_check")

        # 3. Hard Kill-Switch lockdown -> 0 trades executed in Rust engine
        resp_kill = self.orchestrator.process_user_command("activate kill switch")
        self.assertEqual(resp_kill["action"], "KILL_SWITCH_ACTIVATED")
        bt_kill = self.store.run_rust_backtest()
        self.assertEqual(bt_kill["total_trades"], 0)
        self.assertEqual(bt_kill["artifact_kind"], "policy_sanity_check")
        self.assertIs(bt_kill["fill_simulation"], False)

    def test_pro_ta_engine_and_budget_driven_cognitive_depth(self) -> None:
        from backend.tools.ta_tools import TechnicalAnalysisTool

        candles = [
            [1700000000000 + i * 900000, 80.0 + i * 0.2, 81.0 + i * 0.2, 79.5 + i * 0.2, 80.5 + i * 0.2, 1200.0]
            for i in range(60)
        ]
        snap = TechnicalAnalysisTool.analyze_candles("SOL/USDT", candles, obi=0.22, timeframe="15m")
        self.assertIn("ichimoku", snap)
        self.assertIn("fibonacci", snap)
        self.assertIn("rsi", snap)
        self.assertEqual(snap["ichimoku"]["kumo_regime"], "ABOVE_KUMO_BULLISH")
        self.assertGreater(snap["fibonacci"]["golden_pocket_618"], 0.0)

        # Verify budget-driven cognitive depth transitions
        cg = self.orchestrator.cost_guard
        self.assertEqual(cg.get_thinking_depth(), "DEEP_THESIS")
        cg.record_usage({"agent": "test", "cost": 3.0, "tokens": 1000})  # 40% remaining
        self.assertEqual(cg.get_thinking_depth(), "TACTICAL_FOCUS")
        cg.record_usage({"agent": "test", "cost": 1.5, "tokens": 1000})  # 10% remaining
        self.assertEqual(cg.get_thinking_depth(), "ECO_CONSERVATION")
        cg.record_usage({"agent": "test", "cost": 0.4, "tokens": 1000})  # 2% remaining
        self.assertEqual(cg.get_thinking_depth(), "DETERMINISTIC_LOCK")


if __name__ == "__main__":
    unittest.main()

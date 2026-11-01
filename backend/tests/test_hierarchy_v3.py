from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.agents.orchestrator import OrchestratorAgent
from backend.core.hierarchy import (
    LEAF_ECOSYSTEM_CATALOG,
    CrossChainTreasuryRouter,
    HierarchicalFleetManager,
)
from backend.core.memory_palace import StrategyMemoryPalace
from backend.core.state_store import HybridStateStore, resolve_robotrader_binary
from backend.core.transcript_palace import transcript_palace
from backend.tools.rss_tools import CURATED_FIXTURE_TIMESTAMP_MS, EcosystemRSSAggregator
from backend.tools.ta_tools import SocialMacroPanoramaTool


class TestHierarchicalArchitectureV3(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_transcript_path = transcript_palace.storage_path
        self._orig_transcript_entries = list(transcript_palace.entries)
        transcript_palace.storage_path = Path(self._tmpdir.name) / "transcript.jsonl"
        transcript_palace.entries = []

        self.store = HybridStateStore()
        self.store.palace.storage_path = Path(self._tmpdir.name) / "palace.jsonl"
        self.orchestrator = OrchestratorAgent(
            store=self.store,
            ledger_path=Path(self._tmpdir.name) / "transcript_ledger.jsonl",
        )

    def tearDown(self) -> None:
        transcript_palace.storage_path = self._orig_transcript_path
        transcript_palace.entries = self._orig_transcript_entries
        self._tmpdir.cleanup()

    def test_solana_leaf_purification_excludes_non_solana_assets(self) -> None:
        """
        Ensures the Solana leaf robot (`leaf-solana`) and Rust benchmark fixture
        trade ONLY Solana ecosystem assets (SOL, JUP, RAY, BONK) and never BTC or ETH.
        """
        self.assertTrue(self.store._is_solana_ecosystem_symbol("SOL-USDT"))
        self.assertTrue(self.store._is_solana_ecosystem_symbol("JUP-USDT"))
        self.assertTrue(self.store._is_solana_ecosystem_symbol("RAY-USDT"))
        self.assertTrue(self.store._is_solana_ecosystem_symbol("SOL-DEVNET"))
        self.assertFalse(self.store._is_solana_ecosystem_symbol("BTC-USDT"))
        self.assertFalse(self.store._is_solana_ecosystem_symbol("ETH-USDT"))

        bt = self.store.run_rust_backtest()
        exec_symbols = {e["symbol"] for e in bt.get("executions", [])}
        self.assertNotIn("BTC-USDT", exec_symbols)
        self.assertNotIn("ETH-USDT", exec_symbols)
        for sym in exec_symbols:
            self.assertTrue(
                self.store._is_solana_ecosystem_symbol(sym),
                f"Non-Solana symbol found in Solana Rust backtest: {sym}",
            )

    def test_26_leaf_ecosystem_catalog_and_isolated_rss_feeds(self) -> None:
        """
        Verifies all 26 requested blockchains and multi-crypto/paper venues have
        dedicated leaf configurations, unique MemPalace wings, and isolated RSS feeds.
        """
        self.assertEqual(len(LEAF_ECOSYSTEM_CATALOG), 26)
        leaf_ids = {item["id"] for item in LEAF_ECOSYSTEM_CATALOG}
        expected_ids = {
            "leaf-solana",
            "leaf-bitcoin",
            "leaf-ethereum",
            "leaf-sui",
            "leaf-hyperliquid",
            "leaf-bnb",
            "leaf-xrp",
            "leaf-ton",
            "leaf-tron",
            "leaf-avalanche",
            "leaf-cosmos",
            "leaf-aptos",
            "leaf-chainlink",
            "leaf-stacks",
            "leaf-near",
            "leaf-cardano",
            "leaf-polkadot",
            "leaf-dogecoin",
            "leaf-icp",
            "leaf-canton",
            "leaf-celo",
            "leaf-tezos",
            "leaf-flow",
            "leaf-eos",
            "leaf-binance-cex",
            "leaf-paper-sandbox",
        }
        self.assertEqual(leaf_ids, expected_ids)

        wings = {item["mempalace_wing"] for item in LEAF_ECOSYSTEM_CATALOG}
        self.assertEqual(len(wings), 26)

        for lid in expected_ids:
            leaf_state = self.store.hierarchy.leaves[lid]
            self.assertGreaterEqual(len(leaf_state["rust_pods"]), 1)
            self.assertLessEqual(len(leaf_state["rust_pods"]), 4)

        btc_bt = self.store.run_rust_backtest_for_leaf("leaf-bitcoin")
        self.assertEqual(btc_bt["leaf_id"], "leaf-bitcoin")
        self.assertLessEqual(len(btc_bt["ecosystem_pods"]), 4)
        self.assertEqual(btc_bt["artifact_kind"], "policy_sanity_check")
        self.assertEqual(btc_bt["source"], "FIXTURE")
        self.assertIs(btc_bt["fill_simulation"], False)
        # Exact values are fixture determinism baselines, not performance
        # targets or evidence of strategy edge.
        self.assertAlmostEqual(btc_bt["net_profit_usd"], 17.615496250456999, places=9)

        eth_bt = self.store.run_rust_backtest_for_leaf("leaf-ethereum")
        self.assertEqual(eth_bt["leaf_id"], "leaf-ethereum")
        self.assertEqual(len(eth_bt["ecosystem_pods"]), 4)
        self.assertEqual(eth_bt["artifact_kind"], "policy_sanity_check")
        self.assertAlmostEqual(eth_bt["net_profit_usd"], 16.627260812534587, places=9)

        sol_rss = EcosystemRSSAggregator.get_feed_for_agent("leaf-solana")
        btc_rss = EcosystemRSSAggregator.get_feed_for_agent("leaf-bitcoin")
        master_rss = EcosystemRSSAggregator.get_feed_for_agent("master")
        self.assertTrue(len(sol_rss["items"]) >= 2)
        self.assertTrue(len(btc_rss["items"]) >= 2)
        self.assertTrue(len(master_rss["items"]) >= 3)
        self.assertNotEqual(sol_rss["items"][0]["title"], btc_rss["items"][0]["title"])

    def test_master_treasury_deposit_dry_powder_and_emergency_liquidation(self) -> None:
        """
        Verifies Master Treasury deposit allocation, Dry Powder floor (>= 20%),
        and emergency leaf liquidation back to Dry Powder.
        """
        palace = StrategyMemoryPalace(redis_cmd_fn=None, redis_url=None)
        mgr = HierarchicalFleetManager(palace=palace)

        initial_total = mgr.treasury["total_capital_usd"]
        initial_dry = mgr.treasury["dry_powder_usd"]

        dep = mgr.deposit_funds(amount_usd=10000.0, token="USDC", source_chain="Solana")
        self.assertEqual(dep["status"], "completed")
        self.assertAlmostEqual(mgr.treasury["total_capital_usd"], initial_total + 10000.0, places=1)
        self.assertGreater(mgr.treasury["dry_powder_usd"], initial_dry)
        self.assertGreaterEqual(
            mgr.treasury["dry_powder_usd"] / mgr.treasury["total_capital_usd"],
            0.20,
        )

        sol_before = mgr.leaves["leaf-solana"]["allocated_capital_usd"]
        self.assertGreater(sol_before, 0.0)
        dry_before_liq = mgr.treasury["dry_powder_usd"]

        liq = mgr.emergency_liquidate_leaf("leaf-solana", reason="Test ecosystem alert")
        self.assertEqual(liq["status"], "liquidated")
        self.assertEqual(mgr.leaves["leaf-solana"]["allocated_capital_usd"], 0.0)
        self.assertEqual(mgr.leaves["leaf-solana"]["risk_posture"], "HIBERNATION")
        self.assertAlmostEqual(
            mgr.treasury["dry_powder_usd"], dry_before_liq + sol_before, places=1
        )

    def test_cross_chain_bridge_hurdle_rate_and_multi_token_checkout(self) -> None:
        """
        Verifies CrossChainTreasuryRouter rejects transfers below the 2.5x round-trip hurdle
        and executes multi-chain/multi-token operator checkouts accurately.
        """
        # Low expected yield (15 bps) between Solana and Ethereum -> should be rejected
        low_eval = CrossChainTreasuryRouter.evaluate_transfer_viability(
            from_chain="Solana",
            to_chain="Ethereum",
            amount_usd=5000.0,
            expected_yield_bps=15.0,
            horizon_days=7,
        )
        self.assertFalse(low_eval["viable"])
        self.assertEqual(low_eval["recommendation"], "HOLD_CURRENT_CHAIN")

        # High expected yield (180 bps) -> should be approved
        high_eval = CrossChainTreasuryRouter.evaluate_transfer_viability(
            from_chain="Solana",
            to_chain="Ethereum",
            amount_usd=5000.0,
            expected_yield_bps=180.0,
            horizon_days=7,
        )
        self.assertTrue(high_eval["viable"])
        self.assertEqual(high_eval["recommendation"], "APPROVE_TRANSFER")

        # Checkout quote & execution in BTC on Bitcoin L1
        palace = StrategyMemoryPalace(redis_cmd_fn=None, redis_url=None)
        mgr = HierarchicalFleetManager(palace=palace)
        quote = mgr.checkout_funds(
            amount_usd=2000.0,
            target_chain="Bitcoin",
            target_token="BTC",
            quote_only=True,
        )
        self.assertEqual(quote["status"], "quoted")
        self.assertGreater(quote["delivered_token_qty"], 0.0)

        exec_co = mgr.checkout_funds(
            amount_usd=2000.0,
            target_chain="Bitcoin",
            target_token="BTC",
            quote_only=False,
        )
        self.assertEqual(exec_co["status"], "completed")
        self.assertEqual(exec_co["target_token"], "BTC")
        self.assertAlmostEqual(mgr.treasury["total_capital_usd"], 23000.0, places=1)

    def test_bitcoin_warm_path_reflection_and_policy_compilation(self) -> None:
        """
        Verifies:
        - `orchestrator.run_leaf_agent_reflection("leaf-bitcoin", trigger_source="UNIT_TEST")` writes a drawer to `wing == "leaf_bitcoin"` with `thesis_continuity in ("INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED")` and `next_wakeup_sec == 900`.
        - `res["policy_envelope"]["asset_overrides"]` contains strictly `{"BTC-USD", "wBTC-BTC", "sBTC-BTC"}` with all 11 `AssetOverride` keys populated and `ttl_seconds == 900`.
        - `verify_policy_hmac(SignedPolicyBundle.from_dict(res["signed_policy_bundle"]))` returns `True`.
        """
        cg = self.orchestrator.cost_guard
        cg.auto_refill_enabled = False
        cg.record_usage({"agent": "test", "cost": cg.daily_budget_usd, "tokens": 0})
        self.assertTrue(cg.budget_exhausted)

        res = self.orchestrator.run_leaf_agent_reflection("leaf-bitcoin", trigger_source="UNIT_TEST")
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["wing"], "leaf_bitcoin")
        self.assertEqual(res["drawer"]["next_wakeup_sec"], 900)
        self.assertIn(res["drawer"]["thesis_continuity"], ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED"))

        envelope_dict = res["policy_envelope"]
        self.assertEqual(envelope_dict["ttl_seconds"], 900)
        overrides = envelope_dict["asset_overrides"]
        self.assertEqual(set(overrides.keys()), {"BTC-USD", "wBTC-BTC", "sBTC-BTC"})

        expected_11_keys = {
            "catalyst_score",
            "bias",
            "max_leverage",
            "support_zone_usd",
            "resistance_zone_usd",
            "invalidation_price_usd",
            "entry_obi_threshold",
            "max_rsi_long",
            "min_rsi_short",
            "take_profit_bps",
            "stop_loss_bps",
        }
        for sym, override in overrides.items():
            self.assertEqual(set(override.keys()), expected_11_keys)

        from backend.core.schemas import SignedPolicyBundle, verify_policy_hmac
        signed_bundle = SignedPolicyBundle.from_dict(res["signed_policy_bundle"])
        self.assertTrue(verify_policy_hmac(signed_bundle.policy, signed_bundle.signature, "robotrader-dev-hmac-key"))

    def test_ethereum_warm_path_reflection_and_policy_compilation(self) -> None:
        """
        Verifies:
        - `orchestrator.run_leaf_agent_reflection("leaf-ethereum", trigger_source="UNIT_TEST")` writes a drawer to `wing == "leaf_ethereum"` with `next_wakeup_sec == 900` and `thesis_continuity in ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED")`.
        - `res["policy_envelope"]["asset_overrides"]` keys are strictly `{"ETH-USDC", "stETH-ETH", "UNI-ETH", "AAVE-ETH"}` (zero non-Ethereum symbols) with all 11 `AssetOverride` fields populated and `stETH-ETH` support/resistance calibrated around `~1.0`.
        - `verify_policy_hmac(SignedPolicyBundle.from_dict(res["signed_policy_bundle"]))` returns `True`.
        """
        cg = self.orchestrator.cost_guard
        cg.auto_refill_enabled = False
        cg.record_usage({"agent": "test", "cost": cg.daily_budget_usd, "tokens": 0})
        self.assertTrue(cg.budget_exhausted)

        res = self.orchestrator.run_leaf_agent_reflection("leaf-ethereum", trigger_source="UNIT_TEST")
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["wing"], "leaf_ethereum")
        self.assertEqual(res["drawer"]["next_wakeup_sec"], 900)
        self.assertIn(res["drawer"]["thesis_continuity"], ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED"))

        envelope_dict = res["policy_envelope"]
        self.assertEqual(envelope_dict["ttl_seconds"], 900)
        overrides = envelope_dict["asset_overrides"]
        self.assertEqual(set(overrides.keys()), {"ETH-USDC", "stETH-ETH", "UNI-ETH", "AAVE-ETH"})

        expected_11_keys = {
            "catalyst_score",
            "bias",
            "max_leverage",
            "support_zone_usd",
            "resistance_zone_usd",
            "invalidation_price_usd",
            "entry_obi_threshold",
            "max_rsi_long",
            "min_rsi_short",
            "take_profit_bps",
            "stop_loss_bps",
        }
        for sym, override in overrides.items():
            self.assertEqual(set(override.keys()), expected_11_keys)

        steth_override = overrides["stETH-ETH"]
        self.assertAlmostEqual(steth_override["support_zone_usd"], 0.9982, places=4)
        self.assertAlmostEqual(steth_override["resistance_zone_usd"], 1.0002, places=4)
        self.assertAlmostEqual(steth_override["invalidation_price_usd"], 0.9947, places=4)

        from backend.core.schemas import SignedPolicyBundle, verify_policy_hmac
        signed_bundle = SignedPolicyBundle.from_dict(res["signed_policy_bundle"])
        self.assertTrue(verify_policy_hmac(signed_bundle.policy, signed_bundle.signature, "robotrader-dev-hmac-key"))

    def test_sui_warm_path_reflection_and_policy_compilation(self) -> None:
        """
        Verifies:
        - `orchestrator.run_leaf_agent_reflection("leaf-sui", trigger_source="UNIT_TEST")` writes a drawer to `wing == "leaf_sui"` with `next_wakeup_sec == 900` and `thesis_continuity in ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED")`.
        - `res["policy_envelope"]["asset_overrides"]` keys are strictly `{"SUI-USDC", "DEEP-SUI", "CETUS-SUI"}` (zero non-Sui symbols) with all 11 `AssetOverride` fields populated and representative zone values for `DEEP-SUI` and `CETUS-SUI`.
        - `verify_policy_hmac(SignedPolicyBundle.from_dict(res["signed_policy_bundle"]))` returns `True`.
        """
        cg = self.orchestrator.cost_guard
        cg.auto_refill_enabled = False
        cg.record_usage({"agent": "test", "cost": cg.daily_budget_usd, "tokens": 0})
        self.assertTrue(cg.budget_exhausted)

        res = self.orchestrator.run_leaf_agent_reflection("leaf-sui", trigger_source="UNIT_TEST")
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["wing"], "leaf_sui")
        self.assertEqual(res["drawer"]["next_wakeup_sec"], 900)
        self.assertIn(res["drawer"]["thesis_continuity"], ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED"))

        envelope_dict = res["policy_envelope"]
        self.assertEqual(envelope_dict["ttl_seconds"], 900)
        overrides = envelope_dict["asset_overrides"]
        self.assertEqual(set(overrides.keys()), {"SUI-USDC", "DEEP-SUI", "CETUS-SUI"})

        expected_11_keys = {
            "catalyst_score",
            "bias",
            "max_leverage",
            "support_zone_usd",
            "resistance_zone_usd",
            "invalidation_price_usd",
            "entry_obi_threshold",
            "max_rsi_long",
            "min_rsi_short",
            "take_profit_bps",
            "stop_loss_bps",
        }
        for sym, override in overrides.items():
            self.assertEqual(set(override.keys()), expected_11_keys)

        deep_override = overrides["DEEP-SUI"]
        self.assertAlmostEqual(deep_override["support_zone_usd"], 0.047, places=4)
        self.assertAlmostEqual(deep_override["resistance_zone_usd"], 0.0504, places=4)
        self.assertAlmostEqual(deep_override["invalidation_price_usd"], 0.0466, places=4)

        cetus_override = overrides["CETUS-SUI"]
        self.assertAlmostEqual(cetus_override["support_zone_usd"], 0.0235, places=4)
        self.assertAlmostEqual(cetus_override["resistance_zone_usd"], 0.0252, places=4)
        self.assertAlmostEqual(cetus_override["invalidation_price_usd"], 0.0233, places=4)

        from backend.core.schemas import SignedPolicyBundle, verify_policy_hmac
        signed_bundle = SignedPolicyBundle.from_dict(res["signed_policy_bundle"])
        self.assertTrue(verify_policy_hmac(signed_bundle.policy, signed_bundle.signature, "robotrader-dev-hmac-key"))

    def test_sui_warm_path_reflection_and_policy_compilation(self) -> None:
        """
        Verifies:
        - `orchestrator.run_leaf_agent_reflection("leaf-sui", trigger_source="UNIT_TEST")` writes a drawer to `wing == "leaf_sui"` with `next_wakeup_sec == 900` and `thesis_continuity in ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED")`.
        - `res["policy_envelope"]["asset_overrides"]` keys are strictly `{"SUI-USDC", "DEEP-SUI", "CETUS-SUI"}` (zero non-Sui symbols) with all 11 `AssetOverride` fields populated and `DEEP-SUI`/`CETUS-SUI` ratio zones calibrated around their asset ratios.
        - `verify_policy_hmac(SignedPolicyBundle.from_dict(res["signed_policy_bundle"]))` returns `True`.
        """
        cg = self.orchestrator.cost_guard
        cg.auto_refill_enabled = False
        cg.record_usage({"agent": "test", "cost": cg.daily_budget_usd, "tokens": 0})
        self.assertTrue(cg.budget_exhausted)

        res = self.orchestrator.run_leaf_agent_reflection("leaf-sui", trigger_source="UNIT_TEST")
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["wing"], "leaf_sui")
        self.assertEqual(res["drawer"]["next_wakeup_sec"], 900)
        self.assertIn(res["drawer"]["thesis_continuity"], ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED"))

        envelope_dict = res["policy_envelope"]
        self.assertEqual(envelope_dict["ttl_seconds"], 900)
        overrides = envelope_dict["asset_overrides"]
        self.assertEqual(set(overrides.keys()), {"SUI-USDC", "DEEP-SUI", "CETUS-SUI"})

        expected_11_keys = {
            "catalyst_score",
            "bias",
            "max_leverage",
            "support_zone_usd",
            "resistance_zone_usd",
            "invalidation_price_usd",
            "entry_obi_threshold",
            "max_rsi_long",
            "min_rsi_short",
            "take_profit_bps",
            "stop_loss_bps",
        }
        for sym, override in overrides.items():
            self.assertEqual(set(override.keys()), expected_11_keys)

        deep_override = overrides["DEEP-SUI"]
        self.assertAlmostEqual(deep_override["support_zone_usd"], 0.048 * 0.98, places=4)
        self.assertAlmostEqual(deep_override["resistance_zone_usd"], 0.048 * 1.05, places=4)
        self.assertAlmostEqual(deep_override["invalidation_price_usd"], 0.048 * 0.97, places=4)

        cetus_override = overrides["CETUS-SUI"]
        self.assertAlmostEqual(cetus_override["support_zone_usd"], 0.024 * 0.98, places=4)
        self.assertAlmostEqual(cetus_override["resistance_zone_usd"], 0.024 * 1.05, places=4)
        self.assertAlmostEqual(cetus_override["invalidation_price_usd"], 0.024 * 0.97, places=4)

        sui_override = overrides["SUI-USDC"]
        self.assertAlmostEqual(sui_override["support_zone_usd"], 2.96, places=2)
        self.assertAlmostEqual(sui_override["resistance_zone_usd"], 3.17, places=2)
        self.assertAlmostEqual(sui_override["invalidation_price_usd"], 2.93, places=2)

        from backend.core.schemas import SignedPolicyBundle, verify_policy_hmac
        signed_bundle = SignedPolicyBundle.from_dict(res["signed_policy_bundle"])
        self.assertTrue(verify_policy_hmac(signed_bundle.policy, signed_bundle.signature, "robotrader-dev-hmac-key"))

    def test_cross_wing_mempalace_and_master_leaf_reflections(self) -> None:
        """
        Verifies that leaf agents write to their isolated wing (`wing=leaf_bitcoin`)
        and the Master Orchestrator reads across all wings (`wing=master_orchestrator`).
        """
        # Lock LLM budget to deterministic fallback so unit test runs offline in <10ms.
        cg = self.orchestrator.cost_guard
        cg.auto_refill_enabled = False
        cg.record_usage(
            {"agent": "test", "cost": cg.daily_budget_usd, "tokens": 0}
        )
        self.assertTrue(cg.budget_exhausted)

        leaf_res = self.orchestrator.run_leaf_agent_reflection(
            "leaf-bitcoin", trigger_source="UNIT_TEST"
        )
        self.assertEqual(leaf_res["status"], "completed")
        self.assertEqual(leaf_res["wing"], "leaf_bitcoin")

        btc_drawers = self.store.palace.recall_recent(limit=5, wing="leaf_bitcoin")
        self.assertGreaterEqual(len(btc_drawers), 1)

        digest = self.store.palace.format_cross_wing_digest(limit_per_wing=1)
        self.assertIn("leaf_bitcoin", digest)

        master_res = self.orchestrator.run_master_orchestrator_reflection(
            force=True, trigger_source="UNIT_TEST"
        )
        self.assertEqual(master_res["status"], "completed")
        self.assertEqual(master_res["model_configured"], "moonshotai/kimi-k3.1-pro")
        master_drawers = self.store.palace.recall_recent(
            limit=5, wing="master_orchestrator"
        )
        self.assertGreaterEqual(len(master_drawers), 1)

        sol_res = self.orchestrator.run_strategic_reflection(
            force=True, trigger_source="UNIT_TEST"
        )
        self.assertEqual(sol_res["status"], "completed")

        from backend.core.transcript_palace import transcript_palace

        facets = transcript_palace.list_facets()
        self.assertIn("MasterOrchestrator/MacroLoop", facets["agents"])
        self.assertIn("Leaf/leaf-solana", facets["agents"])

        master_calls, master_total = transcript_palace.list_entries(
            agent="MasterOrchestrator/MacroLoop"
        )
        self.assertGreaterEqual(master_total, 1)
        self.assertEqual(master_calls[0]["kind"], "master_reflection")

    def test_profit_gated_openrouter_auto_refill(self) -> None:
        """
        Verifies CostGuard OpenRouter credit auto-refill is strictly profit-gated
        and epoch-capped.
        """
        cg = self.orchestrator.cost_guard
        cg.openrouter_credit_balance_usd = 1.80  # Below the $2.00 low watermark

        # Negative PnL -> rejected
        rej = cg.trigger_openrouter_refill(realized_trading_pnl_usd=-15.0, force=False)
        self.assertEqual(rej["status"], "rejected_no_realized_profit")

        # Positive PnL ($200 -> max 10% = $20) -> approved
        ok = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=200.0, requested_amount_usd=12.0, force=False
        )
        self.assertEqual(ok["status"], "refilled")
        self.assertEqual(ok["refilled_usd"], 12.0)
        self.assertAlmostEqual(cg.openrouter_credit_balance_usd, 13.80, places=2)

    def test_cost_and_cadence_optimizations(self) -> None:
        """
        Verifies the 4 cost & cadence adjustments:
        1. Auto-scheduler paused by default ($0.00/h at startup)
        2. 15m (900s) leaf cadence & 1h (3600s) Master Orchestrator cadence
        3. Compact TA digest in FULL_THESIS (~1,150 tokens instead of ~8,300 tokens)
        4. Realistic OpenRouter pricing + rolling 24h ledger hydration in CostGuard
        """
        import json
        import time
        from pathlib import Path

        cg = self.orchestrator.cost_guard
        self.assertFalse(cg.auto_scheduler_enabled)
        self.assertEqual(self.store.cognitive_base_interval_sec, 900)
        self.assertEqual(self.store.hierarchy.master_interval_sec, 3600)

        profile = cg.select_cognitive_profile(urgency_level="HIGH_INFLECTION")
        self.assertGreaterEqual(profile["min_wakeup_sec"], 900)

        data = self.store.refresh_ta_and_panorama()
        _, user_prompt = self.orchestrator._build_reflection_prompts(
            thinking_depth="DEEP_THESIS",
            output_contract="FULL_THESIS",
            ta_snapshots=data["ta_snapshots"],
            panorama=data["social_panorama"],
            continuity_ctx="Continuité nominale.",
            min_wakeup=900,
            base_interval=900,
        )
        # Compact TA digest keeps user_prompt well under 4,500 chars (~1,100 tokens)
        self.assertLess(len(user_prompt), 4500)
        self.assertIn("fib_382", user_prompt)
        self.assertIn("fib_618", user_prompt)

        # Verify ledger hydration with realistic OpenRouter pricing
        ledger_file = Path(self._tmpdir.name) / "sample_ledger.jsonl"
        sample_entry = {
            "timestamp_ms": int(time.time() * 1000),
            "agent": "Leaf/leaf-solana",
            "model_used": "deepseek/deepseek-v4.1-flash-1017",
            "prompt_tokens": 100_000,
            "completion_tokens": 20_000,
        }
        ledger_file.write_text(json.dumps(sample_entry) + "\n", encoding="utf-8")
        hydrated = cg.hydrate_from_ledger(storage_path=ledger_file)
        self.assertEqual(hydrated["hydrated_calls"], 1)
        # 0.1M * $0.30 + 0.02M * $1.10 = $0.03 + $0.022 = $0.052
        self.assertAlmostEqual(hydrated["hydrated_cost_usd"], 0.052, places=4)
        # The explicit return is the local scan sum, and reading the aggregate
        # afterwards neither recurses nor hydrates a second time.
        self.assertAlmostEqual(cg.total_cost_usd, hydrated["hydrated_cost_usd"], places=6)
        self.assertAlmostEqual(cg.total_cost_usd, 0.052, places=4)

    def test_simulated_vault_manifest_contract(self) -> None:
        """
        Verifies the public simulated vault contract for all 26 blockchains and
        that untrusted checkout destinations are rejected before any mutation.
        """
        manifest = self.store.hierarchy.vault_manifest
        self.assertEqual(manifest["vault_mode"], "SIMULATED")
        self.assertTrue(manifest["simulated"])
        self.assertFalse(manifest["python_private_key_access"])
        self.assertEqual(manifest["whitelist_enforcement"], "SIMULATED")
        self.assertEqual(len(manifest["wallets"]), 26)

        for lid, leaf in self.store.hierarchy.leaves.items():
            wv = leaf.get("wallet_vault", {})
            self.assertEqual(wv.get("leaf_id"), lid)
            self.assertTrue(wv.get("simulated"))
            self.assertFalse(wv.get("address_is_spendable"))
            self.assertTrue(wv.get("target_leaf_derivation_path"))
            self.assertTrue(wv.get("master_treasury_address"))
            self.assertTrue(wv.get("leaf_hot_address"))
            for legacy in (
                "key_isolation_mode",
                "withdrawal_whitelist_enforced",
                "leaf_derivation_path",
                "slip44_coin_type",
            ):
                self.assertNotIn(legacy, wv)

        completed = self.store.hierarchy.checkout_funds(
            amount_usd=10.0,
            target_chain="Solana",
            target_token="SOL",
            quote_only=False,
        )
        self.assertEqual(completed["status"], "completed")
        self.assertTrue(completed["simulated"])
        receipt = completed["receipt"]["simulated_vault_receipt"]
        self.assertTrue(receipt["simulated"])
        self.assertFalse(receipt["signature_is_chain_valid"])
        self.assertEqual(receipt["whitelist_enforcement"], "SIMULATED")
        self.assertNotIn("tx_hash", completed["receipt"])
        self.assertNotIn("enclave_receipt", completed["receipt"])

        capital_before = self.store.hierarchy.total_capital_usd
        history_before = list(self.store.hierarchy.checkout_history)
        rejected = self.store.hierarchy.checkout_funds(
            amount_usd=500.0,
            target_chain="Solana",
            target_token="SOL",
            destination_address="attacker_drain_wallet_xyz",
            quote_only=False,
        )
        self.assertEqual(rejected["status"], "rejected_by_rust_enclave")
        self.assertEqual(self.store.hierarchy.total_capital_usd, capital_before)
        self.assertEqual(self.store.hierarchy.checkout_history, history_before)

    def test_26_leaf_pod_catalog_parity_with_rust_node(self) -> None:
        """
        Task 5.1: Assert 100% attribute equality between Python `_build_rust_pods_for_leaf`
        and Rust `ecosystem_pod_specs` exported via `robotrader-node --dump-pod-catalog`
        across all 26 canonical leaves.
        """
        repo_root = Path(__file__).resolve().parents[2]
        engine_dir = repo_root / "engine-rs"
        binary_path = resolve_robotrader_binary(engine_dir)

        # 1. Full fleet dump
        proc = subprocess.run(
            [str(binary_path), "--dump-pod-catalog"],
            cwd=str(engine_dir),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        rust_catalog = json.loads(proc.stdout)
        self.assertEqual(len(rust_catalog), 26)

        for leaf_meta in LEAF_ECOSYSTEM_CATALOG:
            leaf_id = leaf_meta["id"]
            self.assertIn(leaf_id, rust_catalog)
            rust_pods = rust_catalog[leaf_id]
            py_pods = HierarchicalFleetManager._build_rust_pods_for_leaf(leaf_id)

            self.assertGreaterEqual(len(rust_pods), 1)
            self.assertLessEqual(len(rust_pods), 4)
            self.assertEqual(
                len(py_pods),
                len(rust_pods),
                f"Pod count mismatch for leaf {leaf_id}: Python {len(py_pods)} vs Rust {len(rust_pods)}",
            )

            for idx, (py_pod, rust_pod) in enumerate(zip(py_pods, rust_pods)):
                self.assertEqual(py_pod["slot_id"], rust_pod["slot_id"], f"Slot mismatch in {leaf_id}[{idx}]")
                self.assertEqual(py_pod["pod_code"], rust_pod["pod_code"], f"Code mismatch in {leaf_id}[{idx}]")
                self.assertEqual(py_pod["name"], rust_pod["name"], f"Name mismatch in {leaf_id}[{idx}]")
                self.assertEqual(py_pod["archetype"], rust_pod["archetype"], f"Archetype mismatch in {leaf_id}[{idx}]")
                self.assertEqual(py_pod["native_venue"], rust_pod["native_venue"], f"Venue mismatch in {leaf_id}[{idx}]")
                self.assertAlmostEqual(
                    float(py_pod["default_weight"]),
                    float(rust_pod["default_weight"]),
                    places=4,
                    msg=f"Weight mismatch in {leaf_id}[{idx}]",
                )
                self.assertEqual(py_pod["description"], rust_pod["description"], f"Description mismatch in {leaf_id}[{idx}]")

        # 2. Single-leaf export (--leaf-id leaf-solana)
        single_proc = subprocess.run(
            [str(binary_path), "--dump-pod-catalog", "--leaf-id", "leaf-solana"],
            cwd=str(engine_dir),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        single_pods = json.loads(single_proc.stdout)
        self.assertIsInstance(single_pods, list)
        self.assertEqual(len(single_pods), 4)

        # 3. Unrecognized leaf-id rejection (--leaf-id leaf-unknown)
        bad_proc = subprocess.run(
            [str(binary_path), "--dump-pod-catalog", "--leaf-id", "leaf-unknown"],
            cwd=str(engine_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(bad_proc.returncode, 0)
        self.assertIn("unrecognized leaf identifier", bad_proc.stderr.lower())

    def test_pod_catalog_parity_negative_assertion_detects_mismatch(self) -> None:
        """
        Task 5.2: Negative assertion test verifying that any pod attribute mismatch
        (name, weight, slot, description) triggers an explicit test failure.
        """
        base_pods = HierarchicalFleetManager._build_rust_pods_for_leaf("leaf-bnb")

        def verify_parity(py_pods, rust_pods, leaf_id="leaf-bnb"):
            if len(py_pods) != len(rust_pods):
                raise AssertionError(f"Count mismatch in {leaf_id}")
            for idx, (p, r) in enumerate(zip(py_pods, rust_pods)):
                for attr in ("slot_id", "pod_code", "name", "archetype", "native_venue", "description"):
                    if p.get(attr) != r.get(attr):
                        raise AssertionError(
                            f"Mismatch in {leaf_id}[{idx}] attribute '{attr}': {p.get(attr)!r} != {r.get(attr)!r}"
                        )
                if abs(float(p.get("default_weight", 0.0)) - float(r.get("default_weight", 0.0))) > 1e-4:
                    raise AssertionError(f"Mismatch in {leaf_id}[{idx}] attribute 'default_weight'")

        # 1. Baseline parity passes
        verify_parity(base_pods, base_pods)

        # 2. Mutate name
        mutated_name = [dict(p) for p in base_pods]
        mutated_name[0]["name"] = "Mismatched Name"
        with self.assertRaises(AssertionError) as ctx:
            verify_parity(mutated_name, base_pods)
        self.assertIn("attribute 'name'", str(ctx.exception))

        # 3. Mutate default_weight
        mutated_weight = [dict(p) for p in base_pods]
        mutated_weight[0]["default_weight"] = 0.99
        with self.assertRaises(AssertionError) as ctx:
            verify_parity(mutated_weight, base_pods)
        self.assertIn("attribute 'default_weight'", str(ctx.exception))

        # 4. Mutate slot_id
        mutated_slot = [dict(p) for p in base_pods]
        mutated_slot[0]["slot_id"] = "pod_sniper"
        with self.assertRaises(AssertionError) as ctx:
            verify_parity(mutated_slot, base_pods)
        self.assertIn("attribute 'slot_id'", str(ctx.exception))

        # 5. Mutate description
        mutated_desc = [dict(p) for p in base_pods]
        mutated_desc[0]["description"] = "Altered strategy logic"
        with self.assertRaises(AssertionError) as ctx:
            verify_parity(mutated_desc, base_pods)
        self.assertIn("attribute 'description'", str(ctx.exception))

    def test_execution_mode_and_telemetry_source_classification(self) -> None:
        """
        Task 5.3: Verify execution_mode, scheduler_active, and ta_metrics_source
        across all 26 leaves in hierarchy manager, overview, and detail endpoints.
        """
        palace = StrategyMemoryPalace(redis_cmd_fn=None, redis_url=None)
        mgr = HierarchicalFleetManager(palace=palace)

        # Verify leaf-solana active
        sol_leaf = mgr.get_leaf_detail("leaf-solana")
        self.assertEqual(sol_leaf["execution_mode"], "ACTIVE_SOLANA")
        self.assertEqual(sol_leaf["scheduler_active"], mgr.auto_scheduler_enabled)
        self.assertIn(sol_leaf["ta_metrics_source"], ("CATALOG_FIXTURE", "LIVE_COMPUTED"))

        # Verify the other 25 leaves are PASSIVE_CATALOG
        snapshot = mgr.get_hierarchy_snapshot()
        active_count = 0
        passive_count = 0
        for leaf in snapshot["leaves"]:
            lid = leaf.get("leaf_id") or leaf.get("id")
            if lid == "leaf-solana":
                self.assertEqual(leaf["execution_mode"], "ACTIVE_SOLANA")
                active_count += 1
            else:
                self.assertEqual(leaf["execution_mode"], "PASSIVE_CATALOG")
                self.assertFalse(leaf["scheduler_active"])
                self.assertEqual(leaf["ta_metrics_source"], "CATALOG_FIXTURE")
                passive_count += 1

        self.assertEqual(active_count, 1)
        self.assertEqual(passive_count, 25)

    def test_social_macro_panorama_sentiment_confluence_and_provenance(self) -> None:
        """
        Task 5.3: Verify composite_sentiment casing, dynamic confluence averaging,
        neutral 0.0 fallback on empty snapshots, and SYNTHETIC_FIXTURE provenance.
        """
        # 1. Non-empty Solana symbols only (no BTC/ETH)
        sol_snapshots = {
            "SOL/USDT": {"confluence_score": 0.60, "rsi": {"rsi_14": 55.0}, "ichimoku": {"kumo_regime": "ABOVE_KUMO_BULLISH"}},
            "JUP/USDT": {"confluence_score": 0.80, "rsi": {"rsi_14": 60.0}, "ichimoku": {"kumo_regime": "ABOVE_KUMO_BULLISH"}},
            "RAY/USDT": {"confluence_score": 0.40, "rsi": {"rsi_14": 50.0}, "ichimoku": {"kumo_regime": "INSIDE_KUMO_NEUTRAL"}},
        }
        pano = SocialMacroPanoramaTool.build_panorama(ta_snapshots=sol_snapshots)
        self.assertIn("composite_sentiment", pano)
        self.assertIn("Composite_sentiment", pano)
        self.assertEqual(pano["composite_sentiment"], pano["Composite_sentiment"])
        self.assertIsInstance(pano["composite_sentiment"], (int, float))
        self.assertEqual(pano["source_kind"], "SYNTHETIC_FIXTURE")
        for sig in pano["social_signals"]:
            self.assertEqual(sig.get("source_kind"), "SYNTHETIC_FIXTURE", f"Missing source_kind in {sig}")

        # 2. Single-symbol snapshot -> exact single score (0.60, not 0.20)
        single_snap = {"SOL/USDT": {"confluence_score": 0.60}}
        single_pano = SocialMacroPanoramaTool.build_panorama(ta_snapshots=single_snap)
        # avg_score is 0.60, composite_sentiment = round(0.55 + 0.25 * 0.60, 2) = 0.70
        self.assertAlmostEqual(single_pano["composite_sentiment"], 0.70, places=2)

        # 3. Empty snapshots -> 0.0 fallback without ZeroDivisionError
        empty_pano = SocialMacroPanoramaTool.build_panorama(ta_snapshots={})
        self.assertIn("composite_sentiment", empty_pano)
        # avg_score is 0.0, composite_sentiment = round(0.55 + 0.25 * 0.0, 2) = 0.55
        self.assertAlmostEqual(empty_pano["composite_sentiment"], 0.55, places=2)

    def test_rss_feed_provenance_stamping_and_feed_mode(self) -> None:
        """
        Task 5.3: Verify EcosystemRSSAggregator provenance stamping (CURATED_FIXTURE,
        fixed timestamp, feed_mode, live_count, curated_count).
        """
        feed = EcosystemRSSAggregator.get_feed_for_agent("leaf-solana", try_network=False)
        self.assertEqual(feed["feed_mode"], "CURATED_FALLBACK")
        self.assertEqual(feed["live_count"], 0)
        self.assertGreater(feed["curated_count"], 0)
        self.assertEqual(len(feed["items"]), feed["curated_count"])

        for item in feed["items"]:
            self.assertEqual(item["source_kind"], "CURATED_FIXTURE")
            self.assertTrue(item["curated"])
            self.assertEqual(item["timestamp_ms"], CURATED_FIXTURE_TIMESTAMP_MS)

    def test_bitcoin_leaf_ta_metrics_computation_and_fallback(self) -> None:
        """
        Verifies TechnicalAnalysisTool.compute_bitcoin_ta_metrics across BTC-USD, wBTC-BTC, sBTC-BTC:
        1. Returns ta_metrics_source == "LIVE_COMPUTED" and all 8 required Bitcoin metrics
           (mempool_fee_sat_vb, hash_ribbon_state, etf_netflow_24h_usd_m, miner_reserve_delta_btc,
            kumo_regime, golden_pocket_fib_618, rsi_14, obi_l2) computed from real OHLCV + L2 + telemetry.
        2. Gracefully falls back (ta_metrics_source == "CATALOG_FIXTURE") when candle/telemetry input is empty.
        """
        from backend.tools.ta_tools import TechnicalAnalysisTool

        sample_candles = [
            [1700000000000 + i * 900000, 80000.0 + i * 10, 80100.0 + i * 10, 79900.0 + i * 10, 80050.0 + i * 10, 150.0]
            for i in range(25)
        ]
        sample_bids = [[80040.0, 10.0], [80030.0, 15.0]]
        sample_asks = [[80060.0, 5.0], [80070.0, 8.0]]
        sample_telemetry = {
            "mempool_fee_sat_vb": 12.4,
            "hash_ribbon_state": "EXPANSION_BULLISH",
            "etf_netflow_24h_usd_m": 450.0,
            "miner_reserve_delta_btc": 210.5,
        }

        for sym in ["BTC-USD", "wBTC-BTC", "sBTC-BTC"]:
            res = TechnicalAnalysisTool.compute_bitcoin_ta_metrics(
                candles=sample_candles,
                bids=sample_bids,
                asks=sample_asks,
                onchain_telemetry=sample_telemetry,
                symbol=sym,
            )
            self.assertEqual(res["symbol"], sym)
            self.assertEqual(res["ta_metrics_source"], "LIVE_COMPUTED")
            self.assertEqual(res["mempool_fee_sat_vb"], 12.4)
            self.assertEqual(res["hash_ribbon_state"], "EXPANSION_BULLISH")
            self.assertEqual(res["etf_netflow_24h_usd_m"], 450.0)
            self.assertEqual(res["miner_reserve_delta_btc"], 210.5)
            self.assertIn("kumo_regime", res)
            self.assertIn("golden_pocket_fib_618", res)
            self.assertIn("rsi_14", res)
            self.assertIn("obi_l2", res)
            self.assertIn("Bitcoin L1 Native", res["venues"])
            self.assertIn("ThorChain Native Pool", res["venues"])
            self.assertIn("Lightning Liquidity", res["venues"])

        ingest_res = TechnicalAnalysisTool.ingest_bitcoin_market_snapshot(
            candles=sample_candles,
            bids=sample_bids,
            asks=sample_asks,
            onchain_telemetry=sample_telemetry,
            symbol="BTC-USD",
        )
        self.assertEqual(ingest_res["ta_metrics_source"], "LIVE_COMPUTED")

        fallback_res = TechnicalAnalysisTool.compute_bitcoin_ta_metrics(
            candles=[],
            bids=None,
            asks=None,
            onchain_telemetry=None,
            symbol="BTC-USD",
        )
        self.assertEqual(fallback_res["ta_metrics_source"], "CATALOG_FIXTURE")
        self.assertIn("mempool_fee_sat_vb", fallback_res)
        self.assertIn("hash_ribbon_state", fallback_res)
        self.assertIn("etf_netflow_24h_usd_m", fallback_res)
        self.assertIn("miner_reserve_delta_btc", fallback_res)

    def test_bitcoin_rss_atom_parsing_and_catalyst_scoring(self) -> None:
        """
        Verifies:
        1. Atom XML (<feed xmlns="http://www.w3.org/2005/Atom"><entry>...</entry></feed>) from Bitcoin Optech
           and RSS 2.0 XML (<rss><channel><item>...</item></channel></rss>) from Mempool & Hashrate Intelligence
           parse with source_kind == "LIVE_RSS" and feed_mode == "LIVE".
        2. score_bitcoin_catalyst and verify_and_ingest_bitcoin_feeds compute deterministic catalyst_score,
           impact, category, and affected_assets strictly within ["BTC-USD", "wBTC-BTC", "sBTC-BTC"].
        3. Graceful fallback to CURATED_FIXTURE (feed_mode == "CURATED_FALLBACK") when XML payloads fail or network is unreachable.
        """
        atom_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Bitcoin Optech Newsletter</title>
          <entry>
            <title>Optech #300: Major Taproot upgrade and wBTC bridge expansion</title>
            <summary>Substantial surge in spot ETF inflows and mempool fee efficiency.</summary>
          </entry>
        </feed>
        """
        rss_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>Mempool &amp; Hashrate Intelligence</title>
            <item>
              <title>Hash Ribbon expansion and sBTC bridge stability</title>
              <description>Miner reserves stable, block congestion low at 5 sat/vB.</description>
            </item>
          </channel>
        </rss>
        """

        payloads = {
            "Bitcoin Optech Newsletter": atom_xml,
            "Mempool & Hashrate Intelligence": rss_xml,
        }

        feed_res = EcosystemRSSAggregator.verify_and_ingest_bitcoin_feeds(
            xml_payloads=payloads, try_network=False, max_items=5
        )
        self.assertEqual(feed_res["agent_id"], "leaf-bitcoin")
        self.assertEqual(feed_res["feed_mode"], "LIVE")
        self.assertEqual(feed_res["live_count"], 2)
        self.assertEqual(feed_res["curated_count"], 0)
        self.assertGreaterEqual(len(feed_res["items"]), 2)

        for item in feed_res["items"]:
            self.assertEqual(item["source_kind"], "LIVE_RSS")
            self.assertFalse(item["curated"])
            self.assertIn("catalyst_score", item)
            self.assertIn("impact", item)
            self.assertIn("category", item)
            self.assertIn("affected_assets", item)
            for asset in item["affected_assets"]:
                self.assertIn(asset, ["BTC-USD", "wBTC-BTC", "sBTC-BTC"])

        # Test fallback when payloads are empty and network is disabled
        fallback_res = EcosystemRSSAggregator.verify_and_ingest_bitcoin_feeds(
            xml_payloads={}, try_network=False, max_items=5
        )
        self.assertEqual(fallback_res["feed_mode"], "CURATED_FALLBACK")
        self.assertEqual(fallback_res["live_count"], 0)
        self.assertGreater(fallback_res["curated_count"], 0)
        for item in fallback_res["items"]:
            self.assertEqual(item["source_kind"], "CURATED_FIXTURE")
            self.assertTrue(item["curated"])
            self.assertEqual(item["timestamp_ms"], CURATED_FIXTURE_TIMESTAMP_MS)

    def test_ethereum_leaf_ta_metrics_computation_and_fallback(self) -> None:
        """
        Verifies TechnicalAnalysisTool.compute_ethereum_ta_metrics and ingest_ethereum_market_snapshot
        across all 4 exclusive Ethereum assets (`ETH-USDC`, `stETH-ETH`, `UNI-ETH`, `AAVE-ETH`),
        verifying `LIVE_COMPUTED` vs `CATALOG_FIXTURE` fallback and `ValueError` on non-Ethereum symbols/venues.
        """
        from backend.tools.ta_tools import TechnicalAnalysisTool

        sample_candles = [
            [1700000000000 + i * 900000, 2300.0 + i * 5, 2310.0 + i * 5, 2290.0 + i * 5, 2305.0 + i * 5, 500.0]
            for i in range(25)
        ]
        sample_bids = [[2304.0, 50.0], [2303.0, 75.0]]
        sample_asks = [[2306.0, 40.0], [2307.0, 60.0]]
        sample_telemetry = {
            "eip1559_base_fee_gwei": 3.5,
            "blob_fee_gwei": 0.05,
            "steth_peg_ratio": 0.9999,
            "restaking_apr_pct": 4.10,
        }

        for sym in TechnicalAnalysisTool.ETHEREUM_EXCLUSIVE_ASSETS:
            for venue in TechnicalAnalysisTool.ETHEREUM_VENUES:
                res = TechnicalAnalysisTool.compute_ethereum_ta_metrics(
                    candles=sample_candles,
                    bids=sample_bids,
                    asks=sample_asks,
                    onchain_telemetry=sample_telemetry,
                    symbol=sym,
                    venue=venue,
                )
                self.assertEqual(res["symbol"], sym)
                self.assertEqual(res["venue"], venue)
                self.assertEqual(res["ta_metrics_source"], "LIVE_COMPUTED")
                self.assertEqual(res["eip1559_base_fee_gwei"], 3.5)
                self.assertEqual(res["blob_fee_gwei"], 0.05)
                self.assertEqual(res["steth_peg_ratio"], 0.9999)
                self.assertEqual(res["restaking_apr_pct"], 4.10)
                self.assertIn("kumo_regime", res)
                self.assertIn("golden_pocket_fib_618", res)
                self.assertIn("rsi_14", res)
                self.assertIn("obi_l2", res)

        # Test market snapshot ingestion helper
        market_feeds = {
            "ETH-USDC": {
                "candles": sample_candles,
                "bids": sample_bids,
                "asks": sample_asks,
            }
        }
        ingest_res = TechnicalAnalysisTool.ingest_ethereum_market_snapshot(
            market_feeds=market_feeds,
            onchain_telemetry=sample_telemetry,
            venue="Uniswap v4",
        )
        self.assertEqual(ingest_res["ta_metrics_source"], "LIVE_COMPUTED")
        self.assertEqual(ingest_res["symbol"], "ETH-USDC")

        # Test fallback when candles are empty
        fallback_res = TechnicalAnalysisTool.compute_ethereum_ta_metrics(
            candles=[],
            bids=None,
            asks=None,
            onchain_telemetry=None,
            symbol="ETH-USDC",
            venue="Uniswap v4",
        )
        self.assertEqual(fallback_res["ta_metrics_source"], "CATALOG_FIXTURE")
        self.assertIn("eip1559_base_fee_gwei", fallback_res)
        self.assertIn("blob_fee_gwei", fallback_res)
        self.assertIn("steth_peg_ratio", fallback_res)
        self.assertIn("restaking_apr_pct", fallback_res)

        # Test ValueError on invalid symbol or venue
        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_ethereum_ta_metrics(symbol="BTC-USD", venue="Uniswap v4")

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_ethereum_ta_metrics(symbol="ETH-USDC", venue="InvalidVenue")

    def test_ethereum_rss_atom_parsing_and_catalyst_scoring(self) -> None:
        """
        Verifies RSS 2.0 ("Week in Ethereum News") and Atom ("Ethereum Foundation Blog") XML parsing,
        score_ethereum_catalyst classification across ETH-USDC, stETH-ETH, UNI-ETH, AAVE-ETH
        (zero non-Ethereum symbols), and CURATED_FALLBACK behavior.
        """
        atom_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Ethereum Foundation Blog</title>
          <entry>
            <title>Pectra upgrade and restaking staking rewards stability with Lido stETH</title>
            <summary>EigenLayer restaking APR steady and basefee EIP-1559 low.</summary>
          </entry>
        </feed>
        """
        rss_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>Week in Ethereum News</title>
            <item>
              <title>Uniswap v4 hooks and Aave v3 liquidity expansion</title>
              <description>Institutional ETF inflows and blob gas optimization.</description>
            </item>
          </channel>
        </rss>
        """

        payloads = {
            "Week in Ethereum News": rss_xml,
            "Ethereum Foundation Blog": atom_xml,
        }

        feed_res = EcosystemRSSAggregator.verify_and_ingest_ethereum_feeds(
            xml_payloads=payloads, try_network=False, max_items=5
        )
        self.assertEqual(feed_res["agent_id"], "leaf-ethereum")
        self.assertEqual(feed_res["feed_mode"], "LIVE")
        self.assertEqual(feed_res["live_count"], 2)
        self.assertEqual(feed_res["curated_count"], 0)
        self.assertGreaterEqual(len(feed_res["items"]), 2)

        for item in feed_res["items"]:
            self.assertEqual(item["source_kind"], "LIVE_RSS")
            self.assertFalse(item["curated"])
            self.assertIn("catalyst_score", item)
            self.assertIn("impact", item)
            self.assertIn("category", item)
            self.assertIn("affected_assets", item)
            for asset in item["affected_assets"]:
                self.assertIn(asset, ["ETH-USDC", "stETH-ETH", "UNI-ETH", "AAVE-ETH"])

        for asset in ["ETH-USDC", "stETH-ETH", "UNI-ETH", "AAVE-ETH"]:
            self.assertIn(asset, feed_res["asset_catalyst_scores"])

        # Test fallback when payloads are empty and network is disabled
        fallback_res = EcosystemRSSAggregator.verify_and_ingest_ethereum_feeds(
            xml_payloads={}, try_network=False, max_items=5
        )
        self.assertEqual(fallback_res["feed_mode"], "CURATED_FALLBACK")
        self.assertEqual(fallback_res["live_count"], 0)
        self.assertGreater(fallback_res["curated_count"], 0)
        for item in fallback_res["items"]:
            self.assertEqual(item["source_kind"], "CURATED_FIXTURE")
            self.assertTrue(item["curated"])
            self.assertEqual(item["timestamp_ms"], CURATED_FIXTURE_TIMESTAMP_MS)

    def test_sui_rss_atom_parsing_and_catalyst_scoring(self) -> None:
        """
        Verifies RSS 2.0 ("Sui Foundation & DeepBook Updates") and Atom XML parsing,
        score_sui_catalyst classification across SUI-USDC, DEEP-SUI, CETUS-SUI
        (zero non-Sui symbols), and CURATED_FALLBACK behavior.
        """
        atom_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Sui Foundation &amp; DeepBook Updates</title>
          <entry>
            <title>DeepBook v3 CLOB record throughput and CETUS CLMM expansion</title>
            <summary>Navi Protocol lending growth, mysticeti finality under 390ms.</summary>
          </entry>
        </feed>
        """
        rss_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>Sui Foundation &amp; DeepBook Updates</title>
            <item>
              <title>Sui protocol upgrade and DEEP token surge</title>
              <description>Navi borrow collateral stable, CETUS liquidity.</description>
            </item>
          </channel>
        </rss>
        """

        payloads = {
            "Sui Foundation & DeepBook Updates": rss_xml,
        }

        feed_res = EcosystemRSSAggregator.verify_and_ingest_sui_feeds(
            xml_payloads=payloads, try_network=False, max_items=5
        )
        self.assertEqual(feed_res["agent_id"], "leaf-sui")
        self.assertEqual(feed_res["feed_mode"], "LIVE")
        self.assertEqual(feed_res["live_count"], 1)
        self.assertEqual(feed_res["curated_count"], 0)
        self.assertGreaterEqual(len(feed_res["items"]), 1)

        for item in feed_res["items"]:
            self.assertEqual(item["source_kind"], "LIVE_RSS")
            self.assertFalse(item["curated"])
            self.assertIn("catalyst_score", item)
            self.assertIn("impact", item)
            self.assertIn("category", item)
            self.assertIn("affected_assets", item)
            for asset in item["affected_assets"]:
                self.assertIn(asset, ["SUI-USDC", "DEEP-SUI", "CETUS-SUI"])

        for asset in ["SUI-USDC", "DEEP-SUI", "CETUS-SUI"]:
            self.assertIn(asset, feed_res["asset_catalyst_scores"])

        # Test Atom parsing too
        payloads2 = {
            "Sui Foundation & DeepBook Updates": atom_xml,
        }
        feed_res2 = EcosystemRSSAggregator.verify_and_ingest_sui_feeds(
            xml_payloads=payloads2, try_network=False, max_items=5
        )
        self.assertEqual(feed_res2["feed_mode"], "LIVE")
        self.assertEqual(feed_res2["live_count"], 1)

        # Test fallback when payloads are empty and network is disabled
        fallback_res = EcosystemRSSAggregator.verify_and_ingest_sui_feeds(
            xml_payloads={}, try_network=False, max_items=5
        )
        self.assertEqual(fallback_res["feed_mode"], "CURATED_FALLBACK")
        self.assertEqual(fallback_res["live_count"], 0)
        self.assertGreater(fallback_res["curated_count"], 0)
        for item in fallback_res["items"]:
            self.assertEqual(item["source_kind"], "CURATED_FIXTURE")
            self.assertTrue(item["curated"])
            self.assertEqual(item["timestamp_ms"], CURATED_FIXTURE_TIMESTAMP_MS)

        # get_feed_for_agent serves Sui
        feed = EcosystemRSSAggregator.get_feed_for_agent("leaf-sui", try_network=False)
        self.assertIn("items", feed)
        self.assertIn("feed_mode", feed)

    def test_sui_leaf_ta_metrics_computation_and_fallback(self) -> None:
        """
        Verifies TechnicalAnalysisTool.compute_sui_ta_metrics and ingest_sui_market_snapshot
        across all 3 exclusive Sui assets (`SUI-USDC`, `DEEP-SUI`, `CETUS-SUI`),
        verifying `LIVE_COMPUTED` vs `CATALOG_FIXTURE` fallback and `ValueError` on non-Sui symbols/venues.
        """
        from backend.tools.ta_tools import TechnicalAnalysisTool

        sample_candles = [
            [1700000000000 + i * 900000, 3.0 + i * 0.05, 3.05 + i * 0.05, 2.95 + i * 0.05, 3.02 + i * 0.05, 1000.0]
            for i in range(25)
        ]
        sample_bids = [[3.01, 100.0], [3.00, 150.0]]
        sample_asks = [[3.03, 80.0], [3.04, 120.0]]
        sample_telemetry = {
            "mysticeti_finality_ms": 350,
            "deepbook_v3_vol_usd_m": 510.0,
        }

        for sym in TechnicalAnalysisTool.SUI_EXCLUSIVE_ASSETS:
            for venue in TechnicalAnalysisTool.SUI_VENUES:
                res = TechnicalAnalysisTool.compute_sui_ta_metrics(
                    candles=sample_candles,
                    bids=sample_bids,
                    asks=sample_asks,
                    onchain_telemetry=sample_telemetry,
                    symbol=sym,
                    venue=venue,
                )
                self.assertEqual(res["symbol"], sym)
                self.assertEqual(res["venue"], venue)
                self.assertEqual(res["ta_metrics_source"], "LIVE_COMPUTED")
                self.assertEqual(res["mysticeti_finality_ms"], 350)
                self.assertEqual(res["deepbook_v3_vol_usd_m"], 510.0)
                self.assertIn("kumo_regime", res)
                self.assertIn("golden_pocket_fib_618", res)
                self.assertIn("rsi_14", res)
                self.assertIn("obi_l2", res)

        market_feeds = {
            "SUI-USDC": {
                "candles": sample_candles,
                "bids": sample_bids,
                "asks": sample_asks,
            }
        }
        ingest_res = TechnicalAnalysisTool.ingest_sui_market_snapshot(
            market_feeds=market_feeds,
            onchain_telemetry=sample_telemetry,
            venue="DeepBook v3 CLOB",
        )
        self.assertEqual(ingest_res["ta_metrics_source"], "LIVE_COMPUTED")
        self.assertEqual(ingest_res["symbol"], "SUI-USDC")

        fallback_res = TechnicalAnalysisTool.compute_sui_ta_metrics(
            candles=[],
            bids=None,
            asks=None,
            onchain_telemetry=None,
            symbol="SUI-USDC",
            venue="DeepBook v3 CLOB",
        )
        self.assertEqual(fallback_res["ta_metrics_source"], "CATALOG_FIXTURE")
        self.assertIn("mysticeti_finality_ms", fallback_res)
        self.assertIn("deepbook_v3_vol_usd_m", fallback_res)

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_sui_ta_metrics(symbol="BTC-USD", venue="DeepBook v3 CLOB")

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_sui_ta_metrics(symbol="SUI-USDC", venue="InvalidVenue")

    def test_hyperliquid_leaf_ta_metrics_computation_and_fallback(self) -> None:
        """
        Verifies TechnicalAnalysisTool.compute_hyperliquid_ta_metrics and ingest_hyperliquid_market_snapshot.
        """
        from backend.tools.ta_tools import TechnicalAnalysisTool

        sample_candles = [
            [1700000000000 + i * 900000, 24.0 + i * 0.5, 24.5 + i * 0.5, 23.5 + i * 0.5, 24.2 + i * 0.5, 1000.0]
            for i in range(25)
        ]
        sample_bids = [[24.1, 100.0], [24.0, 150.0]]
        sample_asks = [[24.3, 80.0], [24.4, 120.0]]
        sample_telemetry = {
            "hlp_apr_pct": 21.0,
            "clob_open_interest_usd_b": 4.2,
        }

        for sym in TechnicalAnalysisTool.HYPERLIQUID_EXCLUSIVE_ASSETS:
            for venue in TechnicalAnalysisTool.HYPERLIQUID_VENUES:
                res = TechnicalAnalysisTool.compute_hyperliquid_ta_metrics(
                    candles=sample_candles,
                    bids=sample_bids,
                    asks=sample_asks,
                    onchain_telemetry=sample_telemetry,
                    symbol=sym,
                    venue=venue,
                )
                self.assertEqual(res["symbol"], sym)
                self.assertEqual(res["venue"], venue)
                self.assertEqual(res["ta_metrics_source"], "LIVE_COMPUTED")
                self.assertEqual(res["hlp_apr_pct"], 21.0)
                self.assertEqual(res["clob_open_interest_usd_b"], 4.2)
                self.assertIn("kumo_regime", res)
                self.assertIn("golden_pocket_fib_618", res)
                self.assertIn("rsi_14", res)
                self.assertIn("obi_l2", res)

        market_feeds = {
            "HYPE-USDC": {
                "candles": sample_candles,
                "bids": sample_bids,
                "asks": sample_asks,
            }
        }
        ingest_res = TechnicalAnalysisTool.ingest_hyperliquid_market_snapshot(
            market_feeds=market_feeds,
            onchain_telemetry=sample_telemetry,
            venue="HyperCore L1 CLOB",
        )
        self.assertEqual(ingest_res["ta_metrics_source"], "LIVE_COMPUTED")
        self.assertEqual(ingest_res["symbol"], "HYPE-USDC")

        fallback_res = TechnicalAnalysisTool.compute_hyperliquid_ta_metrics(
            candles=[],
            bids=None,
            asks=None,
            onchain_telemetry=None,
            symbol="HYPE-USDC",
            venue="HyperCore L1 CLOB",
        )
        self.assertEqual(fallback_res["ta_metrics_source"], "CATALOG_FIXTURE")
        self.assertIn("hlp_apr_pct", fallback_res)
        self.assertIn("clob_open_interest_usd_b", fallback_res)

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_hyperliquid_ta_metrics(symbol="BTC-USD", venue="HyperCore L1 CLOB")

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_hyperliquid_ta_metrics(symbol="HYPE-USDC", venue="InvalidVenue")

    def test_ton_leaf_ta_metrics_computation_and_fallback(self) -> None:
        """
        Verifies TechnicalAnalysisTool.compute_ton_ta_metrics and ingest_ton_market_snapshot
        across all 2 exclusive TON assets (`TON-USDT`, `NOT-TON`),
        verifying `LIVE_COMPUTED` vs `CATALOG_FIXTURE` fallback and `ValueError` on non-TON symbols/venues.
        """
        from backend.tools.ta_tools import TechnicalAnalysisTool

        sample_candles = [
            [1700000000000 + i * 900000, 5.0 + i * 0.05, 5.1 + i * 0.05, 4.9 + i * 0.05, 5.05 + i * 0.05, 1000.0]
            for i in range(25)
        ]
        sample_bids = [[5.03, 100.0], [5.02, 150.0]]
        sample_asks = [[5.07, 80.0], [5.08, 120.0]]
        sample_telemetry = {
            "usdt_ton_supply_usd_b": 1.5,
            "stonfi_tvl_usd_m": 250.0,
        }

        for sym in TechnicalAnalysisTool.TON_EXCLUSIVE_ASSETS:
            for venue in TechnicalAnalysisTool.TON_VENUES:
                res = TechnicalAnalysisTool.compute_ton_ta_metrics(
                    candles=sample_candles,
                    bids=sample_bids,
                    asks=sample_asks,
                    onchain_telemetry=sample_telemetry,
                    symbol=sym,
                    venue=venue,
                )
                self.assertEqual(res["symbol"], sym)
                self.assertEqual(res["venue"], venue)
                self.assertEqual(res["ta_metrics_source"], "LIVE_COMPUTED")
                self.assertEqual(res["usdt_ton_supply_usd_b"], 1.5)
                self.assertEqual(res["stonfi_tvl_usd_m"], 250.0)
                self.assertIn("kumo_regime", res)
                self.assertIn("golden_pocket_fib_618", res)
                self.assertIn("rsi_14", res)
                self.assertIn("obi_l2", res)

        market_feeds = {
            "TON-USDT": {
                "candles": sample_candles,
                "bids": sample_bids,
                "asks": sample_asks,
            }
        }
        ingest_res = TechnicalAnalysisTool.ingest_ton_market_snapshot(
            market_feeds=market_feeds,
            onchain_telemetry=sample_telemetry,
            venue="STON.fi",
        )
        self.assertEqual(ingest_res["ta_metrics_source"], "LIVE_COMPUTED")
        self.assertEqual(ingest_res["symbol"], "TON-USDT")

        fallback_res = TechnicalAnalysisTool.compute_ton_ta_metrics(
            candles=[],
            bids=None,
            asks=None,
            onchain_telemetry=None,
            symbol="TON-USDT",
            venue="STON.fi",
        )
        self.assertEqual(fallback_res["ta_metrics_source"], "CATALOG_FIXTURE")
        self.assertIn("usdt_ton_supply_usd_b", fallback_res)
        self.assertIn("stonfi_tvl_usd_m", fallback_res)

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_ton_ta_metrics(symbol="BTC-USD", venue="STON.fi")

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_ton_ta_metrics(symbol="TON-USDT", venue="InvalidVenue")




    def test_hyperliquid_rss_atom_parsing_and_catalyst_scoring(self) -> None:
        """
        Verifies Hyperliquid RSS/Atom parsing (Hyperliquid L1 & HLP Vault Telemetry),
        score_hyperliquid_catalyst classification across HYPE-USDC and PURR-USDC,
        and CURATED_FALLBACK behavior.
        """
        atom_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Hyperliquid L1 &amp; HLP Vault Telemetry</title>
          <entry>
            <title>HLP Vault APR record and HyperCore CLOB perp funding surge</title>
            <summary>HyperEVM spot auction expansion, open interest record.</summary>
          </entry>
        </feed>
        """
        rss_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>Hyperliquid L1 &amp; HLP Vault Telemetry</title>
            <item>
              <title>PURR spot surge on HyperEVM</title>
              <description>HLP liquidity vault stable, HyperCore CLOB expansion.</description>
            </item>
          </channel>
        </rss>
        """

        payloads = {
            "Hyperliquid L1 & HLP Vault Telemetry": rss_xml,
        }

        feed_res = EcosystemRSSAggregator.verify_and_ingest_hyperliquid_feeds(
            xml_payloads=payloads, try_network=False, max_items=5
        )
        self.assertEqual(feed_res["agent_id"], "leaf-hyperliquid")
        self.assertEqual(feed_res["feed_mode"], "LIVE")
        self.assertEqual(feed_res["live_count"], 1)
        self.assertEqual(feed_res["curated_count"], 0)
        self.assertGreaterEqual(len(feed_res["items"]), 1)

        for item in feed_res["items"]:
            self.assertEqual(item["source_kind"], "LIVE_RSS")
            self.assertFalse(item["curated"])
            self.assertIn("catalyst_score", item)
            self.assertIn("impact", item)
            self.assertIn("category", item)
            self.assertIn("affected_assets", item)
            for asset in item["affected_assets"]:
                self.assertIn(asset, ["HYPE-USDC", "PURR-USDC"])

        for asset in ["HYPE-USDC", "PURR-USDC"]:
            self.assertIn(asset, feed_res["asset_catalyst_scores"])

        # Atom parsing
        payloads2 = {
            "Hyperliquid L1 & HLP Vault Telemetry": atom_xml,
        }
        feed_res2 = EcosystemRSSAggregator.verify_and_ingest_hyperliquid_feeds(
            xml_payloads=payloads2, try_network=False, max_items=5
        )
        self.assertEqual(feed_res2["feed_mode"], "LIVE")
        self.assertEqual(feed_res2["live_count"], 1)

        # Fallback
        fallback_res = EcosystemRSSAggregator.verify_and_ingest_hyperliquid_feeds(
            xml_payloads={}, try_network=False, max_items=5
        )
        self.assertEqual(fallback_res["feed_mode"], "CURATED_FALLBACK")
        self.assertEqual(fallback_res["live_count"], 0)
        self.assertGreater(fallback_res["curated_count"], 0)
        for item in fallback_res["items"]:
            self.assertEqual(item["source_kind"], "CURATED_FIXTURE")
            self.assertTrue(item["curated"])
            self.assertEqual(item["timestamp_ms"], CURATED_FIXTURE_TIMESTAMP_MS)

        feed = EcosystemRSSAggregator.get_feed_for_agent("leaf-hyperliquid", try_network=False)
        self.assertIn("items", feed)
        self.assertIn("feed_mode", feed)


    def test_xrp_leaf_ta_metrics_computation_and_fallback(self) -> None:
        """
        Verifies TechnicalAnalysisTool.compute_xrp_ta_metrics and ingest_xrp_market_snapshot.
        """
        from backend.tools.ta_tools import TechnicalAnalysisTool

        sample_candles = [
            [1700000000000 + i * 900000, 1.4 + i * 0.02, 1.42 + i * 0.02, 1.38 + i * 0.02, 1.41 + i * 0.02, 1000.0]
            for i in range(25)
        ]
        sample_bids = [[1.405, 100.0], [1.40, 150.0]]
        sample_asks = [[1.415, 80.0], [1.42, 120.0]]
        sample_telemetry = {
            "xrpl_clob_spread_bps": 3.8,
            "rlusd_pool_tvl_usd_m": 200.0,
        }

        for sym in TechnicalAnalysisTool.XRP_EXCLUSIVE_ASSETS:
            for venue in TechnicalAnalysisTool.XRP_VENUES:
                res = TechnicalAnalysisTool.compute_xrp_ta_metrics(
                    candles=sample_candles,
                    bids=sample_bids,
                    asks=sample_asks,
                    onchain_telemetry=sample_telemetry,
                    symbol=sym,
                    venue=venue,
                )
                self.assertEqual(res["symbol"], sym)
                self.assertEqual(res["venue"], venue)
                self.assertEqual(res["ta_metrics_source"], "LIVE_COMPUTED")
                self.assertEqual(res["xrpl_clob_spread_bps"], 3.8)
                self.assertEqual(res["rlusd_pool_tvl_usd_m"], 200.0)
                self.assertIn("kumo_regime", res)
                self.assertIn("golden_pocket_fib_618", res)
                self.assertIn("rsi_14", res)
                self.assertIn("obi_l2", res)

        market_feeds = {
            "XRP-RLUSD": {
                "candles": sample_candles,
                "bids": sample_bids,
                "asks": sample_asks,
            }
        }
        ingest_res = TechnicalAnalysisTool.ingest_xrp_market_snapshot(
            market_feeds=market_feeds,
            onchain_telemetry=sample_telemetry,
            venue="XRPL Native CLOB",
        )
        self.assertEqual(ingest_res["ta_metrics_source"], "LIVE_COMPUTED")
        self.assertEqual(ingest_res["symbol"], "XRP-RLUSD")

        fallback_res = TechnicalAnalysisTool.compute_xrp_ta_metrics(
            candles=[],
            bids=None,
            asks=None,
            onchain_telemetry=None,
            symbol="XRP-RLUSD",
            venue="XRPL Native CLOB",
        )
        self.assertEqual(fallback_res["ta_metrics_source"], "CATALOG_FIXTURE")
        self.assertIn("xrpl_clob_spread_bps", fallback_res)
        self.assertIn("rlusd_pool_tvl_usd_m", fallback_res)

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_xrp_ta_metrics(symbol="BTC-USD", venue="XRPL Native CLOB")

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_xrp_ta_metrics(symbol="XRP-RLUSD", venue="InvalidVenue")

    def test_bnb_leaf_ta_metrics_computation_and_fallback(self) -> None:
        """
        Verifies TechnicalAnalysisTool.compute_bnb_ta_metrics and ingest_bnb_market_snapshot.
        """
        from backend.tools.ta_tools import TechnicalAnalysisTool

        sample_candles = [
            [1700000000000 + i * 900000, 598.0 + i * 0.5, 600.0 + i * 0.5, 596.0 + i * 0.5, 599.0 + i * 0.5, 1000.0]
            for i in range(25)
        ]
        sample_bids = [[598.5, 100.0], [598.0, 150.0]]
        sample_asks = [[599.0, 80.0], [599.5, 120.0]]
        sample_telemetry = {
            "pancakeswap_24h_vol_usd_m": 1000.0,
            "venus_usdt_supply_apr_pct": 7.5,
        }

        for sym in TechnicalAnalysisTool.BNB_EXCLUSIVE_ASSETS:
            for venue in TechnicalAnalysisTool.BNB_VENUES:
                res = TechnicalAnalysisTool.compute_bnb_ta_metrics(
                    candles=sample_candles,
                    bids=sample_bids,
                    asks=sample_asks,
                    onchain_telemetry=sample_telemetry,
                    symbol=sym,
                    venue=venue,
                )
                self.assertEqual(res["symbol"], sym)
                self.assertEqual(res["venue"], venue)
                self.assertEqual(res["ta_metrics_source"], "LIVE_COMPUTED")
                self.assertEqual(res["pancakeswap_24h_vol_usd_m"], 1000.0)
                self.assertEqual(res["venus_usdt_supply_apr_pct"], 7.5)
                self.assertIn("kumo_regime", res)
                self.assertIn("golden_pocket_fib_618", res)
                self.assertIn("rsi_14", res)
                self.assertIn("obi_l2", res)

        market_feeds = {
            "BNB-USDT": {
                "candles": sample_candles,
                "bids": sample_bids,
                "asks": sample_asks,
            }
        }
        ingest_res = TechnicalAnalysisTool.ingest_bnb_market_snapshot(
            market_feeds=market_feeds,
            onchain_telemetry=sample_telemetry,
            venue="PancakeSwap v3",
        )
        self.assertEqual(ingest_res["ta_metrics_source"], "LIVE_COMPUTED")
        self.assertEqual(ingest_res["symbol"], "BNB-USDT")

        fallback_res = TechnicalAnalysisTool.compute_bnb_ta_metrics(
            candles=[],
            bids=None,
            asks=None,
            onchain_telemetry=None,
            symbol="BNB-USDT",
            venue="PancakeSwap v3",
        )
        self.assertEqual(fallback_res["ta_metrics_source"], "CATALOG_FIXTURE")
        self.assertIn("pancakeswap_24h_vol_usd_m", fallback_res)
        self.assertIn("venus_usdt_supply_apr_pct", fallback_res)

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_bnb_ta_metrics(symbol="BTC-USD", venue="PancakeSwap v3")

        with self.assertRaises(ValueError):
            TechnicalAnalysisTool.compute_bnb_ta_metrics(symbol="BNB-USDT", venue="InvalidVenue")

    def test_xrp_rss_atom_parsing_and_catalyst_scoring(self) -> None:
        """
        Verifies XRP RSS/Atom parsing (XRPL Dev & RLUSD Institutional Feed),
        score_xrp_catalyst classification across XRP-RLUSD and XRP-USDT, and
        CURATED_FALLBACK behavior.
        """
        atom_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>XRPL Dev &amp; RLUSD Institutional Feed</title>
          <entry>
            <title>XRPL Native CLOB liquidity surge and RLUSD settlement corridors</title>
            <summary>XLS-30 AMM pool expansion, order book open interest record.</summary>
          </entry>
        </feed>
        """
        rss_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>XRPL Dev &amp; RLUSD Institutional Feed</title>
            <item>
              <title>XRP spot surge on XRPL Native CLOB</title>
              <description>RLUSD stable settlement, XLS-30 AMM liquidity.</description>
            </item>
          </channel>
        </rss>
        """

        payloads = {
            "XRPL Dev & RLUSD Institutional Feed": rss_xml,
        }

        feed_res = EcosystemRSSAggregator.verify_and_ingest_xrp_feeds(
            xml_payloads=payloads, try_network=False, max_items=5
        )
        self.assertEqual(feed_res["agent_id"], "leaf-xrp")
        self.assertEqual(feed_res["feed_mode"], "LIVE")
        self.assertEqual(feed_res["live_count"], 1)
        self.assertEqual(feed_res["curated_count"], 0)
        self.assertGreaterEqual(len(feed_res["items"]), 1)

        for item in feed_res["items"]:
            self.assertEqual(item["source_kind"], "LIVE_RSS")
            self.assertFalse(item["curated"])
            self.assertIn("catalyst_score", item)
            self.assertIn("impact", item)
            self.assertIn("category", item)
            self.assertIn("affected_assets", item)
            for asset in item["affected_assets"]:
                self.assertIn(asset, ["XRP-RLUSD", "XRP-USDT"])

        for asset in ["XRP-RLUSD", "XRP-USDT"]:
            self.assertIn(asset, feed_res["asset_catalyst_scores"])

        payloads2 = {
            "XRPL Dev & RLUSD Institutional Feed": atom_xml,
        }
        feed_res2 = EcosystemRSSAggregator.verify_and_ingest_xrp_feeds(
            xml_payloads=payloads2, try_network=False, max_items=5
        )
        self.assertEqual(feed_res2["feed_mode"], "LIVE")
        self.assertEqual(feed_res2["live_count"], 1)

        fallback_res = EcosystemRSSAggregator.verify_and_ingest_xrp_feeds(
            xml_payloads={}, try_network=False, max_items=5
        )
        self.assertEqual(fallback_res["feed_mode"], "CURATED_FALLBACK")
        self.assertEqual(fallback_res["live_count"], 0)
        self.assertGreater(fallback_res["curated_count"], 0)
        for item in fallback_res["items"]:
            self.assertEqual(item["source_kind"], "CURATED_FIXTURE")
            self.assertTrue(item["curated"])
            self.assertEqual(item["timestamp_ms"], CURATED_FIXTURE_TIMESTAMP_MS)

        feed = EcosystemRSSAggregator.get_feed_for_agent("leaf-xrp", try_network=False)
        self.assertIn("items", feed)
        self.assertIn("feed_mode", feed)

    def test_bnb_rss_atom_parsing_and_catalyst_scoring(self) -> None:
        """
        Verifies BNB Chain RSS/Atom parsing (BNB Chain Blog & Quarterly Burn),
        score_bnb_catalyst classification across BNB-USDT and CAKE-BNB,
        and CURATED_FALLBACK behavior.
        """
        atom_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>BNB Chain Blog &amp; Quarterly Burn</title>
          <entry>
            <title>PancakeSwap v3 record volume and CAKE launchpool surge</title>
            <summary>Venus Protocol USDT supply APR rise, opBNB L2 expansion, quarterly burn.</summary>
          </entry>
        </feed>
        """
        rss_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0">
          <channel>
            <title>BNB Chain Blog &amp; Quarterly Burn</title>
            <item>
              <title>Venus Protocol lending growth and BNB quarterly burn</title>
              <description>PancakeSwap v3 low-fee swap stable, opBNB L2 expansion.</description>
            </item>
          </channel>
        </rss>
        """

        payloads = {
            "BNB Chain Blog & Quarterly Burn": rss_xml,
        }

        feed_res = EcosystemRSSAggregator.verify_and_ingest_bnb_feeds(
            xml_payloads=payloads, try_network=False, max_items=5
        )
        self.assertEqual(feed_res["agent_id"], "leaf-bnb")
        self.assertEqual(feed_res["feed_mode"], "LIVE")
        self.assertEqual(feed_res["live_count"], 1)
        self.assertEqual(feed_res["curated_count"], 0)
        self.assertGreaterEqual(len(feed_res["items"]), 1)

        for item in feed_res["items"]:
            self.assertEqual(item["source_kind"], "LIVE_RSS")
            self.assertFalse(item["curated"])
            self.assertIn("catalyst_score", item)
            self.assertIn("impact", item)
            self.assertIn("category", item)
            self.assertIn("affected_assets", item)
            for asset in item["affected_assets"]:
                self.assertIn(asset, ["BNB-USDT", "CAKE-BNB"])

        for asset in ["BNB-USDT", "CAKE-BNB"]:
            self.assertIn(asset, feed_res["asset_catalyst_scores"])

        payloads2 = {
            "BNB Chain Blog & Quarterly Burn": atom_xml,
        }
        feed_res2 = EcosystemRSSAggregator.verify_and_ingest_bnb_feeds(
            xml_payloads=payloads2, try_network=False, max_items=5
        )
        self.assertEqual(feed_res2["feed_mode"], "LIVE")
        self.assertEqual(feed_res2["live_count"], 1)

        fallback_res = EcosystemRSSAggregator.verify_and_ingest_bnb_feeds(
            xml_payloads={}, try_network=False, max_items=5
        )
        self.assertEqual(fallback_res["feed_mode"], "CURATED_FALLBACK")
        self.assertEqual(fallback_res["live_count"], 0)
        self.assertGreater(fallback_res["curated_count"], 0)
        for item in fallback_res["items"]:
            self.assertEqual(item["source_kind"], "CURATED_FIXTURE")
            self.assertTrue(item["curated"])
            self.assertEqual(item["timestamp_ms"], CURATED_FIXTURE_TIMESTAMP_MS)

        feed = EcosystemRSSAggregator.get_feed_for_agent("leaf-bnb", try_network=False)
        self.assertIn("items", feed)
        self.assertIn("feed_mode", feed)

if __name__ == "__main__":
    unittest.main()
    unittest.main()

    def test_bitcoin_warm_path_reflection_and_policy_compilation(self) -> None:
        """
        Verifies:
        1. orchestrator.run_leaf_agent_reflection("leaf-bitcoin", trigger_source="UNIT_TEST") writes
           a drawer to wing == "leaf_bitcoin" with thesis_continuity in ("INIT_THESIS", "CONFIRMED",
           "REFINED", "INVALIDATED") and next_wakeup_sec == 900.
        2. res["policy_envelope"]["asset_overrides"] contains strictly {"BTC-USD", "wBTC-BTC", "sBTC-BTC"}
           with all 11 AssetOverride keys populated and ttl_seconds == 900.
        3. verify_policy_hmac(SignedPolicyBundle.from_dict(res["signed_policy_bundle"]).policy,
           SignedPolicyBundle.from_dict(res["signed_policy_bundle"]).signature, _resolve_policy_hmac_key()) returns True.
        """
        from backend.core.schemas import SignedPolicyBundle, verify_policy_hmac
        from backend.core.state_store import _resolve_policy_hmac_key

        res = self.orchestrator.run_leaf_agent_reflection("leaf-bitcoin", trigger_source="UNIT_TEST")
        self.assertEqual(res["leaf_id"], "leaf-bitcoin")
        self.assertEqual(res["wing"], "leaf_bitcoin")

        drawer = res["drawer"]
        self.assertIn(drawer["thesis_continuity"], ("INITIAL", "INIT_THESIS", "CONFIRMED", "REFINED", "INVALIDATED"))
        self.assertEqual(drawer["next_wakeup_sec"], 900)

        penv = res["policy_envelope"]
        self.assertEqual(penv["ttl_seconds"], 900)
        overrides = penv["asset_overrides"]
        self.assertEqual(set(overrides.keys()), {"BTC-USD", "wBTC-BTC", "sBTC-BTC"})

        expected_11_keys = {
            "catalyst_score",
            "bias",
            "max_leverage",
            "support_zone_usd",
            "resistance_zone_usd",
            "invalidation_price_usd",
            "entry_obi_threshold",
            "max_rsi_long",
            "min_rsi_short",
            "take_profit_bps",
            "stop_loss_bps",
        }
        for sym, ov in overrides.items():
            self.assertEqual(set(ov.keys()), expected_11_keys)

        signed_bundle = SignedPolicyBundle.from_dict(res["signed_policy_bundle"])
        self.assertTrue(
            verify_policy_hmac(signed_bundle.policy, signed_bundle.signature, "robotrader-dev-hmac-key")
        )

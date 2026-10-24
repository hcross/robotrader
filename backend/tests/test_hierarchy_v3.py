from __future__ import annotations

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
from backend.core.state_store import HybridStateStore
from backend.core.transcript_palace import transcript_palace
from backend.tools.rss_tools import EcosystemRSSAggregator


class TestHierarchicalArchitectureV3(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_transcript_path = transcript_palace.storage_path
        self._orig_transcript_entries = list(transcript_palace.entries)
        transcript_palace.storage_path = Path(self._tmpdir.name) / "transcript.jsonl"
        transcript_palace.entries = []

        self.store = HybridStateStore()
        self.store.palace.storage_path = Path(self._tmpdir.name) / "palace.jsonl"
        self.orchestrator = OrchestratorAgent(store=self.store)

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
        self.assertGreater(btc_bt["net_profit_usd"], 0.0)

        eth_bt = self.store.run_rust_backtest_for_leaf("leaf-ethereum")
        self.assertEqual(eth_bt["leaf_id"], "leaf-ethereum")
        self.assertEqual(len(eth_bt["ecosystem_pods"]), 4)
        self.assertGreater(eth_bt["net_profit_usd"], 0.0)

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

    def test_cross_wing_mempalace_and_master_leaf_reflections(self) -> None:
        """
        Verifies that leaf agents write to their isolated wing (`wing=leaf_bitcoin`)
        and the Master Orchestrator reads across all wings (`wing=master_orchestrator`).
        """
        # Lock LLM budget to deterministic fallback so unit test runs offline in <10ms
        self.orchestrator.cost_guard.total_cost_usd = (
            self.orchestrator.cost_guard.daily_budget_usd
        )

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
        cg.openrouter_credit_balance_usd = 1.80  # Below $2.50 low watermark

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

    def test_rust_vault_enclave_26_chains_and_whitelist_enforcement(self) -> None:
        """
        Verifies that all 26 blockchains derive public-only HD wallets from the Rust Vault Enclave
        (`python_private_key_access == False`) and that untrusted checkout addresses are blocked.
        """
        manifest = self.store.hierarchy.vault_manifest
        self.assertFalse(manifest["python_private_key_access"])
        self.assertTrue(manifest["zeroize_on_drop"])
        self.assertEqual(len(manifest["wallets"]), 26)

        for lid, leaf in self.store.hierarchy.leaves.items():
            wv = leaf.get("wallet_vault", {})
            self.assertEqual(wv.get("leaf_id"), lid)
            self.assertTrue(wv.get("master_treasury_address"))
            self.assertTrue(wv.get("leaf_hot_address"))

        # Untrusted destination must be rejected by the Rust Enclave
        rejected = self.store.hierarchy.checkout_funds(
            amount_usd=500.0,
            target_chain="Solana",
            target_token="SOL",
            destination_address="attacker_drain_wallet_xyz",
            quote_only=False,
        )
        self.assertEqual(rejected["status"], "rejected_by_rust_enclave")


if __name__ == "__main__":
    unittest.main()

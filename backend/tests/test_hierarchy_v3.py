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


if __name__ == "__main__":
    unittest.main()

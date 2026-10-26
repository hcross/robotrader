"""Integrity provenance contracts (issue #7).

Every performance number or Palace drawer carries a declared source, or is
absent. These tests are the executable form of the approved spec's scenarios:
they fail if a fabricated constant, a seeded model telemetry, a plausible
default, or a mixed-population block reappears.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.agents.orchestrator import OrchestratorAgent
from backend.core import provenance
from backend.core.agent import CallResult
from backend.core.hierarchy import (
    ATTRIBUTED_LIVE_LEAF_IDS,
    LEGACY_PERFORMANCE_KEYS,
    HierarchicalFleetManager,
    leaf_performance,
)
from backend.core.memory_palace import PalaceDrawer, StrategyMemoryPalace
from backend.core.state_store import HybridStateStore

FIXTURE_SUMMARY = {
    "initial_equity_usd": 10000.0,
    "final_equity_usd": 10025.66,
    "net_profit_usd": 25.66,
    "total_return_pct": 0.257,
    "max_drawdown_pct": 0.0,
    "sharpe_ratio": 26.88,
    "win_rate_pct": 100.0,
    "total_trades": 6,
    "rejected_orders": 1,
    "total_fees_usd": 1.78,
    "pod_pnl_attribution": {"pod_carry": 13.61, "pod_momentum": 11.11},
    "executions": [{"symbol": "SOL-USDT", "realized_pnl_usd": 6.0}] * 6,
}

LLM_RESPONSE = json.dumps(
    {
        "thesis_continuity": "CONFIRMED",
        "panorama_summary": "Panorama test",
        "ta_confluence_notes": "Confluence test",
        "hypothesis": "Hypothèse test",
        "invalidation_condition": "Invalidation test",
        "next_wakeup_sec": 900,
        "wakeup_reason": "Test",
    }
)


def _live_report(
    simulated: float = 0.0,
    realized: float | None = 0.0,
    timestamp_ms: int = 1_800_000_000_000,
) -> dict:
    return {
        "timestamp_ms": timestamp_ms,
        "pod_id": "pod_carry",
        "symbol": "SOL-USDT",
        "venue": "BINANCE_TESTNET_LIVE",
        "realized_pnl_usd": realized,
        "simulated_pnl_usd": simulated,
        "fee_usd": 0.01,
    }


def _populations(
    live_pnl=None,
    live_trades=0,
    live_win_rate=None,
    live_sharpe=None,
    paper_pnl=None,
    paper_win_rate=None,
) -> dict:
    return {
        "live_testnet": {
            "source": "MEASURED",
            "recent": {
                "trades": live_trades,
                "pnl_usd": live_pnl if live_pnl is not None else 0.0,
                "win_rate_pct": live_win_rate,
                "sharpe_ratio": live_sharpe,
            },
        },
        "paper_model": {
            "source": "SIMULATED",
            "cumulative_pnl_usd": paper_pnl,
            "lifetime": {"win_rate_pct": paper_win_rate},
        },
    }


class FakeRedis:
    """Minimal in-memory replacement for the RESP helper."""

    def __init__(self) -> None:
        self.store: dict = {}
        self.sets: list = []

    def __call__(self, redis_url, command, *args):
        if command == "GET":
            return self.store.get(args[0])
        if command == "SET":
            self.store[args[0]] = args[1]
            self.sets.append((args[0], args[1]))
            return "OK"
        return None


def _no_redis() -> mock._patch:
    return mock.patch.dict(os.environ, {"REDIS_URL": ""}, clear=False)


class ProvenanceVocabularyTests(unittest.TestCase):
    def test_population_mapping_and_unknown_rejection(self) -> None:
        self.assertEqual(provenance.execution_rows_source("backtest_fixture"), "FIXTURE")
        self.assertEqual(provenance.execution_rows_source("paper_model"), "SIMULATED")
        self.assertEqual(provenance.execution_rows_source("live_testnet"), "MEASURED")
        self.assertIsNone(provenance.execution_rows_source("rust_leaf_backtest"))
        self.assertIsNone(provenance.execution_rows_source("unknown"))
        self.assertIsNone(provenance.execution_rows_source(None))
        self.assertIsNone(provenance.normalise_metric_source("rust_leaf_backtest"))

    def test_drawer_eligibility_and_fail_closed_normalisation(self) -> None:
        self.assertTrue(provenance.eligible_drawer_source("LLM"))
        self.assertTrue(provenance.eligible_drawer_source("DETERMINISTIC_FALLBACK"))
        self.assertFalse(provenance.eligible_drawer_source("BOOTSTRAP"))
        self.assertFalse(provenance.eligible_drawer_source(None))

        legacy = provenance.normalise_drawer_fields(
            {
                "model_used": "deepseek/deepseek-v4.1-flash",
                "tokens_used": 1420,
                "cost_usd": 0.00048,
                "thesis_continuity": "CONFIRMED",
            }
        )
        self.assertEqual(legacy["source"], "BOOTSTRAP")
        self.assertEqual(legacy["model_used"], "")
        self.assertEqual(legacy["tokens_used"], 0)
        self.assertEqual(legacy["cost_usd"], 0.0)
        self.assertEqual(legacy["thesis_continuity"], "INITIAL")

        unknown = provenance.normalise_drawer_fields({"source": "SEEDED"})
        self.assertEqual(unknown["source"], "BOOTSTRAP")

        bootstrap = provenance.normalise_drawer_fields(
            {
                "source": "BOOTSTRAP",
                "model_used": "model",
                "tokens_used": 5,
                "cost_usd": 1.0,
                "thesis_continuity": "REFINED",
            }
        )
        self.assertEqual(
            (
                bootstrap["model_used"],
                bootstrap["tokens_used"],
                bootstrap["cost_usd"],
                bootstrap["thesis_continuity"],
            ),
            ("", 0, 0.0, "INITIAL"),
        )

        llm = provenance.normalise_drawer_fields(
            {
                "source": "LLM",
                "model_used": "model",
                "tokens_used": 10,
                "cost_usd": 0.01,
                "thesis_continuity": "CONFIRMED",
            }
        )
        self.assertEqual(llm["source"], "LLM")
        self.assertEqual(llm["tokens_used"], 10)


class PopulationProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = _no_redis()
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = HybridStateStore()
        self.run_patch = mock.patch(
            "backend.core.state_store.resolve_robotrader_binary",
            return_value=Path("robotrader-node"),
        )
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.sub_patch = mock.patch(
            "backend.core.state_store.subprocess.run",
            return_value=mock.Mock(stdout=json.dumps(FIXTURE_SUMMARY)),
        )
        self.sub_patch.start()
        self.addCleanup(self.sub_patch.stop)

    def test_engine_populations_carry_enum_sources(self) -> None:
        populations = self.store.get_population_metrics()
        self.assertEqual(populations["backtest_fixture"]["source"], "FIXTURE")
        self.assertEqual(populations["paper_model"]["source"], "SIMULATED")
        self.assertEqual(populations["live_testnet"]["source"], "MEASURED")
        self.assertEqual(
            populations["backtest_fixture"]["source_detail"],
            "engine-rs deterministic replay (synthetic scenario)",
        )
        self.assertIn(
            "L2 slippage", populations["paper_model"]["source_detail"]
        )
        self.assertIn("realized_pnl_usd", populations["live_testnet"]["source_detail"])

    def test_sample_stats_sharpe_is_null_when_undefined(self) -> None:
        one = HybridStateStore._sample_stats([{"realized_pnl_usd": 3.0}], "realized_pnl_usd")
        self.assertIsNone(one["sharpe_ratio"])
        zero_variance = HybridStateStore._sample_stats(
            [{"realized_pnl_usd": 3.0}, {"realized_pnl_usd": 3.0}], "realized_pnl_usd"
        )
        self.assertIsNone(zero_variance["sharpe_ratio"])
        two = HybridStateStore._sample_stats(
            [{"realized_pnl_usd": 1.0}, {"realized_pnl_usd": 3.0}], "realized_pnl_usd"
        )
        self.assertAlmostEqual(two["sharpe_ratio"], 1.4142, places=4)

    def test_both_backtest_branches_are_labelled(self) -> None:
        solana = self.store.run_rust_backtest_for_leaf("leaf-solana")
        self.assertEqual(solana["source"], "FIXTURE")
        self.assertEqual(solana["executions_source"], "backtest_fixture")

        btc = self.store.run_rust_backtest_for_leaf("leaf-bitcoin")
        self.assertEqual(btc["source"], "FIXTURE")
        self.assertEqual(btc["executions_source"], "backtest_fixture")
        self.assertEqual(
            btc["source_detail"],
            "engine-rs deterministic leaf replay (robotrader-node --leaf-id)",
        )
        stored = self.store.hierarchy.leaves["leaf-bitcoin"]["last_rust_backtest"]
        self.assertEqual(stored["source"], "FIXTURE")
        self.assertEqual(stored["source_detail"], btc["source_detail"])

    def test_testnet_telemetry_is_measured_and_drops_mixed_fields(self) -> None:
        telemetry = self.store.get_testnet_telemetry()
        self.assertEqual(telemetry["source"], "MEASURED")
        self.assertIn("source_detail", telemetry)
        self.assertNotIn("simulated_model_pnl_usd", telemetry)
        self.assertNotIn("solana_" + "onchain_pnl_sol", telemetry)

        self.store.is_testnet_mode = False
        disabled = self.store.get_testnet_telemetry()
        self.assertFalse(disabled["enabled"])
        self.assertEqual(disabled["source"], "MEASURED")
        self.assertNotIn("binance_realized_pnl_usd", disabled)
        self.assertNotIn("simulated_model_pnl_usd", disabled)

    def test_auditor_reports_a_fixture_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            auditor = OrchestratorAgent(
                store=self.store,
                ledger_path=Path(tmp) / "transcript_ledger.jsonl",
            ).quant_auditor
        result = auditor.audit_latest_backtest()
        self.assertEqual(result["source"], "FIXTURE")
        self.assertIn("deterministic", result["source_detail"])
        self.assertTrue(result["verdict"].startswith("FIXTURE_"))


class LeafPerformanceTests(unittest.TestCase):
    def test_non_solana_leaf_reports_null_live_and_paper_metrics(self) -> None:
        performance = leaf_performance("leaf-bitcoin", _populations())
        self.assertEqual(performance["live_testnet"]["source"], "MEASURED")
        self.assertEqual(performance["paper_model"]["source"], "SIMULATED")
        self.assertIsNone(performance["live_testnet"]["realized_pnl_usd"])
        self.assertIsNone(performance["live_testnet"]["win_rate_pct"])
        self.assertIsNone(performance["live_testnet"]["sharpe_ratio"])
        self.assertIsNone(performance["paper_model"]["paper_pnl_usd"])
        self.assertIsNone(performance["paper_model"]["win_rate_pct"])
        self.assertIsNone(performance["paper_model"]["sharpe_ratio"])

    def test_solana_derives_from_attributed_rows_and_paper_population(self) -> None:
        performance = leaf_performance(
            "leaf-solana",
            _populations(
                live_pnl=6.0,
                live_trades=2,
                live_win_rate=100.0,
                live_sharpe=1.4142,
                paper_pnl=1.5,
                paper_win_rate=50.0,
            ),
        )
        self.assertEqual(performance["live_testnet"]["realized_pnl_usd"], 6.0)
        self.assertEqual(performance["live_testnet"]["win_rate_pct"], 100.0)
        self.assertEqual(performance["live_testnet"]["sharpe_ratio"], 1.4142)
        self.assertEqual(performance["paper_model"]["paper_pnl_usd"], 1.5)
        self.assertEqual(performance["paper_model"]["win_rate_pct"], 50.0)
        self.assertIsNone(performance["paper_model"]["sharpe_ratio"])

    def test_single_row_leaves_sharpe_null(self) -> None:
        stats = HybridStateStore._sample_stats(
            [{"realized_pnl_usd": 1.0}], "realized_pnl_usd"
        )
        performance = leaf_performance(
            "leaf-solana",
            _populations(
                live_pnl=1.0,
                live_trades=1,
                live_win_rate=100.0,
                live_sharpe=stats["sharpe_ratio"],
            ),
        )
        self.assertEqual(performance["live_testnet"]["realized_pnl_usd"], 1.0)
        self.assertIsNone(performance["live_testnet"]["sharpe_ratio"])

    def test_empty_populations_keep_their_sources(self) -> None:
        performance = leaf_performance("leaf-bitcoin", None)
        self.assertEqual(performance["live_testnet"]["source"], "MEASURED")
        self.assertEqual(performance["paper_model"]["source"], "SIMULATED")
        self.assertIsNone(performance["live_testnet"]["realized_pnl_usd"])


class HierarchyProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.palace = StrategyMemoryPalace(
            storage_path=Path(self._tmp.name) / "palace.jsonl"
        )
        self.manager = HierarchicalFleetManager(palace=self.palace)

    def test_leaf_detail_has_no_flat_mirror_and_null_position_count(self) -> None:
        detail = self.manager.get_leaf_detail(
            "leaf-bitcoin", populations=_populations()
        )
        for key in ("realized_pnl_usd", "paper_pnl_usd", "sharpe_ratio", "win_rate_pct"):
            self.assertNotIn(key, detail)
            self.assertNotIn(key, detail["leaf"])
        self.assertIsNone(detail["active_positions_count"])
        self.assertEqual(detail["performance"]["live_testnet"]["source"], "MEASURED")

    def test_deposit_does_not_synthesize_performance(self) -> None:
        before = self.manager.get_leaf_detail(
            "leaf-bitcoin", populations=_populations()
        )["performance"]
        self.manager.deposit_funds(amount_usd=5000.0)
        after = self.manager.get_leaf_detail(
            "leaf-bitcoin", populations=_populations()
        )["performance"]
        self.assertEqual(before, after)
        self.assertIsNone(after["live_testnet"]["realized_pnl_usd"])

    def test_position_count_stays_null_before_and_after_liquidation(self) -> None:
        self.assertIsNone(
            self.manager.get_leaf_detail(
                "leaf-solana", populations=_populations()
            )["active_positions_count"]
        )
        self.manager.emergency_liquidate_leaf("leaf-solana", reason="test")
        self.assertNotIn("active_positions_count", self.manager.leaves["leaf-solana"])
        self.assertIsNone(
            self.manager.get_leaf_detail(
                "leaf-solana", populations=_populations()
            )["active_positions_count"]
        )

    def test_treasury_aggregate_sums_measured_values_only(self) -> None:
        fake = {
            "leaf-solana": {
                "performance": {
                    "live_testnet": {"realized_pnl_usd": 10.0, "source": "MEASURED"}
                }
            },
            "leaf-bitcoin": {
                "performance": {
                    "live_testnet": {"realized_pnl_usd": -4.0, "source": "MEASURED"}
                }
            },
            "leaf-ethereum": {
                "performance": {
                    "live_testnet": {"realized_pnl_usd": None, "source": "MEASURED"},
                    "paper_model": {"paper_pnl_usd": 100.0, "source": "SIMULATED"},
                }
            },
        }

        def fake_detail(leaf_id, **kwargs):
            return fake.get(
                leaf_id,
                {
                    "performance": {
                        "live_testnet": {"realized_pnl_usd": None, "source": "MEASURED"}
                    }
                },
            )

        with mock.patch.object(self.manager, "get_leaf_detail", side_effect=fake_detail):
            snapshot = self.manager.get_hierarchy_snapshot()
        self.assertEqual(snapshot["treasury"]["total_realized_pnl_usd"], 6.0)
        self.assertEqual(snapshot["treasury"]["source"], "MEASURED")

    def test_null_aggregate_declares_bootstrap(self) -> None:
        snapshot = self.manager.get_hierarchy_snapshot(solana_populations=None)
        self.assertIsNone(snapshot["treasury"]["total_realized_pnl_usd"])
        self.assertEqual(snapshot["treasury"]["source"], "BOOTSTRAP")
        self.assertNotEqual(
            snapshot["treasury"]["total_realized_pnl_usd"],
            round(self.manager.deployed_capital_usd * 0.018, 2),
        )

    def test_absent_defaults_are_null_and_measured_zero_survives(self) -> None:
        snapshot = self.manager.get_hierarchy_snapshot(
            cost_status={"openrouter_credit": {}}, solana_populations=None
        )
        self.assertIsNone(snapshot["openrouter_credit"]["credit_balance_usd"])
        self.assertNotEqual(snapshot["openrouter_credit"]["credit_balance_usd"], 24.5)

        measured_zero = self.manager.get_hierarchy_snapshot(
            cost_status={"openrouter_credit": {"credit_balance_usd": 0.0}},
            solana_populations=None,
        )
        self.assertEqual(measured_zero["openrouter_credit"]["credit_balance_usd"], 0.0)

        with mock.patch("backend.core.hierarchy.LEAF_ECOSYSTEM_CATALOG", []):
            empty = self.manager.get_hierarchy_snapshot(solana_populations=None)
        self.assertIsNone(empty["treasury"]["active_leaves_count"])

    def test_empty_leaf_population_is_null_not_zero(self) -> None:
        snapshot = self.manager.get_hierarchy_snapshot(
            solana_populations=_populations(), cost_status={}
        )
        bitcoin = next(lf for lf in snapshot["leaves"] if lf["id"] == "leaf-bitcoin")
        self.assertIsNone(bitcoin["performance"]["live_testnet"]["realized_pnl_usd"])
        self.assertEqual(bitcoin["performance"]["live_testnet"]["source"], "MEASURED")
        self.assertIsNone(bitcoin["performance"]["paper_model"]["paper_pnl_usd"])
        self.assertEqual(bitcoin["performance"]["paper_model"]["source"], "SIMULATED")


class PersistedStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.redis = FakeRedis()

    def _manager(self) -> HierarchicalFleetManager:
        palace = StrategyMemoryPalace(
            storage_path=Path(self._tmp.name) / "palace.jsonl"
        )
        return HierarchicalFleetManager(
            palace=palace, redis_cmd_fn=self.redis, redis_url="redis://fake"
        )

    def test_legacy_performance_is_ignored_and_compacted(self) -> None:
        self.redis.store[HierarchicalFleetManager.REDIS_HIERARCHY_KEY] = json.dumps(
            {
                "total_capital_usd": 31000.0,
                "long_term_strategy_thesis": "thesis-kept",
                "leaves": {
                    "leaf-solana": {
                        "allocated_capital_usd": 1000.0,
                        "capital_weight": 0.04,
                        "risk_posture": "AGGRESSIVE",
                        "enabled": True,
                        "objective_summary": "keep-solana",
                        "realized_pnl_usd": 999.0,
                        "paper_pnl_usd": 888.0,
                        "sharpe_ratio": 2.45,
                        "win_rate_pct": 64.5,
                        "active_positions_count": 2,
                    },
                    "leaf-bitcoin": {
                        "allocated_capital_usd": 500.0,
                        "capital_weight": 0.02,
                        "risk_posture": "DEFENSIVE",
                        "enabled": True,
                        "objective_summary": "keep-bitcoin",
                    },
                },
                "deposit_history": [{"amount_usd": 1.0}],
                "checkout_history": [{"amount_usd": 2.0}],
            }
        )

        manager = self._manager()

        self.assertEqual(manager.total_capital_usd, 31000.0)
        self.assertEqual(manager.long_term_strategy_thesis, "thesis-kept")
        self.assertNotIn("realized_pnl_usd", manager.leaves["leaf-solana"])
        self.assertNotIn("active_positions_count", manager.leaves["leaf-solana"])
        self.assertEqual(manager.leaves["leaf-solana"]["allocated_capital_usd"], 1000.0)
        self.assertEqual(manager.leaves["leaf-bitcoin"]["risk_posture"], "DEFENSIVE")
        self.assertEqual(manager.leaves["leaf-bitcoin"]["objective_summary"], "keep-bitcoin")
        self.assertEqual(manager.deposit_history, [{"amount_usd": 1.0}])
        self.assertEqual(manager.checkout_history, [{"amount_usd": 2.0}])

        solana = manager.get_leaf_detail("leaf-solana", populations=None)
        self.assertIsNone(solana["performance"]["live_testnet"]["realized_pnl_usd"])
        for key in ("realized_pnl_usd", "paper_pnl_usd", "sharpe_ratio", "win_rate_pct"):
            self.assertNotIn(key, solana)
            self.assertNotIn(key, solana["leaf"])
        self.assertIsNone(solana["active_positions_count"])
        self.assertIsNone(solana["leaf"]["active_positions_count"])
        self.assertNotEqual(
            solana["performance"]["live_testnet"]["realized_pnl_usd"], 999.0
        )
        self.assertNotEqual(solana["performance"]["paper_model"]["paper_pnl_usd"], 888.0)

        # The one-time compaction wrote the complete payload.
        compacted = json.loads(
            self.redis.store[HierarchicalFleetManager.REDIS_HIERARCHY_KEY]
        )
        self.assertEqual(compacted["total_capital_usd"], 31000.0)
        self.assertEqual(compacted["long_term_strategy_thesis"], "thesis-kept")
        self.assertEqual(compacted["deposit_history"], [{"amount_usd": 1.0}])
        self.assertEqual(compacted["checkout_history"], [{"amount_usd": 2.0}])
        for leaf in compacted["leaves"].values():
            for key in LEGACY_PERFORMANCE_KEYS:
                self.assertNotIn(key, leaf)

    def test_persist_writes_only_allowed_leaf_keys(self) -> None:
        manager = self._manager()
        manager.persist()
        payload = json.loads(
            self.redis.store[HierarchicalFleetManager.REDIS_HIERARCHY_KEY]
        )
        allowed = {
            "allocated_capital_usd",
            "capital_weight",
            "risk_posture",
            "enabled",
            "objective_summary",
        }
        for leaf in payload["leaves"].values():
            self.assertEqual(set(leaf), allowed)
        self.assertIn("total_capital_usd", payload)
        self.assertIn("long_term_strategy_thesis", payload)


class PalaceProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "palace.jsonl"
        self.redis = FakeRedis()

    def test_bootstrap_append_survives_jsonl_and_redis_round_trip(self) -> None:
        palace = StrategyMemoryPalace(
            redis_cmd_fn=self.redis,
            redis_url="redis://fake",
            storage_path=self.path,
        )
        drawer = PalaceDrawer(
            drawer_id="drw_bootstrap",
            timestamp_ms=1,
            wing="leaf_test",
            room="active_theses",
            model_used="should-be-stripped",
            thinking_depth="DEEP_THESIS",
            thesis_continuity="CONFIRMED",
            global_regime="TRENDING_BULL",
            panorama_summary="p",
            ta_confluence_notes="t",
            hypothesis="h",
            invalidation_condition="i",
            tokens_used=42,
            cost_usd=0.5,
            source="BOOTSTRAP",
        )
        palace.add_drawer(drawer)
        self.assertEqual(drawer.source, "BOOTSTRAP")
        self.assertEqual(drawer.model_used, "")
        self.assertEqual(drawer.tokens_used, 0)
        self.assertEqual(drawer.cost_usd, 0.0)
        self.assertEqual(drawer.thesis_continuity, "INITIAL")

        reloaded = StrategyMemoryPalace(
            redis_cmd_fn=self.redis,
            redis_url="redis://fake",
            storage_path=self.path,
        )
        self.assertEqual(reloaded.drawers[0].source, "BOOTSTRAP")

    def test_legacy_untyped_line_is_read_as_bootstrap(self) -> None:
        legacy = {
            "drawer_id": "legacy",
            "timestamp_ms": 1,
            "wing": "strategy_ledger",
            "room": "active_theses",
            "model_used": "deepseek/deepseek-v4.1-flash",
            "thinking_depth": "DEEP_THESIS",
            "thesis_continuity": "CONFIRMED",
            "global_regime": "TRENDING_BULL",
            "panorama_summary": "p",
            "ta_confluence_notes": "t",
            "hypothesis": "h",
            "invalidation_condition": "i",
            "tokens_used": 1420,
            "cost_usd": 0.00048,
        }
        self.path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
        palace = StrategyMemoryPalace(storage_path=self.path)
        drawer = palace.drawers[0]
        self.assertEqual(drawer.source, "BOOTSTRAP")
        self.assertEqual(drawer.model_used, "")
        self.assertEqual(drawer.tokens_used, 0)
        self.assertEqual(drawer.cost_usd, 0.0)
        self.assertEqual(drawer.thesis_continuity, "INITIAL")

    def test_seeded_drawers_are_bootstrap_rows(self) -> None:
        palace = StrategyMemoryPalace(storage_path=self.path)
        manager = HierarchicalFleetManager(palace=palace)
        seeded = [
            d
            for d in palace.drawers
            if d.wing == "master_orchestrator" or d.drawer_id.startswith("drw_leaf_")
        ]
        self.assertGreaterEqual(len(seeded), 1)
        for drawer in seeded:
            self.assertEqual(drawer.source, "BOOTSTRAP")
            self.assertEqual(drawer.model_used, "")
            self.assertEqual(drawer.tokens_used, 0)
            self.assertEqual(drawer.cost_usd, 0.0)
            self.assertEqual(drawer.thesis_continuity, "INITIAL")
        # Seeding only happens when the wing is empty; manager stays usable.
        self.assertIn("leaf-solana", manager.leaves)

    def test_prompts_exclude_bootstrap_and_filter_before_limit(self) -> None:
        palace = StrategyMemoryPalace(storage_path=self.path)

        def add(drawer_id, source, hypothesis, timestamp_ms):
            palace.add_drawer(
                PalaceDrawer(
                    drawer_id=drawer_id,
                    timestamp_ms=timestamp_ms,
                    wing="leaf_test",
                    room="active_theses",
                    model_used="m" if source != "BOOTSTRAP" else "",
                    thinking_depth="DEEP_THESIS",
                    thesis_continuity="CONFIRMED",
                    global_regime="TRENDING_BULL",
                    panorama_summary="",
                    ta_confluence_notes="",
                    hypothesis=hypothesis,
                    invalidation_condition="",
                    tokens_used=1,
                    cost_usd=0.01,
                    source=source,
                )
            )

        add("bs1", "BOOTSTRAP", "SECRET_BOOTSTRAP_HYPOTHESIS", 3)
        add("bs2", "BOOTSTRAP", "SECRET_BOOTSTRAP_HYPOTHESIS_2", 2)
        add("llm1", "LLM", "ELIGIBLE_LLM_HYPOTHESIS", 1)

        prompt = palace.format_continuity_prompt(limit=1, wing="leaf_test")
        self.assertIn("ELIGIBLE_LLM_HYPOTHESIS", prompt)
        self.assertNotIn("SECRET_BOOTSTRAP", prompt)

        digest = palace.format_cross_wing_digest(wings=["leaf_test"], per_wing_limit=1)
        self.assertIn("ELIGIBLE_LLM_HYPOTHESIS", digest)
        self.assertNotIn("SECRET_BOOTSTRAP", digest)

        # recall_recent stays unfiltered so the UI can still show bootstrap drawers.
        recalled = palace.recall_recent(limit=3, wing="leaf_test")
        self.assertEqual(len(recalled), 3)

    def test_fallback_continuity_requires_a_prior_llm_drawer(self) -> None:
        palace = StrategyMemoryPalace(storage_path=self.path)
        self.assertEqual(palace.fallback_continuity("leaf_test"), "INITIAL")
        palace.add_drawer(
            PalaceDrawer(
                drawer_id="llm",
                timestamp_ms=1,
                wing="leaf_test",
                room="active_theses",
                model_used="m",
                thinking_depth="DEEP_THESIS",
                thesis_continuity="CONFIRMED",
                global_regime="TRENDING_BULL",
                panorama_summary="",
                ta_confluence_notes="",
                hypothesis="",
                invalidation_condition="",
                tokens_used=1,
                cost_usd=0.01,
                source="LLM",
            )
        )
        self.assertEqual(palace.fallback_continuity("leaf_test"), "CONFIRMED")
        self.assertEqual(palace.fallback_continuity("leaf_other"), "INITIAL")


class ReflectionProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = _no_redis()
        self.env.start()
        self.addCleanup(self.env.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = HybridStateStore()
        self.store.palace.storage_path = Path(self._tmp.name) / "palace.jsonl"
        from backend.core.transcript_palace import transcript_palace

        self._orig_transcript_path = transcript_palace.storage_path
        self._orig_transcript_entries = list(transcript_palace.entries)
        transcript_palace.storage_path = Path(self._tmp.name) / "transcript.jsonl"
        transcript_palace.entries = []
        self.addCleanup(
            setattr, transcript_palace, "storage_path", self._orig_transcript_path
        )
        self.addCleanup(
            setattr, transcript_palace, "entries", self._orig_transcript_entries
        )
        self.ta_patch = mock.patch.object(
            self.store,
            "refresh_ta_and_panorama",
            return_value={"ta_snapshots": {}, "social_panorama": {}, "tool_timings": []},
        )
        self.ta_patch.start()
        self.addCleanup(self.ta_patch.stop)
        self.orchestrator = OrchestratorAgent(
            store=self.store,
            ledger_path=Path(self._tmp.name) / "transcript_ledger.jsonl",
        )

    def _lock_budget(self) -> None:
        cg = self.orchestrator.cost_guard
        cg.auto_refill_enabled = False
        cg.record_usage({"agent": "test", "cost": cg.daily_budget_usd, "tokens": 0})
        self.assertTrue(cg.budget_exhausted)

    def test_fallback_without_a_call_carries_no_telemetry(self) -> None:
        self._lock_budget()
        result = self.orchestrator.run_leaf_agent_reflection(
            "leaf-bitcoin", trigger_source="UNIT_TEST"
        )
        drawer = result["drawer"]
        self.assertEqual(drawer["source"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(drawer["model_used"], "")
        self.assertEqual(drawer["tokens_used"], 0)
        self.assertEqual(drawer["cost_usd"], 0.0)
        self.assertEqual(drawer["thesis_continuity"], "INITIAL")

    def test_fallback_with_a_prior_llm_drawer_carries_its_continuity(self) -> None:
        wing = self.store.hierarchy.leaves["leaf-bitcoin"]["mempalace_wing"]
        self.store.palace.add_drawer(
            PalaceDrawer(
                drawer_id="prior_llm",
                timestamp_ms=1,
                wing=wing,
                room="active_theses",
                model_used="m",
                thinking_depth="DEEP_THESIS",
                thesis_continuity="CONFIRMED",
                global_regime="TRENDING_BULL",
                panorama_summary="",
                ta_confluence_notes="",
                hypothesis="",
                invalidation_condition="",
                tokens_used=1,
                cost_usd=0.01,
                source="LLM",
            )
        )
        self._lock_budget()
        result = self.orchestrator.run_leaf_agent_reflection(
            "leaf-bitcoin", trigger_source="UNIT_TEST"
        )
        self.assertEqual(result["drawer"]["source"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(result["drawer"]["thesis_continuity"], "CONFIRMED")

    def test_successful_strategic_reflection_is_labelled_llm(self) -> None:
        self.orchestrator.invoke_openrouter = lambda **kwargs: CallResult(
            raw_resp=LLM_RESPONSE,
            model_used="deepseek/deepseek-v4.1-flash-1017",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=1,
        )
        result = self.orchestrator.run_strategic_reflection(
            force=True, trigger_source="UNIT_TEST"
        )
        drawer = result["drawer"]
        self.assertEqual(drawer["source"], "LLM")
        self.assertEqual(drawer["model_used"], "deepseek/deepseek-v4.1-flash-1017")
        self.assertEqual(drawer["tokens_used"], 150)
        stored = self.store.palace.recall_recent(limit=1, wing="strategy_ledger")
        self.assertEqual(stored[0]["source"], "LLM")


class RefillGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = _no_redis()
        self.env.start()
        self.addCleanup(self.env.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = HybridStateStore()
        self.store.palace.storage_path = Path(self._tmp.name) / "palace.jsonl"
        self.run_patch = mock.patch(
            "backend.core.state_store.resolve_robotrader_binary",
            return_value=Path("robotrader-node"),
        )
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.sub_patch = mock.patch(
            "backend.core.state_store.subprocess.run",
            return_value=mock.Mock(stdout=json.dumps(FIXTURE_SUMMARY)),
        )
        self.sub_patch.start()
        self.addCleanup(self.sub_patch.stop)
        self.orchestrator = OrchestratorAgent(
            store=self.store,
            ledger_path=Path(self._tmp.name) / "transcript_ledger.jsonl",
        )

    def test_all_null_rows_give_zero_without_type_error(self) -> None:
        self.store.live_executions = [
            _live_report(simulated=5.0, realized=None),
            _live_report(simulated=-2.0, realized=None),
        ]
        self.assertEqual(self.store.measured_realized_pnl_usd(), 0.0)
        rejected = self.orchestrator.cost_guard.trigger_openrouter_refill(
            realized_trading_pnl_usd=self.store.measured_realized_pnl_usd(), force=True
        )
        self.assertEqual(rejected["status"], "rejected_no_realized_profit")

    def test_refill_sum_excludes_simulated_pnl(self) -> None:
        self.store.live_executions = [
            _live_report(simulated=100.0, realized=10.0),
        ]
        self.assertEqual(self.store.measured_realized_pnl_usd(), 10.0)
        ok = self.orchestrator.cost_guard.trigger_openrouter_refill(
            realized_trading_pnl_usd=self.store.measured_realized_pnl_usd(),
            requested_amount_usd=1.0,
            force=True,
        )
        self.assertEqual(ok["status"], "refilled")

    def test_zero_and_negative_profit_are_rejected_without_a_floor(self) -> None:
        self.store.live_executions = [
            _live_report(simulated=100.0, realized=0.0),
        ]
        self.assertEqual(self.store.measured_realized_pnl_usd(), 0.0)
        zero = self.orchestrator.cost_guard.trigger_openrouter_refill(
            realized_trading_pnl_usd=self.store.measured_realized_pnl_usd(), force=True
        )
        self.assertEqual(zero["status"], "rejected_no_realized_profit")
        self.assertIn("0.00", zero["reason"])

        self.store.live_executions = [
            _live_report(simulated=100.0, realized=-4.0),
        ]
        self.assertEqual(self.store.measured_realized_pnl_usd(), -4.0)
        negative = self.orchestrator.cost_guard.trigger_openrouter_refill(
            realized_trading_pnl_usd=self.store.measured_realized_pnl_usd(), force=True
        )
        self.assertEqual(negative["status"], "rejected_no_realized_profit")
        self.assertIn("-$4.00", negative["reason"])

    def test_helper_equals_snapshot_measured_sum(self) -> None:
        self.store.live_executions = [
            _live_report(simulated=100.0, realized=10.0, timestamp_ms=1),
            _live_report(simulated=100.0, realized=-4.0, timestamp_ms=2),
        ]
        populations = self.store.get_population_metrics()
        snapshot = self.store.hierarchy.get_hierarchy_snapshot(
            cost_status={}, solana_populations=populations
        )
        measured_sum = sum(
            lf["performance"]["live_testnet"]["realized_pnl_usd"]
            for lf in snapshot["leaves"]
            if lf["performance"]["live_testnet"]["realized_pnl_usd"] is not None
        )
        self.assertAlmostEqual(
            self.store.measured_realized_pnl_usd(), measured_sum, places=4
        )
        self.assertEqual(snapshot["treasury"]["total_realized_pnl_usd"], 6.0)

    def test_retained_window_basis_and_lifetime_cex_divergence(self) -> None:
        for i in range(205):
            self.store._record_live_execution(
                _live_report(simulated=0.0, realized=0.01, timestamp_ms=i)
            )
        # The CEX accumulator is a lifetime figure maintained by the live worker.
        self.store.testnet_cex_realized_pnl_usd = 100.0

        populations = self.store.get_population_metrics()
        snapshot = self.store.hierarchy.get_hierarchy_snapshot(
            cost_status={}, solana_populations=populations
        )
        self.assertEqual(populations["live_testnet"]["recent"]["trades"], 200)
        self.assertAlmostEqual(
            snapshot["treasury"]["total_realized_pnl_usd"], 2.0, places=4
        )
        self.assertEqual(
            populations["live_testnet"]["cumulative_cex_pnl_usd"], 100.0
        )
        solana = next(lf for lf in snapshot["leaves"] if lf["id"] == "leaf-solana")
        self.assertIn(
            "recent 200-row window", solana["performance"]["live_testnet"]["source_detail"]
        )


SERVER_CHILD_SCRIPT = r"""
import json
import sys
from pathlib import Path
from unittest import mock

from backend.core.state_store import HybridStateStore
from backend.agents.orchestrator import OrchestratorAgent

FIXTURE_SUMMARY = {
    "initial_equity_usd": 10000.0,
    "final_equity_usd": 10025.66,
    "net_profit_usd": 25.66,
    "total_return_pct": 0.257,
    "max_drawdown_pct": 0.0,
    "sharpe_ratio": 26.88,
    "win_rate_pct": 100.0,
    "total_trades": 6,
    "rejected_orders": 1,
    "total_fees_usd": 1.78,
    "pod_pnl_attribution": {"pod_carry": 13.61},
    "executions": [{"symbol": "SOL-USDT", "realized_pnl_usd": 6.0}] * 6,
}


def _no_worker(self, interval_sec=10.0):
    return None


def _no_scheduler(self):
    return None


# The HTTP contract must be isolated from the network-bound background loops.
HybridStateStore.start_live_worker = _no_worker
OrchestratorAgent.start_cognitive_scheduler = _no_scheduler

import backend.server as server
from fastapi.testclient import TestClient

server.state_store._redis_url = None
server.state_store.live_executions = []
server.state_store.live_pnl_usd = 0.0
server.state_store.hierarchy._redis_url = None
server.state_store.palace._redis_url = None

backtest = mock.patch.object(
    server.state_store,
    "run_rust_backtest",
    side_effect=lambda *args, **kwargs: dict(
        FIXTURE_SUMMARY,
        executions_source="backtest_fixture",
        source="FIXTURE",
        source_detail="engine-rs deterministic replay (synthetic scenario)",
    ),
)
backtest.start()
cognitive = mock.patch.object(
    server.orchestrator,
    "get_cognitive_state",
    side_effect=lambda: {
        "palace_drawers": server.state_store.palace.recall_recent(limit=15)
    },
)
cognitive.start()
client = TestClient(server.app)
scenario = sys.argv[1]


def _live_report(realized):
    return {
        "timestamp_ms": 1,
        "pod_id": "pod_carry",
        "symbol": "SOL-USDT",
        "venue": "BINANCE_TESTNET_LIVE",
        "realized_pnl_usd": realized,
        "simulated_pnl_usd": 100.0,
        "fee_usd": 0.01,
    }


if scenario == "status":
    server.state_store.live_executions = [_live_report(10.0)]
    payload = client.get("/api/v1/status").json()
    assert payload["contract_version"] == 3, payload.get("contract_version")
    assert payload["cost_guard"]["total_spent_usd"] == 0.0, payload["cost_guard"]
    engine = payload["engine_metrics"]
    assert engine["backtest_fixture"]["source"] == "FIXTURE"
    assert engine["paper_model"]["source"] == "SIMULATED"
    assert engine["live_testnet"]["source"] == "MEASURED"
    assert engine["executions_source"] == "live_testnet"
    assert engine["executions"]
    assert all(row["source"] == "MEASURED" for row in engine["executions"])
    for leaf in payload["hierarchy"]["leaves"]:
        assert leaf["performance"]["live_testnet"]["source"] == "MEASURED"
        assert leaf["performance"]["paper_model"]["source"] == "SIMULATED"
        assert leaf["active_positions_count"] is None
        assert "realized_pnl_usd" not in leaf
    treasury = payload["hierarchy"]["treasury"]
    assert treasury["source"] in ("MEASURED", "BOOTSTRAP")
    assert treasury["total_realized_pnl_usd"] == 10.0
    telemetry = payload["testnet_telemetry"]
    assert telemetry["source"] == "MEASURED"
    assert "simulated_model_pnl_usd" not in telemetry
    assert "solana_" + "onchain_pnl_sol" not in telemetry
    drawer_surfaces = [
        payload["cognitive_engine"]["palace_drawers"],
        payload["hierarchy"]["master_orchestrator"]["palace_drawers"],
    ]
    for leaf in payload["hierarchy"]["leaves"]:
        drawer_surfaces.append(leaf["palace_drawers"])
        drawer_surfaces.append(leaf["mempalace_drawers"])
    for drawers in drawer_surfaces:
        for drawer in drawers:
            assert drawer["source"] in ("LLM", "DETERMINISTIC_FALLBACK", "BOOTSTRAP")
elif scenario == "fixture-rows":
    payload = client.get("/api/v1/status").json()
    engine = payload["engine_metrics"]
    assert engine["executions_source"] == "backtest_fixture"
    assert engine["executions"]
    assert all(row["source"] == "FIXTURE" for row in engine["executions"])
elif scenario == "leaf-endpoints":
    populations = {
        "live_testnet": {
            "source": "MEASURED",
            "recent": {
                "trades": 2,
                "pnl_usd": 12.5,
                "win_rate_pct": 100.0,
                "sharpe_ratio": 1.0,
            },
        },
        "paper_model": {
            "source": "SIMULATED",
            "cumulative_pnl_usd": 3.5,
            "lifetime": {"win_rate_pct": 50.0},
        },
    }
    with mock.patch.object(
        server.state_store, "get_population_metrics", return_value=populations
    ):
        detail = client.get("/api/v1/leaf/leaf-solana").json()["leaf"]
        assert detail["performance"]["live_testnet"]["source"] == "MEASURED"
        assert detail["performance"]["paper_model"]["source"] == "SIMULATED"
        assert detail["performance"]["live_testnet"]["realized_pnl_usd"] == 12.5
        mandate = client.post(
            "/api/v1/leaf/leaf-solana/mandate",
            json={"risk_posture": "AGGRESSIVE"},
        ).json()["leaf"]
        assert mandate["performance"]["live_testnet"]["source"] == "MEASURED"
        assert mandate["active_positions_count"] is None
elif scenario == "leaf-solana-backtest":
    backtest.stop()
    with mock.patch(
        "backend.core.state_store.resolve_robotrader_binary",
        return_value=Path("robotrader-node"),
    ), mock.patch(
        "backend.core.state_store.subprocess.run",
        return_value=mock.Mock(stdout=json.dumps(FIXTURE_SUMMARY)),
    ):
        response = client.post("/api/v1/leaf/leaf-solana/backtest")
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]
    assert summary["source"] == "FIXTURE"
    assert summary["executions_source"] == "backtest_fixture"
else:
    raise SystemExit(f"unknown scenario: {scenario}")

print("server provenance contract ok:" + scenario)
"""


class ServerPayloadTests(unittest.TestCase):
    """The HTTP contract runs in an isolated child, like test_missing_binary.

    Importing ``backend.server`` in-process would start the live worker and the
    cognitive scheduler and breaks the suite's parent-process isolation check.
    """

    def _run(self, scenario: str) -> None:
        # The child imports backend.server, so isolate the CostGuard ledger from
        # any developer ledger at the production default.
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-c", SERVER_CHILD_SCRIPT, scenario],
                capture_output=True,
                text=True,
                timeout=120,
                env={
                    **os.environ,
                    "COSTGUARD_LEDGER_PATH": str(
                        Path(tmp) / "transcript_ledger.jsonl"
                    ),
                },
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"server provenance contract ok:{scenario}", result.stdout)
        self.assertNotIn("backend.server", sys.modules)

    def test_status_payload_declares_provenance_everywhere(self) -> None:
        self._run("status")

    def test_fixture_fallback_rows_are_labelled_fixture(self) -> None:
        self._run("fixture-rows")

    def test_leaf_endpoints_derive_populations(self) -> None:
        self._run("leaf-endpoints")

    def test_leaf_solana_backtest_endpoint_is_fixture(self) -> None:
        self._run("leaf-solana-backtest")


if __name__ == "__main__":
    unittest.main()

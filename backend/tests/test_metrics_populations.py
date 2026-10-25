"""Performance populations must never be blended.

Production defect (2026-10-24): `run_rust_backtest` added `len(live_executions)`
to `total_trades` while keeping `win_rate_pct` from the deterministic Rust
fixture, and added the *paper* PnL (`simulated_pnl_usd`) to the fixture's net
profit. The dashboard therefore showed "100% (200 trades)" whose numerator came
from a 4-trade fixture and whose denominator came from live testnet orders.
"""

import json
import os
import unittest
from unittest.mock import Mock, patch

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


def _live_report(simulated: float, realized: float) -> dict:
    return {
        "timestamp_ms": 1_800_000_000_000,
        "pod_id": "pod_carry",
        "symbol": "SOL-USDT",
        "venue": "BINANCE_TESTNET_LIVE",
        "realized_pnl_usd": realized,
        "simulated_pnl_usd": simulated,
        "fee_usd": 0.01,
    }


class TestPerformancePopulations(unittest.TestCase):
    def setUp(self) -> None:
        # Force the no-Redis path so the test owns every stored value.
        self.env = patch.dict(os.environ, {"REDIS_URL": ""}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = HybridStateStore()
        self.run_patch = patch(
            "backend.core.state_store.subprocess.run",
            return_value=Mock(stdout=json.dumps(FIXTURE_SUMMARY)),
        )
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)

    def test_backtest_summary_is_not_merged_with_live_executions(self) -> None:
        self.store._record_live_execution(_live_report(simulated=0.15, realized=-0.006))
        self.store._record_live_execution(_live_report(simulated=0.20, realized=-0.002))

        bt = self.store.run_rust_backtest()

        self.assertEqual(bt["total_trades"], 6)  # fixture count, not 6 + 2
        self.assertEqual(bt["win_rate_pct"], 100.0)  # fixture rate, untouched
        self.assertEqual(bt["net_profit_usd"], 25.66)  # paper PnL NOT added
        self.assertEqual(bt["final_equity_usd"], 10025.66)
        self.assertEqual(bt["total_fees_usd"], 1.78)
        self.assertEqual(len(bt["executions"]), 6)
        self.assertEqual(bt["executions_source"], "backtest_fixture")

    def test_paper_and_live_populations_use_their_own_pnl_column(self) -> None:
        # Both orders lose money for real; one wins and one loses in the paper model.
        self.store._record_live_execution(_live_report(simulated=0.25, realized=-0.006))
        self.store._record_live_execution(_live_report(simulated=-0.10, realized=-0.002))

        populations = self.store.get_population_metrics()

        paper = populations["paper_model"]
        live = populations["live_testnet"]
        self.assertEqual(paper["cumulative_pnl_usd"], 0.15)
        self.assertEqual(paper["recent"]["trades"], 2)
        self.assertEqual(paper["recent"]["wins"], 1)
        self.assertEqual(paper["recent"]["losses"], 1)
        self.assertEqual(paper["recent"]["win_rate_pct"], 50.0)
        self.assertEqual(paper["recent"]["positive_edge_share_pct"], 50.0)
        self.assertFalse(paper["recent"]["deterministic"])
        self.assertTrue(paper["recent"]["adverse_selection_enabled"])
        self.assertEqual(paper["lifetime"]["trades"], 2)
        self.assertEqual(paper["lifetime"]["wins"], 1)
        self.assertEqual(paper["lifetime"]["losses"], 1)
        self.assertEqual(paper["lifetime"]["win_rate_pct"], 50.0)

        self.assertEqual(live["recent"]["pnl_usd"], -0.008)
        self.assertEqual(live["recent"]["trades"], 2)
        self.assertEqual(live["recent"]["wins"], 0)
        self.assertEqual(live["recent"]["win_rate_pct"], 0.0)

    def test_paper_execution_model_produces_wins_and_adverse_selection_losses(self) -> None:
        win_eval = HybridStateStore.compute_paper_execution_pnl(
            notional_usd=100.0,
            fee_usd=0.036,
            side="BUY",
            obi=0.28,
            price_change_bps=8.0,
            rsi_val=52.0,
            spread_bps=2.0,
            entry_obi_threshold=0.08,
            max_rsi_long=68.0,
        )
        loss_eval = HybridStateStore.compute_paper_execution_pnl(
            notional_usd=100.0,
            fee_usd=0.036,
            side="BUY",
            obi=-0.22,
            price_change_bps=-12.0,
            rsi_val=74.0,
            spread_bps=4.0,
            entry_obi_threshold=0.08,
            max_rsi_long=68.0,
        )
        self.assertGreater(win_eval["simulated_pnl_usd"], 0.0)
        self.assertGreater(win_eval["net_edge_bps"], 0.0)
        self.assertLess(loss_eval["simulated_pnl_usd"], 0.0)
        self.assertLess(loss_eval["net_edge_bps"], 0.0)
        self.assertGreater(loss_eval["adverse_selection_bps"], 20.0)

    def test_paper_short_rsi_threshold_uses_min_rsi_short(self) -> None:
        # Short at RSI 40: min_rsi_short=45 applies a 16 bps exhaustion penalty,
        # while the old `100 - max_rsi_long` (= 30) derivation applied none.
        with_min_rsi_short = HybridStateStore.compute_paper_execution_pnl(
            notional_usd=100.0,
            fee_usd=0.036,
            side="SELL",
            obi=-0.28,
            price_change_bps=-8.0,
            rsi_val=40.0,
            spread_bps=2.0,
            entry_obi_threshold=0.08,
            max_rsi_long=70.0,
            min_rsi_short=45.0,
        )
        with_legacy_threshold = HybridStateStore.compute_paper_execution_pnl(
            notional_usd=100.0,
            fee_usd=0.036,
            side="SELL",
            obi=-0.28,
            price_change_bps=-8.0,
            rsi_val=40.0,
            spread_bps=2.0,
            entry_obi_threshold=0.08,
            max_rsi_long=70.0,
            min_rsi_short=30.0,
        )
        self.assertAlmostEqual(with_min_rsi_short["adverse_selection_bps"], 16.0)
        self.assertEqual(with_legacy_threshold["adverse_selection_bps"], 0.0)

    def test_paper_lifetime_counters_persist_beyond_200_window(self) -> None:
        for i in range(205):
            sim = 0.10 if i % 2 == 0 else -0.05
            self.store._record_live_execution(_live_report(simulated=sim, realized=0.0))

        populations = self.store.get_population_metrics()
        paper = populations["paper_model"]
        self.assertEqual(paper["recent"]["trades"], 200)
        self.assertEqual(paper["lifetime"]["trades"], 205)
        self.assertEqual(paper["lifetime"]["wins"], 103)
        self.assertEqual(paper["lifetime"]["losses"], 102)

    def test_fixture_population_reports_its_own_consistency(self) -> None:
        populations = self.store.get_population_metrics()
        fixture = populations["backtest_fixture"]

        self.assertEqual(fixture["trades"], 6)
        self.assertEqual(fixture["win_rate_pct"], 100.0)
        self.assertEqual(fixture["cumulative_pnl_usd"], 25.66)
        self.assertEqual(fixture["source"], "FIXTURE")
        self.assertEqual(
            fixture["source_detail"], "engine-rs deterministic replay (synthetic scenario)"
        )

    def test_win_rate_breakdown_counts_flat_executions(self) -> None:
        stats = HybridStateStore._sample_stats(
            [
                {"realized_pnl_usd": 1.0},
                {"realized_pnl_usd": -1.0},
                {"realized_pnl_usd": 0.0},
            ],
            "realized_pnl_usd",
        )
        self.assertEqual((stats["wins"], stats["losses"], stats["flat"]), (1, 1, 1))
        self.assertEqual(stats["win_rate_pct"], 33.3)
        self.assertEqual(stats["pnl_usd"], 0.0)

    def test_absent_population_reports_none_not_zero(self) -> None:
        populations = self.store.get_population_metrics()
        recent = populations["live_testnet"]["recent"]

        self.assertEqual(recent["trades"], 0)
        self.assertIsNone(recent["win_rate_pct"])  # renders as "—", never "0%"
        self.assertIsNone(recent["from_ms"])


if __name__ == "__main__":
    unittest.main()

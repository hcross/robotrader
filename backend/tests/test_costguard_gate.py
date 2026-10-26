"""CostGuard profit gate, rolling windows, hydration, and status contracts.

Every test uses an injected clock and an isolated temporary ledger so the
result is independent of the host machine's developer ledger and wall clock.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.agents import monitor as monitor_module
from backend.agents.monitor import LLMMonitorAgent, ROLLING_WINDOW_MS
from backend.agents.orchestrator import OrchestratorAgent
from backend.core import state_store as state_store_module
from backend.core.state_store import HybridStateStore

_UNSET = object()


class _Clock:
    def __init__(self, now_ms: int = 1_700_000_000_000) -> None:
        self.now_ms = int(now_ms)

    def __call__(self) -> int:
        return self.now_ms

    def advance(self, delta_ms: int) -> None:
        self.now_ms += int(delta_ms)


class _Store:
    def __init__(self, pnl: float = 0.0, kill_switch_active: bool = False) -> None:
        self.pnl = float(pnl)
        self.kill_switch_active = bool(kill_switch_active)

    def measured_realized_pnl_usd(self) -> float:
        return self.pnl


class _CostGuardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmpdir = Path(self._tmp.name)
        self.clock = _Clock()

    def guard(
        self,
        store=None,
        ledger_path=_UNSET,
        env=None,
        **kwargs,
    ) -> LLMMonitorAgent:
        if ledger_path is _UNSET:
            ledger_path = self.tmpdir / "transcript_ledger.jsonl"
        merged_env = {
            "OPENROUTER_INITIAL_BALANCE_USD": "8.50",
            "OPENROUTER_LOW_WATERMARK_USD": "2.00",
            "OPENROUTER_REFILL_AMOUNT_USD": "10.00",
            "OPENROUTER_MAX_EPOCH_REFILL_USD": "25.00",
            "MAX_DAILY_LLM_BUDGET_USD": "5.0",
            "COSTGUARD_LEDGER_PATH": "",
            **dict(env or {}),
        }
        with mock.patch.dict(os.environ, merged_env, clear=False):
            return LLMMonitorAgent(
                store=store,
                ledger_path=ledger_path,
                now_ms=self.clock,
                **kwargs,
            )

    def write_ledger(self, entries, name="transcript_ledger.jsonl") -> Path:
        path = self.tmpdir / name
        with path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry) + "\n")
        return path

    @staticmethod
    def entry(timestamp_ms: int, cost_usd: float, **extra) -> dict:
        return {
            "timestamp_ms": int(timestamp_ms),
            "agent": "test",
            "model_used": "deepseek/deepseek-v4.1-flash-1017",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": float(cost_usd),
            **extra,
        }


class InjectionAndSourceTests(_CostGuardTestCase):
    def test_construction_without_store_returns_a_status_payload(self) -> None:
        cg = self.guard(store=None)
        status = cg.get_status()
        self.assertFalse(status["openrouter_credit"]["measured_pnl_source_available"])

    def test_orchestrator_injects_its_own_store(self) -> None:
        store = HybridStateStore()
        store.live_executions = [
            {
                "timestamp_ms": 1,
                "pod_id": "pod_carry",
                "symbol": "SOL-USDT",
                "venue": "BINANCE_TESTNET_LIVE",
                "realized_pnl_usd": -10.0,
                "simulated_pnl_usd": 100.0,
                "fee_usd": 0.01,
            }
        ]
        orchestrator = OrchestratorAgent(
            store=store,
            ledger_path=self.tmpdir / "transcript_ledger.jsonl",
        )
        cg = orchestrator.cost_guard
        cg.openrouter_balance_usd = 2.5

        # A different process-global store would report a large profit; it must
        # never be consulted because the orchestrator's own instance is injected.
        with mock.patch.object(
            state_store_module.state_store,
            "measured_realized_pnl_usd",
            return_value=100.0,
        ):
            cg.record_usage({"agent": "test", "cost": 0.5, "tokens": 0})

        self.assertEqual(cg.refill_history, [])
        self.assertEqual(cg.epoch_refilled_usd, 0.0)
        self.assertAlmostEqual(cg.openrouter_balance_usd, 2.0, places=6)
        self.assertEqual(
            cg.last_refill_rejection["status"], "rejected_no_realized_profit"
        )

    def test_automatic_path_performs_no_refill_without_a_source(self) -> None:
        cg = self.guard(store=None)
        cg.openrouter_balance_usd = 2.5

        cg.record_usage({"agent": "test", "cost": 0.5, "tokens": 0})

        self.assertEqual(cg.refill_history, [])
        self.assertEqual(cg.epoch_refilled_usd, 0.0)
        self.assertAlmostEqual(cg.openrouter_balance_usd, 2.0, places=6)
        self.assertEqual(cg.last_refill_rejection["status"], "rejected_no_pnl_source")

    def test_operator_path_rejects_a_missing_source(self) -> None:
        cg = self.guard(store=None)
        cg.openrouter_balance_usd = 1.8

        result = cg.operator_refill(force=True)

        self.assertEqual(result["status"], "rejected_no_pnl_source")
        self.assertAlmostEqual(cg.openrouter_balance_usd, 1.8, places=6)
        self.assertEqual(cg.epoch_refilled_usd, 0.0)
        self.assertEqual(cg.refill_history, [])


class GateTests(_CostGuardTestCase):
    def test_missing_realized_pnl_argument_raises_before_mutation(self) -> None:
        cg = self.guard(store=_Store(pnl=100.0))
        balance = cg.openrouter_balance_usd

        with self.assertRaises(TypeError):
            cg.trigger_openrouter_refill()  # type: ignore[call-arg]

        self.assertEqual(cg.openrouter_balance_usd, balance)
        self.assertEqual(cg.epoch_refilled_usd, 0.0)
        self.assertEqual(cg.refill_history, [])

    def test_negative_and_zero_pnl_are_rejected_without_mutation(self) -> None:
        cg = self.guard(store=_Store(pnl=-10.0))
        balance = cg.openrouter_balance_usd

        negative = cg.trigger_openrouter_refill(realized_trading_pnl_usd=-10.0, force=True)
        self.assertEqual(negative["status"], "rejected_no_realized_profit")
        self.assertIn("-$10.00", negative["reason"])
        self.assertNotIn("$125.00", negative["reason"])

        zero = cg.trigger_openrouter_refill(realized_trading_pnl_usd=0.0, force=True)
        self.assertEqual(zero["status"], "rejected_no_realized_profit")
        self.assertIn("$0.00", zero["reason"])

        self.assertEqual(cg.openrouter_balance_usd, balance)
        self.assertEqual(cg.epoch_refilled_usd, 0.0)
        self.assertEqual(cg.refill_history, [])

    def test_automatic_negative_and_zero_pnl_do_not_refill(self) -> None:
        for pnl in (-10.0, 0.0):
            with self.subTest(pnl=pnl):
                self.clock.now_ms += 1
                cg = self.guard(store=_Store(pnl=pnl))
                cg.openrouter_balance_usd = 2.5

                cg.record_usage({"agent": "test", "cost": 0.5, "tokens": 0})

                self.assertEqual(cg.refill_history, [])
                self.assertEqual(cg.epoch_refilled_usd, 0.0)
                self.assertAlmostEqual(cg.openrouter_balance_usd, 2.0, places=6)
                self.assertEqual(
                    cg.last_refill_rejection["status"],
                    "rejected_no_realized_profit",
                )

    def test_automatic_amount_above_profit_share_is_rejected(self) -> None:
        cg = self.guard(store=_Store(pnl=50.0))
        result = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=50.0,
            requested_amount_usd=10.0,
            force=True,
        )
        self.assertEqual(result["status"], "rejected_exceeds_profit_share")
        self.assertEqual(cg.openrouter_balance_usd, 8.5)
        self.assertEqual(cg.refill_history, [])

    def test_amount_within_every_cap_refills(self) -> None:
        cg = self.guard(store=_Store(pnl=100.0))
        cg.openrouter_balance_usd = 2.0

        result = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0,
            requested_amount_usd=4.0,
        )

        self.assertEqual(result["status"], "refilled")
        self.assertAlmostEqual(cg.openrouter_balance_usd, 6.0, places=6)
        self.assertAlmostEqual(cg.epoch_refilled_usd, 4.0, places=6)

    def test_single_refill_bound_is_fixed(self) -> None:
        cg = self.guard(store=_Store(pnl=10_000.0))

        zero = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=0.0, force=True
        )
        too_large = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=25.01, force=True
        )

        self.assertEqual(zero["status"], "rejected")
        self.assertEqual(too_large["status"], "rejected")
        self.assertEqual(cg.refill_history, [])

    def test_default_epoch_cap_blocks_and_raised_cap_allows(self) -> None:
        cg = self.guard(store=_Store(pnl=10_000.0))
        first = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=23.0, force=True
        )
        self.assertEqual(first["status"], "refilled")
        blocked = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=4.0, force=True
        )
        self.assertEqual(blocked["status"], "rejected_epoch_cap")
        self.assertAlmostEqual(cg.epoch_refilled_usd, 23.0, places=6)

        raised = self.guard(
            store=_Store(pnl=10_000.0),
            env={"OPENROUTER_MAX_EPOCH_REFILL_USD": "40.00"},
        )
        raised.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=23.0, force=True
        )
        allowed = raised.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=4.0, force=True
        )
        self.assertEqual(allowed["status"], "refilled")
        self.assertAlmostEqual(raised.epoch_refilled_usd, 27.0, places=6)

    def test_epoch_window_boundary_is_exclusive(self) -> None:
        cg = self.guard(store=_Store(pnl=10_000.0))
        start = self.clock.now_ms
        first = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=20.0, force=True
        )
        self.assertEqual(first["status"], "refilled")

        self.clock.now_ms = start + ROLLING_WINDOW_MS - 1
        still_counted = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=6.0, force=True
        )
        self.assertEqual(still_counted["status"], "rejected_epoch_cap")

        self.clock.now_ms = start + ROLLING_WINDOW_MS
        rolled_over = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=6.0, force=True
        )
        self.assertEqual(rolled_over["status"], "refilled")
        self.assertAlmostEqual(cg.epoch_refilled_usd, 6.0, places=6)

    def test_kill_switch_blocks_automatic_and_forced_operator_paths(self) -> None:
        cg = self.guard(store=_Store(pnl=100.0, kill_switch_active=True))
        cg.openrouter_balance_usd = 2.5
        cg.record_usage({"agent": "test", "cost": 0.5, "tokens": 0})
        self.assertEqual(cg.refill_history, [])
        self.assertAlmostEqual(cg.openrouter_balance_usd, 2.0, places=6)
        self.assertEqual(cg.last_refill_rejection["status"], "rejected_kill_switch")

        forced = cg.operator_refill(force=True)
        self.assertEqual(forced["status"], "rejected_kill_switch")
        self.assertAlmostEqual(cg.openrouter_balance_usd, 2.0, places=6)
        self.assertEqual(cg.epoch_refilled_usd, 0.0)

    def test_inactive_kill_switch_lets_the_gate_proceed(self) -> None:
        cg = self.guard(store=_Store(pnl=100.0, kill_switch_active=False))
        cg.openrouter_balance_usd = 2.0

        result = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0, requested_amount_usd=4.0
        )

        self.assertEqual(result["status"], "refilled")

    def test_force_bypasses_only_the_watermark(self) -> None:
        cg = self.guard(store=_Store(pnl=100.0))
        cg.openrouter_balance_usd = 5.0

        skipped = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0, requested_amount_usd=4.0, force=False
        )
        self.assertEqual(skipped["status"], "skipped_sufficient_balance")

        forced = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=100.0, requested_amount_usd=4.0, force=True
        )
        self.assertEqual(forced["status"], "refilled")

        no_profit = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=-10.0, requested_amount_usd=4.0, force=True
        )
        self.assertEqual(no_profit["status"], "rejected_no_realized_profit")

        share = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=4.0, requested_amount_usd=1.0, force=True
        )
        self.assertEqual(share["status"], "rejected_exceeds_profit_share")

    def test_rejection_does_not_consume_epoch_headroom(self) -> None:
        cg = self.guard(store=_Store(pnl=1_000.0))

        cg.trigger_openrouter_refill(realized_trading_pnl_usd=0.0, force=True)
        self.assertEqual(cg.epoch_refilled_usd, 0.0)

        result = cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=1_000.0, requested_amount_usd=25.0, force=True
        )
        self.assertEqual(result["status"], "refilled")
        self.assertAlmostEqual(cg.epoch_refilled_usd, 25.0, places=6)


class RollingSpendWindowTests(_CostGuardTestCase):
    def test_spend_older_than_24h_is_excluded(self) -> None:
        cg = self.guard(store=None)
        cg.record_usage({"agent": "test", "cost": 4.0, "tokens": 0})
        self.clock.advance(ROLLING_WINDOW_MS + 1)

        self.assertEqual(cg.total_cost_usd, 0.0)
        self.assertFalse(cg.budget_exhausted)

    def test_24h_boundary_is_exclusive(self) -> None:
        cg = self.guard(store=None)
        start = self.clock.now_ms
        cg.record_usage({"agent": "test", "cost": 4.0, "tokens": 0})

        self.clock.now_ms = start + ROLLING_WINDOW_MS - 1
        self.assertEqual(cg.total_cost_usd, 4.0)

        self.clock.now_ms = start + ROLLING_WINDOW_MS
        self.assertEqual(cg.total_cost_usd, 0.0)

    def test_reported_total_is_the_window_not_lifetime(self) -> None:
        cg = self.guard(store=None)
        start = self.clock.now_ms
        cg.record_usage({"agent": "test", "cost": 4.0, "tokens": 0})
        self.clock.now_ms = start + ROLLING_WINDOW_MS
        cg.record_usage({"agent": "test", "cost": 1.0, "tokens": 0})

        self.assertEqual(cg.total_cost_usd, 1.0)

    def test_budget_and_thinking_depth_recover_after_rollover(self) -> None:
        cg = self.guard(store=None)
        start = self.clock.now_ms
        cg.record_usage({"agent": "test", "cost": cg.daily_budget_usd, "tokens": 0})
        self.assertTrue(cg.budget_exhausted)
        self.assertEqual(cg.get_thinking_depth(), "DETERMINISTIC_LOCK")

        self.clock.now_ms = start + ROLLING_WINDOW_MS

        self.assertFalse(cg.budget_exhausted)
        self.assertEqual(cg.get_thinking_depth(), "DEEP_THESIS")

    def test_window_works_without_redis(self) -> None:
        cg = self.guard(store=None, env={"REDIS_URL": ""})
        cg.record_usage({"agent": "test", "cost": 1.5, "tokens": 0})
        self.assertEqual(cg.total_cost_usd, 1.5)

    def test_record_prunes_old_entries(self) -> None:
        cg = self.guard(store=None)
        start = self.clock.now_ms
        cg.record_usage({"agent": "test", "cost": 1.0, "tokens": 0})
        self.clock.now_ms = start + ROLLING_WINDOW_MS
        cg.record_usage({"agent": "test", "cost": 2.0, "tokens": 0})
        self.assertEqual(cg.total_cost_usd, 2.0)

    def test_aggregates_are_read_only(self) -> None:
        cg = self.guard(store=None)
        with self.assertRaises(AttributeError):
            cg.total_cost_usd = 1.0  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            cg.epoch_refilled_usd = 1.0  # type: ignore[misc]


class HydrationTests(_CostGuardTestCase):
    def test_construction_performs_no_ledger_read(self) -> None:
        directory = self.tmpdir / "a_directory"
        directory.mkdir()
        cg = self.guard(store=None, ledger_path=directory)

        with self.assertRaises(OSError):
            _ = cg.total_cost_usd
        with self.assertRaises(OSError):
            cg.hydrate_from_ledger()

    def test_isolated_path_blocks_a_developer_ledger(self) -> None:
        self.write_ledger([self.entry(self.clock.now_ms, 50.0)], "developer.jsonl")
        cg = self.guard(store=None, ledger_path=self.tmpdir / "isolated.jsonl")
        self.assertEqual(cg.total_cost_usd, 0.0)

    def test_default_path_does_not_depend_on_the_working_directory(self) -> None:
        previous = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            cg = self.guard(
                store=None,
                ledger_path=None,
                env={"COSTGUARD_LEDGER_PATH": ""},
            )
        finally:
            os.chdir(previous)

        expected = (
            Path(monitor_module.__file__).resolve().parents[1]
            / "data"
            / "transcript_ledger.jsonl"
        )
        self.assertEqual(cg.ledger_path, expected)

    def test_empty_environment_override_is_treated_as_unset(self) -> None:
        cg = self.guard(
            store=None,
            ledger_path=None,
            env={"COSTGUARD_LEDGER_PATH": "   "},
        )
        expected = (
            Path(monitor_module.__file__).resolve().parents[1]
            / "data"
            / "transcript_ledger.jsonl"
        )
        self.assertEqual(cg.ledger_path, expected)

    def test_environment_override_is_resolved(self) -> None:
        target = self.tmpdir / "from_env.jsonl"
        cg = self.guard(
            store=None,
            ledger_path=None,
            env={"COSTGUARD_LEDGER_PATH": str(target)},
        )
        self.assertEqual(cg.ledger_path, target)

    def test_rotated_segment_contributes_in_window_entries(self) -> None:
        self.write_ledger([self.entry(self.clock.now_ms, 2.0)], "transcript_ledger.jsonl.1")
        cg = self.guard(store=None)
        self.assertEqual(cg.hydrate_from_ledger()["hydrated_cost_usd"], 2.0)
        self.assertEqual(cg.total_cost_usd, 2.0)

    def test_authoritative_cost_is_the_larger_of_recorded_and_computed(self) -> None:
        self.write_ledger(
            [
                {
                    "timestamp_ms": self.clock.now_ms,
                    "agent": "test",
                    "model_used": "deepseek/deepseek-v4.1-flash-1017",
                    "prompt_tokens": 100_000,
                    "completion_tokens": 20_000,
                    "cost_usd": 0.01,
                }
            ]
        )
        cg = self.guard(store=None)
        hydrated = cg.hydrate_from_ledger()
        # 0.1 USD/M * 0.1M + 1.1 USD/M * 0.02M = 0.03 + 0.022 = 0.052
        self.assertAlmostEqual(hydrated["hydrated_cost_usd"], 0.052, places=6)

    def test_ledger_boundary_pair_keeps_only_the_younger_entry(self) -> None:
        older = self.entry(self.clock.now_ms - ROLLING_WINDOW_MS, 2.0)
        younger = self.entry(self.clock.now_ms - ROLLING_WINDOW_MS + 1, 1.0)
        self.write_ledger([older, younger])
        cg = self.guard(store=None)
        self.assertEqual(cg.hydrate_from_ledger()["hydrated_cost_usd"], 1.0)

    def test_scan_order_out_of_window_before_in_window(self) -> None:
        older = self.entry(self.clock.now_ms - ROLLING_WINDOW_MS - 5, 9.0)
        younger = self.entry(self.clock.now_ms - 5, 1.0)
        self.write_ledger([older, younger])
        cg = self.guard(store=None)
        self.assertEqual(cg.hydrate_from_ledger()["hydrated_cost_usd"], 1.0)

    def test_late_appended_older_entry_documents_the_early_stop(self) -> None:
        # Monotonicity violation: the older entry is written last, so the reverse
        # scan meets it first and stops, missing the newer in-window entry.
        newer = self.entry(self.clock.now_ms - 5, 1.0)
        older = self.entry(self.clock.now_ms - ROLLING_WINDOW_MS - 5, 9.0)
        self.write_ledger([newer, older])
        cg = self.guard(store=None)
        self.assertEqual(cg.hydrate_from_ledger()["hydrated_cost_usd"], 0.0)

    def test_repeated_hydration_does_not_double_count(self) -> None:
        self.write_ledger(
            [
                self.entry(self.clock.now_ms - 10, 1.0),
                self.entry(self.clock.now_ms - 5, 2.0),
            ]
        )
        cg = self.guard(store=None)
        first = cg.hydrate_from_ledger()
        second = cg.hydrate_from_ledger()
        self.assertAlmostEqual(first["hydrated_cost_usd"], 3.0, places=6)
        self.assertAlmostEqual(second["hydrated_cost_usd"], 3.0, places=6)
        self.assertAlmostEqual(cg.total_cost_usd, 3.0, places=6)

    def test_missing_ledger_leaves_spend_at_zero(self) -> None:
        cg = self.guard(store=None, ledger_path=self.tmpdir / "absent.jsonl")
        hydrated = cg.hydrate_from_ledger()
        self.assertEqual(hydrated["hydrated_cost_usd"], 0.0)
        self.assertEqual(cg.total_cost_usd, 0.0)

    def test_explicit_return_is_the_local_scan_sum(self) -> None:
        self.write_ledger([self.entry(self.clock.now_ms, 2.5)])
        cg = self.guard(store=None)
        hydrated = cg.hydrate_from_ledger()
        self.assertAlmostEqual(hydrated["hydrated_cost_usd"], 2.5, places=6)
        self.assertAlmostEqual(cg.total_cost_usd, hydrated["hydrated_cost_usd"], places=6)

    def test_hydration_precedes_the_first_record_and_reseed_replaces(self) -> None:
        ledger = self.write_ledger([self.entry(self.clock.now_ms, 2.0)])
        cg = self.guard(store=None, ledger_path=ledger)
        cg.record_usage({"agent": "test", "cost": 1.0, "tokens": 0})
        self.assertAlmostEqual(cg.total_cost_usd, 3.0, places=6)

        fresh = self.guard(store=None, ledger_path=ledger)
        self.assertAlmostEqual(fresh.hydrate_from_ledger()["hydrated_cost_usd"], 2.0, places=6)
        self.assertAlmostEqual(fresh.hydrate_from_ledger()["hydrated_cost_usd"], 2.0, places=6)
        fresh.record_usage({"agent": "test", "cost": 1.0, "tokens": 0})
        self.assertAlmostEqual(fresh.total_cost_usd, 3.0, places=6)
        fresh.hydrate_from_ledger()
        self.assertAlmostEqual(fresh.total_cost_usd, 2.0, places=6)
        self.assertEqual(fresh.epoch_refilled_usd, 0.0)

    def test_concurrent_calls_scan_once_and_do_not_double_seed(self) -> None:
        ledger = self.write_ledger([self.entry(self.clock.now_ms, 3.0)])
        cg = self.guard(store=None, ledger_path=ledger)
        real_scan = LLMMonitorAgent._scan_ledger
        scans = []
        started = threading.Event()
        release = threading.Event()
        errors = []
        results = []

        def slow_scan(inner_self, path, now_ms):
            scans.append(path)
            started.set()
            release.wait(timeout=5.0)
            return real_scan(inner_self, path, now_ms)

        def reader() -> None:
            try:
                results.append(cg.total_cost_usd)
            except Exception as exc:  # pragma: no cover - failure diagnostics
                errors.append(exc)

        with mock.patch.object(LLMMonitorAgent, "_scan_ledger", slow_scan):
            first = threading.Thread(target=reader)
            second = threading.Thread(target=reader)
            first.start()
            self.assertTrue(started.wait(timeout=5.0))
            second.start()
            time.sleep(0.05)
            release.set()
            first.join(timeout=5.0)
            second.join(timeout=5.0)

        self.assertEqual(errors, [])
        self.assertEqual(len(scans), 1)
        self.assertEqual(len(results), 2)
        for value in results:
            self.assertAlmostEqual(value, 3.0, places=6)

    def test_monitor_does_not_buffer_the_ledger(self) -> None:
        source = Path(monitor_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("read_text", source)
        self.assertNotIn("splitlines", source)


class StatusTests(_CostGuardTestCase):
    def test_default_watermark_and_source_flag(self) -> None:
        cg = self.guard(store=_Store(pnl=100.0))
        credit = cg.get_status()["openrouter_credit"]
        self.assertEqual(credit["low_watermark_usd"], 2.0)
        self.assertTrue(credit["measured_pnl_source_available"])
        self.assertIsNone(credit["last_refill_rejection"])

    def test_configured_watermark_governs_the_trigger_boundary(self) -> None:
        env = {"OPENROUTER_LOW_WATERMARK_USD": "3.50"}
        at_watermark = self.guard(store=_Store(pnl=100.0), env=env)
        at_watermark.openrouter_balance_usd = 3.50
        at_watermark.record_usage({"agent": "test", "cost": 0.0, "tokens": 0})
        self.assertEqual(len(at_watermark.refill_history), 1)

        above = self.guard(store=_Store(pnl=100.0), env=env)
        above.openrouter_balance_usd = 3.51
        above.record_usage({"agent": "test", "cost": 0.0, "tokens": 0})
        self.assertEqual(above.refill_history, [])

    def test_enabled_and_disabled_labels(self) -> None:
        cg = self.guard(store=_Store(pnl=100.0))
        status = cg.get_status()
        self.assertEqual(status["auto_wallet_refill"], "ENABLED_PROFIT_GATED")
        self.assertEqual(
            status["auto_refill_policy"], "PROFIT_GATED_CAPPED_BY_ORCHESTRATOR"
        )

        cg.auto_refill_enabled = False
        status = cg.get_status()
        self.assertEqual(status["auto_wallet_refill"], "DISABLED")
        self.assertEqual(status["auto_refill_policy"], "DISABLED")

    def test_storeless_status_keeps_the_configured_enum(self) -> None:
        cg = self.guard(store=None)
        status = cg.get_status()
        self.assertEqual(status["auto_wallet_refill"], "ENABLED_PROFIT_GATED")
        self.assertEqual(
            status["auto_refill_policy"], "PROFIT_GATED_CAPPED_BY_ORCHESTRATOR"
        )
        self.assertFalse(status["openrouter_credit"]["measured_pnl_source_available"])

    def test_rejected_automatic_refill_is_observable_without_history(self) -> None:
        cg = self.guard(store=_Store(pnl=-10.0))
        cg.openrouter_balance_usd = 2.5
        cg.record_usage({"agent": "test", "cost": 0.5, "tokens": 0})

        status = cg.get_status()
        credit = status["openrouter_credit"]
        self.assertEqual(credit["refill_history"], [])
        self.assertEqual(
            credit["last_refill_rejection"]["status"], "rejected_no_realized_profit"
        )
        self.assertIn("-$10.00", credit["last_refill_rejection"]["reason"])
        self.assertEqual(status["auto_wallet_refill"], "ENABLED_PROFIT_GATED")

    def test_epoch_refilled_total_follows_the_rolling_window(self) -> None:
        cg = self.guard(store=_Store(pnl=10_000.0))
        start = self.clock.now_ms
        cg.trigger_openrouter_refill(
            realized_trading_pnl_usd=10_000.0, requested_amount_usd=4.0, force=True
        )
        self.assertEqual(cg.get_status()["openrouter_credit"]["epoch_refilled_usd"], 4.0)

        self.clock.now_ms = start + ROLLING_WINDOW_MS
        self.assertEqual(cg.get_status()["openrouter_credit"]["epoch_refilled_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()

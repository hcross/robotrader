"""PolicyEnvelope TTL authority must survive live-worker ticks and restores.

The live worker used to rewrite ``issued_at_ms`` on every 10 s tick and the
restore path used to stamp the restore clock, so the documented fail-safe could
never trigger. This change records no liveness state at all: a tick proves
nothing about policy authority and therefore writes nothing to the envelope.

Offline and deterministic: the exchange venue, the Redis read/write, and the
clock are injected, so no network, credentials, or wall-clock time is involved.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Callable, Dict, List, Optional
from unittest import mock

from backend.core.schemas import SAFE_BASELINE_TTL_SECONDS, PolicyEnvelope
from backend.core.state_store import HybridStateStore
import backend.tools.exchange_tools
import backend.tools.solana_tools

T0 = 1_800_000_000_000
TTL_SECONDS = 900
TTL_MS = TTL_SECONDS * 1000

POLICY_KEYS = {
    "envelope_id",
    "issued_at_ms",
    "ttl_seconds",
    "global_regime",
    "pod_allocations",
    "asset_overrides",
}


class FakeClock:
    """Callable replacement for ``time.time`` expressed in milliseconds."""

    def __init__(self, now_ms: int = T0) -> None:
        self.now_ms = now_ms

    def __call__(self) -> float:
        return self.now_ms / 1000.0


class FakeExchange:
    """Minimal order-book venue, optionally calling back while a tick is open."""

    def __init__(self, on_fetch: Optional[Callable[[], None]] = None) -> None:
        self._on_fetch = on_fetch

    def fetch_order_book(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        if self._on_fetch is not None:
            self._on_fetch()
        return {"bids": [[100.0, 10.0]], "asks": [[100.1, 5.0]]}


class RaisingExchange:
    """Venue whose order-book call always fails, to exercise the raising tick."""

    def fetch_order_book(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        raise RuntimeError("venue unavailable")


class FakeBinance:
    """Authenticated CEX venue double: book, order, and balance, no network."""

    def __init__(self, exchange: Optional[Any] = None) -> None:
        self.authenticated = True
        self.exchange = exchange or FakeExchange()

    def place_order(self, symbol: str, side: str, qty: float, price=None, post_only=False) -> Dict[str, Any]:
        return {
            "status": "success",
            "order": {"id": "fake-order", "average": 100.0, "filled": qty, "amount": qty},
        }

    def get_usdt_balance(self) -> Dict[str, Any]:
        return {"status": "ok", "free_usdt": 10_000.0, "total_usdt": 10_000.0}


class UnauthenticatedBinance(FakeBinance):
    def __init__(self, exchange: Optional[Any] = None) -> None:
        super().__init__(exchange)
        self.authenticated = False


class FakeRedis:
    """Injected replacement for ``_redis_cmd``; records every SET payload."""

    def __init__(self, payload: Optional[str] = None) -> None:
        self.payload = payload
        self.writes: List[str] = []

    def __call__(self, redis_url: str, *args: str) -> Optional[str]:
        if args and args[0] == "GET":
            return self.payload
        if len(args) >= 3 and args[0] == "SET":
            self.payload = args[2]
            self.writes.append(args[2])
            return "OK"
        return None


class PolicyTtlTestBase(unittest.TestCase):
    def setUp(self) -> None:
        # Keep ambient Redis out of the store; the module-level singleton was
        # already built at import and is not used by these tests.
        env_patch = mock.patch.dict("os.environ", {"REDIS_URL": ""})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def new_store(self) -> HybridStateStore:
        return HybridStateStore()

    def carry_only_envelope(
        self,
        issued_at_ms: int = T0,
        ttl_seconds: int = TTL_SECONDS,
        envelope_id: str = "env_test",
    ) -> PolicyEnvelope:
        """A deterministic envelope whose only active pod takes the CEX path."""
        envelope = PolicyEnvelope.default_active(now_ms=issued_at_ms)
        envelope.envelope_id = envelope_id
        envelope.ttl_seconds = ttl_seconds
        for pod_id, pod in envelope.pod_allocations.items():
            pod.enabled = pod_id == "pod_carry"
            pod.capital_weight = 0.5 if pod_id == "pod_carry" else 0.0
        return envelope

    def run_tick(self, store: HybridStateStore, now_ms: int, binance: Any = FakeBinance) -> Any:
        """Run one live tick with the clock, CEX venue, and Solana tool injected."""
        with mock.patch("backend.core.state_store.time.time", new=FakeClock(now_ms)), \
                mock.patch("backend.tools.exchange_tools.BinanceTool", new=binance), \
                mock.patch("backend.tools.solana_tools.SolanaWalletTool", new=mock.MagicMock()):
            return store.run_live_testnet_tick()

    def persisted_payload(self, policy: PolicyEnvelope, kill_switch_active: bool = False) -> Dict[str, Any]:
        return {"policy": policy.to_dict(), "kill_switch_active": kill_switch_active}

    def restore(
        self,
        payload: Optional[Dict[str, Any]] = None,
        now_ms: int = T0,
        fake: Optional[FakeRedis] = None,
    ):
        """Restore a store from an injected Redis read at an injected clock."""
        store = self.new_store()
        store._redis_url = "redis://fake:6379"
        if fake is None:
            fake = FakeRedis(json.dumps(payload))
        with mock.patch("backend.core.state_store._redis_cmd", new=fake), \
                mock.patch("backend.core.state_store.time.time", new=FakeClock(now_ms)):
            store._load_persisted_state()
        return store, fake


class TestLiveTickPreservesIssueTime(PolicyTtlTestBase):
    def test_successful_tick_leaves_issue_time_unchanged(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        store.set_policy(envelope)
        before = envelope.to_dict()

        report = self.run_tick(store, T0 + 10_000)

        self.assertIsNotNone(report)
        self.assertEqual(store._policy.issued_at_ms, T0)
        self.assertEqual(store._policy.ttl_seconds, TTL_SECONDS)
        self.assertEqual(envelope.to_dict(), before)

    def test_unauthenticated_tick_leaves_issue_time_unchanged(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        store.set_policy(envelope)

        report = self.run_tick(store, T0 + 10_000, binance=UnauthenticatedBinance)

        self.assertIsNone(report)
        self.assertEqual(store._policy.issued_at_ms, T0)
        self.assertEqual(store._policy.ttl_seconds, TTL_SECONDS)

    def test_tick_without_active_pod_leaves_issue_time_unchanged(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        for pod in envelope.pod_allocations.values():
            pod.enabled = False
            pod.capital_weight = 0.0
        store.set_policy(envelope)

        report = self.run_tick(store, T0 + 10_000)

        self.assertIsNone(report)
        self.assertEqual(store._policy.issued_at_ms, T0)
        self.assertEqual(store._policy.ttl_seconds, TTL_SECONDS)

    def test_raising_tick_leaves_issue_time_unchanged(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        store.set_policy(envelope)

        def raising_binance() -> FakeBinance:
            return FakeBinance(exchange=RaisingExchange())

        with self.assertRaises(RuntimeError):
            self.run_tick(store, T0 + 10_000, binance=raising_binance)

        self.assertEqual(store._policy.issued_at_ms, T0)
        self.assertEqual(store._policy.ttl_seconds, TTL_SECONDS)

    def test_repeated_ticks_cannot_outlive_the_ttl(self) -> None:
        store = self.new_store()
        store.set_policy(self.carry_only_envelope())

        for tick_index in range(1, TTL_SECONDS // 10 + 1):
            self.run_tick(store, T0 + tick_index * 10_000)
            self.assertEqual(store._policy.issued_at_ms, T0)
            self.assertEqual(store._policy.ttl_seconds, TTL_SECONDS)

        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + TTL_MS).envelope_id,
            "env_test",
        )
        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + TTL_MS + 1).envelope_id,
            "safe_baseline_fallback",
        )

    def test_concurrent_explicit_issuance_survives_the_tick(self) -> None:
        store = self.new_store()
        store.set_policy(self.carry_only_envelope(envelope_id="env_initial"))
        replacement = self.carry_only_envelope(
            issued_at_ms=T0 + 10_000, envelope_id="env_cognitive_cycle"
        )
        issued: List[bool] = []

        def issue_during_fetch() -> None:
            if not issued:
                store.set_policy(replacement)
                issued.append(True)

        def binance_with_callback() -> FakeBinance:
            return FakeBinance(exchange=FakeExchange(on_fetch=issue_during_fetch))

        report = self.run_tick(store, T0 + 10_000, binance=binance_with_callback)

        self.assertIsNotNone(report)
        self.assertTrue(issued)
        effective = store.get_effective_policy(now_ms=T0 + 10_000)
        self.assertEqual(effective.envelope_id, "env_cognitive_cycle")
        self.assertEqual(effective.issued_at_ms, T0 + 10_000)


class TestLivenessSeparateFromAuthority(PolicyTtlTestBase):
    def test_tick_does_not_change_expiry_verdict(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        store.set_policy(envelope)
        fixed_now = T0 + 10_000
        before_expired = envelope.is_expired(fixed_now)
        before_effective = store.get_effective_policy(now_ms=fixed_now).to_dict()

        self.run_tick(store, fixed_now)

        self.assertEqual(envelope.is_expired(fixed_now), before_expired)
        self.assertEqual(
            store.get_effective_policy(now_ms=fixed_now).to_dict(),
            before_effective,
        )

    def test_liveness_after_expiry_does_not_revive_the_envelope(self) -> None:
        store = self.new_store()
        store.set_policy(self.carry_only_envelope(ttl_seconds=60))

        self.run_tick(store, T0 + 61_000)

        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + 61_000).envelope_id,
            "safe_baseline_fallback",
        )

    def test_envelope_wire_shape_is_unchanged(self) -> None:
        self.assertEqual(set(self.carry_only_envelope().to_dict()), POLICY_KEYS)

    def test_persisted_payload_shape_is_unchanged_by_a_tick(self) -> None:
        store = self.new_store()
        store._redis_url = "redis://fake:6379"
        fake = FakeRedis()

        with mock.patch("backend.core.state_store._redis_cmd", new=fake):
            store.set_policy(self.carry_only_envelope())
            before = json.loads(fake.writes[-1])
            self.run_tick(store, T0 + 10_000)
            after = json.loads(fake.writes[-1])

        self.assertEqual(set(after), set(before))
        self.assertEqual(set(after["policy"]), POLICY_KEYS)
        self.assertFalse(
            any("heartbeat" in key or "liveness" in key for key in after)
        )
        self.assertFalse(
            any("heartbeat" in key or "liveness" in key for key in after["policy"])
        )


class TestExpiryBoundary(PolicyTtlTestBase):
    def test_boundary_instant_is_not_expired(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        store.set_policy(envelope)

        self.assertFalse(envelope.is_expired(T0 + TTL_MS))
        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + TTL_MS).envelope_id,
            "env_test",
        )

    def test_one_millisecond_after_boundary_is_expired(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        store.set_policy(envelope)

        self.assertTrue(envelope.is_expired(T0 + TTL_MS + 1))
        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + TTL_MS + 1).envelope_id,
            "safe_baseline_fallback",
        )

    def test_tick_count_does_not_alter_the_boundary(self) -> None:
        store = self.new_store()
        envelope = self.carry_only_envelope()
        store.set_policy(envelope)
        for tick_index in (1, 2, 3):
            self.run_tick(store, T0 + tick_index * 10_000)

        self.assertFalse(envelope.is_expired(T0 + TTL_MS))
        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + TTL_MS).envelope_id,
            "env_test",
        )
        self.assertTrue(envelope.is_expired(T0 + TTL_MS + 1))
        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + TTL_MS + 1).envelope_id,
            "safe_baseline_fallback",
        )


class TestRestorePreservesIssueTime(PolicyTtlTestBase):
    def test_fresh_restore_keeps_original_issue_time(self) -> None:
        envelope = PolicyEnvelope.default_active(now_ms=T0)
        envelope.envelope_id = "env_persisted"
        envelope.ttl_seconds = TTL_SECONDS

        store, _ = self.restore(self.persisted_payload(envelope), now_ms=T0 + 60_000)
        effective = store.get_effective_policy(now_ms=T0 + 60_000)

        self.assertEqual(effective.issued_at_ms, T0)
        self.assertEqual(effective.envelope_id, "env_persisted")
        self.assertEqual(effective.ttl_seconds, TTL_SECONDS)

    def test_persist_and_restore_round_trip_preserves_issue_time(self) -> None:
        envelope = PolicyEnvelope.default_active(now_ms=T0)
        envelope.envelope_id = "env_roundtrip"
        envelope.ttl_seconds = TTL_SECONDS

        writer = self.new_store()
        writer._redis_url = "redis://fake:6379"
        fake = FakeRedis()
        with mock.patch("backend.core.state_store._redis_cmd", new=fake):
            writer.set_policy(envelope)
        self.assertTrue(fake.writes)

        store, _ = self.restore(fake=fake, now_ms=T0 + 60_000)
        effective = store.get_effective_policy(now_ms=T0 + 60_000)

        self.assertEqual(effective.issued_at_ms, T0)
        self.assertEqual(effective.envelope_id, "env_roundtrip")

    def test_restore_without_issue_time_is_not_fresh(self) -> None:
        raw_policy = PolicyEnvelope.default_active(now_ms=T0).to_dict()
        raw_policy.pop("issued_at_ms")

        store, _ = self.restore({"policy": raw_policy}, now_ms=T0 + 60_000)
        effective = store.get_effective_policy(now_ms=T0 + 60_000)

        self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
        self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
        self.assertNotEqual(effective.envelope_id, raw_policy["envelope_id"])
        self.assertEqual(store._policy.envelope_id, "safe_baseline_fallback")

    def test_restore_with_explicit_null_issue_time_yields_safe_baseline(self) -> None:
        raw_policy = PolicyEnvelope.default_active(now_ms=T0).to_dict()
        raw_policy["issued_at_ms"] = None

        store, _ = self.restore({"policy": raw_policy}, now_ms=T0 + 60_000)
        effective = store.get_effective_policy(now_ms=T0 + 60_000)

        self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
        self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
        self.assertEqual(store._policy.envelope_id, "safe_baseline_fallback")

    def test_restore_with_non_numeric_issue_time_yields_safe_baseline(self) -> None:
        raw_policy = PolicyEnvelope.default_active(now_ms=T0).to_dict()
        raw_policy["issued_at_ms"] = "not-a-number"

        store, _ = self.restore({"policy": raw_policy}, now_ms=T0 + 60_000)
        effective = store.get_effective_policy(now_ms=T0 + 60_000)

        self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
        self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
        self.assertEqual(store._policy.envelope_id, "safe_baseline_fallback")

    def test_restore_with_boolean_issue_time_yields_safe_baseline(self) -> None:
        for bool_val in (True, False):
            with self.subTest(bool_val=bool_val):
                raw_policy = PolicyEnvelope.default_active(now_ms=T0).to_dict()
                raw_policy["issued_at_ms"] = bool_val

                store, _ = self.restore({"policy": raw_policy}, now_ms=T0 + 60_000)
                effective = store.get_effective_policy(now_ms=T0 + 60_000)

                self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
                self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
                self.assertEqual(store._policy.envelope_id, "safe_baseline_fallback")

    def test_restore_with_non_positive_issue_time_yields_safe_baseline(self) -> None:
        for bad_val in (0, -1, -T0):
            with self.subTest(bad_val=bad_val):
                raw_policy = PolicyEnvelope.default_active(now_ms=T0).to_dict()
                raw_policy["issued_at_ms"] = bad_val

                store, _ = self.restore({"policy": raw_policy}, now_ms=T0 + 60_000)
                effective = store.get_effective_policy(now_ms=T0 + 60_000)

                self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
                self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
                self.assertEqual(store._policy.envelope_id, "safe_baseline_fallback")

    def test_restore_with_unparseable_policy_dict_yields_safe_baseline(self) -> None:
        for bad_dict in (
            {"envelope_id": "corrupt", "issued_at_ms": T0, "pod_allocations": "invalid_type"},
            {"envelope_id": "corrupt", "issued_at_ms": T0, "ttl_seconds": "not_an_int"},
        ):
            with self.subTest(bad_dict=bad_dict):
                store, _ = self.restore({"policy": bad_dict}, now_ms=T0 + 60_000)
                effective = store.get_effective_policy(now_ms=T0 + 60_000)

                self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
                self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
                self.assertEqual(store._policy.envelope_id, "safe_baseline_fallback")

    def test_restore_with_non_dict_policy_yields_safe_baseline(self) -> None:
        for bad_payload in ("not-a-dict", 12345, [1, 2, 3]):
            with self.subTest(bad_payload=bad_payload):
                store, _ = self.restore({"policy": bad_payload}, now_ms=T0 + 60_000)
                effective = store.get_effective_policy(now_ms=T0 + 60_000)

                self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
                self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
                self.assertEqual(store._policy.envelope_id, "safe_baseline_fallback")


class TestRestorePastTtl(PolicyTtlTestBase):
    def test_stale_restore_yields_safe_baseline(self) -> None:
        envelope = PolicyEnvelope.default_active(now_ms=T0)
        envelope.envelope_id = "env_stale"
        envelope.ttl_seconds = 60

        store, _ = self.restore(self.persisted_payload(envelope), now_ms=T0 + 60_001)
        effective = store.get_effective_policy(now_ms=T0 + 60_001)

        self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
        self.assertEqual(effective.global_regime, "LOW_VOL_CARRY")
        self.assertFalse(effective.pod_allocations["pod_sniper"].enabled)
        self.assertEqual(effective.ttl_seconds, SAFE_BASELINE_TTL_SECONDS)
        self.assertEqual(SAFE_BASELINE_TTL_SECONDS, 900)

    def test_stale_restore_is_not_restamped_as_fresh(self) -> None:
        envelope = PolicyEnvelope.default_active(now_ms=T0)
        envelope.envelope_id = "env_stale"
        envelope.ttl_seconds = 60
        restore_now = T0 + 86_400_000

        store, _ = self.restore(self.persisted_payload(envelope), now_ms=restore_now)
        effective = store.get_effective_policy(now_ms=restore_now)

        self.assertEqual(effective.envelope_id, "safe_baseline_fallback")
        self.assertNotEqual(effective.envelope_id, "env_stale")
        self.assertNotEqual(store._policy.envelope_id, "env_stale")


class TestKillSwitchUnchanged(PolicyTtlTestBase):
    def test_active_kill_switch_overrides_a_fresh_envelope(self) -> None:
        store = self.new_store()
        store.set_policy(self.carry_only_envelope())

        store.set_kill_switch(True, "manual")
        effective = store.get_effective_policy(now_ms=T0 + 1_000)

        self.assertEqual(effective.envelope_id, "kill_switch_lockdown")
        for pod in effective.pod_allocations.values():
            self.assertFalse(pod.enabled)
            self.assertEqual(pod.capital_weight, 0.0)

    def test_active_kill_switch_overrides_an_expired_envelope(self) -> None:
        store = self.new_store()
        store.set_policy(self.carry_only_envelope(ttl_seconds=60))

        store.set_kill_switch(True, "manual")

        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + 61_000).envelope_id,
            "kill_switch_lockdown",
        )

    def test_deactivation_restores_an_unexpired_envelope(self) -> None:
        store = self.new_store()
        store.set_policy(self.carry_only_envelope())
        store.set_kill_switch(True, "manual")

        store.set_kill_switch(False)
        effective = store.get_effective_policy(now_ms=T0 + 30_000)

        self.assertEqual(effective.envelope_id, "env_test")
        self.assertEqual(effective.issued_at_ms, T0)

    def test_deactivation_after_expiry_yields_safe_baseline(self) -> None:
        store = self.new_store()
        store.set_policy(self.carry_only_envelope(ttl_seconds=60))
        store.set_kill_switch(True, "manual")

        store.set_kill_switch(False)

        self.assertEqual(
            store.get_effective_policy(now_ms=T0 + 61_000).envelope_id,
            "safe_baseline_fallback",
        )


if __name__ == "__main__":
    unittest.main()

"""Unit and integration tests for state store security, policy signing, and flatten kill switch.

Covers:
- MinimalRedisClient RESP formatting with EX expiration and socket resilience.
- HybridStateStore HMAC key and key identifier resolution with default fallback.
- Issued policy persistence with signature and active key identifier.
- Authentic state restore vs. tampered content / signature fallback to safe baseline.
- Active policy publishing to robotrader:policy:active with EX TTL.
- Socket failure resilience during active policy publishing.
- Actionable flatten kill switch intent generation (opposite side, reduce_only, symbol order) and deactivation.
"""

from __future__ import annotations

import json
import socket
import unittest
from typing import Any, Dict, List, Optional
from unittest import mock

from backend.core.schemas import (
    AssetOverride,
    PodAllocation,
    PolicyEnvelope,
    SignedPolicyBundle,
    compute_policy_hmac,
    verify_policy_hmac,
)
from backend.core.state_store import (
    DEFAULT_POLICY_HMAC_KEY,
    DEFAULT_POLICY_KEY_ID,
    REDIS_ACTIVE_POLICY_KEY,
    HybridStateStore,
    MinimalRedisClient,
    _resolve_policy_hmac_key,
    _resolve_policy_key_id,
)

T0 = 1_800_000_000_000


def _sample_envelope(ttl_seconds: int = 900) -> PolicyEnvelope:
    return PolicyEnvelope(
        envelope_id="pol_state_store_sec",
        issued_at_ms=T0,
        ttl_seconds=ttl_seconds,
        global_regime="LOW_VOL_CARRY",
        pod_allocations={
            "pod_carry": PodAllocation(
                enabled=True,
                capital_weight=0.5,
                directional_bias="NEUTRAL",
                min_funding_apr=0.1,
                max_slippage_bps=20,
            ),
        },
        asset_overrides={
            "SOL-USDT": AssetOverride(
                catalyst_score=0.8,
                bias="LONG_BIAS",
                max_leverage=2.5,
                support_zone_usd=140.0,
                resistance_zone_usd=155.0,
                invalidation_price_usd=135.0,
                entry_obi_threshold=0.2,
                max_rsi_long=65.0,
                min_rsi_short=35.0,
                take_profit_bps=100.0,
                stop_loss_bps=50.0,
            ),
        },
    )


class FakeClock:
    """Callable replacement for time.time expressed in seconds."""

    def __init__(self, now_ms: int = T0) -> None:
        self.now_ms = now_ms

    def __call__(self) -> float:
        return self.now_ms / 1000.0


class FakeSocket:
    """Mock socket simulating Redis RESP server interaction."""

    def __init__(self, response: bytes = b"+OK\r\n", fail_on_connect: bool = False, fail_on_send: bool = False):
        self.response = response
        self.fail_on_connect = fail_on_connect
        self.fail_on_send = fail_on_send
        self.sent_bytes = bytearray()
        self.closed = False
        self._read_offset = 0

    def connect(self, address: tuple[str, int]) -> None:
        if self.fail_on_connect:
            raise socket.error("Connection refused")

    def settimeout(self, timeout: float) -> None:
        pass

    def sendall(self, data: bytes) -> None:
        if self.fail_on_send:
            raise socket.error("Broken pipe")
        self.sent_bytes.extend(data)

    def recv(self, bufsize: int) -> bytes:
        if self._read_offset >= len(self.response):
            return b""
        chunk = self.response[self._read_offset : self._read_offset + bufsize]
        self._read_offset += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class FakeRedisWithEx:
    """Memory store mimicking MinimalRedisClient and _redis_cmd."""

    def __init__(self, redis_url: str = "redis://fake:6379") -> None:
        self.redis_url = redis_url
        self.store: Dict[str, str] = {}
        self.ex_ttls: Dict[str, int] = {}
        self.set_ex_calls: List[tuple[str, str, int]] = []
        self.fail_set_ex: bool = False

    def __call__(self, redis_url: str, *args: str) -> Optional[str]:
        if args and args[0] == "GET":
            key = args[1] if len(args) >= 2 else "robotrader:v2:state"
            return self.store.get(key)
        if len(args) >= 3 and args[0] == "SET":
            key = args[1]
            val = args[2]
            self.store[key] = val
            return "OK"
        return None

    def set_with_ex(self, key: str, value: str, ttl_seconds: int) -> bool:
        if self.fail_set_ex:
            raise socket.error("Simulated Redis socket failure")
        self.set_ex_calls.append((key, value, ttl_seconds))
        self.store[key] = value
        self.ex_ttls[key] = ttl_seconds
        return True


class TestMinimalRedisClient(unittest.TestCase):
    def test_set_with_ex_formats_resp_command(self) -> None:
        fake_sock = FakeSocket(response=b"+OK\r\n")

        with mock.patch("socket.create_connection", return_value=fake_sock):
            client = MinimalRedisClient("redis://localhost:6379")
            success = client.set_with_ex("robotrader:policy:active", '{"test":1}', 900)

        self.assertTrue(success)
        sent = bytes(fake_sock.sent_bytes)
        expected = (
            b"*5\r\n"
            b"$3\r\nSET\r\n"
            b"$24\r\nrobotrader:policy:active\r\n"
            b"$10\r\n{\"test\":1}\r\n"
            b"$2\r\nEX\r\n"
            b"$3\r\n900\r\n"
        )
        self.assertEqual(sent, expected)

    def test_set_with_ex_catches_socket_error_safely(self) -> None:
        with mock.patch("socket.create_connection", side_effect=socket.error("Connection refused")):
            client = MinimalRedisClient("redis://localhost:6379")
            success = client.set_with_ex("robotrader:policy:active", "data", 300)
            self.assertFalse(success)


class TestHybridStateStoreSecurity(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = mock.patch.dict("os.environ", {"REDIS_URL": ""}, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_default_secret_key_and_key_id_utilized_when_unset(self) -> None:
        with mock.patch.dict("os.environ", {"ROBOTRADER_POLICY_HMAC_KEY": "", "ROBOTRADER_POLICY_KEY_ID": ""}):
            self.assertEqual(_resolve_policy_hmac_key(), DEFAULT_POLICY_HMAC_KEY)
            self.assertEqual(_resolve_policy_key_id(), DEFAULT_POLICY_KEY_ID)

            store = HybridStateStore()
            self.assertEqual(store.policy_hmac_key, DEFAULT_POLICY_HMAC_KEY)
            self.assertEqual(store.active_key_id, DEFAULT_POLICY_KEY_ID)

    def test_explicit_key_identifier_recorded_when_configured(self) -> None:
        with mock.patch.dict("os.environ", {
            "ROBOTRADER_POLICY_HMAC_KEY": "operator-secret-99",
            "ROBOTRADER_POLICY_KEY_ID": "operator-key-2026",
        }):
            self.assertEqual(_resolve_policy_hmac_key(), "operator-secret-99")
            self.assertEqual(_resolve_policy_key_id(), "operator-key-2026")

            store = HybridStateStore()
            self.assertEqual(store.policy_hmac_key, "operator-secret-99")
            self.assertEqual(store.active_key_id, "operator-key-2026")

    def test_issued_policy_persisted_with_valid_signature_and_key_id(self) -> None:
        fake_redis = FakeRedisWithEx("redis://fake:6379")
        store = HybridStateStore()
        store._redis_url = "redis://fake:6379"
        store._redis_client = fake_redis

        env = _sample_envelope(ttl_seconds=900)
        with mock.patch("backend.core.state_store._redis_cmd", new=fake_redis):
            store.set_policy(env)

        # Check persisted snapshot payload in robotrader:v2:state
        raw_state = fake_redis.store.get("robotrader:v2:state")
        self.assertIsNotNone(raw_state)
        state_dict = json.loads(raw_state)

        self.assertIn("policy_signature", state_dict)
        self.assertIn("policy_key_id", state_dict)
        self.assertEqual(state_dict["policy_key_id"], DEFAULT_POLICY_KEY_ID)
        self.assertEqual(len(state_dict["policy_signature"]), 64)

        # Verify signature validity
        self.assertTrue(
            verify_policy_hmac(env, state_dict["policy_signature"], DEFAULT_POLICY_HMAC_KEY)
        )

    def test_restoring_authentic_signed_policy_adopts_envelope(self) -> None:
        env = _sample_envelope(ttl_seconds=1200)
        sig = compute_policy_hmac(env, DEFAULT_POLICY_HMAC_KEY)

        fake_redis = FakeRedisWithEx("redis://fake:6379")
        payload = {
            "policy": env.to_dict(),
            "policy_signature": sig,
            "policy_key_id": DEFAULT_POLICY_KEY_ID,
            "kill_switch_active": False,
        }
        fake_redis.store["robotrader:v2:state"] = json.dumps(payload)

        store = HybridStateStore()
        store._redis_url = "redis://fake:6379"
        store._redis_client = fake_redis

        with mock.patch("backend.core.state_store._redis_cmd", new=fake_redis), \
                mock.patch("backend.core.state_store.time.time", new=FakeClock(T0 + 1000)):
            store._load_persisted_state()

        active = store.get_effective_policy(now_ms=T0 + 1000)
        self.assertEqual(active.envelope_id, env.envelope_id)
        self.assertEqual(active.ttl_seconds, 1200)
        self.assertEqual(active.global_regime, "LOW_VOL_CARRY")

    def test_restoring_tampered_policy_content_falls_back_to_safe_baseline(self) -> None:
        env = _sample_envelope(ttl_seconds=900)
        sig = compute_policy_hmac(env, DEFAULT_POLICY_HMAC_KEY)

        tampered_env_dict = env.to_dict()
        tampered_env_dict["ttl_seconds"] = 99999  # Tampered field!

        fake_redis = FakeRedisWithEx("redis://fake:6379")
        payload = {
            "policy": tampered_env_dict,
            "policy_signature": sig,  # Signature now mismatched
            "policy_key_id": DEFAULT_POLICY_KEY_ID,
            "kill_switch_active": False,
        }
        fake_redis.store["robotrader:v2:state"] = json.dumps(payload)

        store = HybridStateStore()
        store._redis_url = "redis://fake:6379"
        store._redis_client = fake_redis

        with mock.patch("backend.core.state_store._redis_cmd", new=fake_redis), \
                mock.patch("backend.core.state_store.time.time", new=FakeClock(T0 + 1000)):
            store._load_persisted_state()

        # Should fall back closed to safe baseline
        active = store.get_effective_policy(now_ms=T0 + 1000)
        self.assertEqual(active.envelope_id, "safe_baseline_fallback")
        self.assertEqual(active.global_regime, "LOW_VOL_CARRY")

    def test_restoring_tampered_signature_string_falls_back_to_safe_baseline(self) -> None:
        env = _sample_envelope(ttl_seconds=900)
        tampered_sig = "a" * 64  # Bad signature

        fake_redis = FakeRedisWithEx("redis://fake:6379")
        payload = {
            "policy": env.to_dict(),
            "policy_signature": tampered_sig,
            "policy_key_id": DEFAULT_POLICY_KEY_ID,
            "kill_switch_active": False,
        }
        fake_redis.store["robotrader:v2:state"] = json.dumps(payload)

        store = HybridStateStore()
        store._redis_url = "redis://fake:6379"
        store._redis_client = fake_redis

        with mock.patch("backend.core.state_store._redis_cmd", new=fake_redis), \
                mock.patch("backend.core.state_store.time.time", new=FakeClock(T0 + 1000)):
            store._load_persisted_state()

        active = store.get_effective_policy(now_ms=T0 + 1000)
        self.assertEqual(active.envelope_id, "safe_baseline_fallback")

    def test_restoring_missing_signature_falls_back_to_safe_baseline(self) -> None:
        env = _sample_envelope(ttl_seconds=900)

        fake_redis = FakeRedisWithEx("redis://fake:6379")
        payload = {
            "policy": env.to_dict(),
            # No policy_signature provided!
            "kill_switch_active": False,
        }
        fake_redis.store["robotrader:v2:state"] = json.dumps(payload)

        store = HybridStateStore()
        store._redis_url = "redis://fake:6379"
        store._redis_client = fake_redis

        with mock.patch("backend.core.state_store._redis_cmd", new=fake_redis), \
                mock.patch("backend.core.state_store.time.time", new=FakeClock(T0 + 1000)):
            store._load_persisted_state()

        active = store.get_effective_policy(now_ms=T0 + 1000)
        self.assertEqual(active.envelope_id, "safe_baseline_fallback")

    def test_active_policy_bundle_published_with_redis_ex_ttl(self) -> None:
        fake_redis = FakeRedisWithEx("redis://fake:6379")
        store = HybridStateStore()
        store._redis_url = "redis://fake:6379"
        store._redis_client = fake_redis

        env = _sample_envelope(ttl_seconds=600)
        with mock.patch("backend.core.state_store._redis_cmd", new=fake_redis):
            store.set_policy(env)

        # Check that set_with_ex was invoked on robotrader:policy:active with EX=600
        self.assertEqual(len(fake_redis.set_ex_calls), 1)
        key, bundle_json, ttl = fake_redis.set_ex_calls[0]
        self.assertEqual(key, REDIS_ACTIVE_POLICY_KEY)
        self.assertEqual(ttl, 600)

        # Verify payload is a valid SignedPolicyBundle JSON
        bundle = SignedPolicyBundle.from_dict(json.loads(bundle_json))
        self.assertEqual(bundle.policy.envelope_id, env.envelope_id)
        self.assertEqual(bundle.key_id, DEFAULT_POLICY_KEY_ID)
        self.assertTrue(verify_policy_hmac(bundle.policy, bundle.signature, DEFAULT_POLICY_HMAC_KEY))

    def test_socket_failure_during_active_key_publication_fails_safely(self) -> None:
        fake_redis = FakeRedisWithEx("redis://fake:6379")
        fake_redis.fail_set_ex = True  # Will raise socket.error

        store = HybridStateStore()
        store._redis_url = "redis://fake:6379"
        store._redis_client = fake_redis

        env = _sample_envelope(ttl_seconds=450)
        # set_policy must catch the socket error and not crash
        with mock.patch("backend.core.state_store._redis_cmd", new=fake_redis):
            try:
                store.set_policy(env)
            except Exception as exc:
                self.fail(f"set_policy raised an unexpected exception during Redis error: {exc}")

        # In-memory policy is still safely updated
        self.assertEqual(store._policy.envelope_id, env.envelope_id)

    def test_kill_switch_with_active_positions_generates_opposite_reduce_only_orders(self) -> None:
        store = HybridStateStore()
        store.testnet_positions = {
            "SOL-USDT": 15.0,     # Long position -> SELL order
            "BTC-USDT": -0.5,     # Short position -> BUY order
            "ETH-USDT": 0.0,      # Zero exposure -> no order
        }

        res = store.set_kill_switch(True, reason="Critical testnet drawdown")
        self.assertTrue(res["kill_switch_active"])
        self.assertEqual(res["kill_switch_reason"], "Critical testnet drawdown")

        intents = res["kill_switch_flatten_intents"]
        self.assertEqual(len(intents), 2)

        # Deterministically ordered alphabetically by symbol
        self.assertEqual(intents[0]["symbol"], "BTC-USDT")
        self.assertEqual(intents[0]["side"], "BUY")
        self.assertEqual(intents[0]["qty"], 0.5)
        self.assertTrue(intents[0]["reduce_only"])
        self.assertEqual(intents[0]["order_type"], "MARKET")
        self.assertIn("Critical testnet drawdown", intents[0]["rationale"])

        self.assertEqual(intents[1]["symbol"], "SOL-USDT")
        self.assertEqual(intents[1]["side"], "SELL")
        self.assertEqual(intents[1]["qty"], 15.0)
        self.assertTrue(intents[1]["reduce_only"])
        self.assertEqual(intents[1]["order_type"], "MARKET")
        self.assertIn("Critical testnet drawdown", intents[1]["rationale"])

    def test_kill_switch_with_zero_positions_returns_empty_intent_list(self) -> None:
        store = HybridStateStore()
        store.testnet_positions = {
            "SOL-USDT": 0.0,
            "BTC-USDT": 0.0,
        }

        res = store.set_kill_switch(True, reason="Precautionary stop")
        self.assertTrue(res["kill_switch_active"])
        self.assertEqual(res["kill_switch_flatten_intents"], [])

    def test_deactivating_kill_switch_returns_empty_flatten_intents_list(self) -> None:
        store = HybridStateStore()
        store.testnet_positions = {"SOL-USDT": 10.0}

        # First trigger
        store.set_kill_switch(True, "Emergency")
        self.assertTrue(store.kill_switch_active)

        # Deactivate
        res = store.set_kill_switch(False)
        self.assertFalse(res["kill_switch_active"])
        self.assertIsNone(res["kill_switch_reason"])
        self.assertEqual(res["kill_switch_flatten_intents"], [])


if __name__ == "__main__":
    unittest.main()

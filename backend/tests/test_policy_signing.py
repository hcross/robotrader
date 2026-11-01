"""Cross-language and unit tests for detached canonical HMAC-SHA256 policy envelope signing.

Verifies:
1. Cross-language HMAC digest parity between Python and the Rust engine binary.
2. Authentic signature verification success.
3. Verification failure upon field mutation (issued_at_ms, global_regime, ttl_seconds, pod_allocations, asset_overrides).
4. Verification failure upon incorrect secret key.
5. Verification failure upon malformed/non-hex signature strings.
6. SignedPolicyBundle serialization and deserialization roundtrip.
"""

import json
import subprocess
import unittest
from pathlib import Path

from backend.core.schemas import (
    AssetOverride,
    PodAllocation,
    PolicyEnvelope,
    SignedPolicyBundle,
    canonical_policy_json,
    compute_policy_hmac,
    verify_policy_hmac,
)
from backend.core.state_store import resolve_robotrader_binary

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / "engine-rs"


def _sample_envelope() -> PolicyEnvelope:
    return PolicyEnvelope(
        envelope_id="pol_test_signing_1",
        issued_at_ms=1_792_180_000_000,
        ttl_seconds=900,
        global_regime="LOW_VOL_CARRY",
        pod_allocations={
            "pod_carry": PodAllocation(
                enabled=True,
                capital_weight=0.6,
                directional_bias="NEUTRAL",
                min_funding_apr=0.12,
                max_slippage_bps=20,
            ),
            "pod_momentum": PodAllocation(
                enabled=False,
                capital_weight=0.0,
                directional_bias="LONG_BIAS",
                min_funding_apr=0.0,
                max_slippage_bps=30,
            ),
        },
        asset_overrides={
            "SOL-USDT": AssetOverride(
                catalyst_score=0.75,
                bias="LONG_BIAS",
                max_leverage=3.0,
                support_zone_usd=150.0,
                resistance_zone_usd=165.0,
                invalidation_price_usd=140.0,
                entry_obi_threshold=0.25,
                max_rsi_long=65.0,
                min_rsi_short=35.0,
                take_profit_bps=120.0,
                stop_loss_bps=50.0,
            )
        },
    )


def _run_rust_hmac(payload: str, key: str) -> subprocess.CompletedProcess:
    cmd = [
        str(resolve_robotrader_binary(ENGINE_DIR)),
        "--compute-policy-hmac",
        key,
    ]
    return subprocess.run(
        cmd,
        cwd=str(ENGINE_DIR),
        input=payload,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _run_rust_verify(payload: str, key: str, signature: str) -> subprocess.CompletedProcess:
    cmd = [
        str(resolve_robotrader_binary(ENGINE_DIR)),
        "--verify-policy-hmac",
        key,
        signature,
    ]
    return subprocess.run(
        cmd,
        cwd=str(ENGINE_DIR),
        input=payload,
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestPolicySigning(unittest.TestCase):
    def setUp(self) -> None:
        self.secret_key = "robotrader-test-secret-key-2026"
        self.envelope = _sample_envelope()

    def test_canonical_json_preserves_strict_six_key_wire_shape(self) -> None:
        canonical = canonical_policy_json(self.envelope)
        data = json.loads(canonical)
        expected_keys = {
            "envelope_id",
            "issued_at_ms",
            "ttl_seconds",
            "global_regime",
            "pod_allocations",
            "asset_overrides",
        }
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertNotIn(" ", canonical)  # Compact, no insignificant whitespace

    def test_cross_language_hmac_parity_with_rust_binary(self) -> None:
        python_hmac = compute_policy_hmac(self.envelope, self.secret_key)
        self.assertEqual(len(python_hmac), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in python_hmac))

        proc = _run_rust_hmac(json.dumps(self.envelope.to_dict()), self.secret_key)
        self.assertEqual(proc.returncode, 0, f"Rust binary error: {proc.stderr}")
        rust_hmac = proc.stdout.strip()

        self.assertEqual(python_hmac, rust_hmac, "Python and Rust HMAC digests diverged!")

        # Also test Rust verify CLI with Python-computed signature
        verify_proc = _run_rust_verify(
            json.dumps(self.envelope.to_dict()), self.secret_key, python_hmac
        )
        self.assertEqual(verify_proc.returncode, 0, f"Rust verify error: {verify_proc.stderr}")
        self.assertEqual(verify_proc.stdout.strip(), "VALID")

    def test_verification_succeeds_with_authentic_envelope_and_matching_key(self) -> None:
        sig = compute_policy_hmac(self.envelope, self.secret_key)
        self.assertTrue(verify_policy_hmac(self.envelope, sig, self.secret_key))
        # Also bytes secret key
        self.assertTrue(verify_policy_hmac(self.envelope, sig, self.secret_key.encode("utf-8")))

    def test_verification_fails_when_envelope_field_is_modified(self) -> None:
        sig = compute_policy_hmac(self.envelope, self.secret_key)

        # 1. Modify issued_at_ms
        env_mod_time = _sample_envelope()
        env_mod_time.issued_at_ms += 1000
        self.assertFalse(verify_policy_hmac(env_mod_time, sig, self.secret_key))

        # 2. Modify global_regime
        env_mod_regime = _sample_envelope()
        env_mod_regime.global_regime = "HIGH_VOL_MOMENTUM"
        self.assertFalse(verify_policy_hmac(env_mod_regime, sig, self.secret_key))

        # 3. Modify ttl_seconds
        env_mod_ttl = _sample_envelope()
        env_mod_ttl.ttl_seconds = 1800
        self.assertFalse(verify_policy_hmac(env_mod_ttl, sig, self.secret_key))

        # 4. Modify pod allocations
        env_mod_pod = _sample_envelope()
        env_mod_pod.pod_allocations["pod_carry"].capital_weight = 0.9
        self.assertFalse(verify_policy_hmac(env_mod_pod, sig, self.secret_key))

        # 5. Modify asset overrides
        env_mod_asset = _sample_envelope()
        env_mod_asset.asset_overrides["SOL-USDT"].max_leverage = 5.0
        self.assertFalse(verify_policy_hmac(env_mod_asset, sig, self.secret_key))

    def test_verification_fails_when_incorrect_secret_key_is_provided(self) -> None:
        sig = compute_policy_hmac(self.envelope, self.secret_key)
        wrong_key = "wrong-secret-key-attack"
        self.assertFalse(verify_policy_hmac(self.envelope, sig, wrong_key))

    def test_verification_fails_when_signature_is_malformed(self) -> None:
        # Empty string
        self.assertFalse(verify_policy_hmac(self.envelope, "", self.secret_key))
        # Truncated
        valid_sig = compute_policy_hmac(self.envelope, self.secret_key)
        self.assertFalse(verify_policy_hmac(self.envelope, valid_sig[:63], self.secret_key))
        # Extra length
        self.assertFalse(verify_policy_hmac(self.envelope, valid_sig + "0", self.secret_key))
        # Non-hex characters
        malformed = "z" * 64
        self.assertFalse(verify_policy_hmac(self.envelope, malformed, self.secret_key))

    def test_signed_policy_bundle_roundtrip(self) -> None:
        sig = compute_policy_hmac(self.envelope, self.secret_key)
        bundle = SignedPolicyBundle(
            policy=self.envelope,
            signature=sig,
            key_id="operator-key-01",
        )
        data = bundle.to_dict()
        self.assertEqual(data["signature"], sig)
        self.assertEqual(data["key_id"], "operator-key-01")
        self.assertEqual(set(data["policy"].keys()), {
            "envelope_id",
            "issued_at_ms",
            "ttl_seconds",
            "global_regime",
            "pod_allocations",
            "asset_overrides",
        })

        restored = SignedPolicyBundle.from_dict(data)
        self.assertEqual(restored.signature, sig)
        self.assertEqual(restored.key_id, "operator-key-01")
        self.assertEqual(restored.policy.envelope_id, self.envelope.envelope_id)
        self.assertEqual(restored.policy.issued_at_ms, self.envelope.issued_at_ms)
        self.assertEqual(restored.policy.ttl_seconds, self.envelope.ttl_seconds)
        self.assertEqual(restored.policy.global_regime, self.envelope.global_regime)
        self.assertTrue(verify_policy_hmac(restored.policy, restored.signature, self.secret_key))


if __name__ == "__main__":
    unittest.main()

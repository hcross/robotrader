"""Cross-language PolicyEnvelope round-trip contract.

Builds an envelope with the live Python serializer, decodes and re-encodes it
with the Rust implementation through `robotrader-node --contract-roundtrip`, and
asserts that the key sets and values are identical. Offline: no Redis, network,
or exchange access.
"""

import json
import subprocess
import unittest
from pathlib import Path

from backend.core.schemas import AssetOverride, PodAllocation, PolicyEnvelope

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / "engine-rs"
DEBUG_BINARY = ENGINE_DIR / "target" / "debug" / "robotrader-node"

ELEVEN_OVERRIDE_KEYS = {
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


def _roundtrip_command() -> list:
    if DEBUG_BINARY.exists():
        return [str(DEBUG_BINARY), "--contract-roundtrip"]
    return [
        "cargo",
        "run",
        "--quiet",
        "--bin",
        "robotrader-node",
        "--",
        "--contract-roundtrip",
    ]


def _run_rust_roundtrip(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        _roundtrip_command(),
        cwd=str(ENGINE_DIR),
        input=payload,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _distinct_envelope() -> PolicyEnvelope:
    override = AssetOverride(
        catalyst_score=0.731,
        bias="SHORT_BIAS",
        max_leverage=2.75,
        support_zone_usd=150.25,
        resistance_zone_usd=160.75,
        invalidation_price_usd=145.5,
        entry_obi_threshold=0.31,
        max_rsi_long=61.5,
        min_rsi_short=38.5,
        take_profit_bps=115.0,
        stop_loss_bps=55.0,
    )
    return PolicyEnvelope(
        envelope_id="rt_contract",
        issued_at_ms=1_792_180_000_000,
        ttl_seconds=900,
        global_regime="LOW_VOL_CARRY",
        pod_allocations={
            "pod_carry": PodAllocation(
                enabled=True,
                capital_weight=0.5,
                directional_bias="NEUTRAL",
                min_funding_apr=0.15,
                max_slippage_bps=25,
            )
        },
        asset_overrides={"SOL-USDT": override},
    )


class TestContractRoundtrip(unittest.TestCase):
    def test_asset_override_to_dict_emits_exactly_the_eleven_keys(self) -> None:
        serialized = AssetOverride(
            catalyst_score=0.731,
            bias="SHORT_BIAS",
            max_leverage=2.75,
            support_zone_usd=150.25,
            resistance_zone_usd=160.75,
            invalidation_price_usd=145.5,
            entry_obi_threshold=0.31,
            max_rsi_long=61.5,
            min_rsi_short=38.5,
            take_profit_bps=115.0,
            stop_loss_bps=55.0,
        ).to_dict()

        self.assertEqual(set(serialized), ELEVEN_OVERRIDE_KEYS)
        self.assertEqual(serialized["min_rsi_short"], 38.5)

    def test_field_sets_and_values_match_across_languages(self) -> None:
        python_envelope = _distinct_envelope().to_dict()

        proc = _run_rust_roundtrip(json.dumps(python_envelope))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rust_envelope = json.loads(proc.stdout)

        self.assertEqual(set(rust_envelope), set(python_envelope))
        self.assertEqual(
            set(rust_envelope["pod_allocations"]),
            set(python_envelope["pod_allocations"]),
        )
        self.assertEqual(
            set(rust_envelope["asset_overrides"]),
            set(python_envelope["asset_overrides"]),
        )

        rust_override = rust_envelope["asset_overrides"]["SOL-USDT"]
        python_override = python_envelope["asset_overrides"]["SOL-USDT"]
        self.assertEqual(set(rust_override), ELEVEN_OVERRIDE_KEYS)
        self.assertEqual(len(rust_override), 11)
        for key, value in python_override.items():
            self.assertEqual(
                rust_override[key],
                value,
                f"{key} diverged across languages",
            )

    def test_envelope_omitting_an_optional_rule_still_decodes_in_rust(self) -> None:
        python_envelope = _distinct_envelope().to_dict()
        del python_envelope["asset_overrides"]["SOL-USDT"]["entry_obi_threshold"]

        proc = _run_rust_roundtrip(json.dumps(python_envelope))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rust_override = json.loads(proc.stdout)["asset_overrides"]["SOL-USDT"]

        self.assertEqual(set(rust_override), ELEVEN_OVERRIDE_KEYS)
        self.assertIsNone(rust_override["entry_obi_threshold"])

    def test_missing_required_field_is_rejected(self) -> None:
        python_envelope = _distinct_envelope().to_dict()
        del python_envelope["asset_overrides"]["SOL-USDT"]["catalyst_score"]

        proc = _run_rust_roundtrip(json.dumps(python_envelope))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("catalyst_score", proc.stderr)

    def test_unknown_override_key_is_rejected(self) -> None:
        python_envelope = _distinct_envelope().to_dict()
        python_envelope["asset_overrides"]["SOL-USDT"]["trailing_stop_bps"] = 80.0

        proc = _run_rust_roundtrip(json.dumps(python_envelope))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("trailing_stop_bps", proc.stderr)


if __name__ == "__main__":
    unittest.main()

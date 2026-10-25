"""`robotrader-node --policy-json` must fail loud and use the supplied envelope.

The valid case pins `issued_at_ms` to the Rust benchmark `base_ts` in
`engine-rs/crates/backtest/src/lib.rs`; a fixture change there must update it
here too, otherwise the events land before the envelope is issued.
"""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / "engine-rs"
DEBUG_BINARY = ENGINE_DIR / "target" / "debug" / "robotrader-node"

# Must match `base_ts` in engine-rs/crates/backtest/src/lib.rs.
BASE_TS_MS = 1_792_180_000_000


def _policy_command(policy: dict) -> list:
    binary = DEBUG_BINARY if DEBUG_BINARY.exists() else None
    if binary is not None:
        return [str(binary), "--policy-json", json.dumps(policy)]
    return [
        "cargo",
        "run",
        "--quiet",
        "--bin",
        "robotrader-node",
        "--",
        "--policy-json",
        json.dumps(policy),
    ]


def _run_policy(policy: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        _policy_command(policy),
        cwd=str(ENGINE_DIR),
        capture_output=True,
        text=True,
        timeout=300,
    )


class TestPolicyIngestion(unittest.TestCase):
    def test_unknown_key_exits_two_with_the_key_on_stderr(self) -> None:
        policy = {
            "envelope_id": "ingest_unknown",
            "issued_at_ms": BASE_TS_MS,
            "ttl_seconds": 86_400,
            "global_regime": "LOW_VOL_CARRY",
            "pod_allocations": {},
            "asset_overrides": {},
            "unexpected_top_level_key": 1,
        }

        proc = _run_policy(policy)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("unexpected_top_level_key", proc.stderr)

    def test_valid_supplied_envelope_replaces_the_benchmark_default(self) -> None:
        # Empty allocations prove the supplied envelope was used: the default
        # benchmark enables pod_carry/pod_momentum and would produce trades,
        # while every intent here is rejected by HardRiskGate.
        policy = {
            "envelope_id": "ingest_valid",
            "issued_at_ms": BASE_TS_MS,
            "ttl_seconds": 86_400,
            "global_regime": "LOW_VOL_CARRY",
            "pod_allocations": {},
            "asset_overrides": {},
        }

        proc = _run_policy(policy)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["total_trades"], 0)
        self.assertGreater(summary["rejected_orders"], 0)


if __name__ == "__main__":
    unittest.main()

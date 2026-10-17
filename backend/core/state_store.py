from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import CatalystSignal, PolicyEnvelope


class HybridStateStore:
    """
    Manages the shared IPC state between the Python Warm-Path AI Meta-Controller
    and the Rust Hot-Path / Backtest Engine (`engine-rs`).
    """

    def __init__(self) -> None:
        self._policy: PolicyEnvelope = PolicyEnvelope.default_active()
        self.kill_switch_active: bool = False
        self.kill_switch_reason: Optional[str] = None
        self.recent_catalysts: List[CatalystSignal] = [
            CatalystSignal(
                asset="SOL-USDT",
                catalyst_type="WHALE_ACCUMULATION",
                conviction=0.85,
                directional_bias="LONG_BIAS",
                half_life_minutes=240,
                summary="Smart-money inflow +$4.8M on Solana perps & spot; funding APR 32%",
            ),
            CatalystSignal(
                asset="JUP-USDT",
                catalyst_type="GOVERNANCE_CATALYST",
                conviction=0.78,
                directional_bias="LONG_BIAS",
                half_life_minutes=180,
                summary="ASR staking fee distribution vote passed; strong L2 bid absorption",
            ),
        ]
        self.last_backtest_result: Optional[Dict[str, Any]] = None

    def set_policy(self, policy: PolicyEnvelope) -> None:
        self._policy = policy

    def get_effective_policy(self, now_ms: Optional[int] = None) -> PolicyEnvelope:
        if self.kill_switch_active:
            safe = PolicyEnvelope.safe_baseline(now_ms)
            safe.envelope_id = "kill_switch_lockdown"
            for pod in safe.pod_allocations.values():
                pod.enabled = False
                pod.capital_weight = 0.0
            return safe

        if self._policy.is_expired(now_ms):
            return PolicyEnvelope.safe_baseline(now_ms)
        return self._policy

    def set_kill_switch(self, active: bool, reason: Optional[str] = None) -> Dict[str, Any]:
        self.kill_switch_active = active
        self.kill_switch_reason = reason if active else None
        return {
            "kill_switch_active": self.kill_switch_active,
            "kill_switch_reason": self.kill_switch_reason,
            "effective_policy": self.get_effective_policy().to_dict(),
        }

    def run_rust_backtest(self, policy: Optional[PolicyEnvelope] = None) -> Dict[str, Any]:
        """
        Invokes the compiled Rust `robotrader-node` binary with the active PolicyEnvelope
        to run a deterministic multi-pod backtest & anti-rug verification.
        """
        effective_policy = policy or self.get_effective_policy()
        repo_root = Path(__file__).resolve().parents[2]
        engine_dir = repo_root / "engine-rs"
        binary_path = engine_dir / "target" / "debug" / "robotrader-node"

        policy_json = json.dumps(effective_policy.to_dict())

        if binary_path.exists():
            cmd = [str(binary_path), "--policy-json", policy_json]
        else:
            cmd = [
                "cargo",
                "run",
                "--quiet",
                "--bin",
                "robotrader-node",
                "--",
                "--policy-json",
                policy_json,
            ]

        proc = subprocess.run(
            cmd,
            cwd=str(engine_dir),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        result: Dict[str, Any] = json.loads(proc.stdout)
        self.last_backtest_result = result
        return result


state_store = HybridStateStore()

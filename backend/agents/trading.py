from __future__ import annotations

import time
from typing import Any, Dict, Optional

from ..core.agent import BaseWarmAgent
from ..core.schemas import AssetOverride, Message, PodAllocation, PolicyEnvelope
from ..core.state_store import HybridStateStore, state_store


class MetaAllocatorAgent(BaseWarmAgent):
    """
    Warm-Path Chief Investment Officer (CIO) / Regime & Meta-Allocator.
    Never places raw market orders; publishes a TTL-bounded `PolicyEnvelope`
    consumed by the Rust Hot-Path (`engine-rs`).
    """

    def __init__(self, name: str = "MetaAllocator", store: Optional[HybridStateStore] = None):
        super().__init__(name, role="Regime Classification & Dynamic Pod Capital Allocator")
        self.store = store or state_store

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "SET_REGIME":
            preset = str(message.content.get("preset", "RISK_ON_HIGH_VOL"))
            return self.apply_regime_preset(preset).to_dict()
        if message.msg_type == "UPDATE_POD_WEIGHTS":
            return self.update_pod_allocations(message.content).to_dict()
        return None

    def apply_regime_preset(self, preset: str, commit: bool = True) -> PolicyEnvelope:
        """Build the preset envelope; commit it to the store unless told otherwise.

        ``commit=False`` lets a caller validate the envelope (for example with a
        backtest) before making it the effective policy. ``SET_REGIME`` keeps the
        default eager commit.
        """
        now_ms = int(time.time() * 1000)
        preset_upper = preset.upper()

        if preset_upper in ("DEFENSIVE", "LOW_VOL_CARRY", "CARRY_ONLY"):
            env = PolicyEnvelope.safe_baseline(now_ms)
            env.envelope_id = f"env_defensive_{now_ms}"
            env.pod_allocations["pod_carry"].capital_weight = 0.70
            env.pod_allocations["pod_momentum"].capital_weight = 0.15
            if commit:
                self.store.set_policy(env)
            return env

        if preset_upper in ("FULL_SWARM", "AGGRESSIVE_SNIPER"):
            env = PolicyEnvelope.default_active(now_ms)
            env.envelope_id = f"env_full_swarm_{now_ms}"
            env.global_regime = "TRENDING_BULL"
            env.pod_allocations["pod_carry"].capital_weight = 0.35
            env.pod_allocations["pod_momentum"].capital_weight = 0.30
            env.pod_allocations["pod_onchain_alpha"].capital_weight = 0.20
            env.pod_allocations["pod_sniper"] = PodAllocation(
                enabled=True,
                capital_weight=0.10,
                directional_bias="LONG_BIAS",
                min_funding_apr=None,
                max_slippage_bps=120,
            )
            if commit:
                self.store.set_policy(env)
            return env

        # Default: RISK_ON_HIGH_VOL (Pods 1, 2, 3 active; Pod 4 Sniper disabled)
        env = PolicyEnvelope.default_active(now_ms)
        env.envelope_id = f"env_risk_on_{now_ms}"
        if commit:
            self.store.set_policy(env)
        return env

    def update_pod_allocations(self, updates: Dict[str, Dict[str, Any]]) -> PolicyEnvelope:
        current = self.store.get_effective_policy()
        now_ms = int(time.time() * 1000)
        current.envelope_id = f"env_custom_{now_ms}"
        current.issued_at_ms = now_ms

        for pod_key, cfg in updates.items():
            if pod_key in current.pod_allocations:
                alloc = current.pod_allocations[pod_key]
                if "enabled" in cfg:
                    alloc.enabled = bool(cfg["enabled"])
                if "capital_weight" in cfg:
                    alloc.capital_weight = max(0.0, min(1.0, float(cfg["capital_weight"])))
                if "directional_bias" in cfg:
                    alloc.directional_bias = str(cfg["directional_bias"])

        self.store.set_policy(current)
        return current


PortfolioManagerAgent = MetaAllocatorAgent

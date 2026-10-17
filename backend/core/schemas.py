from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PodAllocation:
    enabled: bool
    capital_weight: float
    directional_bias: Optional[str] = "NEUTRAL"
    min_funding_apr: Optional[float] = None
    max_slippage_bps: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AssetOverride:
    catalyst_score: float
    bias: str = "NEUTRAL"
    max_leverage: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyEnvelope:
    envelope_id: str
    issued_at_ms: int
    ttl_seconds: int
    global_regime: str
    pod_allocations: Dict[str, PodAllocation]
    asset_overrides: Dict[str, AssetOverride] = field(default_factory=dict)

    def is_expired(self, now_ms: Optional[int] = None) -> bool:
        current = now_ms if now_ms is not None else int(time.time() * 1000)
        return current > (self.issued_at_ms + self.ttl_seconds * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "issued_at_ms": self.issued_at_ms,
            "ttl_seconds": self.ttl_seconds,
            "global_regime": self.global_regime,
            "pod_allocations": {k: v.to_dict() for k, v in self.pod_allocations.items()},
            "asset_overrides": {k: v.to_dict() for k, v in self.asset_overrides.items()},
        }

    @classmethod
    def safe_baseline(cls, now_ms: Optional[int] = None) -> PolicyEnvelope:
        ts = now_ms if now_ms is not None else int(time.time() * 1000)
        return cls(
            envelope_id="safe_baseline_fallback",
            issued_at_ms=ts,
            ttl_seconds=900,
            global_regime="LOW_VOL_CARRY",
            pod_allocations={
                "pod_carry": PodAllocation(
                    enabled=True,
                    capital_weight=0.50,
                    directional_bias="NEUTRAL",
                    min_funding_apr=0.15,
                    max_slippage_bps=25,
                ),
                "pod_momentum": PodAllocation(
                    enabled=True,
                    capital_weight=0.25,
                    directional_bias="NEUTRAL",
                    min_funding_apr=None,
                    max_slippage_bps=30,
                ),
                "pod_solana_alpha": PodAllocation(
                    enabled=False,
                    capital_weight=0.0,
                    directional_bias="NEUTRAL",
                    min_funding_apr=None,
                    max_slippage_bps=80,
                ),
                "pod_sniper": PodAllocation(
                    enabled=False,
                    capital_weight=0.0,
                    directional_bias="NEUTRAL",
                    min_funding_apr=None,
                    max_slippage_bps=150,
                ),
            },
            asset_overrides={},
        )

    @classmethod
    def default_active(cls, now_ms: Optional[int] = None) -> PolicyEnvelope:
        ts = now_ms if now_ms is not None else int(time.time() * 1000)
        return cls(
            envelope_id=f"env_{ts}",
            issued_at_ms=ts,
            ttl_seconds=900,
            global_regime="RISK_ON_HIGH_VOL",
            pod_allocations={
                "pod_carry": PodAllocation(
                    enabled=True,
                    capital_weight=0.40,
                    directional_bias="NEUTRAL",
                    min_funding_apr=0.15,
                    max_slippage_bps=25,
                ),
                "pod_momentum": PodAllocation(
                    enabled=True,
                    capital_weight=0.35,
                    directional_bias="LONG_BIAS",
                    min_funding_apr=None,
                    max_slippage_bps=30,
                ),
                "pod_solana_alpha": PodAllocation(
                    enabled=True,
                    capital_weight=0.15,
                    directional_bias="LONG_BIAS",
                    min_funding_apr=None,
                    max_slippage_bps=80,
                ),
                "pod_sniper": PodAllocation(
                    enabled=False,
                    capital_weight=0.00,
                    directional_bias="NEUTRAL",
                    min_funding_apr=None,
                    max_slippage_bps=150,
                ),
            },
            asset_overrides={
                "SOL-USDT": AssetOverride(
                    catalyst_score=0.85,
                    bias="LONG_BIAS",
                    max_leverage=2.5,
                ),
                "JUP-USDT": AssetOverride(
                    catalyst_score=0.78,
                    bias="LONG_BIAS",
                    max_leverage=2.0,
                ),
            },
        )


@dataclass
class CatalystSignal:
    asset: str
    catalyst_type: str
    conviction: float
    directional_bias: str
    half_life_minutes: int
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    sender: str
    recipient: str
    msg_type: str
    content: Any
    timestamp: float = field(default_factory=time.time)

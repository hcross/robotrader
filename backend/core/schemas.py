from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# The safe-baseline TTL is declared once in `contracts/policy_contract.conf` and
# resolved here at import, mirroring the Rust `include_str!` const scan.
_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "policy_contract.conf"
_CONTRACT_KEY = "SAFE_BASELINE_TTL_SECONDS"


def _read_contract_ttl(path: Path = _CONTRACT_PATH) -> int:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if separator and key.strip() == _CONTRACT_KEY:
            return int(value.strip())
    raise RuntimeError(f"{_CONTRACT_KEY} not declared in {path}")


SAFE_BASELINE_TTL_SECONDS = _read_contract_ttl()


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
    support_zone_usd: Optional[float] = None
    resistance_zone_usd: Optional[float] = None
    invalidation_price_usd: Optional[float] = None
    entry_obi_threshold: float = 0.08
    max_rsi_long: float = 70.0
    min_rsi_short: float = 30.0
    take_profit_bps: float = 45.0
    stop_loss_bps: float = 30.0

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
    def from_dict(cls, data: Dict[str, Any]) -> PolicyEnvelope:
        now_ms = int(time.time() * 1000)
        raw_allocs = data.get("pod_allocations", {})
        pod_allocs: Dict[str, PodAllocation] = {}
        for k, v in raw_allocs.items():
            canonical_key = "pod_onchain_alpha" if k == "pod_solana_alpha" else k
            pod_allocs[canonical_key] = PodAllocation(**v) if isinstance(v, dict) else v
        overrides = {
            k: AssetOverride(**v) if isinstance(v, dict) else v
            for k, v in data.get("asset_overrides", {}).items()
        }
        return cls(
            envelope_id=str(data.get("envelope_id", f"env_{now_ms}")),
            issued_at_ms=int(data.get("issued_at_ms", now_ms)),
            ttl_seconds=int(data.get("ttl_seconds", 900)),
            global_regime=str(data.get("global_regime", "RISK_ON_HIGH_VOL")),
            pod_allocations=pod_allocs,
            asset_overrides=overrides,
        )

    @classmethod
    def safe_baseline(cls, now_ms: Optional[int] = None) -> PolicyEnvelope:
        ts = now_ms if now_ms is not None else int(time.time() * 1000)
        return cls(
            envelope_id="safe_baseline_fallback",
            issued_at_ms=ts,
            ttl_seconds=SAFE_BASELINE_TTL_SECONDS,
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
                "pod_onchain_alpha": PodAllocation(
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
                "pod_onchain_alpha": PodAllocation(
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


@dataclass
class SignedTransferReceipt:
    leaf_id: str
    chain: str
    curve: str
    vault_mode: str
    simulated: bool
    signature_is_chain_valid: bool
    signature_is_cryptographic: bool
    signature_scheme: str
    whitelist_enforcement: str
    signer_address: str
    destination_address: str
    amount_usd: float
    token: str
    destination_whitelisted: bool
    signature_hex: str
    key_zeroized_after_sign: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioState:
    initial_equity_usd: float
    current_equity_usd: float
    high_water_mark_usd: float
    daily_start_equity_usd: float
    asset_exposures_usd: Dict[str, float] = field(default_factory=dict)
    pod_exposures_usd: Dict[str, float] = field(default_factory=dict)
    gross_exposure_usd: float = 0.0
    last_order_ts_ms: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PortfolioState:
        return cls(
            initial_equity_usd=float(data["initial_equity_usd"]),
            current_equity_usd=float(data["current_equity_usd"]),
            high_water_mark_usd=float(data["high_water_mark_usd"]),
            daily_start_equity_usd=float(data["daily_start_equity_usd"]),
            asset_exposures_usd=dict(data.get("asset_exposures_usd", {})),
            pod_exposures_usd=dict(data.get("pod_exposures_usd", {})),
            gross_exposure_usd=float(data.get("gross_exposure_usd", 0.0)),
            last_order_ts_ms=dict(data.get("last_order_ts_ms", {})),
        )


@dataclass
class PublicWalletDescriptor:
    leaf_id: str
    chain: str
    symbol: str
    curve: str
    simulated: bool
    address_is_spendable: bool
    target_slip44_coin_type: int
    target_master_derivation_path: str
    target_leaf_derivation_path: str
    master_treasury_address: str
    leaf_hot_address: str
    key_fingerprint: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimulatedVaultManifest:
    vault_version: str
    vault_mode: str
    execution_mode: str
    simulated: bool
    simulation_notice: str
    seed_source: str
    master_seed_fingerprint: str
    python_private_key_access: bool
    whitelist_enforcement: str
    simulated_whitelist_entry_count: int
    canonical_bridge_contracts_count: int
    wallets: List[PublicWalletDescriptor]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

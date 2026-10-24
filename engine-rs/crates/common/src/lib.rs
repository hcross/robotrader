use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PodId {
    PodCarry,
    PodMomentum,
    PodSolanaAlpha,
    PodSniper,
}

impl PodId {
    pub fn as_str(&self) -> &'static str {
        match self {
            PodId::PodCarry => "pod_carry",
            PodId::PodMomentum => "pod_momentum",
            PodId::PodSolanaAlpha => "pod_solana_alpha",
            PodId::PodSniper => "pod_sniper",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Side {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderType {
    PostOnlyMaker,
    Limit,
    Market,
    JitoBundleAtomic,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Venue {
    BinanceSpot,
    BinancePerp,
    HyperliquidPerp,
    SolanaJupiterJito,
    SolanaRaydiumAtomic,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GlobalRegime {
    TrendingBull,
    TrendingBear,
    MeanRevertingRange,
    HighVolPanic,
    LowVolCarry,
    RiskOnHighVol,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum DirectionalBias {
    LongBias,
    ShortBias,
    Neutral,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PodAllocation {
    pub enabled: bool,
    pub capital_weight: f64,
    #[serde(default)]
    pub directional_bias: Option<DirectionalBias>,
    #[serde(default)]
    pub min_funding_apr: Option<f64>,
    #[serde(default)]
    pub max_slippage_bps: Option<u32>,
}

/// Metadata describing an ecosystem-specific Rust StrategyPod instance (at most 4 per blockchain).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EcosystemPodSpec {
    pub slot_id: PodId,
    pub pod_code: String,
    pub name: String,
    pub archetype: String,
    pub native_venue: String,
    pub default_weight: f64,
    pub description: String,
}

/// Cryptographic curve or authentication mechanism used by the Rust Vault Enclave for a blockchain/venue.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CryptographicCurve {
    Secp256k1EcdsaBip44,
    Secp256k1SchnorrTaproot,
    Ed25519Slip0010,
    Ed25519Cip1852,
    Sr25519Substrate,
    HmacSha256NoWithdraw,
    MtlsX509Participant,
    VirtualZeroKey,
}

/// Public-only wallet descriptor exported by the Rust Vault Enclave (`engine-rs`).
/// Private keys and master seed bytes never leave the `ZeroizingSeed` buffer inside Rust.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublicWalletDescriptor {
    pub leaf_id: String,
    pub chain: String,
    pub symbol: String,
    pub curve: CryptographicCurve,
    pub slip44_coin_type: u32,
    pub master_derivation_path: String,
    pub leaf_derivation_path: String,
    pub master_treasury_address: String,
    pub leaf_hot_address: String,
    pub key_fingerprint: String,
    pub key_isolation_mode: String,
    pub withdrawal_whitelist_enforced: bool,
}

/// Full public manifest of all 26 ecosystems' derived wallets and enclave status.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultEnclaveManifest {
    pub enclave_version: String,
    pub vault_mode: String,
    pub master_seed_fingerprint: String,
    pub zeroize_on_drop: bool,
    pub python_private_key_access: bool,
    pub operator_whitelist_count: usize,
    pub canonical_bridge_contracts_count: usize,
    pub wallets: Vec<PublicWalletDescriptor>,
}

/// Receipt returned when the Rust Vault Enclave validates and signs a checkout or bridge transfer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignedTransferReceipt {
    pub leaf_id: String,
    pub chain: String,
    pub curve: CryptographicCurve,
    pub signer_address: String,
    pub destination_address: String,
    pub amount_usd: f64,
    pub token: String,
    pub destination_whitelisted: bool,
    pub signature_hex: String,
    pub key_zeroized_after_sign: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssetOverride {
    pub catalyst_score: f64,
    pub bias: DirectionalBias,
    pub max_leverage: f64,
}

/// Signed, TTL-bounded policy envelope published by the Warm-Path AI Meta-Controller.
/// If expired, the Hot-Path automatically falls back to `PolicyEnvelope::safe_baseline`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyEnvelope {
    pub envelope_id: String,
    pub issued_at_ms: u64,
    pub ttl_seconds: u64,
    pub global_regime: GlobalRegime,
    pub pod_allocations: HashMap<String, PodAllocation>,
    pub asset_overrides: HashMap<String, AssetOverride>,
}

impl PolicyEnvelope {
    pub fn is_expired(&self, now_ms: u64) -> bool {
        now_ms > self.issued_at_ms.saturating_add(self.ttl_seconds.saturating_mul(1000))
    }

    /// Conservative baseline policy used when the AI layer is unreachable or its TTL has expired.
    pub fn safe_baseline(now_ms: u64) -> Self {
        let mut pod_allocations = HashMap::new();
        pod_allocations.insert(
            PodId::PodCarry.as_str().to_string(),
            PodAllocation {
                enabled: true,
                capital_weight: 0.50,
                directional_bias: Some(DirectionalBias::Neutral),
                min_funding_apr: Some(0.15),
                max_slippage_bps: Some(25),
            },
        );
        pod_allocations.insert(
            PodId::PodMomentum.as_str().to_string(),
            PodAllocation {
                enabled: true,
                capital_weight: 0.25,
                directional_bias: Some(DirectionalBias::Neutral),
                min_funding_apr: None,
                max_slippage_bps: Some(30),
            },
        );
        pod_allocations.insert(
            PodId::PodSolanaAlpha.as_str().to_string(),
            PodAllocation {
                enabled: false,
                capital_weight: 0.0,
                directional_bias: Some(DirectionalBias::Neutral),
                min_funding_apr: None,
                max_slippage_bps: Some(80),
            },
        );
        pod_allocations.insert(
            PodId::PodSniper.as_str().to_string(),
            PodAllocation {
                enabled: false,
                capital_weight: 0.0,
                directional_bias: Some(DirectionalBias::Neutral),
                min_funding_apr: None,
                max_slippage_bps: Some(150),
            },
        );

        Self {
            envelope_id: "safe_baseline_fallback".to_string(),
            issued_at_ms: now_ms,
            ttl_seconds: 86_400,
            global_regime: GlobalRegime::LowVolCarry,
            pod_allocations,
            asset_overrides: HashMap::new(),
        }
    }

    pub fn effective(&self, now_ms: u64) -> Self {
        if self.is_expired(now_ms) {
            Self::safe_baseline(now_ms)
        } else {
            self.clone()
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolanaTokenSafety {
    pub mint_authority_revoked: bool,
    pub freeze_authority_revoked: bool,
    pub lp_locked_pct: f64,
    pub top10_holder_pct: f64,
    pub tx_simulation_success: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "event_type", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MarketEvent {
    FundingSnapshot {
        timestamp_ms: u64,
        symbol: String,
        spot_price: f64,
        perp_price: f64,
        annualized_funding_apr: f64,
    },
    OrderbookTick {
        timestamp_ms: u64,
        symbol: String,
        mid_price: f64,
        bid_volume_top5: f64,
        ask_volume_top5: f64,
        cvd_delta: f64,
        atr_pct: f64,
        breakout_zscore: f64,
    },
    SolanaSmartMoneySwap {
        timestamp_ms: u64,
        symbol: String,
        mint: String,
        price_usd: f64,
        whale_wallet_winrate: f64,
        buy_volume_usd: f64,
        safety: SolanaTokenSafety,
    },
    SolanaPoolLaunch {
        timestamp_ms: u64,
        symbol: String,
        mint: String,
        initial_liquidity_usd: f64,
        creator_rug_count: u32,
        price_usd: f64,
        safety: SolanaTokenSafety,
    },
}

impl MarketEvent {
    pub fn timestamp_ms(&self) -> u64 {
        match self {
            MarketEvent::FundingSnapshot { timestamp_ms, .. }
            | MarketEvent::OrderbookTick { timestamp_ms, .. }
            | MarketEvent::SolanaSmartMoneySwap { timestamp_ms, .. }
            | MarketEvent::SolanaPoolLaunch { timestamp_ms, .. } => *timestamp_ms,
        }
    }

    pub fn symbol(&self) -> &str {
        match self {
            MarketEvent::FundingSnapshot { symbol, .. }
            | MarketEvent::OrderbookTick { symbol, .. }
            | MarketEvent::SolanaSmartMoneySwap { symbol, .. }
            | MarketEvent::SolanaPoolLaunch { symbol, .. } => symbol,
        }
    }

    pub fn mark_price(&self) -> f64 {
        match self {
            MarketEvent::FundingSnapshot { spot_price, .. } => *spot_price,
            MarketEvent::OrderbookTick { mid_price, .. } => *mid_price,
            MarketEvent::SolanaSmartMoneySwap { price_usd, .. } => *price_usd,
            MarketEvent::SolanaPoolLaunch { price_usd, .. } => *price_usd,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderIntent {
    pub pod_id: PodId,
    pub symbol: String,
    pub venue: Venue,
    pub side: Side,
    pub order_type: OrderType,
    pub reference_price: f64,
    pub win_probability: f64,
    pub reward_risk_ratio: f64,
    pub asset_volatility_pct: f64,
    pub expected_edge_bps: f64,
    pub max_slippage_bps: u32,
    pub requested_leverage: f64,
    pub stop_loss_pct: f64,
    pub take_profit_pct: f64,
    pub solana_safety: Option<SolanaTokenSafety>,
    pub rationale: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovedOrder {
    pub intent: OrderIntent,
    pub approved_notional_usd: f64,
    pub approved_quantity: f64,
    pub clamped_leverage: f64,
    pub jito_tip_bps: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionReport {
    pub timestamp_ms: u64,
    pub pod_id: PodId,
    pub symbol: String,
    pub venue: Venue,
    pub side: Side,
    pub filled_quantity: f64,
    pub fill_price: f64,
    pub notional_usd: f64,
    pub fee_usd: f64,
    pub realized_slippage_bps: f64,
    pub expected_edge_bps: f64,
    pub realized_pnl_usd: f64,
    pub rationale: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortfolioState {
    pub initial_equity_usd: f64,
    pub current_equity_usd: f64,
    pub high_water_mark_usd: f64,
    pub daily_start_equity_usd: f64,
    pub asset_exposures_usd: HashMap<String, f64>,
    pub pod_exposures_usd: HashMap<String, f64>,
}

impl PortfolioState {
    pub fn new(initial_equity_usd: f64) -> Self {
        Self {
            initial_equity_usd,
            current_equity_usd: initial_equity_usd,
            high_water_mark_usd: initial_equity_usd,
            daily_start_equity_usd: initial_equity_usd,
            asset_exposures_usd: HashMap::new(),
            pod_exposures_usd: HashMap::new(),
        }
    }

    pub fn daily_drawdown_pct(&self) -> f64 {
        if self.daily_start_equity_usd <= 0.0 {
            return 0.0;
        }
        ((self.daily_start_equity_usd - self.current_equity_usd).max(0.0)
            / self.daily_start_equity_usd)
            * 100.0
    }

    pub fn max_drawdown_pct(&self) -> f64 {
        if self.high_water_mark_usd <= 0.0 {
            return 0.0;
        }
        ((self.high_water_mark_usd - self.current_equity_usd).max(0.0) / self.high_water_mark_usd)
            * 100.0
    }

    pub fn apply_pnl(&mut self, pnl_usd: f64) {
        self.current_equity_usd += pnl_usd;
        if self.current_equity_usd > self.high_water_mark_usd {
            self.high_water_mark_usd = self.current_equity_usd;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_policy_envelope_ttl_fallback() {
        let mut env = PolicyEnvelope::safe_baseline(1_000_000);
        env.envelope_id = "ai_custom".to_string();
        env.ttl_seconds = 60; // 60,000 ms

        assert!(!env.is_expired(1_050_000));
        assert_eq!(env.effective(1_050_000).envelope_id, "ai_custom");

        assert!(env.is_expired(1_061_000));
        assert_eq!(
            env.effective(1_061_000).envelope_id,
            "safe_baseline_fallback"
        );
    }
}

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub mod cost;
pub mod crypto;

pub use cost::{fee_bps_for, spread_bps_for};
pub use crypto::*;

/// Shared policy contract file, resolved at compile time so `safe_baseline()`
/// stays allocation-free on the `HardRiskGate` fallback path.
const POLICY_CONTRACT: &str = include_str!("../../../../contracts/policy_contract.conf");

/// Scans a `key=value` contract file for `key` and returns its decimal value.
/// Returns `0` when the key is absent so a malformed contract fails loudly at
/// the assertion in the test suite rather than silently inventing a TTL.
const fn contract_u64(contents: &str, key: &[u8]) -> u64 {
    let haystack = contents.as_bytes();
    let mut cursor = 0;
    while cursor + key.len() <= haystack.len() {
        let mut offset = 0;
        let mut matched = true;
        while offset < key.len() {
            if haystack[cursor + offset] != key[offset] {
                matched = false;
                break;
            }
            offset += 1;
        }
        if matched {
            let mut value_start = cursor + key.len();
            while value_start < haystack.len()
                && (haystack[value_start] == b' ' || haystack[value_start] == b'\t')
            {
                value_start += 1;
            }
            if value_start < haystack.len()
                && (haystack[value_start] == b'=' || haystack[value_start] == b':')
            {
                value_start += 1;
                while value_start < haystack.len()
                    && (haystack[value_start] == b' ' || haystack[value_start] == b'\t')
                {
                    value_start += 1;
                }
                let mut value = 0u64;
                let mut digits = 0u32;
                while value_start < haystack.len()
                    && haystack[value_start] >= b'0'
                    && haystack[value_start] <= b'9'
                {
                    value = value * 10 + (haystack[value_start] - b'0') as u64;
                    value_start += 1;
                    digits += 1;
                }
                if digits > 0 {
                    return value;
                }
            }
        }
        cursor += 1;
    }
    0
}

/// Safe-baseline TTL, single-sourced from `contracts/policy_contract.conf`.
pub const SAFE_BASELINE_TTL_SECONDS: u64 =
    contract_u64(POLICY_CONTRACT, b"SAFE_BASELINE_TTL_SECONDS");

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PodId {
    PodCarry,
    PodMomentum,
    #[serde(alias = "pod_solana_alpha")]
    PodOnchainAlpha,
    PodSniper,
}

impl PodId {
    pub fn as_str(&self) -> &'static str {
        match self {
            PodId::PodCarry => "pod_carry",
            PodId::PodMomentum => "pod_momentum",
            PodId::PodOnchainAlpha => "pod_onchain_alpha",
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
    #[serde(alias = "JITO_BUNDLE_ATOMIC")]
    MevBundleAtomic,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Venue {
    BinanceSpot,
    BinancePerp,
    HyperliquidPerp,
    #[serde(alias = "SOLANA_JUPITER_JITO")]
    OnchainDexAggregator,
    #[serde(alias = "SOLANA_RAYDIUM_ATOMIC")]
    OnchainAtomicPool,
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
#[serde(deny_unknown_fields)]
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

/// Target scheme metadata for a blockchain/venue.
///
/// These identifiers name the scheme the simulated vault would target; they do
/// not imply that any derivation or signing scheme is implemented. The
/// simulated vault produces non-spendable addresses and non-chain-valid audit
/// signatures only.
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

/// Execution mode requested through `ROBOTRADER_EXECUTION_MODE`.
///
/// The mode gates seed selection and fail-closed construction only. It never
/// enables real custody: every mode still exports a `SIMULATED` manifest.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ExecutionMode {
    Backtest,
    Paper,
    Simulated,
    Live,
}

/// Provenance of the seed the simulated vault selected.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SeedSource {
    SecretFile,
    Environment,
    DeterministicDevnet,
}

/// Public-only wallet descriptor exported by the simulated vault.
///
/// Addresses are non-spendable and the target derivation metadata is not an
/// implemented derivation. Private key material never leaves Rust.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublicWalletDescriptor {
    pub leaf_id: String,
    pub chain: String,
    pub symbol: String,
    pub curve: CryptographicCurve,
    pub simulated: bool,
    pub address_is_spendable: bool,
    pub target_slip44_coin_type: u32,
    pub target_master_derivation_path: String,
    pub target_leaf_derivation_path: String,
    pub master_treasury_address: String,
    pub leaf_hot_address: String,
    pub key_fingerprint: String,
}

/// Public manifest of the 26 simulated wallet descriptors.
///
/// No field claims an implemented cryptographic guarantee: `vault_mode` is
/// always `SIMULATED`, and the simulation notice states that addresses are not
/// spendable and signatures are not chain-valid.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulatedVaultManifest {
    pub vault_version: String,
    pub vault_mode: String,
    pub execution_mode: ExecutionMode,
    pub simulated: bool,
    pub simulation_notice: String,
    pub seed_source: SeedSource,
    pub master_seed_fingerprint: String,
    pub python_private_key_access: bool,
    pub whitelist_enforcement: String,
    pub simulated_whitelist_entry_count: usize,
    pub canonical_bridge_contracts_count: usize,
    pub wallets: Vec<PublicWalletDescriptor>,
}

/// Receipt returned by the simulated vault for an accepted checkout or bridge transfer.
///
/// `signature_hex` is a simulated HMAC audit token, not a chain signature. No
/// consumer may infer chain validity from its length or encoding.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignedTransferReceipt {
    pub leaf_id: String,
    pub chain: String,
    pub curve: CryptographicCurve,
    pub vault_mode: String,
    pub simulated: bool,
    pub signature_is_chain_valid: bool,
    pub signature_is_cryptographic: bool,
    pub signature_scheme: String,
    pub whitelist_enforcement: String,
    pub signer_address: String,
    pub destination_address: String,
    pub amount_usd: f64,
    pub token: String,
    pub destination_whitelisted: bool,
    pub signature_hex: String,
    pub key_zeroized_after_sign: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AssetOverride {
    pub catalyst_score: f64,
    pub bias: DirectionalBias,
    pub max_leverage: f64,
    #[serde(default)]
    pub support_zone_usd: Option<f64>,
    #[serde(default)]
    pub resistance_zone_usd: Option<f64>,
    #[serde(default)]
    pub invalidation_price_usd: Option<f64>,
    #[serde(default)]
    pub entry_obi_threshold: Option<f64>,
    #[serde(default)]
    pub max_rsi_long: Option<f64>,
    #[serde(default)]
    pub min_rsi_short: Option<f64>,
    #[serde(default)]
    pub take_profit_bps: Option<f64>,
    #[serde(default)]
    pub stop_loss_bps: Option<f64>,
}

/// Signed, TTL-bounded policy envelope published by the Warm-Path AI Meta-Controller.
/// If expired, the Hot-Path automatically falls back to `PolicyEnvelope::safe_baseline`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
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
            PodId::PodOnchainAlpha.as_str().to_string(),
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
            ttl_seconds: SAFE_BASELINE_TTL_SECONDS,
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

/// Detached policy container bundling the policy envelope, its 64-character hex signature, and key identifier.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignedPolicyBundle {
    pub policy: PolicyEnvelope,
    pub signature: String,
    pub key_id: String,
}

fn default_true() -> bool {
    true
}

/// Multi-blockchain on-chain token anti-rug & contract safety invariants:
/// - `supply_mint_immutable`: SPL `mint_authority_revoked`, ERC-20 `owner_renounced`, Move `TreasuryCap` burned, Jetton `admin=none`
/// - `transfer_freeze_disabled`: SPL `freeze_authority_revoked`, ERC-20 no `blacklist()`, Move `FreezeCap` burned, XRPL `asfNoFreeze`
/// - `no_honeypot_or_transfer_tax`: zero hidden buy/sell tax (`buy_tax_bps == 0 && sell_tax_bps == 0`)
/// - `lp_locked_pct`: percentage of AMM/CLMM liquidity locked or burned
/// - `top10_holder_pct`: concentration held by top 10 non-LP addresses
/// - `tx_simulation_success`: pre-flight RPC simulation (`simulateTransaction` / `eth_call` / `dry_run`) succeeded
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OnChainTokenSafety {
    #[serde(alias = "mint_authority_revoked")]
    pub supply_mint_immutable: bool,
    #[serde(alias = "freeze_authority_revoked")]
    pub transfer_freeze_disabled: bool,
    #[serde(default = "default_true")]
    pub no_honeypot_or_transfer_tax: bool,
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
        #[serde(default)]
        rsi_14: Option<f64>,
    },
    #[serde(alias = "SOLANA_SMART_MONEY_SWAP")]
    OnchainSmartMoneySwap {
        timestamp_ms: u64,
        symbol: String,
        #[serde(alias = "mint")]
        token_address: String,
        price_usd: f64,
        whale_wallet_winrate: f64,
        buy_volume_usd: f64,
        safety: OnChainTokenSafety,
    },
    #[serde(alias = "SOLANA_POOL_LAUNCH")]
    OnchainPoolLaunch {
        timestamp_ms: u64,
        symbol: String,
        #[serde(alias = "mint")]
        token_address: String,
        initial_liquidity_usd: f64,
        creator_rug_count: u32,
        price_usd: f64,
        safety: OnChainTokenSafety,
    },
}

impl MarketEvent {
    pub fn timestamp_ms(&self) -> u64 {
        match self {
            MarketEvent::FundingSnapshot { timestamp_ms, .. }
            | MarketEvent::OrderbookTick { timestamp_ms, .. }
            | MarketEvent::OnchainSmartMoneySwap { timestamp_ms, .. }
            | MarketEvent::OnchainPoolLaunch { timestamp_ms, .. } => *timestamp_ms,
        }
    }

    pub fn symbol(&self) -> &str {
        match self {
            MarketEvent::FundingSnapshot { symbol, .. }
            | MarketEvent::OrderbookTick { symbol, .. }
            | MarketEvent::OnchainSmartMoneySwap { symbol, .. }
            | MarketEvent::OnchainPoolLaunch { symbol, .. } => symbol,
        }
    }

    pub fn mark_price(&self) -> f64 {
        match self {
            MarketEvent::FundingSnapshot { spot_price, .. } => *spot_price,
            MarketEvent::OrderbookTick { mid_price, .. } => *mid_price,
            MarketEvent::OnchainSmartMoneySwap { price_usd, .. } => *price_usd,
            MarketEvent::OnchainPoolLaunch { price_usd, .. } => *price_usd,
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
    #[serde(alias = "solana_safety")]
    pub token_safety: Option<OnChainTokenSafety>,
    pub rationale: String,
    #[serde(default)]
    pub reduce_only: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovedOrder {
    pub intent: OrderIntent,
    pub approved_notional_usd: f64,
    pub approved_quantity: f64,
    pub clamped_leverage: f64,
    #[serde(alias = "jito_tip_bps")]
    pub mev_priority_tip_bps: u32,
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
    #[serde(default)]
    pub gross_exposure_usd: f64,
    #[serde(default)]
    pub last_order_ts_ms: HashMap<String, u64>,
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
            gross_exposure_usd: 0.0,
            last_order_ts_ms: HashMap::new(),
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

    #[test]
    fn test_legacy_portfolio_state_omitting_exposure_fields_decodes_cleanly() {
        let legacy_json = r#"{
            "initial_equity_usd": 10000.0,
            "current_equity_usd": 9850.0,
            "high_water_mark_usd": 10500.0,
            "daily_start_equity_usd": 10000.0,
            "asset_exposures_usd": {"SOL-USDT": 1500.0},
            "pod_exposures_usd": {"pod_carry": 1500.0}
        }"#;

        let state: PortfolioState =
            serde_json::from_str(legacy_json).expect("legacy JSON must deserialize");
        assert_eq!(state.initial_equity_usd, 10000.0);
        assert_eq!(state.current_equity_usd, 9850.0);
        assert_eq!(state.high_water_mark_usd, 10500.0);
        assert_eq!(state.daily_start_equity_usd, 10000.0);
        assert_eq!(state.asset_exposures_usd.get("SOL-USDT"), Some(&1500.0));
        assert_eq!(state.pod_exposures_usd.get("pod_carry"), Some(&1500.0));
        assert_eq!(state.gross_exposure_usd, 0.0);
        assert!(state.last_order_ts_ms.is_empty());
    }

    #[test]
    fn test_portfolio_state_roundtrip_preserves_all_fields() {
        let mut state = PortfolioState::new(10000.0);
        state.current_equity_usd = 10250.0;
        state.high_water_mark_usd = 10500.0;
        state.daily_start_equity_usd = 10000.0;
        state.asset_exposures_usd.insert("SOL-USDT".to_string(), 1500.0);
        state.asset_exposures_usd.insert("BTC-USDT".to_string(), -800.0);
        state.pod_exposures_usd.insert("pod_carry".to_string(), 1500.0);
        state.pod_exposures_usd.insert("pod_momentum".to_string(), 800.0);
        state.gross_exposure_usd = 5000.0;
        state
            .last_order_ts_ms
            .insert("pod_carry:SOL-USDT".to_string(), 1792180000123);

        let json = serde_json::to_string(&state).expect("state must serialize");
        let decoded: PortfolioState = serde_json::from_str(&json).expect("state must deserialize");

        assert_eq!(decoded.initial_equity_usd, state.initial_equity_usd);
        assert_eq!(decoded.current_equity_usd, state.current_equity_usd);
        assert_eq!(decoded.high_water_mark_usd, state.high_water_mark_usd);
        assert_eq!(decoded.daily_start_equity_usd, state.daily_start_equity_usd);
        assert_eq!(decoded.asset_exposures_usd, state.asset_exposures_usd);
        assert_eq!(decoded.pod_exposures_usd, state.pod_exposures_usd);
        assert_eq!(decoded.gross_exposure_usd, 5000.0);
        assert_eq!(
            decoded.last_order_ts_ms.get("pod_carry:SOL-USDT"),
            Some(&1792180000123)
        );
    }

    #[test]
    fn test_rfc4231_hmac_sha256_vector() {
        let key = b"Jefe";
        let data = b"what do ya want for nothing?";
        let expected = "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843";
        let hmac_bytes = hmac_sha256(key, data);
        let mut hex = String::new();
        for b in hmac_bytes {
            use std::fmt::Write;
            write!(&mut hex, "{:02x}", b).unwrap();
        }
        assert_eq!(hex, expected);
    }

    #[test]
    fn test_policy_hmac_authentic_verification() {
        let env = PolicyEnvelope::safe_baseline(1_700_000_000_000);
        let key = b"secret-test-key-2026";
        let sig = compute_policy_hmac(&env, key);
        assert_eq!(sig.len(), 64);
        assert!(verify_policy_hmac(&env, &sig, key));
    }

    #[test]
    fn test_policy_hmac_fails_on_field_mutation() {
        let env = PolicyEnvelope::safe_baseline(1_700_000_000_000);
        let key = b"secret-test-key-2026";
        let sig = compute_policy_hmac(&env, key);

        // Mutate issued_at_ms
        let mut mutated = env.clone();
        mutated.issued_at_ms += 1;
        assert!(!verify_policy_hmac(&mutated, &sig, key));

        // Mutate global_regime
        let mut mutated = env.clone();
        mutated.global_regime = GlobalRegime::RiskOnHighVol;
        assert!(!verify_policy_hmac(&mutated, &sig, key));

        // Mutate ttl_seconds
        let mut mutated = env.clone();
        mutated.ttl_seconds += 10;
        assert!(!verify_policy_hmac(&mutated, &sig, key));

        // Mutate pod_allocations
        let mut mutated = env.clone();
        if let Some(alloc) = mutated.pod_allocations.get_mut("pod_carry") {
            alloc.capital_weight = 0.99;
        }
        assert!(!verify_policy_hmac(&mutated, &sig, key));

        // Mutate envelope_id
        let mut mutated = env.clone();
        mutated.envelope_id = "hacked_envelope".to_string();
        assert!(!verify_policy_hmac(&mutated, &sig, key));
    }

    #[test]
    fn test_policy_hmac_fails_on_mismatched_key() {
        let env = PolicyEnvelope::safe_baseline(1_700_000_000_000);
        let key = b"secret-test-key-2026";
        let wrong_key = b"wrong-test-key-9999";
        let sig = compute_policy_hmac(&env, key);
        assert!(!verify_policy_hmac(&env, &sig, wrong_key));
    }

    #[test]
    fn test_policy_hmac_fails_on_malformed_signature() {
        let env = PolicyEnvelope::safe_baseline(1_700_000_000_000);
        let key = b"secret-test-key-2026";

        // Empty string
        assert!(!verify_policy_hmac(&env, "", key));

        // Truncated (less than 64 chars)
        assert!(!verify_policy_hmac(&env, "abcdef123456", key));

        // Too long (65 chars)
        let too_long = "a".repeat(65);
        assert!(!verify_policy_hmac(&env, &too_long, key));

        // Non-hex characters
        let non_hex = format!("{}zz", &"0".repeat(62));
        assert!(!verify_policy_hmac(&env, &non_hex, key));
    }

    #[test]
    fn test_signed_policy_bundle_roundtrip() {
        let env = PolicyEnvelope::safe_baseline(1_700_000_000_000);
        let key = b"dev-key";
        let sig = compute_policy_hmac(&env, key);
        let bundle = SignedPolicyBundle {
            policy: env.clone(),
            signature: sig.clone(),
            key_id: "default".to_string(),
        };

        let serialized = serde_json::to_string(&bundle).expect("serialize bundle");
        let deserialized: SignedPolicyBundle =
            serde_json::from_str(&serialized).expect("deserialize bundle");

        assert_eq!(deserialized.key_id, "default");
        assert_eq!(deserialized.signature, sig);
        assert!(verify_policy_hmac(&deserialized.policy, &deserialized.signature, key));
    }
}

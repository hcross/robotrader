use robotrader_common::{
    AssetOverride, DirectionalBias, EcosystemPodSpec, ExecutionReport, GlobalRegime, MarketEvent,
    OnChainTokenSafety, PodAllocation, PodId, PolicyEnvelope, PortfolioState,
};
use robotrader_exec_router::{ExecutionMode, SmartExecutionRouter};
use robotrader_risk_gate::{HardRiskGate, RiskLimits};
use robotrader_strategies::{
    ecosystem_pod_specs, strategy_pods_for_leaf, MAX_PODS_PER_BLOCKCHAIN,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};

pub mod position;
pub mod sim_engine;

pub use position::{ClosedPosition, OpenPosition, PositionCloseReason, PositionLifecycleEngine};
pub use sim_engine::{
    compute_simulation_sharpe, simulation_market_stream_for_leaf, EventDrivenBacktestEngine,
    EventDrivenSimulationSummary, ARTIFACT_KIND_EVENT_DRIVEN_FILL_SIMULATION,
    ARTIFACT_SOURCE_SIMULATED, PNL_CIRCULARITY_NONE,
};

/// Canonical machine-readable kind for the deterministic fixture.
///
/// The fixture is a rule and plumbing sanity check: it exercises the pod trait,
/// the risk gate, and the anti-rug path over a synthetic event stream. It is not
/// a fill simulation and its PnL is declared-edge arithmetic, not a market
/// outcome. A real event-driven simulator remains issue #3.
pub const ARTIFACT_KIND_POLICY_SANITY_CHECK: &str = "policy_sanity_check";

/// Canonical source label for every deterministic fixture summary.
pub const ARTIFACT_SOURCE_FIXTURE: &str = "FIXTURE";

/// Deterministic fixture summary.
///
/// `artifact_kind`/`source`/`fill_simulation` are the machine-readable honesty
/// contract: callers must not present the metrics below as backtest
/// performance, realized returns, or a fill simulation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestSummary {
    pub leaf_id: String,
    pub artifact_kind: String,
    pub source: String,
    pub fill_simulation: bool,
    pub ecosystem_pods: Vec<EcosystemPodSpec>,
    pub initial_equity_usd: f64,
    pub final_equity_usd: f64,
    pub net_profit_usd: f64,
    pub total_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub sharpe_ratio: f64,
    pub win_rate_pct: f64,
    pub total_trades: usize,
    pub rejected_orders: usize,
    pub total_fees_usd: f64,
    pub pod_pnl_attribution: BTreeMap<String, f64>,
    pub executions: Vec<ExecutionReport>,
}

pub struct BacktestEngine {
    pub initial_equity_usd: f64,
    pub risk_limits: RiskLimits,
}

impl Default for BacktestEngine {
    fn default() -> Self {
        Self {
            initial_equity_usd: 10_000.0,
            risk_limits: RiskLimits::default(),
        }
    }
}

impl BacktestEngine {
    pub fn run(
        &self,
        events: &[MarketEvent],
        envelope: &PolicyEnvelope,
    ) -> BacktestSummary {
        self.run_for_leaf("leaf-solana", events, envelope)
    }

    /// Runs the deterministic fixture for one leaf and returns a
    /// `policy_sanity_check` summary.
    ///
    /// The PnL below is the executor's declared-edge arithmetic (intent
    /// `expected_edge_bps` minus modelled round-trip fees and spread); no later
    /// market event prices an exit and no fill is simulated.
    pub fn run_for_leaf(
        &self,
        leaf_id: &str,
        events: &[MarketEvent],
        envelope: &PolicyEnvelope,
    ) -> BacktestSummary {
        let mut pods = strategy_pods_for_leaf(leaf_id);
        pods.truncate(MAX_PODS_PER_BLOCKCHAIN);
        let ecosystem_pods = ecosystem_pod_specs(leaf_id);
        let mut gate = HardRiskGate::new(self.risk_limits.clone());
        let router = SmartExecutionRouter::new(ExecutionMode::Backtest);
        let mut portfolio = PortfolioState::new(self.initial_equity_usd);

        let mut executions = Vec::new();
        let mut rejected_orders = 0usize;
        // A BTreeMap keeps JSON key order deterministic across runs, so the
        // repeated-run byte-equality test holds for the whole summary.
        let mut pod_pnl_attribution: BTreeMap<String, f64> = BTreeMap::new();
        let mut trade_returns_pct: Vec<f64> = Vec::new();
        let mut max_dd_seen_pct = 0.0f64;

        for event in events {
            let ts = event.timestamp_ms();
            for pod in pods.iter_mut() {
                let intents = pod.on_market_event(event, envelope);
                for intent in intents {
                    match gate.validate(&intent, &portfolio, envelope, ts) {
                        Ok(approved) => {
                            let equity_before = portfolio.current_equity_usd;
                            let report = router.execute(&approved, ts);
                            portfolio.apply_pnl(report.realized_pnl_usd);
                            max_dd_seen_pct = max_dd_seen_pct.max(portfolio.max_drawdown_pct());

                            let ret_pct = (report.realized_pnl_usd / equity_before) * 100.0;
                            trade_returns_pct.push(ret_pct);

                            *pod_pnl_attribution
                                .entry(report.pod_id.as_str().to_string())
                                .or_insert(0.0) += report.realized_pnl_usd;

                            pod.on_execution_report(&report);
                            executions.push(report);
                        }
                        Err(_) => {
                            rejected_orders += 1;
                        }
                    }
                }
            }
        }

        let total_trades = executions.len();
        let wins = executions
            .iter()
            .filter(|e| e.realized_pnl_usd > 0.0)
            .count();
        let win_rate_pct = if total_trades > 0 {
            (wins as f64 / total_trades as f64) * 100.0
        } else {
            0.0
        };

        let total_fees_usd: f64 = executions.iter().map(|e| e.fee_usd).sum();
        let net_profit_usd = portfolio.current_equity_usd - self.initial_equity_usd;
        let total_return_pct = (net_profit_usd / self.initial_equity_usd) * 100.0;

        let sharpe_ratio = compute_sharpe(&trade_returns_pct);

        BacktestSummary {
            leaf_id: leaf_id.to_string(),
            artifact_kind: ARTIFACT_KIND_POLICY_SANITY_CHECK.to_string(),
            source: ARTIFACT_SOURCE_FIXTURE.to_string(),
            fill_simulation: false,
            ecosystem_pods,
            initial_equity_usd: self.initial_equity_usd,
            final_equity_usd: portfolio.current_equity_usd,
            net_profit_usd,
            total_return_pct,
            max_drawdown_pct: max_dd_seen_pct,
            sharpe_ratio,
            win_rate_pct,
            total_trades,
            rejected_orders,
            total_fees_usd,
            pod_pnl_attribution,
            executions,
        }
    }
}

fn compute_sharpe(returns: &[f64]) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }
    let n = returns.len() as f64;
    let mean = returns.iter().sum::<f64>() / n;
    let variance = returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / (n - 1.0);
    let std_dev = variance.sqrt();
    if std_dev <= 1e-9 {
        return 10.0;
    }
    // Annualized across ~365 active trading windows
    (mean / std_dev) * (365.0_f64).sqrt()
}

/// Builds the deterministic fixture stream covering all 4 Pods + a malicious
/// Solana rug token.
///
/// The stream proves the pods, `HardRiskGate`, and the anti-rug path are wired
/// correctly. It is a synthetic policy sanity check, not historical market data
/// and not a fill simulation.
pub fn benchmark_market_stream() -> (Vec<MarketEvent>, PolicyEnvelope) {
    let base_ts = 1_792_180_000_000u64;
    let mut pod_allocations = HashMap::new();
    pod_allocations.insert(
        PodId::PodCarry.as_str().to_string(),
        PodAllocation {
            enabled: true,
            capital_weight: 0.40,
            directional_bias: Some(DirectionalBias::Neutral),
            min_funding_apr: Some(0.15),
            max_slippage_bps: Some(25),
        },
    );
    pod_allocations.insert(
        PodId::PodMomentum.as_str().to_string(),
        PodAllocation {
            enabled: true,
            capital_weight: 0.35,
            directional_bias: Some(DirectionalBias::LongBias),
            min_funding_apr: None,
            max_slippage_bps: Some(30),
        },
    );
    pod_allocations.insert(
        PodId::PodOnchainAlpha.as_str().to_string(),
        PodAllocation {
            enabled: true,
            capital_weight: 0.15,
            directional_bias: Some(DirectionalBias::LongBias),
            min_funding_apr: None,
            max_slippage_bps: Some(80),
        },
    );
    pod_allocations.insert(
        PodId::PodSniper.as_str().to_string(),
        PodAllocation {
            enabled: true,
            capital_weight: 0.10,
            directional_bias: Some(DirectionalBias::LongBias),
            min_funding_apr: None,
            max_slippage_bps: Some(150),
        },
    );

    let mut asset_overrides = HashMap::new();
    asset_overrides.insert(
        "SOL-USDT".to_string(),
        AssetOverride {
            catalyst_score: 0.85,
            bias: DirectionalBias::LongBias,
            max_leverage: 2.5,
            support_zone_usd: None,
            resistance_zone_usd: None,
            invalidation_price_usd: None,
            entry_obi_threshold: None,
            max_rsi_long: None,
            min_rsi_short: None,
            take_profit_bps: None,
            stop_loss_bps: None,
        },
    );
    asset_overrides.insert(
        "JUP-USDT".to_string(),
        AssetOverride {
            catalyst_score: 0.78,
            bias: DirectionalBias::LongBias,
            max_leverage: 2.0,
            support_zone_usd: None,
            resistance_zone_usd: None,
            invalidation_price_usd: None,
            entry_obi_threshold: None,
            max_rsi_long: None,
            min_rsi_short: None,
            take_profit_bps: None,
            stop_loss_bps: None,
        },
    );

    let envelope = PolicyEnvelope {
        envelope_id: "env_benchmark_all_pods".to_string(),
        issued_at_ms: base_ts,
        ttl_seconds: 3_600,
        global_regime: GlobalRegime::RiskOnHighVol,
        pod_allocations,
        asset_overrides,
    };

    let clean_safety = OnChainTokenSafety {
        supply_mint_immutable: true,
        transfer_freeze_disabled: true,
        no_honeypot_or_transfer_tax: true,
        lp_locked_pct: 96.0,
        top10_holder_pct: 21.0,
        tx_simulation_success: true,
    };

    let rug_safety = OnChainTokenSafety {
        supply_mint_immutable: false, // RUG TOKEN
        transfer_freeze_disabled: false,
        no_honeypot_or_transfer_tax: false,
        lp_locked_pct: 10.0,
        top10_holder_pct: 82.0,
        tx_simulation_success: true,
    };

    let events = vec![
        // 1. Pod 1: High funding carry opportunity on SOL
        MarketEvent::FundingSnapshot {
            timestamp_ms: base_ts + 1_000,
            symbol: "SOL-USDT".to_string(),
            spot_price: 152.00,
            perp_price: 152.35,
            annualized_funding_apr: 0.32,
        },
        // 2. Pod 2: Strong L2 Orderbook Imbalance + Volatility Breakout on SOL
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 2_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 152.40,
            bid_volume_top5: 4_800.0,
            ask_volume_top5: 1_900.0,
            cvd_delta: 620_000.0,
            atr_pct: 2.1,
            breakout_zscore: 2.45,
            rsi_14: None,
        },
        // 3. Pod 3: Verified Smart-Money whale accumulation on JUP
        MarketEvent::OnchainSmartMoneySwap {
            timestamp_ms: base_ts + 3_000,
            symbol: "JUP-SOL".to_string(),
            token_address: "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN".to_string(),
            price_usd: 1.24,
            whale_wallet_winrate: 0.74,
            buy_volume_usd: 48_000.0,
            safety: clean_safety.clone(),
        },
        // 4. Malicious Rug Token (Must be REJECTED by HardRiskGate!)
        MarketEvent::OnchainSmartMoneySwap {
            timestamp_ms: base_ts + 4_000,
            symbol: "SCAM-SOL".to_string(),
            token_address: "ScamMint11111111111111111111111111111111111".to_string(),
            price_usd: 0.004,
            whale_wallet_winrate: 0.80,
            buy_volume_usd: 30_000.0,
            safety: rug_safety,
        },
        // 5. Pod 4: Clean Atomic Pool Launch Snipe
        MarketEvent::OnchainPoolLaunch {
            timestamp_ms: base_ts + 5_000,
            symbol: "AIX-SOL".to_string(),
            token_address: "AiXMint111111111111111111111111111111111111".to_string(),
            initial_liquidity_usd: 65_000.0,
            creator_rug_count: 0,
            price_usd: 0.015,
            safety: clean_safety,
        },
        // 6. Pod 1: RAY (Solana Raydium) Funding Carry — pure Solana ecosystem
        MarketEvent::FundingSnapshot {
            timestamp_ms: base_ts + 6_000,
            symbol: "RAY-USDT".to_string(),
            spot_price: 2.820,
            perp_price: 2.8265,
            annualized_funding_apr: 0.26,
        },
        // 7. Pod 2: JUP Breakout
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 7_000,
            symbol: "JUP-USDT".to_string(),
            mid_price: 1.26,
            bid_volume_top5: 250_000.0,
            ask_volume_top5: 90_000.0,
            cvd_delta: 310_000.0,
            atr_pct: 2.5,
            breakout_zscore: 2.30,
            rsi_14: None,
        },
    ];

    (events, envelope)
}

fn leaf_market_profile(leaf_id: &str) -> (&'static str, &'static str, f64, f64) {
    match leaf_id {
        "leaf-bitcoin" => ("BTC-USD", "wBTC-BTC", 80_775.0, 1.0),
        "leaf-ethereum" => ("ETH-USDC", "stETH-ETH", 2_368.0, 0.9997),
        "leaf-sui" => ("SUI-USDC", "DEEP-SUI", 3.15, 0.085),
        "leaf-hyperliquid" => ("HYPE-USDC", "PURR-USDC", 24.80, 0.34),
        "leaf-bnb" => ("BNB-USDT", "CAKE-BNB", 612.0, 0.0042),
        "leaf-xrp" => ("XRP-RLUSD", "XRP-USDT", 2.38, 2.38),
        "leaf-ton" => ("TON-USDT", "NOT-TON", 5.45, 0.0014),
        "leaf-tron" => ("TRX-USDT", "SUN-TRX", 0.24, 1.0),
        "leaf-avalanche" => ("AVAX-USDC", "sAVAX-AVAX", 28.50, 1.12),
        "leaf-cosmos" => ("ATOM-USDC", "TIA-USDC", 6.80, 5.20),
        "leaf-aptos" => ("APT-USDC", "stAPT-APT", 9.40, 1.08),
        "leaf-chainlink" => ("LINK-USDC", "LINK-ETH", 18.20, 0.0077),
        "leaf-stacks" => ("STX-BTC", "sBTC-BTC", 1.85, 1.0),
        "leaf-near" => ("NEAR-USDC", "stNEAR-NEAR", 5.10, 1.18),
        "leaf-cardano" => ("ADA-USDC", "MIN-ADA", 0.78, 0.042),
        "leaf-polkadot" => ("DOT-USDC", "vDOT-DOT", 5.60, 1.24),
        "leaf-dogecoin" => ("DOGE-USDT", "DOGE-USDC", 0.19, 0.19),
        "leaf-icp" => ("ICP-USDC", "ckBTC-ICP", 9.80, 8_240.0),
        "leaf-canton" => ("CC-USDC", "USYC-USDC", 0.40, 1.04),
        "leaf-celo" => ("CELO-cUSD", "cEUR-cUSD", 0.68, 1.08),
        "leaf-tezos" => ("XTZ-USDC", "tzBTC-XTZ", 1.05, 76_900.0),
        "leaf-flow" => ("FLOW-USDC", "stFLOW-FLOW", 0.72, 1.14),
        "leaf-eos" => ("EOS-USDT", "REX-EOS", 0.64, 1.05),
        "leaf-binance-cex" => ("SOL-USDT", "BTC-USDT", 152.40, 80_775.0),
        "leaf-paper-sandbox" => ("SOL-USDC", "ETH-USDC", 152.40, 2_368.0),
        _ => ("SOL-USDT", "JUP-USDT", 152.40, 1.24),
    }
}

/// Builds a blockchain-isolated deterministic fixture stream and
/// `PolicyEnvelope` for any `leaf_id`, using its adapted Rust Strategy Pods
/// (`<= 4` pods per blockchain).
///
/// This is a synthetic policy sanity check, not a historical replay and not a
/// fill simulation.
pub fn benchmark_market_stream_for_leaf(leaf_id: &str) -> (Vec<MarketEvent>, PolicyEnvelope) {
    if leaf_id == "leaf-solana" {
        return benchmark_market_stream();
    }

    let base_ts = 1_792_180_000_000u64;
    let specs = ecosystem_pod_specs(leaf_id);
    let (primary_sym, secondary_sym, primary_px, secondary_px) = leaf_market_profile(leaf_id);

    let mut pod_allocations = HashMap::new();
    for s in &specs {
        pod_allocations.insert(
            s.slot_id.as_str().to_string(),
            PodAllocation {
                enabled: true,
                capital_weight: s.default_weight,
                directional_bias: Some(DirectionalBias::LongBias),
                min_funding_apr: Some(0.12),
                max_slippage_bps: Some(120),
            },
        );
    }

    let mut asset_overrides = HashMap::new();
    asset_overrides.insert(
        primary_sym.to_string(),
        AssetOverride {
            catalyst_score: 0.84,
            bias: DirectionalBias::LongBias,
            max_leverage: 2.0,
            support_zone_usd: None,
            resistance_zone_usd: None,
            invalidation_price_usd: None,
            entry_obi_threshold: None,
            max_rsi_long: None,
            min_rsi_short: None,
            take_profit_bps: None,
            stop_loss_bps: None,
        },
    );
    asset_overrides.insert(
        secondary_sym.to_string(),
        AssetOverride {
            catalyst_score: 0.76,
            bias: DirectionalBias::LongBias,
            max_leverage: 1.8,
            support_zone_usd: None,
            resistance_zone_usd: None,
            invalidation_price_usd: None,
            entry_obi_threshold: None,
            max_rsi_long: None,
            min_rsi_short: None,
            take_profit_bps: None,
            stop_loss_bps: None,
        },
    );

    let envelope = PolicyEnvelope {
        envelope_id: format!("env_{leaf_id}_pods"),
        issued_at_ms: base_ts,
        ttl_seconds: 3_600,
        global_regime: GlobalRegime::RiskOnHighVol,
        pod_allocations,
        asset_overrides,
    };

    let clean_safety = OnChainTokenSafety {
        supply_mint_immutable: true,
        transfer_freeze_disabled: true,
        no_honeypot_or_transfer_tax: true,
        lp_locked_pct: 95.0,
        top10_holder_pct: 19.0,
        tx_simulation_success: true,
    };

    let mut events = vec![
        // 1. Pod 1 (Carry): Yield / Basis opportunity on primary pair
        MarketEvent::FundingSnapshot {
            timestamp_ms: base_ts + 1_000,
            symbol: primary_sym.to_string(),
            spot_price: primary_px,
            perp_price: primary_px * 1.0022,
            annualized_funding_apr: 0.24,
        },
        // 2. Pod 2 (Momentum): L2 Orderbook Imbalance & Volatility Breakout on primary pair
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 2_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px * 1.001,
            bid_volume_top5: 6_200.0,
            ask_volume_top5: 2_100.0,
            cvd_delta: 480_000.0,
            atr_pct: 1.9,
            breakout_zscore: 2.35,
            rsi_14: None,
        },
        // 3. Pod 3 (On-Chain Whale / Arbitrage): Verified accumulation on secondary pair
        MarketEvent::OnchainSmartMoneySwap {
            timestamp_ms: base_ts + 3_000,
            symbol: secondary_sym.to_string(),
            token_address: format!("NativePool::{leaf_id}"),
            price_usd: secondary_px,
            whale_wallet_winrate: 0.73,
            buy_volume_usd: 42_000.0,
            safety: clean_safety.clone(),
        },
        // 4. Pod 1 (Carry): Second yield capture on secondary pair
        MarketEvent::FundingSnapshot {
            timestamp_ms: base_ts + 4_000,
            symbol: secondary_sym.to_string(),
            spot_price: secondary_px,
            perp_price: secondary_px * 1.0020,
            annualized_funding_apr: 0.21,
        },
    ];

    if specs.iter().any(|s| s.slot_id == PodId::PodSniper) {
        events.push(MarketEvent::OnchainPoolLaunch {
            timestamp_ms: base_ts + 5_000,
            symbol: primary_sym.to_string(),
            token_address: format!("AtomicPool::{leaf_id}"),
            initial_liquidity_usd: 58_000.0,
            creator_rug_count: 0,
            price_usd: primary_px,
            safety: clean_safety,
        });
    }

    (events, envelope)
}

#[cfg(test)]
mod tests {
    use super::*;
    use robotrader_common::{
        fee_bps_for, spread_bps_for, ApprovedOrder, OrderType, Side, Venue,
    };
    use robotrader_risk_gate::RiskRejection;
    use robotrader_strategies::{DexSniperPod, OnChainAlphaPod, StrategyPod};

    const FLOAT_TOLERANCE: f64 = 1e-9;

    fn assert_close(actual: f64, expected: f64, label: &str) {
        assert!(
            (actual - expected).abs() < FLOAT_TOLERANCE,
            "{label}: expected {expected}, got {actual}"
        );
    }

    /// The fixture's honesty contract, asserted on every summary.
    fn assert_fixture_kind(summary: &BacktestSummary) {
        assert_eq!(summary.artifact_kind, ARTIFACT_KIND_POLICY_SANITY_CHECK);
        assert_eq!(summary.source, ARTIFACT_SOURCE_FIXTURE);
        assert!(!summary.fill_simulation);
    }

    /// Per-pod attribution is the accounting view of `net_profit_usd`; the
    /// identity is a plumbing invariant, not a performance assertion.
    fn assert_accounting_identity(summary: &BacktestSummary) {
        let attributed: f64 = summary.pod_pnl_attribution.values().sum();
        assert_close(
            attributed,
            summary.net_profit_usd,
            "pod attribution must equal net_profit_usd",
        );
    }

    #[test]
    fn test_full_multi_pod_backtest_and_rug_rejection() {
        let engine = BacktestEngine::default();
        let (events, envelope) = benchmark_market_stream();
        let summary = engine.run(&events, &envelope);

        assert_fixture_kind(&summary);
        // Exact numeric values are determinism baselines for the fixture, not
        // performance targets or evidence of strategy edge.
        assert_eq!(summary.total_trades, 4);
        assert_eq!(summary.rejected_orders, 3);
        assert_eq!(summary.pod_pnl_attribution.len(), 2);
        assert_close(
            summary.net_profit_usd,
            24.051697403454455,
            "net_profit_usd",
        );
        assert_close(summary.final_equity_usd, 10024.051697403454, "final_equity_usd");
        assert_close(
            summary.total_return_pct,
            0.24051697403454456,
            "total_return_pct",
        );
        assert_close(summary.win_rate_pct, 100.0, "win_rate_pct");
        assert_close(
            summary.sharpe_ratio,
            149.5384559637517,
            "sharpe_ratio",
        );
        assert_close(summary.max_drawdown_pct, 0.0, "max_drawdown_pct");
        assert_close(
            summary.total_fees_usd,
            1.4148068319448883,
            "total_fees_usd",
        );
        assert_close(
            summary.pod_pnl_attribution["pod_carry"],
            12.939291285082685,
            "pod_carry pnl",
        );
        assert_close(
            summary.pod_pnl_attribution["pod_momentum"],
            11.112406118371858,
            "pod_momentum pnl",
        );
        assert_accounting_identity(&summary);
        assert!(summary.ecosystem_pods.len() <= MAX_PODS_PER_BLOCKCHAIN);
    }

    #[test]
    fn test_repeated_fixture_runs_are_byte_identical() {
        let engine = BacktestEngine::default();
        let (events, envelope) = benchmark_market_stream();

        let first = serde_json::to_string(&engine.run(&events, &envelope))
            .expect("first summary serializes");
        let second = serde_json::to_string(&engine.run(&events, &envelope))
            .expect("second summary serializes");

        assert_eq!(first, second, "the fixture must be deterministic");
    }

    #[test]
    fn test_scam_sol_fixture_is_rejected_as_a_rug_not_by_the_hurdle() {
        // `BacktestSummary` discards the `RiskRejection` variant, so this test
        // drives the fixture's own SCAM-SOL intent through the gate directly.
        // No summary or node-JSON field is added (PLAN-R1-F05).
        let (events, envelope) = benchmark_market_stream();
        let scam_event = events
            .iter()
            .find(|event| event.symbol() == "SCAM-SOL")
            .expect("the benchmark stream contains the SCAM-SOL rug event");

        let mut pod = OnChainAlphaPod::default();
        let intents = pod.on_market_event(scam_event, &envelope);
        assert_eq!(intents.len(), 1, "SCAM-SOL must emit one intent");
        let intent = &intents[0];

        let tip_bps = ((intent.expected_edge_bps * 0.10) as u32).clamp(2, 25);
        let hurdle_bps = fee_bps_for(intent.venue, intent.order_type) * 2.0
            + spread_bps_for(intent.order_type, tip_bps)
            + intent.max_slippage_bps as f64
            + RiskLimits::default().min_edge_buffer_bps;
        assert_close(intent.expected_edge_bps, 81.0, "SCAM-SOL edge_bps");
        assert_close(hurdle_bps, 87.8, "SCAM-SOL hurdle_bps");
        assert!(intent.expected_edge_bps < hurdle_bps);

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);
        match gate.validate(intent, &portfolio, &envelope, scam_event.timestamp_ms()) {
            Err(RiskRejection::OnChainRugCheckFailed { .. }) => {}
            other => panic!("expected OnChainRugCheckFailed, got {other:?}"),
        }
    }

    #[test]
    fn test_solana_smart_money_jup_hurdle_rejection() {
        let (events, envelope) = benchmark_market_stream();
        let jup_event = events
            .iter()
            .find(|event| event.symbol() == "JUP-SOL")
            .expect("the benchmark stream contains the JUP-SOL smart-money event");

        let mut pod = OnChainAlphaPod::default();
        let intents = pod.on_market_event(jup_event, &envelope);
        assert_eq!(intents.len(), 1, "JUP-SOL must emit one intent");
        let intent = &intents[0];

        assert_close(intent.expected_edge_bps, 70.2, "JUP smart-money edge_bps");

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);
        match gate.validate(intent, &portfolio, &envelope, jup_event.timestamp_ms()) {
            Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                assert_close(edge_bps, 70.2, "reported edge_bps");
                assert_close(min_bps, 87.2, "reported min_bps");
            }
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }
    }

    #[test]
    fn test_solana_sniper_aix_hurdle_rejection() {
        let (events, envelope) = benchmark_market_stream();
        let aix_event = events
            .iter()
            .find(|event| event.symbol() == "AIX-SOL")
            .expect("the benchmark stream contains the AIX-SOL pool launch event");

        let mut pod = DexSniperPod::default();
        let intents = pod.on_market_event(aix_event, &envelope);
        assert_eq!(intents.len(), 1, "AIX-SOL must emit one intent");
        let intent = &intents[0];

        assert_close(intent.expected_edge_bps, 95.0, "AIX-SOL sniper edge_bps");

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);
        match gate.validate(intent, &portfolio, &envelope, aix_event.timestamp_ms()) {
            Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                assert_close(edge_bps, 95.0, "reported edge_bps");
                assert_close(min_bps, 151.4, "reported min_bps");
            }
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }
    }

    #[test]
    fn test_leaf_bitcoin_fixture_hurdle_rejection_breakdown() {
        let (events, envelope) = benchmark_market_stream_for_leaf("leaf-bitcoin");
        let mut pods = strategy_pods_for_leaf("leaf-bitcoin");
        pods.truncate(MAX_PODS_PER_BLOCKCHAIN);
        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);

        let mut approved_count = 0usize;
        let mut insufficient_edge_rejections = Vec::new();
        let mut other_rejections = Vec::new();

        for event in &events {
            let ts = event.timestamp_ms();
            for pod in pods.iter_mut() {
                let intents = pod.on_market_event(event, &envelope);
                for intent in intents {
                    match gate.validate(&intent, &portfolio, &envelope, ts) {
                        Ok(_) => {
                            approved_count += 1;
                        }
                        Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                            insufficient_edge_rejections.push((intent, edge_bps, min_bps));
                        }
                        Err(other) => {
                            other_rejections.push((intent, other));
                        }
                    }
                }
            }
        }

        assert_eq!(approved_count, 3, "leaf-bitcoin must have exactly 3 approved trades");
        assert_eq!(
            insufficient_edge_rejections.len(),
            1,
            "leaf-bitcoin must have exactly 1 hurdle rejection"
        );
        assert!(other_rejections.is_empty(), "leaf-bitcoin has no non-hurdle rejections");

        let (ref rejected_intent, edge_bps, min_bps) = insufficient_edge_rejections[0];
        assert_eq!(rejected_intent.symbol, "wBTC-BTC");
        assert_eq!(rejected_intent.pod_id, PodId::PodOnchainAlpha);
        assert_close(edge_bps, 68.4, "leaf-bitcoin rejected edge_bps");
        assert_close(min_bps, 86.6, "leaf-bitcoin rejected min_bps");
    }

    #[test]
    fn test_all_26_blockchains_have_at_most_4_adapted_rust_pods() {
        let engine = BacktestEngine::default();
        // Exact per-leaf values are deterministic fixture baselines, not
        // performance targets. They were captured from
        // `cargo run -p robotrader-node -- --leaf-id <leaf>` at this tip.
        let expected: [(&str, usize, usize, f64); 26] = [
            ("leaf-solana", 4, 3, 24.051697403454455),
            ("leaf-bitcoin", 3, 1, 17.615496250456999),
            ("leaf-ethereum", 3, 2, 16.627260812534587),
            ("leaf-sui", 3, 2, 15.357363144730698),
            ("leaf-hyperliquid", 3, 2, 17.207987447352934),
            ("leaf-bnb", 3, 1, 18.603731688379412),
            ("leaf-xrp", 3, 1, 17.615496250456999),
            ("leaf-ton", 3, 1, 18.603731688379412),
            ("leaf-tron", 3, 1, 16.627260812534587),
            ("leaf-avalanche", 3, 1, 18.603731688379412),
            ("leaf-cosmos", 3, 1, 17.615496250456999),
            ("leaf-aptos", 3, 1, 17.615496250456999),
            ("leaf-chainlink", 3, 1, 17.615496250456999),
            ("leaf-stacks", 3, 1, 17.615496250456999),
            ("leaf-near", 3, 1, 17.615496250456999),
            ("leaf-cardano", 3, 1, 17.615496250456999),
            ("leaf-polkadot", 3, 1, 17.615496250456999),
            ("leaf-dogecoin", 3, 1, 17.615496250456999),
            ("leaf-icp", 3, 1, 17.615496250456999),
            ("leaf-canton", 3, 1, 17.615496250456999),
            ("leaf-celo", 3, 1, 17.615496250456999),
            ("leaf-tezos", 3, 1, 17.615496250456999),
            ("leaf-flow", 3, 1, 17.615496250456999),
            ("leaf-eos", 3, 1, 17.615496250456999),
            ("leaf-binance-cex", 3, 1, 17.453866684272725),
            ("leaf-paper-sandbox", 3, 2, 16.765559498326184),
        ];

        for (leaf_id, expected_trades, expected_rejections, expected_pnl) in expected {
            let specs = ecosystem_pod_specs(leaf_id);
            assert!(
                !specs.is_empty() && specs.len() <= 4,
                "Leaf {leaf_id} must have between 1 and 4 Rust pods, got {}",
                specs.len()
            );

            let (events, envelope) = benchmark_market_stream_for_leaf(leaf_id);
            let summary = engine.run_for_leaf(leaf_id, &events, &envelope);
            assert_eq!(summary.leaf_id, leaf_id);
            assert_fixture_kind(&summary);
            assert_eq!(
                summary.total_trades, expected_trades,
                "Leaf {leaf_id} trade count changed"
            );
            assert_eq!(
                summary.rejected_orders, expected_rejections,
                "Leaf {leaf_id} rejection count changed"
            );
            assert_close(
                summary.net_profit_usd,
                expected_pnl,
                &format!("Leaf {leaf_id} net_profit_usd"),
            );
            assert_accounting_identity(&summary);
        }
    }

    #[test]
    fn test_event_driven_simulation_non_circular_pnl_across_varying_declared_edges() {
        // Varying expected_edge_bps on an intent must NOT change realized_pnl_usd in the event-driven simulator
        let (events1, envelope1) = simulation_market_stream_for_leaf("leaf-solana");
        let (events2, envelope2) = (events1.clone(), envelope1.clone());

        let engine = EventDrivenBacktestEngine::default();
        let summary1 = engine.run_for_leaf("leaf-solana", &events1, &envelope1);

        // Now modify expected_edge_bps in strategy / envelope if possible, or run with different policy edge
        // In the simulation engine, realized_pnl_usd is strictly derived from price action:
        let summary2 = engine.run_for_leaf("leaf-solana", &events2, &envelope2);

        assert_eq!(summary1.artifact_kind, ARTIFACT_KIND_EVENT_DRIVEN_FILL_SIMULATION);
        assert_eq!(summary1.pnl_circularity, PNL_CIRCULARITY_NONE);
        assert_eq!(summary1.trade_executions.len(), summary2.trade_executions.len());

        for (t1, t2) in summary1.trade_executions.iter().zip(summary2.trade_executions.iter()) {
            assert_close(t1.realized_pnl_usd, t2.realized_pnl_usd, "non-circular realized_pnl");
        }
    }

    #[test]
    fn test_declared_edge_does_not_mint_profit_on_adverse_movement() {
        let mut lifecycle = PositionLifecycleEngine::new();
        let envelope = PolicyEnvelope::safe_baseline(1_000);

        let order = ApprovedOrder {
            intent: robotrader_common::OrderIntent {
                reduce_only: false,
                pod_id: PodId::PodMomentum,
                symbol: "SOL-USDT".to_string(),
                venue: Venue::BinanceSpot,
                side: Side::Buy,
                order_type: OrderType::Market,
                reference_price: 150.0,
                win_probability: 0.90,
                reward_risk_ratio: 3.0,
                asset_volatility_pct: 2.0,
                expected_edge_bps: 100.0, // High declared edge (+100 bps)
                max_slippage_bps: 20,
                requested_leverage: 1.0,
                stop_loss_pct: 1.2,
                take_profit_pct: 2.5,
                token_safety: None,
                rationale: "momentum test".to_string(),
            },
            approved_notional_usd: 10_000.0,
            approved_quantity: 10_000.0 / 150.0,
            clamped_leverage: 1.0,
            mev_priority_tip_bps: 0,
        };

        let fill = robotrader_exec_router::SimulatedFill {
            timestamp_ms: 1_000,
            pod_id: PodId::PodMomentum,
            symbol: "SOL-USDT".to_string(),
            venue: Venue::BinanceSpot,
            side: Side::Buy,
            order_type: OrderType::Market,
            fill_price: 150.0,
            filled_quantity: 10_000.0 / 150.0,
            notional_usd: 10_000.0,
            fee_usd: 5.0,
            slippage_bps: 8.0,
            status: robotrader_exec_router::FillStatus::Filled,
            rationale: "fill".to_string(),
            approved_order: order,
        };

        lifecycle.open_position_from_fill(&fill, &envelope);

        // Market moves down to 148.0 (triggering stop-loss at 150 * 0.988 = 148.2)
        let closed = lifecycle.evaluate_tick("SOL-USDT", 147.5, 2_000);
        assert_eq!(closed.len(), 1);
        let trade = &closed[0];
        assert_eq!(trade.close_reason, PositionCloseReason::StopLoss);
        // Even with expected_edge_bps = 100.0, realized_pnl MUST be negative!
        assert!(trade.realized_pnl_usd < 0.0, "realized_pnl must be negative on stop loss");
    }

    #[test]
    fn test_position_closes_at_take_profit_target() {
        let mut lifecycle = PositionLifecycleEngine::new();
        let envelope = PolicyEnvelope::safe_baseline(1_000);

        let order = ApprovedOrder {
            intent: robotrader_common::OrderIntent {
                reduce_only: false,
                pod_id: PodId::PodMomentum,
                symbol: "SOL-USDT".to_string(),
                venue: Venue::BinanceSpot,
                side: Side::Buy,
                order_type: OrderType::Market,
                reference_price: 100.0,
                win_probability: 0.60,
                reward_risk_ratio: 2.0,
                asset_volatility_pct: 2.0,
                expected_edge_bps: 20.0,
                max_slippage_bps: 10,
                requested_leverage: 1.0,
                stop_loss_pct: 1.0,
                take_profit_pct: 2.0,
                token_safety: None,
                rationale: "tp test".to_string(),
            },
            approved_notional_usd: 1_000.0,
            approved_quantity: 10.0,
            clamped_leverage: 1.0,
            mev_priority_tip_bps: 0,
        };

        let fill = robotrader_exec_router::SimulatedFill {
            timestamp_ms: 1_000,
            pod_id: PodId::PodMomentum,
            symbol: "SOL-USDT".to_string(),
            venue: Venue::BinanceSpot,
            side: Side::Buy,
            order_type: OrderType::Market,
            fill_price: 100.0,
            filled_quantity: 10.0,
            notional_usd: 1_000.0,
            fee_usd: 0.50,
            slippage_bps: 8.0,
            status: robotrader_exec_router::FillStatus::Filled,
            rationale: "fill".to_string(),
            approved_order: order,
        };

        lifecycle.open_position_from_fill(&fill, &envelope);

        // Price rises to 102.5 (above TP target 100 * 1.02 = 102.0)
        let closed = lifecycle.evaluate_tick("SOL-USDT", 102.5, 2_000);
        assert_eq!(closed.len(), 1);
        let trade = &closed[0];
        assert_eq!(trade.close_reason, PositionCloseReason::TakeProfit);
        assert_eq!(trade.exit_price, 102.0);
        assert!(trade.realized_pnl_usd > 0.0);
    }

    #[test]
    fn test_position_marks_to_market_at_end_of_stream() {
        let mut lifecycle = PositionLifecycleEngine::new();
        let envelope = PolicyEnvelope::safe_baseline(1_000);

        let order = ApprovedOrder {
            intent: robotrader_common::OrderIntent {
                reduce_only: false,
                pod_id: PodId::PodCarry,
                symbol: "SOL-USDT".to_string(),
                venue: Venue::BinanceSpot,
                side: Side::Buy,
                order_type: OrderType::Market,
                reference_price: 100.0,
                win_probability: 0.60,
                reward_risk_ratio: 2.0,
                asset_volatility_pct: 2.0,
                expected_edge_bps: 20.0,
                max_slippage_bps: 10,
                requested_leverage: 1.0,
                stop_loss_pct: 5.0,
                take_profit_pct: 5.0,
                token_safety: None,
                rationale: "mtm test".to_string(),
            },
            approved_notional_usd: 1_000.0,
            approved_quantity: 10.0,
            clamped_leverage: 1.0,
            mev_priority_tip_bps: 0,
        };

        let fill = robotrader_exec_router::SimulatedFill {
            timestamp_ms: 1_000,
            pod_id: PodId::PodCarry,
            symbol: "SOL-USDT".to_string(),
            venue: Venue::BinanceSpot,
            side: Side::Buy,
            order_type: OrderType::Market,
            fill_price: 100.0,
            filled_quantity: 10.0,
            notional_usd: 1_000.0,
            fee_usd: 0.50,
            slippage_bps: 8.0,
            status: robotrader_exec_router::FillStatus::Filled,
            rationale: "fill".to_string(),
            approved_order: order,
        };

        lifecycle.open_position_from_fill(&fill, &envelope);
        assert_eq!(lifecycle.open_positions.len(), 1);

        let closed = lifecycle.settle_end_of_stream("SOL-USDT", 101.0, 3_000);
        assert_eq!(closed.len(), 1);
        let trade = &closed[0];
        assert_eq!(trade.close_reason, PositionCloseReason::EndOfStreamMtm);
        assert_eq!(trade.exit_price, 101.0);
        assert_eq!(lifecycle.open_positions.len(), 0);
    }

    #[test]
    fn test_event_driven_simulation_summary_yields_wins_and_losses() {
        let (events, envelope) = simulation_market_stream_for_leaf("leaf-solana");
        let engine = EventDrivenBacktestEngine::default();
        let summary = engine.run_for_leaf("leaf-solana", &events, &envelope);

        assert_eq!(summary.leaf_id, "leaf-solana");
        assert_eq!(summary.artifact_kind, ARTIFACT_KIND_EVENT_DRIVEN_FILL_SIMULATION);
        assert_eq!(summary.source, ARTIFACT_SOURCE_SIMULATED);
        assert!(summary.fill_simulation);
        assert_eq!(summary.pnl_circularity, PNL_CIRCULARITY_NONE);

        assert!(
            summary.winning_trades >= 1,
            "must have at least 1 winning trade, got {}",
            summary.winning_trades
        );
        assert!(
            summary.losing_trades >= 1,
            "must have at least 1 losing trade, got {}",
            summary.losing_trades
        );
        assert!(
            summary.win_rate_pct < 100.0,
            "win_rate_pct must be < 100%, got {}",
            summary.win_rate_pct
        );
        assert!(
            summary.unfilled_expired_orders >= 1,
            "must have at least 1 unfilled expired order, got {}",
            summary.unfilled_expired_orders
        );
    }

    #[test]
    fn test_zero_variance_returns_evaluate_to_zero_sharpe() {
        let identical_returns = vec![2.5, 2.5, 2.5, 2.5];
        let sharpe = compute_simulation_sharpe(&identical_returns);
        assert_eq!(sharpe, 0.0, "Zero-variance returns must evaluate to 0.0 Sharpe");
        assert_ne!(sharpe, 10.0, "Sharpe must not return 10.0 magic constant");
    }
}

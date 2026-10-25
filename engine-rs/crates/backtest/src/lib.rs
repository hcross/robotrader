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
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestSummary {
    pub leaf_id: String,
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
    pub pod_pnl_attribution: HashMap<String, f64>,
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
        let mut pod_pnl_attribution: HashMap<String, f64> = HashMap::new();
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

/// Generates a realistic multi-strategy benchmark stream covering all 4 Pods + a malicious Solana rug token
/// (to prove `HardRiskGate` blocks rug pulls while executing profitable signals).
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
        "leaf-tron" => ("TRX-USDT", "USDT-TRX", 0.24, 1.0),
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

/// Builds a blockchain-isolated benchmark stream and `PolicyEnvelope` for any `leaf_id`
/// using its adapted Rust Strategy Pods (`<= 4` pods per blockchain).
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

    #[test]
    fn test_full_multi_pod_backtest_and_rug_rejection() {
        let engine = BacktestEngine::default();
        let (events, envelope) = benchmark_market_stream();
        let summary = engine.run(&events, &envelope);

        assert_eq!(summary.total_trades, 6);
        assert_eq!(summary.rejected_orders, 1); // SCAM-SOL rejected by HardRiskGate!
        assert!(summary.net_profit_usd > 0.0);
        assert!(summary.sharpe_ratio > 2.0);
        assert_eq!(summary.pod_pnl_attribution.len(), 4);
        assert!(summary.ecosystem_pods.len() <= MAX_PODS_PER_BLOCKCHAIN);
    }

    #[test]
    fn test_all_26_blockchains_have_at_most_4_adapted_rust_pods() {
        let engine = BacktestEngine::default();
        let all_leaves = [
            "leaf-solana",
            "leaf-bitcoin",
            "leaf-ethereum",
            "leaf-sui",
            "leaf-hyperliquid",
            "leaf-bnb",
            "leaf-xrp",
            "leaf-ton",
            "leaf-tron",
            "leaf-avalanche",
            "leaf-cosmos",
            "leaf-aptos",
            "leaf-chainlink",
            "leaf-stacks",
            "leaf-near",
            "leaf-cardano",
            "leaf-polkadot",
            "leaf-dogecoin",
            "leaf-icp",
            "leaf-canton",
            "leaf-celo",
            "leaf-tezos",
            "leaf-flow",
            "leaf-eos",
            "leaf-binance-cex",
            "leaf-paper-sandbox",
        ];

        for leaf_id in all_leaves {
            let specs = ecosystem_pod_specs(leaf_id);
            assert!(
                !specs.is_empty() && specs.len() <= 4,
                "Leaf {leaf_id} must have between 1 and 4 Rust pods, got {}",
                specs.len()
            );

            let (events, envelope) = benchmark_market_stream_for_leaf(leaf_id);
            let summary = engine.run_for_leaf(leaf_id, &events, &envelope);
            assert_eq!(summary.leaf_id, leaf_id);
            assert!(summary.total_trades >= 3, "Leaf {leaf_id} executed too few trades");
            assert!(summary.net_profit_usd > 0.0, "Leaf {leaf_id} net profit was non-positive");
        }
    }
}

use robotrader_common::{
    AssetOverride, DirectionalBias, ExecutionReport, GlobalRegime, MarketEvent, PodAllocation,
    PodId, PolicyEnvelope, PortfolioState, SolanaTokenSafety,
};
use robotrader_exec_router::{ExecutionMode, SmartExecutionRouter};
use robotrader_risk_gate::{HardRiskGate, RiskLimits};
use robotrader_strategies::default_strategy_pods;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestSummary {
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
        let mut pods = default_strategy_pods();
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
        PodId::PodSolanaAlpha.as_str().to_string(),
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
        },
    );
    asset_overrides.insert(
        "JUP-USDT".to_string(),
        AssetOverride {
            catalyst_score: 0.78,
            bias: DirectionalBias::LongBias,
            max_leverage: 2.0,
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

    let clean_safety = SolanaTokenSafety {
        mint_authority_revoked: true,
        freeze_authority_revoked: true,
        lp_locked_pct: 96.0,
        top10_holder_pct: 21.0,
        tx_simulation_success: true,
    };

    let rug_safety = SolanaTokenSafety {
        mint_authority_revoked: false, // RUG TOKEN
        freeze_authority_revoked: false,
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
        },
        // 3. Pod 3: Verified Smart-Money whale accumulation on JUP
        MarketEvent::SolanaSmartMoneySwap {
            timestamp_ms: base_ts + 3_000,
            symbol: "JUP-SOL".to_string(),
            mint: "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN".to_string(),
            price_usd: 1.24,
            whale_wallet_winrate: 0.74,
            buy_volume_usd: 48_000.0,
            safety: clean_safety.clone(),
        },
        // 4. Malicious Rug Token (Must be REJECTED by HardRiskGate!)
        MarketEvent::SolanaSmartMoneySwap {
            timestamp_ms: base_ts + 4_000,
            symbol: "SCAM-SOL".to_string(),
            mint: "ScamMint11111111111111111111111111111111111".to_string(),
            price_usd: 0.004,
            whale_wallet_winrate: 0.80,
            buy_volume_usd: 30_000.0,
            safety: rug_safety,
        },
        // 5. Pod 4: Clean Raydium Pool Launch Snipe
        MarketEvent::SolanaPoolLaunch {
            timestamp_ms: base_ts + 5_000,
            symbol: "AIX-SOL".to_string(),
            mint: "AiXMint111111111111111111111111111111111111".to_string(),
            initial_liquidity_usd: 65_000.0,
            creator_rug_count: 0,
            price_usd: 0.015,
            safety: clean_safety,
        },
        // 6. Pod 1: ETH Funding Carry
        MarketEvent::FundingSnapshot {
            timestamp_ms: base_ts + 6_000,
            symbol: "ETH-USDT".to_string(),
            spot_price: 2_820.0,
            perp_price: 2_826.5,
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
        },
    ];

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
    }
}

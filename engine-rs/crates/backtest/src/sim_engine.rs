use crate::leaf_market_profile;
use crate::position::{ClosedPosition, PositionCloseReason, PositionLifecycleEngine};
use robotrader_common::{
    fee_bps_for, AssetOverride, DirectionalBias, GlobalRegime, MarketEvent, OnChainTokenSafety,
    OrderType, PodAllocation, PolicyEnvelope, PortfolioState, Side,
};
use robotrader_exec_router::{EventDrivenFillSimulator, FillStatus};
use robotrader_risk_gate::{HardRiskGate, RiskLimits};
use robotrader_strategies::{
    ecosystem_pod_specs, strategy_pods_for_leaf, MAX_PODS_PER_BLOCKCHAIN,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const ARTIFACT_KIND_EVENT_DRIVEN_FILL_SIMULATION: &str = "event_driven_fill_simulation";
pub const ARTIFACT_SOURCE_SIMULATED: &str = "SIMULATED";
pub const PNL_CIRCULARITY_NONE: &str = "NONE_PRICE_PATH_DERIVED";

/// Structured report of an event-driven fill simulation run.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventDrivenSimulationSummary {
    pub leaf_id: String,
    pub artifact_kind: String,
    pub source: String,
    pub fill_simulation: bool,
    pub pnl_circularity: String,
    pub initial_equity_usd: f64,
    pub final_equity_usd: f64,
    pub net_profit_usd: f64,
    pub total_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub sharpe_ratio: f64,
    pub win_rate_pct: f64,
    pub total_orders: usize,
    pub filled_orders: usize,
    pub unfilled_expired_orders: usize,
    pub rejected_orders: usize,
    pub winning_trades: usize,
    pub losing_trades: usize,
    pub total_fees_usd: f64,
    pub trade_executions: Vec<ClosedPosition>,
}

/// Unbiased Sharpe ratio calculation over period returns.
/// Evaluates to `0.0` when return variance is zero or sample size < 2.
pub fn compute_simulation_sharpe(returns: &[f64]) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }
    let n = returns.len() as f64;
    let mean = returns.iter().sum::<f64>() / n;
    let variance = returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / (n - 1.0);
    let std_dev = variance.sqrt();
    if std_dev <= 1e-9 {
        return 0.0;
    }
    (mean / std_dev) * (365.0_f64).sqrt()
}

pub struct EventDrivenBacktestEngine {
    pub initial_equity_usd: f64,
    pub risk_limits: RiskLimits,
}

impl Default for EventDrivenBacktestEngine {
    fn default() -> Self {
        Self {
            initial_equity_usd: 10_000.0,
            risk_limits: RiskLimits::default(),
        }
    }
}

impl EventDrivenBacktestEngine {
    pub fn new(initial_equity_usd: f64, risk_limits: RiskLimits) -> Self {
        Self {
            initial_equity_usd,
            risk_limits,
        }
    }

    /// Executes the event-driven fill simulation across sequential market events.
    pub fn run_for_leaf(
        &self,
        leaf_id: &str,
        events: &[MarketEvent],
        envelope: &PolicyEnvelope,
    ) -> EventDrivenSimulationSummary {
        let mut pods = strategy_pods_for_leaf(leaf_id);
        pods.truncate(MAX_PODS_PER_BLOCKCHAIN);
        let mut gate = HardRiskGate::new(self.risk_limits.clone());
        let mut fill_sim = EventDrivenFillSimulator::new();
        let mut lifecycle = PositionLifecycleEngine::new();
        let mut portfolio = PortfolioState::new(self.initial_equity_usd);

        let mut total_orders = 0usize;
        let mut filled_orders = 0usize;
        let mut unfilled_expired_orders = 0usize;
        let mut rejected_orders = 0usize;
        let mut trade_executions: Vec<ClosedPosition> = Vec::new();
        let mut trade_returns_pct: Vec<f64> = Vec::new();
        let mut max_dd_seen_pct = 0.0f64;

        for event in events {
            let ts = event.timestamp_ms();
            let sym = event.symbol();
            let mark_px = event.mark_price();

            // 1. Process pending resting orders against this new event
            let resting_fills = fill_sim.process_market_event(event);
            for fill in resting_fills {
                match fill.status {
                    FillStatus::Filled => {
                        filled_orders += 1;
                        lifecycle.open_position_from_fill(&fill, envelope);
                    }
                    FillStatus::UnfilledExpired => {
                        unfilled_expired_orders += 1;
                    }
                    _ => {}
                }
            }

            // 2. Evaluate open positions against this event for TP / SL triggers
            let closed_positions = lifecycle.evaluate_tick(sym, mark_px, ts);
            for closed in closed_positions {
                let equity_before = portfolio.current_equity_usd;
                portfolio.apply_pnl(closed.realized_pnl_usd);
                max_dd_seen_pct = max_dd_seen_pct.max(portfolio.max_drawdown_pct());

                let ret_pct = (closed.realized_pnl_usd / equity_before) * 100.0;
                trade_returns_pct.push(ret_pct);
                trade_executions.push(closed);
            }

            // 3. Emit intents from strategy pods on this market event
            for pod in pods.iter_mut() {
                let intents = pod.on_market_event(event, envelope);
                for intent in intents {
                    total_orders += 1;
                    match gate.validate(&intent, &portfolio, envelope, ts) {
                        Ok(approved) => {
                            if let Some(immediate_fill) =
                                fill_sim.submit_order(approved, event)
                            {
                                match immediate_fill.status {
                                    FillStatus::Filled => {
                                        filled_orders += 1;
                                        lifecycle
                                            .open_position_from_fill(&immediate_fill, envelope);
                                    }
                                    FillStatus::UnfilledExpired => {
                                        unfilled_expired_orders += 1;
                                    }
                                    _ => {}
                                }
                            }
                        }
                        Err(_) => {
                            rejected_orders += 1;
                        }
                    }
                }
            }
        }

        // 4. End of stream: mark-to-market any remaining active positions
        if let Some(last_event) = events.last() {
            let final_closed = lifecycle.settle_end_of_stream(
                last_event.symbol(),
                last_event.mark_price(),
                last_event.timestamp_ms(),
            );
            for closed in final_closed {
                let equity_before = portfolio.current_equity_usd;
                portfolio.apply_pnl(closed.realized_pnl_usd);
                max_dd_seen_pct = max_dd_seen_pct.max(portfolio.max_drawdown_pct());

                let ret_pct = (closed.realized_pnl_usd / equity_before) * 100.0;
                trade_returns_pct.push(ret_pct);
                trade_executions.push(closed);
            }
        }

        // Drain any remaining positions on other symbols
        if !lifecycle.open_positions.is_empty() {
            for pos in lifecycle.open_positions.drain(..) {
                let exit_fee_bps = fee_bps_for(pos.venue, OrderType::Market);
                let exit_fee_usd = (pos.entry_price * pos.quantity) * (exit_fee_bps / 10_000.0);
                let _direction = match pos.side {
                    Side::Buy => 1.0,
                    Side::Sell => -1.0,
                };
                let gross_pnl_usd = 0.0;
                let realized_pnl_usd = gross_pnl_usd - pos.entry_fee_usd - exit_fee_usd;
                portfolio.apply_pnl(realized_pnl_usd);
                max_dd_seen_pct = max_dd_seen_pct.max(portfolio.max_drawdown_pct());
                trade_executions.push(ClosedPosition {
                    trade_id: pos.position_id,
                    pod_id: pos.pod_id,
                    symbol: pos.symbol,
                    venue: pos.venue,
                    side: pos.side,
                    entry_price: pos.entry_price,
                    exit_price: pos.entry_price,
                    quantity: pos.quantity,
                    entry_fee_usd: pos.entry_fee_usd,
                    exit_fee_usd,
                    gross_pnl_usd,
                    realized_pnl_usd,
                    close_reason: PositionCloseReason::EndOfStreamMtm,
                    holding_duration_ticks: pos.open_duration_ticks + 1,
                });
            }
        }

        // Unfilled resting orders expire
        unfilled_expired_orders += fill_sim.resting_orders.len();
        fill_sim.resting_orders.clear();

        let winning_trades = trade_executions
            .iter()
            .filter(|t| t.realized_pnl_usd > 0.0)
            .count();
        let losing_trades = trade_executions
            .iter()
            .filter(|t| t.realized_pnl_usd < 0.0)
            .count();
        let total_trades = trade_executions.len();
        let win_rate_pct = if total_trades > 0 {
            (winning_trades as f64 / total_trades as f64) * 100.0
        } else {
            0.0
        };

        let total_fees_usd: f64 = trade_executions
            .iter()
            .map(|t| t.entry_fee_usd + t.exit_fee_usd)
            .sum();
        let net_profit_usd = portfolio.current_equity_usd - self.initial_equity_usd;
        let total_return_pct = (net_profit_usd / self.initial_equity_usd) * 100.0;
        let sharpe_ratio = compute_simulation_sharpe(&trade_returns_pct);

        EventDrivenSimulationSummary {
            leaf_id: leaf_id.to_string(),
            artifact_kind: ARTIFACT_KIND_EVENT_DRIVEN_FILL_SIMULATION.to_string(),
            source: ARTIFACT_SOURCE_SIMULATED.to_string(),
            fill_simulation: true,
            pnl_circularity: PNL_CIRCULARITY_NONE.to_string(),
            initial_equity_usd: self.initial_equity_usd,
            final_equity_usd: portfolio.current_equity_usd,
            net_profit_usd,
            total_return_pct,
            max_drawdown_pct: max_dd_seen_pct,
            sharpe_ratio,
            win_rate_pct,
            total_orders,
            filled_orders,
            unfilled_expired_orders,
            rejected_orders,
            winning_trades,
            losing_trades,
            total_fees_usd,
            trade_executions,
        }
    }
}

/// Generates a multi-tick event stream for any leaf ecosystem featuring both
/// winning and losing trades under realistic market price paths.
pub fn simulation_market_stream_for_leaf(leaf_id: &str) -> (Vec<MarketEvent>, PolicyEnvelope) {
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
            catalyst_score: 0.85,
            bias: DirectionalBias::LongBias,
            max_leverage: 2.0,
            support_zone_usd: None,
            resistance_zone_usd: None,
            invalidation_price_usd: None,
            entry_obi_threshold: None,
            max_rsi_long: None,
            min_rsi_short: None,
            take_profit_bps: Some(250.0), // +2.5%
            stop_loss_bps: Some(120.0),   // -1.2%
        },
    );
    asset_overrides.insert(
        secondary_sym.to_string(),
        AssetOverride {
            catalyst_score: 0.80,
            bias: DirectionalBias::LongBias,
            max_leverage: 2.0,
            support_zone_usd: None,
            resistance_zone_usd: None,
            invalidation_price_usd: None,
            entry_obi_threshold: None,
            max_rsi_long: None,
            min_rsi_short: None,
            take_profit_bps: Some(200.0), // +2.0%
            stop_loss_bps: Some(100.0),   // -1.0%
        },
    );

    let envelope = PolicyEnvelope {
        envelope_id: format!("sim_env_{leaf_id}"),
        issued_at_ms: base_ts,
        ttl_seconds: 7_200,
        global_regime: GlobalRegime::RiskOnHighVol,
        pod_allocations,
        asset_overrides,
    };

    let clean_safety = OnChainTokenSafety {
        supply_mint_immutable: true,
        transfer_freeze_disabled: true,
        no_honeypot_or_transfer_tax: true,
        lp_locked_pct: 95.0,
        top10_holder_pct: 18.0,
        tx_simulation_success: true,
    };

    let events = vec![
        // 1. Pod 2 (Momentum): Breakout entry at primary_px -> Places maker order resting at primary_px
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 1_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px,
            bid_volume_top5: 6_000.0,
            ask_volume_top5: 2_000.0,
            cvd_delta: 500_000.0,
            atr_pct: 2.0,
            breakout_zscore: 2.50,
            rsi_14: None,
        },
        // 2. Market price crosses resting bid (0.9995 <= 1.0) -> Maker order fills at primary_px
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 2_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px * 0.9995,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 2.0,
            breakout_zscore: 0.0,
            rsi_14: None,
        },
        // 3. Price surges +3.0% (1.030 >= 1.025) -> Triggers TakeProfit on Position 1 (WINNING TRADE #1)
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 3_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px * 1.030,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 2.0,
            breakout_zscore: 0.0,
            rsi_14: None,
        },
        // 4. Second breakout entry at primary_px * 1.030 -> Places maker order resting at 1.030
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 4_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px * 1.030,
            bid_volume_top5: 6_000.0,
            ask_volume_top5: 2_000.0,
            cvd_delta: 450_000.0,
            atr_pct: 2.0,
            breakout_zscore: 2.40,
            rsi_14: None,
        },
        // 5. Market price crosses resting bid (1.029 <= 1.030) -> Maker order fills at 1.030
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 5_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px * 1.029,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 2.0,
            breakout_zscore: 0.0,
            rsi_14: None,
        },
        // 6. Sudden sharp adverse drop to 1.010 (<= 1.0176 SL level) -> Triggers StopLoss on Position 2 (LOSING TRADE #1)
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 6_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px * 1.010,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 2.0,
            breakout_zscore: 0.0,
            rsi_14: None,
        },
        // 7. Pod 1 (Carry) basis opportunity -> Emits sell maker order resting at perp_price (~primary_px * 1.0125)
        MarketEvent::FundingSnapshot {
            timestamp_ms: base_ts + 7_000,
            symbol: primary_sym.to_string(),
            spot_price: primary_px * 1.010,
            perp_price: primary_px * 1.010 * 1.0025,
            annualized_funding_apr: 0.25,
        },
        // 8. Price drops downward to 0.990 (>50 bps below sell ask) -> Maker order expires UNFILLED_EXPIRED
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 8_000,
            symbol: primary_sym.to_string(),
            mid_price: primary_px * 0.990,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        },
        // 9. Pod 3 (Onchain Alpha): whale accumulation on secondary pair -> Fills immediately
        MarketEvent::OnchainSmartMoneySwap {
            timestamp_ms: base_ts + 9_000,
            symbol: secondary_sym.to_string(),
            token_address: format!("SimPool::{leaf_id}"),
            price_usd: secondary_px,
            whale_wallet_winrate: 0.75,
            buy_volume_usd: 48_000.0,
            safety: clean_safety,
        },
        // 10. Final tick on secondary pair -> Settles Position 3 at END_OF_STREAM_MTM
        MarketEvent::OrderbookTick {
            timestamp_ms: base_ts + 10_000,
            symbol: secondary_sym.to_string(),
            mid_price: secondary_px * 1.004,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        },
    ];

    (events, envelope)
}

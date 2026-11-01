use robotrader_common::{
    fee_bps_for, spread_bps_for, ApprovedOrder, ExecutionReport, OrderType, Side, Venue,
};
use serde::{Deserialize, Serialize};

pub mod fill_sim;
pub use fill_sim::{
    extract_available_liquidity, extract_obi, EventDrivenFillSimulator, FillStatus, RestingOrder,
    SimulatedFill,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ExecutionMode {
    Backtest,
    Paper,
    Live,
}

pub struct SmartExecutionRouter {
    pub mode: ExecutionMode,
}

impl SmartExecutionRouter {
    pub fn new(mode: ExecutionMode) -> Self {
        Self { mode }
    }

    /// Per-side fee in basis points, delegated to the canonical cost model.
    pub fn fee_bps_for(&self, venue: Venue, order_type: OrderType) -> f64 {
        fee_bps_for(venue, order_type)
    }

    /// Spread component in basis points, delegated to the canonical cost model.
    pub fn slippage_bps_for(&self, order: &ApprovedOrder) -> f64 {
        spread_bps_for(order.intent.order_type, order.mev_priority_tip_bps)
    }

    /// Executes an approved order and returns a deterministic `ExecutionReport`
    /// for the policy sanity check fixture.
    ///
    /// `realized_pnl_usd` here is **declared-edge arithmetic** — the intent's
    /// `expected_edge_bps` minus the modelled round-trip fee and modelled
    /// spread, applied to the approved notional. It is not a market outcome:
    /// no later `MarketEvent` prices an exit, and no fill probability, queue
    /// position, latency, partial fill, or adverse selection is simulated. A
    /// real fill simulator remains issue #3.
    pub fn execute(&self, order: &ApprovedOrder, timestamp_ms: u64) -> ExecutionReport {
        let round_trip_fee_bps =
            self.fee_bps_for(order.intent.venue, order.intent.order_type) * 2.0;
        let realized_slippage_bps = self.slippage_bps_for(order);

        let price_adjustment = match order.intent.side {
            Side::Buy => 1.0 + (realized_slippage_bps / 10_000.0),
            Side::Sell => 1.0 - (realized_slippage_bps / 10_000.0),
        };
        let fill_price = order.intent.reference_price * price_adjustment;

        let fee_usd = order.approved_notional_usd * (round_trip_fee_bps / 10_000.0);
        // Declared-edge arithmetic for the fixture; not a market-derived PnL.
        let net_edge_bps =
            order.intent.expected_edge_bps - round_trip_fee_bps - realized_slippage_bps;
        let realized_pnl_usd = order.approved_notional_usd * (net_edge_bps / 10_000.0);

        ExecutionReport {
            timestamp_ms,
            pod_id: order.intent.pod_id,
            symbol: order.intent.symbol.clone(),
            venue: order.intent.venue,
            side: order.intent.side,
            filled_quantity: order.approved_quantity,
            fill_price,
            notional_usd: order.approved_notional_usd,
            fee_usd,
            realized_slippage_bps,
            expected_edge_bps: order.intent.expected_edge_bps,
            realized_pnl_usd,
            rationale: order.intent.rationale.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use robotrader_common::{fee_bps_for, spread_bps_for, MarketEvent, OrderIntent, PodId};

    const ALL_VENUES: [Venue; 5] = [
        Venue::BinanceSpot,
        Venue::BinancePerp,
        Venue::HyperliquidPerp,
        Venue::OnchainDexAggregator,
        Venue::OnchainAtomicPool,
    ];
    const ALL_ORDER_TYPES: [OrderType; 4] = [
        OrderType::PostOnlyMaker,
        OrderType::Limit,
        OrderType::Market,
        OrderType::MevBundleAtomic,
    ];

    fn approved_order(venue: Venue, order_type: OrderType, tip_bps: u32) -> ApprovedOrder {
        ApprovedOrder {
            intent: OrderIntent {
                pod_id: PodId::PodCarry,
                symbol: "SOL-USDT".to_string(),
                venue,
                side: Side::Buy,
                order_type,
                reference_price: 150.0,
                win_probability: 0.68,
                reward_risk_ratio: 2.2,
                asset_volatility_pct: 2.0,
                expected_edge_bps: 12.0,
                max_slippage_bps: 2,
                requested_leverage: 1.0,
                stop_loss_pct: 1.2,
                take_profit_pct: 2.6,
                token_safety: None,
                rationale: "parity fixture".to_string(),
            },
            approved_notional_usd: 10_000.0,
            approved_quantity: 10_000.0 / 150.0,
            clamped_leverage: 1.0,
            mev_priority_tip_bps: tip_bps,
        }
    }

    #[test]
    fn test_fee_bps_delegates_to_the_canonical_table_for_every_pair() {
        let router = SmartExecutionRouter::new(ExecutionMode::Backtest);
        for venue in ALL_VENUES {
            for order_type in ALL_ORDER_TYPES {
                assert_eq!(
                    router.fee_bps_for(venue, order_type),
                    fee_bps_for(venue, order_type),
                    "fee divergence for {venue:?}/{order_type:?}"
                );
            }
        }
    }

    #[test]
    fn test_slippage_bps_delegates_to_the_canonical_table_for_all_order_types() {
        let router = SmartExecutionRouter::new(ExecutionMode::Backtest);
        let expected = [
            (OrderType::PostOnlyMaker, 0.5),
            (OrderType::Limit, 2.0),
            (OrderType::Market, 8.0),
            (OrderType::MevBundleAtomic, 6.0),
        ];

        for (order_type, expected_bps) in expected {
            let order = approved_order(Venue::BinancePerp, order_type, 10);
            assert_eq!(
                router.slippage_bps_for(&order),
                expected_bps,
                "spread divergence for {order_type:?}"
            );
            assert_eq!(
                router.slippage_bps_for(&order),
                spread_bps_for(order_type, 10),
                "router and canonical spread helper disagree for {order_type:?}"
            );
        }
    }

    #[test]
    fn test_execute_charges_the_round_trip_fee_for_binance_maker() {
        let router = SmartExecutionRouter::new(ExecutionMode::Backtest);
        let order = approved_order(Venue::BinancePerp, OrderType::PostOnlyMaker, 2);
        let report = router.execute(&order, 1_000);

        let charged_bps = report.fee_usd / report.notional_usd * 10_000.0;
        assert!((charged_bps - 3.6).abs() < 1e-9, "charged {charged_bps} bps");
    }

    #[test]
    fn test_maker_order_fills_on_crossing_price_tick() {
        let mut sim = EventDrivenFillSimulator::new();
        let order = approved_order(Venue::BinancePerp, OrderType::PostOnlyMaker, 0);
        let entry_event = MarketEvent::OrderbookTick {
            timestamp_ms: 1_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 150.0,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        };

        // Submitting maker order returns None and places it into resting queue
        let immediate = sim.submit_order(order, &entry_event);
        assert!(immediate.is_none());
        assert_eq!(sim.resting_orders.len(), 1);

        // Subsequent tick with matching ask liquidity touches resting price (150.0) with neutral OBI
        let match_event = MarketEvent::OrderbookTick {
            timestamp_ms: 2_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 149.9,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        };

        let fills = sim.process_market_event(&match_event);
        assert_eq!(fills.len(), 1);
        let fill = &fills[0];
        assert_eq!(fill.status, FillStatus::Filled);
        assert_eq!(fill.fill_price, 150.0);
        assert_eq!(fill.filled_quantity, 10_000.0 / 150.0);
        // Maker fee for BinancePerp is 1.8 bps
        assert_eq!(fill.fee_usd, 10_000.0 * (1.8 / 10_000.0));
        assert_eq!(sim.resting_orders.len(), 0);
    }

    #[test]
    fn test_maker_queue_starvation_blocks_fill_under_adverse_imbalance() {
        let mut sim = EventDrivenFillSimulator::new();
        let order = approved_order(Venue::BinancePerp, OrderType::PostOnlyMaker, 0);
        let entry_event = MarketEvent::OrderbookTick {
            timestamp_ms: 1_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 150.0,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        };

        sim.submit_order(order, &entry_event);

        // Price crosses (149.8 <= 150.0), but severe sell imbalance (OBI = (100 - 900) / 1000 = -0.80 < -0.70)
        let starved_event = MarketEvent::OrderbookTick {
            timestamp_ms: 2_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 149.8,
            bid_volume_top5: 100.0,
            ask_volume_top5: 900.0,
            cvd_delta: -50_000.0,
            atr_pct: 1.5,
            breakout_zscore: -2.0,
            rsi_14: None,
        };

        let fills = sim.process_market_event(&starved_event);
        // Starved: no fill produced, remains in resting queue
        assert_eq!(fills.len(), 0);
        assert_eq!(sim.resting_orders.len(), 1);
    }

    #[test]
    fn test_maker_order_expires_unfilled_during_adverse_divergence_with_zero_fee() {
        let mut sim = EventDrivenFillSimulator::new();
        let order = approved_order(Venue::BinancePerp, OrderType::PostOnlyMaker, 0);
        let entry_event = MarketEvent::OrderbookTick {
            timestamp_ms: 1_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 150.0,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        };

        sim.submit_order(order, &entry_event);

        // Market price diverges upwards by > 50 bps (150.0 * 1.006 = 150.9)
        let divergent_event = MarketEvent::OrderbookTick {
            timestamp_ms: 2_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 151.0,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 20_000.0,
            atr_pct: 1.5,
            breakout_zscore: 1.8,
            rsi_14: None,
        };

        let fills = sim.process_market_event(&divergent_event);
        assert_eq!(fills.len(), 1);
        let fill = &fills[0];
        assert_eq!(fill.status, FillStatus::UnfilledExpired);
        assert_eq!(fill.filled_quantity, 0.0);
        assert_eq!(fill.notional_usd, 0.0);
        assert_eq!(fill.fee_usd, 0.0);
        assert_eq!(sim.resting_orders.len(), 0);
    }

    #[test]
    fn test_limit_order_fills_with_adverse_selection_when_market_trades_through() {
        let mut sim = EventDrivenFillSimulator::new();
        let order = approved_order(Venue::BinanceSpot, OrderType::Limit, 0);
        let entry_event = MarketEvent::OrderbookTick {
            timestamp_ms: 1_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 150.0,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        };

        sim.submit_order(order, &entry_event);

        // Market trades through limit price (149.0 < 150.0)
        let trade_through_event = MarketEvent::OrderbookTick {
            timestamp_ms: 2_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 149.0,
            bid_volume_top5: 5_000.0,
            ask_volume_top5: 5_000.0,
            cvd_delta: -10_000.0,
            atr_pct: 1.5,
            breakout_zscore: -1.0,
            rsi_14: None,
        };

        let fills = sim.process_market_event(&trade_through_event);
        assert_eq!(fills.len(), 1);
        let fill = &fills[0];
        assert_eq!(fill.status, FillStatus::Filled);
        // Limit adverse selection for Buy is +2.0 bps over limit price
        let expected_fill_px = 150.0 * (1.0 + 2.0 / 10_000.0);
        assert!((fill.fill_price - expected_fill_px).abs() < 1e-9);
        assert_eq!(fill.fee_usd, 10_000.0 * (5.0 / 10_000.0));
    }

    #[test]
    fn test_taker_order_executes_with_spread_and_depth_impact() {
        let sim = EventDrivenFillSimulator::new();
        let order = approved_order(Venue::BinancePerp, OrderType::Market, 0);
        // Available liquidity = (200 + 200) * 0.5 * 150 = $30,000.
        // Order notional = $10,000.
        // Depth impact = 5.0 * (10_000 / 30_000) = 1.6667 bps (capped at max_slippage_bps = 2.0 bps)
        // Canonical market spread = 8.0 bps
        // Total slippage = 8.0 + 1.6667 = 9.6667 bps
        let event = MarketEvent::OrderbookTick {
            timestamp_ms: 1_000,
            symbol: "SOL-USDT".to_string(),
            mid_price: 150.0,
            bid_volume_top5: 200.0,
            ask_volume_top5: 200.0,
            cvd_delta: 0.0,
            atr_pct: 1.5,
            breakout_zscore: 0.0,
            rsi_14: None,
        };

        let fill = sim.execute_taker(&order, &event);
        assert_eq!(fill.status, FillStatus::Filled);
        let expected_slippage_bps = 8.0 + (5.0 * (10_000.0 / 30_000.0));
        assert!((fill.slippage_bps - expected_slippage_bps).abs() < 1e-9);
        let expected_fill_price = 150.0 * (1.0 + expected_slippage_bps / 10_000.0);
        assert!((fill.fill_price - expected_fill_price).abs() < 1e-9);
    }
}

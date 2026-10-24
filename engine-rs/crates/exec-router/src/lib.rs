use robotrader_common::{ApprovedOrder, ExecutionReport, OrderType, Side, Venue};
use serde::{Deserialize, Serialize};

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

    pub fn fee_bps_for(&self, venue: Venue, order_type: OrderType) -> f64 {
        match (venue, order_type) {
            // Post-Only Maker on CEX drastically reduces fee drag (1.5 to 2.0 bps vs 5-10 bps taker)
            (Venue::BinanceSpot | Venue::BinancePerp, OrderType::PostOnlyMaker) => 1.8,
            (Venue::HyperliquidPerp, OrderType::PostOnlyMaker) => 1.0,
            (Venue::BinanceSpot | Venue::BinancePerp | Venue::HyperliquidPerp, _) => 5.0,
            // On-chain DEX aggregator + MEV bundle fee + priority tip
            (Venue::OnchainDexAggregator, _) => 8.0,
            (Venue::OnchainAtomicPool, _) => 12.0,
        }
    }

    pub fn slippage_bps_for(&self, order: &ApprovedOrder) -> f64 {
        match order.intent.order_type {
            OrderType::PostOnlyMaker => 0.5, // Maker fills capture spread
            OrderType::Limit => 2.0,
            OrderType::Market => 8.0,
            OrderType::MevBundleAtomic => (order.mev_priority_tip_bps as f64) * 0.6,
        }
    }

    /// Executes an approved order and returns a deterministic `ExecutionReport`.
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

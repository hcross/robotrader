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

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BitcoinBridgeQuote {
    pub venues: Vec<String>,
    pub supported_tokens: Vec<String>,
    pub bridge_protocol: String,
    pub base_fee_usd: f64,
    pub variable_bps: f64,
    pub one_way_fee_usd: f64,
    pub round_trip_cost_bps: f64,
    pub hurdle_rate_bps: f64,
    pub finality_sec: u64,
}

pub struct BitcoinVenueAdapter;

impl BitcoinVenueAdapter {
    pub const VENUES: [&'static str; 3] = [
        "Bitcoin L1 Native",
        "ThorChain Native Pool",
        "Lightning Liquidity",
    ];
    pub const SUPPORTED_TOKENS: [&'static str; 3] = ["BTC", "USDT", "USDC"];
    pub const BRIDGE_PROTOCOL: &'static str = "ThorChain / wBTC Institutional";
    pub const BASE_FEE_USD: f64 = 3.50;
    pub const VARIABLE_BPS: f64 = 12.0;
    pub const FINALITY_SEC: u64 = 600;

    pub fn quote_bridge(notional_usd: f64) -> BitcoinBridgeQuote {
        let one_way_fee_usd = Self::BASE_FEE_USD + notional_usd * (Self::VARIABLE_BPS / 10_000.0);
        // Round trip cost in basis points: one-way cost expressed in bps of notional multiplied by 2 (or total round trip percentage)
        // Usually round trip cost bps = (one_way_fee_usd / notional_usd * 10_000.0) * 2.0 or similar. Let's compute precisely:
        // Or variable_bps * 2 + (base_fee / notional * 10_000) * 2.
        let one_way_bps = if notional_usd > 0.0 {
            (one_way_fee_usd / notional_usd) * 10_000.0
        } else {
            Self::VARIABLE_BPS
        };
        let round_trip_cost_bps = one_way_bps * 2.0;
        let hurdle_rate_bps = round_trip_cost_bps * 2.5;

        BitcoinBridgeQuote {
            venues: Self::VENUES.iter().map(|s| s.to_string()).collect(),
            supported_tokens: Self::SUPPORTED_TOKENS.iter().map(|s| s.to_string()).collect(),
            bridge_protocol: Self::BRIDGE_PROTOCOL.to_string(),
            base_fee_usd: Self::BASE_FEE_USD,
            variable_bps: Self::VARIABLE_BPS,
            one_way_fee_usd,
            round_trip_cost_bps,
            hurdle_rate_bps,
            finality_sec: Self::FINALITY_SEC,
        }
    }

    pub fn validate_settlement_destination(dest: &str) -> bool {
        if dest.starts_with("bridge:thorchain:") {
            return dest.len() > "bridge:thorchain:".len();
        }

        // Native Bitcoin Bech32 SegWit (bc1q...) or Taproot (bc1p...)
        // length 42..=62, lowercase alphanumeric without '1', 'b', 'i', 'o' after 'bc1' (or simply valid bech32 charset)
        if dest.starts_with("bc1q") || dest.starts_with("bc1p") {
            if dest.len() < 42 || dest.len() > 62 {
                return false;
            }
            let prefix = &dest[0..4];
            let rest = &dest[4..];
            if prefix != "bc1q" && prefix != "bc1p" {
                return false;
            }
            // Check alphanumeric and exclusion of '1', 'b', 'i', 'o' in rest
            for c in rest.chars() {
                if !c.is_ascii_alphanumeric() {
                    return false;
                }
                if c == '1' || c == 'b' || c == 'i' || c == 'o' || c.is_ascii_uppercase() {
                    return false;
                }
            }
            return true;
        }

        false
    }
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

    pub fn execute_for_leaf(
        &self,
        leaf_id: &str,
        order: &ApprovedOrder,
        timestamp_ms: u64,
    ) -> Result<ExecutionReport, String> {
        if leaf_id == "leaf-bitcoin" {
            let sym = &order.intent.symbol;
            if sym != "BTC-USD" && sym != "wBTC-BTC" && sym != "sBTC-BTC" {
                return Err(format!(
                    "Leaf leaf-bitcoin violates symbol isolation: symbol {sym} not allowed"
                ));
            }
        }
        Ok(self.execute(order, timestamp_ms))
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
                reduce_only: false,
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

        let immediate = sim.submit_order(order, &entry_event);
        assert!(immediate.is_none());
        assert_eq!(sim.resting_orders.len(), 1);

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
        assert_eq!(fill.fee_usd, 10_000.0 * (1.8 / 10_000.0));
        assert_eq!(sim.resting_orders.len(), 0);
    }

    #[test]
    fn test_bitcoin_venue_adapter_bridge_quote_and_custody_destination() {
        let quote = BitcoinVenueAdapter::quote_bridge(10_000.0);
        assert_eq!(quote.venues.len(), 3);
        assert!(quote.venues.contains(&"Bitcoin L1 Native".to_string()));
        assert_eq!(quote.bridge_protocol, "ThorChain / wBTC Institutional");
        assert_eq!(quote.base_fee_usd, 3.50);
        assert_eq!(quote.variable_bps, 12.0);
        assert!((quote.one_way_fee_usd - (3.50 + 10_000.0 * 12.0 / 10_000.0)).abs() < 1e-9);
        assert!(quote.hurdle_rate_bps > quote.round_trip_cost_bps);
        assert_eq!(quote.finality_sec, 600);

        // Test destination validation
        assert!(BitcoinVenueAdapter::validate_settlement_destination("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"));
        assert!(BitcoinVenueAdapter::validate_settlement_destination("bc1p0xlxvlhemja6c4nqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"));
        assert!(BitcoinVenueAdapter::validate_settlement_destination("bridge:thorchain:bnb1234567890"));
        assert!(!BitcoinVenueAdapter::validate_settlement_destination("0xInvalidEthereumAddress"));
        assert!(!BitcoinVenueAdapter::validate_settlement_destination("bc1qInvalidWithUppercaseOR1"));
    }

    #[test]
    fn test_smart_execution_router_execute_for_leaf_bitcoin_isolation() {
        let router = SmartExecutionRouter::new(ExecutionMode::Backtest);
        let mut order = approved_order(Venue::BinanceSpot, OrderType::Limit, 0);
        order.intent.symbol = "BTC-USD".to_string();

        let res = router.execute_for_leaf("leaf-bitcoin", &order, 1000);
        assert!(res.is_ok());

        order.intent.symbol = "ETH-USDT".to_string();
        let res_err = router.execute_for_leaf("leaf-bitcoin", &order, 1000);
        assert!(res_err.is_err());
    }
}

use robotrader_common::{
    fee_bps_for, spread_bps_for, ApprovedOrder, MarketEvent, OrderType, PodId, Side, Venue,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FillStatus {
    Filled,
    UnfilledExpired,
    PendingResting,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulatedFill {
    pub timestamp_ms: u64,
    pub pod_id: PodId,
    pub symbol: String,
    pub venue: Venue,
    pub side: Side,
    pub order_type: OrderType,
    pub fill_price: f64,
    pub filled_quantity: f64,
    pub notional_usd: f64,
    pub fee_usd: f64,
    pub slippage_bps: f64,
    pub status: FillStatus,
    pub rationale: String,
    pub approved_order: ApprovedOrder,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RestingOrder {
    pub order: ApprovedOrder,
    pub placed_at_ts: u64,
    pub resting_price: f64,
    pub resting_ticks: usize,
}

#[derive(Debug, Clone)]
pub struct EventDrivenFillSimulator {
    pub divergence_threshold_bps: f64,
    pub max_resting_ticks: usize,
    pub starvation_obi_threshold: f64,
    pub default_liquidity_usd: f64,
    pub resting_orders: Vec<RestingOrder>,
}

impl Default for EventDrivenFillSimulator {
    fn default() -> Self {
        Self::new()
    }
}

impl EventDrivenFillSimulator {
    pub fn new() -> Self {
        Self {
            divergence_threshold_bps: 50.0,
            max_resting_ticks: 3,
            starvation_obi_threshold: -0.70,
            default_liquidity_usd: 50_000.0,
            resting_orders: Vec::new(),
        }
    }

    /// Submits an approved order. Immediate taker orders execute at once.
    /// Resting maker and limit orders are queued and return None.
    pub fn submit_order(
        &mut self,
        order: ApprovedOrder,
        event: &MarketEvent,
    ) -> Option<SimulatedFill> {
        match order.intent.order_type {
            OrderType::Market | OrderType::MevBundleAtomic => {
                Some(self.execute_taker(&order, event))
            }
            OrderType::PostOnlyMaker => {
                let resting_price = order.intent.reference_price;
                self.resting_orders.push(RestingOrder {
                    order,
                    placed_at_ts: event.timestamp_ms(),
                    resting_price,
                    resting_ticks: 0,
                });
                None
            }
            OrderType::Limit => {
                let limit_price = order.intent.reference_price;
                self.resting_orders.push(RestingOrder {
                    order,
                    placed_at_ts: event.timestamp_ms(),
                    resting_price: limit_price,
                    resting_ticks: 0,
                });
                None
            }
        }
    }

    /// Evaluates all pending resting orders against the new market event.
    /// Orders that fill or expire are removed from the queue and returned.
    pub fn process_market_event(&mut self, event: &MarketEvent) -> Vec<SimulatedFill> {
        let mut results = Vec::new();
        let mut remaining = Vec::new();
        let orders = std::mem::take(&mut self.resting_orders);

        for mut resting in orders {
            if resting.order.intent.symbol == event.symbol() {
                resting.resting_ticks += 1;
                let fill_opt = match resting.order.intent.order_type {
                    OrderType::PostOnlyMaker => self.evaluate_maker_fill(
                        &resting.order,
                        resting.resting_price,
                        resting.resting_ticks,
                        event,
                    ),
                    OrderType::Limit => self.evaluate_limit_fill(
                        &resting.order,
                        resting.resting_price,
                        resting.resting_ticks,
                        event,
                    ),
                    _ => None,
                };

                if let Some(fill) = fill_opt {
                    results.push(fill);
                } else {
                    remaining.push(resting);
                }
            } else {
                remaining.push(resting);
            }
        }

        self.resting_orders = remaining;
        results
    }

    /// Evaluates execution for a `PostOnlyMaker` order on a subsequent tick.
    pub fn evaluate_maker_fill(
        &self,
        order: &ApprovedOrder,
        resting_price: f64,
        resting_ticks: usize,
        event: &MarketEvent,
    ) -> Option<SimulatedFill> {
        let tick_price = event.mark_price();
        let ts = event.timestamp_ms();
        let obi = extract_obi(event);
        let div_threshold = self.divergence_threshold_bps / 10_000.0;

        match order.intent.side {
            Side::Buy => {
                // Crossing/matching check: tick price <= resting maker bid
                if tick_price <= resting_price {
                    // Queue starvation: severe sell imbalance (obi < -0.70)
                    if obi < self.starvation_obi_threshold {
                        // Starved by heavy adverse book pressure, cannot fill this tick
                    } else {
                        // Order fills at resting price
                        let fee_bps =
                            fee_bps_for(order.intent.venue, OrderType::PostOnlyMaker);
                        let fee_usd = order.approved_notional_usd * (fee_bps / 10_000.0);
                        return Some(SimulatedFill {
                            timestamp_ms: ts,
                            pod_id: order.intent.pod_id,
                            symbol: order.intent.symbol.clone(),
                            venue: order.intent.venue,
                            side: Side::Buy,
                            order_type: OrderType::PostOnlyMaker,
                            fill_price: resting_price,
                            filled_quantity: order.approved_quantity,
                            notional_usd: order.approved_notional_usd,
                            fee_usd,
                            slippage_bps: 0.0,
                            status: FillStatus::Filled,
                            rationale: order.intent.rationale.clone(),
                            approved_order: order.clone(),
                        });
                    }
                }

                // Adverse divergence or resting horizon expiration
                if tick_price > resting_price * (1.0 + div_threshold)
                    || resting_ticks >= self.max_resting_ticks
                {
                    return Some(SimulatedFill {
                        timestamp_ms: ts,
                        pod_id: order.intent.pod_id,
                        symbol: order.intent.symbol.clone(),
                        venue: order.intent.venue,
                        side: Side::Buy,
                        order_type: OrderType::PostOnlyMaker,
                        fill_price: 0.0,
                        filled_quantity: 0.0,
                        notional_usd: 0.0,
                        fee_usd: 0.0,
                        slippage_bps: 0.0,
                        status: FillStatus::UnfilledExpired,
                        rationale: "Maker order expired unfilled due to adverse divergence or horizon"
                            .to_string(),
                        approved_order: order.clone(),
                    });
                }

                None
            }
            Side::Sell => {
                // Crossing check: tick price >= resting maker ask
                if tick_price >= resting_price {
                    // Queue starvation: severe buy imbalance (obi > 0.70)
                    if obi > -self.starvation_obi_threshold {
                        // Starved by heavy adverse book pressure
                    } else {
                        let fee_bps =
                            fee_bps_for(order.intent.venue, OrderType::PostOnlyMaker);
                        let fee_usd = order.approved_notional_usd * (fee_bps / 10_000.0);
                        return Some(SimulatedFill {
                            timestamp_ms: ts,
                            pod_id: order.intent.pod_id,
                            symbol: order.intent.symbol.clone(),
                            venue: order.intent.venue,
                            side: Side::Sell,
                            order_type: OrderType::PostOnlyMaker,
                            fill_price: resting_price,
                            filled_quantity: order.approved_quantity,
                            notional_usd: order.approved_notional_usd,
                            fee_usd,
                            slippage_bps: 0.0,
                            status: FillStatus::Filled,
                            rationale: order.intent.rationale.clone(),
                            approved_order: order.clone(),
                        });
                    }
                }

                if tick_price < resting_price * (1.0 - div_threshold)
                    || resting_ticks >= self.max_resting_ticks
                {
                    return Some(SimulatedFill {
                        timestamp_ms: ts,
                        pod_id: order.intent.pod_id,
                        symbol: order.intent.symbol.clone(),
                        venue: order.intent.venue,
                        side: Side::Sell,
                        order_type: OrderType::PostOnlyMaker,
                        fill_price: 0.0,
                        filled_quantity: 0.0,
                        notional_usd: 0.0,
                        fee_usd: 0.0,
                        slippage_bps: 0.0,
                        status: FillStatus::UnfilledExpired,
                        rationale: "Maker order expired unfilled due to adverse divergence or horizon"
                            .to_string(),
                        approved_order: order.clone(),
                    });
                }

                None
            }
        }
    }

    /// Evaluates execution for a `Limit` order when market trades through.
    pub fn evaluate_limit_fill(
        &self,
        order: &ApprovedOrder,
        limit_price: f64,
        resting_ticks: usize,
        event: &MarketEvent,
    ) -> Option<SimulatedFill> {
        let tick_price = event.mark_price();
        let ts = event.timestamp_ms();
        let adverse_bps = spread_bps_for(OrderType::Limit, order.mev_priority_tip_bps);

        match order.intent.side {
            Side::Buy => {
                // Market trades through limit price
                if tick_price < limit_price {
                    let fill_price = limit_price * (1.0 + adverse_bps / 10_000.0);
                    let fee_bps = fee_bps_for(order.intent.venue, OrderType::Limit);
                    let fee_usd = order.approved_notional_usd * (fee_bps / 10_000.0);
                    return Some(SimulatedFill {
                        timestamp_ms: ts,
                        pod_id: order.intent.pod_id,
                        symbol: order.intent.symbol.clone(),
                        venue: order.intent.venue,
                        side: Side::Buy,
                        order_type: OrderType::Limit,
                        fill_price,
                        filled_quantity: order.approved_quantity,
                        notional_usd: order.approved_notional_usd,
                        fee_usd,
                        slippage_bps: adverse_bps,
                        status: FillStatus::Filled,
                        rationale: order.intent.rationale.clone(),
                        approved_order: order.clone(),
                    });
                }

                if resting_ticks >= self.max_resting_ticks {
                    return Some(SimulatedFill {
                        timestamp_ms: ts,
                        pod_id: order.intent.pod_id,
                        symbol: order.intent.symbol.clone(),
                        venue: order.intent.venue,
                        side: Side::Buy,
                        order_type: OrderType::Limit,
                        fill_price: 0.0,
                        filled_quantity: 0.0,
                        notional_usd: 0.0,
                        fee_usd: 0.0,
                        slippage_bps: 0.0,
                        status: FillStatus::UnfilledExpired,
                        rationale: "Limit order expired unfilled without trade-through".to_string(),
                        approved_order: order.clone(),
                    });
                }

                None
            }
            Side::Sell => {
                // Market trades through limit price upwards
                if tick_price > limit_price {
                    let fill_price = limit_price * (1.0 - adverse_bps / 10_000.0);
                    let fee_bps = fee_bps_for(order.intent.venue, OrderType::Limit);
                    let fee_usd = order.approved_notional_usd * (fee_bps / 10_000.0);
                    return Some(SimulatedFill {
                        timestamp_ms: ts,
                        pod_id: order.intent.pod_id,
                        symbol: order.intent.symbol.clone(),
                        venue: order.intent.venue,
                        side: Side::Sell,
                        order_type: OrderType::Limit,
                        fill_price,
                        filled_quantity: order.approved_quantity,
                        notional_usd: order.approved_notional_usd,
                        fee_usd,
                        slippage_bps: adverse_bps,
                        status: FillStatus::Filled,
                        rationale: order.intent.rationale.clone(),
                        approved_order: order.clone(),
                    });
                }

                if resting_ticks >= self.max_resting_ticks {
                    return Some(SimulatedFill {
                        timestamp_ms: ts,
                        pod_id: order.intent.pod_id,
                        symbol: order.intent.symbol.clone(),
                        venue: order.intent.venue,
                        side: Side::Sell,
                        order_type: OrderType::Limit,
                        fill_price: 0.0,
                        filled_quantity: 0.0,
                        notional_usd: 0.0,
                        fee_usd: 0.0,
                        slippage_bps: 0.0,
                        status: FillStatus::UnfilledExpired,
                        rationale: "Limit order expired unfilled without trade-through".to_string(),
                        approved_order: order.clone(),
                    });
                }

                None
            }
        }
    }

    /// Executes an aggressive taker or atomic MEV bundle immediately.
    pub fn execute_taker(&self, order: &ApprovedOrder, event: &MarketEvent) -> SimulatedFill {
        let ts = event.timestamp_ms();
        let ref_price = order.intent.reference_price;
        let spread_bps = spread_bps_for(order.intent.order_type, order.mev_priority_tip_bps);
        let avail_liq = extract_available_liquidity(event, self.default_liquidity_usd);

        let depth_impact_bps = (5.0 * (order.approved_notional_usd / avail_liq))
            .min(order.intent.max_slippage_bps as f64);
        let total_slippage_bps = spread_bps + depth_impact_bps;

        let fill_price = match order.intent.side {
            Side::Buy => ref_price * (1.0 + total_slippage_bps / 10_000.0),
            Side::Sell => ref_price * (1.0 - total_slippage_bps / 10_000.0),
        };

        let fee_bps = fee_bps_for(order.intent.venue, order.intent.order_type);
        let fee_usd = order.approved_notional_usd * (fee_bps / 10_000.0);

        SimulatedFill {
            timestamp_ms: ts,
            pod_id: order.intent.pod_id,
            symbol: order.intent.symbol.clone(),
            venue: order.intent.venue,
            side: order.intent.side,
            order_type: order.intent.order_type,
            fill_price,
            filled_quantity: order.approved_quantity,
            notional_usd: order.approved_notional_usd,
            fee_usd,
            slippage_bps: total_slippage_bps,
            status: FillStatus::Filled,
            rationale: order.intent.rationale.clone(),
            approved_order: order.clone(),
        }
    }
}

pub fn extract_obi(event: &MarketEvent) -> f64 {
    match event {
        MarketEvent::OrderbookTick {
            bid_volume_top5,
            ask_volume_top5,
            ..
        } => {
            let total = bid_volume_top5 + ask_volume_top5;
            if total > 0.0 {
                (bid_volume_top5 - ask_volume_top5) / total
            } else {
                0.0
            }
        }
        _ => 0.0,
    }
}

pub fn extract_available_liquidity(event: &MarketEvent, fallback_usd: f64) -> f64 {
    match event {
        MarketEvent::OrderbookTick {
            mid_price,
            bid_volume_top5,
            ask_volume_top5,
            ..
        } => {
            let vol = (bid_volume_top5 + ask_volume_top5) * 0.5 * mid_price;
            if vol > 0.0 {
                vol
            } else {
                fallback_usd
            }
        }
        MarketEvent::OnchainPoolLaunch {
            initial_liquidity_usd,
            ..
        } => {
            if *initial_liquidity_usd > 0.0 {
                *initial_liquidity_usd
            } else {
                fallback_usd
            }
        }
        MarketEvent::OnchainSmartMoneySwap { buy_volume_usd, .. } => {
            if *buy_volume_usd > 0.0 {
                buy_volume_usd * 2.0
            } else {
                fallback_usd
            }
        }
        MarketEvent::FundingSnapshot { .. } => fallback_usd,
    }
}

use robotrader_common::{fee_bps_for, OrderType, PodId, PolicyEnvelope, Side, Venue};
use robotrader_exec_router::SimulatedFill;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PositionCloseReason {
    TakeProfit,
    StopLoss,
    EndOfStreamMtm,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenPosition {
    pub position_id: String,
    pub pod_id: PodId,
    pub symbol: String,
    pub venue: Venue,
    pub side: Side,
    pub entry_price: f64,
    pub quantity: f64,
    pub notional_usd: f64,
    pub entry_fee_usd: f64,
    pub take_profit_bps: f64,
    pub stop_loss_bps: f64,
    pub opened_at_ts: u64,
    pub open_duration_ticks: usize,
    pub accrued_funding_usd: f64,
    pub rationale: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClosedPosition {
    pub trade_id: String,
    pub pod_id: PodId,
    pub symbol: String,
    pub venue: Venue,
    pub side: Side,
    pub entry_price: f64,
    pub exit_price: f64,
    pub quantity: f64,
    pub entry_fee_usd: f64,
    pub exit_fee_usd: f64,
    pub gross_pnl_usd: f64,
    pub realized_pnl_usd: f64,
    pub close_reason: PositionCloseReason,
    pub holding_duration_ticks: usize,
}

#[derive(Debug, Default)]
pub struct PositionLifecycleEngine {
    pub open_positions: Vec<OpenPosition>,
    pub position_seq: usize,
}

impl PositionLifecycleEngine {
    pub fn new() -> Self {
        Self {
            open_positions: Vec::new(),
            position_seq: 0,
        }
    }

    /// Opens a new position from a filled order. TP and SL thresholds are resolved
    /// from asset overrides in the policy envelope, falling back to intent percentages.
    pub fn open_position_from_fill(
        &mut self,
        fill: &SimulatedFill,
        envelope: &PolicyEnvelope,
    ) -> &OpenPosition {
        self.position_seq += 1;
        let position_id = format!("pos-{}-{}", fill.pod_id.as_str(), self.position_seq);

        let (take_profit_bps, stop_loss_bps) =
            if let Some(override_rule) = envelope.asset_overrides.get(&fill.symbol) {
                let tp = override_rule
                    .take_profit_bps
                    .unwrap_or(fill.approved_order.intent.take_profit_pct * 100.0);
                let sl = override_rule
                    .stop_loss_bps
                    .unwrap_or(fill.approved_order.intent.stop_loss_pct * 100.0);
                (
                    if tp > 0.0 { tp } else { 150.0 },
                    if sl > 0.0 { sl } else { 100.0 },
                )
            } else {
                let tp = fill.approved_order.intent.take_profit_pct * 100.0;
                let sl = fill.approved_order.intent.stop_loss_pct * 100.0;
                (
                    if tp > 0.0 { tp } else { 150.0 },
                    if sl > 0.0 { sl } else { 100.0 },
                )
            };

        let pos = OpenPosition {
            position_id,
            pod_id: fill.pod_id,
            symbol: fill.symbol.clone(),
            venue: fill.venue,
            side: fill.side,
            entry_price: fill.fill_price,
            quantity: fill.filled_quantity,
            notional_usd: fill.notional_usd,
            entry_fee_usd: fill.fee_usd,
            take_profit_bps,
            stop_loss_bps,
            opened_at_ts: fill.timestamp_ms,
            open_duration_ticks: 0,
            accrued_funding_usd: 0.0,
            rationale: fill.rationale.clone(),
        };

        self.open_positions.push(pos);
        self.open_positions.last().unwrap()
    }

    /// Evaluates all open positions against a subsequent market tick.
    /// Positions that cross take-profit or stop-loss boundaries close immediately.
    pub fn evaluate_tick(
        &mut self,
        symbol: &str,
        tick_price: f64,
        _timestamp_ms: u64,
    ) -> Vec<ClosedPosition> {
        let mut closed = Vec::new();
        let mut remaining = Vec::new();

        for mut pos in self.open_positions.drain(..) {
            if pos.symbol == symbol {
                pos.open_duration_ticks += 1;
                let mut close_event = None;

                match pos.side {
                    Side::Buy => {
                        let tp_target = pos.entry_price * (1.0 + pos.take_profit_bps / 10_000.0);
                        let sl_target = pos.entry_price * (1.0 - pos.stop_loss_bps / 10_000.0);

                        if tick_price >= tp_target {
                            close_event = Some((tp_target, PositionCloseReason::TakeProfit));
                        } else if tick_price <= sl_target {
                            close_event = Some((sl_target, PositionCloseReason::StopLoss));
                        }
                    }
                    Side::Sell => {
                        let tp_target = pos.entry_price * (1.0 - pos.take_profit_bps / 10_000.0);
                        let sl_target = pos.entry_price * (1.0 + pos.stop_loss_bps / 10_000.0);

                        if tick_price <= tp_target {
                            close_event = Some((tp_target, PositionCloseReason::TakeProfit));
                        } else if tick_price >= sl_target {
                            close_event = Some((sl_target, PositionCloseReason::StopLoss));
                        }
                    }
                }

                if let Some((exit_px, reason)) = close_event {
                    let exit_order_type = match reason {
                        PositionCloseReason::TakeProfit => OrderType::Limit,
                        _ => OrderType::Market,
                    };
                    let exit_fee_bps = fee_bps_for(pos.venue, exit_order_type);
                    let exit_fee_usd = (exit_px * pos.quantity) * (exit_fee_bps / 10_000.0);

                    let direction = match pos.side {
                        Side::Buy => 1.0,
                        Side::Sell => -1.0,
                    };
                    let gross_pnl_usd = (exit_px - pos.entry_price) * direction * pos.quantity;
                    // Strict non-circular PnL: market price delta minus trading fees and funding
                    let realized_pnl_usd =
                        gross_pnl_usd - pos.entry_fee_usd - exit_fee_usd - pos.accrued_funding_usd;

                    closed.push(ClosedPosition {
                        trade_id: pos.position_id,
                        pod_id: pos.pod_id,
                        symbol: pos.symbol,
                        venue: pos.venue,
                        side: pos.side,
                        entry_price: pos.entry_price,
                        exit_price: exit_px,
                        quantity: pos.quantity,
                        entry_fee_usd: pos.entry_fee_usd,
                        exit_fee_usd,
                        gross_pnl_usd,
                        realized_pnl_usd,
                        close_reason: reason,
                        holding_duration_ticks: pos.open_duration_ticks,
                    });
                } else {
                    remaining.push(pos);
                }
            } else {
                remaining.push(pos);
            }
        }

        self.open_positions = remaining;
        closed
    }

    /// Marks all remaining open positions to market at the final event's mid-price.
    pub fn settle_end_of_stream(
        &mut self,
        symbol: &str,
        final_price: f64,
        _timestamp_ms: u64,
    ) -> Vec<ClosedPosition> {
        let mut closed = Vec::new();
        let mut remaining = Vec::new();

        for pos in self.open_positions.drain(..) {
            if pos.symbol == symbol {
                let exit_fee_bps = fee_bps_for(pos.venue, OrderType::Market);
                let exit_fee_usd = (final_price * pos.quantity) * (exit_fee_bps / 10_000.0);

                let direction = match pos.side {
                    Side::Buy => 1.0,
                    Side::Sell => -1.0,
                };
                let gross_pnl_usd = (final_price - pos.entry_price) * direction * pos.quantity;
                let realized_pnl_usd =
                    gross_pnl_usd - pos.entry_fee_usd - exit_fee_usd - pos.accrued_funding_usd;

                closed.push(ClosedPosition {
                    trade_id: pos.position_id,
                    pod_id: pos.pod_id,
                    symbol: pos.symbol,
                    venue: pos.venue,
                    side: pos.side,
                    entry_price: pos.entry_price,
                    exit_price: final_price,
                    quantity: pos.quantity,
                    entry_fee_usd: pos.entry_fee_usd,
                    exit_fee_usd,
                    gross_pnl_usd,
                    realized_pnl_usd,
                    close_reason: PositionCloseReason::EndOfStreamMtm,
                    holding_duration_ticks: pos.open_duration_ticks + 1,
                });
            } else {
                remaining.push(pos);
            }
        }

        self.open_positions = remaining;
        closed
    }
}

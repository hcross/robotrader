//! Canonical execution-cost model.
//!
//! `HardRiskGate` and `SmartExecutionRouter` both price an order from these two
//! pure helpers. There is exactly one fee table and one spread table in the
//! workspace; consumers delegate here instead of declaring their own values.
//!
//! Both helpers are pure functions over `Copy` enums: no allocation, no
//! logging, no I/O, no global state. They are safe to call on the hot path.

use crate::{OrderType, Venue};

/// Canonical per-side execution fee, in basis points.
///
/// A round trip is twice this value. The table mirrors the venue economics the
/// execution router charges:
///
/// - CEX post-only maker: `1.8` bps (Binance), `1.0` bps (Hyperliquid);
/// - CEX taker/limit: `5.0` bps;
/// - on-chain DEX aggregator: `8.0` bps;
/// - on-chain atomic pool: `12.0` bps.
pub fn fee_bps_for(venue: Venue, order_type: OrderType) -> f64 {
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

/// Canonical spread component, in basis points, for `order_type`.
///
/// `mev_priority_tip_bps` is consumed only by `OrderType::MevBundleAtomic`,
/// whose spread is `0.6 x` the priority tip the gate attaches to the order.
/// The other order types are flat: maker `0.5` bps, limit `2.0` bps, market
/// `8.0` bps.
pub fn spread_bps_for(order_type: OrderType, mev_priority_tip_bps: u32) -> f64 {
    match order_type {
        OrderType::PostOnlyMaker => 0.5, // Maker fills capture spread
        OrderType::Limit => 2.0,
        OrderType::Market => 8.0,
        OrderType::MevBundleAtomic => (mev_priority_tip_bps as f64) * 0.6,
    }
}

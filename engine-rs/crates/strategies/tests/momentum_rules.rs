//! Table-driven tests for the `MomentumPod` mechanical-rule consumption.
//!
//! Each case isolates one rule from the spec: directional OBI, RSI bounds,
//! support/resistance zones, invalidation, and envelope TP/SL distances.

use robotrader_common::{
    AssetOverride, DirectionalBias, GlobalRegime, MarketEvent, OrderIntent, PolicyEnvelope, Side,
};
use robotrader_strategies::{MomentumPod, StrategyPod};
use std::collections::HashMap;

const SYMBOL: &str = "SOL-USDT";

/// Builds an `OrderbookTick` whose imbalance is exactly `obi` in `[-1.0, 1.0]`.
fn tick(mid_price: f64, obi: f64, cvd_delta: f64, zscore: f64, rsi_14: Option<f64>) -> MarketEvent {
    let bid = 1.0 + obi;
    let ask = 1.0 - obi;
    MarketEvent::OrderbookTick {
        timestamp_ms: 1_792_180_002_000,
        symbol: SYMBOL.to_string(),
        mid_price,
        bid_volume_top5: bid * 10_000.0,
        ask_volume_top5: ask * 10_000.0,
        cvd_delta,
        atr_pct: 2.0,
        breakout_zscore: zscore,
        rsi_14,
    }
}

fn long_tick(mid_price: f64, obi: f64, rsi_14: Option<f64>) -> MarketEvent {
    tick(mid_price, obi, 1.0, 2.0, rsi_14)
}

fn short_tick(mid_price: f64, obi: f64, rsi_14: Option<f64>) -> MarketEvent {
    tick(mid_price, obi, -1.0, -2.0, rsi_14)
}

fn rule() -> AssetOverride {
    AssetOverride {
        catalyst_score: 0.5,
        bias: DirectionalBias::Neutral,
        max_leverage: 2.0,
        support_zone_usd: None,
        resistance_zone_usd: None,
        invalidation_price_usd: None,
        entry_obi_threshold: None,
        max_rsi_long: None,
        min_rsi_short: None,
        take_profit_bps: None,
        stop_loss_bps: None,
    }
}

fn envelope(rule: Option<AssetOverride>) -> PolicyEnvelope {
    let mut asset_overrides = HashMap::new();
    if let Some(rule) = rule {
        asset_overrides.insert(SYMBOL.to_string(), rule);
    }
    PolicyEnvelope {
        envelope_id: "momentum_rules".to_string(),
        issued_at_ms: 0,
        ttl_seconds: 900,
        global_regime: GlobalRegime::RiskOnHighVol,
        pod_allocations: HashMap::new(),
        asset_overrides,
    }
}

fn intents(event: &MarketEvent, envelope: &PolicyEnvelope) -> Vec<OrderIntent> {
    let mut pod = MomentumPod::default();
    pod.on_market_event(event, envelope)
}

#[test]
fn override_obi_threshold_blocks_a_marginal_signal() {
    let rule = AssetOverride {
        entry_obi_threshold: Some(0.35),
        ..rule()
    };
    let emitted = intents(&long_tick(100.0, 0.30, None), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn obi_boundary_is_inclusive() {
    let rule = AssetOverride {
        entry_obi_threshold: Some(0.35),
        ..rule()
    };
    let emitted = intents(&long_tick(100.0, 0.35, None), &envelope(Some(rule)));
    assert_eq!(emitted.len(), 1);
    assert_eq!(emitted[0].side, Side::Buy);
}

#[test]
fn long_rsi_guard_blocks_an_overbought_entry() {
    let rule = AssetOverride {
        max_rsi_long: Some(55.0),
        ..rule()
    };
    let emitted = intents(&long_tick(100.0, 0.50, Some(60.0)), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn long_rsi_boundary_is_inclusive() {
    let rule = AssetOverride {
        max_rsi_long: Some(55.0),
        ..rule()
    };
    let emitted = intents(&long_tick(100.0, 0.50, Some(55.0)), &envelope(Some(rule)));
    assert_eq!(emitted.len(), 1);
    assert_eq!(emitted[0].side, Side::Buy);
}

#[test]
fn short_rsi_guard_blocks_an_oversold_entry() {
    let rule = AssetOverride {
        min_rsi_short: Some(45.0),
        ..rule()
    };
    let emitted = intents(&short_tick(100.0, -0.50, Some(40.0)), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn short_rsi_boundary_is_inclusive() {
    let rule = AssetOverride {
        min_rsi_short: Some(45.0),
        ..rule()
    };
    let emitted = intents(&short_tick(100.0, -0.50, Some(45.0)), &envelope(Some(rule)));
    assert_eq!(emitted.len(), 1);
    assert_eq!(emitted[0].side, Side::Sell);
}

#[test]
fn rsi_guard_is_reported_inactive_when_rsi_14_is_absent() {
    let emitted = intents(&long_tick(100.0, 0.50, None), &envelope(Some(rule())));
    assert_eq!(emitted.len(), 1);
    assert!(
        emitted[0].rationale.contains("RSI=INACTIVE"),
        "rationale must report the inactive guard, got: {}",
        emitted[0].rationale
    );
}

#[test]
fn support_gate_blocks_a_long_below_support() {
    let rule = AssetOverride {
        support_zone_usd: Some(150.0),
        ..rule()
    };
    let emitted = intents(&long_tick(149.9, 0.50, None), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn support_boundary_is_inclusive() {
    let rule = AssetOverride {
        support_zone_usd: Some(150.0),
        ..rule()
    };
    let emitted = intents(&long_tick(150.0, 0.50, None), &envelope(Some(rule)));
    assert_eq!(emitted.len(), 1);
}

#[test]
fn resistance_gate_blocks_a_short_above_resistance() {
    let rule = AssetOverride {
        resistance_zone_usd: Some(160.0),
        ..rule()
    };
    let emitted = intents(&short_tick(160.1, -0.50, None), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn resistance_boundary_is_inclusive() {
    let rule = AssetOverride {
        resistance_zone_usd: Some(160.0),
        ..rule()
    };
    let emitted = intents(&short_tick(160.0, -0.50, None), &envelope(Some(rule)));
    assert_eq!(emitted.len(), 1);
}

#[test]
fn invalidation_gate_blocks_a_long_at_the_level() {
    let rule = AssetOverride {
        invalidation_price_usd: Some(145.0),
        ..rule()
    };
    let emitted = intents(&long_tick(145.0, 0.50, None), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn invalidation_gate_blocks_a_short_at_the_level() {
    let rule = AssetOverride {
        invalidation_price_usd: Some(145.0),
        ..rule()
    };
    let emitted = intents(&short_tick(145.0, -0.50, None), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn take_profit_and_stop_loss_come_from_the_envelope() {
    let rule = AssetOverride {
        take_profit_bps: Some(120.0),
        stop_loss_bps: Some(60.0),
        ..rule()
    };
    let emitted = intents(&long_tick(100.0, 0.50, None), &envelope(Some(rule)));
    assert_eq!(emitted.len(), 1);
    assert_eq!(emitted[0].take_profit_pct, 1.2);
    assert_eq!(emitted[0].stop_loss_pct, 0.6);
}

#[test]
fn absent_numeric_rule_uses_the_python_default() {
    let emitted = intents(&long_tick(100.0, 0.05, None), &envelope(Some(rule())));
    assert!(
        emitted.is_empty(),
        "absent entry_obi_threshold must default to 0.08"
    );
}

#[test]
fn no_override_keeps_the_pod_defaults() {
    let emitted = intents(&long_tick(100.0, 0.23, Some(80.0)), &envelope(None));
    assert_eq!(emitted.len(), 1);
    assert_eq!(emitted[0].side, Side::Buy);
    // ATR 2.0: stop loss = 2.0 * 0.9, take profit = 2.0 * 2.2.
    assert_eq!(emitted[0].stop_loss_pct, 1.8);
    assert_eq!(emitted[0].take_profit_pct, 4.4);
}

#[test]
fn long_with_negative_threshold_obi_emits_nothing() {
    let rule = AssetOverride {
        entry_obi_threshold: Some(0.35),
        ..rule()
    };
    // Structurally a long (positive CVD and breakout), but the OBI sign is short.
    let emitted = intents(&tick(100.0, -0.35, 1.0, 2.0, None), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

#[test]
fn short_with_positive_threshold_obi_emits_nothing() {
    let rule = AssetOverride {
        entry_obi_threshold: Some(0.35),
        ..rule()
    };
    // Structurally a short (negative CVD and breakout), but the OBI sign is long.
    let emitted = intents(&tick(100.0, 0.35, -1.0, -2.0, None), &envelope(Some(rule)));
    assert!(emitted.is_empty());
}

//! Executable cross-language contract for `PolicyEnvelope` and `AssetOverride`.
//!
//! These tests pin the eleven-key parity, strict policy decoding, tolerant
//! event decoding, the optional `rsi_14` input, and the single-sourced
//! safe-baseline TTL. They run offline and need no Redis, network, or exchange.

use robotrader_common::{
    MarketEvent, OnChainTokenSafety, PolicyEnvelope, SAFE_BASELINE_TTL_SECONDS,
};
use serde_json::{json, Value};

fn full_override() -> Value {
    json!({
        "catalyst_score": 0.73,
        "bias": "SHORT_BIAS",
        "max_leverage": 2.25,
        "support_zone_usd": 150.5,
        "resistance_zone_usd": 160.5,
        "invalidation_price_usd": 145.5,
        "entry_obi_threshold": 0.35,
        "max_rsi_long": 55.0,
        "min_rsi_short": 45.0,
        "take_profit_bps": 120.0,
        "stop_loss_bps": 60.0,
    })
}

fn envelope_json(overrides: Value) -> Value {
    json!({
        "envelope_id": "rt_contract",
        "issued_at_ms": 1_792_180_000_000u64,
        "ttl_seconds": 900,
        "global_regime": "LOW_VOL_CARRY",
        "pod_allocations": {
            "pod_carry": {
                "enabled": true,
                "capital_weight": 0.5,
                "directional_bias": "NEUTRAL",
                "min_funding_apr": 0.15,
                "max_slippage_bps": 25,
            }
        },
        "asset_overrides": overrides,
    })
}

fn decode(value: Value) -> Result<PolicyEnvelope, serde_json::Error> {
    serde_json::from_value(value)
}

#[test]
fn all_eleven_keys_survive_decode_and_reencode() {
    let original = full_override();
    let envelope = decode(envelope_json(json!({ "SOL-USDT": original.clone() })))
        .expect("complete envelope must decode");

    let encoded = serde_json::to_value(&envelope).expect("envelope must re-encode");
    let override_object = encoded["asset_overrides"]["SOL-USDT"]
        .as_object()
        .expect("override must be an object");

    assert_eq!(override_object.len(), 11, "all eleven keys must be emitted");
    assert_eq!(
        encoded["asset_overrides"]["SOL-USDT"], original,
        "re-encoded values must equal the decoded values"
    );
}

#[test]
fn only_required_keys_decode() {
    let envelope = decode(envelope_json(json!({
        "SOL-USDT": {
            "catalyst_score": 0.5,
            "bias": "NEUTRAL",
            "max_leverage": 2.0,
        }
    })))
    .expect("required-only override must decode");

    let rule = &envelope.asset_overrides["SOL-USDT"];
    assert_eq!(rule.catalyst_score, 0.5);
    assert_eq!(rule.max_leverage, 2.0);
    assert_eq!(rule.support_zone_usd, None);
    assert_eq!(rule.resistance_zone_usd, None);
    assert_eq!(rule.invalidation_price_usd, None);
    assert_eq!(rule.entry_obi_threshold, None);
    assert_eq!(rule.max_rsi_long, None);
    assert_eq!(rule.min_rsi_short, None);
    assert_eq!(rule.take_profit_bps, None);
    assert_eq!(rule.stop_loss_bps, None);
}

#[test]
fn absent_optional_rule_decodes() {
    let mut override_json = full_override();
    override_json
        .as_object_mut()
        .expect("object")
        .remove("entry_obi_threshold");

    let envelope = decode(envelope_json(json!({ "SOL-USDT": override_json })))
        .expect("absent optional rule must decode");
    assert_eq!(
        envelope.asset_overrides["SOL-USDT"].entry_obi_threshold,
        None
    );
}

#[test]
fn missing_required_field_is_rejected() {
    let mut override_json = full_override();
    override_json
        .as_object_mut()
        .expect("object")
        .remove("catalyst_score");

    let error = decode(envelope_json(json!({ "SOL-USDT": override_json })))
        .expect_err("missing catalyst_score must be rejected");
    assert!(
        error.to_string().contains("catalyst_score"),
        "error must name the missing field, got: {error}"
    );
}

#[test]
fn null_optional_zone_is_preserved() {
    let mut override_json = full_override();
    override_json["support_zone_usd"] = Value::Null;

    let envelope = decode(envelope_json(json!({ "SOL-USDT": override_json })))
        .expect("null optional zone must decode");
    let encoded = serde_json::to_value(&envelope).expect("envelope must re-encode");

    assert_eq!(
        encoded["asset_overrides"]["SOL-USDT"]["support_zone_usd"],
        Value::Null
    );
}

#[test]
fn unknown_asset_override_key_is_rejected() {
    let mut override_json = full_override();
    override_json["trailing_stop_bps"] = json!(80.0);

    let error = decode(envelope_json(json!({ "SOL-USDT": override_json })))
        .expect_err("unknown override key must be rejected");
    assert!(
        error.to_string().contains("trailing_stop_bps"),
        "error must name the offending key, got: {error}"
    );
}

#[test]
fn unknown_pod_allocation_key_is_rejected() {
    let mut envelope = envelope_json(json!({}));
    envelope["pod_allocations"]["pod_carry"]["kelly_fraction"] = json!(0.5);

    let error = decode(envelope).expect_err("unknown PodAllocation key must be rejected");
    assert!(
        error.to_string().contains("kelly_fraction"),
        "error must name the offending key, got: {error}"
    );
}

#[test]
fn unknown_top_level_envelope_key_is_rejected() {
    let mut envelope = envelope_json(json!({}));
    envelope["schema_version"] = json!(2);

    let error = decode(envelope).expect_err("unknown top-level key must be rejected");
    assert!(
        error.to_string().contains("schema_version"),
        "error must name the offending key, got: {error}"
    );
}

#[test]
fn complete_known_envelope_is_accepted() {
    let envelope = decode(envelope_json(json!({ "SOL-USDT": full_override() })))
        .expect("a complete known envelope must decode");
    assert_eq!(envelope.envelope_id, "rt_contract");
    assert_eq!(envelope.asset_overrides.len(), 1);
}

#[test]
fn market_event_tolerates_unknown_fields() {
    let event: MarketEvent = serde_json::from_value(json!({
        "event_type": "ORDERBOOK_TICK",
        "timestamp_ms": 1_792_180_002_000u64,
        "symbol": "SOL-USDT",
        "mid_price": 152.4,
        "bid_volume_top5": 4800.0,
        "ask_volume_top5": 1900.0,
        "cvd_delta": 620_000.0,
        "atr_pct": 2.1,
        "breakout_zscore": 2.45,
        "rsi_14": 46.5,
        "unexpected_producer_field": true,
    }))
    .expect("MarketEvent must tolerate unknown fields");

    assert_eq!(event.symbol(), "SOL-USDT");
    assert_eq!(event.mark_price(), 152.4);
}

#[test]
fn onchain_token_safety_tolerates_unknown_fields() {
    let safety: OnChainTokenSafety = serde_json::from_value(json!({
        "supply_mint_immutable": true,
        "transfer_freeze_disabled": true,
        "no_honeypot_or_transfer_tax": true,
        "lp_locked_pct": 96.0,
        "top10_holder_pct": 21.0,
        "tx_simulation_success": true,
        "future_verifier": "ok",
    }))
    .expect("OnChainTokenSafety must tolerate unknown fields");

    assert!(safety.supply_mint_immutable);
    assert_eq!(safety.lp_locked_pct, 96.0);
}

#[test]
fn rsi_14_survives_a_roundtrip() {
    let event = MarketEvent::OrderbookTick {
        timestamp_ms: 1,
        symbol: "SOL-USDT".to_string(),
        mid_price: 152.4,
        bid_volume_top5: 4800.0,
        ask_volume_top5: 1900.0,
        cvd_delta: 620_000.0,
        atr_pct: 2.1,
        breakout_zscore: 2.45,
        rsi_14: Some(46.5),
    };

    let encoded = serde_json::to_string(&event).expect("event must serialize");
    let decoded: MarketEvent = serde_json::from_str(&encoded).expect("event must deserialize");

    let MarketEvent::OrderbookTick { rsi_14, .. } = decoded else {
        panic!("expected an OrderbookTick");
    };
    assert_eq!(rsi_14, Some(46.5));
}

#[test]
fn absent_rsi_14_decodes() {
    let decoded: MarketEvent = serde_json::from_str(
        r#"{
            "event_type": "ORDERBOOK_TICK",
            "timestamp_ms": 1,
            "symbol": "SOL-USDT",
            "mid_price": 152.4,
            "bid_volume_top5": 4800.0,
            "ask_volume_top5": 1900.0,
            "cvd_delta": 620000.0,
            "atr_pct": 2.1,
            "breakout_zscore": 2.45
        }"#,
    )
    .expect("absent rsi_14 must decode");

    let MarketEvent::OrderbookTick { rsi_14, .. } = decoded else {
        panic!("expected an OrderbookTick");
    };
    assert_eq!(rsi_14, None);
}

#[test]
fn safe_baseline_ttl_is_single_sourced() {
    assert_eq!(SAFE_BASELINE_TTL_SECONDS, 900);
    assert_eq!(
        PolicyEnvelope::safe_baseline(1_000_000).ttl_seconds,
        SAFE_BASELINE_TTL_SECONDS
    );
}

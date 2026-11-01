//! Hot-path benchmark for `HardRiskGate::validate`.
//!
//! Run with:
//!
//! ```text
//! cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate
//! ```
//!
//! Two paths are measured: an approved maker order that passes every gate,
//! and an order rejected by the cost hurdle (not by an earlier gate). The
//! closures perform no logging, I/O, or fixture allocation.
//!
//! `cargo test --all-targets` also compiles and executes this bench target
//! because a `harness = false` target is a test target. The benchmark is
//! intentionally kept on a short criterion configuration so the CI test job
//! stays cheap; the measurement is still statistically meaningful. The
//! command above is the canonical evidence path.

use criterion::{criterion_group, criterion_main, Criterion};
use robotrader_common::{
    OrderIntent, OrderType, PodId, PolicyEnvelope, PortfolioState, Side, Venue,
};
use robotrader_risk_gate::{HardRiskGate, RiskLimits};
use std::hint::black_box;
use std::time::Duration;

fn intent(order_type: OrderType) -> OrderIntent {
    OrderIntent {
        pod_id: PodId::PodCarry,
        symbol: "SOL-USDT".to_string(),
        venue: Venue::BinancePerp,
        side: Side::Sell,
        order_type,
        reference_price: 150.0,
        win_probability: 0.68,
        reward_risk_ratio: 2.2,
        asset_volatility_pct: 2.0,
        expected_edge_bps: 12.0,
        max_slippage_bps: 2,
        requested_leverage: 10.0,
        stop_loss_pct: 1.2,
        take_profit_pct: 2.6,
        token_safety: None,
        rationale: "benchmark fixture".to_string(),
        reduce_only: false,
    }
}

fn benchmark(c: &mut Criterion) {
    let portfolio = PortfolioState::new(10_000.0);
    let envelope = PolicyEnvelope::safe_baseline(1_000_000);
    let now_ms = 1_000_500u64;

    let mut approved_gate = HardRiskGate::new(RiskLimits::default());
    let approved = intent(OrderType::PostOnlyMaker);
    c.bench_function("validate/approved", |b| {
        b.iter(|| {
            let result = approved_gate.validate(
                black_box(&approved),
                black_box(&portfolio),
                black_box(&envelope),
                black_box(now_ms),
            );
            black_box(result.expect("the approved fixture must pass every gate"));
        })
    });

    let mut rejected_gate = HardRiskGate::new(RiskLimits::default());
    // `Market` on BinancePerp costs 22.0 bps including the buffer, so a 12.0
    // bps edge is rejected by the hurdle, not by an earlier gate.
    let rejected = intent(OrderType::Market);
    c.bench_function("validate/rejected_hurdle", |b| {
        b.iter(|| {
            let result = rejected_gate.validate(
                black_box(&rejected),
                black_box(&portfolio),
                black_box(&envelope),
                black_box(now_ms),
            );
            black_box(result.expect_err("the rejected fixture must fail the hurdle"));
        })
    });
}

criterion_group! {
    name = benches;
    config = Criterion::default()
        .sample_size(50)
        .warm_up_time(Duration::from_millis(500))
        .measurement_time(Duration::from_secs(2));
    targets = benchmark
}
criterion_main!(benches);

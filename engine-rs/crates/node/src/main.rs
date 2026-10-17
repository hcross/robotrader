use robotrader_backtest::{benchmark_market_stream, BacktestEngine};
use robotrader_common::PolicyEnvelope;
use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    let (events, default_envelope) = benchmark_market_stream();

    // Optional --policy-json argument to override the PolicyEnvelope from Python Warm-Path
    let mut envelope: PolicyEnvelope = default_envelope;
    for i in 0..args.len() {
        if args[i] == "--policy-json" && i + 1 < args.len() {
            if let Ok(parsed) = serde_json::from_str::<PolicyEnvelope>(&args[i + 1]) {
                envelope = parsed;
            }
        }
    }

    let engine = BacktestEngine::default();
    let summary = engine.run(&events, &envelope);
    let json = serde_json::to_string_pretty(&summary).expect("Failed to serialize summary");
    println!("{json}");
}

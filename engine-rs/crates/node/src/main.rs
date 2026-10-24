use robotrader_backtest::{benchmark_market_stream_for_leaf, BacktestEngine};
use robotrader_common::PolicyEnvelope;
use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut leaf_id = "leaf-solana".to_string();
    let mut custom_policy_json: Option<String> = None;

    for i in 0..args.len() {
        if args[i] == "--leaf-id" && i + 1 < args.len() {
            leaf_id = args[i + 1].clone();
        } else if args[i] == "--policy-json" && i + 1 < args.len() {
            custom_policy_json = Some(args[i + 1].clone());
        }
    }

    let (events, default_envelope) = benchmark_market_stream_for_leaf(&leaf_id);
    let mut envelope: PolicyEnvelope = default_envelope;
    if let Some(raw_json) = custom_policy_json {
        if let Ok(parsed) = serde_json::from_str::<PolicyEnvelope>(&raw_json) {
            envelope = parsed;
        }
    }

    let engine = BacktestEngine::default();
    let summary = engine.run_for_leaf(&leaf_id, &events, &envelope);
    let json = serde_json::to_string_pretty(&summary).expect("Failed to serialize summary");
    println!("{json}");
}

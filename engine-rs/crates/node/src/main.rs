use robotrader_backtest::{benchmark_market_stream_for_leaf, BacktestEngine};
use robotrader_common::PolicyEnvelope;
use robotrader_risk_gate::RustVaultEnclave;
use std::env;
use std::io::Read;

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut leaf_id = "leaf-solana".to_string();
    let mut custom_policy_json: Option<String> = None;
    let mut contract_roundtrip = false;
    let mut dump_vault_manifest = false;
    let mut sign_transfer = false;
    let mut dest_address = "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN".to_string();
    let mut amount_usd: f64 = 100.0;
    let mut token = "USDC".to_string();
    let mut kill_switch = false;

    for i in 0..args.len() {
        if (args[i] == "--leaf-id" || args[i] == "--leaf") && i + 1 < args.len() {
            leaf_id = args[i + 1].clone();
        } else if args[i] == "--policy-json" && i + 1 < args.len() {
            custom_policy_json = Some(args[i + 1].clone());
        } else if args[i] == "--contract-roundtrip" {
            contract_roundtrip = true;
        } else if args[i] == "--vault-manifest" {
            dump_vault_manifest = true;
        } else if args[i] == "--sign-transfer" {
            sign_transfer = true;
        } else if args[i] == "--dest" && i + 1 < args.len() {
            dest_address = args[i + 1].clone();
        } else if args[i] == "--amount-usd" && i + 1 < args.len() {
            amount_usd = args[i + 1].parse::<f64>().unwrap_or(100.0);
        } else if args[i] == "--token" && i + 1 < args.len() {
            token = args[i + 1].clone();
        } else if args[i] == "--kill-switch" {
            kill_switch = true;
        }
    }

    if contract_roundtrip {
        // Side-effect-free transport: stdin JSON -> strict decode -> canonical JSON.
        let mut raw_input = String::new();
        std::io::stdin()
            .read_to_string(&mut raw_input)
            .expect("Failed to read stdin");
        match serde_json::from_str::<PolicyEnvelope>(&raw_input) {
            Ok(parsed) => {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&parsed)
                        .expect("Failed to serialize policy envelope")
                );
                return;
            }
            Err(err) => {
                eprintln!("contract roundtrip decode failed: {err}");
                std::process::exit(2);
            }
        }
    }

    if dump_vault_manifest {
        let enclave = RustVaultEnclave::default();
        let manifest = enclave.export_public_manifest();
        println!(
            "{}",
            serde_json::to_string_pretty(&manifest).expect("Failed to serialize vault manifest")
        );
        return;
    }

    if sign_transfer {
        let enclave = RustVaultEnclave::default();
        match enclave.validate_and_sign_transfer(
            kill_switch,
            &leaf_id,
            &dest_address,
            amount_usd,
            &token,
        ) {
            Ok(receipt) => {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&receipt).expect("Failed to serialize receipt")
                );
            }
            Err(err) => {
                let err_json = serde_json::json!({
                    "status": "rejected_by_rust_enclave",
                    "error": err.to_string(),
                });
                println!("{}", serde_json::to_string_pretty(&err_json).unwrap());
                std::process::exit(1);
            }
        }
        return;
    }

    // Strict-decoding happens before event generation so a malformed policy
    // can never run against the benchmark default or leak a summary to stdout.
    let custom_envelope: Option<PolicyEnvelope> = match custom_policy_json {
        Some(raw_json) => match serde_json::from_str::<PolicyEnvelope>(&raw_json) {
            Ok(parsed) => Some(parsed),
            Err(err) => {
                eprintln!("failed to decode --policy-json: {err}");
                std::process::exit(2);
            }
        },
        None => None,
    };

    let (events, default_envelope) = benchmark_market_stream_for_leaf(&leaf_id);
    let envelope = custom_envelope.unwrap_or(default_envelope);

    let engine = BacktestEngine::default();
    let summary = engine.run_for_leaf(&leaf_id, &events, &envelope);
    let json = serde_json::to_string_pretty(&summary).expect("Failed to serialize summary");
    println!("{json}");
}

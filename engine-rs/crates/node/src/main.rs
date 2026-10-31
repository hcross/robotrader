use robotrader_backtest::{benchmark_market_stream_for_leaf, BacktestEngine};
use robotrader_common::PolicyEnvelope;
use robotrader_risk_gate::{HardRiskGate, RiskLimits, SimulatedVault};
use robotrader_strategies::{ecosystem_pod_specs, is_canonical_leaf_id, CANONICAL_LEAF_IDS};
use serde::Deserialize;
use std::env;
use std::io::Read;
use std::path::PathBuf;

#[derive(Debug, Deserialize)]
struct ValidateRefillArgs {
    #[serde(deserialize_with = "deserialize_f64_lenient")]
    requested_usd: f64,
    #[serde(deserialize_with = "deserialize_f64_lenient")]
    realized_trading_pnl_usd: f64,
    #[serde(deserialize_with = "deserialize_f64_lenient")]
    current_balance_usd: f64,
    #[serde(deserialize_with = "deserialize_f64_lenient")]
    low_watermark_usd: f64,
    #[serde(deserialize_with = "deserialize_f64_lenient")]
    epoch_refilled_usd: f64,
    #[serde(deserialize_with = "deserialize_f64_lenient")]
    max_epoch_refill_usd: f64,
    force: bool,
    #[serde(default)]
    kill_switch_active: bool,
}

fn deserialize_f64_lenient<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: serde::Deserializer<'de>,
{
    use serde::de::Error;
    let v = serde_json::Value::deserialize(deserializer)?;
    match v {
        serde_json::Value::Number(n) => {
            n.as_f64().ok_or_else(|| D::Error::custom("invalid number"))
        }
        serde_json::Value::String(s) => match s.trim().to_ascii_lowercase().as_str() {
            "nan" => Ok(f64::NAN),
            "inf" | "+inf" | "infinity" | "+infinity" => Ok(f64::INFINITY),
            "-inf" | "-infinity" => Ok(f64::NEG_INFINITY),
            _ => s.parse::<f64>().map_err(D::Error::custom),
        },
        _ => Err(D::Error::custom("expected a number or numeric string")),
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut leaf_id = "leaf-solana".to_string();
    let mut custom_leaf_id: Option<String> = None;
    let mut custom_policy_json: Option<String> = None;
    let mut contract_roundtrip = false;
    let mut dump_vault_manifest = false;
    let mut dump_pod_catalog = false;
    let mut sign_transfer = false;
    let mut dest_address = "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN".to_string();
    let mut amount_usd: f64 = 100.0;
    let mut token = "USDC".to_string();
    let mut kill_switch = false;
    let mut vault_secret_file: Option<PathBuf> = None;
    let mut validate_refill = false;
    let mut validate_refill_json: Option<String> = None;

    for i in 0..args.len() {
        if (args[i] == "--leaf-id" || args[i] == "--leaf") && i + 1 < args.len() {
            leaf_id = args[i + 1].clone();
            custom_leaf_id = Some(args[i + 1].clone());
        } else if args[i] == "--policy-json" && i + 1 < args.len() {
            custom_policy_json = Some(args[i + 1].clone());
        } else if args[i] == "--dump-pod-catalog" || args[i] == "--export-pod-catalog" {
            dump_pod_catalog = true;
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
        } else if args[i] == "--vault-secret-file" && i + 1 < args.len() {
            // Test-only override; production uses the default secret mount path.
            vault_secret_file = Some(PathBuf::from(args[i + 1].clone()));
        } else if args[i] == "--validate-refill" {
            validate_refill = true;
            if i + 1 < args.len() && !args[i + 1].starts_with("--") {
                validate_refill_json = Some(args[i + 1].clone());
            }
        }
    }

    if validate_refill {
        let raw_json = match validate_refill_json {
            Some(j) => j,
            None => {
                eprintln!("missing argument for --validate-refill");
                std::process::exit(2);
            }
        };

        let parsed: ValidateRefillArgs = match serde_json::from_str(&raw_json) {
            Ok(args) => args,
            Err(err) => {
                eprintln!("failed to parse --validate-refill JSON: {err}");
                std::process::exit(2);
            }
        };

        let mut gate = HardRiskGate::new(RiskLimits::default());
        if parsed.kill_switch_active {
            gate.trigger_kill_switch("Kill-switch active in refill request");
        }
        let verdict = gate.validate_inference_refill(
            parsed.requested_usd,
            parsed.realized_trading_pnl_usd,
            parsed.current_balance_usd,
            parsed.low_watermark_usd,
            parsed.epoch_refilled_usd,
            parsed.max_epoch_refill_usd,
            parsed.force,
        );

        println!(
            "{}",
            serde_json::to_string_pretty(&verdict).expect("Failed to serialize verdict")
        );
        std::process::exit(0);
    }

    if dump_pod_catalog {
        match custom_leaf_id {
            Some(ref id) => {
                if !is_canonical_leaf_id(id) {
                    eprintln!("unrecognized leaf identifier: {id}");
                    std::process::exit(1);
                }
                let specs = ecosystem_pod_specs(id);
                println!(
                    "{}",
                    serde_json::to_string_pretty(&specs)
                        .expect("Failed to serialize leaf pod catalog")
                );
            }
            None => {
                let mut map = serde_json::Map::new();
                for &id in CANONICAL_LEAF_IDS {
                    let specs = ecosystem_pod_specs(id);
                    let val = serde_json::to_value(&specs)
                        .expect("Failed to serialize leaf pod catalog");
                    map.insert(id.to_string(), val);
                }
                println!(
                    "{}",
                    serde_json::to_string_pretty(&serde_json::Value::Object(map))
                        .expect("Failed to serialize full pod catalog")
                );
            }
        }
        return;
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
        let vault = match vault_secret_file {
            Some(path) => SimulatedVault::from_env_with_secret_file(path),
            None => SimulatedVault::from_env(),
        };
        let vault = match vault {
            Ok(vault) => vault,
            Err(err) => {
                eprintln!("{err}");
                std::process::exit(2);
            }
        };
        let manifest = vault.export_public_manifest();
        println!(
            "{}",
            serde_json::to_string_pretty(&manifest).expect("Failed to serialize vault manifest")
        );
        return;
    }

    if sign_transfer {
        let vault = match vault_secret_file {
            Some(path) => SimulatedVault::from_env_with_secret_file(path),
            None => SimulatedVault::from_env(),
        };
        let vault = match vault {
            Ok(vault) => vault,
            Err(err) => {
                eprintln!("{err}");
                std::process::exit(2);
            }
        };
        match vault.validate_and_sign_transfer(
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

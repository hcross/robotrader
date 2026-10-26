//! Serialized-contract regression for the simulated vault.
//!
//! The risk-gate unit tests cover behaviour; this integration test owns the
//! wire shape because the node crate already depends on `serde_json`. It uses
//! a non-existent secret path so the deterministic seed is selected.

use robotrader_risk_gate::{SeedInput, SimulatedVault, VaultBootstrap, VaultModeInput};
use std::path::PathBuf;

fn paper_vault() -> SimulatedVault {
    SimulatedVault::load(VaultBootstrap {
        execution_mode: VaultModeInput::Unset,
        secret_file: PathBuf::from("/nonexistent/robotrader-seed-for-test"),
        env_seed: SeedInput::Unset,
    })
    .expect("the default PAPER configuration must construct")
}

#[test]
fn test_serialized_contract_has_no_legacy_keys() {
    let vault = paper_vault();
    let manifest = serde_json::to_value(vault.export_public_manifest()).unwrap();

    for legacy in ["enclave_version", "zeroize_on_drop", "operator_whitelist_count"] {
        assert!(manifest.get(legacy).is_none(), "{legacy} must be absent");
    }
    assert!(manifest.get("master_seed_fingerprint").is_some());
    assert_eq!(
        manifest
            .get("python_private_key_access")
            .and_then(|value| value.as_bool()),
        Some(false)
    );

    for wallet in manifest["wallets"].as_array().unwrap() {
        for legacy in [
            "key_isolation_mode",
            "withdrawal_whitelist_enforced",
            "master_derivation_path",
            "leaf_derivation_path",
            "slip44_coin_type",
        ] {
            assert!(wallet.get(legacy).is_none(), "{legacy} must be absent");
        }
        assert!(wallet.get("target_master_derivation_path").is_some());
        assert!(wallet.get("target_leaf_derivation_path").is_some());
        assert!(wallet.get("target_slip44_coin_type").is_some());
    }

    let receipt = vault
        .validate_and_sign_transfer(
            false,
            "Solana",
            "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN",
            1500.0,
            "SOL",
        )
        .unwrap();
    let receipt_value = serde_json::to_value(receipt).unwrap();
    assert!(receipt_value.get("key_isolation_mode").is_none());
    assert!(receipt_value.get("withdrawal_whitelist_enforced").is_none());
    assert_eq!(receipt_value["simulated"], true);
    assert_eq!(receipt_value["signature_is_chain_valid"], false);
    assert_eq!(receipt_value["whitelist_enforcement"], "SIMULATED");
}

//! Serialized-contract regression for the cryptographic HD vault.
//!
//! Asserts the JSON wire shape of the BIP-32/SLIP-0010 CryptographicVault manifest
//! and checkout receipts.

use robotrader_risk_gate::{
    bs58, sha256, validate_chain_address, verify_checkout_signature, CryptoVaultBootstrap,
    CryptographicVault, SeedInput, VaultModeInput,
};
use std::path::PathBuf;

fn paper_crypto_vault() -> CryptographicVault {
    CryptographicVault::load(CryptoVaultBootstrap {
        execution_mode: VaultModeInput::Unset,
        secret_file: PathBuf::from("/nonexistent/robotrader-seed-for-test"),
        env_seed: SeedInput::Unset,
        allow_test_seed: true,
        allowlist_file: None,
    })
    .expect("the default PAPER configuration with test seed must construct")
}

#[test]
fn test_cryptographic_vault_serialized_manifest_contract() {
    let vault = paper_crypto_vault();
    let manifest = serde_json::to_value(vault.export_public_manifest()).unwrap();

    for legacy in ["enclave_version", "zeroize_on_drop", "operator_whitelist_count"] {
        assert!(manifest.get(legacy).is_none(), "{legacy} must be absent");
    }

    assert_eq!(manifest["vault_mode"], "CRYPTO_HD_BIP32");
    assert_eq!(manifest["simulated"], false);
    assert_eq!(manifest["whitelist_enforcement"], "STRICT_FORMAT_AND_ALLOWLIST");
    assert_eq!(manifest["python_private_key_access"], false);
    assert!(manifest["master_seed_fingerprint"].is_string());
    assert!(manifest["simulation_notice"].is_string());

    let wallets = manifest["wallets"].as_array().unwrap();
    assert_eq!(wallets.len(), 26);

    let mut spendable_count = 0;
    let mut non_spendable_count = 0;

    for wallet in wallets {
        for legacy in [
            "key_isolation_mode",
            "withdrawal_whitelist_enforced",
            "master_derivation_path",
            "leaf_derivation_path",
            "slip44_coin_type",
        ] {
            assert!(wallet.get(legacy).is_none(), "{legacy} must be absent");
        }
        assert_eq!(wallet["simulated"], false);
        assert!(wallet.get("target_master_derivation_path").is_some());
        assert!(wallet.get("target_leaf_derivation_path").is_some());
        assert!(wallet.get("target_slip44_coin_type").is_some());

        let is_spendable = wallet["address_is_spendable"].as_bool().unwrap();
        if is_spendable {
            spendable_count += 1;
        } else {
            non_spendable_count += 1;
        }

        let chain = wallet["chain"].as_str().unwrap();
        let hot_addr = wallet["leaf_hot_address"].as_str().unwrap();
        assert!(
            validate_chain_address(chain, hot_addr).is_ok(),
            "chain {chain} hot address {hot_addr} must validate"
        );
    }

    assert_eq!(spendable_count, 23);
    assert_eq!(non_spendable_count, 3);
}

#[test]
fn test_cryptographic_vault_serialized_receipt_contract() {
    let vault = paper_crypto_vault();
    let sol_desc = vault.derive_wallet_descriptor("leaf-solana").unwrap();
    let sol_dest = sol_desc.master_treasury_address.clone();

    let receipt = vault
        .validate_and_sign_transfer(
            false,
            "leaf-solana",
            &sol_dest,
            2500.0,
            "SOL",
        )
        .unwrap();

    let receipt_val = serde_json::to_value(&receipt).unwrap();
    assert!(receipt_val.get("key_isolation_mode").is_none());
    assert!(receipt_val.get("withdrawal_whitelist_enforced").is_none());

    assert_eq!(receipt_val["vault_mode"], "CRYPTO_HD_BIP32");
    assert_eq!(receipt_val["simulated"], false);
    assert_eq!(receipt_val["signature_is_chain_valid"], false);
    assert_eq!(receipt_val["signature_is_cryptographic"], true);
    assert_eq!(receipt_val["signature_scheme"], "ED25519");
    assert_eq!(receipt_val["whitelist_enforcement"], "STRICT_FORMAT_AND_ALLOWLIST");
    assert_eq!(receipt_val["destination_whitelisted"], true);
    assert_eq!(receipt_val["key_zeroized_after_sign"], true);
    assert_eq!(receipt_val["amount_usd"], 2500.0);
    assert_eq!(receipt_val["token"], "SOL");

    let sig_hex = receipt_val["signature_hex"].as_str().unwrap();
    assert!(sig_hex.starts_with("0x"));
    assert_eq!(sig_hex.len(), 2 + 128);

    // Cryptographic signature verification
    let payload = format!(
        "ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}",
        receipt.chain, receipt.signer_address, receipt.destination_address, 2500.0, "SOL"
    );
    let digest = sha256(payload.as_bytes());
    let sol_pub = bs58::decode(&receipt.signer_address).into_vec().unwrap();

    assert!(verify_checkout_signature(
        &receipt.chain,
        &sol_pub,
        &digest,
        sig_hex
    ));
}

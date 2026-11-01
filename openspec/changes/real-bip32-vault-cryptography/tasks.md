# Tasks — real-bip32-vault-cryptography

## 1. Rust Cryptographic Dependencies & Shared Contracts

- [ ] 1.1 Add pure-Rust cryptographic dependencies to `engine-rs/crates/risk-gate/Cargo.toml` (`k256`, `ed25519-dalek`, `sha2`, `hmac`, `ripemd`, `sha3`, `blake2`, `bs58`, `bech32`). (covers: design D2; invariant no C/C++ FFI)
- [ ] 1.2 Update `SignedTransferReceipt` in `engine-rs/crates/common/src/lib.rs` and `backend/core/schemas.py` with `vault_mode: String`, `signature_is_cryptographic: bool`, and `signature_scheme: String`. (covers: scenario "Receipt carries the simulated whitelist label", scenario "Transfer receipt denies chain validity")
- [ ] 1.3 Ensure `PublicWalletDescriptor` and `SimulatedVaultManifest` in `common/src/lib.rs` support both simulated metadata and cryptographic leaf descriptors (`address_is_spendable: true`, `simulated: false`). (covers: scenario "Wallet descriptors deny spendable addresses", scenario "No legacy vault type name remains public")

## 2. BIP-32, SLIP-0010, & Substrate Key Derivation Engine

- [ ] 2.1 Implement master seed loading, entropy validation (>= 32 bytes), and fail-closed resolution in `risk-gate` (`SECRET_FILE` -> `ENVIRONMENT` -> `MissingLiveSeed` in LIVE / test seed flag in non-live). (covers: scenario "Master seed validation fails closed on insufficient entropy", scenario "Live mode fails closed without explicit master seed", scenario "Secret-mounted seed reports SECRET_FILE provenance", scenario "Environment seed reports ENVIRONMENT provenance", scenario "Live mode without any seed fails closed", scenario "Live mode with an empty secret falls through to the environment seed", scenario "Live mode with an environment-only seed succeeds", scenario "Secret file takes precedence over the environment seed", scenario "Non-live mode uses the deterministic seed with effective mode PAPER", scenario "Unrecognized mode fails closed")
- [ ] 2.2 Implement SLIP-0010 HMAC-SHA512 hardened key derivation for Ed25519 leaves (`leaf-solana`, `leaf-sui`, `leaf-aptos`, `leaf-ton`, `leaf-near`, `leaf-cardano` CIP-1852, `leaf-icp`, `leaf-tezos`). (covers: scenario "Ed25519 SLIP-0010 child key derivation for Solana")
- [ ] 2.3 Implement BIP-32 / BIP-44 HMAC-SHA512 key derivation with Secp256k1 scalar addition and EC point multiplication for 6 EVM leaves (`ethereum`, `hyperliquid`, `bnb`, `avalanche`, `chainlink`, `celo`) and 8 non-EVM leaves (`bitcoin`, `cosmos`, `tron`, `xrp`, `dogecoin`, `stacks`, `flow`, `eos`). (covers: scenario "Secp256k1 BIP-32 child key derivation for Ethereum and Chainlink")
- [ ] 2.4 Implement Substrate mini-secret derivation for `leaf-polkadot` with curve `SR25519_SUBSTRATE`. (covers: scenario "Polkadot Sr25519 key derivation")
- [ ] 2.5 Implement deterministic audit identifiers for non-BIP32 leaves (`leaf-canton`, `leaf-binance-cex`, `leaf-paper-sandbox`) with `address_is_spendable: false`. (covers: scenario "Non-BIP32 leaves derive deterministic audit identifiers", scenario "Non-spendable leaves set address_is_spendable false")

## 3. Spendable Public Address Encoding & Checksums across 26 Leaves

- [ ] 3.1 Implement EVM address generation with Keccak-256 and EIP-55 mixed-case checksum for 6 EVM leaves plus EOS. (covers: scenario "EVM address derivation with EIP-55 checksum")
- [ ] 3.2 Implement Solana Base58 public address encoding from 32-byte Ed25519 public key. (covers: scenario "Solana Base58 address derivation")
- [ ] 3.3 Implement Bitcoin native SegWit Bech32 (`bc1q...`, witness v0) and Cosmos Bech32 (`cosmos1...`) address formatting. (covers: scenario "Bitcoin Bech32 native SegWit address derivation")
- [ ] 3.4 Implement Base58Check address formatting with double-SHA256 checksums for TRON (`T...`), Dogecoin (`D...`), XRP (`r...`), and Tezos (`tz1...`). (covers: scenario "Tron and Dogecoin Base58Check derivation")
- [ ] 3.5 Implement address formatting for Sui (Blake2b-256), Aptos (SHA3-256), NEAR (64-hex), TON (bounceable user-friendly), Cardano (Shelley Bech32 `addr1`), Polkadot (SS58), Stacks (c32check `SP`), Flow (`0x16`), and ICP (principal ID). (covers: requirement "Spendable public address derivation across all 26 catalog leaves")

## 4. Strict Chain Address Validation & Exact Allowlisting

- [ ] 4.1 Implement `validate_chain_address(chain: &str, address: &str) -> Result<(), AddressValidationError>` enforcing chain-specific syntax, length, character set, and checksums. (covers: scenario "EVM invalid address rejected", scenario "EVM invalid EIP-55 checksum rejected", scenario "Solana invalid Base58 address rejected", scenario "Valid destination passes validation")
- [ ] 4.2 Implement `CryptographicVault` destination allowlist evaluator with exact match against operator allowlist, rejecting broad prefix wildcards (`0x`, `bc1q`, `T`, `r`, `D`). (covers: scenario "Syntactically valid but unlisted destination is rejected", scenario "Broad prefix is not treated as a wildcard allowlist entry", scenario "Allowed operator destination is accepted", scenario "Rejected destination does not yield a receipt")

## 5. Cryptographic Checkout Signing, Verification, & Ephemeral Zeroization

- [ ] 5.1 Implement canonical payload construction and 64-byte Ed25519 signing via `ed25519-dalek` for Ed25519 leaves. (covers: scenario "Ed25519 checkout signing and verification")
- [ ] 5.2 Implement canonical payload construction and 64-byte compact Secp256k1 ECDSA signing via `k256` for Secp256k1 leaves. (covers: scenario "Secp256k1 ECDSA checkout signing and verification")
- [ ] 5.3 Implement public verification helper `verify_checkout_signature` for Ed25519 and Secp256k1 signatures. (covers: scenario "Tampered signature fails verification")
- [ ] 5.4 Enforce ephemeral child key zeroization in RAM via volatile writes and verify `key_zeroized_after_sign` against the actual buffer. (covers: scenario "Zeroization flag reflects the observed buffer")
- [ ] 5.5 Enforce kill-switch rejection on cryptographic signing requests. (covers: scenario "Kill switch blocks cryptographic signing", scenario "Kill switch still blocks signing without a binary")
- [ ] 5.6 Produce signed receipts setting `vault_mode: "CRYPTO_HD_BIP32"`, `simulated: false`, `signature_is_chain_valid: false`, `signature_is_cryptographic: true`, and `whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`. (covers: scenario "Accepted receipt reflects the evaluated predicate")

## 6. Vault Backend Selection & Node CLI

- [ ] 6.1 Implement runtime selection in `risk-gate`: `ROBOTRADER_VAULT_MODE` selects `SimulatedVault` (unset/`SIMULATED`) or `CryptographicVault` (`CRYPTO_HD_BIP32`), failing closed on any other value. (covers: scenario "Default mode selects SimulatedVault", scenario "Explicit SIMULATED selects SimulatedVault", scenario "Explicit CRYPTO_HD_BIP32 selects CryptographicVault", scenario "Unknown vault mode fails closed")
- [ ] 6.2 Update `engine-rs/crates/node/src/main.rs` CLI (`--vault-manifest` and `--sign-transfer`) to dispatch to the selected vault backend and support `--vault-allowlist-file`. (covers: scenario "Available binary response is served unchanged", scenario "Available binary returns a valid receipt")

## 7. Python Integration & Control Plane Parity

- [ ] 7.1 Update `backend/core/hierarchy.py` manifest loading and validation to accept both `SIMULATED` and `CRYPTO_HD_BIP32` manifests, preserving 503 fail-closed responses when the binary is unavailable or returns an error. (covers: scenario "Missing binary produces a fail-closed manifest response", scenario "Binary failure produces a fail-closed manifest response", scenario "Missing-binary startup contract remains green", scenario "Python manifest retrieval fails closed without the Rust vault")
- [ ] 7.2 Update `backend/core/hierarchy.py` receipt validation to accept both `SIMULATED` and `CRYPTO_HD_BIP32` receipts, verifying `vault_mode`, `whitelist_enforcement`, and `signature_is_chain_valid: false` before mutating checkout state. (covers: scenario "Checkout without a binary is rejected without mutation", scenario "Rust rejection is propagated without a Python signature", scenario "Python signing and checkout fail closed without the Rust vault")
- [ ] 7.3 Verify that Python continues to hold zero private key custody and never broadcasts Solana transactions. (covers: scenario "Environment key is ignored", scenario "Live tick never broadcasts", scenario "Recorded Solana action is labelled simulated", scenario "Testnet verification exposes no Python-held key")

## 8. Documentation, Target Metadata Verification, & UI Parity

- [ ] 8.1 Update `docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md`, `README.md`, `AGENTS.md`, `docs/architecture.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` to describe `ROBOTRADER_VAULT_MODE` and honest internal checkout receipts. (covers: scenario "Documentation states the simulation and its non-goals", scenario "Operator documentation defines the execution mode", scenario "Repository-wide sweep covers code and process artifacts", scenario "Curve and derivation metadata are target-qualified", scenario "Unqualified derivation field names are absent", scenario "Key isolation mode claims no custody guarantee")
- [ ] 8.2 Update frontend leaf view to display `CRYPTO_HD_BIP32` badge when running in cryptographic mode and `SIMULATED` badge when simulated. (covers: scenario "UI shows a SIMULATED badge")
- [ ] 8.3 Run Rust and Python test suites asserting both `SIMULATED` and `CRYPTO_HD_BIP32` modes and ensuring existing fail-closed tests remain green. (covers: scenario "Vault tests assert simulation fields", scenario "Existing fail-closed tests remain green")

## Verification

- `cd engine-rs && cargo test` → expected: all unit and integration tests pass, including BIP-32 derivation, SLIP-0010 derivation, address formatting, checksum validation, allowlist enforcement, and signature verification.
- `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` → expected: `HardRiskGate::validate` remains under the 50 µs budget (mean < 1 µs).
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: all Python backend tests pass, including missing-binary and fail-closed checkout tests.
- `robotrader-node --vault-manifest` (with `ROBOTRADER_VAULT_MODE=SIMULATED`) → expected: outputs valid `SIMULATED` manifest with `simulated: true` and `address_is_spendable: false`.
- `robotrader-node --vault-manifest` (with `ROBOTRADER_VAULT_MODE=CRYPTO_HD_BIP32` and test seed) → expected: outputs valid `CRYPTO_HD_BIP32` manifest with `simulated: false` and `address_is_spendable: true` for cryptographic leaves.
- `openspec validate real-bip32-vault-cryptography --strict` → expected: validation passes with zero errors.
- `python3 scripts/sdlc/spec-lint.py --change real-bip32-vault-cryptography` → expected: lint passes with zero errors.

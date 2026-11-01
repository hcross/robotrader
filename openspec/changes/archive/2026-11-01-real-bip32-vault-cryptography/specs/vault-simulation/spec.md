## MODIFIED Requirements

### Requirement: The Rust vault identifies itself as simulated
When running in simulated mode (selected when `ROBOTRADER_VAULT_MODE` is unset or set to `SIMULATED`), the public Rust vault type exported by `robotrader-risk-gate` SHALL be named `SimulatedVault`, and no public Rust type or module SHALL retain the name `RustVaultEnclave`. In simulated mode, every manifest produced by `export_public_manifest()` MUST set `vault_mode` to the exact string `SIMULATED`, regardless of seed source. The manifest MUST set a top-level boolean `simulated` to `true`; every wallet descriptor MUST set `simulated` to `true` and `address_is_spendable` to `false`. The manifest MUST carry a non-empty `simulation_notice` string that states addresses are not spendable and signatures are not chain-valid. The manifest MUST report seed provenance in a top-level `seed_source` field whose value is exactly one of `SECRET_FILE`, `ENVIRONMENT`, or `DETERMINISTIC_DEVNET`, selected by the precedence defined in the live-mode requirement. `vault_mode` MUST NOT carry any seed-source value, so it never equals `DOCKER_SECRET_ENCLAVE`, `ENV_VAULT_SEED_ENCLAVE`, or `DEVNET_DETERMINISTIC_ENCLAVE`. When `ROBOTRADER_VAULT_MODE=CRYPTO_HD_BIP32`, `CryptographicVault` SHALL be instantiated instead, setting `vault_mode` to `CRYPTO_HD_BIP32`, `simulated` to `false`, and `address_is_spendable` to `true` for cryptographic leaves.

#### Scenario: Secret-mounted seed reports SECRET_FILE provenance
- **WHEN** the vault loads a non-empty seed from `/run/secrets/robotrader_master_seed` and exports its public manifest in simulated mode
- **THEN** `vault_mode` equals `SIMULATED`
- **THEN** the manifest `simulated` field is `true`
- **THEN** `seed_source` equals `SECRET_FILE`

#### Scenario: Environment seed reports ENVIRONMENT provenance
- **WHEN** the secret file is absent or empty and the vault loads a non-empty `ROBOTRADER_VAULT_MASTER_SEED` and exports its public manifest in simulated mode
- **THEN** `vault_mode` equals `SIMULATED`
- **THEN** `seed_source` equals `ENVIRONMENT`

#### Scenario: Wallet descriptors deny spendable addresses
- **WHEN** the manifest contains a wallet descriptor for any of the 26 ecosystems in simulated mode
- **THEN** that descriptor has `simulated` set to `true`
- **THEN** that descriptor has `address_is_spendable` set to `false`
- **THEN** the top-level `simulation_notice` is non-empty and states that addresses are not spendable

#### Scenario: No legacy vault type name remains public
- **WHEN** the `robotrader-risk-gate` public API is compiled and inspected
- **THEN** the vault type name is `SimulatedVault` (or `CryptographicVault` for cryptographic mode)
- **THEN** no public type or module named `RustVaultEnclave` is exported

### Requirement: No vault surface claims an implemented cryptographic guarantee
When running in simulated mode, the manifest, transfer receipts, API responses, UI text, documentation, source docstrings and comments, test names, and process artifacts MUST NOT state that BIP-32, BIP-44, SLIP-0010, CIP-1852, secp256k1, ed25519, sr25519, real address encoding, or chain-valid signing is performed. A retained `curve` identifier MAY name a target scheme only when the same descriptor sets `simulated` to `true`, `address_is_spendable` to `false`, and the manifest `simulation_notice` qualifies the value as a target rather than an implementation. In simulated mode, derivation and coin-type metadata MUST be exposed only as target metadata: `target_master_derivation_path`, `target_leaf_derivation_path`, and `target_slip44_coin_type`. `key_isolation_mode` MUST be removed or set to a `SIMULATED_*` value that claims neither HD derivation, zeroization, custody, nor exchange-withdrawal enforcement; the values `RUST_ENCLAVE_HD_ZEROIZE` and `RUST_ENCLAVE_HMAC_TRADE_ONLY` MUST NOT appear. In both simulated and cryptographic modes, no transfer receipt MAY claim to be a raw broadcastable on-chain transaction: `signature_is_chain_valid` MUST remain `false` for all checkout transfer receipts.

#### Scenario: Curve and derivation metadata are target-qualified
- **WHEN** a wallet descriptor exposes `curve`, `target_master_derivation_path`, `target_leaf_derivation_path`, or `target_slip44_coin_type` in simulated mode
- **THEN** the same descriptor sets `simulated` to `true`
- **THEN** the descriptor sets `address_is_spendable` to `false`
- **THEN** the manifest `simulation_notice` identifies all of these values as target metadata, not implemented derivation

#### Scenario: Unqualified derivation field names are absent
- **WHEN** the simulated manifest is serialized
- **THEN** it contains `target_master_derivation_path`, `target_leaf_derivation_path`, and `target_slip44_coin_type`
- **THEN** it contains no `master_derivation_path`, `leaf_derivation_path`, or `slip44_coin_type` field

#### Scenario: Key isolation mode claims no custody guarantee
- **WHEN** a simulated wallet descriptor contains a `key_isolation_mode` value
- **THEN** the value starts with `SIMULATED_` and claims neither HD derivation, zeroization, custody, nor exchange-withdrawal enforcement
- **THEN** the values `RUST_ENCLAVE_HD_ZEROIZE` and `RUST_ENCLAVE_HMAC_TRADE_ONLY` do not appear in the manifest

#### Scenario: Transfer receipt denies chain validity
- **WHEN** the simulated vault signs a transfer and returns a receipt
- **THEN** the receipt sets `simulated` to `true`
- **THEN** the receipt sets `signature_is_chain_valid` to `false`
- **THEN** the receipt sets `signature_is_cryptographic` to `false`

#### Scenario: Repository-wide sweep covers code and process artifacts
- **WHEN** the repository is searched for statements that derivation, zeroization, custody, whitelist enforcement, or signing is implemented, including `docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md`, `README.md`, `AGENTS.md`, `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md`, `docs/architecture.md`, `sdlc/checklists/dev.md`, `openspec/config.yaml`, `backend/server.py`, `backend/core/hierarchy.py`, `engine-rs/crates/risk-gate/src/vault.rs`, and the frontend sources
- **THEN** simulated surfaces are explicitly qualified as simulated, and cryptographic claims are strictly scoped to `CryptographicVault` under `ROBOTRADER_VAULT_MODE=CRYPTO_HD_BIP32`
- **THEN** no docstring, comment, checklist item, or configuration line claims a checkout receipt is directly broadcastable as a raw transaction to a public blockchain mempool

### Requirement: Python manifest retrieval fails closed without the Rust vault
`HierarchicalFleetManager` MUST NOT construct, cache, or serve a Python-generated manifest. When `robotrader-node --vault-manifest` is absent, times out, exits non-zero, or returns unparsable or empty JSON, `GET /api/v1/vault/manifest` MUST return HTTP status 503 with an error body and MUST NOT include a `wallets` array, a master seed fingerprint, a whitelist count, or any hardcoded fallback value. The backend MUST remain importable and startable without the Rust binary: constructing `HierarchicalFleetManager` MUST NOT raise, and its `vault_manifest` MUST be an empty mapping with no `wallets` key, or absent, so that no fabricated value is cached. Python manifest validation MUST accept both `SIMULATED` manifests (with `vault_mode: SIMULATED`, `simulated: true`, `address_is_spendable: false`) and `CRYPTO_HD_BIP32` manifests (with `vault_mode: CRYPTO_HD_BIP32`, `simulated: false`, `address_is_spendable: true` for cryptographic leaves). The pre-existing endpoint contracts asserted by `backend/tests/test_missing_binary.py` MUST remain unchanged: `/api/v1/status`, `/api/v1/hierarchy`, `/api/v1/backtest/run`, the leaf backtest, `/api/v1/policy/regime`, `/api/v1/chat`, and `/api/v1/risk/kill` keep their 503 responses, and `/api/v1/health` keeps its 200 response.

#### Scenario: Missing binary produces a fail-closed manifest response
- **WHEN** no `robotrader-node` binary exists in either candidate path and the manifest endpoint is called
- **THEN** the response status is HTTP 503
- **THEN** the body contains no `wallets` array
- **THEN** the body contains no master seed fingerprint and no whitelist count

#### Scenario: Binary failure produces a fail-closed manifest response
- **WHEN** `robotrader-node --vault-manifest` exits non-zero or emits unparsable JSON and the manifest endpoint is called
- **THEN** the response status is HTTP 503
- **THEN** no manifest is served from a Python fallback

#### Scenario: Available binary response is served unchanged
- **WHEN** `robotrader-node --vault-manifest` returns a valid manifest
- **THEN** the endpoint returns that manifest's `wallets`, `vault_mode`, and flags without Python substituting values

#### Scenario: Missing-binary startup contract remains green
- **WHEN** the backend starts with no `robotrader-node` binary and `backend/tests/test_missing_binary.py` runs
- **THEN** the backend imports and starts without an exception
- **THEN** the tested status, hierarchy, backtest, policy-regime, chat, kill-switch, and health responses match their pre-existing contracts
- **THEN** `GET /api/v1/vault/manifest` returns HTTP 503 with no fabricated manifest

### Requirement: Python signing and checkout fail closed without the Rust vault
`sign_transfer_in_rust_enclave` MUST NOT produce a signature with a Python HMAC or any other Python-local primitive. When the Rust binary is unavailable or rejects the transfer, it MUST return a failure status and MUST NOT include `signature_hex`, `destination_whitelisted`, or `key_zeroized_after_sign`. `checkout_funds` MUST return a rejection status and MUST NOT mutate `total_capital_usd`, any leaf allocation, `checkout_history`, or the dry-powder reserve. The receipt validation in Python MUST accept valid receipts from `SimulatedVault` (`vault_mode: SIMULATED`, `simulated: true`, `whitelist_enforcement: "SIMULATED"`, `signature_is_chain_valid: false`, `signature_is_cryptographic: false`) and from `CryptographicVault` (`vault_mode: CRYPTO_HD_BIP32`, `simulated: false`, `whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`, `signature_is_chain_valid: false`, `signature_is_cryptographic: true`). The existing kill-switch rejection MUST remain in force and MUST NOT be weakened or bypassed by the fail-closed path.

#### Scenario: Checkout without a binary is rejected without mutation
- **WHEN** no Rust binary is available and `checkout_funds` is called with a positive amount
- **THEN** the returned status is a rejection
- **THEN** the result contains no `signature_hex`
- **THEN** `total_capital_usd`, leaf allocations, `checkout_history`, and the dry-powder reserve are unchanged

#### Scenario: Rust rejection is propagated without a Python signature
- **WHEN** the Rust binary rejects a destination as not whitelisted
- **THEN** the returned status is `rejected_by_rust_enclave`
- **THEN** no Python signature is generated and no checkout state is mutated

#### Scenario: Kill switch still blocks signing without a binary
- **WHEN** the kill switch is active and no Rust binary is available
- **THEN** the returned status is a rejection
- **THEN** no signature is produced

#### Scenario: Available binary returns a valid receipt
- **WHEN** the Rust binary is available and accepts a destination and amount in simulated mode
- **THEN** the returned receipt is the binary's receipt with `simulated: true`, `signature_is_chain_valid: false`, and `signature_is_cryptographic: false`
- **THEN** the checkout proceeds on the validated contract

### Requirement: Python holds no Solana private key and never broadcasts
`SolanaWalletTool` MUST NOT read the `SOLANA_PRIVATE_KEY` environment variable, accept a private key argument, construct a signing `Keypair`, or call the Solana `sendTransaction` RPC method. `run_live_testnet_tick` MUST NOT call `transfer_sol(..., simulate_only=False)` and MUST NOT broadcast a transaction; any Solana action it records MUST be explicitly simulated, MUST carry a `SIMULATED` source label, and MUST NOT carry a transaction signature. `GET /api/v1/testnet/verify` MUST NOT expose a public key derived from Python-held private key material. `.env.example` MUST NOT advertise `SOLANA_PRIVATE_KEY` as a supported credential.

#### Scenario: Environment key is ignored
- **WHEN** `SOLANA_PRIVATE_KEY` is set in the environment and `SolanaWalletTool` is constructed
- **THEN** the tool holds no signing keypair
- **THEN** no public key is derived from that environment value

#### Scenario: Live tick never broadcasts
- **WHEN** `run_live_testnet_tick` executes its Solana branch
- **THEN** no `sendTransaction` RPC call is issued
- **THEN** no execution record carries a transaction signature

#### Scenario: Recorded Solana action is labelled simulated
- **WHEN** the live tick records a Solana execution or self-transfer outcome
- **THEN** the record's source label is `SIMULATED`
- **THEN** the record does not claim a broadcast or a confirmed on-chain transfer

#### Scenario: Testnet verification exposes no Python-held key
- **WHEN** `/api/v1/testnet/verify` is called
- **THEN** the response does not contain a public key derived from Python-held private key material
- **THEN** any wallet balance reported is read from a configured public address only

### Requirement: Live mode fails closed without seed material
Both `SimulatedVault` and `CryptographicVault` MUST recognize exactly four execution modes from `ROBOTRADER_EXECUTION_MODE`: `BACKTEST`, `PAPER`, `SIMULATED`, and `LIVE`. An unset variable MUST select `PAPER`. Any other non-empty value MUST cause vault construction to fail closed, with no manifest and no signature, rather than defaulting silently. Seed selection MUST apply this precedence: a readable `/run/secrets/robotrader_master_seed` whose trimmed content is non-empty selects `SECRET_FILE` and the environment variable is ignored; otherwise a non-empty trimmed `ROBOTRADER_VAULT_MASTER_SEED` (or `ROBOTRADER_VAULT_MASTER_SEED_HEX` for `CryptographicVault`) selects `ENVIRONMENT`; otherwise, in `LIVE` mode construction MUST fail, and in `BACKTEST`, `PAPER`, or `SIMULATED` mode the deterministic devnet seed selects `DETERMINISTIC_DEVNET` (for `CryptographicVault`, test seed is allowed only if `ROBOTRADER_VAULT_ALLOW_TEST_SEED=1`). An unreadable or empty secret file MUST be treated as absent and MUST fall through to the environment seed. In `LIVE` mode the deterministic devnet seed MUST NOT be used.

#### Scenario: Live mode without any seed fails closed
- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE`, the secret file is absent, and the environment seed is absent
- **THEN** vault construction fails
- **THEN** no manifest and no signature are produced
- **THEN** the deterministic devnet seed is not used

#### Scenario: Live mode with an empty secret falls through to the environment seed
- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE`, the secret file exists but contains only whitespace, and a non-empty environment seed is present
- **THEN** vault construction succeeds
- **THEN** the manifest reports `seed_source: ENVIRONMENT`

#### Scenario: Live mode with an environment-only seed succeeds
- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE`, the secret file is absent, and a non-empty environment seed is present
- **THEN** vault construction succeeds
- **THEN** the manifest reports `seed_source: ENVIRONMENT`

#### Scenario: Secret file takes precedence over the environment seed
- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE`, the secret file contains a non-empty seed, and the environment seed is also non-empty
- **THEN** vault construction succeeds
- **THEN** the manifest reports `seed_source: SECRET_FILE`

#### Scenario: Non-live mode uses the deterministic seed with effective mode PAPER
- **WHEN** `ROBOTRADER_EXECUTION_MODE` is unset and neither seed source is configured
- **THEN** the effective mode is `PAPER`
- **THEN** vault construction succeeds with the deterministic devnet seed
- **THEN** the manifest reports `seed_source: DETERMINISTIC_DEVNET`

#### Scenario: Unrecognized mode fails closed
- **WHEN** `ROBOTRADER_EXECUTION_MODE` holds a non-empty value outside `BACKTEST`, `PAPER`, `SIMULATED`, and `LIVE`
- **THEN** vault construction fails
- **THEN** no manifest and no signature are produced
- **THEN** the vault does not silently select `PAPER`

### Requirement: Receipt safety flags are derived and the whitelist is labelled simulated
In `SimulatedVault`, `destination_whitelisted` MUST be assigned from the whitelist predicate evaluated for the same destination in the same signing call and MUST NOT be a literal `true`. No receipt MUST be produced when the predicate returns `false`. `key_zeroized_after_sign` MUST be the result of an actual post-sign check of the ephemeral key buffer and MUST NOT be a compile-time literal; if the check observes any non-zero byte, the field MUST be `false`. The simulated whitelist contract MUST have exactly this shape: the top-level manifest MUST carry `whitelist_enforcement: "SIMULATED"`; every wallet descriptor MUST remove `withdrawal_whitelist_enforced`, and if the field is retained for compatibility it MUST be `false` and MUST NOT be `true`; every signed simulated receipt MUST carry `whitelist_enforcement: "SIMULATED"`. For `CryptographicVault`, `whitelist_enforcement` MUST be `"STRICT_FORMAT_AND_ALLOWLIST"`, requiring valid address syntax/checksum and exact allowlist matching.

#### Scenario: Rejected destination does not yield a receipt
- **WHEN** the whitelist predicate returns `false` for a destination
- **THEN** signing returns an error
- **THEN** no receipt containing `destination_whitelisted` is produced

#### Scenario: Zeroization flag reflects the observed buffer
- **WHEN** the post-sign check observes a non-zero byte in the ephemeral key buffer
- **THEN** `key_zeroized_after_sign` is `false`
- **THEN** a fully zeroed buffer yields `key_zeroized_after_sign` equal to `true`

#### Scenario: Manifest carries the top-level simulated whitelist label
- **WHEN** the simulated manifest is exported
- **THEN** the top-level `whitelist_enforcement` equals `SIMULATED`
- **THEN** no wallet descriptor sets `withdrawal_whitelist_enforced` to `true`

#### Scenario: Receipt carries the simulated whitelist label
- **WHEN** the simulated vault returns a signed receipt
- **THEN** the receipt's `whitelist_enforcement` equals `SIMULATED`
- **THEN** the receipt's `destination_whitelisted` equals the evaluated predicate result

#### Scenario: Accepted receipt reflects the evaluated predicate
- **WHEN** the whitelist predicate returns `true` for a destination and a receipt is produced
- **THEN** the receipt's `destination_whitelisted` is `true` because the predicate was evaluated in that call
- **THEN** the receipt does not claim production whitelist enforcement

### Requirement: Documentation, UI, and tests present the simulation truthfully
`docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md`, `README.md`, `AGENTS.md`, `docs/architecture.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` MUST describe the vault mode architecture truthfully: `ROBOTRADER_VAULT_MODE` defaults to `SIMULATED`, where non-goals (no real derivation, non-spendable addresses, non-chain-valid receipts) hold strictly; when `ROBOTRADER_VAULT_MODE=CRYPTO_HD_BIP32`, real BIP-32/SLIP-0010 derivation and Ed25519/Secp256k1 signing are active, while transfer receipts continue to state `signature_is_chain_valid: false` because receipts are internal authorization tokens rather than broadcastable mempool transactions. Tests that cover the simulated vault MUST assert `vault_mode: SIMULATED`, `simulated: true`, `address_is_spendable: false`, `signature_is_chain_valid: false`, and `signature_is_cryptographic: false`.

#### Scenario: Documentation states the simulation and its non-goals
- **WHEN** a reader opens the vault document, README, AGENTS.md, architecture document, or ADR-0003
- **THEN** the vault's dual-mode architecture is described truthfully
- **THEN** the document states that simulated mode implements no real derivation, and that cryptographic mode receipts authorize internal checkout transfers rather than raw chain transactions

#### Scenario: Operator documentation defines the execution mode
- **WHEN** a reader opens `README.md` or `.env.example`
- **THEN** `ROBOTRADER_EXECUTION_MODE` is documented with the values `BACKTEST`, `PAPER`, `SIMULATED`, and `LIVE`
- **THEN** the `PAPER` default and the security consequence of an unset or unrecognized value are stated

#### Scenario: UI shows a SIMULATED badge
- **WHEN** a leaf detail view renders the wallet vault block for a simulated vault
- **THEN** a visible `SIMULATED` badge is displayed
- **THEN** the view does not claim real custody or a spendable address

#### Scenario: Vault tests assert simulation fields
- **WHEN** the Rust and Python vault test suites run in simulated mode
- **THEN** they assert `vault_mode: SIMULATED`, `simulated: true`, `address_is_spendable: false`, `signature_is_chain_valid: false`, and `signature_is_cryptographic: false`
- **THEN** no test relies on the removed Python fallback manifest or signer

#### Scenario: Existing fail-closed tests remain green
- **WHEN** the kill-switch, negative-amount, unknown-leaf, and `backend/tests/test_missing_binary.py` suites run
- **THEN** those rejections and endpoint contracts still hold
- **THEN** the dual-mode change does not weaken any existing rejection path

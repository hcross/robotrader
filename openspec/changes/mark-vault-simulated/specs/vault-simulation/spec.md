## ADDED Requirements

### Requirement: The Rust vault identifies itself as simulated

The public Rust vault type exported by `robotrader-risk-gate` SHALL be named `SimulatedVault`, and no public Rust type or module SHALL retain the name `RustVaultEnclave`. Every manifest produced by `export_public_manifest()` MUST set `vault_mode` to the exact string `SIMULATED`, regardless of seed source. The manifest MUST set a top-level boolean `simulated` to `true`; every wallet descriptor MUST set `simulated` to `true` and `address_is_spendable` to `false`. The manifest MUST carry a non-empty `simulation_notice` string that states addresses are not spendable and signatures are not chain-valid. The seed source MUST be reported in a field other than `vault_mode`, so `vault_mode` never carries `DOCKER_SECRET_ENCLAVE`, `ENV_VAULT_SEED_ENCLAVE`, or `DEVNET_DETERMINISTIC_ENCLAVE`.

#### Scenario: Manifest reports SIMULATED with a secret-mounted seed

- **WHEN** the vault loads a non-empty seed from `/run/secrets/robotrader_master_seed` and exports its public manifest
- **THEN** `vault_mode` equals `SIMULATED`
- **THEN** the manifest `simulated` field is `true`
- **THEN** the seed source is reported separately from `vault_mode`

#### Scenario: Manifest reports SIMULATED with the non-live devnet seed

- **WHEN** the vault runs outside live mode with no configured seed and exports its public manifest
- **THEN** `vault_mode` equals `SIMULATED`
- **THEN** the seed source is reported as the deterministic devnet seed
- **THEN** `vault_mode` does not contain `DEVNET_DETERMINISTIC_ENCLAVE`

#### Scenario: Wallet descriptors deny spendable addresses

- **WHEN** the manifest contains a wallet descriptor for any of the 26 ecosystems
- **THEN** that descriptor has `simulated` set to `true`
- **THEN** that descriptor has `address_is_spendable` set to `false`
- **THEN** the top-level `simulation_notice` is non-empty and states that addresses are not spendable

#### Scenario: No legacy vault type name remains public

- **WHEN** the `robotrader-risk-gate` public API is compiled and inspected
- **THEN** the vault type name is `SimulatedVault`
- **THEN** no public type or module named `RustVaultEnclave` is exported

### Requirement: No vault surface claims an implemented cryptographic guarantee

The manifest, transfer receipts, API responses, UI text, documentation, and test names MUST NOT state that BIP-32, BIP-44, SLIP-0010, CIP-1852, secp256k1, ed25519, sr25519, real address encoding, or chain-valid signing is performed. A retained `curve` identifier MAY name a target scheme only when the same descriptor sets `simulated` to `true`, and all vault-facing text MUST qualify the identifier as a target rather than an implementation. No vault-facing text MAY describe a derived address as spendable or a receipt as broadcastable to a chain.

#### Scenario: Manifest curve metadata is qualified as a target

- **WHEN** a wallet descriptor exposes a `curve` value that names secp256k1, ed25519, or sr25519
- **THEN** the same descriptor sets `simulated` to `true`
- **THEN** the manifest `simulation_notice` identifies the value as a target scheme, not an implemented one

#### Scenario: Transfer receipt denies chain validity

- **WHEN** the simulated vault signs a transfer and returns a receipt
- **THEN** the receipt sets `simulated` to `true`
- **THEN** the receipt sets `signature_is_chain_valid` to `false`

#### Scenario: No repository text asserts the false guarantee

- **WHEN** the vault documentation, README, AGENTS.md, ADR-0003, and UI source are searched for statements that derivation or signing is implemented
- **THEN** every occurrence of a cryptographic scheme name is qualified as a target or as simulated
- **THEN** no statement claims a derived address is spendable or a receipt is broadcastable

### Requirement: Python manifest retrieval fails closed without the Rust vault

`HierarchicalFleetManager` MUST NOT construct, cache, or serve a Python-generated manifest. When `robotrader-node --vault-manifest` is absent, times out, exits non-zero, or returns unparsable or empty JSON, `GET /api/v1/vault/manifest` MUST return HTTP status 503 with an error body and MUST NOT include a `wallets` array, a master seed fingerprint, a whitelist count, or any hardcoded fallback value. The backend MAY start without the Rust binary, but every vault-dependent endpoint MUST fail closed until the binary answers.

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
- **THEN** the endpoint returns that manifest's `wallets`, `vault_mode: SIMULATED`, and simulation flags without Python substituting values

### Requirement: Python signing and checkout fail closed without the Rust vault

`sign_transfer_in_rust_enclave` MUST NOT produce a signature with a Python HMAC or any other Python-local primitive. When the Rust binary is unavailable or rejects the transfer, it MUST return a failure status and MUST NOT include `signature_hex`, `destination_whitelisted`, or `key_zeroized_after_sign`. `checkout_funds` MUST return a rejection status and MUST NOT mutate `total_capital_usd`, any leaf allocation, `checkout_history`, or the dry-powder reserve. The existing kill-switch rejection MUST remain in force and MUST NOT be weakened or bypassed by the fail-closed path.

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

#### Scenario: Available binary returns a simulated receipt

- **WHEN** the Rust binary is available and accepts a destination and amount
- **THEN** the returned receipt is the binary's receipt with `simulated: true` and `signature_is_chain_valid: false`
- **THEN** the checkout proceeds on the simulated contract only

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
- **THEN** the response does not contain a public key derived from a Python-held private key
- **THEN** any wallet balance reported is read from a configured public address only

### Requirement: Live mode fails closed without a secret-mounted seed

The vault MUST select live mode only from explicit execution-mode configuration (`ROBOTRADER_EXECUTION_MODE=LIVE`); when the variable is unset or holds an unrecognized value, the mode MUST default to `PAPER` and MUST NOT be live. In live mode, a missing, unreadable, or whitespace-only `/run/secrets/robotrader_master_seed` and a missing or empty `ROBOTRADER_VAULT_MASTER_SEED` MUST cause vault construction to fail: vault CLI commands MUST exit non-zero and vault-backed endpoints MUST return a fail-closed error. In live mode the deterministic devnet seed MUST NOT be used. In `BACKTEST`, `PAPER`, and `SIMULATED` modes the deterministic devnet seed MAY be used, and the manifest MUST still report `vault_mode: SIMULATED` with the seed source reported explicitly.

#### Scenario: Live mode without any seed fails closed

- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE` and neither a secret file nor an environment seed is present
- **THEN** vault construction fails
- **THEN** no manifest and no signature are produced
- **THEN** the deterministic devnet seed is not used

#### Scenario: Live mode with an empty secret fails closed

- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE` and the secret file exists but contains only whitespace
- **THEN** vault construction fails
- **THEN** no manifest and no signature are produced

#### Scenario: Live mode with a valid secret remains simulated

- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE` and the secret file contains a non-empty seed
- **THEN** vault construction succeeds
- **THEN** the manifest reports `vault_mode: SIMULATED` and the secret seed source

#### Scenario: Non-live mode may use the deterministic seed

- **WHEN** `ROBOTRADER_EXECUTION_MODE` is unset or `PAPER` and no seed is configured
- **THEN** vault construction succeeds with the deterministic devnet seed
- **THEN** the manifest reports `vault_mode: SIMULATED` and the devnet seed source

#### Scenario: Unset mode never selects live

- **WHEN** `ROBOTRADER_EXECUTION_MODE` is unset
- **THEN** the effective mode is `PAPER`
- **THEN** missing seed material does not cause a live-mode failure

### Requirement: Receipt safety flags are derived and the whitelist is labelled simulated

`destination_whitelisted` MUST be assigned from the whitelist predicate evaluated for the same destination in the same signing call and MUST NOT be a literal `true`. No receipt MUST be produced when the predicate returns `false`. `key_zeroized_after_sign` MUST be the result of an actual post-sign check of the ephemeral key buffer and MUST NOT be a compile-time literal; if the check observes any non-zero byte, the field MUST be `false`. The manifest and receipts MUST label whitelist enforcement as simulated through a `whitelist_enforcement` value of `SIMULATED`, and the per-wallet `withdrawal_whitelist_enforced` boolean MUST NOT remain an unqualified `true` presented as a production guarantee.

#### Scenario: Rejected destination does not yield a receipt

- **WHEN** the whitelist predicate returns `false` for a destination
- **THEN** signing returns an error
- **THEN** no receipt containing `destination_whitelisted` is produced

#### Scenario: Zeroization flag reflects the observed buffer

- **WHEN** the post-sign check observes a non-zero byte in the ephemeral key buffer
- **THEN** `key_zeroized_after_sign` is `false`
- **THEN** a fully zeroed buffer yields `key_zeroized_after_sign` equal to `true`

#### Scenario: Manifest labels whitelist enforcement simulated

- **WHEN** the manifest is exported
- **THEN** `whitelist_enforcement` equals `SIMULATED`
- **THEN** no wallet descriptor presents whitelist enforcement as a production guarantee

#### Scenario: Accepted receipt reflects the evaluated predicate

- **WHEN** the whitelist predicate returns `true` for a destination
- **THEN** the receipt's `destination_whitelisted` equals that evaluated result
- **THEN** the receipt also reports the simulated whitelist label

### Requirement: Documentation, UI, and tests present the simulation truthfully

`docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md`, `README.md`, `AGENTS.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` MUST describe the vault as `SIMULATED` and MUST state the non-goals: no real BIP-32/BIP-44/SLIP-0010/secp256k1/ed25519/sr25519 derivation, no real address encoding, no chain-valid signature, and no mainnet custody. The leaf UI MUST render a visible `SIMULATED` vault badge and MUST NOT claim real custody or spendable addresses. Tests that cover the vault MUST assert `vault_mode: SIMULATED`, `simulated: true`, `address_is_spendable: false`, and `signature_is_chain_valid: false`; they MUST NOT assert a signature length or encoding as proof of chain validity, and tests MUST NOT pass by exercising a removed Python fallback.

#### Scenario: Documentation states the simulation and its non-goals

- **WHEN** a reader opens the vault document, README, AGENTS.md, or ADR-0003
- **THEN** the vault is identified as simulated
- **THEN** the document states that no real derivation, address encoding, chain signature, or mainnet custody is implemented

#### Scenario: UI shows a SIMULATED badge

- **WHEN** a leaf detail view renders the wallet vault block
- **THEN** a visible `SIMULATED` badge is displayed
- **THEN** the view does not claim real custody or a spendable address

#### Scenario: Vault tests assert simulation fields

- **WHEN** the Rust and Python vault test suites run
- **THEN** they assert `vault_mode: SIMULATED`, `simulated: true`, `address_is_spendable: false`, and `signature_is_chain_valid: false`
- **THEN** no test relies on the removed Python fallback manifest or signer

#### Scenario: Existing fail-closed tests remain green

- **WHEN** the kill-switch, negative-amount, and unknown-leaf rejection tests run
- **THEN** those rejections still occur
- **THEN** the simulation change does not weaken any existing rejection path

# Tasks — mark-vault-simulated

> Design: [`design.md`](design.md). Spec: [`specs/vault-simulation/spec.md`](specs/vault-simulation/spec.md). This list orders the work; the spec defines the required behaviour.

## 1. Rust contract types (`engine-rs/crates/common/src/lib.rs`)

- [x] 1.1 Rename `VaultEnclaveManifest` to `SimulatedVaultManifest`; add `ExecutionMode` (`BACKTEST`, `PAPER`, `SIMULATED`, `LIVE`) and `SeedSource` (`SECRET_FILE`, `ENVIRONMENT`, `DETERMINISTIC_DEVNET`) enums with `SCREAMING_SNAKE_CASE` serde. (covers: "The Rust vault identifies itself as simulated"; design D1, D2, D8, D9)
- [x] 1.2 Update `PublicWalletDescriptor` to carry `simulated: bool`, `address_is_spendable: bool`, `target_slip44_coin_type`, `target_master_derivation_path`, `target_leaf_derivation_path`; remove `key_isolation_mode` and `withdrawal_whitelist_enforced`. (covers: "Wallet descriptors deny spendable addresses"; "Unqualified derivation field names are absent"; design D3)
- [x] 1.3 Replace the manifest fields with `vault_version`, `vault_mode`, `execution_mode`, `simulated`, `simulation_notice`, `seed_source`, `master_seed_fingerprint`, `python_private_key_access`, `whitelist_enforcement`, `simulated_whitelist_entry_count`, `canonical_bridge_contracts_count`, `wallets`; remove `enclave_version`, `zeroize_on_drop`, and `operator_whitelist_count`. (covers: "The Rust vault identifies itself as simulated"; "Manifest carries the top-level simulated whitelist label"; design D2)
- [x] 1.4 Add `simulated: bool`, `signature_is_chain_valid: bool`, and `whitelist_enforcement: String` to `SignedTransferReceipt`; document that `signature_hex` is a simulated HMAC audit token, not a chain signature. (covers: "Transfer receipt denies chain validity"; "Receipt carries the simulated whitelist label"; design D4)
- [x] 1.5 Update the `CryptographicCurve` doc comment and every scheme-name comment in this file to say "target scheme metadata only; not implemented by the simulated vault". (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)

## 2. Rust simulated vault (`engine-rs/crates/risk-gate/src/vault.rs`)

- [x] 2.1 Rename `RustVaultEnclave` to `SimulatedVault`; update `engine-rs/crates/risk-gate/src/lib.rs` to re-export `SimulatedVault`, `VaultBootstrap`, `VaultInitError`, and `ZeroizingBytes`. (covers: "No legacy vault type name remains public"; design D1)
- [x] 2.2 Add `VaultBootstrap { execution_mode: VaultModeInput, secret_file: PathBuf, env_seed: SeedInput }`, where each input is `Unset | Value(String) | NonUnicode`; add `VaultInitError` with `InvalidExecutionMode`, `EmptyExecutionMode`, `NonUnicodeExecutionMode`, `InvalidEnvironmentSeedEncoding`, and `MissingLiveSeed`, each with the exact `Display` text from design D7/D8; add `SimulatedVault::load(VaultBootstrap)` / `from_env()`; remove the `Default` impl. (covers: "Unrecognized mode fails closed"; design D7, D8, F08, F20)
- [x] 2.3 Implement mode parsing and seed precedence exactly as the design's tables: absent → `PAPER`; exact, case-sensitive equality for the four values; empty, whitespace-only, `paper`, `PAPER `, ` Paper`, unknown, and non-Unicode → fail closed; secret file → environment seed → live failure or deterministic devnet seed. Set `seed_source` and `execution_mode` from the selected values. (covers: all live-mode and seed scenarios; design D8, D9, D10; F04)
- [x] 2.4 Remove BIP-32/BIP-44/SLIP-0010/HD/zeroize claims from `sha256`, `hmac_sha256`, `derive_private_key`, `format_public_address`, and the chain-spec comments; describe the HMAC and character mappers as simulated derivation and non-spendable formatting. (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)
- [x] 2.5 Build each descriptor with `simulated: true`, `address_is_spendable: false`, the three `target_*` fields, and no `key_isolation_mode` or `withdrawal_whitelist_enforced`. (covers: "Wallet descriptors deny spendable addresses"; "Curve and derivation metadata are target-qualified"; design D3)
- [x] 2.6 Build the manifest with `vault_version`, `vault_mode: "SIMULATED"`, `execution_mode`, `simulated: true`, the non-empty `simulation_notice`, `seed_source`, `whitelist_enforcement: "SIMULATED"`, `simulated_whitelist_entry_count`, and `python_private_key_access: false`. (covers: "The Rust vault identifies itself as simulated"; "Manifest carries the top-level simulated whitelist label"; design D2, D11)
- [x] 2.7 Rename `DEFAULT_WHITELISTED_PREFIXES` to `SIMULATED_WHITELIST_PREFIXES` and document the predicate as a simulated prefix filter, not a production allowlist; keep the prefix-matching behavior unchanged. (covers: "Receipt safety flags are derived and the whitelist is labelled simulated"; design D2, D6)
- [x] 2.8 Evaluate the whitelist predicate once, reject with `RiskRejection::VaultSigningRejected` when it is `false`, and assign `destination_whitelisted` from that evaluated value; construct no receipt on rejection. (covers: "Rejected destination does not yield a receipt"; "Accepted receipt reflects the evaluated predicate"; design D6)
- [x] 2.9 Add `ZeroizingBytes::is_zeroized()`; after `zeroize_now()`, set `key_zeroized_after_sign` from the observed buffer; set `simulated: true`, `signature_is_chain_valid: false`, and `whitelist_enforcement: "SIMULATED"` on every receipt. (covers: "Zeroization flag reflects the observed buffer"; "Transfer receipt denies chain validity"; design D4, D5)
- [x] 2.10 Update the `RiskRejection::VaultSigningRejected` error string and every vault doc comment to say "simulated vault"; no comment may describe an address as spendable or a receipt as broadcastable. (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)

## 3. Rust CLI and tests (`engine-rs/crates/node/src/main.rs`, `engine-rs/crates/risk-gate/src/lib.rs`)

- [x] 3.1 Construct the vault with `SimulatedVault::from_env()` in the `--vault-manifest` and `--sign-transfer` paths; add an optional `--vault-secret-file <path>` override passed into `VaultBootstrap` for hermetic tests; on `VaultInitError`, print the display text to stderr and exit `2` with empty stdout. (covers: "Unrecognized mode fails closed"; "Live mode without any seed fails closed"; design D7, D8, D9; F19)
- [x] 3.2 Replace `test_vault_enclave_26_chains_hd_derivation_and_whitelist_signing` with `test_simulated_vault_manifest_contract`: 26 wallets, `vault_mode: SIMULATED`, `simulated`, `address_is_spendable == false`, target fields present, legacy fields absent, `seed_source` valid. (covers: "Wallet descriptors deny spendable addresses"; "Unqualified derivation field names are absent"; design D2, D3)
- [x] 3.3 Add `test_execution_mode_parsing`: absent → `PAPER`; the four exact values; empty/whitespace, `paper`, `PAPER `, ` Paper`, unknown, and non-Unicode → error. Use `VaultModeInput` rather than mutating process-global environment variables. (covers: "Unrecognized mode fails closed"; "Non-live mode uses the deterministic seed with effective mode PAPER"; design D7, D8; F04, F08)
- [x] 3.4 Add `test_seed_precedence` with injected `secret_file` paths: secret wins over environment; empty secret falls through to environment; live without any seed fails; live with an environment seed succeeds with `ENVIRONMENT`; non-live without any seed succeeds with `DETERMINISTIC_DEVNET`; a non-Unicode `SeedInput` fails with `InvalidEnvironmentSeedEncoding`. (covers: "Secret file takes precedence over the environment seed"; "Live mode with an empty secret falls through to the environment seed"; "Live mode with an environment-only seed succeeds"; "Live mode without any seed fails closed"; design D9; F08, F19)
- [x] 3.5 Add `test_simulated_receipt_contract` and `test_rejected_destination_no_receipt`: accepted receipt has `simulated: true`, `signature_is_chain_valid: false`, `whitelist_enforcement: "SIMULATED"`, derived `destination_whitelisted`, derived `key_zeroized_after_sign`; a rejected destination returns an error and no receipt. (covers: "Transfer receipt denies chain validity"; "Rejected destination does not yield a receipt"; "Receipt carries the simulated whitelist label"; design D4, D5, D6)
- [x] 3.6 Add `test_key_zeroization_observation` (a non-zero buffer reports `false`, a zeroed buffer reports `true`) and `test_serialized_contract_has_no_legacy_keys` (serialize the manifest and receipt, assert the old field names are absent). (covers: "Zeroization flag reflects the observed buffer"; "Unqualified derivation field names are absent"; "Manifest carries the top-level simulated whitelist label"; design D4, D5)
- [x] 3.7 Add a compile-time use of `robotrader_risk_gate::SimulatedVault` and remove every `RustVaultEnclave`/`VaultEnclaveManifest` reference from the Rust workspace. (covers: "No legacy vault type name remains public"; design D1)

## 4. Python vault boundary (`backend/core/hierarchy.py`)

- [x] 4.1 Rewrite `_load_rust_vault_manifest` to validate `vault_mode == "SIMULATED"`, `simulated is True`, a non-empty `wallets` list, and `address_is_spendable is False` on every wallet; return `{}` on absent/timeout/non-zero/unparsable/invalid and record a short `vault_manifest_error`. Keep `_rust_binary_candidates` unchanged. (covers: "Missing binary produces a fail-closed manifest response"; "Binary failure produces a fail-closed manifest response"; design D12, D13)
- [x] 4.2 Delete the Python fallback manifest block, the hardcoded fingerprint/whitelist count, and the now-unused `hashlib` **and** `hmac` imports; rewrite the docstrings to describe a public `SIMULATED` manifest, not BIP-32/BIP-44/SLIP-0010 or a zeroizing enclave. (covers: "Python manifest retrieval fails closed without the Rust vault"; design D13, D19; F22)
- [x] 4.3 Rewrite `sign_transfer_in_rust_enclave` without the Python HMAC fallback. Before returning `signed`, validate the parsed receipt: `simulated is True`, `signature_is_chain_valid is False`, `whitelist_enforcement == "SIMULATED"`, `destination_whitelisted is True`, a non-empty `signature_hex`, the receipt's `leaf_id` or `chain` matches the requested leaf case-insensitively, the destination matches exactly, and `amount_usd` is within `$0.01`. Return `rejected_by_rust_enclave` on a non-zero binary exit and `rejected_vault_unavailable` on a missing binary, timeout, unparsable output, old-contract receipt, or any mismatch; never emit `signature_hex`, `destination_whitelisted`, or `key_zeroized_after_sign` on failure. (covers: "Python signing and checkout fail closed without the Rust vault"; "Kill switch still blocks signing without a binary"; design D14, D15; F05)
- [x] 4.4 Update `checkout_funds` to accept `kill_switch_active` and `kill_switch_reason`, pass them to the signer, and return the rejection for any status other than `signed` before mutating capital, leaf allocations, `checkout_history`, or dry powder; remove the fabricated `tx_hash` fallback and rename the success keys to `simulated_receipt_id` and `simulated_vault_receipt`; add `simulated: true` and the simulation notice to the wrapper. Wire the server endpoint to pass `state_store.kill_switch_active` and `state_store.kill_switch_reason`. (covers: "Checkout without a binary is rejected without mutation"; "Rust rejection is propagated without a Python signature"; "Kill switch still blocks signing without a binary"; design D14, D15; F13)
- [x] 4.5 Update `get_hierarchy_snapshot` and `get_leaf_detail` so `vault_enclave` is the empty mapping when unavailable and no fallback value is synthesized; keep the existing snapshot shape otherwise. (covers: "Missing-binary startup contract remains green"; design D13, D14)
- [x] 4.6 Implement the kill-switch path in the signer: when the flag is active, return `rejected_by_rust_enclave` with the reason before consulting a binary and before producing a signature; do not mutate any checkout state. (covers: "Kill switch still blocks signing without a binary"; design D15; F13)

## 5. Python Solana custody removal

- [x] 5.1 Rewrite `backend/tools/solana_tools.py` as a read-only RPC client: remove `SOLANA_PRIVATE_KEY`, `Keypair`, `transfer_sol`, `sendTransaction`, and the signing imports; expose `rpc_url`, `public_address` from `SOLANA_PUBLIC_KEY`, `custody = "NONE"`, `simulated = true`, and `get_balance(address=None) -> Optional[float]`, which returns `None` when neither the argument nor `public_address` is configured and `None` on an RPC error. (covers: "Environment key is ignored"; "Live tick never broadcasts"; design D16; F01)
- [x] 5.2 Update `backend/core/state_store.py#run_live_testnet_tick`: replace the `if solana.keypair:` guard with the existing Solana pod-selection condition so the branch always executes without a keypair; record a simulated action with `tx_signature: None`, `source: "SIMULATED"`, `is_simulated: True`, a simulation notice, and no transaction/gas counter increments; read the balance only from the configured public address. Make `measured_realized_pnl_usd` and the `live_testnet` population skip `is_simulated: true` rows while the paper population may use their `simulated_pnl_usd`. (covers: "Live tick never broadcasts"; "Recorded Solana action is labelled simulated"; design D16; F06)
- [x] 5.3 Replace the fabricated `solana_balance_sol: 5.0` and empty-address defaults with `None`; `get_testnet_telemetry` returns `None` when no public address is configured and keeps its provenance fields. (covers: "Testnet verification exposes no Python-held key"; design D17; F01)
- [x] 5.4 Update `backend/server.py#verify_testnet_connectivity`: no keypair; return `public_address` from `SOLANA_PUBLIC_KEY`, `balance_sol` from `get_balance(public_address)` or `None`, and `custody: "NONE"`; do not expose a `public_key` field or any key-derived material. (covers: "Testnet verification exposes no Python-held key"; design D16, D17; F01, F12)

## 6. API fail-closed contract (`backend/server.py`)

- [x] 6.1 Rename the vault manifest handler and return `HTTPException(status_code=503, detail=...)` when `state_store.hierarchy.vault_manifest` is empty or not `SIMULATED`; the detail contains no `wallets`, fingerprint, or whitelist count. (covers: "Missing binary produces a fail-closed manifest response"; design D14)
- [x] 6.2 Update the manifest docstring to describe the public `SIMULATED` contract and its non-goals; remove `RustVaultEnclave`, BIP-32, BIP-44, and SLIP-0010 wording. (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)
- [x] 6.3 Confirm the existing `RustBinaryNotFoundError` handler and the `/api/v1/status`, `/api/v1/hierarchy`, `/api/v1/backtest/run`, leaf backtest, `/api/v1/policy/regime`, `/api/v1/chat`, `/api/v1/risk/kill`, and `/api/v1/health` contracts are unchanged. (covers: "Missing-binary startup contract remains green"; design D13, D22)

## 7. Frontend

- [x] 7.1 Update `frontend/src/components/LeafAgentView.jsx`: use `target_leaf_derivation_path`, always render a visible `SIMULATED` badge (including when `wallet_vault` is empty), render `address_is_spendable === false` and the non-spendable address, and remove "Enclave Rust" and "Zeroize RAM & Clé Privée hors Python". (covers: "UI shows a SIMULATED badge"; design D18)
- [x] 7.2 Update `frontend/src/components/Dashboard.jsx` testnet copy: replace "Comptabilité Réelle On-Chain", "Transactions signées", "auto-transferts", and "Gas réseau consommé" with read-only/simulated/unsigned wording; keep the Solscan link for the configured public address. (covers: "Recorded Solana action is labelled simulated"; "UI shows a SIMULATED badge"; design D17, D18)
- [x] 7.3 Add static assertions to `frontend/scripts/check-provenance.mjs`: `target_leaf_derivation_path` is present, `SIMULATED` and `address_is_spendable` appear in `LeafAgentView`, and the old `leaf.wallet_vault.leaf_derivation_path`, `Zeroize RAM`, and `Enclave Rust` strings are absent. (covers: "UI shows a SIMULATED badge"; design D18, D19)
- [x] 7.4 Confirm the frontend renders the unavailable state without crashing when `/api/v1/vault/manifest` returns 503 and `wallet_vault` is `{}`. (covers: "UI shows a SIMULATED badge"; "Missing-binary startup contract remains green"; design D18)

## 8. Documentation, ADR, and process artifacts

- [x] 8.1 Rewrite `docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md` in English as a `SIMULATED` vault document: current behavior, seed precedence, execution mode, the `--vault-secret-file` test override, manifest/receipt contract, simulated whitelist, Python boundary, 26 target-metadata rows, non-goals, and the issue #2 follow-up. Describe removed names with descriptive language ("the former enclave type", "the removed Solana private-key variable") so the no-legacy gates stay empty. (covers: "Documentation states the simulation and its non-goals"; design D20; F21)
- [x] 8.2 Update `README.md`: Tier 3 wording, the architecture diagram label, the vault link description, a new section documenting `ROBOTRADER_EXECUTION_MODE` (four exact values, `PAPER` default, empty/unknown fail-closed, case-sensitive, blank-line consequence), and the Testnet/Devnet telemetry bullet (read-only public-address balance, simulated Solana actions, measured PnL only from CEX testnet). (covers: "Operator documentation defines the execution mode"; "Documentation states the simulation and its non-goals"; design D20; F11, F14, F20)
- [x] 8.3 Update `AGENTS.md`: replace the `RustVaultEnclave`/HD/zeroize/whitelist claims in the Tier 3 description and project structure with `SimulatedVault`/`SIMULATED` and the non-goals, using descriptive language for removed names. (covers: "Documentation states the simulation and its non-goals"; design D20; F21)
- [x] 8.4 Update `docs/architecture.md` in three places: the `HardRiskGate` node to `SimulatedVault (SIMULATED)`; the `crates/exec-router` execution-mode text from three modes (`Backtest`, `Paper`, `Live`) to the four `ROBOTRADER_EXECUTION_MODE` values including `SIMULATED`; and section 5's security invariants to state no exchange keys or signing keypairs in `engine-rs`, no Python key custody, no broadcast, and a read-only configured public address. (covers: "Documentation states the simulation and its non-goals"; design D20; F09, F18)
- [x] 8.5 Amend `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md`: replace the Rust enclave/HD derivation bullet with a `SIMULATED` vault bullet and a pointer to ADR-0005; keep the rest of ADR-0003 unchanged. (covers: "Documentation states the simulation and its non-goals"; design D20)
- [x] 8.6 Add `docs/adr/0005-vault-is-simulated.md`: context (issue #2), decision (types, manifest, execution mode, Python boundary, Solana custody, UI/docs), alternatives, consequences, and the real-cryptography follow-up; use descriptive language for removed names. (covers: "Documentation states the simulation and its non-goals"; design D20; F21)
- [x] 8.7 Update `sdlc/checklists/dev.md` so the vault invariant checks `SIMULATED` labels, no Python key custody, derived flags, and no false BIP/HD claim instead of asserting `RustVaultEnclave` zeroization and whitelist enforcement. (covers: "Repository-wide sweep covers code and process artifacts"; design D19, D20)
- [x] 8.8 Update the vault invariant in `openspec/config.yaml` to name `SimulatedVault`, no Python key custody, and the `SIMULATED`/non-spendable/non-chain-valid labels. (covers: "Repository-wide sweep covers code and process artifacts"; design D19, D20)
- [x] 8.9 Update `.env.example`: remove `SOLANA_PRIVATE_KEY`; add `ROBOTRADER_EXECUTION_MODE=PAPER` with the four exact values, the case-sensitive rule, and the empty/unknown fail-closed warning; add `SOLANA_PUBLIC_KEY`; document the secret file and environment seed precedence without placing a secret value. (covers: "Operator documentation defines the execution mode"; design D9, D20; F14, F20)
- [x] 8.10 Add `scripts/vault-claim-allowlist.txt` as a **patterns-only** file: exactly one ERE per line, no comments, no blank lines, covering the justified legitimate mentions (the `CryptographicCurve` variants, `SimulatedVault`/`SimulatedVaultManifest`, the spec-mandated Python method name, and `ROBOTRADER_VAULT_MASTER_SEED`); add `scripts/vault-claim-allowlist.md` with one justification per pattern. No entry may permit a spendable-address, broadcast, or measured-simulated claim. (covers: "Repository-wide sweep covers code and process artifacts"; design D19; F02)
- [x] 8.11 Update `docs/PERFORMANCE_AND_COST_AUDIT.md`: correct the `live_testnet` description to Binance Spot Testnet as measured and Solana Devnet actions as simulated/excluded, and add a dated note that the historical `162` Devnet self-transfers are not measured after this change. (covers: "Documentation states the simulation and its non-goals"; design D20; F10)

## 9. Tests and non-regression

- [x] 9.1 Update `backend/tests/test_hierarchy_v3.py`: rename the vault test, assert `vault_mode: SIMULATED`, `simulated`, `address_is_spendable == false`, target fields, no legacy fields, `assertFalse(manifest["python_private_key_access"])`, and a valid simulated checkout receipt with explicit `assertTrue(receipt["simulated"])`, `assertFalse(receipt["signature_is_chain_valid"])`, and `assertEqual(receipt["whitelist_enforcement"], "SIMULATED")`; remove only the `zeroize_on_drop` assertion; assert the attacker checkout rejects without changing capital or history. (covers: "Vault tests assert simulation fields"; "Existing fail-closed tests remain green"; design D12, D14; F15, F17)
- [x] 9.2 Add the loader and signer matrices in `backend/tests/test_simulated_vault.py`: loader cases absent/timeout/non-zero/unparsable/old contract/valid; signer cases unavailable/rejected/signed, no signature on failure, and an old-contract receipt without the simulation flags. Use temporary candidate paths and fake binaries; do not touch the real `target/` binary. (covers: "Missing binary produces a fail-closed manifest response"; "Binary failure produces a fail-closed manifest response"; "Rust rejection is propagated without a Python signature"; design D12, D15; F05, F16)
- [x] 9.3 Add the checkout/no-mutation and kill-switch tests in `backend/tests/test_simulated_vault.py`: a rejected checkout changes no capital, leaf allocation, `checkout_history`, or dry powder; a kill switch active with no binary and with a valid binary returns a rejection and no signature. (covers: "Checkout without a binary is rejected without mutation"; "Kill switch still blocks signing without a binary"; design D14, D15; F13, F16)
- [x] 9.4 Add the Solana/telemetry/population tests in `backend/tests/test_simulated_vault.py`: no key custody and no send path; `get_balance` returns `None` without a configured address; telemetry returns `None` without a public address; a simulated Solana row (`is_simulated: true`, `tx_signature: None`) does not change `measured_realized_pnl_usd` or the measured live trade count. Drive `run_live_testnet_tick` through a fake Binance and a mocked `SolanaWalletTool` so the simulated branch is exercised. (covers: "Environment key is ignored"; "Live tick never broadcasts"; "Recorded Solana action is labelled simulated"; design D16, D17; F01, F06, F16)
- [x] 9.5 Add the `/api/v1/testnet/verify` endpoint test in `backend/tests/test_simulated_vault.py`: with `SOLANA_PRIVATE_KEY` set and no `SOLANA_PUBLIC_KEY`, assert no `public_key`/key-derived material, `custody: "NONE"`, `public_address` absent or `None`, and `balance_sol` `None`. Use the isolated child-process pattern so importing `backend.server` does not start the live worker or scheduler. (covers: "Testnet verification exposes no Python-held key"; design D17; F12)
- [x] 9.6 Update `backend/tests/test_missing_binary.py`: import `HierarchicalFleetManager` first, patch `_rust_binary_candidates` to a non-existent path **before any import that transitively imports `backend.core.state_store`** (including `backend.agents.orchestrator` and `backend.server`; `state_store` constructs the singleton and loads the manifest at import time), keep every existing 503/200 assertion, and add a vault-specific `GET /api/v1/vault/manifest` → 503 assertion with no `wallets`, fingerprint, or whitelist count. Do not reuse the shared `assert_503` detail markers for the vault response. (covers: "Missing-binary startup contract remains green"; design D13, D14; F07)
- [x] 9.7 Update `backend/tests/test_integrity_provenance.py` where the testnet telemetry contract is asserted: no fabricated `5.0` SOL balance, `None` without a configured public address, provenance fields unchanged. (covers: "Testnet verification exposes no Python-held key"; design D17, D22; F01)
- [x] 9.8 Run `backend/tests/test_policy_ttl_heartbeat.py`, `backend/tests/test_costguard_gate.py`, and `backend/tests/test_metrics_populations.py` to confirm the Solana tool and telemetry changes do not regress #5, #7, or #8a. (covers: "Existing fail-closed tests remain green"; design D22)
- [x] 9.9 Run `backend/tests/test_contract_roundtrip.py`, `test_contract_single_source.py`, `test_contract_no_codegen.py`, and `test_architecture.py` to confirm `PolicyEnvelope` parity and the backend structure are unchanged. (covers: "Existing fail-closed tests remain green"; design D22)

## Verification

Run from the repository root unless a step changes directory. Attach the output to the issue or PR under `.sdlc/mark-vault-simulated/evidence/` (gitignored).

- `openspec validate mark-vault-simulated --strict` → expected: `Change 'mark-vault-simulated' is valid`.
- `scripts/sdlc/sdlc.sh check mark-vault-simulated` → expected: `spec-lint` PASS, `verdict-lint` PASS; unchecked tasks are expected at PLAN.
- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` → expected: the binary builds at `engine-rs/target/debug/robotrader-node`.
- `cd engine-rs && cargo test` → expected: all Rust tests pass, including the manifest, execution-mode, seed-precedence, receipt, zeroization, and no-legacy-key tests.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: the full warm-path suite passes; `test_hierarchy_v3` and `test_simulated_vault` use the built binary and the isolated fake-binary cases.
- `PYTHONPATH=. python3 -m unittest backend.tests.test_missing_binary backend.tests.test_simulated_vault backend.tests.test_hierarchy_v3 backend.tests.test_costguard_gate backend.tests.test_policy_ttl_heartbeat backend.tests.test_metrics_populations backend.tests.test_integrity_provenance -v` → expected: all pass.
- `cd frontend && npm run lint` → expected: exit 0.
- `cd frontend && npm run build` → expected: the Rolldown build succeeds and writes `dist/`.
- `cd frontend && node scripts/check-provenance.mjs` → expected: `provenance wiring OK`; the new field and badge assertions pass.
- `env -u ROBOTRADER_EXECUTION_MODE -u ROBOTRADER_VAULT_MASTER_SEED ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --vault-manifest | python3 -c 'import json,sys
m=json.load(sys.stdin)
assert m["vault_mode"]=="SIMULATED", m
assert m["simulated"] is True
assert m["execution_mode"]=="PAPER", m
assert m["seed_source"]=="DETERMINISTIC_DEVNET", m
assert len(m["wallets"])==26, len(m["wallets"])
assert m["whitelist_enforcement"]=="SIMULATED"
assert all(w["simulated"] is True and w["address_is_spendable"] is False for w in m["wallets"])
assert all("target_leaf_derivation_path" in w and "leaf_derivation_path" not in w for w in m["wallets"])
print("simulated manifest OK")'` → expected: `simulated manifest OK`; the explicit secret path makes the check independent of a host-mounted secret.
- `ROBOTRADER_EXECUTION_MODE=BOGUS ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --vault-manifest; echo "exit=$?"` → expected: empty stdout, an error on stderr naming `ROBOTRADER_EXECUTION_MODE` and the four values, `exit=2`.
- `ROBOTRADER_EXECUTION_MODE= ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --vault-manifest 2>/tmp/empty-mode.err; echo "exit=$?"; grep -q 'ROBOTRADER_EXECUTION_MODE' /tmp/empty-mode.err; grep -q 'BACKTEST' /tmp/empty-mode.err` → expected: empty stdout, `exit=2`, and both greps succeed.
- `for value in paper "PAPER " " Paper"; do ROBOTRADER_EXECUTION_MODE="$value" ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --vault-manifest >/dev/null 2>&1; test $? -eq 2 || exit 1; done; echo "out-of-spec modes fail closed"` → expected: `out-of-spec modes fail closed`.
- `env -u ROBOTRADER_VAULT_MASTER_SEED ROBOTRADER_EXECUTION_MODE=LIVE ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --vault-manifest; echo "exit=$?"` → expected: empty stdout, `exit=2`, no deterministic seed used.
- `ROBOTRADER_EXECUTION_MODE=LIVE ROBOTRADER_VAULT_MASTER_SEED=test-only-not-a-secret ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --vault-manifest | python3 -c 'import json,sys
m=json.load(sys.stdin)
assert m["vault_mode"]=="SIMULATED"
assert m["execution_mode"]=="LIVE", m
assert m["seed_source"]=="ENVIRONMENT", m
assert all(w["address_is_spendable"] is False for w in m["wallets"])
print("live-mode simulated manifest OK")'` → expected: `live-mode simulated manifest OK`.
- `tmp=$(mktemp); printf 'test-only-not-a-secret\n' > "$tmp"; ROBOTRADER_EXECUTION_MODE=LIVE ROBOTRADER_VAULT_MASTER_SEED=environment-seed ./engine-rs/target/debug/robotrader-node --vault-secret-file "$tmp" --vault-manifest | python3 -c 'import json,sys
m=json.load(sys.stdin)
assert m["seed_source"]=="SECRET_FILE", m
print("secret-file precedence OK")'; rc=$?; rm -f "$tmp"; test $rc -eq 0` → expected: `secret-file precedence OK`; the explicit temp path makes the precedence check hermetic.
- `ROBOTRADER_EXECUTION_MODE=PAPER ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --sign-transfer --leaf-id Solana --dest FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN --amount-usd 1500 --token SOL | python3 -c 'import json,sys
r=json.load(sys.stdin)
assert r["simulated"] is True
assert r["signature_is_chain_valid"] is False
assert r["whitelist_enforcement"]=="SIMULATED"
assert r["destination_whitelisted"] is True
assert r["key_zeroized_after_sign"] is True
assert "signature_hex" in r
print("simulated receipt OK")'` → expected: `simulated receipt OK`.
- `ROBOTRADER_EXECUTION_MODE=PAPER ./engine-rs/target/debug/robotrader-node --vault-secret-file /nonexistent/robotrader_seed --sign-transfer --leaf-id Solana --dest attacker_drain_wallet_999 --amount-usd 1500 --token SOL > /tmp/rejected.json; echo "exit=$?"; python3 -c 'import json
r=json.load(open("/tmp/rejected.json"))
assert "signature_hex" not in r, r
assert "destination_whitelisted" not in r, r
assert r.get("status")=="rejected_by_rust_enclave", r
print("rejected destination OK")'` → expected: `exit=1`, `rejected destination OK`.
- `git grep -n 'RustVaultEnclave\|VaultEnclaveManifest\|RUST_ENCLAVE_HD_ZEROIZE\|RUST_ENCLAVE_HMAC_TRADE_ONLY' -- ':!openspec/changes' ':!.sdlc'` → expected: no output (exit 1).
- `git grep -nE '"(key_isolation_mode|withdrawal_whitelist_enforced|master_derivation_path|leaf_derivation_path|slip44_coin_type|zeroize_on_drop|enclave_version|operator_whitelist_count)"' -- engine-rs/crates/common/src/lib.rs engine-rs/crates/risk-gate/src/vault.rs engine-rs/crates/node/src/main.rs backend/core backend/tools backend/server.py frontend/src` → expected: no output (exit 1).
- `git grep -n 'SOLANA_PRIVATE_KEY' -- ':!openspec/changes' ':!.sdlc' ':!backend/tests'` → expected: no output (exit 1); tests may set the variable to assert it is ignored.
- `git grep -nE 'transfer_sol|simulate_only=False|sendTransaction' -- backend/core backend/tools backend/server.py` → expected: no output (exit 1); tests may name the removed methods to assert their absence.
- `git grep -nE 'test_[A-Za-z0-9_]*(RustVaultEnclave|vault_enclave|hd_derivation)' -- backend/tests engine-rs/crates/risk-gate/src/lib.rs` → expected: no output (exit 1); the old fallback test names are removed, not merely skipped.
- `git grep -nE '^import (hashlib|hmac)|^from (hashlib|hmac)' -- backend/core/hierarchy.py` → expected: no output (exit 1); both imports are removed with the Python fallback.
- `git grep -nE '(^|[^_])leaf_derivation_path' -- frontend/src` → expected: no output (exit 1); the word-boundary form does not match `target_leaf_derivation_path`.
- `git grep -nE 'SIMULATED|address_is_spendable|target_leaf_derivation_path' -- frontend/src/components/LeafAgentView.jsx` → expected: all three appear.
- `git grep -n 'ROBOTRADER_EXECUTION_MODE' README.md .env.example` → expected: both files contain the variable.
- `python3 - <<'PY'
from pathlib import Path
text = Path("README.md").read_text(encoding="utf-8") + "\n" + Path(".env.example").read_text(encoding="utf-8")
for value in ("BACKTEST", "PAPER", "SIMULATED", "LIVE"):
    assert value in text, value
assert "PAPER" in text
assert "empty" in text.lower() or "blank" in text.lower()
assert "unknown" in text.lower() or "unrecognized" in text.lower()
print("execution-mode docs OK")
PY` → expected: `execution-mode docs OK`.
- `test -s scripts/vault-claim-allowlist.txt` → expected: exit 0; the patterns file is not empty.
- `grep -nE '^[[:space:]]*$|^[[:space:]]*#' scripts/vault-claim-allowlist.txt` → expected: no output (exit 1); no blank or comment line can make the gate vacuous.
- `printf 'Secp256k1EcdsaBip44\n' | grep -vEf scripts/vault-claim-allowlist.txt` → expected: no output (exit 1); an allowlisted line is filtered.
- `printf 'BIP-32 HD wallet\n' | grep -vEf scripts/vault-claim-allowlist.txt` → expected: the line survives (exit 0); the gate is not vacuous.
- `git grep -nEi 'BIP-32|BIP-44|SLIP-0010|CIP-1852|secp256k1|ed25519|sr25519|RustVaultEnclave|RUST_ENCLAVE_HD_ZEROIZE|RUST_ENCLAVE_HMAC_TRADE_ONLY|key_isolation_mode|withdrawal_whitelist_enforced|signing keypairs|hot trading sub-wallet|Exchange trade API keys|real PnL tracking|Devnet self-transfer' -- README.md AGENTS.md docs backend/core/hierarchy.py backend/server.py backend/tools/solana_tools.py backend/core/state_store.py engine-rs/crates/risk-gate/src/vault.rs engine-rs/crates/common/src/lib.rs engine-rs/crates/node/src/main.rs sdlc/checklists/dev.md openspec/config.yaml frontend/src | grep -vEi 'SIMULATED|simulated|target_|target scheme|target metadata|not implemented|no real|does not|MUST NOT|non-goal|not measured|read-only|not injected|no signing keypairs|no exchange keys|no exchange trade API keys|no hot trading sub-wallet|no Python key custody' | grep -vEf scripts/vault-claim-allowlist.txt` → expected: no output (exit 1); the claim sweep passes with only justified allowlist entries. Removed names in docs are descriptive, so the separate no-legacy grep above stays empty.
- `docker compose up --build -d` → expected: the command returns; the image builds the release binary in the builder stage.
- `docker compose ps --format '{{.Service}} {{.State}}'` → expected: `redis running`, `backend running`, `frontend running`.
- `curl --retry 30 --retry-delay 2 --retry-connrefused -fsS http://localhost:8000/api/v1/status >/dev/null` → expected: exit 0 once the backend answers.
- `curl -s http://localhost:8000/api/v1/vault/manifest | python3 -c 'import json,sys
m=json.load(sys.stdin)
assert m["vault_mode"]=="SIMULATED"
assert m["simulated"] is True
assert len(m["wallets"])==26
assert m["whitelist_enforcement"]=="SIMULATED"
assert m["execution_mode"] in {"BACKTEST","PAPER","SIMULATED","LIVE"}, m
assert m["seed_source"] in {"SECRET_FILE","ENVIRONMENT","DETERMINISTIC_DEVNET"}, m
assert all(w["address_is_spendable"] is False for w in m["wallets"])
assert "operator_whitelist_count" not in m
assert "zeroize_on_drop" not in m
print("vault endpoint OK")'` → expected: `vault endpoint OK`.
- `curl -s http://localhost:8000/api/v1/testnet/verify | python3 -c 'import json,sys
d=json.load(sys.stdin)
sw=d["solana_wallet"]
assert "public_key" not in sw or sw["public_key"] is None, sw
assert sw.get("custody")=="NONE", sw
assert "balance_sol" in sw, sw
if not sw.get("public_address"):
    assert sw["balance_sol"] is None, sw
assert "private" not in json.dumps(d).lower(), d
print("testnet verify OK")'` → expected: `testnet verify OK`; no key-derived public key, no private material, custody `NONE`, and no fabricated balance without a configured address.
- `curl -s -X POST http://localhost:8000/api/v1/treasury/checkout -H 'Content-Type: application/json' -d '{"amount_usd": 10, "target_chain": "Solana", "target_token": "SOL", "destination_address": "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN", "quote_only": false}' | python3 -c 'import json,sys
r=json.load(sys.stdin)
assert r.get("status") in {"completed","rejected_by_rust_enclave","rejected_vault_unavailable"}, r
if r.get("status")=="completed":
    assert r.get("simulated") is True, r
    receipt=r.get("receipt",{})
    assert "tx_hash" not in receipt, receipt
    assert "enclave_receipt" not in receipt, receipt
    assert "simulated_vault_receipt" in receipt, receipt
print("checkout contract OK:", r.get("status"))'` → expected: `checkout contract OK: completed` (or a structured rejection if the image's binary is unavailable).
- Attach evidence: `evidence/rust-tests.txt`, `evidence/python-tests.txt`, `evidence/frontend-build.txt`, `evidence/check-provenance.txt`, `evidence/vault-manifest.json`, `evidence/sign-receipt.json`, `evidence/testnet-verify.json`, `evidence/execution-mode-fail-closed.txt`, `evidence/claim-gate-self-test.txt`, `evidence/docker-status.json`, and `evidence/claim-sweep.txt`.

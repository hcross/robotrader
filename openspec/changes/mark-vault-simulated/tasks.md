# Tasks — mark-vault-simulated

> Design: [`design.md`](design.md). Spec: [`specs/vault-simulation/spec.md`](specs/vault-simulation/spec.md). This list orders the work; the spec defines the required behaviour.

## 1. Rust contract types (`engine-rs/crates/common/src/lib.rs`)

- [ ] 1.1 Rename `VaultEnclaveManifest` to `SimulatedVaultManifest`; add `ExecutionMode` (`BACKTEST`, `PAPER`, `SIMULATED`, `LIVE`) and `SeedSource` (`SECRET_FILE`, `ENVIRONMENT`, `DETERMINISTIC_DEVNET`) enums with `SCREAMING_SNAKE_CASE` serde. (covers: "The Rust vault identifies itself as simulated"; design D1, D2, D8, D9)
- [ ] 1.2 Replace `PublicWalletDescriptor` with `simulated: bool`, `address_is_spendable: bool`, `target_slip44_coin_type`, `target_master_derivation_path`, `target_leaf_derivation_path`; remove `key_isolation_mode` and `withdrawal_whitelist_enforced`. (covers: "Wallet descriptors deny spendable addresses"; "Unqualified derivation field names are absent"; design D3)
- [ ] 1.3 Replace the manifest fields with `vault_version`, `vault_mode`, `execution_mode`, `simulated`, `simulation_notice`, `seed_source`, `master_seed_fingerprint`, `python_private_key_access`, `whitelist_enforcement`, `simulated_whitelist_entry_count`, `canonical_bridge_contracts_count`, `wallets`; remove `enclave_version`, `zeroize_on_drop`, and `operator_whitelist_count`. (covers: "The Rust vault identifies itself as simulated"; "Manifest carries the top-level simulated whitelist label"; design D2)
- [ ] 1.4 Add `simulated: bool`, `signature_is_chain_valid: bool`, and `whitelist_enforcement: String` to `SignedTransferReceipt`; document that `signature_hex` is a simulated HMAC audit token, not a chain signature. (covers: "Transfer receipt denies chain validity"; "Receipt carries the simulated whitelist label"; design D4)
- [ ] 1.5 Update the `CryptographicCurve` doc comment and every scheme-name comment in this file to say "target scheme metadata only; not implemented by the simulated vault". (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)

## 2. Rust simulated vault (`engine-rs/crates/risk-gate/src/vault.rs`)

- [ ] 2.1 Rename `RustVaultEnclave` to `SimulatedVault`; update `engine-rs/crates/risk-gate/src/lib.rs` to re-export `SimulatedVault`, `VaultBootstrap`, `VaultInitError`, and `ZeroizingBytes`. (covers: "No legacy vault type name remains public"; design D1)
- [ ] 2.2 Add `VaultBootstrap { execution_mode: Option<String>, secret_file: PathBuf, env_seed: Option<String> }`, `VaultInitError` with `InvalidExecutionMode`, `EmptyExecutionMode`, `NonUnicodeExecutionMode`, `InvalidEnvironmentSeedEncoding`, and `MissingLiveSeed`, and `SimulatedVault::load(VaultBootstrap)` / `from_env()`; remove the `Default` impl. (covers: "Unrecognized mode fails closed"; design D7, D8)
- [ ] 2.3 Implement mode parsing and seed precedence exactly as the design's tables: absent → `PAPER`; empty/whitespace → fail closed; exact four values accepted; unknown/non-Unicode → fail closed; secret file → environment seed → live failure or deterministic devnet seed. Set `seed_source` and `execution_mode` from the selected values. (covers: all live-mode and seed scenarios; design D8, D9, D10)
- [ ] 2.4 Remove BIP-32/BIP-44/SLIP-0010/HD/zeroize claims from `sha256`, `hmac_sha256`, `derive_private_key`, `format_public_address`, and the chain-spec comments; describe the HMAC and character mappers as simulated derivation and non-spendable formatting. (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)
- [ ] 2.5 Build each descriptor with `simulated: true`, `address_is_spendable: false`, the three `target_*` fields, and no `key_isolation_mode` or `withdrawal_whitelist_enforced`. (covers: "Wallet descriptors deny spendable addresses"; "Curve and derivation metadata are target-qualified"; design D3)
- [ ] 2.6 Build the manifest with `vault_version`, `vault_mode: "SIMULATED"`, `execution_mode`, `simulated: true`, the non-empty `simulation_notice`, `seed_source`, `whitelist_enforcement: "SIMULATED"`, `simulated_whitelist_entry_count`, and `python_private_key_access: false`. (covers: "The Rust vault identifies itself as simulated"; "Manifest carries the top-level simulated whitelist label"; design D2, D11)
- [ ] 2.7 Rename `DEFAULT_WHITELISTED_PREFIXES` to `SIMULATED_WHITELIST_PREFIXES` and document the predicate as a simulated prefix filter, not a production allowlist; keep the prefix-matching behavior unchanged. (covers: "Receipt safety flags are derived and the whitelist is labelled simulated"; design D2, D6)
- [ ] 2.8 Evaluate the whitelist predicate once, reject with `RiskRejection::VaultSigningRejected` when it is `false`, and assign `destination_whitelisted` from that evaluated value; construct no receipt on rejection. (covers: "Rejected destination does not yield a receipt"; "Accepted receipt reflects the evaluated predicate"; design D6)
- [ ] 2.9 Add `ZeroizingBytes::is_zeroized()`; after `zeroize_now()`, set `key_zeroized_after_sign` from the observed buffer; set `simulated: true`, `signature_is_chain_valid: false`, and `whitelist_enforcement: "SIMULATED"` on every receipt. (covers: "Zeroization flag reflects the observed buffer"; "Transfer receipt denies chain validity"; design D4, D5)
- [ ] 2.10 Update the `RiskRejection::VaultSigningRejected` error string and every vault doc comment to say "simulated vault"; no comment may describe an address as spendable or a receipt as broadcastable. (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)

## 3. Rust CLI and tests (`engine-rs/crates/node/src/main.rs`, `engine-rs/crates/risk-gate/src/lib.rs`)

- [ ] 3.1 Construct the vault with `SimulatedVault::from_env()` in the `--vault-manifest` and `--sign-transfer` paths; on `VaultInitError`, print the display text to stderr and exit `2` with empty stdout. (covers: "Unrecognized mode fails closed"; "Live mode without any seed fails closed"; design D7, D8, D9)
- [ ] 3.2 Replace `test_vault_enclave_26_chains_hd_derivation_and_whitelist_signing` with `test_simulated_vault_manifest_contract`: 26 wallets, `vault_mode: SIMULATED`, `simulated`, `address_is_spendable == false`, target fields present, legacy fields absent, `seed_source` valid. (covers: "Wallet descriptors deny spendable addresses"; "Unqualified derivation field names are absent"; design D2, D3)
- [ ] 3.3 Add `test_execution_mode_parsing`: absent → `PAPER`; the four accepted values; empty/whitespace → error; unknown → error. Use `VaultBootstrap` rather than mutating process-global environment variables. (covers: "Unrecognized mode fails closed"; "Non-live mode uses the deterministic seed with effective mode PAPER"; design D7, D8)
- [ ] 3.4 Add `test_seed_precedence` with temporary secret files: secret wins over environment; empty secret falls through to environment; live without any seed fails; live with an environment seed succeeds with `ENVIRONMENT`; non-live without any seed succeeds with `DETERMINISTIC_DEVNET`. (covers: "Secret file takes precedence over the environment seed"; "Live mode with an empty secret falls through to the environment seed"; "Live mode with an environment-only seed succeeds"; "Live mode without any seed fails closed"; design D9)
- [ ] 3.5 Add `test_simulated_receipt_contract` and `test_rejected_destination_no_receipt`: accepted receipt has `simulated: true`, `signature_is_chain_valid: false`, `whitelist_enforcement: "SIMULATED"`, derived `destination_whitelisted`, derived `key_zeroized_after_sign`; a rejected destination returns an error and no receipt. (covers: "Transfer receipt denies chain validity"; "Rejected destination does not yield a receipt"; "Receipt carries the simulated whitelist label"; design D4, D5, D6)
- [ ] 3.6 Add `test_key_zeroization_observation` (a non-zero buffer reports `false`, a zeroed buffer reports `true`) and `test_serialized_contract_has_no_legacy_keys` (serialize the manifest and receipt, assert the old field names are absent). (covers: "Zeroization flag reflects the observed buffer"; "Unqualified derivation field names are absent"; "Manifest carries the top-level simulated whitelist label"; design D4, D5)
- [ ] 3.7 Add a compile-time use of `robotrader_risk_gate::SimulatedVault` and remove every `RustVaultEnclave`/`VaultEnclaveManifest` reference from the Rust workspace. (covers: "No legacy vault type name remains public"; design D1)

## 4. Python vault boundary (`backend/core/hierarchy.py`)

- [ ] 4.1 Rewrite `_load_rust_vault_manifest` to validate `vault_mode == "SIMULATED"`, `simulated is True`, a non-empty `wallets` list, and `address_is_spendable is False` on every wallet; return `{}` on absent/timeout/non-zero/unparsable/invalid and record a short `vault_manifest_error`. Keep `_rust_binary_candidates` unchanged. (covers: "Missing binary produces a fail-closed manifest response"; "Binary failure produces a fail-closed manifest response"; design D12, D13)
- [ ] 4.2 Delete the Python fallback manifest block, the hardcoded fingerprint/whitelist count, and any now-unused `hashlib` import; rewrite the docstrings to describe a public `SIMULATED` manifest, not BIP-32/BIP-44/SLIP-0010 or a zeroizing enclave. (covers: "Python manifest retrieval fails closed without the Rust vault"; design D13, D19)
- [ ] 4.3 Rewrite `sign_transfer_in_rust_enclave` without the Python HMAC fallback: accept only a valid simulated receipt; return `rejected_by_rust_enclave` on a non-zero binary exit and `rejected_vault_unavailable` when no valid binary/receipt is available; never emit `signature_hex`, `destination_whitelisted`, or `key_zeroized_after_sign` on failure. (covers: "Python signing and checkout fail closed without the Rust vault"; "Kill switch still blocks signing without a binary"; design D14, D15)
- [ ] 4.4 Update `checkout_funds` to return the rejection for any status other than `signed` before mutating capital, leaf allocations, `checkout_history`, or dry powder; remove the fabricated `tx_hash` fallback and rename the success keys to `simulated_receipt_id` and `simulated_vault_receipt`; add `simulated: true` and the simulation notice to the wrapper. (covers: "Checkout without a binary is rejected without mutation"; "Rust rejection is propagated without a Python signature"; design D14, D15)
- [ ] 4.5 Update `get_hierarchy_snapshot` and `get_leaf_detail` so `vault_enclave` is the empty mapping when unavailable and no fallback value is synthesized; keep the existing snapshot shape otherwise. (covers: "Missing-binary startup contract remains green"; design D13, D14)
- [ ] 4.6 Confirm the kill-switch path returns a rejection with no signature and no mutation when the binary is unavailable. (covers: "Kill switch still blocks signing without a binary"; design D15)

## 5. Python Solana custody removal

- [ ] 5.1 Rewrite `backend/tools/solana_tools.py` as a read-only RPC client: remove `SOLANA_PRIVATE_KEY`, `Keypair`, `transfer_sol`, `sendTransaction`, and the signing imports; expose `rpc_url`, `public_address` from `SOLANA_PUBLIC_KEY`, `custody = "NONE"`, `simulated = true`, and `get_balance(address=None)`. (covers: "Environment key is ignored"; "Live tick never broadcasts"; design D16)
- [ ] 5.2 Update `backend/core/state_store.py#run_live_testnet_tick`: the Solana branch records a simulated action with `tx_signature: None`, `source: "SIMULATED"`, `is_simulated: True`, a simulation notice, and no transaction/gas counter increments; read the balance only from the configured public address. Make `measured_realized_pnl_usd` and the `live_testnet` population skip `is_simulated: true` rows while the paper population may use their `simulated_pnl_usd`. (covers: "Live tick never broadcasts"; "Recorded Solana action is labelled simulated"; design D16)
- [ ] 5.3 Replace the fabricated `solana_balance_sol: 5.0` and empty-address defaults with `None`; `get_testnet_telemetry` returns `None` when no public address is configured and keeps its provenance fields. (covers: "Testnet verification exposes no Python-held key"; design D17)
- [ ] 5.4 Update `backend/server.py#verify_testnet_connectivity`: no keypair; return `public_address` from `SOLANA_PUBLIC_KEY`, a balance read from that address, and `custody: "NONE"`; no public key derived from private material. (covers: "Testnet verification exposes no Python-held key"; design D16, D17)

## 6. API fail-closed contract (`backend/server.py`)

- [ ] 6.1 Rename the vault manifest handler and return `HTTPException(status_code=503, detail=...)` when `state_store.hierarchy.vault_manifest` is empty or not `SIMULATED`; the detail contains no `wallets`, fingerprint, or whitelist count. (covers: "Missing binary produces a fail-closed manifest response"; design D14)
- [ ] 6.2 Update the manifest docstring to describe the public `SIMULATED` contract and its non-goals; remove `RustVaultEnclave`, BIP-32, BIP-44, and SLIP-0010 wording. (covers: "No vault surface claims an implemented cryptographic guarantee"; design D19)
- [ ] 6.3 Confirm the existing `RustBinaryNotFoundError` handler and the `/api/v1/status`, `/api/v1/hierarchy`, `/api/v1/backtest/run`, leaf backtest, `/api/v1/policy/regime`, `/api/v1/chat`, `/api/v1/risk/kill`, and `/api/v1/health` contracts are unchanged. (covers: "Missing-binary startup contract remains green"; design D13, D22)

## 7. Frontend

- [ ] 7.1 Update `frontend/src/components/LeafAgentView.jsx`: use `target_leaf_derivation_path`, always render a visible `SIMULATED` badge (including when `wallet_vault` is empty), render `address_is_spendable === false` and the non-spendable address, and remove "Enclave Rust" and "Zeroize RAM & Clé Privée hors Python". (covers: "UI shows a SIMULATED badge"; design D18)
- [ ] 7.2 Update `frontend/src/components/Dashboard.jsx` testnet copy: replace "Comptabilité Réelle On-Chain", "Transactions signées", "auto-transferts", and "Gas réseau consommé" with read-only/simulated/unsigned wording; keep the Solscan link for the configured public address. (covers: "Recorded Solana action is labelled simulated"; "UI shows a SIMULATED badge"; design D17, D18)
- [ ] 7.3 Add static assertions to `frontend/scripts/check-provenance.mjs`: `target_leaf_derivation_path` is present, `SIMULATED` and `address_is_spendable` appear in `LeafAgentView`, and the old `leaf.wallet_vault.leaf_derivation_path`, `Zeroize RAM`, and `Enclave Rust` strings are absent. (covers: "UI shows a SIMULATED badge"; design D18, D19)
- [ ] 7.4 Confirm the frontend renders the unavailable state without crashing when `/api/v1/vault/manifest` returns 503 and `wallet_vault` is `{}`. (covers: "UI shows a SIMULATED badge"; "Missing-binary startup contract remains green"; design D18)

## 8. Documentation, ADR, and process artifacts

- [ ] 8.1 Rewrite `docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md` in English as a `SIMULATED` vault document: current behavior, seed precedence, execution mode, manifest/receipt contract, simulated whitelist, Python boundary, 26 target-metadata rows, non-goals, and the issue #2 follow-up. (covers: "Documentation states the simulation and its non-goals"; design D20)
- [ ] 8.2 Update `README.md`: Tier 3 wording, the architecture diagram label, the vault link description, and a new section documenting `ROBOTRADER_EXECUTION_MODE`, its four values, the `PAPER` default, empty/unknown fail-closed behavior, and the non-goals. (covers: "Operator documentation defines the execution mode"; "Documentation states the simulation and its non-goals"; design D20)
- [ ] 8.3 Update `AGENTS.md`: replace the `RustVaultEnclave`/HD/zeroize/whitelist claims in the Tier 3 description and project structure with `SimulatedVault`/`SIMULATED` and the non-goals. (covers: "Documentation states the simulation and its non-goals"; design D20)
- [ ] 8.4 Update `docs/architecture.md` so the `HardRiskGate` node names `SimulatedVault (SIMULATED)` and does not imply real custody. (covers: "Documentation states the simulation and its non-goals"; design D20)
- [ ] 8.5 Amend `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md`: replace the Rust enclave/HD derivation bullet with a `SIMULATED` vault bullet and a pointer to ADR-0005; keep the rest of ADR-0003 unchanged. (covers: "Documentation states the simulation and its non-goals"; design D20)
- [ ] 8.6 Add `docs/adr/0005-vault-is-simulated.md`: context (issue #2), decision (types, manifest, execution mode, Python boundary, Solana custody, UI/docs), alternatives, consequences, and the real-cryptography follow-up. (covers: "Documentation states the simulation and its non-goals"; design D20)
- [ ] 8.7 Update `sdlc/checklists/dev.md` so the vault invariant checks `SIMULATED` labels, no Python key custody, derived flags, and no false BIP/HD claim instead of asserting `RustVaultEnclave` zeroization and whitelist enforcement. (covers: "Repository-wide sweep covers code and process artifacts"; design D19, D20)
- [ ] 8.8 Update the vault invariant in `openspec/config.yaml` to name `SimulatedVault`, no Python key custody, and the `SIMULATED`/non-spendable/non-chain-valid labels. (covers: "Repository-wide sweep covers code and process artifacts"; design D19, D20)
- [ ] 8.9 Update `.env.example`: remove `SOLANA_PRIVATE_KEY`; add `ROBOTRADER_EXECUTION_MODE=PAPER` with the four values and the fail-closed warning; add `SOLANA_PUBLIC_KEY`; document the secret file and environment seed precedence without placing a secret value. (covers: "Operator documentation defines the execution mode"; design D9, D20)
- [ ] 8.10 Add `scripts/vault-claim-allowlist.txt` with one ERE pattern and justification per legitimate mention (the `CryptographicCurve` variants, `SimulatedVault`/`SimulatedVaultManifest`, the spec-mandated Python method name, and `ROBOTRADER_VAULT_MASTER_SEED`); no entry may permit a spendable-address or broadcast claim. (covers: "Repository-wide sweep covers code and process artifacts"; design D19)

## 9. Tests and non-regression

- [ ] 9.1 Update `backend/tests/test_hierarchy_v3.py`: rename the vault test, assert `vault_mode: SIMULATED`, `simulated`, `address_is_spendable == false`, target fields, no legacy fields, and a valid simulated checkout receipt; remove the `zeroize_on_drop`/`python_private_key_access` fallback assertions; assert the attacker checkout rejects without changing capital or history. (covers: "Vault tests assert simulation fields"; "Existing fail-closed tests remain green"; design D12, D14)
- [ ] 9.2 Add `backend/tests/test_simulated_vault.py`: loader matrix (absent/timeout/non-zero/unparsable/old contract/valid), signer matrix (unavailable/rejected/signed, no signature on failure), checkout no-mutation, Solana tool no key custody/no sendTransaction, telemetry `None` without a public address, and a simulated Solana row that does not change `measured_realized_pnl_usd` or the measured live trade count. Use temporary candidate paths and fake binaries; do not touch the real `target/` binary. (covers: "Missing binary produces a fail-closed manifest response"; "Binary failure produces a fail-closed manifest response"; "Checkout without a binary is rejected without mutation"; "Environment key is ignored"; "Live tick never broadcasts"; design D12–D17)
- [ ] 9.3 Update `backend/tests/test_missing_binary.py`: patch `HierarchicalFleetManager._rust_binary_candidates` to a non-existent path before importing `backend.server`; keep every existing 503/200 assertion and add `GET /api/v1/vault/manifest` → 503 with no `wallets`, fingerprint, or whitelist count. (covers: "Missing-binary startup contract remains green"; design D13, D14)
- [ ] 9.4 Update `backend/tests/test_integrity_provenance.py` where the testnet telemetry contract is asserted: no fabricated `5.0` SOL balance, `None` without a configured public address, provenance fields unchanged. (covers: "Testnet verification exposes no Python-held key"; design D17, D22)
- [ ] 9.5 Run `backend/tests/test_policy_ttl_heartbeat.py`, `backend/tests/test_costguard_gate.py`, and `backend/tests/test_metrics_populations.py` to confirm the Solana tool and telemetry changes do not regress #5, #7, or #8a. (covers: "Existing fail-closed tests remain green"; design D22)
- [ ] 9.6 Run `backend/tests/test_contract_roundtrip.py`, `test_contract_single_source.py`, `test_contract_no_codegen.py`, and `test_architecture.py` to confirm `PolicyEnvelope` parity and the backend structure are unchanged. (covers: "Existing fail-closed tests remain green"; design D22)

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
- `env -u ROBOTRADER_EXECUTION_MODE -u ROBOTRADER_VAULT_MASTER_SEED ./engine-rs/target/debug/robotrader-node --vault-manifest | python3 -c 'import json,sys
m=json.load(sys.stdin)
assert m["vault_mode"]=="SIMULATED", m
assert m["simulated"] is True
assert m["execution_mode"]=="PAPER", m
assert m["seed_source"]=="DETERMINISTIC_DEVNET", m
assert len(m["wallets"])==26, len(m["wallets"])
assert m["whitelist_enforcement"]=="SIMULATED"
assert all(w["simulated"] is True and w["address_is_spendable"] is False for w in m["wallets"])
assert all("target_leaf_derivation_path" in w and "leaf_derivation_path" not in w for w in m["wallets"])
print("simulated manifest OK")'` → expected: `simulated manifest OK`.
- `ROBOTRADER_EXECUTION_MODE=BOGUS ./engine-rs/target/debug/robotrader-node --vault-manifest; echo "exit=$?"` → expected: empty stdout, an error on stderr, `exit=2`.
- `ROBOTRADER_EXECUTION_MODE= ./engine-rs/target/debug/robotrader-node --vault-manifest; echo "exit=$?"` → expected: empty stdout, an error on stderr, `exit=2`.
- `env -u ROBOTRADER_VAULT_MASTER_SEED ROBOTRADER_EXECUTION_MODE=LIVE ./engine-rs/target/debug/robotrader-node --vault-manifest; echo "exit=$?"` → expected: empty stdout, `exit=2`, no deterministic seed used.
- `ROBOTRADER_EXECUTION_MODE=LIVE ROBOTRADER_VAULT_MASTER_SEED=test-only-not-a-secret ./engine-rs/target/debug/robotrader-node --vault-manifest | python3 -c 'import json,sys
m=json.load(sys.stdin)
assert m["vault_mode"]=="SIMULATED"
assert m["execution_mode"]=="LIVE", m
assert m["seed_source"]=="ENVIRONMENT", m
assert all(w["address_is_spendable"] is False for w in m["wallets"])
print("live-mode simulated manifest OK")'` → expected: `live-mode simulated manifest OK`.
- `ROBOTRADER_EXECUTION_MODE=PAPER ./engine-rs/target/debug/robotrader-node --sign-transfer --leaf-id Solana --dest FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN --amount-usd 1500 --token SOL | python3 -c 'import json,sys
r=json.load(sys.stdin)
assert r["simulated"] is True
assert r["signature_is_chain_valid"] is False
assert r["whitelist_enforcement"]=="SIMULATED"
assert r["destination_whitelisted"] is True
assert r["key_zeroized_after_sign"] is True
assert "signature_hex" in r
print("simulated receipt OK")'` → expected: `simulated receipt OK`.
- `ROBOTRADER_EXECUTION_MODE=PAPER ./engine-rs/target/debug/robotrader-node --sign-transfer --leaf-id Solana --dest attacker_drain_wallet_999 --amount-usd 1500 --token SOL > /tmp/rejected.json; echo "exit=$?"; python3 -c 'import json
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
- `git grep -n 'leaf_derivation_path' -- frontend/src` → expected: no output (exit 1); `target_leaf_derivation_path` is present.
- `git grep -nE 'SIMULATED|address_is_spendable|target_leaf_derivation_path' -- frontend/src/components/LeafAgentView.jsx` → expected: all three appear.
- `git grep -nEi 'BIP-32|BIP-44|SLIP-0010|CIP-1852|secp256k1|ed25519|sr25519|RustVaultEnclave|RUST_ENCLAVE_HD_ZEROIZE|RUST_ENCLAVE_HMAC_TRADE_ONLY|key_isolation_mode|withdrawal_whitelist_enforced' -- README.md AGENTS.md docs backend/core/hierarchy.py backend/server.py backend/tools/solana_tools.py backend/core/state_store.py engine-rs/crates/risk-gate/src/vault.rs engine-rs/crates/common/src/lib.rs engine-rs/crates/node/src/main.rs sdlc/checklists/dev.md openspec/config.yaml frontend/src | grep -vEi 'SIMULATED|simulated|target|not implemented|no real|MUST NOT|non-goal' | grep -vEf scripts/vault-claim-allowlist.txt` → expected: no output (exit 1); the claim sweep passes with only justified allowlist entries.
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
- Attach evidence: `evidence/rust-tests.txt`, `evidence/python-tests.txt`, `evidence/frontend-build.txt`, `evidence/check-provenance.txt`, `evidence/vault-manifest.json`, `evidence/sign-receipt.json`, `evidence/execution-mode-fail-closed.txt`, `evidence/docker-status.json`, and `evidence/claim-sweep.txt`.

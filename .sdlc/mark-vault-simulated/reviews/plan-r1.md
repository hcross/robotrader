# PLAN Review — mark-vault-simulated (round 1)

- **Change**: `mark-vault-simulated` (Lane L, partial issue #2)
- **Stage**: `plan`
- **Round**: 1
- **Reviewed SHA**: `c3f658d896449835434e1a690b1b0944f85ccb9c`
- **Artifact**: `openspec/changes/mark-vault-simulated/design.md`, `openspec/changes/mark-vault-simulated/tasks.md` at the reviewed SHA; approved SPEC at `65ae70510af46b7a29f2ee6abb097a875ea58777`
- **Reviewer**: `sdlc-plan-reviewer` (cold start)

## Human Summary (≤ 150 words)

The honest-simulation design and the 55-task plan are largely traceable to the approved SPEC, and the Rust/Python/frontend/docs slices are identified. Two blockers and twelve majors nevertheless prevent approval. The plan reports a fabricated `0.0` SOL balance instead of `None`, and its central claim-sweep gate cannot work as written with `grep -f`. Two verification commands are objectively broken (`leaf_derivation_path` matches `target_leaf_derivation_path`; the allowlist format is not a regex-per-line file). The mode parser accepts out-of-spec values (`paper`, `PAPER `), the Python signer does not validate a stale receipt's simulation flags, the simulated Solana branch becomes unreachable after removing `keypair`, and the missing-binary test patches the candidate list after the manager has already loaded the manifest. Documentation tasks also miss false custody/metric claims in `docs/architecture.md`, `docs/PERFORMANCE_AND_COST_AUDIT.md`, and `README.md`.

## Risk Rulings (requested)

1. **LIVE + simulated vault** — Acceptable under the approved SPEC. The SPEC explicitly requires construction to succeed in `LIVE` with a seed and requires `vault_mode: SIMULATED`; refusing `LIVE` outright would be a spec gap, not a plan fix. The plan labels every surface and adds no real custody. Non-blocking suggestion: surface `execution_mode` in the leaf UI, not only in the manifest.
2. **Retained `SignedTransferReceipt` / `python_private_key_access` names** — Acceptable. The SPEC mandates the vault/manifest names and only requires the receipt flags; the docstrings and `simulated`/`signature_is_chain_valid` fields carry the qualification. The stale-receipt validation gap is a separate finding (F05).
3. **Broad prefix whitelist retained and labelled simulated** — Acceptable as a simulation. The SPEC explicitly leaves exact allowlists out of scope; addresses are non-spendable and no broadcast exists. The ADR and issue #2 must keep the follow-up explicit (the plan does).
4. **Empty `ROBOTRADER_EXECUTION_MODE=` fails closed** — Acceptable and intentional. The operator sees an empty manifest and a 503; the failure is fail-closed rather than a silent `PAPER`. The plan should make the error text name the variable and accepted values (F18, minor).
5. **Vault binary path distinct from the backtest resolver** — Acceptable. #9 requires the existing `_rust_binary_candidates` list to remain unchanged; contract validation is a stricter fail-closed boundary, not a hidden resolver change. The test-timing defect in F07 is separate from this boundary.

## Checklist Walk

| Checklist item | Status | Evidence |
|---|---|---|
| 1.1 Every design decision traces to a requirement/invariant | PASS | Traceability table (`design.md#L292-L303`) and per-task `covers:` annotations. |
| 1.2 Every requirement addressed by a task | FAIL | Docs/verification gaps: F09, F10, F11, F12, F13, F14; F08/F05 for boundaries. |
| 1.3 No unapproved behaviour implemented | FAIL | D8 accepts trimmed/uppercased values outside the four (`design.md#L128`; F04). |
| 1.4 Spec gap escalated, not patched | PASS | No spec gap found; the `LIVE`/simulated decision is already in the SPEC. |
| 2.1 Alternatives named per decision | PASS | D1–D22 table (`design.md#L119-L142`). |
| 2.2 Rejections have technical reasons | PASS | Each rejection cites churn/defect/scope, not preference. |
| 2.3 Reversible vs one-way doors separated | PASS | Contract migration/rollback (`design.md#L322-L362`); no data migration. |
| 2.4 Simplest design considered | PASS | D1/D2/D3 reject aliases and additive fields; no new dependency. |
| 2.5 New dependencies justified | PASS | D21: none added; `solders` removed from the signing path. |
| 3.1 PolicyEnvelope parity addressed | PASS | D22: untouched; 9.6 runs the parity/contract suites. |
| 3.2 IPC/API/DB/CLI changes versioned or compatible | PASS with caveat | `vault_version` and the migration table; checkout wrapper is intentionally breaking with a migration (D15). |
| 3.3 Schema evolution has migration/rollback | PASS | Manifest/receipt migration table and rollback (`design.md#L322-L362`). |
| 3.4 Serialization boundaries explicit | PASS | JSON stdout/API, Redis unaffected; `vault_version` carried. |
| 3.5 No cross-chain/venue leakage | PASS | Each leaf descriptors remain chain-scoped; no change to leaf isolation. |
| 4.1 No LLM/blocking I/O/allocation/logging in hot path | PASS | Vault is not on `HardRiskGate::validate` or `StrategyPod::on_market_event`; D22. |
| 4.2 50 µs budget preserved | PASS | D22; no hot-path change; 9.6 non-regression. |
| 4.3 New loops/data structures bounded | PASS | Manifest/descriptor loops are 26-item constant; no new hot loop. |
| 4.4 Failure modes defined | FAIL | Signer receipt validation (F05); dead Solana branch (F06); kill-switch wiring/test (F13). |
| 5.1 Capital protection not weakened | FAIL | Hardcoded `kill_switch_active=False` in `checkout_funds` and no test (F21); fabricated balance (F01). |
| 5.2 Vault/key material inside enclave; zeroize/whitelist preserved | FAIL | Python signer can accept a stale receipt without simulation flags (F05); documentation still claims custody (F09). |
| 5.3 Trust-boundary inputs validated | FAIL | Receipt validation is undefined (F05); non-Unicode mode/seed untestable (F08). |
| 5.4 No secrets in logs/fixtures/evidence | PASS | No key material introduced; tests use fake binaries/temp paths (9.2). |
| 5.5 Fail-closed on money/risk paths | FAIL | F01, F04, F05, F06, F13. |
| 6.1 Each scenario has a named test/verification | FAIL | Testnet verification (F12), kill switch (F13), operator docs (F14); broken commands (F02/F03). |
| 6.2 Unit/integration/e2e proportional to risk | FAIL | F16 (9.2 overloaded); missing endpoint test (F12). |
| 6.3 Determinism backtest == paper == live | PASS | Vault/telemetry only; no strategy branch; D22. |
| 6.4 Negative/boundary tests planned | FAIL | Non-Unicode (F08); out-of-spec mode values (F04); stale receipt (F05). |
| 6.5 Performance tests where a budget exists | PASS | No hot-path change; existing 50 µs non-regression is sufficient. |
| 6.6 Test data contains no real keys | PASS | 9.2 requires fake binaries/temp paths; no real key fixtures. |
| 7.1 Deployment order explicit | PASS | `design.md#L341-L351`; one PR, binary rebuilt before backend. |
| 7.2 Rollback concrete | PASS | `design.md#L353-L362`; rebuild both binary and image; old/new contract pairing explained. |
| 7.3 Observability planned | PASS | 503 detail, signer statuses, `execution_mode`/`seed_source`, UI badge (`design.md#L364-L370`). |
| 7.4 Cost impact assessed | PASS | Zero new LLM/RPC/Redis loops (`design.md#L370`). |
| 8.1 Tasks are checkboxes under numbered headings | PASS | 55 tasks in 9 groups. |
| 8.2 Each task fits one session and is verifiable | FAIL | 9.2 is materially larger than one session (F13); several tasks depend on broken commands (F02/F03). |
| 8.3 Dependency order correct | PASS | Rust contract → vault → CLI → Python → UI → docs → tests; no cycle. |
| 8.4 `## Verification` exact commands/evidence | FAIL | F02, F03, F19; F12/F13/F14 missing commands. |
| 8.5 No task hides a spec change | FAIL | D8 normalization (F04); `get_balance` 0.0 (F01). |

## Findings (most severe first)

### F01 — `get_balance` reports a fabricated `0.0` balance (blocker)

- **Location**: `backend/tools/solana_tools.py#L55-L65`; `backend/server.py#L377-L381`; `openspec/changes/mark-vault-simulated/design.md#L263`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L148-L152`.
- **Evidence**: Design D16 says `get_balance(address=None)` "returns `0.0` when neither [address] exists". The current `SolanaWalletTool.get_balance` returns `0.0` without a target, and `verify_testnet_connectivity` reports `balance_sol: solana.get_balance()`. The SPEC says "any wallet balance reported is read from a configured public address only." `0.0` is a plausible default on a money/telemetry surface, the exact class of fabricated value this change removes. `get_testnet_telemetry` correctly returns `None`, so the two paths disagree.
- **Required fix**: Make `get_balance` return `None` (or omit the field) when no configured address exists; update `server.py`, `state_store`, and tests. Add a test with no `SOLANA_PUBLIC_KEY` and with `SOLANA_PRIVATE_KEY` set, asserting no reported balance and no key-derived public key.
- **Status**: open. **Origin**: initial.

### F02 — Claim-sweep allowlist format is incompatible with `grep -f` (blocker)

- **Location**: `openspec/changes/mark-vault-simulated/design.md#L139`; `openspec/changes/mark-vault-simulated/tasks.md#L76`; `openspec/changes/mark-vault-simulated/tasks.md#L143`.
- **Evidence**: The design requires "ERE patterns with a justification per line", but the verification pipeline filters with `grep -vEf scripts/vault-claim-allowlist.txt`. `grep -f` treats every line as a regex; a line `Secp256k1 # variant` does not match `Secp256k1EcdsaBip44`, so an allowed legitimate mention still fails the gate. A blank line is an empty regex and filters **every** line, making the gate pass vacuously. I reproduced both behaviours with `printf ... | grep -vEf`.
- **Required fix**: Define a `grep -f`-compatible format (one ERE per line, no comments, no blank lines) and put justifications in a sibling `scripts/vault-claim-allowlist.md`; or add a wrapper that parses `pattern<TAB>justification`, rejects blank lines, and extracts the first field. Add a self-test proving an allowlisted line passes and a disallowed line fails.
- **Status**: open. **Origin**: initial.

### F03 — `git grep 'leaf_derivation_path'` is impossible to satisfy (major)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L141`.
- **Evidence**: `target_leaf_derivation_path` contains the substring `leaf_derivation_path`. Once task 7.1 is implemented, `git grep -n 'leaf_derivation_path' -- frontend/src` returns the target line and exits 0, so the expected "no output (exit 1)" cannot occur. I verified the substring with `printf 'target_leaf_derivation_path\n' | grep -n 'leaf_derivation_path'`.
- **Required fix**: Use a precise pattern, for example `git grep -nE '(^|[^_])leaf_derivation_path' -- frontend/src` or `git grep -n 'wallet_vault\.leaf_derivation_path' -- frontend/src`, or assert the serialized JSON key with a Python check.
- **Status**: open. **Origin**: initial.

### F04 — D8 normalizes mode values and accepts out-of-spec inputs (major)

- **Location**: `openspec/changes/mark-vault-simulated/design.md#L128`; `openspec/changes/mark-vault-simulated/tasks.md#L17`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L156`.
- **Evidence**: D8 says the four values are "accepted exactly (trimmed, uppercase)". That normalization accepts `paper`, `PAPER `, and ` Paper`. The SPEC requires exactly four values and says "Any other non-empty value MUST cause vault construction to fail closed." The plan neither tests the normalized cases nor records a spec change.
- **Required fix**: Compare the raw value exactly (no trim/uppercase), or escalate a spec change that explicitly allows normalization; add tests for `paper`, `PAPER `, and ` Paper` with the expected fail-closed result.
- **Status**: open. **Origin**: initial.

### F05 — Python signer does not validate a receipt's simulation flags (major, security)

- **Location**: `openspec/changes/mark-vault-simulated/design.md#L135`; `openspec/changes/mark-vault-simulated/tasks.md#L40`; `backend/core/hierarchy.py#L1147-L1150`.
- **Evidence**: The current signer accepts any zero-exit JSON containing `signature_hex`. Task 4.3 says "accept only a valid simulated receipt" but neither the design nor the task defines validity. A stale pre-change binary (the risk the design calls out at `design.md#L310`) can return an old receipt without `simulated: true`, `signature_is_chain_valid: false`, or `whitelist_enforcement: "SIMULATED"`; the signer would return `signed`, and `checkout_funds` would mutate capital with a false receipt. Manifest validation does not cover the signer path.
- **Required fix**: Define and implement receipt validation before returning `signed`: `simulated is True`, `signature_is_chain_valid is False`, `whitelist_enforcement == "SIMULATED"`, non-empty `signature_hex`, and the returned destination/leaf match the request. Treat any mismatch as `rejected_vault_unavailable`; add an old-contract-receipt case to the signer matrix.
- **Status**: open. **Origin**: initial (security-relevant defect).

### F06 — The simulated Solana branch becomes unreachable (major)

- **Location**: `openspec/changes/mark-vault-simulated/design.md#L263`; `openspec/changes/mark-vault-simulated/tasks.md#L48`; `backend/core/state_store.py#L588-L593`.
- **Evidence**: The current branch is guarded by `if solana.keypair:`. Task 5.1 removes `Keypair` from `SolanaWalletTool`, so the branch can never execute. The design nevertheless says `run_live_testnet_tick` "records a simulated Solana action"; task 5.2 does not state what replaces the guard. The "Live tick never broadcasts" scenario is satisfied vacuously, but "Recorded Solana action is labelled simulated" is not exercised.
- **Required fix**: Replace the `keypair` guard with an explicit condition (for example Solana pod selection or a configured public address) and test that the simulated row is recorded with `tx_signature: None` and `is_simulated: True`; or explicitly drop the "records a simulated action" design claim and reconcile it with the SPEC scenario.
- **Status**: open. **Origin**: initial.

### F07 — Missing-binary test patches the candidate list after the manager is constructed (major)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L82`; `backend/tests/test_missing_binary.py#L143` and `#L177-L182`; `backend/core/state_store.py#L982`.
- **Evidence**: The child script imports `backend.core.state_store` before patching. That module executes `state_store = HybridStateStore()` at import time, and `HierarchicalFleetManager.__init__` loads the vault manifest. Patching `_rust_binary_candidates` before importing `backend.server` is therefore too late. Because the Verification builds the binary, the loader finds the real manifest and the new `GET /api/v1/vault/manifest` assertion would return 200, not 503.
- **Required fix**: Patch `HierarchicalFleetManager._rust_binary_candidates` before importing `backend.core.state_store` (and `backend.server`), or inject the candidate list into the manager; use a vault-specific 503 assertion rather than the shared `assert_503` detail markers.
- **Status**: open. **Origin**: initial.

### F08 — Non-Unicode mode/seed paths are not testable through `VaultBootstrap` (major)

- **Location**: `openspec/changes/mark-vault-simulated/design.md#L127`; `openspec/changes/mark-vault-simulated/tasks.md#L16`; `openspec/changes/mark-vault-simulated/tasks.md#L30`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L156`.
- **Evidence**: `VaultBootstrap { execution_mode: Option<String>, env_seed: Option<String> }` cannot represent a non-Unicode `ROBOTRADER_EXECUTION_MODE` or seed. `VaultInitError::NonUnicodeExecutionMode` and `InvalidEnvironmentSeedEncoding` are reachable only through `from_env`, while task 3.3 explicitly avoids mutating process-global environment variables. No Verification command covers non-Unicode.
- **Required fix**: Represent the input as `Option<OsString>` or an input enum that can carry non-Unicode bytes, or add a controlled `from_env` integration test; add a non-Unicode mode (and seed) fail-closed test.
- **Status**: open. **Origin**: initial.

### F09 — `docs/architecture.md` still claims engine-rs custody (major)

- **Location**: `docs/architecture.md#L151-L153`; `openspec/changes/mark-vault-simulated/tasks.md#L70`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L233`.
- **Evidence**: The document states "Exchange trade API keys and Solana signing keypairs are injected exclusively into `engine-rs`" and "`engine-rs` operates with a hot trading sub-wallet". The change removes Python Solana signing and does not move exchange keys into engine-rs; the vault is simulated. Task 8.4 only updates the `HardRiskGate` node at line 52. The claim-sweep token list does not include "signing keypairs" or "hot trading sub-wallet", so the gate will not catch this.
- **Required fix**: Update §5 to the simulated reality (no signing keypairs in engine-rs; no Python key custody; no broadcast) and extend task 8.4 to cover the security invariants, not only the diagram node.
- **Status**: open. **Origin**: initial.

### F10 — The audit still counts Solana Devnet self-transfers as measured (major)

- **Location**: `docs/PERFORMANCE_AND_COST_AUDIT.md#L121` and `#L125`; `openspec/changes/mark-vault-simulated/tasks.md#L65-L76`.
- **Evidence**: The audit labels `live_testnet` as "Binance Spot Testnet + Solana Devnet [`MEASURED`]" and counts "162 transactions Devnet self-transfer" in the measured population. The change marks Solana actions `is_simulated: true` and excludes them from `live_testnet`/`measured_realized_pnl_usd`. No task updates this document, and the claim-sweep tokens do not match "Solana Devnet"/"MEASURED".
- **Required fix**: Add a task to revise the `live_testnet` description and numbers (or add a dated note that Solana Devnet actions are simulated and excluded after this change), and add a sweep check for the measured-Solana claim.
- **Status**: open. **Origin**: initial.

### F11 — README still claims "real PnL tracking" for Testnet/Devnet (major)

- **Location**: `README.md#L134`; `openspec/changes/mark-vault-simulated/tasks.md#L68`.
- **Evidence**: README says "Testnet/Devnet Telemetry: Live Solana Devnet wallet balance and real PnL tracking." After the change, the Solana balance is read-only from a configured address and Solana actions are simulated/not measured. Task 8.2 lists Tier 3 wording, the diagram, the vault link, and execution-mode docs, but not this bullet.
- **Required fix**: Rewrite the telemetry bullet to "read-only public-address balance and simulated Solana actions; measured PnL only from CEX testnet" and add a claim-sweep check for "real PnL".
- **Status**: open. **Origin**: initial.

### F12 — No verification for the `/api/v1/testnet/verify` scenario (major)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L80-L85`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L148-L152`; `backend/server.py#L364-L382`.
- **Evidence**: The SPEC scenario "Testnet verification exposes no Python-held key" is implemented by task 5.4 but has no named test or Verification command. Task 9.2 covers the tool and telemetry, not the endpoint; the Verification list never calls `/api/v1/testnet/verify`.
- **Required fix**: Add an endpoint test (or `curl` verification) with `SOLANA_PRIVATE_KEY` set and no public key, asserting no key-derived public key, no private material, `custody: "NONE"`, and `None`/absent balance without an address.
- **Status**: open. **Origin**: initial.

### F13 — Kill-switch coverage is a manual "confirm", not a test, and `checkout_funds` hardcodes `False` (major)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L84`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L118-L125`; `backend/core/hierarchy.py#L1820-L1831`.
- **Evidence**: `checkout_funds` calls `sign_transfer_in_rust_enclave(..., kill_switch_active=False)` hardcoded. The store's `kill_switch_active` is never passed. Task 4.6 only says "Confirm" and task 9.2's signer matrix does not include the kill switch. The SPEC requires the existing kill-switch rejection to remain in force and not be bypassed.
- **Required fix**: Pass the store's kill-switch state (and reason) into `checkout_funds`/`sign_transfer_in_rust_enclave`, return the rejection before mutation, and add a test for (a) kill switch active with no binary and (b) kill switch active with a valid binary.
- **Status**: open. **Origin**: initial.

### F14 — Operator-documentation scenario has no verification command (major)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L68` and `#L75`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L239-L242`.
- **Evidence**: The SPEC scenario "Operator documentation defines the execution mode" requires a reader of `README.md`/`.env.example` to find `ROBOTRADER_EXECUTION_MODE`, its four values, the `PAPER` default, and the fail-closed consequence. The plan implements this in tasks 8.2/8.9 but the Verification list has no `git grep`/assertion over those files.
- **Required fix**: Add a verification command such as `git grep -n 'ROBOTRADER_EXECUTION_MODE' README.md .env.example` plus a small Python assertion for the four values and the empty/unknown warning.
- **Status**: open. **Origin**: initial.

### F15 — Python vault tests do not explicitly assert `signature_is_chain_valid: false` (minor)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L80`; `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L253-L256`.
- **Evidence**: The SPEC says the Rust **and Python** vault suites MUST assert `signature_is_chain_valid: false`. Task 9.1 says "a valid simulated checkout receipt" without naming the flag; task 3.5 covers the Rust test only.
- **Required fix**: Add explicit Python assertions for `simulated is True`, `signature_is_chain_valid is False`, and `whitelist_enforcement == "SIMULATED"` on the checkout receipt.
- **Status**: open. **Origin**: initial.

### F16 — Task 9.2 is too large for one session (minor)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L81`.
- **Evidence**: One task bundles the loader matrix, signer matrix, checkout no-mutation, Solana tool custody, telemetry, and simulated-row population. This exceeds the plan's own "one session per task" rule and makes the evidence hard to review.
- **Required fix**: Split into loader/signer tests, checkout/no-mutation tests, and Solana/telemetry/population tests, or state a concrete session/evidence budget.
- **Status**: open. **Origin**: initial.

### F17 — Task 9.1 removes a still-valid `python_private_key_access` assertion (minor)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L80`; `openspec/changes/mark-vault-simulated/design.md#L122`.
- **Evidence**: Task 9.1 says to remove the `zeroize_on_drop`/`python_private_key_access` fallback assertions, but `python_private_key_access: false` remains in the manifest (D2) and is a truthful field after the Solana custody removal. Removing its assertion loses coverage.
- **Required fix**: Remove only the `zeroize_on_drop` assertion; keep and update `assertFalse(manifest["python_private_key_access"])` in the new test.
- **Status**: open. **Origin**: initial.

### F18 — `docs/architecture.md` still says "three execution modes" (minor)

- **Location**: `docs/architecture.md#L135`; `openspec/changes/mark-vault-simulated/tasks.md#L70`.
- **Evidence**: The document says "Supports three execution modes ... `Backtest`, `Paper`, ... and `Live`"; the change adds `SIMULATED` to `ROBOTRADER_EXECUTION_MODE` (four values) and the vault is simulated. Task 8.4 does not mention this line.
- **Required fix**: Update the execution-mode text to the four values and the simulated vault in task 8.4.
- **Status**: open. **Origin**: initial.

### F19 — LIVE/secret verification is not hermetic (minor)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L113-L120`; `openspec/changes/mark-vault-simulated/design.md#L129`.
- **Evidence**: The commands `env -u ...` and `ROBOTRADER_EXECUTION_MODE=LIVE ...` cannot unset a host-mounted `/run/secrets/robotrader_master_seed`. If that file exists, the expected `DETERMINISTIC_DEVNET`/`ENVIRONMENT` assertions fail.
- **Required fix**: Allow the CLI/bootstrap to take an explicit secret-file path for tests, or run these checks in an isolated container/temp root and document the isolation.
- **Status**: open. **Origin**: initial.

### F20 — Empty-mode operator message is unspecified (minor)

- **Location**: `openspec/changes/mark-vault-simulated/design.md#L233`; `openspec/changes/mark-vault-simulated/tasks.md#L68` and `#L75`.
- **Evidence**: The plan makes an empty `.env` value fail closed but does not specify the `VaultInitError` display text. Without a message naming `ROBOTRADER_EXECUTION_MODE` and the four accepted values, the operator sees a generic 503.
- **Required fix**: Specify the `Display` text for `EmptyExecutionMode`, `InvalidExecutionMode`, and `MissingLiveSeed`, and require README/`.env.example` to state the blank-line failure.
- **Status**: open. **Origin**: initial.

### F21 — Legacy identifiers in historical docs may trip the no-legacy gates (minor)

- **Location**: `openspec/changes/mark-vault-simulated/tasks.md#L72`; `openspec/changes/mark-vault-simulated/tasks.md#L136` and `#L138`.
- **Evidence**: The no-legacy `git grep` excludes `openspec/changes`/`.sdlc` but scans all other files. ADR-0005's context (issue #2) or the vault document may need to name `RustVaultEnclave`/`VaultEnclaveManifest` historically, and the `SOLANA_PRIVATE_KEY` grep scans `docs`. The plan does not say how to describe removed names without failing the gate.
- **Required fix**: State that docs use descriptive language ("the former enclave type", "the removed Solana private-key variable"), or add justified allowlist entries/exclusions; align tasks 8.1/8.6 with the Verification commands.
- **Status**: open. **Origin**: initial.

### F22 — Python import cleanup is incomplete (nit)

- **Location**: `backend/core/hierarchy.py#L3-L4`; `openspec/changes/mark-vault-simulated/tasks.md#L39`.
- **Evidence**: `hashlib` is used by the removed fallback manifest/signer; `hmac` is used only by the removed Python signer. Task 4.2 mentions removing `hashlib` if unused but not `hmac`. An unused import can fail lint/architecture checks.
- **Required fix**: Remove both unused imports (or verify any remaining use) and add the static check to the non-regression suite.
- **Status**: open. **Origin**: initial.

## Checks Run

- `openspec validate mark-vault-simulated --strict` → `Change 'mark-vault-simulated' is valid` (exit 0).
- `scripts/sdlc/sdlc.sh check mark-vault-simulated` → `check: PASS`; `spec-lint` PASS; `openspec validate --strict` pass; `spec-r1` CHANGES_REQUESTED (5 open blocker/major), `spec-r2` APPROVE; 55 open tasks (expected at PLAN).
- `git rev-parse HEAD` → `c3f658d896449835434e1a690b1b0944f85ccb9c`; `git diff --stat` → only `.sdlc/mark-vault-simulated/state.json` modified; `design.md`/`tasks.md` are at HEAD.
- Shell probes:
  - `printf 'Secp256k1 # variant\n' | grep -vEf /tmp/allow.txt` did not filter `Secp256k1EcdsaBip44`; an empty line filters every line.
  - `printf 'target_leaf_derivation_path\n' | grep -n 'leaf_derivation_path'` matched (exit 0), proving the F03 command is unsatisfiable.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "mark-vault-simulated",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "c3f658d896449835434e1a690b1b0944f85ccb9c",
  "verdict": "CHANGES_REQUESTED",
  "summary": "The honest-simulation plan is traceable and covers the main slices, but it is not approvable as written. A fabricated 0.0 SOL balance, an out-of-spec mode normalization, an unvalidated Python receipt path, a dead simulated-Solana branch, a missing-binary test that patches too late, and a claim-sweep allowlist that cannot work with grep -f must be fixed. Two verification commands are objectively unexecutable, and documentation tasks miss stale custody/metric claims in docs/architecture.md, docs/PERFORMANCE_AND_COST_AUDIT.md, and README.md.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "backend/tools/solana_tools.py#L55-L65; backend/server.py#L377-L381; design.md#L263; specs/vault-simulation/spec.md#L148-L152",
      "evidence": "get_balance returns 0.0 when no address is configured, and verify_testnet_connectivity reports balance_sol from it. The SPEC requires any reported balance to be read from a configured public address only; 0.0 is a fabricated plausible default and contradicts the design's own None telemetry.",
      "required_fix": "Return None (Optional[float]) or omit the balance when no configured address exists; update server.py, state_store and tests; add a no-public-key test with SOLANA_PRIVATE_KEY set."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L139; tasks.md#L76; tasks.md#L143",
      "evidence": "The design requires one ERE pattern plus justification per line, but the gate uses grep -vEf. grep treats the whole line as a regex, so 'pattern # justification' does not match; a blank line is an empty regex and filters every line, making the gate vacuous. Reproduced with printf | grep -vEf.",
      "required_fix": "Define a grep -f-compatible allowlist (one ERE per line, no comments/blank lines) with justifications in a sibling file, or add a wrapper that parses pattern+justification and rejects blank lines; add a gate self-test."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L141",
      "evidence": "target_leaf_derivation_path contains leaf_derivation_path, so git grep -n 'leaf_derivation_path' -- frontend/src returns the target line and exits 0; the expected no-output/exit-1 result is impossible.",
      "required_fix": "Use a precise pattern (e.g. git grep -nE '(^|[^_])leaf_derivation_path') or assert the serialized JSON key with Python."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L128; tasks.md#L17; specs/vault-simulation/spec.md#L156",
      "evidence": "D8 normalizes values by trimming and uppercasing, accepting paper, 'PAPER ' and ' Paper'. The SPEC requires exactly four values and says any other non-empty value must fail closed.",
      "required_fix": "Compare the raw value exactly, or escalate a spec change allowing normalization; add tests for paper, 'PAPER ' and ' Paper' with fail-closed results."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L135; tasks.md#L40; backend/core/hierarchy.py#L1147-L1150",
      "evidence": "The signer accepts any zero-exit JSON with signature_hex. 'Valid simulated receipt' is undefined. A stale pre-change binary can return an old receipt without simulated=true, signature_is_chain_valid=false or whitelist_enforcement=SIMULATED; checkout_funds would then mutate capital.",
      "required_fix": "Validate simulated is true, signature_is_chain_valid is false, whitelist_enforcement == SIMULATED, non-empty signature_hex, and matching destination/leaf before returning signed; reject mismatches as rejected_vault_unavailable; add an old-contract-receipt test."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L263; tasks.md#L48; backend/core/state_store.py#L588-L593",
      "evidence": "The Solana branch is guarded by if solana.keypair:. Task 5.1 removes Keypair, making the branch unreachable, while the design says the tick records a simulated Solana action. Task 5.2 does not replace the guard.",
      "required_fix": "Replace the keypair guard with an explicit condition and test the simulated row, or remove the 'records a simulated action' claim and reconcile it with the SPEC scenario."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L82; backend/tests/test_missing_binary.py#L143; backend/core/state_store.py#L982",
      "evidence": "The child imports backend.core.state_store before patching; the module constructs the singleton at import and loads the vault manifest. Patching _rust_binary_candidates before importing backend.server is too late; with the built binary the vault endpoint returns 200, not 503.",
      "required_fix": "Patch HierarchicalFleetManager._rust_binary_candidates before importing backend.core.state_store and backend.server, or inject the candidate list; use a vault-specific 503 assertion."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L127; tasks.md#L16; tasks.md#L30; specs/vault-simulation/spec.md#L156",
      "evidence": "VaultBootstrap uses Option<String> for execution_mode and env_seed, so non-Unicode values cannot be represented. NonUnicodeExecutionMode and InvalidEnvironmentSeedEncoding are only reachable via from_env, which task 3.3 avoids; no test covers them.",
      "required_fix": "Use Option<OsString> or an input enum for the bootstrap, or add a controlled from_env test; add non-Unicode mode and seed fail-closed tests."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "docs/architecture.md#L151-L153; tasks.md#L70; specs/vault-simulation/spec.md#L233",
      "evidence": "docs/architecture.md still says exchange keys and Solana signing keypairs are injected exclusively into engine-rs and that engine-rs operates a hot trading sub-wallet. The change removes Python Solana signing and does not move exchange keys; task 8.4 only updates the HardRiskGate node. The claim sweep does not match these phrases.",
      "required_fix": "Update the security invariants to the simulated reality and extend task 8.4 and the sweep tokens to cover them."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "docs/PERFORMANCE_AND_COST_AUDIT.md#L121; docs/PERFORMANCE_AND_COST_AUDIT.md#L125; tasks.md#L65-L76",
      "evidence": "The audit labels live_testnet as Binance Spot Testnet + Solana Devnet MEASURED and counts 162 Devnet self-transfers in the measured population. The change marks those rows simulated and excludes them; no task updates the audit.",
      "required_fix": "Add a task to revise the live_testnet description/numbers or add a dated simulation note, and add a sweep check for the measured-Solana claim."
    },
    {
      "id": "PLAN-R1-F11",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "README.md#L134; tasks.md#L68",
      "evidence": "README says 'Live Solana Devnet wallet balance and real PnL tracking'. After the change the balance is read-only from a configured address and Solana actions are simulated/not measured. Task 8.2 does not name this bullet.",
      "required_fix": "Rewrite the telemetry bullet and add a claim-sweep check for 'real PnL'."
    },
    {
      "id": "PLAN-R1-F12",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L80-L85; specs/vault-simulation/spec.md#L148-L152; backend/server.py#L364-L382",
      "evidence": "The SPEC scenario 'Testnet verification exposes no Python-held key' is implemented by task 5.4 but has no named test or Verification command; the new suite covers the tool and telemetry, not the endpoint.",
      "required_fix": "Add an endpoint test or curl check with SOLANA_PRIVATE_KEY set and no public key, asserting no key-derived public key, no private material, custody NONE, and no fabricated balance."
    },
    {
      "id": "PLAN-R1-F13",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L84; specs/vault-simulation/spec.md#L118-L125; backend/core/hierarchy.py#L1820-L1831",
      "evidence": "checkout_funds hardcodes kill_switch_active=False and never passes the store's kill switch. Task 4.6 only says 'Confirm', and task 9.2 does not test the kill switch. The SPEC requires the existing rejection to remain in force.",
      "required_fix": "Pass the store's kill-switch state into checkout_funds/sign_transfer_in_rust_enclave, return a rejection before mutation, and test active-kill-switch cases with and without a binary."
    },
    {
      "id": "PLAN-R1-F14",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L68; tasks.md#L75; specs/vault-simulation/spec.md#L239-L242",
      "evidence": "The operator-documentation scenario requires README/.env.example to document ROBOTRADER_EXECUTION_MODE, its four values, the PAPER default and the fail-closed consequence. The Verification list has no assertion over those files.",
      "required_fix": "Add a git grep/Python assertion over README.md and .env.example for the variable, the four values and the empty/unknown warning."
    },
    {
      "id": "PLAN-R1-F15",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L80; specs/vault-simulation/spec.md#L253-L256",
      "evidence": "The SPEC requires the Rust and Python vault suites to assert signature_is_chain_valid=false. Task 9.1 mentions only 'a valid simulated checkout receipt'; the explicit flag is covered by the Rust test, not named for Python.",
      "required_fix": "Add explicit Python assertions for simulated=true, signature_is_chain_valid=false and whitelist_enforcement=SIMULATED on the checkout receipt."
    },
    {
      "id": "PLAN-R1-F16",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L81",
      "evidence": "Task 9.2 bundles the loader matrix, signer matrix, checkout no-mutation, Solana tool custody, telemetry and simulated-row population; this exceeds the one-session task rule.",
      "required_fix": "Split task 9.2 into loader/signer, checkout/no-mutation, and Solana/telemetry/population tasks, or record a concrete session/evidence budget."
    },
    {
      "id": "PLAN-R1-F17",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L80; design.md#L122",
      "evidence": "Task 9.1 says to remove the zeroize_on_drop and python_private_key_access assertions, but python_private_key_access=false remains in the manifest and is truthful after the custody removal.",
      "required_fix": "Remove only the zeroize_on_drop assertion; keep and update the python_private_key_access is False assertion."
    },
    {
      "id": "PLAN-R1-F18",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "docs/architecture.md#L135; tasks.md#L70",
      "evidence": "docs/architecture.md still says three execution modes (Backtest, Paper, Live); the change adds SIMULATED to ROBOTRADER_EXECUTION_MODE (four values). Task 8.4 does not mention this line.",
      "required_fix": "Update the execution-mode text to the four values and the simulated vault in task 8.4."
    },
    {
      "id": "PLAN-R1-F19",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L113-L120; design.md#L129",
      "evidence": "The LIVE/secret-file verification commands cannot unset a host-mounted /run/secrets/robotrader_master_seed; if present, the expected DETERMINISTIC_DEVNET/ENVIRONMENT assertions fail.",
      "required_fix": "Allow an explicit secret-file path for tests or run the checks in an isolated container/temp root and document the isolation."
    },
    {
      "id": "PLAN-R1-F20",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L233; tasks.md#L68; tasks.md#L75",
      "evidence": "The plan makes an empty .env value fail closed but does not specify the VaultInitError display text naming ROBOTRADER_EXECUTION_MODE and the accepted values; the operator would see a generic 503.",
      "required_fix": "Specify the Display text for EmptyExecutionMode, InvalidExecutionMode and MissingLiveSeed, and require README/.env.example to state the blank-line failure."
    },
    {
      "id": "PLAN-R1-F21",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L72; tasks.md#L136; tasks.md#L138",
      "evidence": "The no-legacy gates scan all non-openspec/.sdlc files. ADR-0005 context or the vault document may need to name RustVaultEnclave/VaultEnclaveManifest historically, and the SOLANA_PRIVATE_KEY grep scans docs; the plan does not say how to describe removed names without failing the gates.",
      "required_fix": "State that docs use descriptive language for removed names, or add justified allowlist entries/exclusions; align tasks 8.1/8.6 with the Verification commands."
    },
    {
      "id": "PLAN-R1-F22",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "backend/core/hierarchy.py#L3-L4; tasks.md#L39",
      "evidence": "hashlib is used by the removed fallback manifest/signer; hmac is used only by the removed Python signer. Task 4.2 mentions hashlib but not hmac.",
      "required_fix": "Remove both unused imports (or verify remaining use) and add the static check to the non-regression suite."
    }
  ],
  "closed": []
}
```

# SPEC Review — Round 1

## Summary

CHANGES REQUESTED. The delta spec is well-shaped and the three stage checks pass, but it does not yet close the false-guarantee surface it exists to close. Five major gaps: `key_isolation_mode` can still carry HD/zeroize claims; the seed-source field is unnamed; the breaking whitelist contract is underdetermined; the repository-wide false-claim check omits code docstrings, `docs/architecture.md`, `sdlc/checklists/dev.md`, and `openspec/config.yaml`; and the missing-binary requirement ("MAY start") can break the existing `test_missing_binary.py` endpoint contract. `ROBOTRADER_EXECUTION_MODE` is in scope, justified, and testable — no `TRADING_ENV` or other global mode exists — but its silent-PAPER residual risk and operator documentation must be added. Keeping `curve` as target metadata is honest enough with `simulated: true` and a notice; `key_isolation_mode` is not.

## Assessed as sound

- Capability mapping is one-to-one: `vault-simulation` has exactly one delta spec.
- 8 requirements / 31 scenarios; all use SHALL/MUST and WHEN/THEN; names are unique.
- Non-goals are explicit and the out-of-scope real derivation/signing/mainnet custody list keeps issue #2 open.
- Review Card: 154 words, 1 Mermaid diagram, ~1.3 min read (spec-lint).
- The Python key-custody and Solana broadcast removal is correctly scoped; no `PolicyEnvelope` or strategy-pod change.
- Deriving `destination_whitelisted` and `key_zeroized_after_sign` from observations is the right direction.
- Ruling on `ROBOTRADER_EXECUTION_MODE`: keep it. No `TRADING_ENV` exists; `BINANCE_TESTNET` and `SOLANA_RPC_URL` are venue-scoped and cannot represent a global execution mode. The variable is testable and directly needed for the requested live-mode gate.
- Ruling on curve metadata: keep `curve` as target metadata, qualified by the descriptor's `simulated: true`, `address_is_spendable: false`, and the manifest `simulation_notice`. Do not remove it. The unqualified `key_isolation_mode` is a different case and must be fixed.

## Findings

### SPEC-R1-F01 — [major] `key_isolation_mode` can still carry an explicit HD/zeroize/custody guarantee
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L34-L54` (Requirement 2 and its scenarios)
- Evidence: `engine-rs/crates/risk-gate/src/vault.rs#L567-L578` currently emits `key_isolation_mode` values such as `RUST_ENCLAVE_HD_ZEROIZE (Private Key Never Enters Python)` and `RUST_ENCLAVE_HMAC_TRADE_ONLY (Withdrawals Disabled at Exchange)`. Requirement 2 enumerates BIP/SLIP/curve scheme names but not this field, and the "No repository text asserts the false guarantee" scenario searches only vault documentation, README, AGENTS.md, ADR-0003, and UI source. A descriptor can therefore set `simulated: true` and still carry an "HD_ZEROIZE" guarantee.
- Required fix: add a requirement that `key_isolation_mode` (and any other descriptor string field) is removed or set to a `SIMULATED_*` value that claims neither HD derivation, zeroization, custody, nor exchange withdrawal enforcement; add a scenario asserting no descriptor string outside `simulation_notice` claims an implemented guarantee.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [major] The seed-source field is unnamed, so the manifest contract is not testable
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L5` and `#L7-L19`
- Evidence: Requirement 1 says "The seed source MUST be reported in a field other than `vault_mode`", and three scenarios assert "the seed source is reported separately", but no field name or allowed values are defined. A test cannot assert a stable key or value; the author can choose `seed_source`, `seed_mode`, or anything else.
- Required fix: name the field (for example `seed_source`) and define its allowed values and their mapping to the three origins (`/run/secrets/...`, `ROBOTRADER_VAULT_MASTER_SEED`, deterministic devnet seed); add scenarios asserting the exact field/value for each source.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [major] The breaking whitelist contract is underdetermined
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L170-L196` (Requirement 7)
- Evidence: The requirement says the "manifest and receipts MUST label whitelist enforcement as simulated through a `whitelist_enforcement` value of `SIMULATED`", but it does not say whether that member is top-level or per-wallet, and no scenario covers the receipt. It also says the per-wallet `withdrawal_whitelist_enforced` boolean "MUST NOT remain an unqualified `true`" without requiring either removal or a specific replacement value. Several incompatible JSON contracts satisfy this text.
- Required fix: define the exact shape: top-level manifest `whitelist_enforcement: "SIMULATED"`; per-wallet `withdrawal_whitelist_enforced` removed or set to `false`; receipt `whitelist_enforcement: "SIMULATED"`. Add scenarios for the receipt and the per-wallet field.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [major] The "no false guarantee remains" check excludes known false claims
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L50-L54` (scenario "No repository text asserts the false guarantee") and `#L198-L224` (Requirement 8)
- Evidence: The scenario's search set is vault documentation, README, AGENTS.md, ADR-0003, and UI source; Requirement 8 lists only four documents. False or stale claims remain outside that set: `backend/server.py#L201-L202` ("BIP-32 / BIP-44 / SLIP-0010 ... RustVaultEnclave"), `backend/core/hierarchy.py#L1066` ("BIP-32 / BIP-44 / SLIP-0010 wallet descriptors"), `engine-rs/crates/risk-gate/src/vault.rs#L128` ("BIP-32 / SLIP-0010 child key derivation and signing"), `docs/architecture.md#L52` (`RustVaultEnclave`), `sdlc/checklists/dev.md#L28` ("`RustVaultEnclave` zeroizes volatile RAM; destination whitelist is enforced"), and `openspec/config.yaml#L21` ("Vault material never leaves `RustVaultEnclave`"). The DEV checklist is the most serious: it would instruct a future DEV reviewer to assert the very guarantee this change removes.
- Required fix: extend Requirement 2/8 and the search scenario to source docstrings/comments and these repository artifacts, or replace the file list with a repo-wide search with an explicit allowlist. Add a task to update `docs/architecture.md`, `sdlc/checklists/dev.md`, and `openspec/config.yaml`.
- Status: open
- Origin: initial

### SPEC-R1-F05 — [major] The existing missing-binary endpoint contract is not preserved; "MAY start" is too weak
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L56-L76` (Requirement 3, especially L58) and `#L220-L224` (existing fail-closed scenario)
- Evidence: `backend/tests/test_missing_binary.py` (child script, L192-L259) asserts that with the Rust binary unavailable the backend still starts and `/api/v1/status`, `/api/v1/hierarchy`, `/api/v1/backtest/run`, `/api/v1/policy/regime`, and `/api/v1/health` keep their existing 503/200 contracts. If the new fail-closed `_load_rust_vault_manifest` raises inside `HierarchicalFleetManager.__init__`, the server import fails and this test breaks. The spec says only that "The backend MAY start without the Rust binary" and the "Existing fail-closed tests remain green" scenario lists only kill-switch, negative-amount, and unknown-leaf tests.
- Required fix: change "MAY start" to "MUST remain importable/startable" (or equivalent), state how the missing manifest is represented (empty/absent, no fallback values), and add a scenario that the `test_missing_binary.py` endpoint contract remains green while `GET /api/v1/vault/manifest` returns 503.
- Status: open
- Origin: initial

### SPEC-R1-F06 — [minor] `ROBOTRADER_EXECUTION_MODE` is justified, but its residual risk and operator documentation are missing
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L135-L168`; `openspec/changes/mark-vault-simulated/proposal.md#L5`, `#L8`, `#L60`
- Evidence: A repo-wide search finds zero occurrences of `TRADING_ENV`; the only mode-like settings are `BINANCE_TESTNET` and the venue RPC URL. The new variable is therefore necessary and testable, not scope creep. However, when unset or unrecognized it defaults to `PAPER` and may use the deterministic devnet seed; a live-intended deployment that forgets or typos the variable still gets the devnet seed (the manifest is `SIMULATED`, so the residual risk is honesty, not fund loss). The proposal's Risk row does not state this, and Requirement 8 does not require `.env.example` or README to document the variable even though the Impact section lists `.env.example`.
- Required fix: document `ROBOTRADER_EXECUTION_MODE` (values, default, security meaning) in `.env.example` and README; add the residual-risk statement to the proposal; and consider failing closed on an unrecognized value rather than silently treating it as `PAPER`.
- Status: open
- Origin: initial

### SPEC-R1-F07 — [minor] Review Card does not match the spec's seed sources or its own risk statement
- Location: `openspec/changes/mark-vault-simulated/proposal.md#L5`, `#L8`, `#L28`
- Evidence: The Card says "live mode refuses to start without a secret-mounted seed", but Requirement 6 also accepts a non-empty `ROBOTRADER_VAULT_MASTER_SEED`. The Card's "Worst failure" says a paper or devnet run can be refused because "the seed is unavailable", but in `BACKTEST`/`PAPER`/`SIMULATED` the deterministic seed may be used; only an unavailable binary refuses. The silent-PAPER risk is absent.
- Required fix: say "without seed material (secret mount or environment)" and align the risk row with the spec, including the unrecognized-mode risk.
- Status: open
- Origin: initial

### SPEC-R1-F08 — [minor] The proposal omits the existing build-packaging requirement on the vault candidate list
- Location: `openspec/changes/mark-vault-simulated/proposal.md#L41-L43`
- Evidence: `openspec/specs/build-packaging/spec.md#L131` states that the separate vault-manifest/sign-transfer candidate list in `backend/core/hierarchy.py` is out of scope and MUST remain unchanged. The proposal says "no existing requirement governs vault claims". The new change does not need to change the candidate list, so there is no direct contradiction, but the capability analysis should acknowledge the requirement and confirm it is unaffected.
- Required fix: add one sentence confirming the candidate list remains unchanged and the build-packaging requirement stays satisfied, or add a MODIFIED requirement if the list changes.
- Status: open
- Origin: initial

### SPEC-R1-F09 — [minor] `curve` is qualified; the derivation-path and SLIP-44 metadata are not
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L34-L54`
- Evidence: Requirement 2 explicitly permits a retained `curve` only with `simulated: true` and target-qualified text, which is honest. But `PublicWalletDescriptor` also carries `master_derivation_path`, `leaf_derivation_path`, and `slip44_coin_type`; the spec does not qualify these. They remain BIP-44-shaped values that a machine consumer can read as an implemented derivation.
- Required fix: extend the `simulation_notice`/Requirement 2 to cover all target metadata (`curve`, both derivation paths, and `slip44_coin_type`), or rename the path fields (for example `target_derivation_path`); add a scenario.
- Status: open
- Origin: initial

### SPEC-R1-F10 — [minor] Live-mode seed precedence and combinations are ambiguous
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L135-L168`
- Evidence: Requirement 6 says a missing/unreadable/whitespace secret file "and" a missing/empty `ROBOTRADER_VAULT_MASTER_SEED` must fail. The scenarios cover neither source and an empty secret file, but not (a) secret file absent with a valid environment seed, or (b) empty secret file with a valid environment seed. The conjunction can be read as "both missing" or as "each condition fails".
- Required fix: define the precedence (`/run/secrets/...` first, environment second) and the four combinations explicitly; add scenarios for environment-only live construction and for an empty secret file that must fail even when an environment seed is present (or state the opposite).
- Status: open
- Origin: initial

### SPEC-R1-F11 — [nit] Duplicate non-live devnet-seed scenarios
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L14-L19` and `#L158-L162`
- Evidence: R1 scenario 2 and R6 scenario 4 assert nearly the same manifest behavior for the deterministic devnet seed.
- Required fix: consolidate them or make each assert a distinct fact (for example, R1 asserts the manifest seed source; R6 asserts the effective default mode).
- Status: open
- Origin: initial

## Checks run

- `openspec validate mark-vault-simulated --strict` → `Change 'mark-vault-simulated' is valid`.
- `scripts/sdlc/spec-lint.py --change mark-vault-simulated` → `PASS` (Review Card 154 words, 1 diagram, ~1.3 min; `design.md`/`tasks.md` warnings are expected at PLAN).
- `scripts/sdlc/sdlc.sh check mark-vault-simulated` → `PASS` (change valid; no verdicts yet).
- `PYTHONPATH=. python3 -m unittest backend.tests.test_missing_binary -v` → could not run in this environment: `ModuleNotFoundError: No module named 'fastapi'`. The file is cited statically as the existing endpoint contract; this environment limitation is not a failure of the spec.
- Read time: Review Card 1.3 min (spec-lint); full review ~35 min.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "mark-vault-simulated",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "a991e6df72e0264362f910bb9de7ec843a5e2d83",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Five major gaps remain in the honest-simulation contract: key_isolation_mode can still claim HD/zeroize, the seed-source field is unnamed, the breaking whitelist contract is ambiguous, the repository-wide false-claim check omits code docstrings and the DEV checklist, and the missing-binary requirement can break the existing backend-start contract. ROBOTRADER_EXECUTION_MODE is justified (no existing global mode exists) but needs residual-risk and documentation coverage; curve metadata is acceptable only with the requested target qualification.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L34-L54; engine-rs/crates/risk-gate/src/vault.rs#L567-L578",
      "evidence": "key_isolation_mode currently emits values such as RUST_ENCLAVE_HD_ZEROIZE (Private Key Never Enters Python); Requirement 2 enumerates crypto scheme names but not this descriptor field, so a simulated descriptor can still carry an HD/zeroize guarantee.",
      "required_fix": "Require key_isolation_mode (and any other descriptor string field) to be removed or set to a SIMULATED_* value with no HD, zeroize, custody, or exchange-withdrawal claim; add a scenario covering it."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L5 and #L7-L19",
      "evidence": "The seed source must be reported 'in a field other than vault_mode', but no field name or allowed values are defined; three scenarios assert separate reporting without a stable key to assert.",
      "required_fix": "Name the seed-source field and define its allowed values and mapping to the secret file, environment seed, and deterministic devnet seed; add scenarios with exact field/value assertions."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L170-L196",
      "evidence": "The requirement does not state whether whitelist_enforcement is top-level or per-wallet, does not cover the receipt in a scenario, and does not require removal or a specific replacement for withdrawal_whitelist_enforced; several incompatible contracts satisfy the text.",
      "required_fix": "Define the exact JSON shape for manifest, wallet descriptor, and receipt; require withdrawal_whitelist_enforced to be removed or false; add receipt and per-wallet scenarios."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L50-L54 and #L198-L224",
      "evidence": "The search set excludes backend/server.py#L201-L202, backend/core/hierarchy.py#L1066, engine-rs/crates/risk-gate/src/vault.rs#L128, docs/architecture.md#L52, sdlc/checklists/dev.md#L28, and openspec/config.yaml#L21, all of which still carry BIP/SLIP/HD/RustVaultEnclave/whitelist-enforced claims.",
      "required_fix": "Extend the false-claim requirement and scenario to source docstrings/comments and the named repository artifacts, or use a repo-wide search with an explicit allowlist; add a task to update them."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L56-L76 and #L220-L224",
      "evidence": "backend/tests/test_missing_binary.py asserts that the backend still starts with the Rust binary unavailable and preserves the 503/200 endpoint contracts; the spec only says the backend MAY start, so a fail-closed manifest loader that raises at construction would break this existing contract, which the existing-tests scenario does not list.",
      "required_fix": "Require the backend to remain importable/startable without the binary, state how the missing manifest is represented, and add a scenario that the test_missing_binary.py endpoint contract stays green while the vault manifest returns 503."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L135-L168; openspec/changes/mark-vault-simulated/proposal.md#L5, #L8, #L60",
      "evidence": "No TRADING_ENV exists; the new variable is necessary and testable, but unset/unrecognized defaults to PAPER with the devnet seed, the proposal does not state that residual risk, and Requirement 8 does not require .env.example/README documentation although Impact lists .env.example.",
      "required_fix": "Document ROBOTRADER_EXECUTION_MODE in .env.example and README, add the residual-risk statement to the proposal, and consider failing closed on an unrecognized value."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/proposal.md#L5, #L8, #L28",
      "evidence": "The Review Card says live mode needs a secret-mounted seed, while Requirement 6 also accepts ROBOTRADER_VAULT_MASTER_SEED; it also says a paper/devnet run can be refused for an unavailable seed, while non-live modes may use the deterministic seed and only a missing binary refuses.",
      "required_fix": "Align the Card with the spec's two seed sources and non-live devnet seed, and state the silent-PAPER residual risk."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/proposal.md#L41-L43",
      "evidence": "openspec/specs/build-packaging/spec.md#L131 requires the separate vault-manifest/sign-transfer candidate list in backend/core/hierarchy.py to remain unchanged, yet the proposal states that no existing requirement governs vault claims.",
      "required_fix": "Acknowledge the build-packaging requirement and confirm the candidate list remains unchanged, or add a MODIFIED requirement if it changes."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L34-L54",
      "evidence": "Only curve is qualified as target metadata; master_derivation_path, leaf_derivation_path, and slip44_coin_type remain BIP-44-shaped values that can be read as an implemented derivation.",
      "required_fix": "Extend the target qualification to all derivation/slip44 metadata or rename the path fields; add a scenario."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L135-L168",
      "evidence": "The requirement's 'and' between the secret file and environment seed is ambiguous, and no scenario covers secret-absent plus valid environment seed or empty secret plus valid environment seed.",
      "required_fix": "Define the seed-source precedence and the four combinations explicitly; add scenarios for environment-only construction and the empty-secret fail-closed case."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L14-L19 and #L158-L162",
      "evidence": "R1 scenario 2 and R6 scenario 4 assert nearly the same non-live devnet-seed manifest behavior.",
      "required_fix": "Consolidate the scenarios or give each a distinct assertion."
    }
  ],
  "closed": []
}
```

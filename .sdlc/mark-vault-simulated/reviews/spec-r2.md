# SPEC Review — Round 2

## Summary

APPROVED. All eleven R1 findings are closed at `65ae705`. `key_isolation_mode` is banned or forced to `SIMULATED_*` with the two legacy values named forbidden; `seed_source` is named with three exact values and per-source assertions; the whitelist shape is fixed at manifest, receipt, and per-wallet levels; the false-claim sweep now covers the six named code and process artifacts with an allowlist; the backend must stay startable with an empty `vault_manifest` and the full `test_missing_binary.py` contract; `ROBOTRADER_EXECUTION_MODE` fails closed on unrecognized values and is documented; the Card, build-packaging acknowledgment, `target_*` rename, seed precedence, and duplicate scenario are fixed. `curve` stays a target scheme only under the three required qualifications. The issue remains partial. Non-blocking follow-ups: empty-string mode, allowlist location, `test_hierarchy_v3.py`, and the frontend field rename.

## Assessed as sound

- 8 requirements / 37 scenarios; all use SHALL/MUST, every scenario has WHEN/THEN, all names unique (verified by script and `openspec validate --strict`).
- No contradiction introduced with `openspec/specs/contract`, `build-packaging`, or `integrity`; the `build-packaging` candidate-list requirement is explicitly acknowledged and unchanged.
- The breaking manifest/receipt contract is coherent: `target_*` renames, `simulated`, `address_is_spendable`, `signature_is_chain_valid`, `whitelist_enforcement`, and `seed_source` are additive or rename-only; the Python fail-closed path does not mutate state.
- `curve` remains permitted only when the descriptor sets `simulated: true`, `address_is_spendable: false`, and `simulation_notice` qualifies it as target metadata.
- Non-goals exclude real derivation, address encoding, chain signatures, and mainnet custody; `partial_issue` is true and the issue stays open.
- Review Card: 169 words, 1 diagram, ~1.3 min (spec-lint), ≤ 400 words and ≤ 5.0 min.
- No false-guarantee wording remains in the contract surface: manifest, receipt, API, UI, docs, docstrings, tests, and process artifacts are all covered.

## Findings

### SPEC-R1-F01 — [major] `key_isolation_mode` can still carry an explicit HD/zeroize/custody guarantee
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L35` (Requirement 2) and `#L50-L54` (scenario)
- Evidence: Requirement 2 now requires `key_isolation_mode` to be removed or set to a `SIMULATED_*` value claiming neither HD derivation, zeroization, custody, nor exchange-withdrawal enforcement, and names `RUST_ENCLAVE_HD_ZEROIZE` and `RUST_ENCLAVE_HMAC_TRADE_ONLY` as forbidden. Scenario "Key isolation mode claims no custody guarantee" asserts the `SIMULATED_` prefix and the absence of both legacy values.
- Required fix: Applied — requirement and scenario added.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [major] The seed-source field is unnamed, so the manifest contract is not testable
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L5`, scenarios `#L7-L18` and `#L183-L188`
- Evidence: Requirement 1 names the top-level `seed_source` field and enumerates exactly `SECRET_FILE`, `ENVIRONMENT`, `DETERMINISTIC_DEVNET`, selected by the R6 precedence. Scenarios assert `seed_source: SECRET_FILE`, `seed_source: ENVIRONMENT`, and `seed_source: DETERMINISTIC_DEVNET` with exact values.
- Required fix: Applied — field named, values enumerated, exact assertions added.
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [major] The breaking whitelist contract is underdetermined
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L199` (Requirement 7), scenarios `#L213-L229`
- Evidence: Requirement 7 fixes the shape: top-level manifest `whitelist_enforcement: "SIMULATED"`; per-wallet `withdrawal_whitelist_enforced` removed, or `false` (never `true`); every signed receipt `whitelist_enforcement: "SIMULATED"`. Scenarios "Manifest carries the top-level simulated whitelist label" and "Receipt carries the simulated whitelist label" cover both levels.
- Required fix: Applied — exact shape and both scenarios added.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [major] The "no false guarantee remains" check excludes known false claims
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L33-L35` (Requirement 2) and `#L62-L66` (sweep scenario); `proposal.md#L61`
- Evidence: The sweep scenario now names `docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md`, `README.md`, `AGENTS.md`, ADR-0003, `docs/architecture.md`, `sdlc/checklists/dev.md`, `openspec/config.yaml`, `backend/server.py`, `backend/core/hierarchy.py`, `engine-rs/crates/risk-gate/src/vault.rs`, and frontend sources, plus docstrings, comments, test names, and process artifacts, with an explicit allowlist. All cited claims still exist at this SHA (`docs/architecture.md#L52`, `sdlc/checklists/dev.md#L28`, `openspec/config.yaml#L21`, `backend/server.py#L201-L202`, `backend/core/hierarchy.py#L1066`, `vault.rs#L128`), so the requirement is materially needed; the proposal Impact lists all of them.
- Required fix: Applied — repo-wide sweep with named targets and allowlist.
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [major] The existing missing-binary endpoint contract is not preserved; "MAY start" is too weak
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L70` (Requirement 3) and `#L90-L95` (startup scenario)
- Evidence: Requirement 3 now requires the backend to stay importable and startable, `HierarchicalFleetManager` construction not to raise, and `vault_manifest` to be an empty mapping with no `wallets` key (or absent). The listed 503 contract (`/api/v1/status`, `/api/v1/hierarchy`, `/api/v1/backtest/run`, leaf backtest, `/api/v1/policy/regime`, `/api/v1/chat`, `/api/v1/risk/kill`) and the 200 `/api/v1/health` contract match `backend/tests/test_missing_binary.py#L208-L258` exactly. Scenario "Missing-binary startup contract remains green" adds the 503 manifest endpoint.
- Required fix: Applied — MUST-start wording, empty-manifest representation, and scenario added.
- Status: closed
- Origin: initial

### SPEC-R1-F06 — [minor] `ROBOTRADER_EXECUTION_MODE` is justified, but its residual risk and operator documentation are missing
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L156`, `#L190-L195`, `#L241-L245`; `proposal.md#L8`
- Evidence: Requirement 6 fails closed on any non-empty unrecognized value; scenario "Unrecognized mode fails closed" asserts no silent `PAPER`. Requirement 8's "Operator documentation defines the execution mode" scenario names `README.md` and `.env.example`, the four values, the `PAPER` default, and the security consequence. The proposal Risk row now states the silent-`PAPER` residual risk and the fail-closed behaviors.
- Required fix: Applied — fail-closed, documentation, and risk statement added.
- Status: closed
- Origin: initial

### SPEC-R1-F07 — [minor] Review Card does not match the spec's seed sources or its own risk statement
- Location: `openspec/changes/mark-vault-simulated/proposal.md#L5`, `#L8`
- Evidence: Outcome now says "without seed material (secret mount or environment)", matching Requirement 6's two sources. Risk row now states the silent-`PAPER` residual risk, the fail-closed unrecognized value, and that an unavailable binary refuses vault operations instead of claiming a seed refusal.
- Required fix: Applied — Outcome and Risk aligned with the spec.
- Status: closed
- Origin: initial

### SPEC-R1-F08 — [minor] The proposal omits the existing build-packaging requirement on the vault candidate list
- Location: `openspec/changes/mark-vault-simulated/proposal.md#L44`
- Evidence: Modified Capabilities now acknowledges `openspec/specs/build-packaging/spec.md#L131`: the separate vault-manifest/sign-transfer candidate list in `backend/core/hierarchy.py` remains unchanged and the existing requirement stays satisfied. This change does not modify `_rust_binary_candidates`, so no MODIFIED delta is required.
- Required fix: Applied — acknowledgment sentence added.
- Status: closed
- Origin: initial

### SPEC-R1-F09 — [minor] `curve` is qualified; the derivation-path and SLIP-44 metadata are not
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L35`, scenarios `#L37-L48`
- Evidence: Requirement 2 renames the fields to `target_master_derivation_path`, `target_leaf_derivation_path`, and `target_slip44_coin_type`, and forbids the unqualified names in the manifest. Scenario "Unqualified derivation field names are absent" asserts both the presence of the `target_*` names and the absence of the unqualified ones; "Curve and derivation metadata are target-qualified" asserts the descriptor flags and the notice. The `curve` qualification (simulated, non-spendable, notice) is unchanged and intact.
- Required fix: Applied — `target_*` rename plus both scenarios.
- Status: closed
- Origin: initial

### SPEC-R1-F10 — [minor] Live-mode seed precedence and combinations are ambiguous
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L156`, scenarios `#L158-L181`
- Evidence: Requirement 6 defines the precedence (non-empty secret file, else non-empty environment seed, else live failure, else non-live deterministic seed) and treats empty/unreadable secret files as absent. Scenarios cover both-missing live failure, whitespace secret with a valid environment seed (`ENVIRONMENT`), environment-only live construction, secret precedence over the environment, and the non-live deterministic seed.
- Required fix: Applied — precedence and the four combinations defined and tested.
- Status: closed
- Origin: initial

### SPEC-R1-F11 — [nit] Duplicate non-live devnet-seed scenarios
- Location: `openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L14-L18` and `#L183-L188`
- Evidence: The duplicate deterministic-seed scenario was removed from Requirement 1, which now asserts secret and environment provenance only. The remaining scenario in Requirement 6 asserts distinct facts: effective mode `PAPER` and `seed_source: DETERMINISTIC_DEVNET`.
- Required fix: Applied — scenarios consolidated and differentiated.
- Status: closed
- Origin: initial

## Follow-ups (non-blocking)

- Empty-string `ROBOTRADER_EXECUTION_MODE` is undefined: Requirement 6 covers only unset and non-empty values. Define the empty case (treat as unset or fail closed) in PLAN/DEV.
- The "explicit allowlist of approved simulation statements" has no named location or format. Pin it (for example a committed allowlist file) during PLAN so the sweep is reproducible.
- `backend/tests/test_hierarchy_v3.py::test_rust_vault_enclave_26_chains_and_whitelist_enforcement` still asserts the removed Python fallback (`python_private_key_access`, `zeroize_on_drop`, 26 wallets). Requirement 8 already forbids relying on it; name it in the Impact when PLAN derives tasks.
- `frontend/src/components/LeafAgentView.jsx#L214` reads `leaf_derivation_path`; update it to `target_leaf_derivation_path` with the contract rename.
- `VaultEnclaveManifest` retains "Enclave" in its public type name. Requirement 1 bans only `RustVaultEnclave`; consider renaming during PLAN for consistency.

## Checks run

- `openspec validate mark-vault-simulated --strict` → `Change 'mark-vault-simulated' is valid`.
- `scripts/sdlc/spec-lint.py --change mark-vault-simulated` → `PASS` (Review Card 169 words, 1 diagram, ~1.3 min; `design.md`/`tasks.md` warnings expected at PLAN).
- `scripts/sdlc/sdlc.sh check mark-vault-simulated` → `PASS` (change valid; spec-r1 verdict parsed: 5 open blocker/major, 11 findings).
- Structural script check → 8 requirements, 37 scenarios, no duplicate names, every scenario has WHEN and THEN, no TBD/TODO.
- Static verification of `backend/tests/test_missing_binary.py#L208-L258` → the endpoint list and status codes reproduced by Requirement 3 are exact.
- `test_missing_binary.py` not executed: `fastapi` is not importable in this environment (`ModuleNotFoundError`). The contract was verified statically, as in R1; this is an environment limitation, not a spec failure.
- Read time: Review Card 1.3 min (spec-lint); full closure review ~25 min.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "mark-vault-simulated",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "65ae70510af46b7a29f2ee6abb097a875ea58777",
  "verdict": "APPROVE",
  "summary": "All eleven R1 findings are closed: key_isolation_mode is banned or SIMULATED_*, seed_source is named with exact values, the whitelist shape is fixed at every level, the false-claim sweep covers the named code and process artifacts with an allowlist, the backend must stay startable with an empty vault_manifest and the test_missing_binary.py contract, ROBOTRADER_EXECUTION_MODE fails closed and is documented, and the Card, build-packaging acknowledgment, target_* rename, seed precedence, and duplicate scenario are corrected. curve remains target-qualified, the issue stays partial, and no new blocker or major was introduced.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L35, #L50-L54",
      "evidence": "Requirement 2 bans or SIMULATED_-qualifies key_isolation_mode, names RUST_ENCLAVE_HD_ZEROIZE and RUST_ENCLAVE_HMAC_TRADE_ONLY as forbidden, and forbids other descriptor string fields from claiming an implemented guarantee; the scenario asserts the prefix and both absences.",
      "required_fix": "Applied: requirement and scenario added."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L5, #L7-L18, #L183-L188",
      "evidence": "seed_source is a top-level field with exactly SECRET_FILE, ENVIRONMENT, DETERMINISTIC_DEVNET and exact per-source assertions.",
      "required_fix": "Applied: field named, values enumerated, scenarios added."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L199, #L213-L229",
      "evidence": "Top-level manifest whitelist_enforcement SIMULATED, per-wallet withdrawal_whitelist_enforced removed or false (never true), and every receipt whitelist_enforcement SIMULATED are fixed; manifest and receipt scenarios cover both.",
      "required_fix": "Applied: exact shape and scenarios added."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L33-L35, #L62-L66",
      "evidence": "The sweep scenario names all six R1 artifacts plus docstrings, comments, test names, and process artifacts, with an explicit allowlist; proposal Impact lists the same files.",
      "required_fix": "Applied: repo-wide sweep with named targets and allowlist."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L70, #L90-L95",
      "evidence": "The backend MUST remain importable and startable, construction MUST NOT raise, vault_manifest MUST be empty or absent, and the full test_missing_binary.py 503/200 contract is reproduced and covered by a scenario.",
      "required_fix": "Applied: MUST-start wording, empty-manifest representation, and scenario added."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L156, #L190-L195, #L241-L245; proposal.md#L8",
      "evidence": "Unrecognized non-empty ROBOTRADER_EXECUTION_MODE fails closed, README.md and .env.example must document values/default/security meaning, and the proposal Risk row states the silent-PAPER residual risk.",
      "required_fix": "Applied: fail-closed, documentation, and risk statement added."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/proposal.md#L5, #L8",
      "evidence": "Outcome now reads 'without seed material (secret mount or environment)'; the Risk row states silent PAPER, unrecognized-mode fail-closed, and binary-unavailable refusal.",
      "required_fix": "Applied: Outcome and Risk aligned with the spec."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/proposal.md#L44",
      "evidence": "Modified Capabilities acknowledges build-packaging/spec.md#L131 and confirms the hierarchy.py vault-manifest/sign-transfer candidate list is unchanged.",
      "required_fix": "Applied: acknowledgment sentence added."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L35, #L37-L48",
      "evidence": "Derivation paths and slip44 are renamed target_*, unqualified names are forbidden, and both the qualification and absence scenarios exist; curve remains target-qualified by simulated, address_is_spendable, and the notice.",
      "required_fix": "Applied: target_* rename and scenarios added."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L156, #L158-L181",
      "evidence": "Precedence is explicit (secret file, then environment, then live failure or non-live deterministic seed); scenarios cover both-missing, whitespace secret, environment-only, secret precedence, and non-live deterministic.",
      "required_fix": "Applied: precedence defined and combinations tested."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/mark-vault-simulated/specs/vault-simulation/spec.md#L14-L18, #L183-L188",
      "evidence": "The duplicate deterministic-seed scenario was removed from Requirement 1; Requirement 6 asserts the distinct effective-mode PAPER plus DETERMINISTIC_DEVNET facts.",
      "required_fix": "Applied: scenarios consolidated and differentiated."
    }
  ],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04",
    "SPEC-R1-F05",
    "SPEC-R1-F06",
    "SPEC-R1-F07",
    "SPEC-R1-F08",
    "SPEC-R1-F09",
    "SPEC-R1-F10",
    "SPEC-R1-F11"
  ]
}
```

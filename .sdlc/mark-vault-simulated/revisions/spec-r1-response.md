stage: spec
round: 1
head_sha: a991e6df72e0264362f910bb9de7ec843a5e2d83
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: >-
      Requirement "No vault surface claims an implemented cryptographic guarantee" now
      covers `key_isolation_mode` explicitly: it MUST be removed or set to a `SIMULATED_*`
      value claiming neither HD derivation, zeroization, custody, nor exchange-withdrawal
      enforcement, and the values `RUST_ENCLAVE_HD_ZEROIZE` and
      `RUST_ENCLAVE_HMAC_TRADE_ONLY` MUST NOT appear. New scenario "Key isolation mode
      claims no custody guarantee" asserts the prefix and the absence of both legacy values.
  - id: SPEC-R1-F02
    action: fixed
    evidence: >-
      Requirement "The Rust vault identifies itself as simulated" now names the top-level
      `seed_source` field and enumerates exactly `SECRET_FILE`, `ENVIRONMENT`, and
      `DETERMINISTIC_DEVNET`. Scenarios assert `seed_source: SECRET_FILE`,
      `seed_source: ENVIRONMENT`, and, in the live-mode requirement,
      `seed_source: DETERMINISTIC_DEVNET`.
  - id: SPEC-R1-F03
    action: fixed
    evidence: >-
      Requirement "Receipt safety flags are derived and the whitelist is labelled simulated"
      now defines the exact shape: top-level manifest `whitelist_enforcement: "SIMULATED"`,
      per-wallet `withdrawal_whitelist_enforced` removed or `false` (never `true`), and every
      signed receipt `whitelist_enforcement: "SIMULATED"`. Scenarios "Manifest carries the
      top-level simulated whitelist label" and "Receipt carries the simulated whitelist label"
      cover both levels.
  - id: SPEC-R1-F04
    action: fixed
    evidence: >-
      The false-claim requirement and the "Repository-wide sweep covers code and process
      artifacts" scenario now name `backend/server.py`, `backend/core/hierarchy.py`,
      `engine-rs/crates/risk-gate/src/vault.rs`, `docs/architecture.md`,
      `sdlc/checklists/dev.md`, and `openspec/config.yaml`, plus the earlier documents and
      the frontend, and require an explicit allowlist of approved simulation statements.
      `proposal.md` Impact lists all of them; the PLAN stage derives the update tasks.
  - id: SPEC-R1-F05
    action: fixed
    evidence: >-
      Requirement "Python manifest retrieval fails closed without the Rust vault" now says
      the backend MUST remain importable and startable without the binary, that
      `HierarchicalFleetManager` construction MUST NOT raise, and that `vault_manifest` MUST
      be an empty mapping with no `wallets` key or absent. It reproduces the existing
      `test_missing_binary.py` endpoint contract. New scenario "Missing-binary startup
      contract remains green" asserts the 503/200 responses and the fail-closed manifest.
      The existing-tests scenario in Requirement 8 also names `test_missing_binary.py`.
  - id: SPEC-R1-F06
    action: fixed
    evidence: >-
      Requirement 6 now fails closed on any non-empty unrecognized
      `ROBOTRADER_EXECUTION_MODE` value instead of silently selecting `PAPER`, with scenario
      "Unrecognized mode fails closed". Requirement 8 adds a scenario requiring `README.md`
      and `.env.example` to document the four values, the `PAPER` default, and the security
      meaning. The proposal Risk row states the silent-`PAPER` residual risk.
  - id: SPEC-R1-F07
    action: fixed
    evidence: >-
      The Review Card Outcome now says "without seed material (secret mount or environment)".
      The Risk row now states the silent-`PAPER` residual risk, the fail-closed unrecognized
      value, and that an unavailable binary refuses vault operations instead of claiming a
      seed refusal.
  - id: SPEC-R1-F08
    action: fixed
    evidence: >-
      The Modified Capabilities section now acknowledges the `build-packaging` requirement:
      the separate vault-manifest/sign-transfer candidate list in
      `backend/core/hierarchy.py` remains unchanged and the existing requirement stays
      satisfied. No MODIFIED delta is needed because the list does not change.
  - id: SPEC-R1-F09
    action: fixed
    evidence: >-
      Requirement 2 now requires `master_derivation_path`, `leaf_derivation_path`, and
      `slip44_coin_type` to be renamed `target_master_derivation_path`,
      `target_leaf_derivation_path`, and `target_slip44_coin_type`, with the unqualified names
      absent. Scenarios "Curve and derivation metadata are target-qualified" and "Unqualified
      derivation field names are absent" assert both the qualification and the rename.
  - id: SPEC-R1-F10
    action: fixed
    evidence: >-
      Requirement 6 now states an explicit precedence (non-empty secret file, else non-empty
      environment seed, else live failure or non-live deterministic seed) and treats an empty
      or unreadable secret file as absent. Scenarios cover both-missing live failure, empty
      secret with a valid environment seed (`ENVIRONMENT`), environment-only live
      construction, secret-file precedence over the environment, and the non-live
      deterministic seed.
  - id: SPEC-R1-F11
    action: fixed
    evidence: >-
      The duplicate non-live devnet-seed scenario was removed from Requirement 1; Requirement 1
      now asserts secret and environment provenance. The remaining deterministic-seed scenario
      in Requirement 6 asserts a distinct fact: effective mode `PAPER` plus
      `seed_source: DETERMINISTIC_DEVNET`.

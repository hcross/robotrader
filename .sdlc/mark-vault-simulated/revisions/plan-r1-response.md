stage: plan
round: 1
head_sha: c3f658d896449835434e1a690b1b0944f85ccb9c
responses:
  - id: PLAN-R1-F01
    action: fixed
    evidence: >-
      Design D16/D17 now require `get_balance(address=None) -> Optional[float]`
      to return `None` when neither the argument nor `public_address` is configured
      and `None` on an RPC error; the endpoint returns `public_address`,
      `balance_sol` from that address or `None`, and `custody: "NONE"`. Tasks 5.1,
      5.3, 5.4, 9.4, and 9.5 implement and test the no-public-key case, and the
      testnet-verify curl check asserts no key-derived field and no fabricated
      balance.
  - id: PLAN-R1-F02
    action: fixed
    evidence: >-
      Design D19 and task 8.10 now define `scripts/vault-claim-allowlist.txt` as a
      patterns-only file (one ERE per line, no comments, no blank lines) with
      `scripts/vault-claim-allowlist.md` for justifications. The Verification adds
      `test -s`, a blank/comment-line rejection, and two self-tests: an allowlisted
      line is filtered and a disallowed `BIP-32 HD wallet` line survives.
  - id: PLAN-R1-F03
    action: fixed
    evidence: >-
      The frontend gate is now
      `git grep -nE '(^|[^_])leaf_derivation_path' -- frontend/src`, which does not
      match `target_leaf_derivation_path`. Task 7.3's static check also asserts the
      old `leaf.wallet_vault.leaf_derivation_path` access is absent.
  - id: PLAN-R1-F04
    action: fixed
    evidence: >-
      Design D8 now requires exact, case-sensitive equality with no trimming or
      case folding; `paper`, `PAPER `, and ` Paper` are in the fail-closed row.
      Tasks 2.3 and 3.3 add the matching `VaultModeInput` cases, and Verification
      runs a shell loop over those three values expecting exit 2.
  - id: PLAN-R1-F05
    action: fixed
    evidence: >-
      Design D15 and task 4.3 now define receipt validity before `signed`:
      `simulated is True`, `signature_is_chain_valid is False`,
      `whitelist_enforcement == "SIMULATED"`, `destination_whitelisted is True`,
      non-empty `signature_hex`, matching leaf/chain, exact destination, and
      amount within $0.01. Any mismatch is `rejected_vault_unavailable`; task 9.2
      adds the old-contract-receipt case.
  - id: PLAN-R1-F06
    action: fixed
    evidence: >-
      Design D16 and task 5.2 remove the `if solana.keypair:` guard and keep an
      explicit simulated branch under the Solana pod-selection condition. Task 9.4
      drives `run_live_testnet_tick` through a fake Binance and mocked
      `SolanaWalletTool`, asserting the row is emitted with `tx_signature: None`,
      `is_simulated: True`, and no measured live PnL.
  - id: PLAN-R1-F07
    action: fixed
    evidence: >-
      Design D13 and task 9.6 now require importing `HierarchicalFleetManager`
      first and patching `_rust_binary_candidates` before any import that
      transitively imports `backend.core.state_store`, explicitly naming
      `backend.agents.orchestrator` and `backend.server`. The vault assertion is
      vault-specific and does not reuse the shared `assert_503` detail markers.
  - id: PLAN-R1-F08
    action: fixed
    evidence: >-
      Design D7 and task 2.2 replace `Option<String>` with
      `VaultModeInput`/`SeedInput` (`Unset | Value(String) | NonUnicode`). Tasks
      3.3 and 3.4 add non-Unicode mode and seed cases, so
      `NonUnicodeExecutionMode` and `InvalidEnvironmentSeedEncoding` are testable
      without mutating process-global environment variables.
  - id: PLAN-R1-F09
    action: fixed
    evidence: >-
      Task 8.4 now updates `docs/architecture.md` in three places: the diagram
      node, the execution-mode section (four values including `SIMULATED`), and
      section 5 (no exchange keys or signing keypairs in `engine-rs`, no Python key
      custody, no broadcast, read-only configured public address). The claim sweep
      adds `signing keypairs`, `hot trading sub-wallet`, and
      `Exchange trade API keys` to its token set.
  - id: PLAN-R1-F10
    action: fixed
    evidence: >-
      New task 8.11 corrects `docs/PERFORMANCE_AND_COST_AUDIT.md`: `live_testnet`
      is Binance Spot Testnet measured plus Solana Devnet simulated/excluded, with
      a dated note that the historical 162 Devnet self-transfers are not measured.
      The claim sweep adds `Devnet self-transfer` and the design migration table
      records the measured-population change.
  - id: PLAN-R1-F11
    action: fixed
    evidence: >-
      Task 8.2 now names the README Testnet/Devnet telemetry bullet and rewrites it
      to a read-only public-address balance, simulated Solana actions, and measured
      PnL only from CEX testnet. The claim sweep adds `real PnL tracking`.
  - id: PLAN-R1-F12
    action: fixed
    evidence: >-
      Task 9.5 adds a `/api/v1/testnet/verify` child-process test with
      `SOLANA_PRIVATE_KEY` set and no public key, asserting no key-derived public
      key, no private material, `custody: "NONE"`, and a `None`/absent balance. The
      Verification also adds a live curl assertion for the endpoint.
  - id: PLAN-R1-F13
    action: fixed
    evidence: >-
      Design D14/D15 and tasks 4.4/4.6 now pass `kill_switch_active` and
      `kill_switch_reason` from the server/store into `checkout_funds` and the
      signer; the active path returns `rejected_by_rust_enclave` before any binary
      or mutation. Task 9.3 tests both the no-binary and valid-binary active cases.
  - id: PLAN-R1-F14
    action: fixed
    evidence: >-
      The Verification now greps `ROBOTRADER_EXECUTION_MODE` in `README.md` and
      `.env.example` and runs a Python assertion for the four values, the `PAPER`
      default, and the empty/unknown warning; tasks 8.2 and 8.9 own the content.
  - id: PLAN-R1-F15
    action: fixed
    evidence: >-
      Task 9.1 now requires explicit Python assertions for
      `receipt["simulated"] is True`, `receipt["signature_is_chain_valid"] is
      False`, and `receipt["whitelist_enforcement"] == "SIMULATED"` on the
      checkout receipt.
  - id: PLAN-R1-F16
    action: fixed
    evidence: >-
      The former task 9.2 is split into 9.2 (loader/signer matrices), 9.3
      (checkout/no-mutation and kill switch), and 9.4 (Solana tool, telemetry,
      population, and the simulated tick). Each is a single-session, separately
      reviewable evidence unit.
  - id: PLAN-R1-F17
    action: fixed
    evidence: >-
      Task 9.1 now removes only the `zeroize_on_drop` assertion and keeps
      `assertFalse(manifest["python_private_key_access"])`, matching the manifest
      field retained in design D2.
  - id: PLAN-R1-F18
    action: fixed
    evidence: >-
      Task 8.4 now updates the `docs/architecture.md` execution-mode text from
      three modes to the four `ROBOTRADER_EXECUTION_MODE` values including
      `SIMULATED`, alongside the diagram and section 5 updates.
  - id: PLAN-R1-F19
    action: fixed
    evidence: >-
      Design D7/D9 and task 3.1 add the `robotrader-node --vault-secret-file
      <path>` override for hermetic tests. The Verification now passes explicit
      non-existent or temporary secret paths for the unset, LIVE-no-seed,
      LIVE-environment, and secret-precedence checks, so a host-mounted
      `/run/secrets/robotrader_master_seed` cannot change the result.
  - id: PLAN-R1-F20
    action: fixed
    evidence: >-
      Design D8 now specifies the exact `Display` text for
      `EmptyExecutionMode`, `InvalidExecutionMode`, `NonUnicodeExecutionMode`,
      `InvalidEnvironmentSeedEncoding`, and `MissingLiveSeed`; each names
      `ROBOTRADER_EXECUTION_MODE` and the accepted values where applicable. Tasks
      2.2, 8.2, and 8.9 require the same wording, and the Verification checks the
      empty-mode stderr for the variable name and the accepted value list.
  - id: PLAN-R1-F21
    action: fixed
    evidence: >-
      Design D19 and tasks 8.1/8.3/8.6 now require descriptive language for
      removed names ("the former enclave type", "the removed Solana private-key
      variable") so the no-legacy `RustVaultEnclave`/`VaultEnclaveManifest` and
      `SOLANA_PRIVATE_KEY` greps stay empty without allowlist entries. The
      Verification notes this convention beside the no-legacy gates.
  - id: PLAN-R1-F22
    action: fixed
    evidence: >-
      Task 4.2 now removes both unused `hashlib` and `hmac` imports with the
      fallback manifest/signer, and the Verification adds a static grep for
      `^import (hashlib|hmac)` / `^from (hashlib|hmac)` in
      `backend/core/hierarchy.py` expecting no output.

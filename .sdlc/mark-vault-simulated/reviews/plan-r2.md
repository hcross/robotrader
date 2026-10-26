# PLAN Review — mark-vault-simulated (round 2, closure)

- **Change**: `mark-vault-simulated` (Lane L, partial issue #2)
- **Stage**: `plan`
- **Round**: 2
- **Reviewed SHA**: `45f6b1e34061f28d0ce4a6742b530126401f0fd6`
- **Artifact**: `openspec/changes/mark-vault-simulated/design.md` and `tasks.md` at the reviewed SHA; approved SPEC unchanged since `65ae70510af46b7a29f2ee6abb097a875ea58777`
- **Reviewer**: `sdlc-plan-reviewer` (cold start)

## Human Summary (≤ 150 words)

Round-2 closure passes. All 22 R1 findings are closed at `45f6b1e`. The two blockers are resolved: `get_balance` returns `None` and the endpoint exposes `custody: "NONE"` with no fabricated balance; the claim allowlist is patterns-only with a sibling justification file and a non-vacuous self-test. The twelve majors are closed: exact case-sensitive mode parsing with out-of-spec tests, full receipt validation before mutation, a reachable and mocked simulated Solana branch excluded from measured PnL, early candidate patching in the missing-binary test, injectable `VaultModeInput`/`SeedInput`, corrected architecture/audit/README claims, endpoint, kill-switch, and execution-mode verification, plus the three minors and the import nit. The approved SPEC is unchanged; 59 tasks preserve dependency order, cover all 8 requirements, and the root-runnable Verification is executable. Residual risks are explicit and acceptable. No allowed new finding.

## R1 Finding Closure

| ID | Severity | R1 | R2 | Evidence at `45f6b1e` |
|---|---|---|---|---|
| PLAN-R1-F01 | blocker | open | closed | D16/D17; tasks 5.1, 5.3, 5.4, 9.4, 9.5, 9.7; Verification `testnet/verify` curl asserts `custody: "NONE"` and `balance_sol: None` without a public address. |
| PLAN-R1-F02 | blocker | open | closed | D19 and task 8.10 define a patterns-only `vault-claim-allowlist.txt` with a sibling `.md`; Verification lines 164–167 add `test -s`, blank/comment rejection, and both non-vacuity self-tests. Reproduced both `grep -vEf` outcomes. |
| PLAN-R1-F03 | major | open | closed | Verification line 151 uses `(^|[^_])leaf_derivation_path`; probe returns exit 1 for `target_leaf_derivation_path` and exit 0 for the old access. |
| PLAN-R1-F04 | major | open | closed | D8 exact case-sensitive equality; tasks 2.3/3.3; Verification loop over `paper`, `PAPER `, ` Paper` expects exit 2. |
| PLAN-R1-F05 | major | open | closed | D15 defines every receipt field, leaf/chain, destination, and amount check before `signed`; task 4.3 implements it; task 9.2 adds the old-contract-receipt case. |
| PLAN-R1-F06 | major | open | closed | D16 and task 5.2 remove the `keypair` guard and use pod selection; task 9.4 drives the tick with a fake Binance and mocked tool and asserts `tx_signature: None`, `is_simulated: True`, and measured-PnL exclusion. |
| PLAN-R1-F07 | major | open | closed | D13 and task 9.6 require importing `HierarchicalFleetManager` first and patching before any transitive `state_store` import; verified `hierarchy` dependencies do not import `state_store`. |
| PLAN-R1-F08 | major | open | closed | D7 and task 2.2 introduce `VaultModeInput`/`SeedInput` (`Unset | Value | NonUnicode`); tasks 3.3/3.4 test non-Unicode mode and seed without mutating process env. |
| PLAN-R1-F09 | major | open | closed | Task 8.4 updates the diagram, execution-mode text, and §5 security invariants; D19 sweep adds `signing keypairs`, `hot trading sub-wallet`, `Exchange trade API keys`. |
| PLAN-R1-F10 | major | open | closed | Task 8.11 corrects the `live_testnet` description and `162` self-transfer count; D19 adds `Devnet self-transfer`; migration table records the change. |
| PLAN-R1-F11 | major | open | closed | Task 8.2 names the README telemetry bullet; D19 adds `real PnL tracking`. |
| PLAN-R1-F12 | major | open | closed | Task 9.5 adds the isolated endpoint test; Verification adds a live `curl` assertion for `/api/v1/testnet/verify`. |
| PLAN-R1-F13 | major | open | closed | D14/D15 and tasks 4.4/4.6 pass `kill_switch_active`/`reason` into checkout and the signer; task 9.3 tests active kill switch with and without a binary. Verified the store exposes both fields. |
| PLAN-R1-F14 | major | open | closed | Verification greps `ROBOTRADER_EXECUTION_MODE` in `README.md`/`.env.example` and asserts the four values, `PAPER` default, and empty/unknown wording; tasks 8.2/8.9 own the content. |
| PLAN-R1-F15 | minor | open | closed | Task 9.1 requires explicit Python assertions for `simulated`, `signature_is_chain_valid`, and `whitelist_enforcement`. |
| PLAN-R1-F16 | minor | open | closed | Former 9.2 split into 9.2 (loader/signer), 9.3 (checkout/kill switch), 9.4 (Solana/telemetry/population). |
| PLAN-R1-F17 | minor | open | closed | Task 9.1 removes only the `zeroize_on_drop` assertion and keeps `assertFalse(manifest["python_private_key_access"])`. |
| PLAN-R1-F18 | minor | open | closed | Task 8.4 updates the architecture execution-mode text to four values including `SIMULATED`. |
| PLAN-R1-F19 | minor | open | closed | D7/D9 and task 3.1 add `--vault-secret-file`; Verification passes explicit non-existent/temporary paths for all seed cases. |
| PLAN-R1-F20 | minor | open | closed | D8 specifies the exact `Display` text for all five `VaultInitError` variants; Verification greps the empty-mode stderr for the variable and accepted values. |
| PLAN-R1-F21 | minor | open | closed | D19 and tasks 8.1/8.3/8.6 require descriptive language for removed names; no-legacy gates remain satisfiable. |
| PLAN-R1-F22 | nit | open | closed | Task 4.2 removes both `hashlib` and `hmac`; Verification line 150 greps their imports and expects none. |

No finding is open or regressed. No new finding is raised.

## Checklist Walk

| Checklist item | Status | Evidence |
|---|---|---|
| 1.1 Every design decision traces to a requirement/invariant | PASS | Traceability table (`design.md#L303-L314`); per-task `covers:` annotations. |
| 1.2 Every requirement addressed by a task | PASS | All 8 requirements map to tasks; F09–F14 gaps now have tasks 8.2, 8.4, 8.11, 9.3–9.5 and Verification commands. |
| 1.3 No unapproved behaviour implemented | PASS | D8 exact equality matches the SPEC; D16 `None` balance matches the SPEC's configured-address-only rule. |
| 1.4 Spec gap escalated, not patched | PASS | No spec gap; `LIVE` + `SIMULATED` is fixed by the approved SPEC. |
| 2.1 Alternatives named per decision | PASS | D1–D22 table. |
| 2.2 Rejections have technical reasons | PASS | Each rejection cites churn, defect, or scope. |
| 2.3 Reversible vs one-way doors separated | PASS | Contract migration/rollback; no data migration. |
| 2.4 Simplest design considered | PASS | D1–D3 reject aliases; D21 adds no dependency. |
| 2.5 New dependencies justified | PASS | D21: none; `solders` removed from the signing path. |
| 3.1 `PolicyEnvelope` parity addressed | PASS | D22 untouched; 9.9 runs parity/contract suites. |
| 3.2 IPC/API/DB/CLI changes versioned or compatible | PASS | `vault_version`; intentional breaking checkout contract with migration table (D2/D15). |
| 3.3 Schema evolution has migration/rollback | PASS | Manifest/receipt migration and rollback (`design.md#L336-L379`). |
| 3.4 Serialization boundaries explicit | PASS | JSON stdout/API; Redis unaffected; `vault_version` carried. |
| 3.5 No cross-chain/venue leakage | PASS | Leaf descriptors remain chain-scoped; no leaf-isolation change. |
| 4.1 No LLM/blocking I/O/allocation/logging in hot path | PASS | Vault is outside `HardRiskGate::validate` and `StrategyPod::on_market_event`; D22. |
| 4.2 50 µs budget preserved | PASS | D22; no hot-path change; 9.6/9.9 non-regression. |
| 4.3 New loops/data structures bounded | PASS | 26-item constant manifest/descriptor loops; no new hot loop. |
| 4.4 Failure modes defined | PASS | Loader matrix (D12/D13) and signer matrix (D15) cover absent, timeout, non-zero, unparsable, old contract, invalid receipt, kill switch. |
| 5.1 Capital protection not weakened | PASS | Kill switch wired from the store (D14/D15, 4.4/4.6, 9.3); no fabricated balance (D16/D17). |
| 5.2 Vault/key material inside enclave; zeroize/whitelist preserved | PASS | D4–D6 derive flags; Python fallback removed; docs corrected. |
| 5.3 Trust-boundary inputs validated | PASS | D15 validates every receipt field before `signed`; D7/D8 test non-Unicode inputs. |
| 5.4 No secrets in logs/fixtures/evidence | PASS | No key material introduced; tests use fake binaries, temp paths, and throwaway seeds. |
| 5.5 Fail-closed on money/risk paths | PASS | D8/D9 construction, D14 manifest 503, D15 signer/checkout rejection before mutation. |
| 6.1 Each scenario has a named test/verification | PASS | Tasks 9.1–9.9 plus Verification for manifest, modes, seed precedence, receipt, endpoint, checkout, and docs. |
| 6.2 Unit/integration/e2e proportional to risk | PASS | 9.2–9.4 split by risk surface; endpoint and process-isolation tests added. |
| 6.3 Determinism backtest == paper == live | PASS | Vault/telemetry only; no strategy branch; D22. |
| 6.4 Negative/boundary tests planned | PASS | Non-Unicode, empty/whitespace/out-of-spec modes, stale receipt, rejected destination, missing binary, kill switch. |
| 6.5 Performance tests where a budget exists | PASS | No vault change on the 50 µs path; existing non-regression suffices. |
| 6.6 Test data contains no real keys | PASS | Fake binaries, temp paths, `test-only-not-a-secret` seeds. |
| 7.1 Deployment order explicit | PASS | `design.md#L358-L366`; one PR, binary rebuilt before backend. |
| 7.2 Rollback concrete | PASS | `design.md#L370-L379`; rebuild binary and image; old/new contract pairing explained. |
| 7.3 Observability planned | PASS | 503 detail, signer statuses, `execution_mode`/`seed_source`, UI badge (`design.md#L381-L387`). |
| 7.4 Cost impact assessed | PASS | Zero new LLM/RPC/Redis loops. |
| 8.1 Tasks are checkboxes under numbered headings | PASS | 59 tasks in 9 groups. |
| 8.2 Each task fits one session and is verifiable | PASS | 9.2–9.4 split; each names evidence. |
| 8.3 Dependency order correct | PASS | Contract → vault → CLI → Python → Solana → API → UI → docs → tests; no cycle. |
| 8.4 `## Verification` exact commands/evidence | PASS | Root-runnable commands; probes confirm the F02/F03 forms work. |
| 8.5 No task hides a spec change | PASS | No spec change; all tasks trace to the approved requirements. |

## Residual Risks (explicit and acceptable)

- **LIVE + simulated vault**: D10 and the worst-failure risk bullet state that `LIVE` gates seed selection only and every surface stays `SIMULATED`; the approved SPEC requires `LIVE` construction with a seed.
- **Broad prefix whitelist retained as simulated**: D6/D19 and the risk bullet label it `SIMULATED`, keep addresses non-spendable, and leave exact allowlists to issue #2; the SPEC places them out of scope.
- **Distinct vault binary path**: D13 keeps `_rust_binary_candidates` unchanged and validates a stricter fail-closed contract; build-packaging #9 is preserved.

## Checks Run

- `openspec validate mark-vault-simulated --strict` → `Change 'mark-vault-simulated' is valid` (exit 0).
- `scripts/sdlc/sdlc.sh check mark-vault-simulated` → `check: PASS`; `spec-lint` PASS; 59 open tasks (expected at PLAN); `spec-r1` CHANGES_REQUESTED, `spec-r2` APPROVE, `plan-r1` CHANGES_REQUESTED.
- `git rev-parse HEAD` → `45f6b1e34061f28d0ce4a6742b530126401f0fd6`; `design.md`/`tasks.md` match HEAD.
- `git diff --stat 65ae705..HEAD -- proposal.md specs .openspec.yaml` → empty; the approved SPEC is unchanged.
- Shell probes:
  - `printf 'target_leaf_derivation_path\n' | grep -nE '(^|[^_])leaf_derivation_path'` → no match (exit 1); the old `leaf_derivation_path` access matches (exit 0).
  - Pattern-only allowlist: an allowlisted `Secp256k1EcdsaBip44` line is filtered; `BIP-32 HD wallet` survives.
  - Repository tokens for `SOLANA_PRIVATE_KEY` and legacy vault names occur only in files owned by tasks 5.1, 8.1–8.9, and 6.2.
  - `run_live_testnet_tick` imports `SolanaWalletTool` locally, so task 9.4's mock is implementable.
  - Store exposes `kill_switch_active`/`kill_switch_reason`; `HierarchicalFleetManager._rust_binary_candidates` is a static method patchable before `state_store` import; hierarchy dependencies do not import `state_store`.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "mark-vault-simulated",
  "stage": "plan",
  "round": 2,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "45f6b1e34061f28d0ce4a6742b530126401f0fd6",
  "verdict": "APPROVE",
  "summary": "Round-2 closure passes: all 22 R1 findings are closed, the approved SPEC is unchanged, 59 tasks cover all 8 requirements in dependency order, and the Verification is root-runnable. Residual risks are explicit and acceptable. No allowed new finding.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D16/D17; tasks.md 5.1, 5.3, 5.4, 9.4, 9.5, 9.7",
      "evidence": "get_balance is Optional[float] and returns None without a configured address or on RPC error; the endpoint returns public_address, balance_sol None, and custody NONE; tests cover the no-public-key case.",
      "required_fix": "Return None or omit the balance when no configured address exists; update server, state store, and tests; add a no-public-key test with SOLANA_PRIVATE_KEY set."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D19; tasks.md 8.10; tasks.md Verification lines 164-167",
      "evidence": "The allowlist is patterns-only (one ERE per line, no comments, no blanks) with justifications in a sibling .md; the gate self-test filters an allowlisted line and keeps a disallowed line; both behaviours reproduced.",
      "required_fix": "Define a grep -f-compatible patterns-only allowlist with a sibling justification file, reject blank/comment lines, and add a non-vacuity self-test."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md Verification line 151",
      "evidence": "The frontend gate uses (^|[^_])leaf_derivation_path; the probe returns exit 1 for target_leaf_derivation_path and exit 0 for the old field access.",
      "required_fix": "Use a precise pattern that cannot match target_leaf_derivation_path, or assert the serialized JSON key with Python."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D8; tasks.md 2.3, 3.3; tasks.md Verification line 117",
      "evidence": "Mode parsing is exact and case-sensitive with no trim or case folding; paper, 'PAPER ', and ' Paper' are in the fail-closed row; the Verification loop expects exit 2 for all three.",
      "required_fix": "Compare the raw value exactly or escalate a spec change; add tests for paper, 'PAPER ', and ' Paper' with fail-closed results."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D15; tasks.md 4.3, 9.2",
      "evidence": "A receipt is valid only with simulated true, signature_is_chain_valid false, whitelist_enforcement SIMULATED, destination_whitelisted true, non-empty signature_hex, matching leaf/chain, exact destination, and amount within $0.01; mismatches are rejected before mutation; the old-contract receipt case is tested.",
      "required_fix": "Validate all simulation flags and request fields before returning signed; reject mismatches as rejected_vault_unavailable; add an old-contract-receipt test."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D16; tasks.md 5.2, 9.4",
      "evidence": "The keypair guard is removed in favour of pod selection; the simulated row carries tx_signature None and is_simulated true; the tick is exercised with a fake Binance and mocked SolanaWalletTool; measured PnL and live population skip simulated rows.",
      "required_fix": "Replace the keypair guard with an explicit condition and test the simulated row, or reconcile the design claim with the SPEC scenario."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D13; tasks.md 9.6",
      "evidence": "The test imports HierarchicalFleetManager first and patches _rust_binary_candidates before any import that transitively imports backend.core.state_store, naming orchestrator and server; the vault 503 assertion is vault-specific. Hierarchy dependencies do not import state_store.",
      "required_fix": "Patch the candidate list before importing state_store/server or inject it; use a vault-specific 503 assertion."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D7; tasks.md 2.2, 3.3, 3.4",
      "evidence": "VaultBootstrap carries VaultModeInput and SeedInput (Unset | Value | NonUnicode), making non-Unicode mode and seed paths testable without mutating process-global environment variables.",
      "required_fix": "Represent mode and seed inputs so non-Unicode values are testable and add fail-closed tests for them."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 8.4; design.md D19",
      "evidence": "Task 8.4 updates the diagram, execution-mode text, and section 5 security invariants; the sweep token set adds signing keypairs, hot trading sub-wallet, and Exchange trade API keys.",
      "required_fix": "Update the security invariants to the simulated reality and extend the task and sweep tokens to cover them."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 8.11; design.md D19 and migration table",
      "evidence": "The audit is corrected to Binance Spot Testnet measured plus Solana Devnet simulated/excluded with a dated note on the 162 historical self-transfers; the sweep adds Devnet self-transfer.",
      "required_fix": "Revise the live_testnet description and numbers or add a dated simulation note, and add a sweep check for the measured-Solana claim."
    },
    {
      "id": "PLAN-R1-F11",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 8.2; design.md D19",
      "evidence": "Task 8.2 names the README Testnet/Devnet telemetry bullet and rewrites it to read-only public-address balance and simulated actions; the sweep adds real PnL tracking.",
      "required_fix": "Rewrite the telemetry bullet and add a claim-sweep check for real PnL."
    },
    {
      "id": "PLAN-R1-F12",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 9.5; tasks.md Verification lines 184-193",
      "evidence": "An isolated child-process test calls /api/v1/testnet/verify with SOLANA_PRIVATE_KEY set and no public key, asserting no key-derived material, custody NONE, and no fabricated balance; the live curl assertion covers the same.",
      "required_fix": "Add an endpoint test or curl check with SOLANA_PRIVATE_KEY set and no public key, asserting no key-derived public key, custody NONE, and no fabricated balance."
    },
    {
      "id": "PLAN-R1-F13",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D14/D15; tasks.md 4.4, 4.6, 9.3",
      "evidence": "checkout_funds receives kill_switch_active and kill_switch_reason from the store and rejects before mutation; task 9.3 tests an active kill switch with and without a binary; the store exposes both fields.",
      "required_fix": "Pass the store's kill-switch state into checkout and the signer, reject before mutation, and test active cases with and without a binary."
    },
    {
      "id": "PLAN-R1-F14",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 8.2, 8.9, Verification lines 153-163",
      "evidence": "The Verification greps ROBOTRADER_EXECUTION_MODE in README.md and .env.example and asserts the four values, the PAPER default, and the empty/unknown warning.",
      "required_fix": "Add a git grep/Python assertion over README.md and .env.example for the variable, values, default, and fail-closed warning."
    },
    {
      "id": "PLAN-R1-F15",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 9.1",
      "evidence": "Task 9.1 now requires explicit Python assertions for simulated true, signature_is_chain_valid false, and whitelist_enforcement SIMULATED on the checkout receipt.",
      "required_fix": "Add explicit Python assertions for the three receipt fields."
    },
    {
      "id": "PLAN-R1-F16",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 9.2, 9.3, 9.4",
      "evidence": "The former bundled task is split into loader/signer matrices, checkout/no-mutation and kill switch, and Solana/telemetry/population, each a single-session evidence unit.",
      "required_fix": "Split the oversized task into separate single-session tasks."
    },
    {
      "id": "PLAN-R1-F17",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 9.1; design.md D2",
      "evidence": "Task 9.1 removes only the zeroize_on_drop assertion and keeps assertFalse(manifest['python_private_key_access']), matching the retained manifest field.",
      "required_fix": "Remove only the zeroize_on_drop assertion and keep the python_private_key_access is False assertion."
    },
    {
      "id": "PLAN-R1-F18",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 8.4",
      "evidence": "Task 8.4 updates the docs/architecture.md execution-mode text from three modes to the four ROBOTRADER_EXECUTION_MODE values including SIMULATED.",
      "required_fix": "Update the execution-mode text to the four values and the simulated vault."
    },
    {
      "id": "PLAN-R1-F19",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D7/D9; tasks.md 3.1; Verification lines 104-129",
      "evidence": "The node CLI accepts --vault-secret-file for hermetic tests; every seed-precedence check passes an explicit non-existent or temporary path, so a host-mounted secret cannot change the result.",
      "required_fix": "Allow an explicit secret-file path for tests or run the checks in an isolated root and document the isolation."
    },
    {
      "id": "PLAN-R1-F20",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D8; tasks.md 8.2, 8.9; Verification line 116",
      "evidence": "D8 specifies exact Display text for EmptyExecutionMode, InvalidExecutionMode, NonUnicodeExecutionMode, InvalidEnvironmentSeedEncoding, and MissingLiveSeed; the Verification greps the empty-mode stderr for the variable and accepted values.",
      "required_fix": "Specify the Display text for each construction error and require the docs to state the blank-line failure."
    },
    {
      "id": "PLAN-R1-F21",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md D19; tasks.md 8.1, 8.3, 8.6",
      "evidence": "The plan requires descriptive language for removed names so the no-legacy RustVaultEnclave/VaultEnclaveManifest and SOLANA_PRIVATE_KEY greps stay empty; task 8.1/8.3/8.6 state the convention.",
      "required_fix": "State the descriptive-language convention for removed names or add justified allowlist entries, aligned with the gates."
    },
    {
      "id": "PLAN-R1-F22",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md 4.2; tasks.md Verification line 150",
      "evidence": "Task 4.2 removes both unused hashlib and hmac imports with the fallback; the Verification greps their import forms and expects no output.",
      "required_fix": "Remove both unused imports and add the static check to the non-regression suite."
    }
  ],
  "closed": [
    "PLAN-R1-F01",
    "PLAN-R1-F02",
    "PLAN-R1-F03",
    "PLAN-R1-F04",
    "PLAN-R1-F05",
    "PLAN-R1-F06",
    "PLAN-R1-F07",
    "PLAN-R1-F08",
    "PLAN-R1-F09",
    "PLAN-R1-F10",
    "PLAN-R1-F11",
    "PLAN-R1-F12",
    "PLAN-R1-F13",
    "PLAN-R1-F14",
    "PLAN-R1-F15",
    "PLAN-R1-F16",
    "PLAN-R1-F17",
    "PLAN-R1-F18",
    "PLAN-R1-F19",
    "PLAN-R1-F20",
    "PLAN-R1-F21",
    "PLAN-R1-F22"
  ]
}
```

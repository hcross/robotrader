# DEV Review — Round 1

## Summary

APPROVE. The change implements the approved honest-simulation slice at
`76b6d09`: the Rust vault is `SimulatedVault`, every manifest, receipt, API, and
UI surface is `SIMULATED`, Python fabricates no manifest or signature and holds
no Solana key, and execution-mode/seed selection fails closed. I independently
ran the shipped image suite (191 tests, `OK (skipped=9)`), `cargo test` (46
passed), the frontend build and provenance check, OpenSpec and SDLC checks, the
full CLI mode/receipt matrix, every claim/legacy/custody gate, and an API smoke
through the built image; all required checks pass. The five frontend lint errors
are pre-existing on unchanged lines. One minor follow-up remains: the PR body
still names the pre-fix head and stale diff counts. No blocker or major remains,
and the reviewed SHA equals the PR head.

## Findings

### DEV-R1-F01 — [minor] PR body names a stale head SHA and stale diff counts
- Location: PR #19 body, `Base`/`Head` line and `## Diff` section
- Evidence: `gh pr view 19 --json headRefOid` returns
  `76b6d098431f74094dc68705b4cdbb505b9054cb`, while the body says
  `Head: 2abbd0c`. `git diff --stat master...76b6d09` reports
  `47 files changed, 4590 insertions(+), 561 deletions(-)`, while the body says
  `+4589 / -560`. The final follow-up commit (`76b6d09`) added one line and
  superseded that body text.
- Required fix: Update the PR body Head value to
  `76b6d098431f74094dc68705b4cdbb505b9054cb` and the diff counts to
  `4590/561`, or remove the hardcoded counts.
- Status: open
- Origin: initial

## Checks run

### Build and shipped test suite
- `docker build -f Dockerfile.backend -t robotrader-backend:vault-review .` → exit 0
- `docker run --rm -e PYTHONPATH=. robotrader-backend:vault-review python -m unittest discover -s backend/tests -v` → `Ran 191 tests`, `OK (skipped=9)`, exit 0

### Rust
- `cd engine-rs && cargo test` → all workspace suites green: 2 + 1 + 14 + 1 + 10 + 18 = 46 passed, 0 failed, exit 0
- `git diff master...HEAD -- engine-rs/crates/risk-gate/src/lib.rs` → only the re-export, the rejection message, and the `mod tests` block change; `HardRiskGate::validate`, Kelly sizing, token safety, and inference refill are untouched
- Manifest contract: `SimulatedVaultManifest` carries `vault_version`, `vault_mode: "SIMULATED"`, `execution_mode`, `simulated: true`, non-empty `simulation_notice`, `seed_source`, `python_private_key_access: false`, `whitelist_enforcement: "SIMULATED"`, `simulated_whitelist_entry_count`, `canonical_bridge_contracts_count`, `wallets`
- Descriptor contract: `simulated: true`, `address_is_spendable: false`, `target_slip44_coin_type`, `target_master_derivation_path`, `target_leaf_derivation_path`; `key_isolation_mode` and `withdrawal_whitelist_enforced` absent
- Receipt contract: `simulated: true`, `signature_is_chain_valid: false`, `whitelist_enforcement: "SIMULATED"`; `destination_whitelisted` assigned from the single predicate evaluation; `key_zeroized_after_sign` read from the buffer after `zeroize_now()`; rejection returns `RiskRejection::VaultSigningRejected` before any receipt
- Serialized-contract test in `engine-rs/crates/node/tests/simulated_vault_contract.rs` asserts the legacy keys are absent and the simulation flags present

### Frontend
- `cd frontend && npm run build` → Rolldown build succeeded, `dist/` written, exit 0
- `node frontend/scripts/check-provenance.mjs` → `provenance wiring OK`, exit 0
- `cd frontend && npm run lint` → exit 1 with exactly five errors, all on unchanged lines: `App.jsx:113`, `Dashboard.jsx:38`, `MasterOverview.jsx:65/66/79`. Diff hunks for `Dashboard.jsx` start at line 176, and `App.jsx`/`MasterOverview.jsx` are not in the diff. No new lint error.
- `LeafAgentView.jsx` always renders the `SIMULATED` badge, reads `target_leaf_derivation_path`, and renders `address_is_spendable=false`; `Dashboard.jsx` removes the signed-transaction and gas-accounting claims and suppresses the Solscan link for simulated rows

### SDLC and API
- `openspec validate mark-vault-simulated --strict` → `Change 'mark-vault-simulated' is valid`
- `scripts/sdlc/sdlc.sh check mark-vault-simulated` → `check: PASS`; `spec-lint` PASS (59/59 tasks done), `verdict-lint` PASS
- `gh pr checks 19` → `rust`, `sdlc`, `python`, `helm`, `frontend` all `SUCCESS`
- `gh pr view 19 --json isDraft,headRefOid,mergeable` → `headRefOid = 76b6d098431f74094dc68705b4cdbb505b9054cb`, `isDraft = true`, `mergeable = MERGEABLE`

### CLI matrix (built binary)
- Default (unset mode/seed) → `simulated manifest OK`: `SIMULATED`, `PAPER`, `DETERMINISTIC_DEVNET`, 26 wallets, all `address_is_spendable=false`, target paths present and legacy paths absent
- `ROBOTRADER_EXECUTION_MODE=BOGUS` → empty stdout, exit 2, stderr names the variable and accepted values
- `ROBOTRADER_EXECUTION_MODE=` (empty) → empty stdout, exit 2, stderr names the variable and accepted values
- `paper`, `PAPER `, ` Paper` → each exit 2 (`out-of-spec modes fail closed`)
- `LIVE` without any seed → empty stdout, exit 2, `MissingLiveSeed`
- `LIVE` + environment seed → `live-mode simulated manifest OK`: still `SIMULATED`, `execution_mode=LIVE`, `seed_source=ENVIRONMENT`
- Secret file + environment seed → `secret-file precedence OK` (`seed_source=SECRET_FILE`), hermetic via `--vault-secret-file`
- Accepted destination → `simulated receipt OK`: `simulated=true`, `signature_is_chain_valid=false`, `whitelist_enforcement=SIMULATED`, `destination_whitelisted=true`, `key_zeroized_after_sign=true`
- Rejected destination → exit 1, `rejected_by_rust_enclave` with no `signature_hex` and no `destination_whitelisted`

### Claim, legacy, custody, and allowlist gates
- `git grep -n 'RustVaultEnclave\|VaultEnclaveManifest\|RUST_ENCLAVE_HD_ZEROIZE\|RUST_ENCLAVE_HMAC_TRADE_ONLY' -- ':!openspec/changes' ':!.sdlc'` → no output (exit 1)
- Legacy manifest-field grep over the Rust/Python/frontend contract files → no output (exit 1)
- `SOLANA_PRIVATE_KEY` grep outside tests → no output (exit 1)
- `transfer_sol|simulate_only=False|sendTransaction` over `backend/core`, `backend/tools`, `backend/server.py` → no output (exit 1)
- Old vault test-name grep, `hashlib`/`hmac` import grep, and unqualified frontend `leaf_derivation_path` grep → no output (exit 1)
- Full tasks claim sweep (scheme/legacy tokens + default qualifiers + `grep -vEf scripts/vault-claim-allowlist.txt`) → no output (exit 1)
- Allowlist self-test: non-empty, no blank/comment lines, an allowlisted line is filtered, `BIP-32 HD wallet` survives
- No secrets or long key material found in the diff; no new dependency (`Cargo.lock`, `package.json`, `pyproject.toml` unchanged)

### API smoke through the built image
- Started `robotrader-backend:vault-review` with `REDIS_URL=` and `PYTHONPATH=.`
- `GET /api/v1/vault/manifest` → HTTP 200, `vault_mode=SIMULATED`, `execution_mode=PAPER`, `seed_source=DETERMINISTIC_DEVNET`, 26 wallets, every `address_is_spendable=false`, `whitelist_enforcement=SIMULATED`
- `GET /api/v1/testnet/verify` → HTTP 200, `custody=NONE`, `balance_sol=null`, `public_address=null`, no `public_key`, no private material
- `POST /api/v1/treasury/checkout` → HTTP 200, `status=completed`, `simulated=true`, nested `simulated_vault_receipt` with the simulation flags; no `tx_hash`, no `enclave_receipt`, no seed/private material
- The missing-binary 503 path is covered by `backend/tests/test_missing_binary.py`, which passes in the shipped suite; the compose smoke itself was not run because the gitignored `.env` is absent in this worktree and the reviewer may not create files outside the verdict

### Scope and non-regression
- Approved artifacts unchanged: `proposal.md` and `specs/vault-simulation/spec.md` are identical to `65ae705`; `design.md` is identical to `45f6b1e`; `tasks.md` differs only by checkbox state (59/59 done)
- No change to `PolicyEnvelope`, Redis schema, strategy pods, `HardRiskGate`, Kelly sizing, the kill switch, CostGuard, or provenance; the full suite covers #5/#7/#8a/#9/#10
- Python holds no key custody: no seed read, no `Keypair`, no `transfer_sol`, no `sendTransaction`; `get_balance` returns `None` without a configured address or on RPC error; the live Solana branch records `tx_signature: null`, `source: SIMULATED`, `is_simulated: true`, and does not increment tx/gas counters
- `measured_realized_pnl_usd` and the `live_testnet` population exclude `is_simulated` rows; the paper population may consume their simulated PnL
- The real kill-switch state is passed from `server.py` into `checkout_funds` and the signer; a rejection mutates no capital, allocation, history, or dry powder

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "mark-vault-simulated",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "76b6d098431f74094dc68705b4cdbb505b9054cb",
  "verdict": "APPROVE",
  "summary": "The approved simulated-vault slice is implemented and independently verified at the PR head; no blocker or major remains.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "PR #19 body, Base/Head line and ## Diff section",
      "evidence": "headRefOid is 76b6d098431f74094dc68705b4cdbb505b9054cb but the body says Head: 2abbd0c; git diff --stat master...76b6d09 reports 4590 insertions and 561 deletions while the body says +4589 / -560.",
      "required_fix": "Update the PR body Head to 76b6d098431f74094dc68705b4cdbb505b9054cb and the diff counts to 4590/561, or remove the hardcoded counts."
    }
  ],
  "closed": []
}
```

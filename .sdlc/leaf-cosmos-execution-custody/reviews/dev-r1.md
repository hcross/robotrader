# DEV Review — Round 1

## Summary

Single-file change adds `CosmosVenueAdapter`, atomic type aliases, `leaf-cosmos`
symbol isolation, and two tests; Rust suite passes (22 exec-router tests, all
crates green). One major defect: the hand-written bech32 charset
(`qpzry9x8gf2tvdw0s3jnb5hcekmua7l`, 31 distinct chars) differs from the vault's
charset (`qpzry9x8gf2tvdw0s3jn54khce6mua7l`, 32 distinct chars), so simulated
Cosmos addresses the vault emits that contain `4`/`6` are rejected, while
`b`-bearing strings (not in the vault alphabet) are accepted. Capital/risk/vault/
hot-path invariants otherwise hold: no allocations in the gate, no LLM on the
hot path, no key material.

## Findings

### DEV-R1-F01 — [major] Cosmos bech32 destination charset disagrees with the vault
- Location: `engine-rs/crates/exec-router/src/lib.rs:711-712`
- Evidence: router literal `const BECH32_CHARSET: &str = "qpzry9x8gf2tvdw0s3jnb5hcekmua7l";` (31 distinct chars) vs. vault literal at `engine-rs/crates/risk-gate/src/vault.rs:202` `const CHARSET: &[u8; 32] = b"qpzry9x8gf2tvdw0s3jn54khce6mua7l";` (32 distinct chars). Vault-generated Cosmos addresses are `cosmos1` + 38 chars drawn from the vault charset, so destinations containing `4`/`6` are rejected and any `b`-bearing string slips through.
- Required fix: replace the router literal with the vault's charset (or, better, delegate to the same validation helper the vault uses), and add a positive test using a vault-style simulated address containing `4`/`6` plus a negative test for `b`.
- Status: open
- Origin: initial

### DEV-R1-F02 — [minor] No length bound on the Cosmos bech32 payload
- Location: `engine-rs/crates/exec-router/src/lib.rs:705-713`
- Evidence: only `rest.is_empty()` is checked; arbitrary-length all-charset strings are accepted, unlike the Ethereum (40), Sui (64), TRON (34) and Bitcoin (42-62) branches. The vault emits exactly 38 trailing chars (`cosmos1` + 38).
- Required fix: enforce the vault's simulated length (`rest.len() == 38`, total 45) or at least a sane bound, and add a regression test.
- Status: open
- Origin: initial

### DEV-R1-F03 — [nit] PR body carries stale change id and issue number
- Location: PR #234 body (metadata; `Change ID: leaf-aptos-hot-path-pods`, `Issue: #91`)
- Evidence: the PR head is `52196b355f1a3fe5be06be332b217857c78184b8` on branch `sdlc/86-leaf-cosmos-execution-custody` for issue #86, but the body's decision card still describes `leaf-aptos-hot-path-pods` / issue #91.
- Required fix: regenerate the PR body from the change template (`sdlc/templates/pr-body.md`) with `leaf-cosmos-execution-custody` / issue #86.
- Status: open
- Origin: initial

### DEV-R1-F04 — [nit] Symbol/token list mismatch
- Location: `engine-rs/crates/exec-router/src/lib.rs:662-666` vs `:849-853`
- Evidence: `SUPPORTED_TOKENS` is `["ATOM", "USDC"]` while the isolation gate accepts `ATOM-USDC`, `OSMO-ATOM`, `INJ-USDC` (OSMO/INJ absent from the token list).
- Required fix: align `SUPPORTED_TOKENS` with the isolation gate's token set, or document the convention used by sibling adapters (Avalanche/XRPL have the same shape).
- Status: open
- Origin: initial

## Follow-ups (non-blocking)
- Vault-style length check depends on `to_bech32_chars` output length (38); coordinate if the vault format changes.

## Checks run
- `cd engine-rs && cargo test` → all crates passed (exec-router 22 tests OK; cosmos tests pass).
- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` → OK.
- `PYTHONPATH=. python3.11 -m unittest discover -s backend/tests` → 315 tests OK (Python 3.11).
- `cd frontend && npm run build` → not run locally (no node_modules); CI `frontend` job on PR #234 passed.
- `gh pr checks 234` → frontend, helm, python, rust all pass.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-cosmos-execution-custody",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "52196b355f1a3fe5be06be332b217857c78184b8",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Major bech32 charset mismatch between the Cosmos router adapter and the vault must be fixed before merge.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/exec-router/src/lib.rs:711-712",
      "evidence": "Router charset 'qpzry9x8gf2tvdw0s3jnb5hcekmua7l' (31 distinct chars) vs. vault charset 'qpzry9x8gf2tvdw0s3jn54khce6mua7l' (32 distinct chars); vault-generated Cosmos addresses containing 4/6 are rejected, b-bearing strings accepted.",
      "required_fix": "Replace the router charset literal with the vault's charset or delegate to the vault validation, and add positive/negative tests using vault-style simulated addresses."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/exec-router/src/lib.rs:705-713",
      "evidence": "Only rest.is_empty() is checked; arbitrary-length all-charset strings are accepted, unlike the other chain branches; the vault emits 38 trailing chars.",
      "required_fix": "Enforce rest.len() == 38 (total 45) or a sane bound, with a regression test."
    },
    {
      "id": "DEV-R1-F03",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "PR #234 body (metadata)",
      "evidence": "Body says Change ID 'leaf-aptos-hot-path-pods' / Issue #91 while head SHA 52196b3 is on branch sdlc/86-leaf-cosmos-execution-custody for issue #86.",
      "required_fix": "Regenerate the PR body from sdlc/templates/pr-body.md with leaf-cosmos-execution-custody / issue #86."
    },
    {
      "id": "DEV-R1-F04",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/exec-router/src/lib.rs:662-666 vs :849-853",
      "evidence": "SUPPORTED_TOKENS is ['ATOM','USDC'] but the isolation gate also accepts OSMO-ATOM and INJ-USDC.",
      "required_fix": "Align SUPPORTED_TOKENS with the isolation gate's token set, or follow the sibling-adapter convention."
    }
  ],
  "closed": []
}
```
```

Let's run verdict-lint to ensure OK.
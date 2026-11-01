# DEV Review — Round 1

## Summary
Cold review of PR #207 at reviewed SHA `46a023245eb1c946ab5311d581643ceac1ba1fa0`. The change is lane M and is confined to `engine-rs/crates/exec-router/src/lib.rs`: it adds `SuiBridgeQuote`/`SuiVenueAdapter` (DeepBook v3 CLOB, Cetus CLMM, Navi) plus a Sui settlement-destination validator, plus leaf-sui symbol isolation in `SmartExecutionRouter`. The additions mirror the existing Bitcoin/Ethereum adapter pattern, preserve the SimulatedVault-only chain model, and touch no money/risk/vault/LLM paths. `cargo test` (all crates) passes. Python discover and the frontend build are red in this environment for pre-existing/infra reasons unrelated to this diff.

## Findings

### DEV-R1-F01 — [nit] Sui destination validator accepts mixed-case hex
- Location: `engine-rs/crates/exec-router/src/lib.rs` (`SuiVenueAdapter::validate_settlement_destination`)
- Evidence: `hex_part.chars().all(|c| c.is_ascii_hexdigit())` permits uppercase A–F, while canonical Sui addresses are lowercase; mixed-case strings pass.
- Required fix: none blocking; optionally enforce `.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit())` if canonical form is intended. Listed as follow-up, does not block.

## Checks run
- `cd engine-rs && cargo test` → OK (all crates: common 13, risk-gate 9, strategies 14, exec-router 10, backtest 2, node 1, common integration 59, 6 property, 18 additional; 0 failures).
- `cargo fmt --check` → only pre-existing diffs in `crates/backtest/src/lib.rs` (not this change); added hunk is fmt-clean.
- `cargo clippy -p robotrader-exec-router` → no errors (only unrelated warnings in other crates).
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → 234 tests run, 10 failures + 7 errors, all pre-existing/environmental (`ccxt`/missing modules, missing `robotrader-node` binary built on base differs) and identical failure classes on base SHA `af3c181`; no regression from this diff.
- `cd frontend && npm run build` → not runnable in this environment (`vite: command not found`); no frontend files changed.
- `gh pr checks 207` → not run (no CI configured in this offline environment).

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-sui-execution-custody",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "46a023245eb1c946ab5311d581643ceac1ba1fa0",
  "verdict": "APPROVE",
  "summary": "Lane M slice adds SuiVenueAdapter and leaf-sui isolation mirroring existing adapters; cargo test passes and no invariant is violated.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/exec-router/src/lib.rs (SuiVenueAdapter::validate_settlement_destination)",
      "evidence": "is_ascii_hexdigit() accepts uppercase A-F for an address class whose canonical rendering is lowercase.",
      "required_fix": "None required; optionally restrict to lowercase hex for canonical-form strictness."
    }
  ],
  "closed": []
}
```

# DEV Review — Round 1

## Summary

The TRON adapter and `leaf-tron` symbol isolation mirror the established leaf pattern, and CI is green (cargo test, 311 Python tests, frontend build, `gh pr checks` 4/4). However, unlike every prior leaf commit, the change adds no tests exercising the new adapter or isolation, and settlement destination validation is over-permissive: it accepts any bare `bridge:` suffix, inconsistent with the XRP hardening that requires a named rail. These are the only findings.

## Findings

### DEV-R1-F01 — [blocker] No tests exercise the new Tron adapter or leaf-tron isolation

- Location: `engine-rs/crates/exec-router/src/lib.rs:569-645` (adapter) and `mod tests` at line 762 (no tron cases)
- Evidence: feature commit `0cb3445` adds `TronBridgeQuote`/`TronVenueAdapter` and the `leaf-tron` arm in `SmartExecutionRouter::execute_for_leaf`, but the test module gains no `test_tron_…` or `test_smart_execution_router_execute_for_leaf_tron_isolation` case; `cargo test` reports 18 exec-router tests, none referencing Tron. Every prior leaf commit (`8a451ec`, `48a24aa`, `278ec99`…) added both cases in the same commit.
- Required fix: Add unit tests in `exec-router/src/lib.rs::tests` for `TronVenueAdapter::quote_bridge` (venues, protocol, fees, hurdle rate, finality), `TronVenueAdapter::validate_settlement_destination` (valid TRON Base58 address `T…34`, at least one valid named bridge, invalid short/other-chain/bare-bridge addresses), and `SmartExecutionRouter::execute_for_leaf("leaf-tron", …)` accepting `TRX-USDT`/`SUN-TRX` and rejecting an unrelated symbol.
- Status: open
- Origin: initial

### DEV-R1-F02 — [major] Settlement destination validation accepts bare `bridge:` suffix

- Location: `engine-rs/crates/exec-router/src/lib.rs:617-620`
- Evidence: `if dest.starts_with("bridge:") { return dest.len() > "bridge:".len(); }` accepts arbitrary unroutable `bridge:…` destinations. Commit `278ec99` (XRP) explicitly rejected this shape because "a bare `bridge:` prefix is not a routable venue" and now requires `bridge:xrpl:`/`bridge:ripple:`. Every other leaf (`bridge:cctp:`, `bridge:wormhole:`, …) follows the same named-prefix discipline; only TRON uses the bare form.
- Required fix: Replace the bare `bridge:` check with two or more named chain-specific bridge prefixes (e.g. `bridge:tron:` and `bridge:bittorrent:`) each requiring a non-empty suffix, keep the TRON Base58/length-34 native address check, and add negative cases for bare `bridge:` in the new tests.
- Status: open
- Origin: initial

## Checks run

- `cd engine-rs && cargo test` → 15 test suites passed, 0 failures (exec-router: 18 tests)
- `PYTHONPATH=. python3.11 -m unittest discover -s backend/tests -v` → Ran 311 tests, OK
- `cd frontend && npm run build` → built in 0.487s, 0 errors
- `gh pr checks 225` → frontend, python, rust, helm all pass

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-tron-execution-custody",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "fef3ca1bbd0ffccaa79d32efcbaeef73325e80a8",
  "verdict": "CHANGES_REQUESTED",
  "summary": "The Tron adapter and leaf-tron isolation follow the leaf pattern and CI is green, but the change ships no tests and accepts unroutable bare bridge: destinations.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/exec-router/src/lib.rs:569-645 (adapter) and mod tests at line 762 (no tron cases)",
      "evidence": "Feature commit adds TronBridgeQuote/TronVenueAdapter and the leaf-tron arm but mod tests gain no Tron case; cargo test passes with 18 exec-router tests, none referencing Tron. Prior leaf commits added both tests in the same commit.",
      "required_fix": "Add quote_bridge, validate_settlement_destination, and execute_for_leaf tests in exec-router/src/lib.rs::tests matching prior leaves."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/exec-router/src/lib.rs:617-620",
      "evidence": "validate_settlement_destination accepts bare bridge: suffix; every other leaf requires named bridge prefixes (XRP hardened in 278ec99).",
      "required_fix": "Replace bare bridge: check with named chain-specific prefixes (e.g. bridge:tron:, bridge:bittorrent:) with non-empty suffix, keeping the TRON Base58/length-34 check, and add negative tests for bare bridge:."
    }
  ],
  "closed": []
}
```
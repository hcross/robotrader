# DEV Review — Round 1

## Summary

CHANGES REQUESTED. While the diff cleanly updates backtest honesty labels across the API, UI, documentation, and tests, `cargo test --manifest-path engine-rs/Cargo.toml --workspace --all-targets` fails with exit code 101 because `test_repeated_fixture_runs_are_byte_identical` fails due to randomized `HashMap` key iteration order in `pod_pnl_attribution`, causing CI `CI/rust` on PR #21 to fail.

## Findings

### DEV-R1-F01 — [blocker] Non-deterministic serialization order in pod_pnl_attribution fails test_repeated_fixture_runs_are_byte_identical and CI/rust
- Location: `engine-rs/crates/backtest/src/lib.rs:46`
- Evidence: `cargo test --manifest-path engine-rs/Cargo.toml --workspace --all-targets` failed with exit code 101 (`assertion left == right failed: the fixture must be deterministic` due to randomized key order in `pod_pnl_attribution`), and PR #21 GitHub check `CI/rust` failed (`tests::test_repeated_fixture_runs_are_byte_identical FAILED`).
- Required fix: Change `pod_pnl_attribution` in `BacktestSummary` and `BacktestEngine::run_for_leaf` to `std::collections::BTreeMap<String, f64>` to guarantee deterministic JSON key serialization order across runs, and verify that `cargo test` passes.
- Status: open
- Origin: initial

## Checks run
- `cargo test --manifest-path engine-rs/Cargo.toml --workspace --all-targets` → FAIL (exit code 101, `test_repeated_fixture_runs_are_byte_identical`)
- `openspec validate mark-backtest-artifact-honest --strict` → PASS
- `scripts/sdlc/sdlc.sh check mark-backtest-artifact-honest` → PASS
- `gh pr checks 21` → FAIL (CI/rust failed)

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "mark-backtest-artifact-honest",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "692e4b7125050e75d2c3fac45396967c2f9b982f",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Rust unit test test_repeated_fixture_runs_are_byte_identical fails due to non-deterministic HashMap key serialization in pod_pnl_attribution, causing CI/rust to fail on PR #21.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/backtest/src/lib.rs:46",
      "evidence": "cargo test failed with exit code 101 on test_repeated_fixture_runs_are_byte_identical because HashMap iteration order in pod_pnl_attribution is randomized across runs, causing string equality assertion to fail. CI/rust also failed on PR #21.",
      "required_fix": "Use std::collections::BTreeMap<String, f64> for pod_pnl_attribution in BacktestSummary and BacktestEngine::run_for_leaf to guarantee deterministic JSON key ordering across repeated runs."
    }
  ],
  "closed": []
}
```

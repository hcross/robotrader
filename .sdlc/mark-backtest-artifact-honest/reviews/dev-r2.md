# DEV Review — Round 2

## Summary

DEV-R1-F01 is closed at `11babc7` with no regressions. `BacktestSummary.pod_pnl_attribution` and the accumulator in `BacktestEngine::run_for_leaf` now use `std::collections::BTreeMap<String, f64>`, ensuring deterministic JSON serialization key ordering across repeated runs. Local workspace tests pass without failure, 10 consecutive iterations of `test_repeated_fixture_runs_are_byte_identical` succeed, strict OpenSpec validation and SDLC checks pass, and all GitHub Actions CI checks on PR #21 (`CI/rust`, `CI/python`, `CI/frontend`, `CI/helm`, `SDLC checks/sdlc`) are green. The reviewed SHA matches the PR head SHA and the change is approved.

## Findings

### DEV-R1-F01 — [blocker] Non-deterministic serialization order in pod_pnl_attribution fails test_repeated_fixture_runs_are_byte_identical and CI/rust
- Location: `engine-rs/crates/backtest/src/lib.rs:46,96`
- Evidence: `pod_pnl_attribution` in `BacktestSummary` and `BacktestEngine::run_for_leaf` is now `std::collections::BTreeMap<String, f64>`. 10 consecutive iterations of `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest test_repeated_fixture_runs_are_byte_identical` pass cleanly with byte-identical serializations. Full workspace tests (`cargo test --manifest-path engine-rs/Cargo.toml --workspace --all-targets`) exit 0. GitHub Actions CI check `CI/rust` on PR #21 succeeded at commit `11babc7`.
- Required fix: (was) Change `pod_pnl_attribution` in `BacktestSummary` and `BacktestEngine::run_for_leaf` to `std::collections::BTreeMap<String, f64>`.
- Status: closed
- Origin: initial

### New findings
None. The fix commit is minimal and tightly scoped to `engine-rs/crates/backtest/src/lib.rs`. No regression, security, or critical defects were introduced.

## Checks run
- `cargo test --manifest-path engine-rs/Cargo.toml --workspace --all-targets` → PASS (exit 0; backtest 4/4, common 1/1, asset_override_contract 14/14, exec-router 3/3, simulated_vault_contract 1/1, risk-gate 17/17, validate bench Success, momentum_rules 18/18).
- `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest test_repeated_fixture_runs_are_byte_identical` (10 consecutive runs) → PASS (10/10 passed).
- `openspec validate mark-backtest-artifact-honest --strict` → PASS (`Change 'mark-backtest-artifact-honest' is valid`).
- `scripts/sdlc/sdlc.sh check mark-backtest-artifact-honest` → PASS (`check: PASS`, 28 tasks done, 0 open).
- `gh pr checks 21` → PASS (5/5 checks successful: `CI/frontend`, `CI/helm`, `CI/python`, `CI/rust`, `SDLC checks/sdlc`).
- `gh pr view 21 --json headRefOid,state,title` → `headRefOid=11babc754f47153d5c1c437b4b41db195b4526da`, matches worktree `HEAD`.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "mark-backtest-artifact-honest",
  "stage": "dev",
  "round": 2,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "11babc754f47153d5c1c437b4b41db195b4526da",
  "verdict": "APPROVE",
  "summary": "DEV-R1-F01 is closed at 11babc7 with deterministic BTreeMap serialization, all workspace cargo tests pass repeatedly, PR #21 CI checks are completely green, and no regressions were introduced.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "engine-rs/crates/backtest/src/lib.rs:46,96",
      "evidence": "BacktestSummary.pod_pnl_attribution and BacktestEngine::run_for_leaf now use std::collections::BTreeMap<String, f64>. 10 repeated iterations of test_repeated_fixture_runs_are_byte_identical pass cleanly, cargo test --workspace --all-targets exits 0, and GitHub Actions CI/rust on PR #21 succeeded.",
      "required_fix": "N/A — fixed and verified."
    }
  ],
  "closed": [
    "DEV-R1-F01"
  ]
}
```

stage: dev
round: 1
head_sha: 364074617a59c88312b9a001a87151d5db130418
responses:
  - id: DEV-R1-F01
    action: fixed
    evidence: "`BacktestSummary.pod_pnl_attribution` and the accumulator in `BacktestEngine::run_for_leaf` are now `std::collections::BTreeMap<String, f64>` (`engine-rs/crates/backtest/src/lib.rs`). BTreeMap serializes keys in sorted order, so `serde_json` output is deterministic across runs. Verified: 10 consecutive runs of `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest test_repeated_fixture_runs_are_byte_identical` all pass; full `cargo test --manifest-path engine-rs/Cargo.toml --workspace --all-targets` exits 0 (backtest 4/4, risk-gate 17/17, strategies 18/18, benches Success); repeated `robotrader-node --leaf-id leaf-solana` and `--leaf-id leaf-bitcoin` runs are byte-identical; all 26 leaf JSONs remain numerically and structurally equal to the pre-change baseline (0 mismatches after removing the three additive kind fields); the Docker Python suite still reports `Ran 191 tests ... OK (skipped=9)`. Evidence: `.sdlc/mark-backtest-artifact-honest/evidence/rust-tests-r2.log`, `leaf-comparison-r2.log`, `python-tests-r2.log`."

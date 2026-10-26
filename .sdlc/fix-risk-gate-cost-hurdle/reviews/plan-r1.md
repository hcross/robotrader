# PLAN Review — Round 1

## Summary

**APPROVE.** The plan is traceable to all nine approved requirements, preserves the safety-first gate order and the SCAM-SOL anti-rug proof, pins the regenerated 4/3/2 Solana baseline, and keeps the hot path synchronous and allocation-neutral. The canonical cost helpers in `common`, with `SmartExecutionRouter` delegating, are the right shared home for this change. Ten minor/nit findings remain: `cargo test --all-targets` actually runs the criterion bench; the diagram/tree `<50µs` annotation form is unspecified; the `<50µs` and stale-figure verification greps are incomplete; the SCAM-SOL fixture assertion lacks a mechanism; task 1.4 implies an unstated dev-dependency; criterion's MSRV/feature surface is unrecorded; the audit annotations lack an English-only instruction; the `execute` fee parity is tested only at `fee_bps_for`; and task 2.4 overstates non-finite handling. None blocks approval.

## Rulings on the stated risks

1. **`common` vs `exec-router` layering — acceptable.** The delta spec explicitly permits "a helper shared between the gate and `SmartExecutionRouter`", and `common` is the only existing shared crate: `Venue` and `OrderType` already live there, and both consumers already depend on it. `SmartExecutionRouter` remains the execution facade; delegation preserves one source and no release-graph inversion. The only caveat is the unstated test-only dependency in task 1.4 (F06). If the cost model grows beyond fee/spread, extract a `cost-model` crate later; not needed here.
2. **26-leaf exact assertions from node JSON — deterministic and sufficient, with two checks.** `benchmark_market_stream_for_leaf("leaf-solana")` returns `benchmark_market_stream()` (`engine-rs/crates/backtest/src/lib.rs:370-373`), the node and the test both use `BacktestEngine::default()`/`run_for_leaf`, the base timestamp is fixed, and there is no randomness or I/O. `serde_json` round-trips `f64`, so the `1e-9` tolerance is sound if full-precision literals are copied. Verify each JSON's `leaf_id` (unknown ids silently fall back to the Solana profile) and do not compare `pod_pnl_attribution` key order, which is a `HashMap`.
3. **Removing `README.md:42` instead of annotating — acceptable.** Line 42 is a Redis read-latency arrow ("Sub-millisecond reads (<50µs)"), not the `validate` budget; annotating it with the `validate` benchmark would be a category error. Removal satisfies the scenario's "no bare `<50µs` claim remains", and task 6.1 records the per-line choice in the evidence.
4. **Adding `criterion` and lockfile churn — justified but under-documented.** Criterion 0.8.2 is Apache-2.0 OR MIT, dev-only, and not linked into release binaries. However, the plan omits the MSRV (1.86) and the default `plotters`/`rayon` features, and `cargo test --all-targets` runs the bench rather than only compiling it (F01, F07). `engine-rs/Cargo.lock` is tracked, so committing it is correct.
5. **Audit French/English mix — real risk.** The audit is French (`docs/PERFORMANCE_AND_COST_AUDIT.md:1-12`) while `openspec/config.yaml:34` requires English-only repository content. The plan rewrites its `[FIXTURE]` block without saying that new/regenerated annotations must be English; otherwise the change deepens the mix (F08).

## Findings

### PLAN-R1-F01 — [minor] `cargo test --all-targets` runs the criterion bench, not just compiles it

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/design.md:88`; `.github/workflows/ci.yml:40`; `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:3-4`.
- Evidence: The design says "`cargo test --all-targets` still compiles the bench target". A probe with a `[[bench]] harness = false` target showed Cargo executing the bench binary (`Running benches/b.rs ... BENCH_WAS_RUN`). With criterion 0.8.2 it printed `Testing add / Success` and added ~10 s wall time even with a 50 ms measurement; the default criterion settings (100 samples, 3 s warm-up, 5 s measurement) will add ~16 s or more for the two new benchmarks. CI runs `cargo test --all-targets` (`.github/workflows/ci.yml:40`).
- Required fix: Either gate the bench behind a `required-features` feature so `cargo test --all-targets` skips it and `cargo bench --features <f>` runs it, or document the CI execution time and adjust the expected evidence in `## Verification`; state the choice in D7/task 4.1.
- Status: open
- Origin: initial

### PLAN-R1-F02 — [minor] The command cannot be embedded inline in the diagram/tree `<50µs` occurrences as written

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:43` (task 6.1); `README.md:48,147`; `AGENTS.md:66`; `docs/architecture.md:52`.
- Evidence: These occurrences are a fixed-width ASCII box line (`README.md:48`), `├──` tree rows (`README.md:147`, `AGENTS.md:66`), and a Mermaid node (`docs/architecture.md:52`). Inserting `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` inline would break the box/tree alignment and bloat the Mermaid node, yet the spec scenario requires each occurrence to state the measured mean and the command.
- Required fix: Define an annotation form that satisfies the spec without breaking layout, e.g. measured mean inline plus the command in a footnote/caption immediately below the occurrence, and make the verification check both the occurrence and the footnote.
- Status: open
- Origin: initial

### PLAN-R1-F03 — [minor] The `<50µs` verification grep misses the space-separated occurrences

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:73` (Verification); `docs/PERFORMANCE_AND_COST_AUDIT.md:37,65`.
- Evidence: `grep -n "50µs"` shows `docs/PERFORMANCE_AND_COST_AUDIT.md:37` and `:65` use `< 50µs` with a space. The Verification command `grep -rn "<50µs" README.md AGENTS.md docs/architecture.md docs/PERFORMANCE_AND_COST_AUDIT.md` will not match them, so a missed edit would pass. Task 6.1 names both lines, but the command is the acceptance evidence.
- Required fix: Broaden the pattern (e.g. `grep -rnE "< ?50 ?µs"`) and state the per-line expected output; keep the line inventory.
- Status: open
- Origin: initial

### PLAN-R1-F04 — [minor] Task 5.5's stale-figure grep does not cover the French audit's stale values

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:39`; `docs/PERFORMANCE_AND_COST_AUDIT.md:85,88,89,91-94`.
- Evidence: The proof command greps `22.78\|28.22\|6 trades`. It catches `$10,022.78` and `28.22`, but not `100.0%`, `6 gains / 0 perte sur 6 exécutions`, `$1.67`, `AntiRugRejected`, or the four per-pod attribution values. Task 5.4 names them, but the task 5.5 proof does not.
- Required fix: Extend the grep to the actual stale forms (e.g. `22\.78|28\.22|6 (trades|gains|exécutions)|100\.0%|1\.67|AntiRugRejected`) or replace it with a per-line checklist tied to task 5.4.
- Status: open
- Origin: initial

### PLAN-R1-F05 — [minor] The SCAM-SOL fixture-level assertion has no specified mechanism and the summary discards rejection variants

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:36` (task 5.2); `engine-rs/crates/backtest/src/lib.rs:82-90`; `BacktestSummary` fields at `engine-rs/crates/backtest/src/lib.rs:12-27`.
- Evidence: `run_for_leaf` matches `Err(_) => { rejected_orders += 1; }`, so `BacktestSummary` exposes only a count, not `RiskRejection::OnChainRugCheckFailed`. Task 5.2 asks for a fixture-level assertion that SCAM-SOL returns `OnChainRugCheckFailed` and that its edge `81.0` is below the `87.8` hurdle, but the backtest API cannot observe either. Task 3.4 already asserts the variant at the unit level.
- Required fix: Specify that task 5.2 calls `HardRiskGate::validate` directly on the fixture intent (or reuses task 3.4's assertion) and state that no `BacktestSummary`/node-JSON field is added.
- Status: open
- Origin: initial

### PLAN-R1-F06 — [minor] Task 1.4 implies an unstated `risk-gate` -> `exec-router` dev-dependency

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:6`; `design.md:69` (D1); `engine-rs/crates/risk-gate/Cargo.toml`.
- Evidence: Task 1.4 requires a `risk-gate` test that compares with `SmartExecutionRouter`, but `risk-gate` has no `robotrader-exec-router` dependency and no `[dev-dependencies]`. D1 rejects adding `robotrader-exec-router` as a `risk-gate` dependency because it "inverts the layering", without distinguishing a test-only edge.
- Required fix: State that the comparison is a `[dev-dependencies]` edge (no release-graph cycle, no release binary impact) and justify it, or move the gate-side parity assertion into `exec-router`, which already depends on `common`.
- Status: open
- Origin: initial

### PLAN-R1-F07 — [minor] Criterion 0.8.2's MSRV and default feature surface are unrecorded

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/design.md:75,88` (D7 and its risk); `tasks.md:29` (task 4.1).
- Evidence: `cargo info criterion@0.8` reports version `0.8.2`, `license: Apache-2.0 OR MIT`, `rust-version: 1.86`, and default features `[rayon, plotters, cargo_bench_support]`. The plan records the license and build-time cost but not the MSRV or the optional `plotters`/`rayon` surface. CI uses `dtolnay/rust-toolchain@stable`, so CI is fine; the local toolchain requirement is unrecorded.
- Required fix: Record the MSRV (`1.86`) and confirm the CI/local toolchain; consider `default-features = false, features = ["cargo_bench_support"]` if HTML reports and parallel execution are not needed (a probe confirmed this configuration compiles and runs), and state the chosen feature set in D7.
- Status: open
- Origin: initial

### PLAN-R1-F08 — [minor] The audit regeneration has no English-only instruction

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:38,43` (tasks 5.4, 6.1); `docs/PERFORMANCE_AND_COST_AUDIT.md:1-12`; `openspec/config.yaml:34`.
- Evidence: `openspec/config.yaml:34` requires repository content to be English-only, while the audit is French and already carries a mixed English "Provenance legend (new text — English)" block. Tasks 5.4/6.1 rewrite the `[FIXTURE]` block and add `<50µs` annotations without specifying the language of the new text.
- Required fix: State in tasks 5.4/6.1 that every new or regenerated annotation/prose is English (leaving untouched pre-existing French text out of scope), so the change does not add more mixed language.
- Status: open
- Origin: initial

### PLAN-R1-F09 — [minor] The round-trip fee scenario is tested at `fee_bps_for`, not `SmartExecutionRouter::execute`

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:5` (task 1.3); spec scenario "The round-trip fee matches the executor" in `openspec/changes/fix-risk-gate-cost-hurdle/specs/risk-hurdle/spec.md`.
- Evidence: Task 1.3 asserts the per-side fee is identical between the `common` helper and `SmartExecutionRouter::fee_bps_for`; the spec's THEN says "`SmartExecutionRouter::execute` charges `3.6` bps of round-trip fee for the same pair". `engine-rs/crates/exec-router/src/lib.rs` currently has no tests (grep for `#[test]` returns nothing), so no existing test covers `execute`.
- Required fix: Add an `execute`-level assertion (construct an `ApprovedOrder`, call `execute`, and assert `fee_usd / notional_usd * 10_000 == 3.6` for `BinancePerp`/`PostOnlyMaker`), or explicitly state that `fee_bps_for` parity plus the unchanged `* 2.0` in `execute` is the evidence.
- Status: open
- Origin: initial

### PLAN-R1-F10 — [nit] Task 2.4 overstates the strict comparison as rejecting every "non-finite edge"

- Location: `openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:13` (task 2.4).
- Evidence: `if !(expected_edge_bps > hurdle_bps)` rejects `NaN` and `-inf`, but `+inf > hurdle` is true and would be approved. The spec only requires `NaN` fail-closed; task 3.6 correctly names `NaN`.
- Required fix: Say "NaN edge" (matching task 3.6), or add an explicit `expected_edge_bps.is_finite()` guard if `+inf` must also be rejected and record that as an approved behavior.
- Status: open
- Origin: initial

## Checks run

- `git rev-parse HEAD` → `6ed356c35e5380e6cfc5dc676b6861b75350a16d`.
- `openspec validate fix-risk-gate-cost-hurdle --strict` → `Change 'fix-risk-gate-cost-hurdle' is valid` (exit 0).
- `scripts/sdlc/sdlc.sh check fix-risk-gate-cost-hurdle` → `PASS` (OpenSpec, spec-lint, verdict-lint; 35 open tasks).
- Inspected `engine-rs/crates/risk-gate/src/lib.rs`, `exec-router/src/lib.rs`, `common/src/lib.rs`, `backtest/src/lib.rs`, `node/src/main.rs`, `strategies/src/lib.rs`, and the crate manifests.
- Verified the documentation line inventory with `grep -n "50µs" README.md AGENTS.md docs/architecture.md docs/PERFORMANCE_AND_COST_AUDIT.md`.
- Verified `criterion 0.8.2` metadata with `cargo info criterion@0.8` (Apache-2.0 OR MIT, `rust-version: 1.86`, default features `rayon`/`plotters`/`cargo_bench_support`).
- Probed `cargo test --all-targets` with a `[[bench]] harness = false` target: Cargo ran the bench binary; with criterion 0.8.2 it printed `Testing add / Success` and added ~10 s wall time with a 50 ms measurement.
- Confirmed `origin/master` == base `7c7537c`, `engine-rs/Cargo.lock` is tracked, and `scripts/check_contract_single_source.py` accepts `--root`.
- Re-derived the spec's key hurdle values from the current fee table (`8.1`, `22.0`, `6.5`, `87.8`, `177.2`) and confirmed the unchanged pod formulas are consistent with the 4/3/2 fixture split.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-risk-gate-cost-hurdle",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "6ed356c35e5380e6cfc5dc676b6861b75350a16d",
  "verdict": "APPROVE",
  "summary": "The plan is traceable, preserves the safety gate order and the anti-rug proof, and its cost model and fixture strategy are sound; ten minor/nit findings remain, none blocking.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/design.md:88; .github/workflows/ci.yml:40",
      "evidence": "The design says cargo test --all-targets only compiles the bench, but a probe with a [[bench]] harness=false target showed Cargo executes it; with criterion 0.8.2 it printed 'Testing add / Success' and added ~10 s with a 50 ms measurement.",
      "required_fix": "Gate the bench behind required-features so cargo test --all-targets skips it and cargo bench --features runs it, or document the CI execution time and adjust the Verification evidence."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:43 (task 6.1); README.md:48,147; AGENTS.md:66; docs/architecture.md:52",
      "evidence": "These occurrences are a fixed-width ASCII box line, tree rows, and a Mermaid node; inserting the full cargo bench command inline would break layout, yet the spec scenario requires each occurrence to state the mean and the command.",
      "required_fix": "Define an annotation form (measured mean inline plus the command in an adjacent footnote/caption) that satisfies the spec without breaking layout, and make the verification check both."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:73; docs/PERFORMANCE_AND_COST_AUDIT.md:37,65",
      "evidence": "The audit uses '< 50µs' with a space at lines 37 and 65; the Verification command 'grep -rn \"<50µs\"' cannot match them, so a missed edit would pass.",
      "required_fix": "Broaden the pattern (e.g. grep -rnE \"< ?50 ?µs\") and state the per-line expected output."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:39; docs/PERFORMANCE_AND_COST_AUDIT.md:85,88,89,91-94",
      "evidence": "The task 5.5 proof greps 22.78|28.22|6 trades, which misses 100.0%, '6 gains / 0 perte sur 6 exécutions', $1.67, AntiRugRejected, and the four per-pod attribution values.",
      "required_fix": "Extend the grep to the actual stale forms or replace it with a per-line checklist tied to task 5.4."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:36; engine-rs/crates/backtest/src/lib.rs:82-90",
      "evidence": "run_for_leaf discards the RiskRejection variant in Err(_) and BacktestSummary exposes only rejected_orders, so task 5.2's fixture-level assertion of OnChainRugCheckFailed and the 87.8 hurdle has no specified mechanism.",
      "required_fix": "Specify a direct HardRiskGate::validate call on the fixture intent (or reuse task 3.4) and state that no BacktestSummary/node-JSON field is added."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:6; design.md:69; engine-rs/crates/risk-gate/Cargo.toml",
      "evidence": "Task 1.4 requires a risk-gate test that calls SmartExecutionRouter, but risk-gate has no exec-router dependency; D1 rejects an exec-router dependency without distinguishing a test-only dev-dependency.",
      "required_fix": "State that the comparison is a [dev-dependencies] edge with no release-graph cycle and justify it, or move the gate-side parity assertion into exec-router."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/design.md:75,88; tasks.md:29",
      "evidence": "cargo info criterion@0.8 reports 0.8.2, Apache-2.0 OR MIT, rust-version 1.86, and default features [rayon, plotters, cargo_bench_support]; the plan records neither the MSRV nor the feature surface.",
      "required_fix": "Record the MSRV (1.86) and confirm the toolchain; consider default-features = false with cargo_bench_support if HTML reports and parallel execution are unnecessary, and state the chosen feature set in D7."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:38,43; docs/PERFORMANCE_AND_COST_AUDIT.md:1-12; openspec/config.yaml:34",
      "evidence": "openspec/config.yaml:34 requires English-only repository content, while the audit is French and tasks 5.4/6.1 rewrite it without specifying the language of the new annotations.",
      "required_fix": "State in tasks 5.4/6.1 that every new or regenerated annotation/prose is English, leaving untouched pre-existing French text out of scope."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:5; specs/risk-hurdle/spec.md (scenario 'The round-trip fee matches the executor')",
      "evidence": "Task 1.3 tests the per-side fee via fee_bps_for; the spec's THEN says SmartExecutionRouter::execute charges 3.6 bps, and exec-router currently has no tests covering execute.",
      "required_fix": "Add an execute-level assertion of the 3.6 bps round-trip fee for BinancePerp/PostOnlyMaker, or explicitly state that fee_bps_for parity plus the unchanged *2.0 in execute is the evidence."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-risk-gate-cost-hurdle/tasks.md:13 (task 2.4)",
      "evidence": "The task says the strict comparison rejects a 'non-finite edge', but !(edge > hurdle) rejects NaN and -inf while +inf > hurdle is approved; the spec only requires NaN fail-closed and task 3.6 names NaN.",
      "required_fix": "Say 'NaN edge' to match task 3.6, or add an explicit is_finite guard if +inf must also be rejected and record that as approved behavior."
    }
  ],
  "closed": []
}
```

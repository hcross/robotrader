# Tasks — mark-backtest-artifact-honest

> Spec: [`specs/backtest-honesty/spec.md`](specs/backtest-honesty/spec.md). Lane S has no `design.md`; this list orders the work and the spec defines the required behaviour.

## 1. Rust fixture contract

- [ ] 1.1 Add `artifact_kind: String`, `source: String`, and `fill_simulation: bool` to `BacktestSummary`; set them to `policy_sanity_check`, `FIXTURE`, and `false` in every constructor path. (covers: "The deterministic execution artefact declares a policy-sanity-check kind" / "Node summary is a policy sanity check")
- [ ] 1.2 Update the `exec-router` and `backtest` doc comments to describe `realized_pnl_usd` as declared-edge minus modelled fees and spread; make no arithmetic change. (covers: "The fixture is explicitly a rule and plumbing sanity check, not a fill simulation" / "The PnL model is described as declared-edge arithmetic")
- [ ] 1.3 Confirm the fixture event inputs, pod edge formulas, `max_slippage_bps` values, PnL arithmetic, and Sharpe arithmetic are unchanged in the diff. (covers: "Labels are consistent and no numeric baseline is silently re-derived" / "Numbers are unchanged"; "The shared strategy and risk code path is unchanged")

## 2. Rust tests

- [ ] 2.1 Update the Solana, per-leaf, and anti-rug tests to assert `artifact_kind`, `source`, and `fill_simulation` on the summary while keeping every existing numeric baseline. (covers: "Tests assert the canonical pair"; "Rule outcomes remain asserted")
- [ ] 2.2 Replace the `net_profit_usd > 0` acceptance in the fixture tests with exact-baseline and rule/plumbing assertions; keep exact numeric equality as a determinism baseline. (covers: "Profitability is not an acceptance criterion")
- [ ] 2.3 Add a repeat-run test that runs the same leaf and envelope twice and asserts identical numeric fields. (covers: "A repeated run is byte-identical")
- [ ] 2.4 Add the accounting-identity assertion that the sum of `pod_pnl_attribution` equals `net_profit_usd`. (covers: "Rule outcomes remain asserted")
- [ ] 2.5 Keep the SCAM-SOL `OnChainRugCheckFailed`, edge-hurdle boundary, venue-hurdle, and `<= 4` pods-per-chain assertions unchanged and green. (covers: "The anti-rug and edge-hurdle assertions remain green")

## 3. Backend payloads

- [ ] 3.1 Add a canonical `ARTIFACT_KIND_POLICY_SANITY_CHECK = "policy_sanity_check"` constant next to the provenance enum; do not change the four source values. (covers: "One canonical pair is used"; "The provenance enum and #7 labels are unchanged")
- [ ] 3.2 Propagate `artifact_kind`, `source`, and `fill_simulation` through `run_rust_backtest`, `run_rust_backtest_for_leaf`, `last_rust_backtest`, `get_population_metrics`, and no-null default handling. (covers: "Every API surface propagates the kind"; "Fixture metrics remain numeric under the new kind")
- [ ] 3.3 Rewrite both `source_detail` strings to state "deterministic policy sanity check on a synthetic fixture; not a fill simulation". (covers: "The description denies fill simulation"; "Tests assert the canonical pair")
- [ ] 3.4 Update `backend/server.py` docstrings and responses for status, hierarchy, backtest, regime, and kill-switch so no endpoint describes the fixture as backtest performance. (covers: "Status payload does not claim performance"; "Every API surface propagates the kind")
- [ ] 3.5 Update `QuantAuditorAgent.audit_latest_backtest`: carry the three kind fields and replace the Sharpe-derived `FIXTURE_HEALTHY_EDGE` verdict with a plumbing verdict that claims no edge or health. (covers: "Profitability is not an acceptance criterion"; "Every API surface propagates the kind")
- [ ] 3.6 Keep the fixture/live execution split and the measured-only treasury aggregate unchanged; add a regression assertion that no fixture PnL enters the measured population. (covers: "No fixture value enters the measured population"; "The provenance enum and #7 labels are unchanged")

## 4. Backend tests

- [ ] 4.1 Extend `test_integrity_provenance.py` and `test_metrics_populations.py` to assert the canonical kind pair, `fill_simulation == false`, and the new `source_detail` on both backtest branches and the auditor. (covers: "Tests assert the canonical pair"; "Every API surface propagates the kind")
- [ ] 4.2 Replace positive-PnL acceptance in `test_architecture.py` and `test_hierarchy_v3.py` with exact fixture-baseline or rule/plumbing assertions. (covers: "Profitability is not an acceptance criterion")
- [ ] 4.3 Keep the `#7` provenance, `#4a` hurdle, anti-rug, and 26-leaf tests green without changing their numeric expectations. (covers: "The anti-rug and edge-hurdle assertions remain green"; "The provenance enum and #7 labels are unchanged")

## 5. Frontend labels

- [ ] 5.1 Add the shared human label "Policy sanity check" to `frontend/src/lib/provenance.js` and render it with the existing `FIXTURE` badge. (covers: "One canonical pair is used"; "UI fixture surfaces name the policy sanity check")
- [ ] 5.2 Relabel the dashboard fixture tile and any fixture summary caption from "Fixture Backtest Rust" to the policy sanity check wording; remove performance-claim phrasing from the fixture tile. (covers: "UI fixture surfaces name the policy sanity check")
- [ ] 5.3 Relabel the leaf replay result, per-pod attribution, and fixture execution-ledger caption; keep the `FIXTURE` badge and do not imply a real fill ledger. (covers: "UI fixture surfaces name the policy sanity check"; "The description denies fill simulation")

## 6. Documentation

- [ ] 6.1 Update `README.md`: name the current artefact a deterministic policy sanity check, qualify or remove `Replay == Paper == Live` as an implemented claim, and stop quoting fixture PnL/Sharpe as performance in the audit summary. (covers: "README and AGENTS do not claim measured backtest performance")
- [ ] 6.2 Update `AGENTS.md`: same qualification in the project overview, the `backtest` crate description, and the test heading. (covers: "README and AGENTS do not claim measured backtest performance")
- [ ] 6.3 Update `docs/architecture.md`: remove the implemented Parquet/DuckDB historical-replay and Sharpe/Sortino performance claim for the current artefact. (covers: "Architecture documentation does not claim an implemented historical replay")
- [ ] 6.4 Update `docs/PERFORMANCE_AND_COST_AUDIT.md` §1 and §3.1: label every fixture figure block `policy_sanity_check` / `FIXTURE`, state it is not a fill simulation, and keep live-testnet as the only measured population. (covers: "Audit document presents the fixture as a policy sanity check"; "The description denies fill simulation")
- [ ] 6.5 Sweep the repository for `Fixture Backtest Rust`, `FIXTURE_HEALTHY_EDGE`, `sanity backtest`, `synthetic backtest`, `simulated backtest`, and unqualified `Backtest == Paper == Live`; leave only intended-target wording and identifier names. (covers: "One canonical pair is used")

## 7. Evidence

- [ ] 7.1 Capture the pre-change and post-change `robotrader-node --leaf-id <leaf>` JSON for all 26 leaves and record numeric equality in the change evidence. (covers: "Numbers are unchanged"; "A numeric drift is explicit, never silent")
- [ ] 7.2 Capture the two identical Solana runs used by the determinism test. (covers: "A repeated run is byte-identical")
- [ ] 7.3 Attach the Rust, Python, frontend, OpenSpec, and SDLC check outputs to the issue or PR. (covers: "Tests assert the canonical pair"; "The anti-rug and edge-hurdle assertions remain green")

## Verification

- `cd engine-rs && cargo test`
  → expected: all Rust suites pass, including the 26-leaf baselines, SCAM-SOL `OnChainRugCheckFailed`, the edge hurdle, the `<= 4` bound, the new kind fields, the repeat-run determinism test, and the accounting identity.
- `cargo run --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id leaf-solana`
  → expected: JSON with `artifact_kind == "policy_sanity_check"`, `source == "FIXTURE"`, `fill_simulation == false`, and the unchanged baseline (`total_trades: 4`, `rejected_orders: 3`, `net_profit_usd ≈ 24.727172152519415`, `sharpe_ratio ≈ 128.52308889884674`).
- `diff <(cargo run --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id leaf-solana) <(cargo run --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id leaf-solana)`
  → expected: no output (byte-identical repeated runs).
- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node && PYTHONPATH=. python3 -m unittest discover -s backend/tests -v`
  → expected: all Python suites pass, including the canonical kind assertions, the updated auditor verdict, the `#7` provenance split, and the `#4a` non-regression tests.
- `cd frontend && npm run build`
  → expected: production build succeeds; the fixture surfaces render "Policy sanity check" with the `FIXTURE` badge.
- `openspec validate mark-backtest-artifact-honest --strict`
  → expected: pass.
- `scripts/sdlc/sdlc.sh check mark-backtest-artifact-honest`
  → expected: pass (OpenSpec strict, spec lint, verdict lint).
- `grep -rn "Fixture Backtest Rust\|FIXTURE_HEALTHY_EDGE\|sanity backtest\|synthetic backtest\|simulated backtest" README.md AGENTS.md docs frontend/src backend engine-rs`
  → expected: no output.
- `grep -rn "policy_sanity_check" README.md AGENTS.md docs frontend/src backend engine-rs`
  → expected: a hit in the Rust summary, each backend payload path, the UI label module, the audit, and the README/AGENTS fixture descriptions.
- Diff the 26 post-change `robotrader-node --leaf-id <leaf>` JSON files against the baselines recorded at the base SHA; numeric equality is required, and any difference must be recorded as a spec amendment, not a silent re-baseline.

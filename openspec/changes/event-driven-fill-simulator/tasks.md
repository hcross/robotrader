# Tasks: Event-Driven Fill Simulator and Position Lifecycle Engine

## 1. Core Fill Simulation & Order Queue Engine (`robotrader-exec-router`)

- [ ] 1.1 Implement `EventDrivenFillSimulator` struct, `SimulatedFill`, `FillStatus`, and order queue state in `robotrader-exec-router` (covers: Order type execution and queue fill models).
- [ ] 1.2 Implement resting queue placement, tick-crossing execution, and OBI-based queue starvation logic for `OrderType::PostOnlyMaker` (covers: Scenario: Maker order fills on crossing price tick).
- [ ] 1.3 Implement adverse price divergence tracking and resting horizon expiration for maker orders transitioning to `UNFILLED_EXPIRED` with zero fee (covers: Scenario: Maker order expires unfilled during adverse price divergence).
- [ ] 1.4 Implement trade-through fill evaluation with adverse selection spread adjustment for `OrderType::Limit` (covers: Scenario: Limit order fills with adverse selection when market trades through).
- [ ] 1.5 Implement immediate execution applying canonical spread and liquidity-scaled depth slippage for `OrderType::Market` and `OrderType::MevBundleAtomic` (covers: Scenario: Taker order executes with spread and liquidity-dependent price impact).
- [ ] 1.6 Add comprehensive unit tests in `exec-router` validating maker queue starvation, expiration, limit trade-through, and taker liquidity impact (covers: Order type execution and queue fill models).

## 2. Multi-Tick Position Lifecycle & Non-Circular PnL Engine (`robotrader-backtest`)

- [ ] 2.1 Implement `OpenPosition` and `ClosedPosition` data structures tracking entry price, quantity, side, entry fee, TP/SL levels, and duration in `robotrader-backtest` (covers: Multi-tick position lifecycle and exit boundary evaluation).
- [ ] 2.2 Implement non-circular net realized PnL calculation strictly derived from `(exit_price - entry_price) * direction * quantity - entry_fee - exit_fee - funding_settlement` independent of `expected_edge_bps` (covers: Scenario: Non-circular PnL invariant across varying declared edges).
- [ ] 2.3 Implement stop-loss boundary evaluation realizing losses on adverse market movements (covers: Scenario: Declared edge does not mint profit on adverse price movement, Scenario: Position closes at stop-loss boundary with realized loss).
- [ ] 2.4 Implement take-profit target exit evaluation when market ticks reach or exceed profit targets (covers: Scenario: Position closes at take-profit target).
- [ ] 2.5 Implement end-of-stream mark-to-market position settlement using final tick mid-price with reason `END_OF_STREAM_MTM` (covers: Scenario: Position marks to market at end of stream).

## 3. Multi-Tick Market Streams & Statistical Metrics (`robotrader-backtest`)

- [ ] 3.1 Implement multi-tick synthetic market stream generator for leaf ecosystems featuring both uptrends and downtrends with realistic volatility (covers: Multi-tick market stream and statistical return metrics).
- [ ] 3.2 Implement `EventDrivenBacktestEngine` orchestrating pod events, risk gate validation, fill simulator, and position lifecycle over sequential ticks (covers: Multi-tick market stream and statistical return metrics).
- [ ] 3.3 Implement unbiased Sharpe ratio calculation returning `0.0` on zero return variance without sentinel constants (covers: Scenario: Zero variance return stream evaluates to zero Sharpe ratio).
- [ ] 3.4 Verify simulation stream yields both winning and losing trades with `win_rate_pct < 100.0` and `losing_trades >= 1` (covers: Scenario: Simulation generates both winning and losing trades).
- [ ] 3.5 Define `EventDrivenSimulationSummary` struct carrying `artifact_kind: "event_driven_fill_simulation"`, `source: "SIMULATED"`, `fill_simulation: true`, and `pnl_circularity: "NONE_PRICE_PATH_DERIVED"` (covers: Requirement: Node CLI exposes event-driven fill simulation).

## 4. Node CLI Integration (`robotrader-node`)

- [ ] 4.1 Add `--simulate-fills` command-line flag handling in `robotrader-node/src/main.rs` (covers: Requirement: Node CLI exposes event-driven fill simulation).
- [ ] 4.2 Wire `--simulate-fills` with optional `--leaf-id` to execute `EventDrivenBacktestEngine` and emit serialized `EventDrivenSimulationSummary` JSON to stdout (covers: Scenario: Node CLI with simulate-fills flag produces simulation artifact).
- [ ] 4.3 Ensure default invocation without `--simulate-fills` continues emitting legacy `policy_sanity_check` summary (covers: Scenario: Node CLI without simulate-fills flag preserves policy sanity check).

## 5. Regression Testing & Baseline Compatibility

- [ ] 5.1 Verify `SmartExecutionRouter::execute` remains intact and produces identical declared-edge PnL for sanity check callers (covers: Scenario: Legacy execution router produces identical declared-edge fixture output).
- [ ] 5.2 Verify that all existing unit and integration tests in `robotrader-backtest`, `robotrader-risk-gate`, `robotrader-strategies`, and `robotrader-exec-router` continue to pass without modification (covers: Scenario: Deterministic sanity check test suite remains green).
- [ ] 5.3 Write dedicated end-to-end integration tests in `backtest` asserting invariance of PnL when `expected_edge_bps` is varied on the event-driven simulator (covers: Scenario: Non-circular PnL invariant across varying declared edges).

## Verification

- `cargo test --manifest-path engine-rs/Cargo.toml` → expected: all tests pass across all crates (exec-router, backtest, risk-gate, strategies, common, node).
- `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest` → expected: all legacy baseline fixture tests and new event-driven simulation tests pass.
- `cargo run --manifest-path engine-rs/Cargo.toml --bin robotrader-node -- --leaf-id leaf-solana` → expected: JSON output with `"artifact_kind": "policy_sanity_check"`, `"fill_simulation": false`, and identical legacy baseline numbers.
- `cargo run --manifest-path engine-rs/Cargo.toml --bin robotrader-node -- --leaf-id leaf-solana --simulate-fills` → expected: JSON output with `"artifact_kind": "event_driven_fill_simulation"`, `"source": "SIMULATED"`, `"fill_simulation": true`, `"pnl_circularity": "NONE_PRICE_PATH_DERIVED"`, and `"losing_trades" >= 1`.
- `openspec validate event-driven-fill-simulator --strict` → expected: validation passes with zero errors.
- `python3 scripts/sdlc/spec-lint.py --change event-driven-fill-simulator` → expected: lint passes with zero warnings or errors.

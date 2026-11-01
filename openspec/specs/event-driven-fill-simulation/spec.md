# event-driven-fill-simulation Specification

## Purpose
TBD - created by archiving change event-driven-fill-simulator. Update Purpose after archive.
## Requirements
### Requirement: Event-driven fill simulator separates execution from declared edge

The system SHALL provide an `EventDrivenFillSimulator` and position lifecycle management engine that compute realized PnL without reading or multiplying `OrderIntent::expected_edge_bps`. Realized PnL MUST be computed solely from the difference between the actual exit price and actual entry price, adjusted for transaction fees and funding settlements: `(exit_price - entry_price) * direction * quantity - entry_fee_usd - exit_fee_usd - funding_settlement_usd`. For any approved order, mutating `expected_edge_bps` to any value that passes `HardRiskGate::validate` SHALL NOT alter the resulting `realized_pnl_usd`.

#### Scenario: Non-circular PnL invariant across varying declared edges

- **WHEN** an approved order intent is processed through the event-driven simulator across identical subsequent market events with `expected_edge_bps` set to 15.0 and then repeated with `expected_edge_bps` set to 85.0
- **THEN** the resulting `realized_pnl_usd` is identical to the exact cent between both runs

#### Scenario: Declared edge does not mint profit on adverse price movement

- **WHEN** an approved buy order has `expected_edge_bps` set to 100.0 but subsequent market ticks decline below the entry price and trigger a stop-loss exit
- **THEN** `realized_pnl_usd` is negative, reflecting the adverse price movement and trading fees

### Requirement: Order type execution and queue fill models

The `EventDrivenFillSimulator` SHALL simulate order execution according to the order's `OrderType`. For `OrderType::PostOnlyMaker`, resting orders SHALL be placed at the top of book (`best_bid` for Buy, `best_ask` for Sell) and SHALL fill on a subsequent tick only when the market price touches or crosses the resting price and order book imbalance (`obi`) does not cause complete queue starvation. If the market price diverges before fill within the order's resting horizon, the order MUST transition to `UNFILLED_EXPIRED`. For `OrderType::Limit`, the order SHALL fill at the limit or reference price adjusted for adverse selection when a subsequent tick trades through the limit price. For `OrderType::Market` and `OrderType::MevBundleAtomic`, the order SHALL fill on the entry tick or next latency-delayed tick, applying canonical spread from `spread_bps_for(order_type, mev_priority_tip_bps)` and depth slippage proportional to order notional relative to available book liquidity.

#### Scenario: Maker order fills on crossing price tick

- **WHEN** a buy `OrderType::PostOnlyMaker` order rests at the top of book and a subsequent tick offers matching ask liquidity at or below the resting price without queue starvation
- **THEN** the order status transitions to filled with fill price matching the resting maker price

#### Scenario: Maker order expires unfilled during adverse price divergence

- **WHEN** a buy `OrderType::PostOnlyMaker` order rests at the top of book and subsequent ticks move upward away from the resting price through the resting horizon without matching
- **THEN** the order status transitions to `UNFILLED_EXPIRED`
- **THEN** zero position is opened and zero trading fee is assessed

#### Scenario: Limit order fills with adverse selection when market trades through

- **WHEN** a limit order is placed and subsequent market events trade through the limit price
- **THEN** the limit order fills with an adverse selection adjustment applied to the execution price

#### Scenario: Taker order executes with spread and liquidity-dependent price impact

- **WHEN** an `OrderType::Market` or `OrderType::MevBundleAtomic` order executes against the order book
- **THEN** the fill price reflects the canonical order-type spread plus adverse selection slippage scaled by order notional relative to available market liquidity

### Requirement: Multi-tick position lifecycle and exit boundary evaluation

The simulation engine SHALL track open positions across sequential market events, recording `entry_price`, `quantity`, `side`, `entry_fee_usd`, `take_profit_bps`, `stop_loss_bps`, and open duration. An open position MUST close when a subsequent market event reaches or exceeds its take-profit price boundary, reaches or falls below its stop-loss price boundary, or reaches the final tick of the event stream. When closed at the final tick of the event stream, the position MUST be marked to market using the final mid price. Every closed position MUST record its exit price, exit fee, gross PnL, net realized PnL, and close reason.

#### Scenario: Position closes at take-profit target

- **WHEN** an open long position encounters a subsequent market tick whose price equals or exceeds the entry price plus `take_profit_bps`
- **THEN** the position closes with close reason `TAKE_PROFIT`
- **THEN** the realized PnL reflects the positive price difference minus entry and exit transaction fees

#### Scenario: Position closes at stop-loss boundary with realized loss

- **WHEN** an open long position encounters a subsequent market tick whose price equals or falls below the entry price minus `stop_loss_bps`
- **THEN** the position closes with close reason `STOP_LOSS`
- **THEN** the realized PnL is negative, accounting for the adverse price delta and transaction fees

#### Scenario: Position marks to market at end of stream

- **WHEN** an open position remains active when the input market event stream terminates
- **THEN** the position closes with close reason `END_OF_STREAM_MTM`
- **THEN** exit valuation is calculated at the final tick's mid price

### Requirement: Multi-tick market stream and statistical return metrics

The event-driven simulation stream SHALL provide multi-tick price series featuring both favourable and adverse market movements relative to active pod entries. The simulation summary MUST record `filled_orders`, `unfilled_expired_orders`, `rejected_orders`, `winning_trades`, `losing_trades`, `net_profit_usd`, `max_drawdown_pct`, and `sharpe_ratio`. The simulation stream MUST generate at least one winning trade and at least one losing trade, verifying that `losing_trades > 0` under realistic market variation. The Sharpe ratio SHALL be computed from per-period equity returns across the simulation timeline, and MUST evaluate to `0.0` when return variance is zero without returning any magic sentinel value.

#### Scenario: Simulation generates both winning and losing trades

- **WHEN** the event-driven fill simulation executes across the multi-tick leaf market stream
- **THEN** the summary reports `winning_trades >= 1`
- **THEN** the summary reports `losing_trades >= 1`
- **THEN** `win_rate_pct` is strictly less than 100.0

#### Scenario: Zero variance return stream evaluates to zero Sharpe ratio

- **WHEN** all trade period returns in a simulation stream are identical resulting in zero variance
- **THEN** the computed Sharpe ratio is `0.0`
- **THEN** the Sharpe ratio does not equal `10.0` or any sentinel constant

### Requirement: Node CLI exposes event-driven fill simulation

`robotrader-node` SHALL support the `--simulate-fills` CLI flag, accepting an optional `--leaf-id <id>` argument. When invoked with `--simulate-fills`, `robotrader-node` MUST emit JSON to stdout with `artifact_kind` equal to `event_driven_fill_simulation`, `source` equal to `SIMULATED`, `fill_simulation` equal to `true`, and `pnl_circularity` equal to `NONE_PRICE_PATH_DERIVED`. The JSON output MUST include `leaf_id`, `filled_orders`, `unfilled_expired_orders`, `rejected_orders`, `winning_trades`, `losing_trades`, `net_profit_usd`, `sharpe_ratio`, `max_drawdown_pct`, and `trade_executions`. When invoked without `--simulate-fills`, `robotrader-node` MUST continue emitting the deterministic policy sanity check summary with `artifact_kind: "policy_sanity_check"` and `fill_simulation: false`.

#### Scenario: Node CLI with simulate-fills flag produces simulation artifact

- **WHEN** `robotrader-node --leaf-id leaf-solana --simulate-fills` completes
- **THEN** stdout JSON carries `artifact_kind` equal to `event_driven_fill_simulation`
- **THEN** stdout JSON carries `source` equal to `SIMULATED`
- **THEN** stdout JSON carries `fill_simulation` equal to `true`
- **THEN** stdout JSON carries `pnl_circularity` equal to `NONE_PRICE_PATH_DERIVED`

#### Scenario: Node CLI without simulate-fills flag preserves policy sanity check

- **WHEN** `robotrader-node --leaf-id leaf-solana` is invoked without `--simulate-fills`
- **THEN** stdout JSON carries `artifact_kind` equal to `policy_sanity_check`
- **THEN** stdout JSON carries `source` equal to `FIXTURE`
- **THEN** stdout JSON carries `fill_simulation` equal to `false`

### Requirement: Compatibility and preservation of policy sanity check baselines

The system MUST preserve `SmartExecutionRouter::execute`, `run_deterministic_6_month_benchmark`, and `run_leaf_ecosystem_benchmark` intact without altering their declared-edge PnL arithmetic, trade counts, or per-leaf numeric baselines. All existing tests in `robotrader-backtest` and `robotrader-risk-gate` verifying `policy_sanity_check` baselines, anti-rug rejections, and fee hurdles SHALL continue to pass without modification.

#### Scenario: Legacy execution router produces identical declared-edge fixture output

- **WHEN** `SmartExecutionRouter::execute` is called on an approved order with timestamp `T`
- **THEN** the returned `ExecutionReport` contains `realized_pnl_usd` computed from `order.approved_notional_usd * (net_edge_bps / 10_000.0)`
- **THEN** no event-driven fill simulator logic is invoked on this legacy path

#### Scenario: Deterministic sanity check test suite remains green

- **WHEN** `cargo test -p robotrader-backtest` and `cargo test -p robotrader-risk-gate` are executed
- **THEN** all legacy baseline tests pass without numeric deviation
- **THEN** `artifact_kind` on legacy summaries remains `policy_sanity_check`


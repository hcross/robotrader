# risk-hurdle Specification

## Purpose
TBD - created by archiving change fix-risk-gate-cost-hurdle. Update Purpose after archive.
## Requirements
### Requirement: The edge hurdle is computed from execution cost

`HardRiskGate::validate` MUST compute a per-intent execution-cost hurdle and MUST reject the intent unless `intent.expected_edge_bps` is strictly greater than that hurdle. The hurdle MUST equal `round_trip_fee_bps + spread_bps + expected_impact_bps + effective_buffer_bps`, where:

- `round_trip_fee_bps` is twice the canonical per-side fee for `intent.venue` and `intent.order_type`;
- `spread_bps` is the canonical spread component for `intent.order_type`, as defined by the canonical-cost requirement below;
- `expected_impact_bps` is `intent.max_slippage_bps` converted to `f64`;
- `effective_buffer_bps` is defined by the buffer requirement below.

The gate MUST read `intent.venue`, `intent.order_type`, and `intent.max_slippage_bps`. A fixed threshold MUST NOT replace the computed hurdle. The computation MUST be a pure function of the intent and `RiskLimits`; it MUST NOT read another leaf's, chain's, or venue's state.

#### Scenario: On-chain atomic pool rejects a 12 bps edge

- **WHEN** a `PodSniper` intent uses `Venue::OnchainAtomicPool`, `OrderType::MevBundleAtomic`, `max_slippage_bps = 150`, and `expected_edge_bps = 12.0`, the sniper pod is enabled, and token safety is absent or passing
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`
- **THEN** the reported `min_bps` is strictly greater than `12.0`

#### Scenario: Low-cost maker order passes a 12 bps edge

- **WHEN** a `PodCarry` intent uses `Venue::BinancePerp`, `OrderType::PostOnlyMaker`, `max_slippage_bps = 2`, and `expected_edge_bps = 12.0`, and every other gate passes
- **THEN** `validate` returns `Ok(ApprovedOrder)`

#### Scenario: Taker order at the same edge is rejected

- **WHEN** a `PodCarry` intent uses `Venue::BinancePerp`, `OrderType::Market`, `max_slippage_bps = 2`, and `expected_edge_bps = 12.0`
- **THEN** `validate` returns `RiskRejection::InsufficientEdge` with `min_bps = 22.0`

#### Scenario: Venue identity changes the threshold for one edge

- **WHEN** two intents differ only in venue, one using `Venue::HyperliquidPerp` and one using `Venue::BinancePerp`, both `OrderType::PostOnlyMaker`, `max_slippage_bps = 2`, and `expected_edge_bps = 7.0`
- **THEN** the `HyperliquidPerp` intent is approved because its hurdle is `6.5`
- **THEN** the `BinancePerp` intent is rejected because its hurdle is `8.1`

### Requirement: Execution costs come from the single canonical cost model

The fee and spread terms MUST be taken from the same canonical cost model that `robotrader_exec_router::SmartExecutionRouter` applies; `robotrader-risk-gate` MUST NOT define, duplicate, or hardcode a second fee or spread table. The canonical per-side fee values are those returned by `SmartExecutionRouter::fee_bps_for(venue, order_type)`, and the round-trip fee used by the gate MUST equal the round-trip fee `SmartExecutionRouter::execute` charges for the same pair. The canonical spread values MUST equal the per-order-type values `SmartExecutionRouter::slippage_bps_for` applies: `0.5` bps for `PostOnlyMaker`, `2.0` bps for `Limit`, `8.0` bps for `Market`, and `0.6 × mev_priority_tip_bps` for `MevBundleAtomic`, where the tip is the value the unchanged tip formula attaches to the intent. The gate MUST obtain the spread term without constructing a throwaway `ApprovedOrder` and without allocating; a helper shared between the gate and `SmartExecutionRouter` satisfies this. A parity test MAY construct an `ApprovedOrder` to call `slippage_bps_for`.

#### Scenario: The round-trip fee matches the executor

- **WHEN** an intent uses `Venue::BinancePerp` and `OrderType::PostOnlyMaker`, whose canonical per-side fee is `1.8` bps
- **THEN** the gate's fee term is `3.6` bps
- **THEN** `SmartExecutionRouter::execute` charges `3.6` bps of round-trip fee for the same pair

#### Scenario: Every venue and order type reads the same fee table

- **WHEN** the gate's fee term and `SmartExecutionRouter::fee_bps_for` are evaluated for every supported `(Venue, OrderType)` pair
- **THEN** the per-side fee is identical for each pair
- **THEN** no fee value is declared inside `robotrader-risk-gate`

#### Scenario: The spread term matches the executor for all four order types

- **WHEN** the gate's spread helper and `SmartExecutionRouter::slippage_bps_for` are evaluated for `PostOnlyMaker`, `Limit`, `Market`, and `MevBundleAtomic` with `mev_priority_tip_bps = 10`
- **THEN** both sides produce `0.5`, `2.0`, `8.0`, and `6.0` bps respectively
- **THEN** no spread value is declared inside `robotrader-risk-gate`

#### Scenario: The spread component follows the order type

- **WHEN** two `Venue::BinancePerp` intents differ only in order type, one `OrderType::Limit` and one `OrderType::Market`, with the same `max_slippage_bps`
- **THEN** the `Market` hurdle is exactly `6.0` bps higher than the `Limit` hurdle

### Requirement: The hurdle buffer is configurable and fail-safe

`RiskLimits` MUST expose `min_edge_buffer_bps: f64`, whose default MUST be `2.0`. The field's Rustdoc MUST state that it is the minimum margin, in basis points, by which `expected_edge_bps` must exceed estimated execution cost. The effective buffer MUST be the greater of the configured value and `0.0`; a non-finite configured value MUST resolve to `0.0`. The former `min_edge_over_cost_bps` field MUST be removed so that no fixed floor remains.

#### Scenario: The default buffer is explicit

- **WHEN** `RiskLimits::default()` is constructed
- **THEN** `min_edge_buffer_bps` equals `2.0`
- **THEN** the field's Rustdoc documents the value and its meaning

#### Scenario: A custom buffer shifts the hurdle by exactly its value

- **WHEN** the same intent is validated with `min_edge_buffer_bps = 2.0` and then with `min_edge_buffer_bps = 5.0`
- **THEN** the computed hurdle is `3.0` bps higher in the second case
- **THEN** no other cost term changes

#### Scenario: A zero buffer still requires strict exceedance

- **WHEN** `min_edge_buffer_bps = 0.0` and `expected_edge_bps` equals the fee plus spread plus impact
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`

#### Scenario: A negative or non-finite buffer cannot weaken the hurdle

- **WHEN** `min_edge_buffer_bps` is `-5.0` or `NaN`
- **THEN** the effective buffer is `0.0`
- **THEN** the hurdle is no lower than fee plus spread plus impact

### Requirement: The hurdle boundary is strict

An order MUST be approved only when `expected_edge_bps > hurdle_bps`; equality MUST be rejected. The rule applies both at the cost boundary and at the cost-plus-buffer boundary.

#### Scenario: An edge below cost is rejected

- **WHEN** a `Venue::HyperliquidPerp`, `OrderType::PostOnlyMaker` intent has `max_slippage_bps = 2`, the default `2.0` bps buffer, and `expected_edge_bps = 4.4`
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`

#### Scenario: An edge exactly at cost is rejected

- **WHEN** the same intent has `expected_edge_bps = 4.5`, which equals fee plus spread plus impact
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`

#### Scenario: An edge exactly at cost plus buffer is rejected

- **WHEN** the same intent has `expected_edge_bps = 6.5`, which equals fee plus spread plus impact plus buffer
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`

#### Scenario: An edge above cost plus buffer is approved

- **WHEN** the same intent has `expected_edge_bps = 6.6`
- **THEN** `validate` returns `Ok(ApprovedOrder)`

### Requirement: Safety gates precede the edge hurdle

`HardRiskGate::validate` MUST evaluate its gates in this order: active kill switch, daily drawdown circuit breaker, effective-envelope resolution and pod enablement, slippage ceiling, on-chain token safety when `intent.token_safety` is present, edge hurdle, leverage clamp, fractional-Kelly sizing and zero-position rejection. The edge hurdle MUST NOT preempt the slippage ceiling or the token-safety check.

#### Scenario: The SCAM-SOL fixture is rejected as a rug, not by the hurdle

- **WHEN** the deterministic fixture's SCAM-SOL intent is validated: `Venue::OnchainDexAggregator`, `OrderType::MevBundleAtomic`, `expected_edge_bps = 81.0`, `max_slippage_bps = 65`, the on-chain alpha pod enabled with a cap of `80`, and a malicious `token_safety` payload
- **THEN** the slippage ceiling passes
- **THEN** `validate` returns `RiskRejection::OnChainRugCheckFailed`
- **THEN** the returned variant is not `InsufficientEdge`, even though `81.0` is below the computed hurdle of `87.8`

#### Scenario: Excessive slippage below the hurdle still wins

- **WHEN** a carry intent has `expected_edge_bps = 1.0` and `max_slippage_bps = 30` against a carry cap of `25`
- **THEN** `validate` returns `RiskRejection::ExcessiveSlippage { requested_bps: 30, max_bps: 25 }`
- **THEN** the returned variant is not `InsufficientEdge`

### Requirement: All other risk gates keep their current behavior

Each gate named here MUST keep its current decision rule and rejection variant for an intent that reaches it: active kill switch, daily drawdown circuit breaker, effective-envelope/TTL fallback, pod enablement, slippage ceiling, on-chain token safety, leverage clamp, fractional-Kelly sizing, zero-position rejection, and `validate_inference_refill`. The safety gates' precedence is defined by the preceding requirement. The leverage clamp, Kelly sizing, and zero-position rule MUST keep their current thresholds and MUST NOT gain a rejection variant.

#### Scenario: An already-active kill switch rejects first

- **WHEN** the gate's kill switch is active and a hurdle-failing intent is validated
- **THEN** `validate` returns `RiskRejection::KillSwitchActive`
- **THEN** the edge hurdle is not evaluated

#### Scenario: Drawdown still trips the kill switch

- **WHEN** the portfolio's daily drawdown is the result of a `-350.0` USD move on a `10_000.0` USD daily start
- **THEN** `validate` returns `RiskRejection::DailyDrawdownExceeded`
- **THEN** the gate's kill switch is active after the call

#### Scenario: A disabled pod is still rejected

- **WHEN** `PolicyEnvelope::safe_baseline` is active and the intent's pod is `PodId::PodSniper`, which the baseline disables
- **THEN** `validate` returns `RiskRejection::PodDisabled`

#### Scenario: An expired policy still falls back to the safe baseline

- **WHEN** the supplied envelope was issued at `T0` with `ttl_seconds = 900` and `validate` runs at `T0 + 900_001` with a sniper intent
- **THEN** the effective envelope is `safe_baseline_fallback`
- **THEN** `validate` returns `RiskRejection::PodDisabled` naming `safe_baseline_fallback`

#### Scenario: Leverage is still clamped to the hard ceiling

- **WHEN** a hurdle-passing intent requests `10.0x` leverage
- **THEN** the approved order's `clamped_leverage` equals `3.0`

#### Scenario: Zero or negative Kelly size is still rejected

- **WHEN** a hurdle-passing intent has `win_probability = 0.01`, `reward_risk_ratio = 0.1`, and `requested_leverage = 1.0`
- **THEN** the fractional-Kelly notional is zero
- **THEN** `validate` returns `RiskRejection::ZeroPositionSize`

#### Scenario: A valid inference refill is still accepted

- **WHEN** `validate_inference_refill(10.0, 1.20, 2.00, 5.0, 25.0)` is called
- **THEN** it returns `Ok(10.0)`

#### Scenario: An inference refill above the watermark is still rejected

- **WHEN** `validate_inference_refill(10.0, 4.50, 2.00, 5.0, 25.0)` is called
- **THEN** it returns `RiskRejection::InferenceRefillRejected`

### Requirement: Fixture baselines are regenerated from a real run

The benchmark fixture's event inputs, pod edge formulas, and declared `max_slippage_bps` values MUST remain unchanged by this change; the prior trade counts MUST NOT be restored by tuning edges or slippage. The deterministic backtest assertions MUST be re-derived from an actual run of `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest`, and the change evidence MUST include that command and its output. Every `[FIXTURE]` figure in `docs/PERFORMANCE_AND_COST_AUDIT.md` MUST be regenerated from the JSON summary produced by `cargo run --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id <leaf>` for the relevant leaf and MUST match it; a figure that can no longer be produced MUST be replaced or removed, not retained. The anti-rug assertion MUST remain: SCAM-SOL is rejected as `OnChainRugCheckFailed`. The at-most-four-pods-per-chain assertion MUST remain.

#### Scenario: Fixture inputs are unchanged

- **WHEN** the change diff is inspected
- **THEN** the benchmark event inputs, the pod edge formulas, and the declared `max_slippage_bps` values are unchanged
- **THEN** no edge or slippage value was tuned to preserve a prior trade count

#### Scenario: The deterministic baseline is re-derived from a run

- **WHEN** `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest` runs at the change tip
- **THEN** the Solana summary equals the recorded run output
- **THEN** for the fixture at this change the summary reports `4` trades, `3` rejections, and `2` pods
- **THEN** the SCAM-SOL rejection is `OnChainRugCheckFailed`

#### Scenario: Audit figures match the node JSON

- **WHEN** every `[FIXTURE]` number in `docs/PERFORMANCE_AND_COST_AUDIT.md` is compared with the JSON from `cargo run --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id <leaf>`
- **THEN** each number matches the JSON for its leaf
- **THEN** no pre-change figure (6 trades, 100% win rate, +$22.78, Sharpe 28.22) remains

#### Scenario: The 26-leaf assertions are re-derived

- **WHEN** the 26-leaf test runs
- **THEN** each per-leaf trade-count and PnL assertion equals that leaf's node JSON
- **THEN** the `<= 4` pod bound and the anti-rug assertion are unchanged

### Requirement: The hurdle computation preserves the hot-path budget

The hurdle computation MUST be synchronous and MUST NOT add any allocation site, logging, blocking I/O, sleeping, or unbounded loop to `HardRiskGate::validate`. The evidence is the diff review: a cold dev reviewer MUST confirm that no new allocation, logging, I/O, sleeping, or unbounded loop is introduced, and that the pre-existing effective-envelope and `ApprovedOrder` clones are unchanged. A `criterion` benchmark MUST measure `HardRiskGate::validate` on at least one approved intent and one rejected intent and MUST be runnable with `cargo bench -p robotrader-risk-gate`. The measured mean for the approved path MUST be at most `50` µs. The measured value and the command MUST be stated at every occurrence of the `<50µs` claim in `README.md` (currently lines 8, 42, 48, 75), `docs/architecture.md` (currently line 52), and `docs/PERFORMANCE_AND_COST_AUDIT.md` (currently lines 4, 37, 65, 79, 145).

#### Scenario: The benchmark runs and reports a per-iteration time

- **WHEN** `cargo bench -p robotrader-risk-gate` completes successfully
- **THEN** its output reports a mean time for `HardRiskGate::validate`

#### Scenario: The published measurement is within budget

- **WHEN** the benchmark evidence is attached to the change
- **THEN** the reported mean for the approved `validate` path is at most `50` µs

#### Scenario: Every claim occurrence carries the measured number

- **WHEN** the named lines in `README.md`, `docs/architecture.md`, and `docs/PERFORMANCE_AND_COST_AUDIT.md` are inspected
- **THEN** each `<50µs` occurrence states the measured mean and the benchmark command
- **THEN** no bare `<50µs` claim remains in those files

#### Scenario: The hot-path diff adds no allocating or blocking site

- **WHEN** a cold dev reviewer inspects the change diff for `engine-rs/crates/risk-gate/src/lib.rs`
- **THEN** the hurdle computation contains no new allocation, logging, I/O, sleeping, or unbounded loop
- **THEN** the pre-existing effective-envelope and `ApprovedOrder` clones are the only allocations on the path and are unchanged

### Requirement: An InsufficientEdge rejection reports the computed hurdle

When the edge check fails, `RiskRejection::InsufficientEdge` MUST report `edge_bps` equal to `intent.expected_edge_bps` and `min_bps` equal to the computed hurdle for that intent. The variant and its field names MUST remain unchanged.

#### Scenario: The rejection reports the venue-specific hurdle

- **WHEN** a `Venue::BinancePerp`, `OrderType::Market` intent with `max_slippage_bps = 2`, the default buffer, and `expected_edge_bps = 12.0` reaches the hurdle and is rejected
- **THEN** the rejection is `InsufficientEdge { edge_bps: 12.0, min_bps: 22.0 }`

### Requirement: Risk-gate dev-dependencies specify MSRV metadata

The `engine-rs/crates/risk-gate/Cargo.toml` manifest MUST document the `criterion = "0.8.2"` dev-dependency MSRV requirement (`1.86`) and the benchmark execution toolchain either via package `rust-version = "1.86"` or via an explicit comment preceding `[dev-dependencies]`.

#### Scenario: Criterion MSRV is explicitly documented in Cargo.toml

- **WHEN** `engine-rs/crates/risk-gate/Cargo.toml` is inspected
- **THEN** it explicitly states the MSRV requirement of `1.86` for the `criterion` dev-dependency

### Requirement: Per-intent hurdle rejections are asserted in the test suite

The test suite in `engine-rs/crates/backtest/src/lib.rs` (or `engine-rs/crates/risk-gate/src/lib.rs`) MUST assert the individual `RiskRejection::InsufficientEdge` rejections and hurdle values documented in the performance audit fixture summary. Specifically, it MUST assert that the JUP smart-money intent with `expected_edge_bps = 70.2` is rejected against `min_bps = 87.2`, that the AIX-SOL sniper intent with `expected_edge_bps = 95.0` is rejected against `min_bps = 151.4`, and that the `leaf-bitcoin` fixture execution produces exactly one hurdle rejection matching the fixture audit table.

#### Scenario: Solana smart-money hurdle rejection is verified

- **WHEN** the JUP smart-money fixture intent is evaluated by `HardRiskGate::validate`
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`
- **THEN** the reported `edge_bps` is `70.2` and `min_bps` is `87.2`

#### Scenario: Solana sniper hurdle rejection is verified

- **WHEN** the AIX-SOL sniper fixture intent is evaluated by `HardRiskGate::validate`
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`
- **THEN** the reported `edge_bps` is `95.0` and `min_bps` is `151.4`

#### Scenario: Leaf-bitcoin fixture hurdle rejection is verified

- **WHEN** the `leaf-bitcoin` fixture intents are evaluated through the test engine or `HardRiskGate::validate`
- **THEN** exactly one intent is rejected by `InsufficientEdge` matching the audit table

### Requirement: Performance and cost audit document is English-only

The document `docs/PERFORMANCE_AND_COST_AUDIT.md` MUST be written entirely in English. All French section titles, table labels, headers, and body prose paragraphs MUST be translated to English. All numeric `[FIXTURE]`, `[SIMULATED]`, and `[MEASURED]` figures, benchmark values, and table layouts MUST be preserved verbatim.

#### Scenario: Performance audit contains no residual French prose

- **WHEN** `docs/PERFORMANCE_AND_COST_AUDIT.md` is inspected
- **THEN** all section headers, table headers, and body sentences are in English
- **THEN** all `[FIXTURE]` numbers, Sharpe ratios, PnL values, and token counts are preserved without modification

### Requirement: Hot-path latency claims cite measured benchmark evidence across ADRs

Every occurrence of `<50µs` or `<50 µs` hot-path latency claims in `docs/adr/0001-hybrid-quant-agentic-architecture.md`, `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` MUST cite the measured mean (`0.244 µs`) and the benchmark command `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`. Across `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/PERFORMANCE_AND_COST_AUDIT.md`, and `docs/adr/0001..0003`, zero bare `<50µs` or `<50 µs` claims SHALL remain.

#### Scenario: Architecture ADRs cite benchmark command and measured latency

- **WHEN** `docs/adr/0001-hybrid-quant-agentic-architecture.md`, `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` are inspected
- **THEN** every hot-path latency claim states the measured mean of `0.244 µs` and the benchmark command `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`

#### Scenario: Zero bare 50µs claims across documentation corpus

- **WHEN** a regex search for `< ?50 ?[uµ]s` without measured benchmark citation is executed over `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/PERFORMANCE_AND_COST_AUDIT.md`, and `docs/adr/*.md`
- **THEN** zero unannotated bare claims are found


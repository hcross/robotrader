## ADDED Requirements

### Requirement: The edge hurdle is computed from execution cost

`HardRiskGate::validate` MUST compute a per-intent execution-cost hurdle and MUST reject the intent unless `intent.expected_edge_bps` is strictly greater than that hurdle. The hurdle MUST equal `round_trip_fee_bps + spread_bps + expected_impact_bps + effective_buffer_bps`, where:

- `round_trip_fee_bps` is twice the canonical per-side fee for `intent.venue` and `intent.order_type`;
- `spread_bps` is the canonical spread component for `intent.order_type`, as defined by the canonical-cost requirement below;
- `expected_impact_bps` is `intent.max_slippage_bps` converted to `f64`;
- `effective_buffer_bps` is defined by the buffer requirement below.

The gate MUST read `intent.venue`, `intent.order_type`, and `intent.max_slippage_bps`. A fixed threshold MUST NOT replace the computed hurdle. The computation MUST be a pure function of the intent and `RiskLimits`; it MUST NOT read another leaf's, chain's, or venue's state.

#### Scenario: On-chain atomic pool rejects a 12 bps edge

- **WHEN** a `PodSniper` intent uses `Venue::OnchainAtomicPool`, `OrderType::MevBundleAtomic`, `max_slippage_bps = 150`, and `expected_edge_bps = 12.0`, and the sniper pod is enabled
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

The fee and spread terms MUST be taken from the same canonical cost model that `robotrader_exec_router::SmartExecutionRouter` applies; `robotrader-risk-gate` MUST NOT define, duplicate, or hardcode a second fee or spread table. The canonical per-side fee values are those returned by `SmartExecutionRouter::fee_bps_for(venue, order_type)`, and the round-trip fee used by the gate MUST equal the round-trip fee `SmartExecutionRouter::execute` charges for the same pair. The canonical spread values MUST equal the per-order-type values `SmartExecutionRouter::slippage_bps_for` applies: `0.5` bps for `PostOnlyMaker`, `2.0` bps for `Limit`, `8.0` bps for `Market`, and `0.6 × mev_priority_tip_bps` for `MevBundleAtomic`, where the tip is the value the unchanged tip formula attaches to the intent.

#### Scenario: The round-trip fee matches the executor

- **WHEN** an intent uses `Venue::BinancePerp` and `OrderType::PostOnlyMaker`, whose canonical per-side fee is `1.8` bps
- **THEN** the gate's fee term is `3.6` bps
- **THEN** `SmartExecutionRouter::execute` charges `3.6` bps of round-trip fee for the same pair

#### Scenario: Every venue and order type reads the same table

- **WHEN** the gate's fee term and `SmartExecutionRouter::fee_bps_for` are evaluated for every supported `(Venue, OrderType)` pair
- **THEN** the per-side fee is identical for each pair
- **THEN** no fee value is declared inside `robotrader-risk-gate`

#### Scenario: The spread component follows the order type

- **WHEN** two intents differ only in order type, one `OrderType::Limit` and one `OrderType::Market`, with the same venue and the same `max_slippage_bps`
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

### Requirement: The hurdle computation preserves the hot-path budget

The hurdle computation MUST be synchronous and MUST NOT add heap allocation, logging, blocking I/O, sleeping, or unbounded work to `HardRiskGate::validate`. The pre-existing effective-envelope clone and `ApprovedOrder` intent clone are outside this change and MUST NOT be expanded. A `criterion` benchmark MUST measure `HardRiskGate::validate` on at least one approved intent and one rejected intent and MUST be runnable with `cargo bench -p robotrader-risk-gate`. The measured mean for the approved path MUST be at most `50` µs, and the measured value plus the command MUST be published in the change evidence and stated where the `<50µs` claim appears in `README.md` and `docs/architecture.md`.

#### Scenario: The benchmark runs and reports a per-iteration time

- **WHEN** `cargo bench -p robotrader-risk-gate` completes successfully
- **THEN** its output reports a mean time for `HardRiskGate::validate`

#### Scenario: The published measurement is within budget

- **WHEN** the benchmark evidence is attached to the change
- **THEN** the reported mean for the approved `validate` path is at most `50` µs
- **THEN** the command and the measured number are present in the evidence and in the two documents

#### Scenario: The gate path adds no blocking behavior

- **WHEN** `validate` executes the hurdle check
- **THEN** it performs no logging, no I/O, no sleeping, and no allocation inside the hurdle computation

### Requirement: All other risk gates keep their current behavior

The change MUST NOT alter the outcome or precedence of the kill switch, the daily drawdown circuit breaker, the pod-enabled/TTL-fallback check, the slippage ceiling, the on-chain token-safety check, the leverage clamp, fractional-Kelly sizing, the zero-position rejection, or `validate_inference_refill`. For an intent rejected by any of those gates, `validate` MUST return the same `RiskRejection` variant it returns today.

#### Scenario: Drawdown still trips the kill switch

- **WHEN** the portfolio's daily drawdown is `3.5%` against a `3.0%` limit
- **THEN** `validate` returns `RiskRejection::DailyDrawdownExceeded`
- **THEN** the gate's kill switch is active after the call

#### Scenario: A disabled pod is still rejected

- **WHEN** `PolicyEnvelope::safe_baseline` is active and the intent's pod is `PodId::PodSniper`, which the baseline disables
- **THEN** `validate` returns `RiskRejection::PodDisabled`

#### Scenario: An expired policy still falls back to the safe baseline

- **WHEN** the supplied envelope was issued at `T0` with `ttl_seconds = 900` and `validate` runs at `T0 + 900_001` with a sniper intent
- **THEN** the effective envelope is `safe_baseline_fallback`
- **THEN** `validate` returns `RiskRejection::PodDisabled` naming `safe_baseline_fallback`

#### Scenario: Excessive slippage is still rejected with the same variant

- **WHEN** a carry intent has `expected_edge_bps = 200.0`, `max_slippage_bps = 30`, and the carry cap is `25`
- **THEN** the intent passes the hurdle
- **THEN** `validate` returns `RiskRejection::ExcessiveSlippage { requested_bps: 30, max_bps: 25 }`

#### Scenario: Token safety still rejects a malicious token

- **WHEN** an enabled on-chain intent has a hurdle-passing edge and a `token_safety` payload whose `supply_mint_immutable` is false
- **THEN** `validate` returns `RiskRejection::OnChainRugCheckFailed`

#### Scenario: Leverage is still clamped to the hard ceiling

- **WHEN** a hurdle-passing intent requests `10.0x` leverage
- **THEN** the approved order's `clamped_leverage` equals `3.0`

### Requirement: An InsufficientEdge rejection reports the computed hurdle

When the edge check fails, `RiskRejection::InsufficientEdge` MUST report `edge_bps` equal to `intent.expected_edge_bps` and `min_bps` equal to the computed hurdle for that intent. The variant and its field names MUST remain unchanged.

#### Scenario: The rejection reports the venue-specific hurdle

- **WHEN** a `Venue::BinancePerp`, `OrderType::Market` intent with `max_slippage_bps = 2`, the default buffer, and `expected_edge_bps = 12.0` is rejected
- **THEN** the rejection is `InsufficientEdge { edge_bps: 12.0, min_bps: 22.0 }`

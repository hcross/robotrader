# risk-hurdle Specification

## MODIFIED Requirements

### Requirement: Safety gates precede the edge hurdle

`HardRiskGate::validate` MUST evaluate its gates in this canonical order: active kill switch, daily drawdown circuit breaker, effective-envelope resolution and pod enablement, per-`(pod_id, symbol)` order rate-limit cooldown, slippage ceiling, on-chain token safety when `intent.token_safety` is present, execution-cost edge hurdle, leverage clamp, fractional-Kelly sizing (clamped by single-position cap `max_single_position_pct * equity`) and zero-position rejection, aggregate exposure caps (asset exposure -> pod exposure -> gross exposure), and bounded MEV priority tip attachment. The edge hurdle MUST NOT preempt the slippage ceiling, token-safety check, or rate-limit cooldown check.

#### Scenario: The SCAM-SOL fixture is rejected as a rug, not by the hurdle

- **WHEN** the deterministic fixture's SCAM-SOL intent is validated: `Venue::OnchainDexAggregator`, `OrderType::MevBundleAtomic`, `expected_edge_bps = 81.0`, `max_slippage_bps = 65`, the on-chain alpha pod enabled with a cap of `80`, and a malicious `token_safety` payload
- **THEN** the slippage ceiling passes
- **THEN** `validate` returns `RiskRejection::OnChainRugCheckFailed`
- **THEN** the returned variant is not `InsufficientEdge`, even though `81.0` is below the computed hurdle of `87.8`

#### Scenario: Excessive slippage below the hurdle still wins

- **WHEN** a carry intent has `expected_edge_bps = 1.0` and `max_slippage_bps = 30` against a carry cap of `25`
- **THEN** `validate` returns `RiskRejection::ExcessiveSlippage { requested_bps: 30, max_bps: 25 }`
- **THEN** the returned variant is not `InsufficientEdge`

#### Scenario: Rate limit cooldown check precedes execution cost hurdle

- **WHEN** an intent is evaluated within `min_order_cooldown_ms` of a prior order on the same pod and symbol, with `expected_edge_bps` below the cost hurdle
- **THEN** `validate` returns `RiskRejection::OrderRateLimited`
- **THEN** the returned variant is not `InsufficientEdge`

### Requirement: All other risk gates keep their current behavior

Each gate named here MUST keep its current decision rule and rejection variant for an intent that reaches it: active kill switch, daily drawdown circuit breaker, effective-envelope/TTL fallback, pod enablement, slippage ceiling, on-chain token safety, leverage clamp ceiling, zero-position rejection, and `validate_inference_refill`. The safety gates' precedence is defined by the preceding requirement. The leverage clamp and zero-position rule MUST keep their current thresholds and MUST NOT regress. New rejection variants `OrderRateLimited`, `AssetExposureExceeded`, `PodExposureExceeded`, and `GrossExposureExceeded` are evaluated at their designated pipeline positions without altering the behavior of pre-existing gates.

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

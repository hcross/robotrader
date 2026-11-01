# risk-exposure-caps Specification

## ADDED Requirements

### Requirement: Asset exposure cap enforcement

`HardRiskGate::validate` MUST enforce a maximum asset exposure ceiling on all non-stablecoin asset orders. The gate MUST compute the prospective asset exposure as the sum of existing exposure `portfolio.asset_exposures_usd` for `intent.symbol` and the order's approved notional `approved_notional_usd`. If the prospective asset exposure exceeds `portfolio.current_equity_usd * self.limits.max_asset_exposure_pct`, `validate` MUST reject the intent with `RiskRejection::AssetExposureExceeded { asset, current_usd, requested_usd, max_usd }`. The default value of `max_asset_exposure_pct` in `RiskLimits` MUST be `0.15` (15% of equity).

#### Scenario: Order exceeding asset exposure cap is rejected

- **WHEN** an order with notional `1_600.0` USD on symbol `SOL-USDT` is validated against equity of `10_000.0` USD with zero prior exposure and `max_asset_exposure_pct = 0.15`
- **THEN** `validate` returns `RiskRejection::AssetExposureExceeded`
- **THEN** the rejection reports `current_usd = 0.0`, `requested_usd = 1600.0`, and `max_usd = 1500.0`

#### Scenario: Existing asset exposure accumulates with new order

- **WHEN** an order with notional `600.0` USD on symbol `SOL-USDT` is validated against equity of `10_000.0` USD with existing exposure of `1_000.0` USD on `SOL-USDT` and `max_asset_exposure_pct = 0.15`
- **THEN** `validate` returns `RiskRejection::AssetExposureExceeded`
- **THEN** the rejection reports `current_usd = 1000.0`, `requested_usd = 600.0`, and `max_usd = 1500.0`

#### Scenario: Order within asset exposure cap is approved

- **WHEN** an order with notional `400.0` USD on symbol `SOL-USDT` is validated against equity of `10_000.0` USD with existing exposure of `1_000.0` USD on `SOL-USDT` and all other gates pass
- **THEN** `validate` returns `Ok(ApprovedOrder)`

### Requirement: Pod exposure cap enforcement

`HardRiskGate::validate` MUST enforce a maximum capital exposure ceiling for each strategy pod. The gate MUST compute the prospective pod exposure as the sum of existing exposure `portfolio.pod_exposures_usd` for `intent.pod_id` and the order's approved notional `approved_notional_usd`. If the prospective pod exposure exceeds `portfolio.current_equity_usd * self.limits.max_pod_exposure_pct`, `validate` MUST reject the intent with `RiskRejection::PodExposureExceeded { pod_id, current_usd, requested_usd, max_usd }`. The default value of `max_pod_exposure_pct` in `RiskLimits` MUST be `0.40` (40% of equity).

#### Scenario: Order exceeding pod exposure cap is rejected

- **WHEN** a `PodCarry` intent with approved notional `4_200.0` USD is validated against equity of `10_000.0` USD with zero prior exposure and `max_pod_exposure_pct = 0.40`
- **THEN** `validate` returns `RiskRejection::PodExposureExceeded`
- **THEN** the rejection reports `current_usd = 0.0`, `requested_usd = 4200.0`, and `max_usd = 4000.0`

#### Scenario: Prior pod exposure prevents subsequent order exceeding cap

- **WHEN** a `PodMomentum` intent with approved notional `1_500.0` USD is validated against equity of `10_000.0` USD with existing exposure of `3_000.0` USD in `pod_momentum` and `max_pod_exposure_pct = 0.40`
- **THEN** `validate` returns `RiskRejection::PodExposureExceeded`
- **THEN** the rejection reports `current_usd = 3000.0`, `requested_usd = 1500.0`, and `max_usd = 4000.0`

#### Scenario: Order within pod exposure cap is approved

- **WHEN** a `PodMomentum` intent with approved notional `800.0` USD is validated against equity of `10_000.0` USD with existing exposure of `3_000.0` USD in `pod_momentum` and all other gates pass
- **THEN** `validate` returns `Ok(ApprovedOrder)`

### Requirement: Gross portfolio exposure cap enforcement

`HardRiskGate::validate` MUST enforce a maximum aggregate gross exposure ceiling across all assets and positions. The gate MUST compute the prospective gross exposure as the sum of current portfolio gross exposure and the order's approved notional `approved_notional_usd`. If `portfolio.gross_exposure_usd` is zero or omitted, the current gross exposure MUST be computed as the sum of absolute values in `portfolio.asset_exposures_usd`. If the prospective gross exposure exceeds `portfolio.current_equity_usd * self.limits.max_gross_exposure_pct`, `validate` MUST reject the intent with `RiskRejection::GrossExposureExceeded { current_gross_usd, requested_usd, max_gross_usd }`. The default value of `max_gross_exposure_pct` in `RiskLimits` MUST be `1.50` (150% of equity).

#### Scenario: Order exceeding gross portfolio exposure cap is rejected

- **WHEN** an order with notional `2_000.0` USD is validated against equity of `10_000.0` USD when current gross exposure is `14_000.0` USD and `max_gross_exposure_pct = 1.50`
- **THEN** `validate` returns `RiskRejection::GrossExposureExceeded`
- **THEN** the rejection reports `current_gross_usd = 14000.0`, `requested_usd = 2000.0`, and `max_gross_usd = 15000.0`

#### Scenario: Short and long positions both contribute to gross exposure

- **WHEN** a portfolio has `+6_000.0` USD in BTC and `-8_000.0` USD in ETH, yielding `14_000.0` USD gross exposure, and an intent requests `1_500.0` USD with equity `10_000.0` USD and `max_gross_exposure_pct = 1.50`
- **THEN** `validate` evaluates prospective gross exposure as `15_500.0` USD
- **THEN** `validate` returns `RiskRejection::GrossExposureExceeded`

#### Scenario: Order within gross exposure cap is approved

- **WHEN** an order with notional `800.0` USD is validated against equity of `10_000.0` USD with current gross exposure of `14_000.0` USD and all other gates pass
- **THEN** `validate` returns `Ok(ApprovedOrder)`

### Requirement: Single-position hard cap decoupling from leverage

`HardRiskGate::compute_kelly_notional` SHALL clamp the desired position notional against a hard ceiling equal to `portfolio.current_equity_usd * self.limits.max_single_position_pct`. The single-position hard cap calculation MUST NOT multiply equity by `clamped_leverage`. When an intent requests leverage greater than 1.0, the maximum permitted notional for the single trade MUST remain strictly bounded by `max_single_position_pct * equity`. In addition, if accumulated asset exposure plus the new order notional exceeds `max_single_position_pct * equity`, the order MUST NOT bypass single-position concentration limits.

#### Scenario: High leverage does not multiply single position notional cap

- **WHEN** `compute_kelly_notional` evaluates an intent with equity `10_000.0` USD, `max_single_position_pct = 0.15`, and `clamped_leverage = 3.0`
- **THEN** the returned notional is at most `1_500.0` USD
- **THEN** the computed ceiling does not evaluate to `4_500.0` USD

#### Scenario: Single position notional respects 15% equity ceiling at 3x leverage

- **WHEN** an intent with large Kelly sizing fraction requests `3.0x` leverage against `10_000.0` USD equity
- **THEN** `compute_kelly_notional` returns exactly `1_500.0` USD

#### Scenario: Repeated orders on same symbol cannot exceed single position limit

- **WHEN** an asset already holds `1_200.0` USD exposure against `10_000.0` USD equity with `max_single_position_pct = 0.15` and a new order requests `400.0` USD
- **THEN** `validate` rejects the order because the accumulated asset notional would reach `1_600.0` USD exceeding the `1_500.0` USD ceiling

### Requirement: Per-pod-symbol order rate-limit cooldown

`HardRiskGate::validate` MUST enforce a minimum time cooldown `min_order_cooldown_ms` between consecutive orders for the same `(pod_id, symbol)` pair. When `min_order_cooldown_ms > 0`, the gate MUST check `portfolio.last_order_ts_ms` for key `"{pod_id}:{symbol}"`. If an order was previously recorded at `last_ts` and `now_ms < last_ts + min_order_cooldown_ms`, `validate` MUST reject the intent with `RiskRejection::OrderRateLimited { pod_id, symbol, elapsed_ms, min_cooldown_ms }`. When `min_order_cooldown_ms == 0` or no prior order timestamp exists, the rate limit gate MUST pass.

#### Scenario: Order within cooldown period is rejected

- **WHEN** an intent for `(pod_momentum, SOL-USDT)` is validated at `now_ms = 1_000_050` with prior order timestamp `1_000_000` and `min_order_cooldown_ms = 100`
- **THEN** `validate` returns `RiskRejection::OrderRateLimited`
- **THEN** the rejection reports `pod_id = "pod_momentum"`, `symbol = "SOL-USDT"`, `elapsed_ms = 50`, and `min_cooldown_ms = 100`

#### Scenario: Order after cooldown period elapsed is approved

- **WHEN** an intent for `(pod_momentum, SOL-USDT)` is validated at `now_ms = 1_000_150` with prior order timestamp `1_000_000` and `min_order_cooldown_ms = 100` and all other gates pass
- **THEN** `validate` returns `Ok(ApprovedOrder)`

#### Scenario: Cooldown is isolated per pod and symbol pair

- **WHEN** an intent for `(pod_carry, SOL-USDT)` is validated at `now_ms = 1_000_050` while `(pod_momentum, SOL-USDT)` has prior timestamp `1_000_000` and `min_order_cooldown_ms = 100`
- **THEN** the rate limit check passes because pod IDs differ

#### Scenario: Zero cooldown disables rate limiting

- **WHEN** `min_order_cooldown_ms = 0` and two consecutive orders for the same pod and symbol arrive at the exact same `now_ms`
- **THEN** the rate limit check does not reject either order

### Requirement: Bounded MEV priority tip

`HardRiskGate::validate` MUST compute `mev_priority_tip_bps` bounded by `self.limits.max_mev_tip_bps` and the effective slippage ceiling. The tip calculation MUST NOT allow an arbitrarily large `expected_edge_bps` to scale the priority tip beyond `max_mev_tip_bps`. The tip MUST be computed as `((intent.expected_edge_bps * 0.10) as u32).clamp(2, tip_ceiling)`, where `tip_ceiling = self.limits.max_mev_tip_bps.min(effective_slippage_cap)`. The default value of `max_mev_tip_bps` in `RiskLimits` MUST be `25`.

#### Scenario: Large expected edge cannot exceed max MEV tip cap

- **WHEN** an intent declares `expected_edge_bps = 500.0` with `max_mev_tip_bps = 25` and `max_slippage_bps = 150`
- **THEN** `mev_priority_tip_bps` in `ApprovedOrder` equals `25`
- **THEN** the tip does not evaluate to `50` bps

#### Scenario: MEV tip respects tighter slippage ceiling

- **WHEN** an intent declares `expected_edge_bps = 200.0` with `max_mev_tip_bps = 25` and effective slippage cap is `15` bps
- **THEN** `mev_priority_tip_bps` in `ApprovedOrder` equals `15`

#### Scenario: Moderate edge derives proportional tip within bounds

- **WHEN** an intent declares `expected_edge_bps = 80.0` with `max_mev_tip_bps = 25` and effective slippage cap is `50` bps
- **THEN** `mev_priority_tip_bps` in `ApprovedOrder` equals `8`

### Requirement: PortfolioState schema synchronization and backward compatibility

`PortfolioState` in `robotrader_common` and `backend.core.schemas` MUST expose `asset_exposures_usd` (mapping symbol to f64), `pod_exposures_usd` (mapping pod key to f64), `gross_exposure_usd` (f64), and `last_order_ts_ms` (mapping `"{pod_id}:{symbol}"` to u64 timestamp). All new fields in Rust MUST use `#[serde(default)]` and in Python MUST have default empty containers or zero values. Existing payloads that omit these fields MUST deserialize successfully into valid default states.

#### Scenario: Legacy JSON payload omitting exposure and timestamp fields decodes successfully

- **WHEN** a JSON representation of `PortfolioState` omitting `gross_exposure_usd` and `last_order_ts_ms` is deserialized in Rust
- **THEN** deserialization succeeds without error
- **THEN** `gross_exposure_usd` defaults to `0.0` and `last_order_ts_ms` defaults to an empty map

#### Scenario: Serializing and deserializing preserves exposure maps and timestamps

- **WHEN** a `PortfolioState` populated with non-empty `asset_exposures_usd`, `pod_exposures_usd`, `gross_exposure_usd = 5000.0`, and `last_order_ts_ms` is serialized and deserialized
- **THEN** all four fields retain their exact keys and values

#### Scenario: Python PortfolioState schema mirrors Rust field names and types

- **WHEN** `backend.core.schemas.PortfolioState` is instantiated and converted via `to_dict()`
- **THEN** the dictionary contains keys `initial_equity_usd`, `current_equity_usd`, `high_water_mark_usd`, `daily_start_equity_usd`, `asset_exposures_usd`, `pod_exposures_usd`, `gross_exposure_usd`, and `last_order_ts_ms`

### Requirement: Risk gate hot-path purity and latency budget

The evaluation of exposure caps, rate-limit cooldown, and bounded MEV tip inside `HardRiskGate::validate` MUST be synchronous and MUST NOT perform heap allocations, unbounded loops, logging, or blocking I/O. The measured execution latency of `HardRiskGate::validate` across approved and rejected paths MUST remain under the `50 µs` budget, maintaining compliance with the Criterion benchmark suite.

#### Scenario: Exposure caps and rate limit evaluation introduce no allocation on hot path

- **WHEN** a reviewer inspects the changes to `HardRiskGate::validate` in `engine-rs/crates/risk-gate/src/lib.rs`
- **THEN** no new heap allocation, logging macro, network call, or unbounded loop is present on the validation path

#### Scenario: Benchmark execution confirms validate latency stays under 50 microseconds

- **WHEN** `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` is executed
- **THEN** the measured mean latency for `HardRiskGate::validate` remains below `50 µs`

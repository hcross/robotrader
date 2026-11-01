# risk-exposure-caps Specification

## ADDED Requirements

### Requirement: Asset exposure cap enforcement

`HardRiskGate::validate` MUST enforce a maximum asset exposure ceiling on all non-stablecoin asset orders. The gate MUST compute the prospective asset exposure using absolute values as `existing_asset_usd + approved_notional_usd`, where `existing_asset_usd = portfolio.asset_exposures_usd.get(&intent.symbol).copied().unwrap_or(0.0).abs()`. If the prospective asset exposure exceeds `portfolio.current_equity_usd * self.limits.max_asset_exposure_pct`, `validate` MUST reject the intent with `RiskRejection::AssetExposureExceeded { symbol: intent.symbol.clone(), current_usd: existing_asset_usd, requested_usd: approved_notional_usd, max_usd: portfolio.current_equity_usd * self.limits.max_asset_exposure_pct }`.

#### Scenario: Order exceeding asset exposure cap is rejected

- **WHEN** an order with notional `1_600.0` USD on symbol `SOL-USDT` is validated against equity of `10_000.0` USD with zero prior exposure and `max_asset_exposure_pct = 0.15`
- **THEN** `validate` returns `RiskRejection::AssetExposureExceeded`
- **THEN** the rejection reports `symbol = "SOL-USDT"`, `current_usd = 0.0`, `requested_usd = 1600.0`, and `max_usd = 1500.0`

#### Scenario: Existing short asset exposure accumulates via absolute value with new order

- **WHEN** an asset holds existing short exposure of `-1_000.0` USD on `SOL-USDT` and an order requests notional `600.0` USD against `10_000.0` USD equity with `max_asset_exposure_pct = 0.15`
- **THEN** the gate evaluates existing exposure as `1_000.0` USD via absolute value and prospective exposure as `1_600.0` USD
- **THEN** `validate` returns `RiskRejection::AssetExposureExceeded` with `symbol = "SOL-USDT"`, `current_usd = 1000.0`, `requested_usd = 600.0`, and `max_usd = 1500.0`

#### Scenario: Order within asset exposure cap is approved

- **WHEN** an order with notional `400.0` USD on symbol `SOL-USDT` is validated against equity of `10_000.0` USD with existing exposure of `1_000.0` USD on `SOL-USDT` and all other gates pass
- **THEN** `validate` returns `Ok(ApprovedOrder)`

### Requirement: Pod exposure cap enforcement

`HardRiskGate::validate` MUST enforce a maximum capital exposure ceiling for each strategy pod. The gate MUST compute the prospective pod exposure using absolute values as `existing_pod_usd + approved_notional_usd`, where `existing_pod_usd = portfolio.pod_exposures_usd.get(pod_key).copied().unwrap_or(0.0).abs()`. If the prospective pod exposure exceeds `portfolio.current_equity_usd * self.limits.max_pod_exposure_pct`, `validate` MUST reject the intent with `RiskRejection::PodExposureExceeded { pod_id: pod_key.to_string(), current_usd: existing_pod_usd, requested_usd: approved_notional_usd, max_usd: portfolio.current_equity_usd * self.limits.max_pod_exposure_pct }`.

#### Scenario: Order exceeding pod exposure cap is rejected

- **WHEN** a `PodCarry` intent with approved notional `4_200.0` USD is validated against equity of `10_000.0` USD with zero prior exposure and `max_pod_exposure_pct = 0.40`
- **THEN** `validate` returns `RiskRejection::PodExposureExceeded`
- **THEN** the rejection reports `pod_id = "pod_carry"`, `current_usd = 0.0`, `requested_usd = 4200.0`, and `max_usd = 4000.0`

#### Scenario: Prior pod exposure prevents subsequent order exceeding cap

- **WHEN** a `PodMomentum` intent with approved notional `1_500.0` USD is validated against equity of `10_000.0` USD with existing exposure of `3_000.0` USD in `pod_momentum` and `max_pod_exposure_pct = 0.40`
- **THEN** `validate` returns `RiskRejection::PodExposureExceeded`
- **THEN** the rejection reports `pod_id = "pod_momentum"`, `current_usd = 3000.0`, `requested_usd = 1500.0`, and `max_usd = 4000.0`

#### Scenario: Order within pod exposure cap is approved

- **WHEN** a `PodMomentum` intent with approved notional `800.0` USD is validated against equity of `10_000.0` USD with existing exposure of `3_000.0` USD in `pod_momentum` and all other gates pass
- **THEN** `validate` returns `Ok(ApprovedOrder)`

### Requirement: Gross portfolio exposure cap enforcement

`HardRiskGate::validate` MUST enforce a maximum aggregate gross exposure ceiling across all assets and positions. The gate MUST compute the prospective gross exposure as `current_gross_usd + approved_notional_usd`. If `portfolio.gross_exposure_usd > 0.0`, `current_gross_usd` MUST be `portfolio.gross_exposure_usd`; otherwise, `current_gross_usd` MUST be computed as the sum of absolute values in `portfolio.asset_exposures_usd.values().map(|v| v.abs()).sum()`. If the prospective gross exposure exceeds `portfolio.current_equity_usd * self.limits.max_gross_exposure_pct`, `validate` MUST reject the intent with `RiskRejection::GrossExposureExceeded { current_gross_usd, requested_usd: approved_notional_usd, max_gross_usd: portfolio.current_equity_usd * self.limits.max_gross_exposure_pct }`.

#### Scenario: Order exceeding gross portfolio exposure cap is rejected

- **WHEN** an order with notional `2_000.0` USD is validated against equity of `10_000.0` USD when current gross exposure is `14_000.0` USD and `max_gross_exposure_pct = 1.50`
- **THEN** `validate` returns `RiskRejection::GrossExposureExceeded`
- **THEN** the rejection reports `current_gross_usd = 14000.0`, `requested_usd = 2000.0`, and `max_gross_usd = 15000.0`

#### Scenario: Short and long positions both contribute to gross exposure

- **WHEN** a portfolio has `+6_000.0` USD in BTC and `-8_000.0` USD in ETH, yielding `14_000.0` USD gross exposure via sum of absolute values, and an intent requests `1_500.0` USD with equity `10_000.0` USD and `max_gross_exposure_pct = 1.50`
- **THEN** `validate` evaluates prospective gross exposure as `15_500.0` USD
- **THEN** `validate` returns `RiskRejection::GrossExposureExceeded`

#### Scenario: Order within gross exposure cap is approved

- **WHEN** an order with notional `800.0` USD is validated against equity of `10_000.0` USD with current gross exposure of `14_000.0` USD and all other gates pass
- **THEN** `validate` returns `Ok(ApprovedOrder)`

### Requirement: Single-position hard cap decoupling from leverage

`HardRiskGate::compute_kelly_notional` SHALL clamp the desired position notional against a hard ceiling equal to `portfolio.current_equity_usd * self.limits.max_single_position_pct`. The single-position hard cap calculation MUST NOT multiply equity by `clamped_leverage`. When an intent requests leverage greater than 1.0, the maximum permitted notional for the single trade MUST remain strictly bounded by `max_single_position_pct * equity`.

#### Scenario: High leverage does not multiply single position notional cap

- **WHEN** `compute_kelly_notional` evaluates an intent with equity `10_000.0` USD, `max_single_position_pct = 0.15`, and `clamped_leverage = 3.0`
- **THEN** the returned notional is at most `1_500.0` USD
- **THEN** the computed ceiling does not evaluate to `4_500.0` USD

#### Scenario: Single position notional respects 15% equity ceiling at 3x leverage

- **WHEN** an intent with large Kelly sizing fraction requests `3.0x` leverage against `10_000.0` USD equity
- **THEN** `compute_kelly_notional` returns exactly `1_500.0` USD

#### Scenario: Fractional Kelly sizing clamps notional to single position cap

- **WHEN** `compute_kelly_notional` calculates a desired notional of `2_200.0` USD for an intent with `10_000.0` USD equity and `max_single_position_pct = 0.15`
- **THEN** the returned notional is clamped to `1_500.0` USD

### Requirement: Per-pod-symbol order rate-limit cooldown

`HardRiskGate::validate` MUST enforce a minimum time cooldown `self.limits.min_order_cooldown_ms` between consecutive orders for the same `(pod_id, symbol)` pair. When `self.limits.min_order_cooldown_ms > 0`, the gate MUST check `portfolio.last_order_ts_ms` for key `"{pod_id}:{symbol}"`. If an order was previously recorded at `last_ts` and `now_ms < last_ts + self.limits.min_order_cooldown_ms`, `validate` MUST reject the intent with `RiskRejection::OrderRateLimited { pod_id: intent.pod_id.as_str().to_string(), symbol: intent.symbol.clone(), elapsed_ms: now_ms.saturating_sub(last_ts), min_cooldown_ms: self.limits.min_order_cooldown_ms }`. When `self.limits.min_order_cooldown_ms == 0` or no prior order timestamp exists, the rate limit gate MUST pass.

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

`HardRiskGate::validate` MUST compute `mev_priority_tip_bps` bounded by `self.limits.max_mev_tip_bps` and the effective slippage ceiling. To prevent panic in Rust std when `tip_ceiling < 2`, the gate MUST define `tip_ceiling = self.limits.max_mev_tip_bps.min(effective_slippage_cap)` and `tip_floor = 2u32.min(tip_ceiling)`, computing `mev_priority_tip_bps = ((intent.expected_edge_bps * 0.10) as u32).clamp(tip_floor, tip_ceiling)`. When `tip_ceiling < 2`, `tip_floor` MUST equal `tip_ceiling`, guaranteeing safe clamp evaluation without panicking. The tip calculation MUST NOT allow an arbitrarily large `expected_edge_bps` to scale the priority tip beyond `tip_ceiling`.

#### Scenario: Large expected edge cannot exceed max MEV tip cap

- **WHEN** an intent declares `expected_edge_bps = 500.0` with `max_mev_tip_bps = 50` and `max_slippage_bps = 150`
- **THEN** `mev_priority_tip_bps` in `ApprovedOrder` equals `50`
- **THEN** the tip does not evaluate to `50` bps beyond the ceiling

#### Scenario: MEV tip respects tighter slippage ceiling

- **WHEN** an intent declares `expected_edge_bps = 200.0` with `max_mev_tip_bps = 50` and effective slippage cap is `15` bps
- **THEN** `mev_priority_tip_bps` in `ApprovedOrder` equals `15`

#### Scenario: Tight slippage ceiling below 2 clamps safely without panicking

- **WHEN** an intent has effective slippage cap of `1` bps and `max_mev_tip_bps = 50`
- **THEN** the gate derives `tip_ceiling = 1` and `tip_floor = 1`
- **THEN** `mev_priority_tip_bps` evaluates to `1` without panicking in `u32::clamp`

#### Scenario: Moderate edge derives proportional tip within bounds

- **WHEN** an intent declares `expected_edge_bps = 80.0` with `max_mev_tip_bps = 50` and effective slippage cap is `50` bps
- **THEN** `mev_priority_tip_bps` in `ApprovedOrder` equals `8`

### Requirement: Explicit RiskLimits configuration fields and default values

`RiskLimits` in `robotrader_risk_gate` MUST declare the following fields with their specified types: `max_asset_exposure_pct: f64`, `max_pod_exposure_pct: f64`, `max_gross_exposure_pct: f64`, `min_order_cooldown_ms: u64`, and `max_mev_tip_bps: u32`. `RiskLimits::default()` MUST initialize these fields to `max_asset_exposure_pct = 0.15`, `max_pod_exposure_pct = 0.40`, `max_gross_exposure_pct = 1.50`, `min_order_cooldown_ms = 0`, and `max_mev_tip_bps = 50`. Each field MUST use `#[serde(default)]` so that deserializing legacy configurations that omit these fields automatically populates them with their default values.

#### Scenario: RiskLimits default values match specification

- **WHEN** `RiskLimits::default()` is constructed
- **THEN** `max_asset_exposure_pct` equals `0.15`
- **THEN** `max_pod_exposure_pct` equals `0.40`
- **THEN** `max_gross_exposure_pct` equals `1.50`
- **THEN** `min_order_cooldown_ms` equals `0`
- **THEN** `max_mev_tip_bps` equals `50`

#### Scenario: Deserializing legacy RiskLimits JSON populates defaults

- **WHEN** a JSON representation of `RiskLimits` omitting `max_asset_exposure_pct`, `max_pod_exposure_pct`, `max_gross_exposure_pct`, `min_order_cooldown_ms`, and `max_mev_tip_bps` is deserialized
- **THEN** deserialization succeeds
- **THEN** all omitted fields evaluate to their respective default values

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

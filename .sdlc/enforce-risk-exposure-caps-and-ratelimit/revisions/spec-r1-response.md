stage: spec
round: 1
head_sha: 90829f1ed3dd9bb0aa62d80143917046302c5ad4
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: >-
      Fixed the bounded MEV priority tip clamping formula to prevent runtime panics when tip_ceiling < 2.
      In `specs/risk-exposure-caps/spec.md`, the requirement "Bounded MEV priority tip" defines
      `tip_ceiling = self.limits.max_mev_tip_bps.min(effective_slippage_cap)` and `tip_floor = 2u32.min(tip_ceiling)`,
      computing `((intent.expected_edge_bps * 0.10) as u32).clamp(tip_floor, tip_ceiling)`.
      When `tip_ceiling < 2`, `tip_floor == tip_ceiling`, safely evaluating to `tip_ceiling` without panicking in `u32::clamp`.
      Added a dedicated scenario "Tight slippage ceiling below 2 clamps safely without panicking".
  - id: SPEC-R1-F02
    action: fixed
    evidence: >-
      Explicitly declared `min_order_cooldown_ms: u64` and `max_mev_tip_bps: u32` on `RiskLimits` in `specs/risk-exposure-caps/spec.md`.
      Added the requirement "Explicit RiskLimits configuration fields and default values" mandating `RiskLimits::default()`
      initialization with `min_order_cooldown_ms = 0` (for backwards compatibility with deterministic backtest fixtures)
      and `max_mev_tip_bps = 50`, with `#[serde(default)]` on each new field to safely populate defaults when deserializing legacy JSON configs.
  - id: SPEC-R1-F03
    action: fixed
    evidence: >-
      Updated prospective exposure arithmetic to use absolute values across asset, pod, and gross exposure checks:
      `existing_asset_usd = portfolio.asset_exposures_usd.get(&intent.symbol).copied().unwrap_or(0.0).abs()`,
      `existing_pod_usd = portfolio.pod_exposures_usd.get(pod_key).copied().unwrap_or(0.0).abs()`, and
      gross exposure evaluates the sum of `v.abs()` across all asset exposures. Added scenario "Existing short asset exposure
      accumulates via absolute value with new order" asserting that short positions (-1,000 USD) cannot evade the 15% cap.
      Removed the conflicting accumulated check against `max_single_position_pct`: `max_single_position_pct` is strictly
      enforced as a single-order notional clamp during Kelly sizing, while `max_asset_exposure_pct` caps aggregate asset exposure.
  - id: SPEC-R1-F04
    action: fixed
    evidence: >-
      Standardized identifier naming and explicitly declared exact Rust enum variant fields and types for all new `RiskRejection` variants:
      `OrderRateLimited { pod_id: String, symbol: String, elapsed_ms: u64, min_cooldown_ms: u64 }`,
      `AssetExposureExceeded { symbol: String, current_usd: f64, requested_usd: f64, max_usd: f64 }`,
      `PodExposureExceeded { pod_id: String, current_usd: f64, requested_usd: f64, max_usd: f64 }`, and
      `GrossExposureExceeded { current_gross_usd: f64, requested_usd: f64, max_gross_usd: f64 }`.
  - id: SPEC-R1-F05
    action: fixed
    evidence: >-
      Updated `specs/risk-hurdle/spec.md` requirement "Safety gates precede the edge hurdle" to clarify that the single-position cap
      is applied as a clamp during fractional-Kelly sizing (`desired_notional.min(equity_usd * max_single_position_pct)`),
      and only aggregate exposure caps (asset exposure -> pod exposure -> gross exposure) act as subsequent rejection gates.

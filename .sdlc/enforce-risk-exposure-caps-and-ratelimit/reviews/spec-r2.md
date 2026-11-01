# SPEC Review — Round 2

## Summary
SPEC review round 2 for `enforce-risk-exposure-caps-and-ratelimit` approves the specification at SHA `4ff66d6d9a16723e8d64d63059a9246f09653996`. All five Round 1 findings are verified closed. The author resolved the hot-path panic risk by clamping MEV priority tips between `2u32.min(tip_ceiling)` and `tip_ceiling`, explicitly defined `RiskLimits` configuration defaults (`min_order_cooldown_ms = 0`, `max_mev_tip_bps = 50`) with backward compatibility, fixed asset exposure arithmetic using absolute values for signed short positions, standardized `RiskRejection` struct variant types, and disambiguated single-position clamping within fractional-Kelly sizing. Tooling validation (`openspec validate` and `spec-lint.py`) passes cleanly with zero open blockers and zero open majors. The change is approved to proceed to the PLAN stage.

## Findings

### SPEC-R1-F01 — [blocker] Bounded MEV priority tip formula panics in Rust std when tip_ceiling < 2
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L115`
- Evidence: Requirement defines `tip_ceiling = self.limits.max_mev_tip_bps.min(effective_slippage_cap)` and `tip_floor = 2u32.min(tip_ceiling)`, computing `((intent.expected_edge_bps * 0.10) as u32).clamp(tip_floor, tip_ceiling)`. Safe clamp behavior is verified with scenario `Tight slippage ceiling below 2 clamps safely without panicking`.
- Required fix: Specify safe clamping when tip_ceiling < 2 (e.g. `let tip_floor = 2.min(tip_ceiling); ...clamp(tip_floor, tip_ceiling)`) to prevent runtime panics on the hot path.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [major] Missing RiskLimits field definition and default value for min_order_cooldown_ms
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L139-L157`
- Evidence: Requirement 'Explicit RiskLimits configuration fields and default values' declares `min_order_cooldown_ms: u64` (default `0`) and `max_mev_tip_bps: u32` (default `50`) with `#[serde(default)]` and dedicated test scenarios.
- Required fix: Explicitly specify that min_order_cooldown_ms is a u64 field on RiskLimits and declare its mandatory default value in RiskLimits::default() (e.g. 0).
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [major] Asset exposure arithmetic ignores signed short positions and conflicts with single-position cap
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L5-L25`
- Evidence: Prospective exposure arithmetic uses `existing_asset_usd.abs()` and evaluates existing short positions via absolute value (`SOL-USDT` short `-1_000.0` USD accumulates with `600.0` USD to `1_600.0` USD prospective exposure). Single-position cap is decoupled to fractional-Kelly sizing clamping.
- Required fix: Define prospective asset exposure using absolute values (`existing.abs() + approved_notional_usd`) so short positions cannot evade caps, clarify whether stablecoin filtering applies, and restrict max_single_position_pct to single-order notional clamping.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [minor] Rejection field type and naming inconsistency across exposure rejection variants
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L7-L90`
- Evidence: Rust enum variants `AssetExposureExceeded`, `PodExposureExceeded`, `GrossExposureExceeded`, and `OrderRateLimited` have explicit fields and types matching specification across all scenarios (`symbol: String`, `pod_id: String`, `current_usd: f64`, etc.).
- Required fix: Declare the exact Rust struct variant fields and types for AssetExposureExceeded, PodExposureExceeded, GrossExposureExceeded, and OrderRateLimited on RiskRejection.
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [nit] Safety gates precedence requirement lists single position under aggregate exposure caps
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-hurdle/spec.md#L7`
- Evidence: Requirement clarifies single-position cap as a clamp during fractional-Kelly sizing (`desired_notional.min(equity_usd * max_single_position_pct)`), and specifies aggregate exposure caps as sequential rejection gates (asset exposure -> pod exposure -> gross exposure).
- Required fix: Clarify that the single-position cap is applied as a clamp during fractional-Kelly sizing, and only asset, pod, and gross exposure caps act as subsequent rejection gates.
- Status: closed
- Origin: initial

## Checks run
- `openspec validate enforce-risk-exposure-caps-and-ratelimit --strict` → PASS
- `python3 scripts/sdlc/spec-lint.py --change enforce-risk-exposure-caps-and-ratelimit` → PASS
- Read time: 4.8 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "enforce-risk-exposure-caps-and-ratelimit",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "4ff66d6d9a16723e8d64d63059a9246f09653996",
  "verdict": "APPROVE",
  "summary": "All Round 1 findings are verified closed with safe MEV tip clamping, explicit RiskLimits defaults, absolute exposure math, unified rejection fields, and clear gate ordering.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L115",
      "evidence": "Requirement defines tip_ceiling = self.limits.max_mev_tip_bps.min(effective_slippage_cap) and tip_floor = 2u32.min(tip_ceiling), computing `((intent.expected_edge_bps * 0.10) as u32).clamp(tip_floor, tip_ceiling)`. Safe clamp behavior is verified with scenario `Tight slippage ceiling below 2 clamps safely without panicking`.",
      "required_fix": "Specify safe clamping when tip_ceiling < 2 (e.g. `let tip_floor = 2.min(tip_ceiling); ...clamp(tip_floor, tip_ceiling)`) to prevent runtime panics on the hot path."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L139-L157",
      "evidence": "Requirement 'Explicit RiskLimits configuration fields and default values' declares min_order_cooldown_ms: u64 (default 0) and max_mev_tip_bps: u32 (default 50) with #[serde(default)] and dedicated test scenarios.",
      "required_fix": "Explicitly specify that min_order_cooldown_ms is a u64 field on RiskLimits and declare its mandatory default value in RiskLimits::default() (e.g. 0)."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L5-L25",
      "evidence": "Prospective exposure arithmetic uses existing_asset_usd.abs() and evaluates existing short positions via absolute value (SOL-USDT short -1_000.0 USD accumulates with 600.0 USD to 1_600.0 USD prospective exposure). Single-position cap is decoupled to fractional-Kelly sizing clamping.",
      "required_fix": "Define prospective asset exposure using absolute values (`existing.abs() + approved_notional_usd`) so short positions cannot evade caps, clarify whether stablecoin filtering applies, and restrict max_single_position_pct to single-order notional clamping."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L7-L90",
      "evidence": "Rust enum variants AssetExposureExceeded, PodExposureExceeded, GrossExposureExceeded, and OrderRateLimited have explicit fields and types matching specification across all scenarios (symbol: String, pod_id: String, current_usd: f64, etc.).",
      "required_fix": "Declare the exact Rust struct variant fields and types for AssetExposureExceeded, PodExposureExceeded, GrossExposureExceeded, and OrderRateLimited on RiskRejection."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-hurdle/spec.md#L7",
      "evidence": "Requirement clarifies single-position cap as a clamp during fractional-Kelly sizing (desired_notional.min(equity_usd * max_single_position_pct)), and specifies aggregate exposure caps as sequential rejection gates (asset exposure -> pod exposure -> gross exposure).",
      "required_fix": "Clarify that the single-position cap is applied as a clamp during fractional-Kelly sizing, and only asset, pod, and gross exposure caps act as subsequent rejection gates."
    }
  ],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04",
    "SPEC-R1-F05"
  ]
}
```

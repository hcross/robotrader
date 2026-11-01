# SPEC Review — Round 1

## Summary
SPEC review round 1 for `enforce-risk-exposure-caps-and-ratelimit` requests changes due to 1 blocker and 2 major findings. While the proposal structure, backward compatibility, and zero-allocation hot-path constraints are sound, mathematical edge cases in MEV tip calculation and asset exposure accumulation require immediate correction. Specifically, calling `.clamp(2, tip_ceiling)` panics in Rust std when `tip_ceiling < 2`, crashing the node on the synchronous hot path. Furthermore, `RiskLimits` lacks a default value specification for `min_order_cooldown_ms`, and scalar addition of existing asset exposure allows negative short positions to bypass concentration ceilings. Resolving these boundary conditions is required before proceeding to the PLAN stage.

## Findings

### SPEC-R1-F01 — [blocker] Bounded MEV priority tip formula panics in Rust std when tip_ceiling < 2
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L115`
- Evidence: Requirement mandates `((intent.expected_edge_bps * 0.10) as u32).clamp(2, tip_ceiling)`. In Rust std, `u32::clamp(min, max)` panics with 'min > max' when `tip_ceiling < 2`. If effective_slippage_cap or max_mev_tip_bps is < 2, this panics and crashes the node on the hot path.
- Required fix: Specify safe clamping when tip_ceiling < 2 (e.g. `let tip_floor = 2.min(tip_ceiling); ...clamp(tip_floor, tip_ceiling)`) to prevent runtime panics on the hot path.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [major] Missing RiskLimits field definition and default value for min_order_cooldown_ms
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L90`
- Evidence: Requirement specifies behavior when min_order_cooldown_ms > 0 and min_order_cooldown_ms == 0, but omits declaring min_order_cooldown_ms on RiskLimits and omits its mandatory default value in RiskLimits::default().
- Required fix: Explicitly specify that min_order_cooldown_ms is a u64 field on RiskLimits and declare its mandatory default value in RiskLimits::default() (e.g. 0).
- Status: open
- Origin: initial

### SPEC-R1-F03 — [major] Asset exposure arithmetic ignores signed short positions and conflicts with single-position cap
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L7-L8`
- Evidence: Prospective asset exposure is defined as scalar `existing + approved_notional_usd`. Since Scenario L57-L62 establishes that asset_exposures_usd holds signed values for short positions (e.g. -8000 USD), scalar addition yields negative or reduced values, bypassing the cap. In addition, L70 duplicates/conflicts with max_asset_exposure_pct by capping accumulated exposure with max_single_position_pct.
- Required fix: Define prospective asset exposure using absolute values (`existing.abs() + approved_notional_usd`) so short positions cannot evade caps, clarify whether stablecoin filtering applies, and restrict max_single_position_pct to single-order notional clamping.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [minor] Rejection field type and naming inconsistency across exposure rejection variants
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L7`
- Evidence: RiskRejection::AssetExposureExceeded names its symbol identifier field `asset` while OrderRateLimited uses `symbol` and PodExposureExceeded uses `pod_id`. The exact field types on RiskRejection enum variants are not explicitly declared.
- Required fix: Declare the exact Rust struct variant fields and types for AssetExposureExceeded, PodExposureExceeded, GrossExposureExceeded, and OrderRateLimited on RiskRejection.
- Status: open
- Origin: initial

### SPEC-R1-F05 — [nit] Safety gates precedence requirement lists single position under aggregate exposure caps
- Location: `openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-hurdle/spec.md#L7`
- Evidence: Safety gates order lists 'single position' under aggregate exposure caps after Kelly sizing, whereas single position concentration is enforced via notional clamping inside compute_kelly_notional during Kelly sizing.
- Required fix: Clarify that the single-position cap is applied as a clamp during fractional-Kelly sizing, and only asset, pod, and gross exposure caps act as subsequent rejection gates.
- Status: open
- Origin: initial

## Checks run
- `openspec validate enforce-risk-exposure-caps-and-ratelimit --strict` → PASS
- `python3 scripts/sdlc/spec-lint.py --change enforce-risk-exposure-caps-and-ratelimit` → PASS
- Read time: 4.5 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "enforce-risk-exposure-caps-and-ratelimit",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "90829f1ed3dd9bb0aa62d80143917046302c5ad4",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Changes requested due to hot-path MEV tip clamp panic boundary condition, missing min_order_cooldown_ms default, and signed asset exposure calculation ambiguity.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L115",
      "evidence": "Requirement mandates `((intent.expected_edge_bps * 0.10) as u32).clamp(2, tip_ceiling)`. In Rust std, `u32::clamp(min, max)` panics with 'min > max' when `tip_ceiling < 2`. If effective_slippage_cap or max_mev_tip_bps is < 2, this panics and crashes the node on the hot path.",
      "required_fix": "Specify safe clamping when tip_ceiling < 2 (e.g. `let tip_floor = 2.min(tip_ceiling); ...clamp(tip_floor, tip_ceiling)`) to prevent runtime panics on the hot path."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L90",
      "evidence": "Requirement specifies behavior when min_order_cooldown_ms > 0 and min_order_cooldown_ms == 0, but omits declaring min_order_cooldown_ms on RiskLimits and omits its mandatory default value in RiskLimits::default().",
      "required_fix": "Explicitly specify that min_order_cooldown_ms is a u64 field on RiskLimits and declare its mandatory default value in RiskLimits::default() (e.g. 0)."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L7-L8",
      "evidence": "Prospective asset exposure is defined as scalar `existing + approved_notional_usd`. Since Scenario L57-L62 establishes that asset_exposures_usd holds signed values for short positions (e.g. -8000 USD), scalar addition yields negative or reduced values, bypassing the cap. In addition, L70 duplicates/conflicts with max_asset_exposure_pct by capping accumulated exposure with max_single_position_pct.",
      "required_fix": "Define prospective asset exposure using absolute values (`existing.abs() + approved_notional_usd`) so short positions cannot evade caps, clarify whether stablecoin filtering applies, and restrict max_single_position_pct to single-order notional clamping."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-exposure-caps/spec.md#L7",
      "evidence": "RiskRejection::AssetExposureExceeded names its symbol identifier field `asset` while OrderRateLimited uses `symbol` and PodExposureExceeded uses `pod_id`. The exact field types on RiskRejection enum variants are not explicitly declared.",
      "required_fix": "Declare the exact Rust struct variant fields and types for AssetExposureExceeded, PodExposureExceeded, GrossExposureExceeded, and OrderRateLimited on RiskRejection."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/enforce-risk-exposure-caps-and-ratelimit/specs/risk-hurdle/spec.md#L7",
      "evidence": "Safety gates order lists 'single position' under aggregate exposure caps after Kelly sizing, whereas single position concentration is enforced via notional clamping inside compute_kelly_notional during Kelly sizing.",
      "required_fix": "Clarify that the single-position cap is applied as a clamp during fractional-Kelly sizing, and only asset, pod, and gross exposure caps act as subsequent rejection gates."
    }
  ],
  "closed": []
}
```

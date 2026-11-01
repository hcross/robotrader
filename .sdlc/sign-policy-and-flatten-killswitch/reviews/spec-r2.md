# SPEC Review — Round 2

## Summary
APPROVED. All four Round 1 findings (SPEC-R1-F01 through SPEC-R1-F04) have been completely resolved at `eb6346ccda3ab5024be7e6a2db79ebb8fdee4e1f`. The blocker contradiction regarding Redis per-key EX expiration has been cleanly resolved by adding `## MODIFIED Requirements` for `Redis persistence contract documentation honesty`, recognizing `robotrader:policy:active` per-key EX expiration as implemented while maintaining roadmap status for Streams and Pub/Sub. Key identifier configuration via `ROBOTRADER_POLICY_KEY_ID`, kill-switch deactivation behavior returning empty flatten intents, and precise references to `HybridStateStore` have all been incorporated with corresponding testable scenarios. No new blocker or major issues were introduced.

## Assessed as sound
- 6 requirements (5 ADDED, 1 MODIFIED) across 19 scenarios; all use MUST/SHALL, each scenario contains explicit WHEN and THEN conditions, and all requirement/scenario names are unique and testable.
- OpenSpec strict validation (`openspec validate sign-policy-and-flatten-killswitch --strict`) and `spec-lint.py` both pass without errors.
- Hard platform invariants remain satisfied: detached HMAC signing preserves the strict 6-key `PolicyEnvelope` wire shape, `HardRiskGate` hot-path performance is protected with zero allocation or logging, and kill-switch flattening enforces deterministic reduce-only portfolio de-risking.
- Review Card is concise (122 words, 1 diagram, ~1.1 min read time), well under the ≤400 words and ≤5.0 min thresholds.

## Findings

### SPEC-R1-F01 — [blocker] Contradiction with existing capability spec on Redis per-key EX expiration
- Location: `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L125-L139`
- Evidence: Added a `## MODIFIED Requirements` section containing the full block for `Requirement: Redis persistence contract documentation honesty`, updating §4.2 and README descriptions to recognize `robotrader:policy:active` per-key EX TTL expiration as implemented architecture while preserving roadmap status for Redis Streams and Pub/Sub. Added documentation updates to `proposal.md` under What Changes, Modified Capabilities, and Impact.
- Required fix: Applied: full modified requirement block and documentation impacts added.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [minor] Unspecified key identifier configuration when non-default HMAC key is set
- Location: `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31-L44`
- Evidence: `Requirement: State store policy signature enforcement and safe baseline fallback` now explicitly specifies that the active key identifier is resolved from `ROBOTRADER_POLICY_KEY_ID` (defaulting to `"default"` when unset, empty, or whitespace), backed by scenarios for both default resolution and explicit configuration (`operator-key-2026`).
- Required fix: Applied: environment variable resolution and scenarios added.
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [minor] Unspecified kill-switch deactivation behavior for flatten intents payload
- Location: `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L97-L120`
- Evidence: `Requirement: Actionable kill-switch position flattening contract` now explicitly specifies that invoking `set_kill_switch(False)` resets `kill_switch_active` to `False`, clears `kill_switch_reason` to `None`, and returns an empty list `[]` for `kill_switch_flatten_intents`, verified by scenario `Deactivating kill switch returns empty flatten intents list`.
- Required fix: Applied: deactivation contract and scenario added.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [nit] State store class naming precision in spec prose
- Location: `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31` and `proposal.md#L16`
- Evidence: Requirement text and proposal prose updated across all instances to reference `HybridStateStore` (module-level instance `state_store`) in `backend/core/state_store.py`.
- Required fix: Applied: precise class and instance naming clarified throughout.
- Status: closed
- Origin: initial

## Checks run
- `git rev-parse HEAD` → `eb6346ccda3ab5024be7e6a2db79ebb8fdee4e1f`
- `openspec validate sign-policy-and-flatten-killswitch --strict` → `Change 'sign-policy-and-flatten-killswitch' is valid`
- `python3 scripts/sdlc/spec-lint.py --change sign-policy-and-flatten-killswitch` → `PASS` (122 words, 1 diagram, ~1.1 min)
- Read time: 1.1 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "sign-policy-and-flatten-killswitch",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "eb6346ccda3ab5024be7e6a2db79ebb8fdee4e1f",
  "verdict": "APPROVE",
  "summary": "All Round 1 findings (SPEC-R1-F01 through SPEC-R1-F04) are fully closed with no regressions, resolving the Redis EX documentation contradiction and specifying ROBOTRADER_POLICY_KEY_ID, kill-switch deactivation contract, and HybridStateStore class naming.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L125-L139",
      "evidence": "Added ## MODIFIED Requirements section containing full requirement block for Redis persistence contract documentation honesty, documenting robotrader:policy:active per-key EX expiration as implemented while preserving roadmap status for Redis Streams and Pub/Sub. Added documentation updates to proposal.md Impact.",
      "required_fix": "Applied: full modified requirement block and documentation impacts added."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31-L44",
      "evidence": "Requirement State store policy signature enforcement and safe baseline fallback specifies ROBOTRADER_POLICY_KEY_ID defaulting to 'default', with scenarios for default and explicit configuration.",
      "required_fix": "Applied: environment variable resolution and scenarios added."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L97-L120",
      "evidence": "Requirement Actionable kill-switch position flattening contract specifies set_kill_switch(False) resets kill_switch_active to False, clears kill_switch_reason to None, and returns kill_switch_flatten_intents as [], backed by scenario Deactivating kill switch returns empty flatten intents list.",
      "required_fix": "Applied: deactivation contract and scenario added."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31",
      "evidence": "Requirement text and proposal prose updated across all instances to reference HybridStateStore (module-level instance state_store) in backend/core/state_store.py.",
      "required_fix": "Applied: precise class and instance naming clarified throughout."
    }
  ],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04"
  ]
}
```

# Revision Response: SPEC Round 1

- **Change ID**: `sign-policy-and-flatten-killswitch`
- **Stage**: `spec`
- **Round**: 1 → 2
- **Author**: `sdlc-spec-author`
- **Reviewed SHA**: `568a760ba00641b69637e3a8c08d8b1d0321afaa`

## Responses to Findings

### SPEC-R1-F01 [blocker] — Contradiction with existing capability spec on Redis per-key EX expiration
- **Action taken**: Added a `## MODIFIED Requirements` section to `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md` with the complete requirement block for `Requirement: Redis persistence contract documentation honesty`. Updated the requirement description and scenarios to recognize `robotrader:policy:active` per-key `EX` TTL expiration as implemented architecture while preserving future roadmap status for Redis Streams and Pub/Sub. Updated `proposal.md` (`Impact` and `Modified Capabilities`) to include documentation updates for `docs/adr/0001-hybrid-quant-agentic-architecture.md` and `README.md`.
- **Location**:
  - `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md`: `## MODIFIED Requirements`
  - `openspec/changes/sign-policy-and-flatten-killswitch/proposal.md`: `## What Changes`, `### Modified Capabilities`, `## Impact`

### SPEC-R1-F02 [minor] — Unspecified key identifier configuration when non-default HMAC key is set
- **Action taken**: Specified in `Requirement: State store policy signature enforcement and safe baseline fallback` that the active key identifier is resolved from the `ROBOTRADER_POLICY_KEY_ID` environment variable (defaulting to `"default"` when unset, empty, or whitespace). Added scenarios verifying both default resolution and explicit configuration.
- **Location**:
  - `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md`: `Requirement: State store policy signature enforcement and safe baseline fallback` (scenarios `Default secret key and key ID are utilized when environment variables are unset` and `Explicit key identifier is recorded when configured`)

### SPEC-R1-F03 [minor] — Unspecified kill-switch deactivation behavior for flatten intents payload
- **Action taken**: Updated `Requirement: Actionable kill-switch position flattening contract` to explicitly specify that invoking `set_kill_switch(False)` to deactivate the kill switch resets `kill_switch_active` to `False`, `kill_switch_reason` to `None`, and `kill_switch_flatten_intents` in the returned status dictionary to an empty list `[]`. Added scenario `Deactivating kill switch returns empty flatten intents list`.
- **Location**:
  - `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md`: `Requirement: Actionable kill-switch position flattening contract`

### SPEC-R1-F04 [nit] — State store class naming precision in spec prose
- **Action taken**: Clarified in `specs/control-plane-security/spec.md` and `proposal.md` that references to the state store designate `HybridStateStore` (module-level instance `state_store`) in `backend/core/state_store.py`.
- **Location**:
  - `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md`
  - `openspec/changes/sign-policy-and-flatten-killswitch/proposal.md`

# SPEC Review — Round 1

## Summary
The specification is well-structured and comprehensive, successfully covering cross-language canonical HMAC-SHA256 signing, Redis active policy TTL publication, and actionable kill-switch position flattening. Changes are requested because adding implemented Redis per-key EX publication introduces a direct contradiction with the existing `control-plane-security` requirement (`Redis persistence contract documentation honesty`), which still mandates labelling per-key EX expiration as a future roadmap item. To resolve this, the existing honesty requirement must be included under `## MODIFIED Requirements` to recognize `robotrader:policy:active` EX expiration as implemented while keeping Redis Streams and Pub/Sub as roadmap items.

## Findings

### SPEC-R1-F01 — [blocker] Contradiction with existing capability spec on Redis per-key EX expiration
- Location: `openspec/specs/control-plane-security/spec.md#L61-L75`
- Evidence: Existing capability spec `openspec/specs/control-plane-security/spec.md` requires in Requirement `Redis persistence contract documentation honesty` that "References to Redis Streams, Pub/Sub, or per-key `EX` expiration MUST be explicitly labelled as future roadmap items rather than implemented architecture." Delta spec `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md` adds Requirement `Active policy published to Redis with explicit TTL expiration` implementing per-key `EX` expiration without modifying the existing requirement or listing doc updates in `proposal.md` Impact, creating a direct contradiction within `control-plane-security` upon merge.
- Required fix: Add a `## MODIFIED Requirements` section to `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md` containing the full requirement block for `Redis persistence contract documentation honesty`, updating it so `robotrader:policy:active` per-key `EX` expiration is documented as implemented architecture while preserving future roadmap status for Redis Streams and Pub/Sub. Update `proposal.md` Impact to list `docs/adr/0001-hybrid-quant-agentic-architecture.md` and `README.md`.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [minor] Unspecified key identifier configuration when non-default HMAC key is set
- Location: `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31-L40`
- Evidence: Requirement `State store policy signature enforcement and safe baseline fallback` specifies `ROBOTRADER_POLICY_HMAC_KEY` and tests `policy_key_id = "default"` when unset, but leaves active key identifier resolution unspecified when an operator provides an explicit custom secret key.
- Required fix: Specify whether the active key identifier is configured via an environment variable (e.g. `ROBOTRADER_POLICY_KEY_ID` defaulting to `"default"`) or remains fixed as `"default"` unless explicitly configured.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [minor] Unspecified kill-switch deactivation behavior for flatten intents payload
- Location: `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L93-L112`
- Evidence: Requirement `Actionable kill-switch position flattening contract` mandates that `StateStore.set_kill_switch(True, reason)` records `kill_switch_flatten_intents` in the returned status dictionary, but omits the expected payload contract when `set_kill_switch(False)` is invoked to deactivate the kill-switch.
- Required fix: Specify that when `set_kill_switch(False)` is invoked, `kill_switch_flatten_intents` in the returned status dictionary is an empty list `[]`.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [nit] State store class naming precision in spec prose
- Location: `openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31`
- Evidence: Requirement prose references `StateStore` in `backend/core/state_store.py`, whereas the Python class is `HybridStateStore` (module instance `state_store`).
- Required fix: Clarify in the requirement text that `StateStore` refers to `HybridStateStore` in `backend/core/state_store.py`.
- Status: open
- Origin: initial

## Checks run
- `git rev-parse HEAD` → `568a760ba00641b69637e3a8c08d8b1d0321afaa`
- `openspec validate sign-policy-and-flatten-killswitch --strict` → `Change 'sign-policy-and-flatten-killswitch' is valid`
- `python3 scripts/sdlc/spec-lint.py --change sign-policy-and-flatten-killswitch` → `PASS` (120 words, 1 diagram, ~1.1 min)
- Read time: 1.1 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "sign-policy-and-flatten-killswitch",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "568a760ba00641b69637e3a8c08d8b1d0321afaa",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Changes requested due to a contradiction with existing capability requirement 'Redis persistence contract documentation honesty' which still classifies per-key EX expiration as a roadmap item.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/specs/control-plane-security/spec.md#L61-L75",
      "evidence": "Existing capability spec openspec/specs/control-plane-security/spec.md requires in Requirement 'Redis persistence contract documentation honesty' that 'References to Redis Streams, Pub/Sub, or per-key EX expiration MUST be explicitly labelled as future roadmap items rather than implemented architecture'. Delta spec openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md adds Requirement 'Active policy published to Redis with explicit TTL expiration' implementing per-key EX expiration without modifying the existing requirement or listing doc updates in proposal.md Impact, creating a direct contradiction within control-plane-security upon merge.",
      "required_fix": "Add a '## MODIFIED Requirements' section to openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md containing the full requirement block for 'Redis persistence contract documentation honesty', updating it so robotrader:policy:active per-key EX expiration is documented as implemented architecture while preserving future roadmap status for Redis Streams and Pub/Sub. Update proposal.md Impact to list docs/adr/0001-hybrid-quant-agentic-architecture.md and README.md."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31-L40",
      "evidence": "Requirement 'State store policy signature enforcement and safe baseline fallback' specifies ROBOTRADER_POLICY_HMAC_KEY and tests policy_key_id='default' when unset, but leaves active key identifier resolution unspecified when an operator provides an explicit custom secret key.",
      "required_fix": "Specify whether the active key identifier is configured via an environment variable (e.g. ROBOTRADER_POLICY_KEY_ID defaulting to 'default') or remains fixed as 'default' unless explicitly configured."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L93-L112",
      "evidence": "Requirement 'Actionable kill-switch position flattening contract' mandates that StateStore.set_kill_switch(True, reason) records kill_switch_flatten_intents in the returned status dictionary, but omits the expected payload contract when set_kill_switch(False) is invoked to deactivate the kill-switch.",
      "required_fix": "Specify that when set_kill_switch(False) is invoked, kill_switch_flatten_intents in the returned status dictionary is an empty list []."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/sign-policy-and-flatten-killswitch/specs/control-plane-security/spec.md#L31",
      "evidence": "Requirement prose references StateStore in backend/core/state_store.py, whereas the Python class is HybridStateStore (module instance state_store).",
      "required_fix": "Clarify in the requirement text that StateStore refers to HybridStateStore in backend/core/state_store.py."
    }
  ],
  "closed": []
}
```

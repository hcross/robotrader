# SPEC Review — Round 1

## Summary

The proposal and delta specifications for `reconcile-openrouter-credits-live` establish live OpenRouter credit balance reconciliation and out-of-band settlement receipts. However, the change cannot be approved in Round 1 because the delta specification omits a `## MODIFIED Requirements` block for `Requirement: OpenRouter credit status and UI display simulated ledger provenance` from the base spec. The base requirement explicitly forbids querying live `/api/v1/credits` and mandates `balance_source: 'SIMULATED_INTERNAL_LEDGER'`, creating a direct specification contradiction. Furthermore, the status dictionary extensions declared in the proposal and tasks are omitted from the specification requirements, task 1.3 references a non-existent scenario, and the return contract for successful live probes lacks a defined `reconciliation_status` value. `CHANGES_REQUESTED` with 1 blocker, 2 majors, and 2 minors.

## Findings

### SPEC-R1-F01 — [blocker] Base specification contradiction: `Requirement: OpenRouter credit status and UI display simulated ledger provenance` not modified
- Location: `openspec/specs/costguard/spec.md#L410-L421` vs `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L3-L8`
- Evidence: Existing base requirement in `openspec/specs/costguard/spec.md#L410-L421` states: "LLMMonitorAgent.get_status() MUST include balance_source: 'SIMULATED_INTERNAL_LEDGER' within the openrouter_credit status object. Neither the API nor the UI MAY represent the credit balance as queried from a live OpenRouter /api/v1/credits endpoint." The delta spec in `specs/costguard/spec.md` lists the live credits probe under `## ADDED Requirements` without placing the existing requirement under `## MODIFIED Requirements` and copying the full block as required by OpenSpec and SDLC rules. This creates an unresolvable contradiction between the base spec and the change spec.
- Required fix: Add a `## MODIFIED Requirements` section to `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md` copying the full block of `Requirement: OpenRouter credit status and UI display simulated ledger provenance`, update its normative text and scenarios to allow transitioning `balance_source` to `"MEASURED_OPENROUTER_API"` on successful live reconciliation while preserving `"SIMULATED_INTERNAL_LEDGER"` as the initial/fallback state, and specify the frontend badge behavior for both provenance states.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [major] Status dictionary extensions omitted from spec requirements and task 1.3 references non-existent scenario
- Location: `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md` vs `openspec/changes/reconcile-openrouter-credits-live/tasks.md#L7`
- Evidence: `proposal.md#L53` promises "additive last_reconciled_ms and reconciliation_status in status payload" and `tasks.md#L7` specifies Task 1.3: "Expose balance_source, last_reconciled_ms, and last_reconciliation_status in LLMMonitorAgent.get_status() status dictionary (satisfies Scenario: Status payload reports simulated or measured provenance)." However, `specs/costguard/spec.md` contains no requirement or scenario specifying the additions to `get_status()`, and no scenario named `Status payload reports simulated or measured provenance` exists in any spec file. Furthermore, the field name is inconsistent between proposal (`reconciliation_status`) and tasks (`last_reconciliation_status`).
- Required fix: Specify the status dictionary extensions (`last_reconciled_ms` and a consistently named reconciliation status field) under a modified `get_status()` requirement in `specs/costguard/spec.md` accompanied by testable scenarios covering both simulated and measured status outputs, and harmonize field naming across `proposal.md`, `specs/costguard/spec.md`, and `tasks.md`.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [major] Undefined success status value, probe return contract ambiguities, and unhandled post-success failure state
- Location: `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L7-L28`
- Evidence: In `Requirement: Live OpenRouter credit balance probe and fallback`, fallback returns a diagnostic dict with `reconciliation_status: "FALLBACK_SIMULATED"`, but neither the requirement nor any scenario defines the exact value of `reconciliation_status` upon success (e.g. `"OK"`, `"MEASURED_OPENROUTER_API"`, or `"SUCCESS"`). Furthermore, the requirement parenthetical "(unless a prior live reconciliation succeeded, in which case openrouter_balance_usd is preserved)" is ambiguous regarding what `balance_source` transitions to when a subsequent probe fails after a prior success, and no scenario tests this boundary condition. Finally, Requirement 1 names `last_reconciled_ms` while Requirement 2 names `timestamp_ms` for the probe return dictionary timestamp.
- Required fix: Define the exact return dictionary schema for `reconcile_openrouter_credits()` in `specs/costguard/spec.md` including the literal value of `reconciliation_status` on success, standardize the timestamp key name across requirements, and add a scenario specifying `balance_source` and `openrouter_balance_usd` state when a probe fails following a prior successful live reconciliation.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [minor] Prescribed receipt ID formula breaks under bounded history length
- Location: `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L43`
- Evidence: Line 43 prescribes: "every approved refill MUST include a deterministic and unique settlement_receipt_id formatted as f\"or-refill-{now_ms}-{len(self.refill_history) + 1}\"". In `backend/agents/monitor.py#L661`, `self.refill_history` is capped to 25 entries (`self.refill_history = self.refill_history[:25]`). Deriving the receipt sequence from `len(self.refill_history) + 1` causes the counter to halt at 26 after 25 refills, violating the requirement that receipt IDs are unique and incrementing across consecutive refills.
- Required fix: Decouple the requirement from the Python expression `len(self.refill_history) + 1` and require `settlement_receipt_id` to be formatted as `or-refill-<timestamp_ms>-<counter>` where `<counter>` is a monotonic positive integer tracking total approved refills in the instance lifetime (e.g., via a dedicated sequence counter).
- Status: open
- Origin: initial

### SPEC-R1-F05 — [minor] Verification commands cite non-existent test files
- Location: `openspec/changes/reconcile-openrouter-credits-live/tasks.md#L23-L24`
- Evidence: `tasks.md` lines 23-24 list `PYTHONPATH=. python3 -m unittest backend/tests/test_cost_guard_pnl_gate.py -v` and `PYTHONPATH=. python3 -m unittest backend/tests/test_rust_refill_validator.py -v`. Neither file exists in `backend/tests/`, and running those commands fails with `ModuleNotFoundError`. The actual test files are `backend/tests/test_costguard_gate.py` and `backend/tests/test_costguard_refill_gate.py`.
- Required fix: Update the test execution commands in `tasks.md#L23-L24` to reference the existing test modules (`backend/tests/test_costguard_gate.py` and `backend/tests/test_costguard_refill_gate.py`).
- Status: open
- Origin: initial

## Checks run
- `openspec validate reconcile-openrouter-credits-live --strict` → pass
- `python3 scripts/sdlc/spec-lint.py --change reconcile-openrouter-credits-live` → pass
- Read time: 1.0 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "reconcile-openrouter-credits-live",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "e376ae2affdfe3c45502f84b6bddbfaa36d20857",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Changes requested due to direct contradiction with existing base costguard specification, omitted status dictionary requirements with orphaned task scenario mapping, and ambiguous live probe return contracts.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/specs/costguard/spec.md#L410-L421 vs openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L3-L8",
      "evidence": "Existing base requirement in openspec/specs/costguard/spec.md#L410-L421 states: 'LLMMonitorAgent.get_status() MUST include balance_source: \"SIMULATED_INTERNAL_LEDGER\" within the openrouter_credit status object. Neither the API nor the UI MAY represent the credit balance as queried from a live OpenRouter /api/v1/credits endpoint.' The delta spec in specs/costguard/spec.md lists the live credits probe under '## ADDED Requirements' without placing the existing requirement under '## MODIFIED Requirements' and copying the full block as required by OpenSpec and SDLC rules. This creates an unresolvable contradiction between the base spec and the change spec.",
      "required_fix": "Add a '## MODIFIED Requirements' section to openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md copying the full block of 'Requirement: OpenRouter credit status and UI display simulated ledger provenance', update its normative text and scenarios to allow transitioning balance_source to 'MEASURED_OPENROUTER_API' on successful live reconciliation while preserving 'SIMULATED_INTERNAL_LEDGER' as the initial/fallback state, and specify the frontend badge behavior for both provenance states."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md vs openspec/changes/reconcile-openrouter-credits-live/tasks.md#L7",
      "evidence": "proposal.md#L53 promises 'additive last_reconciled_ms and reconciliation_status in status payload' and tasks.md#L7 specifies Task 1.3: 'Expose balance_source, last_reconciled_ms, and last_reconciliation_status in LLMMonitorAgent.get_status() status dictionary (satisfies Scenario: Status payload reports simulated or measured provenance).' However, specs/costguard/spec.md contains no requirement or scenario specifying the additions to get_status(), and no scenario named 'Status payload reports simulated or measured provenance' exists in any spec file. Furthermore, the field name is inconsistent between proposal (reconciliation_status) and tasks (last_reconciliation_status).",
      "required_fix": "Specify the status dictionary extensions (last_reconciled_ms and a consistently named reconciliation status field) under a modified get_status() requirement in specs/costguard/spec.md accompanied by testable scenarios covering both simulated and measured status outputs, and harmonize field naming across proposal.md, specs/costguard/spec.md, and tasks.md."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L7-L28",
      "evidence": "In Requirement: Live OpenRouter credit balance probe and fallback, fallback returns a diagnostic dict with reconciliation_status: 'FALLBACK_SIMULATED', but neither the requirement nor any scenario defines the exact value of reconciliation_status upon success (e.g. 'OK', 'MEASURED_OPENROUTER_API', or 'SUCCESS'). Furthermore, the requirement parenthetical '(unless a prior live reconciliation succeeded, in which case openrouter_balance_usd is preserved)' is ambiguous regarding what balance_source transitions to when a subsequent probe fails after a prior success, and no scenario tests this boundary condition. Finally, Requirement 1 names last_reconciled_ms while Requirement 2 names timestamp_ms for the probe return dictionary timestamp.",
      "required_fix": "Define the exact return dictionary schema for reconcile_openrouter_credits() in specs/costguard/spec.md including the literal value of reconciliation_status on success, standardize the timestamp key name across requirements, and add a scenario specifying balance_source and openrouter_balance_usd state when a probe fails following a prior successful live reconciliation."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L43",
      "evidence": "Line 43 prescribes: 'every approved refill MUST include a deterministic and unique settlement_receipt_id formatted as f\"or-refill-{now_ms}-{len(self.refill_history) + 1}\"'. In backend/agents/monitor.py#L661, self.refill_history is capped to 25 entries (self.refill_history = self.refill_history[:25]). Deriving the receipt sequence from len(self.refill_history) + 1 causes the counter to halt at 26 after 25 refills, violating the requirement that receipt IDs are unique and incrementing across consecutive refills.",
      "required_fix": "Decouple the requirement from the Python expression len(self.refill_history) + 1 and require settlement_receipt_id to be formatted as or-refill-<timestamp_ms>-<counter> where <counter> is a monotonic positive integer tracking total approved refills in the instance lifetime (e.g., via a dedicated sequence counter)."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/reconcile-openrouter-credits-live/tasks.md#L23-L24",
      "evidence": "tasks.md lines 23-24 list 'PYTHONPATH=. python3 -m unittest backend/tests/test_cost_guard_pnl_gate.py -v' and 'PYTHONPATH=. python3 -m unittest backend/tests/test_rust_refill_validator.py -v'. Neither file exists in backend/tests/, and running those commands fails with ModuleNotFoundError. The actual test files are backend/tests/test_costguard_gate.py and backend/tests/test_costguard_refill_gate.py.",
      "required_fix": "Update the test execution commands in tasks.md#L23-L24 to reference the existing test modules (backend/tests/test_costguard_gate.py and backend/tests/test_costguard_refill_gate.py)."
    }
  ],
  "closed": []
}
```

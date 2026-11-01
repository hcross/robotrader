# SPEC Review — Round 2

## Summary

All five findings from Round 1 (SPEC-R1-F01 through SPEC-R1-F05) have been verified and successfully resolved at commit `0ada65e17513f507a27ca73e24555bf5b1defdf1`. The delta specification now incorporates the full modified requirement for OpenRouter credit provenance, harmonizes `get_status()` fields across proposal, specs, and tasks, formally defines the return schemas and post-success failure retention for the live credit probe, specifies a monotonic counter for settlement receipt IDs, and references existing unit tests in the verification commands. Zero open blocker or major findings remain. The specification satisfies all checklist criteria and platform invariants. Verdict: APPROVE.

## Findings

### SPEC-R1-F01 — [blocker] Base specification contradiction: `Requirement: OpenRouter credit status and UI display simulated ledger provenance` not modified
- Location: `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L3-L30`
- Evidence: The full block of `Requirement: OpenRouter credit status and UI display simulated ledger provenance` is now included under `## MODIFIED Requirements`. Normative text and scenarios explicitly specify transitioning `balance_source` to `"MEASURED_OPENROUTER_API"` on successful live probe while preserving `"SIMULATED_INTERNAL_LEDGER"` as default/fallback, and badge rendering is specified for both states.
- Required fix: Add a `## MODIFIED Requirements` section copying the full requirement block and updating normative text and scenarios (verified complete).
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [major] Status dictionary extensions omitted from spec requirements and task 1.3 references non-existent scenario
- Location: `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L5-L22` and `openspec/changes/reconcile-openrouter-credits-live/tasks.md#L7`
- Evidence: `get_status()` status dictionary extensions (`balance_source`, `reconciliation_status`, `last_reconciled_ms`, and `reconciled_balance_usd`) are specified in the modified requirement with testable scenarios covering default simulated and measured states. Task 1.3 in `tasks.md` maps directly to the actual scenarios and field names are harmonized across proposal, spec, and tasks.
- Required fix: Specify status dictionary extensions in `specs/costguard/spec.md` with testable scenarios and harmonize field naming across artifacts (verified complete).
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [major] Undefined success status value, probe return contract ambiguities, and unhandled post-success failure state
- Location: `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L33-L63`
- Evidence: Exact return dictionary schemas are formally specified for all outcomes (`"RECONCILED_OK"`, `"SKIPPED_NO_API_KEY"`, and `"RECONCILE_FAILED"`). The post-success failure condition is defined and tested via `Scenario: Probe failure following prior successful probe preserves balance and reports failure status` (preserving `openrouter_balance_usd`, `reconciled_balance_usd`, and `last_reconciled_ms` from the last successful probe while setting `reconciliation_status = "RECONCILE_FAILED"` and reverting `balance_source = "SIMULATED_INTERNAL_LEDGER"`). Timestamp field names are standardized to `last_reconciled_ms`.
- Required fix: Define return dictionary schema with exact status values, standardize timestamp field name, and specify post-success failure handling (verified complete).
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [minor] Prescribed receipt ID formula breaks under bounded history length
- Location: `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L78` and `openspec/changes/reconcile-openrouter-credits-live/tasks.md#L12`
- Evidence: The requirement decouples `settlement_receipt_id` from history length and specifies `or-refill-<timestamp_ms>-<counter>` where `<counter>` is a monotonic positive integer counter tracking lifetime approved refills (`self._refill_seq`), tested in `Scenario: Consecutive approved refills receive unique and incrementing receipt identifiers`.
- Required fix: Decouple receipt ID from history array length and use a monotonic sequence counter (verified complete).
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [minor] Verification commands cite non-existent test files
- Location: `openspec/changes/reconcile-openrouter-credits-live/tasks.md#L23-L25`
- Evidence: Verification section now references actual existing test suites: `backend/tests/test_costguard_gate.py`, `backend/tests/test_costguard_refill_gate.py`, and `backend/tests/test_hierarchy_v3.py`.
- Required fix: Update test paths to reference existing test modules (verified complete).
- Status: closed
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
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "0ada65e17513f507a27ca73e24555bf5b1defdf1",
  "verdict": "APPROVE",
  "summary": "All Round 1 findings (SPEC-R1-F01 through SPEC-R1-F05) are resolved with complete delta specifications, harmonized contracts, and valid verification references.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L3-L30",
      "evidence": "Requirement: OpenRouter credit status and UI display simulated ledger provenance is fully copied under MODIFIED Requirements, specifying transition to MEASURED_OPENROUTER_API on live success and SIMULATED_INTERNAL_LEDGER on fallback/default.",
      "required_fix": "Add a MODIFIED Requirements section copying the full requirement block and updating normative text and scenarios."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L5-L22",
      "evidence": "Status dictionary extensions (balance_source, reconciliation_status, last_reconciled_ms, reconciled_balance_usd) are formally defined with scenarios, and task 1.3 references valid scenario names.",
      "required_fix": "Specify status dictionary extensions in specs/costguard/spec.md with testable scenarios and harmonize field naming across artifacts."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L33-L63",
      "evidence": "Exact return schemas are specified (RECONCILED_OK, SKIPPED_NO_API_KEY, RECONCILE_FAILED), post-success failure retention behavior is specified and tested, and timestamp keys are standardized to last_reconciled_ms.",
      "required_fix": "Define return dictionary schema with exact status values, standardize timestamp field name, and specify post-success failure handling."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md#L78",
      "evidence": "Receipt ID is decoupled from refill history length and specified as or-refill-<timestamp_ms>-<counter> with a lifetime monotonic sequence counter.",
      "required_fix": "Decouple receipt ID from history array length and use a monotonic sequence counter."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/reconcile-openrouter-credits-live/tasks.md#L23-L25",
      "evidence": "Verification commands cite real existing test files backend/tests/test_costguard_gate.py, backend/tests/test_costguard_refill_gate.py, and backend/tests/test_hierarchy_v3.py.",
      "required_fix": "Update test paths to reference existing test modules."
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

# SPEC Author Revision Response — Round 1

All findings from Round 1 review (`spec-r1.md`) have been addressed:

## SPEC-R1-F01 [blocker]: Base specification contradiction: `Requirement: OpenRouter credit status and UI display simulated ledger provenance` not modified
- **Resolution**: Added a `## MODIFIED Requirements` block to `openspec/changes/reconcile-openrouter-credits-live/specs/costguard/spec.md` copying the full block of `Requirement: OpenRouter credit status and UI display simulated ledger provenance`.
- **Details**: Updated normative text and scenarios to allow transitioning `balance_source` to `"MEASURED_OPENROUTER_API"` upon successful live reconciliation, while preserving `"SIMULATED_INTERNAL_LEDGER"` as the initial and fallback state. Specified frontend badge rendering for both provenance values.

## SPEC-R1-F02 [major]: Status dictionary extensions omitted from spec requirements and task 1.3 references non-existent scenario
- **Resolution**: Added explicit status dictionary fields (`balance_source`, `reconciliation_status`, `last_reconciled_ms`, `reconciled_balance_usd`) in the modified `get_status()` requirement and accompanying scenarios.
- **Details**: Updated Task 1.3 in `tasks.md` to reference the actual scenario names (`Status payload reports simulated internal ledger provenance by default`, `Status payload reports measured provenance after successful reconciliation`).

## SPEC-R1-F03 [major]: Undefined success status value, probe return contract ambiguities, and unhandled post-success failure state
- **Resolution**: Formally defined the exact return contract for `reconcile_openrouter_credits()`:
  - `reconciliation_status`: `"RECONCILED_OK"`, `"SKIPPED_NO_API_KEY"`, or `"RECONCILE_FAILED"`.
  - Harmonized timestamp field name to `last_reconciled_ms` across all requirements and endpoints.
  - Specified post-success failure state: when a probe fails following a prior successful reconciliation, `openrouter_balance_usd`, `reconciled_balance_usd`, and `last_reconciled_ms` are preserved from the last success, while `reconciliation_status` becomes `"RECONCILE_FAILED"` and `balance_source` reverts to `"SIMULATED_INTERNAL_LEDGER"`. Added `Scenario: Probe failure following prior successful probe preserves balance and reports failure status`.

## SPEC-R1-F04 [minor]: Prescribed receipt ID formula breaks under bounded history length
- **Resolution**: Decoupled `settlement_receipt_id` from `len(self.refill_history) + 1`.
- **Details**: Formatted as `or-refill-<timestamp_ms>-<counter>` where `<counter>` is a monotonic positive integer tracking total approved refills in the instance lifetime (`self._refill_seq`).

## SPEC-R1-F05 [minor]: Verification commands cite non-existent test files
- **Resolution**: Updated `tasks.md` and `proposal.md` to reference real, existing test files: `backend/tests/test_costguard_gate.py`, `backend/tests/test_costguard_refill_gate.py`, and `backend/tests/test_hierarchy_v3.py`.

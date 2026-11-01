# Implementation Tasks: Reconcile OpenRouter Credits Live

## 1. Live Balance Probe Implementation

- [ ] 1.1 Implement `LLMMonitorAgent.reconcile_openrouter_credits` in `backend/agents/monitor.py` with 3.0s timeout and bearer authentication (satisfies Scenario: Successful live API probe updates credit balance and provenance).
- [ ] 1.2 Implement defensive error handling, placeholder check, post-success failure retention, and fallback logic in `reconcile_openrouter_credits` (satisfies Scenarios: Unset or placeholder API key bypasses network probe and reports skipped status, Upstream HTTP error or timeout preserves balance and returns failure status, Malformed or non-finite JSON payload fails safe without mutating balance, Probe failure following prior successful probe preserves balance and reports failure status).
- [ ] 1.3 Expose `balance_source`, `reconciliation_status`, `last_reconciled_ms`, and `reconciled_balance_usd` in `LLMMonitorAgent.get_status()` status dictionary (satisfies Scenarios: Status payload reports simulated internal ledger provenance by default, Status payload reports measured provenance after successful reconciliation).

## 2. Settlement Metadata & Provenance

- [ ] 2.1 Update `LLMMonitorAgent.trigger_openrouter_refill` to compute `settlement_mode` (`OPERATOR_OUT_OF_BAND_INTENT` vs `SIMULATED_LEDGER_INCREMENT`) based on `balance_source` (satisfies Scenarios: Refill under measured provenance records out-of-band operator intent settlement, Refill under simulated provenance records simulated ledger increment settlement).
- [ ] 2.2 Add monotonic sequence counter `self._refill_seq` to generate deterministic `settlement_receipt_id` and attach it to approved refill events in `refill_history` and return payloads (satisfies Scenario: Consecutive approved refills receive unique and incrementing receipt identifiers).

## 3. Control Plane Endpoint & Integration

- [ ] 3.1 Implement `POST /api/v1/openrouter/reconcile` in `backend/server.py` delegating to `orchestrator.cost_guard.reconcile_openrouter_credits` (satisfies Scenarios: Operator invokes on-demand reconciliation endpoint successfully, Upstream failure during on-demand reconciliation returns structured fallback without server error).
- [ ] 3.2 Add unit and integration tests in `backend/tests/test_openrouter_reconciliation.py` verifying live probe success, mock network errors, placeholder key bypass, settlement receipt metadata, and REST endpoint behavior (satisfies verification of all added and modified requirements).

## Verification

Run the following test commands to verify all scenarios and invariants:
- `PYTHONPATH=. python3 -m unittest backend/tests/test_openrouter_reconciliation.py -v`
- `PYTHONPATH=. python3 -m unittest backend/tests/test_costguard_gate.py -v`
- `PYTHONPATH=. python3 -m unittest backend/tests/test_costguard_refill_gate.py -v`
- `PYTHONPATH=. python3 -m unittest backend/tests/test_hierarchy_v3.py -v`
- `cd engine-rs && cargo test`
- `python3 scripts/sdlc/spec-lint.py --change reconcile-openrouter-credits-live`

# Proposal: reconcile-openrouter-credits-live

## Review Card (≤ 5 min)

| Field | Value |
|---|---|
| Outcome | Reconcile inference credit balances against live OpenRouter API and record auditable out-of-band settlement receipts on refills. |
| Why now | Completes the final slice of Issue #5 by replacing simulated balance assumptions with live `/api/v1/credits` polling and establishing explicit settlement provenance. |
| Blast radius | `backend/agents/monitor.py` (`LLMMonitorAgent`), `backend/server.py` (`POST /api/v1/openrouter/reconcile`), `openspec/specs/costguard`. |
| Risk | Low. API failures fall back cleanly to internal simulated balance without blocking execution or corrupting accounting state. |
| Effort | S (1 dev round, 1 review round). |
| Decision needed | None. Follows established CostGuard architecture and closes Issue #5. |

```mermaid
flowchart LR
    A["Operator / Scheduler"] -->|"POST /reconcile"| B["LLMMonitorAgent"]
    B -->|"GET /api/v1/credits"| C{"OpenRouter API"}
    C -->|"200 OK (credits - usage)"| D["MEASURED_OPENROUTER_API"]
    C -->|"Timeout / Error / Unset"| E["FALLBACK_SIMULATED"]
    D -->|"Trigger Refill"| F["OPERATOR_OUT_OF_BAND_INTENT"]
    E -->|"Trigger Refill"| G["SIMULATED_LEDGER_INCREMENT"]
```

## Why

While CostGuard's auto-refill is now profit-gated and validated by Rust HardRiskGate, the reported OpenRouter balance remains an unverified internal simulation. This change implements live credit balance reconciliation via `GET https://openrouter.ai/api/v1/credits` and tags refills with auditable out-of-band settlement metadata to complete Issue #5.

## What Changes

- Add `LLMMonitorAgent.reconcile_openrouter_credits(timeout_sec=3.0)` to query the OpenRouter credits API with bearer authentication, updating `openrouter_balance_usd` to `round(max(0.0, total_credits - total_usage), 4)`, setting `balance_source` to `"MEASURED_OPENROUTER_API"`, and recording `last_reconciled_ms`.
- Implement defensive fallback in `reconcile_openrouter_credits` when `OPENROUTER_API_KEY` is missing, empty, or a placeholder, or when network/HTTP/JSON errors occur, returning status `"FALLBACK_SIMULATED"` and preserving state without raising unhandled exceptions.
- Add `POST /api/v1/openrouter/reconcile` in `backend/server.py` to allow on-demand credit balance reconciliation by operators and the Master Orchestrator.
- Tag every approved refill event in `LLMMonitorAgent.trigger_openrouter_refill` with `settlement_mode` (`"OPERATOR_OUT_OF_BAND_INTENT"` when measured vs `"SIMULATED_LEDGER_INCREMENT"` when simulated) and a deterministic `settlement_receipt_id` (`or-refill-<timestamp_ms>-<count>`).

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `costguard`: Adds live OpenRouter credit balance reconciliation probe, on-demand REST endpoint, and out-of-band settlement receipt tracking.

## Non-goals

- Direct automated credit purchasing or Coinbase Commerce cryptocurrency payment execution, as OpenRouter requires interactive billing or crypto checkout; settlement remains out-of-band operator intent.
- Modifying Rust `HardRiskGate::validate_inference_refill` or the CLI `--validate-refill` interface, which are already authoritative and tested.
- Frontend UI redesign beyond consuming the existing `balance_source` and new reconciliation status fields.
- Background polling daemon for credit reconciliation; reconciliation is performed on demand or during explicit scheduler cycles to avoid excessive external network calls.

## Impact

- Affected code: `backend/agents/monitor.py` (`LLMMonitorAgent`), `backend/server.py` (`/api/v1/openrouter/reconcile`).
- API contracts: Additive `POST /api/v1/openrouter/reconcile` endpoint; additive `settlement_mode` and `settlement_receipt_id` fields in refill history events; additive `last_reconciled_ms` and `reconciliation_status` in status payload.
- Dependencies: Standard library `urllib.request` / `urllib.error` (no new external dependencies).
- Invariants: Zero hot-path impact, zero key exposure, non-spendable vault preserved, capital protection and daily LLM caps preserved.

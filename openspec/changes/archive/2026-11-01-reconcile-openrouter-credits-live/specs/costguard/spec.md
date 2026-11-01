# costguard Delta Specification

## MODIFIED Requirements

### Requirement: OpenRouter credit status and UI display simulated ledger provenance

`LLMMonitorAgent.get_status()` MUST include `balance_source`, `reconciliation_status`, `last_reconciled_ms`, and `reconciled_balance_usd` within the `openrouter_credit` status object. Prior to any successful reconciliation, `balance_source` MUST be `"SIMULATED_INTERNAL_LEDGER"`, `reconciliation_status` MUST be `"UNRECONCILED"`, and `last_reconciled_ms` and `reconciled_balance_usd` MUST be null. When live reconciliation succeeds via `GET /api/v1/credits`, `balance_source` MUST transition to `"MEASURED_OPENROUTER_API"`, `reconciliation_status` MUST become `"RECONCILED_OK"`, `reconciled_balance_usd` MUST record the measured credit balance, and `last_reconciled_ms` MUST record the evaluation timestamp. When a subsequent reconciliation probe fails or when `OPENROUTER_API_KEY` is missing, `balance_source` MUST be `"SIMULATED_INTERNAL_LEDGER"`, while `last_reconciled_ms` and `reconciled_balance_usd` preserve the values from the last successful probe. The frontend `MasterOverview.jsx` component MUST display a visible provenance badge reflecting the current `balance_source` (`"SIMULATED_INTERNAL_LEDGER"` or `"MEASURED_OPENROUTER_API"`).

#### Scenario: Status payload reports simulated internal ledger provenance by default
- **WHEN** `LLMMonitorAgent.get_status()` is called on an active monitor agent prior to any reconciliation
- **THEN** `status["openrouter_credit"]["balance_source"]` equals `"SIMULATED_INTERNAL_LEDGER"`
- **THEN** `status["openrouter_credit"]["reconciliation_status"]` equals `"UNRECONCILED"`
- **THEN** `status["openrouter_credit"]["last_reconciled_ms"]` is null
- **THEN** `status["openrouter_credit"]["reconciled_balance_usd"]` is null

#### Scenario: Status payload reports measured provenance after successful reconciliation
- **WHEN** `reconcile_openrouter_credits()` succeeds with a valid OpenRouter response
- **THEN** `status["openrouter_credit"]["balance_source"]` equals `"MEASURED_OPENROUTER_API"`
- **THEN** `status["openrouter_credit"]["reconciliation_status"]` equals `"RECONCILED_OK"`
- **THEN** `status["openrouter_credit"]["last_reconciled_ms"]` is an integer timestamp greater than zero
- **THEN** `status["openrouter_credit"]["reconciled_balance_usd"]` is a non-negative float

#### Scenario: MasterOverview renders simulated ledger provenance badge
- **WHEN** the frontend renders the OpenRouter credit card with status containing `balance_source = "SIMULATED_INTERNAL_LEDGER"`
- **THEN** a visible badge displaying `"SIMULATED_INTERNAL_LEDGER"` is rendered within the credit card container

#### Scenario: MasterOverview renders measured live API provenance badge
- **WHEN** the frontend renders the OpenRouter credit card with status containing `balance_source = "MEASURED_OPENROUTER_API"`
- **THEN** a visible badge displaying `"MEASURED_OPENROUTER_API"` is rendered within the credit card container

## ADDED Requirements

### Requirement: Live OpenRouter credit balance probe and fallback

`LLMMonitorAgent` MUST implement a `reconcile_openrouter_credits(self, timeout_sec: float = 3.0) -> Dict[str, Any]` method that queries `GET https://openrouter.ai/api/v1/credits` with an `Authorization: Bearer <OPENROUTER_API_KEY>` HTTP header when `OPENROUTER_API_KEY` is present, non-empty, and not a known placeholder (`"your_..."` or `"sk-or-v1-placeholder"`). When the HTTP probe returns status 200 OK with valid JSON containing finite numbers for `data.total_credits` and `data.total_usage`, `openrouter_balance_usd` and `reconciled_balance_usd` MUST be updated to `round(max(0.0, total_credits - total_usage), 4)`, `balance_source` MUST transition to `"MEASURED_OPENROUTER_API"`, `last_reconciled_ms` MUST record the evaluation timestamp, and the method MUST return a dictionary with `reconciliation_status: "RECONCILED_OK"`, `balance_source: "MEASURED_OPENROUTER_API"`, `openrouter_balance_usd`, `last_reconciled_ms`, and `reason: "Reconciliation successful"`. When `OPENROUTER_API_KEY` is unset, empty, or a placeholder, `reconcile_openrouter_credits` MUST NOT perform a network request and MUST return a dictionary with `reconciliation_status: "SKIPPED_NO_API_KEY"`, `balance_source: "SIMULATED_INTERNAL_LEDGER"`, `openrouter_balance_usd`, `last_reconciled_ms`, and a descriptive reason. When the HTTP probe fails, times out, returns a non-200 status, or returns malformed or non-finite JSON, `reconcile_openrouter_credits` MUST NOT raise an unhandled exception; it MUST preserve the existing `openrouter_balance_usd`, set `balance_source` to `"SIMULATED_INTERNAL_LEDGER"` while preserving `last_reconciled_ms` and `reconciled_balance_usd` from the last successful probe, and return a dictionary with `reconciliation_status: "RECONCILE_FAILED"`, `balance_source: "SIMULATED_INTERNAL_LEDGER"`, `openrouter_balance_usd`, `last_reconciled_ms`, and the failure reason.

#### Scenario: Successful live API probe updates credit balance and provenance
- **WHEN** `OPENROUTER_API_KEY` is configured and `GET https://openrouter.ai/api/v1/credits` responds with HTTP 200 and `{"data": {"total_credits": 15.50, "total_usage": 5.25}}`
- **THEN** `openrouter_balance_usd` is updated to `10.25`
- **THEN** `balance_source` transitions to `"MEASURED_OPENROUTER_API"`, `reconciliation_status` is `"RECONCILED_OK"`, and `last_reconciled_ms` is recorded

#### Scenario: Unset or placeholder API key bypasses network probe and reports skipped status
- **WHEN** `OPENROUTER_API_KEY` is empty, unset, or set to `"your_openrouter_api_key_here"`
- **THEN** `reconcile_openrouter_credits` executes no external network request
- **THEN** `openrouter_balance_usd` is unchanged, `balance_source` is `"SIMULATED_INTERNAL_LEDGER"`, and the response reports `reconciliation_status = "SKIPPED_NO_API_KEY"`

#### Scenario: Upstream HTTP error or timeout preserves balance and returns failure status
- **WHEN** the live probe times out after 3.0 seconds or the server responds with HTTP 502 Bad Gateway
- **THEN** `reconcile_openrouter_credits` handles the error without raising an exception
- **THEN** `openrouter_balance_usd` remains unchanged, `balance_source` is `"SIMULATED_INTERNAL_LEDGER"`, and the response reports `reconciliation_status = "RECONCILE_FAILED"`

#### Scenario: Malformed or non-finite JSON payload fails safe without mutating balance
- **WHEN** the API returns HTTP 200 with malformed JSON or `{"data": {"total_credits": "NaN", "total_usage": 0.0}}`
- **THEN** `openrouter_balance_usd` is not modified
- **THEN** the response reports `reconciliation_status = "RECONCILE_FAILED"` with a description of the validation failure

#### Scenario: Probe failure following prior successful probe preserves balance and reports failure status
- **WHEN** a successful reconciliation established `openrouter_balance_usd = 10.25` and `last_reconciled_ms = 1700000000000`, and a subsequent probe fails due to a network timeout
- **THEN** `openrouter_balance_usd` remains `10.25`
- **THEN** `balance_source` reverts to `"SIMULATED_INTERNAL_LEDGER"`
- **THEN** `reconciliation_status` is `"RECONCILE_FAILED"`
- **THEN** `last_reconciled_ms` remains `1700000000000`

### Requirement: On-demand reconciliation endpoint in control plane

The control-plane application in `backend/server.py` MUST expose an HTTP `POST /api/v1/openrouter/reconcile` endpoint that triggers `LLMMonitorAgent.reconcile_openrouter_credits()`. The endpoint MUST return HTTP 200 containing the structured reconciliation result dictionary with `openrouter_balance_usd`, `balance_source`, `reconciliation_status`, `last_reconciled_ms`, and `reason`. When `ROBOTRADER_API_TOKEN` is configured in the environment, the endpoint MUST enforce bearer token authentication.

#### Scenario: Operator invokes on-demand reconciliation endpoint successfully
- **WHEN** an operator sends a valid POST request to `/api/v1/openrouter/reconcile` while upstream OpenRouter returns valid credit metrics
- **THEN** the endpoint returns HTTP 200 with `balance_source = "MEASURED_OPENROUTER_API"`, `reconciliation_status = "RECONCILED_OK"`, and the reconciled balance

#### Scenario: Upstream failure during on-demand reconciliation returns structured fallback without server error
- **WHEN** an operator sends a POST request to `/api/v1/openrouter/reconcile` while OpenRouter is unreachable
- **THEN** the endpoint returns HTTP 200 with `reconciliation_status = "RECONCILE_FAILED"`, `balance_source = "SIMULATED_INTERNAL_LEDGER"`, and the preserved balance

### Requirement: Out-of-band settlement metadata on approved refills

Every approved refill event generated by `LLMMonitorAgent.trigger_openrouter_refill` MUST record explicit settlement metadata in both the return dictionary and the recorded `refill_history` entry. When `balance_source` is `"MEASURED_OPENROUTER_API"`, `settlement_mode` MUST be set to `"OPERATOR_OUT_OF_BAND_INTENT"`, indicating that programmatic payment execution is not supported by OpenRouter and requires manual out-of-band operator funding. When `balance_source` is `"SIMULATED_INTERNAL_LEDGER"`, `settlement_mode` MUST be set to `"SIMULATED_LEDGER_INCREMENT"`. In addition, every approved refill MUST include a deterministic and unique `settlement_receipt_id` formatted as `or-refill-<timestamp_ms>-<counter>` where `<counter>` is a three-digit or longer monotonic positive integer counter tracking total approved refills in the instance lifetime.

#### Scenario: Refill under measured provenance records out-of-band operator intent settlement
- **WHEN** `balance_source` is `"MEASURED_OPENROUTER_API"` and a refill is approved by `HardRiskGate`
- **THEN** the resulting refill event records `"settlement_mode": "OPERATOR_OUT_OF_BAND_INTENT"`
- **THEN** the resulting refill event records a `"settlement_receipt_id"` starting with `"or-refill-"`

#### Scenario: Refill under simulated provenance records simulated ledger increment settlement
- **WHEN** `balance_source` is `"SIMULATED_INTERNAL_LEDGER"` and a refill is approved by `HardRiskGate`
- **THEN** the resulting refill event records `"settlement_mode": "SIMULATED_LEDGER_INCREMENT"`
- **THEN** the resulting refill event records a `"settlement_receipt_id"` starting with `"or-refill-"`

#### Scenario: Consecutive approved refills receive unique and incrementing receipt identifiers
- **WHEN** two consecutive refills are approved at timestamps `1700000001000` and `1700000002000`
- **THEN** the first event has `"settlement_receipt_id": "or-refill-1700000001000-001"`
- **THEN** the second event has `"settlement_receipt_id": "or-refill-1700000002000-002"`

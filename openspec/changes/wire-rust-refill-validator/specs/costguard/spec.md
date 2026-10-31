## ADDED Requirements

### Requirement: Refill validation delegates to authoritative Rust HardRiskGate

`HardRiskGate::validate_inference_refill` in `engine-rs` MUST evaluate all inference credit refills in the following exact canonical order:
1. Kill switch: if `kill_switch_active` is true, reject with status `rejected_kill_switch`.
2. Realized trading PnL: if `realized_trading_pnl_usd <= 0.0` or is non-finite (`NaN`, `+Inf`, `-Inf`), reject with status `rejected_no_realized_profit`.
3. Single refill bounds: if `requested_usd <= 0.0` or `requested_usd > 25.0` or is non-finite, reject with status `rejected`.
4. Profit-share cap: if `requested_usd > (realized_trading_pnl_usd * 0.10) + 1e-6`, reject with status `rejected_exceeds_profit_share`.
5. Low-watermark threshold: if `force` is false and `current_balance_usd > low_watermark_usd`, skip with status `skipped_sufficient_balance`.
6. Rolling 24-hour epoch cap: if `epoch_refilled_usd + requested_usd > max_epoch_refill_usd`, reject with status `rejected_epoch_cap`.

When all six checks pass, the gate MUST return an approved verdict with status `refilled` and the approved dollar amount. `LLMMonitorAgent.trigger_openrouter_refill` in `backend/agents/monitor.py` MUST delegate validation to `HardRiskGate` (via `robotrader-node --validate-refill`) when the binary is present. If the Rust validator invocation fails unexpectedly, is missing, or exits non-zero, the Python monitor MUST fail closed by returning `rejected_validator_unavailable` and MUST NOT mutate credit balance or epoch refilled totals. Every refill event appended to the refill history MUST record `validator: "RUST_HARD_RISK_GATE"`.

#### Scenario: Active kill switch rejects refill in Rust gate
- **WHEN** `kill_switch_active` is true in the Rust risk gate and a `$4.00` refill is requested with `$100.00` realized PnL and `$1.00` current balance
- **THEN** the validator returns status `rejected_kill_switch` with `approved = false`
- **THEN** credit balance and epoch refilled total remain unchanged

#### Scenario: Non-positive or non-finite realized PnL rejects refill
- **WHEN** `realized_trading_pnl_usd` is `-$5.00`, `$0.00`, or non-finite, and a `$4.00` refill is requested
- **THEN** the validator returns status `rejected_no_realized_profit` with `approved = false`
- **THEN** credit balance and epoch refilled total remain unchanged

#### Scenario: Out-of-bounds requested amount rejects refill
- **WHEN** `requested_usd` is `$0.00`, `-$1.00`, `$25.01`, or non-finite
- **THEN** the validator returns status `rejected` with `approved = false`
- **THEN** credit balance and epoch refilled total remain unchanged

#### Scenario: Profit share violation rejects refill
- **WHEN** `requested_usd` is `$10.00` and `realized_trading_pnl_usd` is `$50.00`, so the requested amount exceeds the 10% profit share limit of `$5.00`
- **THEN** the validator returns status `rejected_exceeds_profit_share` with `approved = false`
- **THEN** credit balance and epoch refilled total remain unchanged

#### Scenario: Sufficient balance skips non-forced refill
- **WHEN** `force` is false, `current_balance_usd` is `$3.00`, and `low_watermark_usd` is `$2.00`
- **THEN** the validator returns status `skipped_sufficient_balance` with `approved = false`
- **THEN** credit balance is not incremented and no refill event is recorded

#### Scenario: Forced refill bypasses watermark check when profitable
- **WHEN** `force` is true, `current_balance_usd` is `$3.00`, `low_watermark_usd` is `$2.00`, `realized_trading_pnl_usd` is `$100.00`, and `requested_usd` is `$4.00`
- **THEN** the validator returns status `refilled` with `approved = true` and `approved_usd = 4.00`
- **THEN** credit balance increases by `$4.00`

#### Scenario: Epoch cap violation rejects refill
- **WHEN** `epoch_refilled_usd` is `$23.00`, `requested_usd` is `$4.00`, and `max_epoch_refill_usd` is `$25.00`
- **THEN** the validator returns status `rejected_epoch_cap` with `approved = false`
- **THEN** credit balance and epoch refilled total remain unchanged

#### Scenario: Valid refill passes all checks and stamps Rust validator provenance
- **WHEN** all gate conditions are satisfied and a `$4.00` refill is authorized by the Rust validator
- **THEN** the result status is `refilled`, credit balance increases by `$4.00`, and the recorded refill history event contains `"validator": "RUST_HARD_RISK_GATE"`

#### Scenario: Validator execution failure fails closed
- **WHEN** the Rust validator binary fails to execute or exits unexpectedly
- **THEN** `trigger_openrouter_refill` returns status `rejected_validator_unavailable`
- **THEN** credit balance and epoch refilled total remain unchanged

### Requirement: Node CLI exposes authoritative refill validator

The `robotrader-node` binary MUST support a `--validate-refill <json>` command-line option that invokes `HardRiskGate::validate_inference_refill` and prints a deterministic JSON response to stdout. The CLI input JSON MUST accept `requested_usd` (number), `realized_trading_pnl_usd` (number), `current_balance_usd` (number), `low_watermark_usd` (number), `epoch_refilled_usd` (number), `max_epoch_refill_usd` (number), `force` (boolean), and optional `kill_switch_active` (boolean, defaulting to false). If the argument is missing, contains unparseable JSON, or lacks mandatory numeric fields, the binary MUST exit with a non-zero exit code (`2`) and print a descriptive error to stderr. On successful evaluation, the binary MUST exit with code 0 and emit a JSON object with keys `approved` (boolean), `status` (string), `reason` (string), and `approved_usd` (number).

#### Scenario: CLI returns approved verdict for valid parameters
- **WHEN** `robotrader-node --validate-refill` is executed with valid JSON parameters where realized PnL is `$100.00`, requested amount is `$5.00`, balance is `$1.00`, watermark is `$2.00`, and epoch spend is `$0.00`
- **THEN** the command exits with code 0 and outputs JSON with `"approved": true`, `"status": "refilled"`, and `"approved_usd": 5.0`

#### Scenario: CLI returns rejection verdict for exceeding profit share
- **WHEN** `robotrader-node --validate-refill` is executed with valid JSON parameters where realized PnL is `$20.00` and requested amount is `$5.00`
- **THEN** the command exits with code 0 and outputs JSON with `"approved": false`, `"status": "rejected_exceeds_profit_share"`, and `"approved_usd": 0.0`

#### Scenario: CLI returns skip verdict for sufficient balance
- **WHEN** `robotrader-node --validate-refill` is executed with valid JSON parameters where `force` is false and balance `$3.00` exceeds watermark `$2.00`
- **THEN** the command exits with code 0 and outputs JSON with `"approved": false`, `"status": "skipped_sufficient_balance"`, and `"approved_usd": 0.0`

#### Scenario: CLI exits non-zero on malformed JSON payload
- **WHEN** `robotrader-node --validate-refill` is executed with invalid JSON text such as `"{not_valid_json}"`
- **THEN** the command exits with code 2 and outputs an error message on stderr

### Requirement: Ledger scanning hardens against malformed JSON and non-numeric tokens

`LLMMonitorAgent._scan_ledger` in `backend/agents/monitor.py` MUST defensively validate every decoded JSON line from the transcript ledger files (`transcript_ledger.jsonl` and rotated `.1` segments). Any line that decodes to a non-dictionary JSON value (including integers, floats, lists, strings, booleans, and null) MUST be skipped without raising `AttributeError`. Any line where `prompt_tokens`, `completion_tokens`, or `cost_usd` cannot be converted to finite numbers (including non-numeric strings, `NaN`, `+Inf`, and `-Inf`) MUST be skipped without raising `ValueError` or `TypeError`. Valid entries preceding or succeeding malformed lines MUST be processed and hydrated into the rolling spend window normally.

#### Scenario: Non-dict JSON entries are skipped without exception
- **WHEN** the ledger contains lines with primitive JSON values such as `"42"`, `"[1, 2, 3]"`, `"true"`, `"\"raw text\""`, or `"null"` alongside valid entries
- **THEN** `_scan_ledger` skips the non-dictionary lines cleanly without raising `AttributeError`
- **THEN** all valid entries in the file contribute to the spend window

#### Scenario: Non-numeric and non-finite token or cost entries are skipped without exception
- **WHEN** a ledger entry contains `"prompt_tokens": "unparsed"`, `"cost_usd": "NaN"`, or `"cost_usd": Infinity`
- **THEN** `_scan_ledger` skips the corrupted entry cleanly without raising `ValueError`
- **THEN** non-finite cost values do not pollute `total_cost_usd`

#### Scenario: Valid entries around malformed lines are preserved in spend window
- **WHEN** a ledger contains a valid entry for `$1.25`, followed by a corrupt line `"123"`, followed by a valid entry for `$2.50`
- **THEN** hydration completes with exactly 2 hydrated calls and a total hydrated cost of `$3.75`

### Requirement: OpenRouter credit status and UI display simulated ledger provenance

`LLMMonitorAgent.get_status()` MUST include `balance_source: "SIMULATED_INTERNAL_LEDGER"` within the `openrouter_credit` status object. Neither the API nor the UI MAY represent the credit balance as queried from a live OpenRouter `/api/v1/credits` endpoint. The frontend `MasterOverview.jsx` component MUST display a visible provenance badge labeled `"SIMULATED_INTERNAL_LEDGER"` within the OpenRouter credit card.

#### Scenario: Status payload reports simulated internal ledger provenance
- **WHEN** `LLMMonitorAgent.get_status()` is called on an active monitor agent
- **THEN** `status["openrouter_credit"]["balance_source"]` equals `"SIMULATED_INTERNAL_LEDGER"`

#### Scenario: MasterOverview renders simulated ledger provenance badge
- **WHEN** the frontend renders the OpenRouter credit card with status containing `balance_source = "SIMULATED_INTERNAL_LEDGER"`
- **THEN** a visible badge displaying `"SIMULATED_INTERNAL_LEDGER"` is rendered within the credit card container

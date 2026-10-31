# costguard Specification

## Purpose
TBD - created by archiving change fix-costguard-python-gate. Update Purpose after archive.
## Requirements
### Requirement: The CostGuard receives its measured PnL source by injection

`LLMMonitorAgent` MUST accept a state-store source at construction, defaulting to none. `OrchestratorAgent` MUST inject the same store instance it uses for its own state, including a per-test store, and no module-global store MAY be used as the measured source. The automatic path MUST call `measured_realized_pnl_usd()` on the injected instance. When no source is injected, the automatic path MUST perform no refill and the operator path MUST return `rejected_no_pnl_source`, both without mutating state.

#### Scenario: The orchestrator injects its own store instance

- **WHEN** an orchestrator is constructed with a store whose measured realized PnL is `-$10.00` while a different process-global store reports `$100.00`, and usage brings the credit balance to the low watermark
- **THEN** no refill occurs
- **THEN** the credit balance and epoch refilled total are unchanged

#### Scenario: The automatic path performs no refill without a measured source

- **WHEN** no state store is injected and usage recording brings the credit balance to or below the low watermark
- **THEN** no refill event is appended to the refill history
- **THEN** the credit balance and epoch refilled total are unchanged

#### Scenario: The operator path rejects a missing measured source

- **WHEN** the REST refill endpoint is served by a `CostGuard` with no state store injected
- **THEN** the result is `rejected_no_pnl_source`
- **THEN** the credit balance and epoch refilled total are unchanged

#### Scenario: Construction succeeds without a state store

- **WHEN** a `CostGuard` is constructed with no state store
- **THEN** construction completes without an error
- **THEN** `get_status()` returns a status payload

### Requirement: Every refill path requires a measured realized PnL

The refill entry point MUST require a realized trading PnL argument. A call that omits it MUST raise `TypeError` before any state mutation. The operator path MUST obtain the value from the injected store's measured helper, and the automatic path MUST obtain it from the same helper. The measured helper MUST treat a null `realized_pnl_usd` row as no contribution and MUST return `0.0` when no retained row is non-null.

#### Scenario: A call without a realized PnL raises before mutating state

- **WHEN** a caller invokes the refill entry point without a realized trading PnL
- **THEN** the call raises `TypeError`
- **THEN** the credit balance, epoch refilled total, and refill history are unchanged

#### Scenario: The operator path uses the measured helper

- **WHEN** the REST refill endpoint is called with `force = true` and the injected store's measured realized PnL is `-$10.00`
- **THEN** the result is `rejected_no_realized_profit`
- **THEN** the rejection reason reports `-$10.00`

#### Scenario: Null execution rows do not fabricate profit

- **WHEN** every retained live execution row has a null `realized_pnl_usd`
- **THEN** the measured realized PnL supplied to the gate is `$0.00`
- **THEN** the refill is rejected

### Requirement: A refill requires strictly positive realized profit

Every refill, automatic or operator-triggered, MUST be rejected when the measured realized PnL is zero or negative. A rejected automatic refill MUST leave the credit balance, the epoch refilled total, and the refill history unchanged. A rejected operator refill MUST return `rejected_no_realized_profit`. Neither rejection MAY append an event to the refill history.

#### Scenario: Negative measured PnL on the automatic path performs no refill

- **WHEN** usage recording brings the credit balance to or below the low watermark and the measured realized PnL is `-$10.00`
- **THEN** the credit balance and epoch refilled total are unchanged
- **THEN** no event is appended to the refill history

#### Scenario: Zero measured PnL on the automatic path performs no refill

- **WHEN** usage recording brings the credit balance to or below the low watermark and the measured realized PnL is `$0.00`
- **THEN** the credit balance and epoch refilled total are unchanged
- **THEN** no event is appended to the refill history

#### Scenario: Negative measured PnL on the operator path is rejected

- **WHEN** the REST refill endpoint is called with `force = true` and the measured realized PnL is `-$0.01`
- **THEN** the result is `rejected_no_realized_profit`
- **THEN** the credit balance is unchanged

#### Scenario: A rejection does not consume epoch headroom

- **WHEN** a refill is rejected for zero or negative PnL
- **THEN** the epoch refilled total is unchanged
- **THEN** a subsequent refill backed by positive measured PnL can use the full configured epoch cap

### Requirement: Profit-share and epoch caps apply on every path

Every refill, automatic or operator-triggered, MUST be rejected when its amount exceeds 10% of the measured realized PnL, when its amount is outside the fixed single-refill bound `(0, $25.00]`, or when adding it to the epoch refilled total would exceed the configured epoch cap. The epoch cap MUST be resolved from `OPENROUTER_MAX_EPOCH_REFILL_USD` with a default of `$25.00`; the single-refill bound is fixed and distinct from that configurable cap.

#### Scenario: The automatic amount above the profit share is rejected

- **WHEN** the automatic refill amount is `$10.00` and the measured realized PnL is `$50.00`, so the 10% share is `$5.00`
- **THEN** the result is `rejected_exceeds_profit_share`
- **THEN** the credit balance is unchanged

#### Scenario: The automatic amount within every cap refills

- **WHEN** the automatic refill amount is `$4.00`, the measured realized PnL is `$100.00`, and the epoch refilled total is `$0.00`
- **THEN** the result is `refilled`
- **THEN** the credit balance increases by exactly `$4.00` and the epoch refilled total becomes `$4.00`

#### Scenario: The configured epoch cap blocks a refill at the default threshold

- **WHEN** `OPENROUTER_MAX_EPOCH_REFILL_USD` is unset, the epoch refilled total is `$23.00`, and the requested amount is `$4.00`
- **THEN** the result is `rejected_epoch_cap`
- **THEN** the credit balance is unchanged

#### Scenario: A raised configured epoch cap allows the same refill

- **WHEN** `OPENROUTER_MAX_EPOCH_REFILL_USD` is `$40.00`, the epoch refilled total is `$23.00`, and the requested amount is `$4.00`
- **THEN** the result is `refilled`
- **THEN** the epoch refilled total becomes `$27.00`

#### Scenario: A single-refill amount outside the bound is rejected

- **WHEN** a refill is requested for `$0.00` or for `$25.01`
- **THEN** the result is `rejected`
- **THEN** the credit balance is unchanged

### Requirement: No fabricated profit floor

No refill decision MAY substitute a minimum, floor, or default for the measured realized PnL. The value evaluated by the gate MUST be the measured value verbatim: a negative measured value MUST remain negative, a zero measured value MUST remain zero, and a positive measured value MUST NOT be raised to a larger constant.

#### Scenario: A negative measured value is evaluated unchanged

- **WHEN** the measured realized PnL is `-$10.00`
- **THEN** the rejection reason reports `-$10.00`
- **THEN** the rejection reason does not report any larger positive amount

#### Scenario: A zero measured value is evaluated unchanged

- **WHEN** the measured realized PnL is `$0.00`
- **THEN** the gate evaluates `$0.00` and rejects the refill
- **THEN** no positive default is substituted

#### Scenario: A small positive measured value is not raised

- **WHEN** the measured realized PnL is `$4.00` and a `$1.00` refill is requested
- **THEN** the result is `rejected_exceeds_profit_share`
- **THEN** the gate does not treat the PnL as a larger floor value

### Requirement: Force bypasses only the low-watermark check

The operator `force` flag MUST bypass only the credit-balance-versus-low-watermark check. It MUST NOT bypass the measured-PnL gate, the profit-share cap, the single-refill bound, the epoch cap, or the kill-switch check.

#### Scenario: A forced refill above the watermark is allowed with positive profit

- **WHEN** the credit balance is above the low watermark, `force = true`, the measured realized PnL is `$100.00`, and the requested amount is `$4.00`
- **THEN** the result is `refilled`
- **THEN** the credit balance increases by `$4.00`

#### Scenario: Force does not bypass the profit gate

- **WHEN** the credit balance is above the low watermark, `force = true`, and the measured realized PnL is `-$10.00`
- **THEN** the result is `rejected_no_realized_profit`

#### Scenario: Force does not bypass the profit-share cap

- **WHEN** the credit balance is above the low watermark, `force = true`, the measured realized PnL is `$4.00`, and the requested amount is `$1.00`
- **THEN** the result is `rejected_exceeds_profit_share`

### Requirement: Refills are refused while the kill switch is active

No refill MAY execute while the injected store reports `kill_switch_active = true`, regardless of `force`, measured PnL, or remaining caps. The automatic path MUST perform no refill, and the operator path MUST return `rejected_kill_switch`; both MUST leave the credit balance, epoch refilled total, and refill history unchanged. When the kill switch is inactive, the remaining gate checks apply unchanged.

#### Scenario: The automatic path performs no refill under an active kill switch

- **WHEN** the injected store reports `kill_switch_active = true`, the measured realized PnL is `$100.00`, and usage brings the credit balance to the low watermark
- **THEN** the credit balance and epoch refilled total are unchanged
- **THEN** no event is appended to the refill history

#### Scenario: The operator path rejects a forced refill under an active kill switch

- **WHEN** the injected store reports `kill_switch_active = true` and the REST refill endpoint is called with `force = true`
- **THEN** the result is `rejected_kill_switch`
- **THEN** the credit balance is unchanged

#### Scenario: An inactive kill switch lets the gate proceed

- **WHEN** the injected store reports `kill_switch_active = false`, the measured realized PnL is `$100.00`, and the balance is at the low watermark
- **THEN** the refill is evaluated against the profit-share and epoch caps
- **THEN** a within-cap amount is refilled

### Requirement: Daily spend is a rolling 24-hour window

`CostGuard` MUST compute daily spend as the sum of per-call costs whose age is strictly less than `86,400,000` ms at the evaluation instant. An entry whose age is exactly `86,400,000` ms or greater MUST NOT contribute. The observable field `total_cost_usd` MUST be the derived total of that window and MUST NOT be independently assignable. The window MUST be maintained and evaluated independently of Redis: with `REDIS_URL` unset, usage recording, reported spend, `budget_exhausted`, and thinking-depth selection MUST all use the same window.

#### Scenario: Spend older than 24 hours is excluded

- **WHEN** a `$4.00` call is recorded and evaluated again `86,400,001` ms later
- **THEN** the reported daily spend is `$0.00`
- **THEN** `budget_exhausted` is false for a `$5.00` daily budget

#### Scenario: The 24-hour boundary is exclusive

- **WHEN** a call is evaluated at age `86,399,999` ms and again at age `86,400,000` ms
- **THEN** the call contributes at the first instant
- **THEN** the call does not contribute at the second instant

#### Scenario: The window works without Redis

- **WHEN** `REDIS_URL` is unset and a `$1.50` call is recorded
- **THEN** the reported daily spend is `$1.50`
- **THEN** no Redis connection is required for the value to be correct

#### Scenario: A long-lived process recovers its budget after rollover

- **WHEN** cumulative usage reached the `$5.00` daily budget and `86,400,000` ms have elapsed since the oldest call
- **THEN** the rolling daily spend falls below the budget
- **THEN** `budget_exhausted` becomes false without a process restart

#### Scenario: Thinking depth recovers after rollover

- **WHEN** the process was in `DETERMINISTIC_LOCK` and every call in the window has aged out
- **THEN** `get_thinking_depth()` returns `DEEP_THESIS`

#### Scenario: The reported total is the window, not lifetime spend

- **WHEN** a `$4.00` call is recorded, the window rolls past it, and a `$1.00` call is recorded
- **THEN** `total_cost_usd` is `$1.00`
- **THEN** it is not `$5.00`

### Requirement: Ledger hydration is injectable, lazy, and bounded

`hydrate_from_ledger` MUST remain available and MUST accept an injectable ledger path. `CostGuard` construction MUST accept that path, with `COSTGUARD_LEDGER_PATH` as an environment override and `backend/data/transcript_ledger.jsonl` as the production default resolved relative to the module, never the process working directory. Construction MUST perform zero ledger reads; hydration MUST run lazily on the first daily-spend access or on an explicit call. Hydration MUST stream the active ledger and, when present, the most recent rotated segment `<name>.1`, retaining only entries younger than `86,400,000` ms, and MUST NOT buffer an entire file. The per-entry cost MUST be `max(entry cost_usd, computed cost from model and token counts)`. Repeated hydration MUST replace the window, not append duplicate entries. The test suite MUST inject an isolated ledger path so a developer ledger cannot alter the suite's initial spend.

#### Scenario: Construction performs no ledger read

- **WHEN** a `CostGuard` is constructed with a ledger path whose read raises an error
- **THEN** construction completes without an error
- **THEN** the error is observable only when daily spend is first accessed or `hydrate_from_ledger` is called

#### Scenario: An isolated ledger path blocks a developer ledger

- **WHEN** a developer ledger at the production default contains `$50.00` of in-window spend and a `CostGuard` is constructed with an isolated empty path
- **THEN** the reported daily spend is `$0.00`

#### Scenario: The default path does not depend on the working directory

- **WHEN** a `CostGuard` is constructed from a working directory other than the repository root without a ledger path
- **THEN** the resolved default ledger path is the module-anchored `backend/data/transcript_ledger.jsonl`

#### Scenario: The rotated segment contributes in-window entries

- **WHEN** an in-window `$2.00` entry is in the most recent rotated segment `<name>.1` and the active file is empty
- **THEN** hydration contributes `$2.00` to the window

#### Scenario: The authoritative cost is the larger of recorded and computed

- **WHEN** a ledger entry records `cost_usd = $0.01` and its model and token counts compute to `$1.00`
- **THEN** hydration contributes `$1.00`

#### Scenario: Ledger entries outside the window are ignored

- **WHEN** the ledger contains one entry aged `86,399,999` ms and one aged `86,400,000` ms
- **THEN** hydration contributes only the younger entry

#### Scenario: Repeated hydration does not double count

- **WHEN** `hydrate_from_ledger` is invoked twice against the same ledger contents
- **THEN** the reported daily spend after the second invocation equals the value after the first

#### Scenario: A missing ledger leaves spend at zero

- **WHEN** the injected ledger path does not exist
- **THEN** the reported daily spend is `$0.00`
- **THEN** hydration completes without an error

### Requirement: The low watermark has one backend-owned value

The low watermark MUST be a single backend value resolved from `OPENROUTER_LOW_WATERMARK_USD`, defaulting to `$2.00`. The status payload MUST expose it as `openrouter_credit.low_watermark_usd`. The automatic trigger and the non-forced operator path MUST compare the credit balance against that same value; a forced operator refill is exempt from the comparison only, as specified by the force requirement. The frontend MUST render the value received from the backend and MUST display an em dash (`—`) when the field is absent.

#### Scenario: The status exposes the default watermark

- **WHEN** `OPENROUTER_LOW_WATERMARK_USD` is unset
- **THEN** `cost_guard.openrouter_credit.low_watermark_usd` is `2.00`

#### Scenario: The status and the automatic trigger share the configured value

- **WHEN** `OPENROUTER_LOW_WATERMARK_USD` is `3.50`
- **THEN** the status reports `3.50`
- **THEN** an automatic evaluation at balance `3.50` reaches the refill gate and at balance `3.51` it does not

#### Scenario: The UI renders the backend watermark

- **WHEN** the status reports `low_watermark_usd = 2.00`
- **THEN** the OpenRouter card displays `$2.00`
- **THEN** it does not display `$5.00`

#### Scenario: The UI renders an em dash for a missing watermark

- **WHEN** the status omits `low_watermark_usd`
- **THEN** the OpenRouter card displays `—` for the threshold
- **THEN** it does not display a numeric threshold

### Requirement: Auto-refill status labels are truthful

The status payload MUST describe auto-refill exactly as it operates. When `auto_refill_enabled` is true, `auto_wallet_refill` MUST be `ENABLED_PROFIT_GATED` and the pre-existing `auto_refill_policy` MUST be `PROFIT_GATED_CAPPED_BY_ORCHESTRATOR`. When `auto_refill_enabled` is false, both fields MUST be `DISABLED`. The status MUST NOT report `DISABLED_BY_SECURITY_POLICY` for `auto_wallet_refill` while the automatic path is enabled.

#### Scenario: The enabled status is truthful

- **WHEN** `auto_refill_enabled` is true
- **THEN** `auto_wallet_refill` is `ENABLED_PROFIT_GATED`
- **THEN** `auto_refill_policy` is `PROFIT_GATED_CAPPED_BY_ORCHESTRATOR`

#### Scenario: The disabled status is truthful

- **WHEN** `auto_refill_enabled` is false
- **THEN** `auto_wallet_refill` is `DISABLED`
- **THEN** `auto_refill_policy` is `DISABLED`

#### Scenario: A rejected automatic refill does not change the label

- **WHEN** an automatic refill is rejected for negative measured PnL and `auto_refill_enabled` is true
- **THEN** `auto_wallet_refill` remains `ENABLED_PROFIT_GATED`
- **THEN** the status does not claim that auto-refill is disabled by security policy

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


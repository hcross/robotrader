## ADDED Requirements

### Requirement: Every refill path requires a measured realized PnL

Every OpenRouter credit refill entry point MUST require a realized trading PnL value supplied by the caller. The automatic path, reached from usage recording, MUST supply the state store's measured realized PnL for the attributed live executions. The operator path, reached through the REST refill endpoint, MUST supply that same measured value. A refill call that supplies no realized PnL MUST NOT execute and MUST NOT change the credit balance, the epoch refilled total, or the refill history.

#### Scenario: The automatic path supplies the measured store value

- **WHEN** usage recording brings the credit balance to or below the low watermark and the state store's measured realized PnL is `-$10.00`
- **THEN** the automatic refill evaluation receives `-$10.00`
- **THEN** the result is `rejected_no_realized_profit` and the credit balance is unchanged

#### Scenario: The operator path supplies the measured store value

- **WHEN** the REST refill endpoint is called while the state store's measured realized PnL is `-$10.00`
- **THEN** the refill evaluation receives `-$10.00`
- **THEN** the result is `rejected_no_realized_profit` and the credit balance is unchanged

#### Scenario: A refill call without a realized PnL cannot execute

- **WHEN** a caller invokes the refill entry point without a realized PnL value
- **THEN** the call fails before mutating any state
- **THEN** the credit balance, epoch refilled total, and refill history are unchanged

#### Scenario: Null execution rows do not fabricate profit

- **WHEN** every retained live execution row has a null `realized_pnl_usd`
- **THEN** the measured realized PnL supplied to the gate is `$0.00`
- **THEN** no refill is approved

### Requirement: A refill requires strictly positive realized profit

The refill gate MUST reject every refill when the measured realized PnL is zero or negative. A rejected refill MUST NOT increase the credit balance, MUST NOT increase the epoch refilled total, and MUST NOT append a successful refill event. The rejection reason MUST state the evaluated PnL value.

#### Scenario: Negative measured PnL on the automatic path performs no refill

- **WHEN** usage recording brings the credit balance to or below the low watermark and the measured realized PnL is `-$10.00`
- **THEN** no refill event is appended to the refill history
- **THEN** the credit balance and the epoch refilled total are unchanged

#### Scenario: Zero measured PnL on the automatic path performs no refill

- **WHEN** usage recording brings the credit balance to or below the low watermark and the measured realized PnL is `$0.00`
- **THEN** no refill event is appended to the refill history
- **THEN** the credit balance and the epoch refilled total are unchanged

#### Scenario: Negative measured PnL on the operator path performs no refill

- **WHEN** the REST refill endpoint is called with a force flag and the measured realized PnL is `-$0.01`
- **THEN** the result is `rejected_no_realized_profit`
- **THEN** the credit balance is unchanged

#### Scenario: A rejection does not consume epoch headroom

- **WHEN** a refill is rejected for zero or negative PnL
- **THEN** the epoch refilled total is unchanged
- **THEN** a subsequent refill backed by positive measured PnL can use the full epoch cap

### Requirement: Profit-share and epoch caps apply on every path

Every refill, automatic or operator-triggered, MUST be rejected when its amount exceeds 10% of the measured realized PnL, when its amount is outside `(0, $25.00]`, or when adding it to the epoch refilled total would exceed the epoch cap of `$25.00`. The automatic path MUST be subject to exactly the same three limits as the operator path.

#### Scenario: The automatic amount above the profit share is rejected

- **WHEN** the automatic refill amount is `$10.00` and the measured realized PnL is `$50.00`, so the 10% share is `$5.00`
- **THEN** the result is `rejected_exceeds_profit_share`
- **THEN** the credit balance is unchanged

#### Scenario: The automatic amount within every cap refills

- **WHEN** the automatic refill amount is `$4.00`, the measured realized PnL is `$100.00`, and the epoch refilled total is `$0.00`
- **THEN** the result is `refilled`
- **THEN** the credit balance increases by exactly `$4.00` and the epoch refilled total becomes `$4.00`

#### Scenario: The epoch cap blocks the automatic path

- **WHEN** the epoch refilled total is `$23.00`, the automatic amount is `$4.00`, and the epoch cap is `$25.00`
- **THEN** the result is `rejected_epoch_cap`
- **THEN** the credit balance is unchanged

#### Scenario: A single-refill amount outside the bound is rejected

- **WHEN** a refill is requested for `$0.00` or for `$25.01`
- **THEN** the result is `rejected`
- **THEN** the credit balance is unchanged

### Requirement: No fabricated profit floor

No refill decision MAY substitute a minimum, floor, or default for the measured realized PnL. The value evaluated by the gate MUST be the measured value verbatim: a negative measured value MUST remain negative, a zero measured value MUST remain zero, and a positive measured value MUST NOT be raised to a larger constant.

#### Scenario: A negative measured value is evaluated unchanged

- **WHEN** the measured realized PnL is `-$10.00`
- **THEN** the rejection reason reports `$-10.00`
- **THEN** the rejection reason does not report any larger positive amount

#### Scenario: A zero measured value is evaluated unchanged

- **WHEN** the measured realized PnL is `$0.00`
- **THEN** the gate evaluates `$0.00` and rejects the refill
- **THEN** no positive default is substituted

#### Scenario: A small positive measured value is not raised

- **WHEN** the measured realized PnL is `$4.00` and a `$1.00` refill is requested
- **THEN** the result is `rejected_exceeds_profit_share`
- **THEN** the gate does not treat the PnL as a larger floor value

### Requirement: Daily spend is a rolling 24-hour window

`CostGuard` MUST compute daily spend as the sum of per-call costs whose age is strictly less than `86,400,000` ms at the evaluation instant. An entry whose age is exactly `86,400,000` ms or greater MUST NOT contribute to daily spend. The window MUST be maintained and evaluated independently of Redis: with `REDIS_URL` unset, usage recording, reported spend, `budget_exhausted`, and thinking-depth selection MUST all use that same window.

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
- **THEN** no Redis connection attempt is required for the value to be correct

#### Scenario: A long-lived process recovers its budget after rollover

- **WHEN** cumulative usage reached the `$5.00` daily budget and `86,400,000` ms have elapsed since the oldest call
- **THEN** the rolling daily spend falls below the budget
- **THEN** `budget_exhausted` becomes false without a process restart

#### Scenario: Thinking depth recovers after rollover

- **WHEN** the process was in `DETERMINISTIC_LOCK` and every call in the window has aged out
- **THEN** `get_thinking_depth()` returns `DEEP_THESIS`

### Requirement: Ledger hydration seeds the rolling window

`hydrate_from_ledger` MUST remain available. When invoked, it MUST replace the rolling window with the costs of ledger entries younger than `86,400,000` ms and MUST NOT append duplicate entries on a repeated invocation. `CostGuard` initialization MUST invoke hydration from `backend/data/transcript_ledger.jsonl` whenever that file exists, regardless of whether `REDIS_URL` is set, so that a process restart reconstructs the prior 24-hour spend.

#### Scenario: A restart without Redis reconstructs the window

- **WHEN** the transcript ledger contains a `$2.00` entry that is one hour old, `REDIS_URL` is unset, and a new `CostGuard` is constructed
- **THEN** the reported daily spend is `$2.00`

#### Scenario: Ledger entries outside the window are ignored

- **WHEN** the transcript ledger contains one entry aged `86,399,999` ms and one aged `86,400,000` ms
- **THEN** hydration contributes only the younger entry

#### Scenario: Repeated hydration does not double count

- **WHEN** `hydrate_from_ledger` is invoked twice against the same ledger contents
- **THEN** the reported daily spend after the second invocation equals the value after the first

#### Scenario: A missing ledger leaves spend at zero

- **WHEN** no transcript ledger file exists at initialization
- **THEN** the reported daily spend is `$0.00`
- **THEN** initialization completes without an error

### Requirement: The low watermark has one backend-owned value

The low watermark MUST be a single backend value resolved from `OPENROUTER_LOW_WATERMARK_USD`, defaulting to `$2.00`. The status payload MUST expose it as `openrouter_credit.low_watermark_usd`, and every refill trigger MUST compare the credit balance against that same value. The frontend MUST render the value received from the backend and MUST NOT substitute a literal threshold when the field is absent.

#### Scenario: The status exposes the default watermark

- **WHEN** `OPENROUTER_LOW_WATERMARK_USD` is unset
- **THEN** `cost_guard.openrouter_credit.low_watermark_usd` is `2.00`

#### Scenario: The status and the trigger share the configured value

- **WHEN** `OPENROUTER_LOW_WATERMARK_USD` is `3.50`
- **THEN** the status reports `3.50`
- **THEN** a balance of `3.50` is at the trigger threshold and a balance of `3.51` is not

#### Scenario: The UI renders the backend watermark

- **WHEN** the status reports `low_watermark_usd = 2.00`
- **THEN** the OpenRouter card displays `$2.00`
- **THEN** it does not display `$5.00`

#### Scenario: The UI does not fabricate a missing watermark

- **WHEN** the status omits `low_watermark_usd`
- **THEN** the OpenRouter card shows an unavailable marker or omits the threshold text
- **THEN** it does not display a numeric threshold

### Requirement: Auto-refill status labels are truthful

The status payload MUST describe auto-refill exactly as it operates. When `auto_refill_enabled` is true, `auto_wallet_refill` MUST be `ENABLED_PROFIT_GATED` and `auto_refill_policy` MUST be `PROFIT_GATED_CAPPED_BY_ORCHESTRATOR`. When `auto_refill_enabled` is false, both fields MUST be `DISABLED`. The status MUST NOT report `DISABLED_BY_SECURITY_POLICY` for `auto_wallet_refill` while the automatic path is enabled.

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

### Requirement: The automatic profit gate is regression-tested

The backend test suite MUST include an automatic-path test that records usage with the credit balance at or below the low watermark and a measured realized PnL of `-$10.00`, and MUST assert that no refill event is recorded and the balance is unchanged. The suite MUST also cover a zero-PnL automatic attempt and a positive control that refills within the profit-share and epoch caps.

#### Scenario: The negative-PnL automatic test passes

- **WHEN** the backend test suite runs
- **THEN** the automatic-path test with `-$10.00` measured PnL passes
- **THEN** removing the PnL from the automatic path makes that test fail

#### Scenario: The zero-PnL automatic test passes

- **WHEN** the backend test suite runs
- **THEN** the automatic-path test with `$0.00` measured PnL passes
- **THEN** no refill event is recorded

#### Scenario: The positive control refills

- **WHEN** the automatic-path test uses a measured PnL of `$100.00` and an amount within every cap
- **THEN** the test observes exactly one refill event and an increased balance

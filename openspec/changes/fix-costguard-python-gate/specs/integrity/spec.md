## MODIFIED Requirements

### Requirement: Refill gating consumes null-safe measured PnL only

The OpenRouter refill callers — `POST /api/v1/openrouter/refill` and the Master reflection — MUST sum only non-null `MEASURED` leaf `realized_pnl_usd` values, MUST treat a `null` as no contribution, and MUST NOT pass a `null` to a numeric conversion. They MUST NOT add the simulated `paper_model` `live_pnl_usd`. The measured total passed to the profit gate MUST be the actual sum, including `0.0` when no measured profit exists; the `max(125.0, …)` floor MUST NOT be applied. The automatic path, the daily rolling window, the low-watermark constants, and the measured-source injection are specified by the `costguard` capability. The unused Rust validator, the real `/credits` balance source, and routing the gate through Rust remain out of scope for issue #5.

#### Scenario: Null leaf PnL does not raise in the refill path

- **WHEN** a fresh install has every leaf `realized_pnl_usd` equal to `null` and a client calls `POST /api/v1/openrouter/refill`
- **THEN** the endpoint returns a structured response and does not raise `TypeError`
- **THEN** the measured total passed to the gate is `0.0`

#### Scenario: Refill sum excludes simulated PnL

- **WHEN** measured leaf PnL is `10.00` and simulated paper PnL is `100.00`
- **THEN** the profit gate receives `10.00`, not `110.00`

#### Scenario: No fabricated profit floor

- **WHEN** measured realized PnL is `0.00` and a refill is requested
- **THEN** the gate receives `0.00` and rejects with `rejected_no_realized_profit`
- **THEN** it does not receive `125.0` and does not authorise a `$12.50` refill

#### Scenario: Negative measured profit is rejected

- **WHEN** measured realized PnL is `-4.00`
- **THEN** the gate rejects the refill and reports the negative measured value
- **THEN** no floor replaces it

## ADDED Requirements

### Requirement: Complete AssetOverride field parity

The Rust `AssetOverride` SHALL expose all eleven keys published by the Python `AssetOverride`: `catalyst_score`, `bias`, `max_leverage`, `support_zone_usd`, `resistance_zone_usd`, `invalidation_price_usd`, `entry_obi_threshold`, `max_rsi_long`, `min_rsi_short`, `take_profit_bps`, and `stop_loss_bps`. The seven mechanical-rule keys absent from the current Rust type SHALL be `Option<T>` with `#[serde(default)]`, and decoding MUST NOT discard any of them. Re-encoding a decoded envelope SHALL emit all eleven keys, using JSON `null` for an absent optional value.

#### Scenario: All eleven keys survive a decode and re-encode

- **WHEN** a Python envelope sets all eleven `AssetOverride` fields to distinct non-default values and the Rust implementation decodes and re-encodes it
- **THEN** the re-encoded override contains exactly the eleven keys
- **THEN** every re-encoded value equals the corresponding Python value

#### Scenario: Absent optional rule decodes

- **WHEN** a Python envelope omits `entry_obi_threshold` from an override
- **THEN** Rust decoding succeeds and the field reads as absent rather than as a decode error or a dropped key

#### Scenario: Null optional zone is preserved

- **WHEN** `support_zone_usd` is `null` in the Python JSON
- **THEN** the re-encoded JSON contains `support_zone_usd` with value `null`

#### Scenario: No field is silently dropped

- **WHEN** any one of the eleven fields is changed to a distinct value
- **THEN** the Rust re-encoded JSON changes for that field and no other field changes

### Requirement: Strict policy decoding

The policy types `PolicyEnvelope`, `PodAllocation`, and `AssetOverride` SHALL use `#[serde(deny_unknown_fields)]` or an equivalent strict decoder. A JSON key not declared by the target type MUST cause deserialisation to fail with an error that identifies the offending key, and unknown policy keys MUST NOT be ignored.

#### Scenario: Unknown AssetOverride key is rejected

- **WHEN** a policy JSON contains an `AssetOverride` key not declared by Rust, for example `trailing_stop_bps`
- **THEN** decoding returns an error naming `trailing_stop_bps`
- **THEN** no `PolicyEnvelope` value is produced

#### Scenario: Unknown PodAllocation key is rejected

- **WHEN** a `PodAllocation` object contains a key not declared by Rust
- **THEN** decoding returns an error naming that key

#### Scenario: Unknown top-level PolicyEnvelope key is rejected

- **WHEN** the envelope object contains a key not declared at the top level
- **THEN** decoding returns an error naming that key

#### Scenario: Complete known envelope is accepted

- **WHEN** the envelope contains exactly the six declared top-level keys, the five declared `PodAllocation` keys, and the eleven declared `AssetOverride` keys
- **THEN** decoding succeeds and no field is reported as unknown

### Requirement: Fail-loud CLI policy ingestion

When `robotrader-node` is invoked with `--policy-json`, it SHALL use the supplied envelope if strict decoding succeeds. If decoding fails, the process MUST exit with a non-zero status, MUST write an error message naming the offending key to stderr, and MUST NOT write a backtest summary to stdout or execute with the default envelope.

#### Scenario: Malformed policy exits non-zero

- **WHEN** `robotrader-node --policy-json` receives an envelope with an unknown or missing key
- **THEN** the exit status is non-zero
- **THEN** stderr names the offending key and stdout contains no backtest summary

#### Scenario: Valid policy is used

- **WHEN** `robotrader-node --policy-json` receives a strictly valid envelope
- **THEN** the exit status is zero
- **THEN** the backtest runs with the supplied envelope rather than the default envelope

### Requirement: RSI input on MarketEvent

`MarketEvent::OrderbookTick` SHALL carry a required `rsi_14` field containing the 14-period RSI computed by the warm path. Serialisation and deserialisation MUST preserve the value, and an `OrderbookTick` JSON object without `rsi_14` MUST fail to deserialise.

#### Scenario: rsi_14 survives a round-trip

- **WHEN** an `OrderbookTick` with `rsi_14 = 46.5` is serialised and deserialised
- **THEN** the decoded `rsi_14` equals 46.5

#### Scenario: Missing rsi_14 is rejected

- **WHEN** an `OrderbookTick` JSON object omits `rsi_14`
- **THEN** deserialisation fails and no `MarketEvent` is produced

### Requirement: Momentum pod applies envelope mechanical rules

When the envelope contains an `AssetOverride` for the event symbol, `MomentumPod` SHALL apply that override's mechanical rules to entry decisions and emitted `OrderIntent` values. The OBI gate MUST require `|OBI| >= entry_obi_threshold` for both directions, with an absent value resolving to 0.08. The long RSI guard MUST require `rsi_14 <= max_rsi_long`, with an absent value resolving to 70.0. The short RSI guard MUST require `rsi_14 >= min_rsi_short`, with an absent value resolving to 30.0. A long entry MUST require `mid_price >= support_zone_usd` when that field is present, and a short entry MUST require `mid_price <= resistance_zone_usd` when that field is present. A long entry MUST require `mid_price > invalidation_price_usd` when that field is present, and a short entry MUST require `mid_price < invalidation_price_usd` when that field is present. The emitted intent MUST set `take_profit_pct = take_profit_bps / 100.0` and `stop_loss_pct = stop_loss_bps / 100.0`, with absent values resolving to 45.0 and 30.0 respectively. When the symbol has no `AssetOverride`, the pod MUST preserve its configured OBI threshold and ATR-derived TP/SL values and MUST NOT apply RSI, support, resistance, or invalidation gates. When any applicable rule fails, the pod MUST emit no `OrderIntent` for that event and direction.

#### Scenario: Override OBI threshold blocks a marginal signal

- **WHEN** an override sets `entry_obi_threshold = 0.35` and a long setup has OBI 0.30 with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: Long RSI guard blocks an overbought entry

- **WHEN** an override sets `max_rsi_long = 55.0` and a long setup has `rsi_14 = 60.0` with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: Long RSI boundary is inclusive

- **WHEN** an override sets `max_rsi_long = 55.0` and a long setup has `rsi_14 = 55.0` with every other entry condition passing
- **THEN** a long `OrderIntent` is emitted

#### Scenario: Short RSI guard blocks an oversold entry

- **WHEN** an override sets `min_rsi_short = 45.0` and a short setup has `rsi_14 = 40.0` with every other entry condition passing
- **THEN** no short `OrderIntent` is emitted

#### Scenario: Support gate blocks a long below support

- **WHEN** an override sets `support_zone_usd = 150.0` and the mid-price is 149.9 with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: Resistance gate blocks a short above resistance

- **WHEN** an override sets `resistance_zone_usd = 160.0` and the mid-price is 160.1 with every other entry condition passing
- **THEN** no short `OrderIntent` is emitted

#### Scenario: Invalidation gate blocks a long at the level

- **WHEN** an override sets `invalidation_price_usd = 145.0` and the mid-price is 145.0 with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: TP and SL distances come from the envelope

- **WHEN** an override sets `take_profit_bps = 120.0` and `stop_loss_bps = 60.0` and an entry passes every gate
- **THEN** the emitted intent has `take_profit_pct = 1.2` and `stop_loss_pct = 0.6`

#### Scenario: Absent numeric rule uses the Python default

- **WHEN** an override omits `entry_obi_threshold` and a long setup has OBI 0.05 with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted because the effective threshold is 0.08

#### Scenario: No override keeps the pod defaults

- **WHEN** the symbol has no `AssetOverride` and a long setup has OBI 0.23, `rsi_14 = 80.0`, and every other entry condition passing
- **THEN** a long `OrderIntent` is emitted with the pod's configured OBI threshold and ATR-derived TP/SL values
- **THEN** no RSI gate is applied

### Requirement: Cross-language round-trip contract test

A test SHALL exist that runs without Redis, network access, or a live exchange and that builds a `PolicyEnvelope` JSON from the Python implementation containing at least one `AssetOverride` with all eleven keys set to distinct non-default values, decodes that JSON with the Rust implementation, re-encodes it, and asserts that the envelope key set, each override key set of exactly eleven keys, and every value are identical between the Python JSON and the Rust re-encoded JSON. The test MUST fail if any `AssetOverride` field is removed from the Rust type or dropped during decoding.

#### Scenario: Field sets and values match across languages

- **WHEN** the round-trip test runs on the distinct-value fixture
- **THEN** the envelope and override key sets are identical between Python and Rust
- **THEN** every value matches

#### Scenario: Dropped field is detected

- **WHEN** a Rust `AssetOverride` field is removed or marked to skip serialisation
- **THEN** the round-trip test fails

#### Scenario: Test is offline and part of the standard suites

- **WHEN** the standard Rust and Python test commands run without Redis or network access
- **THEN** the round-trip test executes and passes

### Requirement: Single-sourced safe-baseline TTL

The safe-baseline envelope TTL SHALL have exactly one authoritative definition in the repository. The Rust and Python `safe_baseline` envelopes MUST both expose `ttl_seconds = 900` resolved from that definition, and neither runtime MUST restate the safe-baseline TTL as an independent literal. A repository check MUST fail when a second authoritative definition exists.

#### Scenario: Rust baseline TTL is 900

- **WHEN** the Rust safe-baseline envelope is built
- **THEN** its `ttl_seconds` equals 900

#### Scenario: Python baseline TTL is 900

- **WHEN** the Python safe-baseline envelope is built
- **THEN** its `ttl_seconds` equals 900

#### Scenario: Runtimes agree with the single source

- **WHEN** the Rust and Python baseline TTLs are compared with the authoritative definition
- **THEN** both equal that definition

#### Scenario: Duplicate definition is rejected

- **WHEN** a second hard-coded safe-baseline TTL literal is introduced in either runtime
- **THEN** the repository check fails

### Requirement: Hand-maintained contract with executable drift detection

This change MUST NOT introduce generated schema artifacts, codegen build steps, or schema-generation dependencies. The contract SHALL remain a hand-maintained mirror, and drift MUST be detected by the cross-language round-trip test. Generated-schema codegen is deferred to a follow-up ADR.

#### Scenario: No codegen is introduced

- **WHEN** the change's dependency manifests and generated artifacts are inspected
- **THEN** no schema codegen dependency, codegen build step, or generated contract file is present

#### Scenario: Drift is caught by the test

- **WHEN** one field's Rust serialisation diverges from the Python value
- **THEN** the cross-language round-trip test fails

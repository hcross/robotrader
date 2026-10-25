## ADDED Requirements

### Requirement: Complete AssetOverride field parity

The Rust `AssetOverride` SHALL expose all eleven keys published by the Python `AssetOverride`: `catalyst_score`, `bias`, `max_leverage`, `support_zone_usd`, `resistance_zone_usd`, `invalidation_price_usd`, `entry_obi_threshold`, `max_rsi_long`, `min_rsi_short`, `take_profit_bps`, and `stop_loss_bps`. The eight mechanical-rule keys absent from the current Rust type — `support_zone_usd`, `resistance_zone_usd`, `invalidation_price_usd`, `entry_obi_threshold`, `max_rsi_long`, `min_rsi_short`, `take_profit_bps`, and `stop_loss_bps` — SHALL be `Option<T>` with `#[serde(default)]`, and decoding MUST NOT discard any of them. `catalyst_score` (f64), `bias` (`DirectionalBias`), and `max_leverage` (f64) SHALL remain required non-`Option` fields. Re-encoding a decoded envelope SHALL emit all eleven keys, using JSON `null` for an absent optional value.

#### Scenario: All eleven keys survive a decode and re-encode

- **WHEN** a Python envelope sets all eleven `AssetOverride` fields to distinct non-default values and the Rust implementation decodes and re-encodes it
- **THEN** the re-encoded override contains exactly the eleven keys
- **THEN** every re-encoded value equals the corresponding Python value

#### Scenario: Only the required keys decode

- **WHEN** an envelope JSON contains only `catalyst_score`, `bias`, and `max_leverage` for an override
- **THEN** decoding succeeds
- **THEN** the eight optional fields read as absent

#### Scenario: Absent optional rule decodes

- **WHEN** an envelope JSON from a non-Python or older producer omits `entry_obi_threshold`
- **THEN** Rust decoding succeeds and the field reads as absent rather than as a decode error or a dropped key
- **THEN** the Python `to_dict()` path is unaffected because it always emits all eleven keys

#### Scenario: Missing required field is rejected

- **WHEN** an envelope JSON omits `catalyst_score`, `bias`, or `max_leverage`
- **THEN** decoding fails and the error names the missing field

#### Scenario: Null optional zone is preserved

- **WHEN** `support_zone_usd` is `null` in the Python JSON
- **THEN** the re-encoded JSON contains `support_zone_usd` with value `null`

#### Scenario: No field is silently dropped

- **WHEN** any one of the eleven fields is changed to a distinct value
- **THEN** the Rust re-encoded JSON changes for that field and no other field changes

### Requirement: Strict policy decoding

The policy types `PolicyEnvelope`, `PodAllocation`, and `AssetOverride` SHALL use `#[serde(deny_unknown_fields)]` or an equivalent strict decoder. A JSON key not declared by the target type MUST cause deserialisation to fail with an error that identifies the offending key, and unknown policy keys MUST NOT be ignored. `MarketEvent` and `OnChainTokenSafety` SHALL retain serde's default tolerant behaviour and MUST NOT receive `deny_unknown_fields` in this change.

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

#### Scenario: Unknown event field remains tolerated

- **WHEN** a `MarketEvent` or `OnChainTokenSafety` JSON object contains a key not declared by Rust
- **THEN** decoding succeeds and every declared field retains its value

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

### Requirement: Optional RSI input on MarketEvent

`MarketEvent::OrderbookTick` SHALL carry an optional `rsi_14` field (`Option<f64>` with `#[serde(default)]`) holding the 14-period RSI supplied by the tick producer. Serialisation and deserialisation MUST preserve a present value, and an absent `rsi_14` MUST decode as absent rather than fail decoding. This change adds no Python warm-path producer or transport for `MarketEvent::OrderbookTick`; today only the Rust backtest fixtures produce that event.

#### Scenario: rsi_14 survives a round-trip

- **WHEN** an `OrderbookTick` with `rsi_14 = 46.5` is serialised and deserialised
- **THEN** the decoded `rsi_14` equals 46.5

#### Scenario: Absent rsi_14 decodes

- **WHEN** an `OrderbookTick` JSON object omits `rsi_14`
- **THEN** deserialisation succeeds and the decoded `rsi_14` is absent
- **THEN** no decode error is produced

### Requirement: Momentum pod applies envelope mechanical rules

When the envelope contains an `AssetOverride` for the event symbol, `MomentumPod` SHALL apply that override's mechanical rules to entry decisions and emitted `OrderIntent` values. The OBI gate MUST require `|OBI| >= entry_obi_threshold` for both directions, with an absent value resolving to 0.08. The long RSI guard MUST require `rsi_14 <= max_rsi_long` when `rsi_14` is present, with an absent `max_rsi_long` resolving to 70.0. The short RSI guard MUST require `rsi_14 >= min_rsi_short` when `rsi_14` is present, with an absent `min_rsi_short` resolving to 30.0. When `rsi_14` is absent and the symbol has an override, the RSI guard MUST be reported as `RSI=INACTIVE` in the emitted `OrderIntent.rationale`. A long entry MUST require `mid_price >= support_zone_usd` when that field is present, and a short entry MUST require `mid_price <= resistance_zone_usd` when that field is present. A long entry MUST require `mid_price > invalidation_price_usd` when that field is present, and a short entry MUST require `mid_price < invalidation_price_usd` when that field is present. The emitted intent MUST set `take_profit_pct = take_profit_bps / 100.0` and `stop_loss_pct = stop_loss_bps / 100.0`, with absent values resolving to 45.0 and 30.0 respectively. When the symbol has no `AssetOverride`, the pod MUST preserve its configured OBI threshold and ATR-derived TP/SL values and MUST NOT apply RSI, support, resistance, or invalidation gates. When any applicable rule fails, the pod MUST emit no `OrderIntent` for that event and direction. The warm-path paper execution model in `backend/core/state_store.py` MUST use `min_rsi_short` as its short RSI threshold, and the `100.0 - max_rsi_long` derivation MUST NOT remain.

#### Scenario: Override OBI threshold blocks a marginal signal

- **WHEN** an override sets `entry_obi_threshold = 0.35` and a long setup has OBI 0.30 with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: OBI boundary is inclusive

- **WHEN** an override sets `entry_obi_threshold = 0.35` and a long setup has OBI 0.35 with every other entry condition passing
- **THEN** a long `OrderIntent` is emitted

#### Scenario: Long RSI guard blocks an overbought entry

- **WHEN** an override sets `max_rsi_long = 55.0` and a long setup has `rsi_14 = 60.0` with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: Long RSI boundary is inclusive

- **WHEN** an override sets `max_rsi_long = 55.0` and a long setup has `rsi_14 = 55.0` with every other entry condition passing
- **THEN** a long `OrderIntent` is emitted

#### Scenario: Short RSI guard blocks an oversold entry

- **WHEN** an override sets `min_rsi_short = 45.0` and a short setup has `rsi_14 = 40.0` with every other entry condition passing
- **THEN** no short `OrderIntent` is emitted

#### Scenario: Short RSI boundary is inclusive

- **WHEN** an override sets `min_rsi_short = 45.0` and a short setup has `rsi_14 = 45.0` with every other entry condition passing
- **THEN** a short `OrderIntent` is emitted

#### Scenario: RSI guard is reported inactive when rsi_14 is absent

- **WHEN** an override exists, `rsi_14` is absent, and a long setup passes every other gate
- **THEN** a long `OrderIntent` is emitted
- **THEN** its `rationale` contains `RSI=INACTIVE`

#### Scenario: Support gate blocks a long below support

- **WHEN** an override sets `support_zone_usd = 150.0` and the mid-price is 149.9 with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: Support boundary is inclusive

- **WHEN** an override sets `support_zone_usd = 150.0` and the mid-price is 150.0 with every other entry condition passing
- **THEN** a long `OrderIntent` is emitted

#### Scenario: Resistance gate blocks a short above resistance

- **WHEN** an override sets `resistance_zone_usd = 160.0` and the mid-price is 160.1 with every other entry condition passing
- **THEN** no short `OrderIntent` is emitted

#### Scenario: Resistance boundary is inclusive

- **WHEN** an override sets `resistance_zone_usd = 160.0` and the mid-price is 160.0 with every other entry condition passing
- **THEN** a short `OrderIntent` is emitted

#### Scenario: Invalidation gate blocks a long at the level

- **WHEN** an override sets `invalidation_price_usd = 145.0` and the mid-price is 145.0 with every other entry condition passing
- **THEN** no long `OrderIntent` is emitted

#### Scenario: Invalidation gate blocks a short at the level

- **WHEN** an override sets `invalidation_price_usd = 145.0` and a short setup has a mid-price of 145.0 with every other entry condition passing
- **THEN** no short `OrderIntent` is emitted

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

#### Scenario: Warm-path short RSI uses min_rsi_short

- **WHEN** the warm-path paper model evaluates a short under an override with `min_rsi_short = 45.0` and `max_rsi_long = 70.0`
- **THEN** the short-side RSI exhaustion threshold applied is 45.0, not 30.0
- **THEN** the hot path and the warm path use the same short RSI threshold for that override

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

The safe-baseline TTL SHALL be declared exactly once, as the named key `SAFE_BASELINE_TTL_SECONDS` in a single machine-readable contract file, with value `900`. The Rust and Python `safe_baseline()` constructors MUST resolve `ttl_seconds` from that declaration and MUST NOT carry an independent safe-baseline literal. `PolicyEnvelope.from_dict`'s generic decode default and `default_active()`'s TTL MUST either resolve from the same declaration or be listed as explicit exemptions by the repository check. A repository check MUST fail, naming the duplicate file, when a second declaration of `SAFE_BASELINE_TTL_SECONDS` appears.

#### Scenario: Rust baseline resolves the named key

- **WHEN** the Rust safe-baseline envelope is built
- **THEN** its `ttl_seconds` equals the value of `SAFE_BASELINE_TTL_SECONDS`
- **THEN** that value equals 900

#### Scenario: Python baseline resolves the named key

- **WHEN** the Python safe-baseline envelope is built
- **THEN** its `ttl_seconds` equals the value of `SAFE_BASELINE_TTL_SECONDS`
- **THEN** that value equals 900

#### Scenario: Exempt defaults do not trip the check

- **WHEN** `PolicyEnvelope.from_dict` and `default_active()` retain 900 as generic envelope defaults
- **THEN** the repository check passes because neither is a safe-baseline declaration

#### Scenario: Duplicate declaration is rejected

- **WHEN** a second file declares `SAFE_BASELINE_TTL_SECONDS`
- **THEN** the repository check exits non-zero and names the duplicate file

### Requirement: Hand-maintained contract with executable drift detection

This change MUST NOT introduce generated schema artifacts, codegen build steps, or schema-generation dependencies. The contract SHALL remain a hand-maintained mirror, and drift MUST be detected by the cross-language round-trip test. Generated-schema codegen is deferred to a follow-up ADR.

#### Scenario: No codegen is introduced

- **WHEN** the change's dependency manifests and generated artifacts are inspected
- **THEN** no schema codegen dependency, codegen build step, or generated contract file is present

#### Scenario: Drift is caught by the test

- **WHEN** one field's Rust serialisation diverges from the Python value
- **THEN** the cross-language round-trip test fails

# control-plane-security Delta Specification

## ADDED Requirements

### Requirement: Detached canonical HMAC-SHA256 policy envelope signing and verification

The control plane and engine MUST support detached canonical HMAC-SHA256 policy envelope authentication. Canonical serialization of a `PolicyEnvelope` MUST sort all mapping keys recursively and emit compact UTF-8 JSON without insignificant whitespace, preserving the strict six-key wire shape (`envelope_id`, `issued_at_ms`, `ttl_seconds`, `global_regime`, `pod_allocations`, and `asset_overrides`). Both Python (`backend/core/schemas.py`) and Rust (`engine-rs/crates/common/src/lib.rs`) MUST implement `compute_policy_hmac(envelope, secret_key) -> str` and `verify_policy_hmac(envelope, signature_hex, secret_key) -> bool`. For any valid `PolicyEnvelope` and shared secret key, both language implementations MUST produce identical 64-character lowercase hexadecimal digests. Verification MUST compare digests using constant-time equality checks and MUST return false if the signature string length is not 64, contains non-hexadecimal characters, or if any field within the envelope has been modified. The detached signature container MUST be encapsulated as a `SignedPolicyBundle` carrying the `PolicyEnvelope` under `policy`, the 64-character hex signature under `signature`, and a string identifier under `key_id`.

#### Scenario: Cross-language digest parity for identical policy envelopes
- **WHEN** the same `PolicyEnvelope` structure and secret key are passed to `compute_policy_hmac` in Python and in Rust
- **THEN** both implementations produce the exact same 64-character lowercase hexadecimal string

#### Scenario: Verification succeeds with authentic envelope and matching key
- **WHEN** `verify_policy_hmac` evaluates an authentic `PolicyEnvelope` against the signature computed with the corresponding secret key
- **THEN** the verification result is true

#### Scenario: Verification fails when an envelope field is modified
- **WHEN** an envelope's `issued_at_ms`, `global_regime`, `ttl_seconds`, or any allocation value is altered after signing
- **THEN** `verify_policy_hmac` returns false

#### Scenario: Verification fails when an incorrect secret key is provided
- **WHEN** `verify_policy_hmac` evaluates a valid signature using a different secret key than the one used during signing
- **THEN** the verification result is false

#### Scenario: Verification fails when the signature string is malformed
- **WHEN** `verify_policy_hmac` is provided a signature string that is empty, truncated, contains non-hex characters, or is not exactly 64 characters
- **THEN** the verification result is false

### Requirement: State store policy signature enforcement and safe baseline fallback

`HybridStateStore` (module-level instance `state_store`) in `backend/core/state_store.py` MUST sign every issued `PolicyEnvelope` upon creation or mutation using `compute_policy_hmac` with the secret key retrieved from the `ROBOTRADER_POLICY_HMAC_KEY` environment variable (defaulting to the deterministic development key `"robotrader-dev-hmac-key"` when unset, empty, or whitespace). The active key identifier MUST be resolved from the `ROBOTRADER_POLICY_KEY_ID` environment variable (defaulting to `"default"` when unset, empty, or whitespace). When persisting state, `HybridStateStore` MUST include `policy_signature` and `policy_key_id` in the serialized snapshot alongside `"policy"`. When restoring state or reading persisted policy, `HybridStateStore` MUST verify `policy_signature` against the active secret key. If the signature is absent, malformed, or fails HMAC verification, `HybridStateStore` MUST reject the persisted policy, log a security violation warning, and set the active policy to `PolicyEnvelope.safe_baseline()` (`safe_baseline_fallback`).

#### Scenario: Issued policy is persisted with a valid signature and key identifier
- **WHEN** `set_policy` is invoked with a newly issued `PolicyEnvelope`
- **THEN** the persisted state payload contains `policy_signature` as a valid 64-character hex string and `policy_key_id` equal to the active key identifier

#### Scenario: Default secret key and key ID are utilized when environment variables are unset
- **WHEN** `ROBOTRADER_POLICY_HMAC_KEY` and `ROBOTRADER_POLICY_KEY_ID` are unset or empty and a policy is issued
- **THEN** the policy is signed using the default development key and `policy_key_id` is set to `"default"`

#### Scenario: Explicit key identifier is recorded when configured
- **WHEN** `ROBOTRADER_POLICY_KEY_ID` is set to `"operator-key-2026"` and a policy is issued
- **THEN** the persisted state payload records `policy_key_id: "operator-key-2026"`

#### Scenario: Restoring authentic signed policy adopts the envelope
- **WHEN** persisted state contains a valid `policy` whose `policy_signature` matches the computed HMAC and whose TTL is unexpired
- **THEN** `HybridStateStore` adopts the envelope as the active policy

#### Scenario: Restoring tampered policy content falls back to safe baseline
- **WHEN** persisted state contains a `policy` where any field has been modified without updating `policy_signature`
- **THEN** `HybridStateStore` rejects the envelope and sets the active policy to `safe_baseline_fallback`

#### Scenario: Restoring tampered signature string falls back to safe baseline
- **WHEN** persisted state contains an invalid or modified `policy_signature` string
- **THEN** `HybridStateStore` rejects the envelope and sets the active policy to `safe_baseline_fallback`

### Requirement: Hard risk gate signed envelope validation

`HardRiskGate` in `engine-rs/crates/risk-gate/src/lib.rs` MUST provide `validate_signed_envelope(&mut self, intent: &OrderIntent, portfolio: &PortfolioState, raw_envelope: &PolicyEnvelope, signature_hex: &str, secret_key: &[u8], now_ms: u64) -> Result<ApprovedOrder, RiskRejection>`. The method MUST verify `signature_hex` against `raw_envelope` and `secret_key` using `verify_policy_hmac` before evaluating pod allocations, capital limits, or execution thresholds. If signature verification fails, `validate_signed_envelope` MUST immediately return `Err(RiskRejection::InvalidPolicySignature)` without modifying gate state or evaluating downstream risk checks. The existing `validate` method MUST remain available and preserve backward compatibility for callers that do not supply detached signatures.

#### Scenario: Valid signed envelope passes risk gate authentication
- **WHEN** `validate_signed_envelope` is invoked with an authentic `PolicyEnvelope`, valid `signature_hex`, and matching `secret_key`
- **THEN** signature verification passes and risk gate proceeds to standard allocation and edge evaluations

#### Scenario: Tampered envelope signature fails risk gate with InvalidPolicySignature
- **WHEN** `validate_signed_envelope` is invoked with a modified `PolicyEnvelope` whose content does not match `signature_hex`
- **THEN** the call returns `Err(RiskRejection::InvalidPolicySignature)`
- **THEN** no trade is approved and downstream risk calculations are not performed

#### Scenario: Corrupted signature hex fails risk gate with InvalidPolicySignature
- **WHEN** `validate_signed_envelope` is invoked with an invalid or malformed signature string
- **THEN** the call returns `Err(RiskRejection::InvalidPolicySignature)`

#### Scenario: Existing validate method maintains backward compatibility
- **WHEN** `validate` is invoked directly without signature arguments
- **THEN** the risk gate evaluates the order intent against the raw envelope without requiring signature verification

### Requirement: Active policy published to Redis with explicit TTL expiration

`MinimalRedisClient` in `backend/core/state_store.py` MUST implement `set_with_ex(key: str, value: str, ttl_seconds: int) -> bool` executing the Redis `SET <key> <value> EX <ttl_seconds>` command over the existing zero-dependency socket transport. Whenever a policy is issued or persisted, `HybridStateStore` (module-level instance `state_store`) MUST serialize a `SignedPolicyBundle` containing the active `PolicyEnvelope`, its HMAC `signature`, and `key_id`, and publish it to the Redis key `robotrader:policy:active` with `EX` set to the policy's configured `ttl_seconds`. `HybridStateStore` MUST simultaneously continue to persist the complete application snapshot to `robotrader:v2:state`. Any socket or communication failure during Redis active policy publication MUST be caught and logged without aborting state store operations or raising unhandled exceptions.

#### Scenario: Active policy bundle published with Redis EX TTL
- **WHEN** `HybridStateStore` persists state with an active policy having `ttl_seconds = 900`
- **THEN** `MinimalRedisClient` sends a Redis `SET robotrader:policy:active <bundle_json> EX 900` command
- **THEN** the payload stored in `robotrader:policy:active` is a valid `SignedPolicyBundle` JSON string

#### Scenario: Redis client formats SET command with EX expiration
- **WHEN** `set_with_ex("robotrader:policy:active", payload, 900)` is executed
- **THEN** the RESP wire format transmits arguments `SET`, `robotrader:policy:active`, payload, `EX`, and `900`

#### Scenario: Socket failure during active key publication fails safely
- **WHEN** Redis is unreachable or socket communication fails during active policy publication
- **THEN** `HybridStateStore` catches the exception, logs a warning, and continues in-memory execution without crashing

### Requirement: Actionable kill-switch position flattening contract

`HardRiskGate` in `engine-rs/crates/risk-gate/src/lib.rs` MUST provide `trigger_kill_switch_with_flatten(&mut self, reason: impl Into<String>, portfolio: &PortfolioState, now_ms: u64) -> Vec<OrderIntent>`. The method MUST set `self.kill_switch_active = true`, record `self.kill_switch_reason`, and inspect `portfolio.asset_exposures_usd`. For every entry with non-zero exposure, it MUST emit an opposite-side market flatten `OrderIntent` with `reduce_only = true` (or the reduce-only flag set), where positive exposures generate `Side::Sell` intents and negative exposures generate `Side::Buy` intents. The returned list of `OrderIntent` objects MUST be sorted deterministically in lexicographical order by asset symbol. When `set_kill_switch(True, reason)` on `HybridStateStore` (module-level instance `state_store`) in `backend/core/state_store.py` is invoked, it MUST mark `kill_switch_active = True`, record the reason, and include the generated `kill_switch_flatten_intents` in the returned status dictionary. When `set_kill_switch(False)` is invoked to deactivate the kill switch, `kill_switch_active` MUST be set to `False`, `kill_switch_reason` MUST be cleared to `None`, and `kill_switch_flatten_intents` in the returned status dictionary MUST be an empty list `[]`.

#### Scenario: Triggering kill switch with active positions generates opposite market flatten orders
- **WHEN** `trigger_kill_switch_with_flatten` is invoked with a portfolio having exposure `{"SOL-USDT": 1500.0, "BTC-USDT": -500.0}`
- **THEN** the returned intents contain a `Side::Sell` market order for `SOL-USDT` and a `Side::Buy` market order for `BTC-USDT`
- **THEN** each intent carries `reduce_only = true` and indicates kill-switch flatten rationale

#### Scenario: Triggering kill switch with zero exposures returns an empty intent list
- **WHEN** `trigger_kill_switch_with_flatten` is invoked with a portfolio having zero or empty asset exposures
- **THEN** the method returns an empty vector of order intents
- **THEN** `kill_switch_active` is set to true

#### Scenario: Flatten intents are deterministically ordered by asset symbol
- **WHEN** `trigger_kill_switch_with_flatten` processes exposures for multiple assets in arbitrary insertion order
- **THEN** the emitted `OrderIntent` list is strictly sorted alphabetically by asset symbol

#### Scenario: State store set_kill_switch records flatten intents in status payload
- **WHEN** `HybridStateStore.set_kill_switch(True, "Emergency stop")` is invoked
- **THEN** the returned dictionary contains `kill_switch_active: True`, `kill_switch_reason: "Emergency stop"`, and a `kill_switch_flatten_intents` list

#### Scenario: Deactivating kill switch returns empty flatten intents list
- **WHEN** `HybridStateStore.set_kill_switch(False)` is invoked to reset the kill switch
- **THEN** the returned dictionary contains `kill_switch_active: False`, `kill_switch_reason: null`, and `kill_switch_flatten_intents: []`

#### Scenario: Subsequent trade validation is rejected while kill switch is active
- **WHEN** `validate` or `validate_signed_envelope` is called after `trigger_kill_switch_with_flatten` has been executed
- **THEN** the call returns `Err(RiskRejection::KillSwitchActive)`

## MODIFIED Requirements

### Requirement: Redis persistence contract documentation honesty

`docs/adr/0001-hybrid-quant-agentic-architecture.md` and `README.md` MUST accurately describe the implemented Redis persistence contract: state snapshots are persisted to `robotrader:v2:state` with in-memory fallback, and the active `PolicyEnvelope` is published to `robotrader:policy:active` with native per-key `EX` TTL expiration matching envelope validity. References to Redis Streams or Pub/Sub MUST remain explicitly labelled as future roadmap items rather than implemented architecture.

#### Scenario: ADR-0001 documents state snapshot and marks streams as roadmap
- **WHEN** `docs/adr/0001-hybrid-quant-agentic-architecture.md` is inspected
- **THEN** §4.2 describes `robotrader:v2:state` state snapshots and `robotrader:policy:active` per-key EX expiration as implemented architecture
- **THEN** Redis Streams and Pub/Sub are explicitly distinguished as future roadmap architecture

#### Scenario: README accurately reflects state persistence architecture
- **WHEN** `README.md` is inspected
- **THEN** the IPC & State Bus section describes Redis 7 snapshot persistence and `robotrader:policy:active` EX key expiration without claiming active Redis Streams or Pub/Sub

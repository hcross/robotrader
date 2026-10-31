# policy-ttl Specification

## Purpose
TBD - created by archiving change fix-policy-ttl-heartbeat. Update Purpose after archive.
## Requirements
### Requirement: Live ticks preserve policy issue time

The live testnet worker tick MUST NOT modify the active envelope's `issued_at_ms` or `ttl_seconds`. After any `run_live_testnet_tick()` call — including one that returns early because the exchange is unauthenticated or no pod is active, and one that raises — those two fields MUST equal their values before the call. A live tick MUST NOT issue, renew, or re-stamp a policy envelope. Only an explicit policy issuance, which supplies a newly built envelope to `set_policy`, MAY carry a new `issued_at_ms` and `ttl_seconds`.

#### Scenario: A successful tick leaves the issue time unchanged

- **WHEN** an unexpired envelope issued at `T0` with `ttl_seconds = 900` is active and `run_live_testnet_tick()` completes at wall-clock `T0 + 10_000`
- **THEN** the active envelope's `issued_at_ms` is still `T0`
- **THEN** the active envelope's `ttl_seconds` is still `900`

#### Scenario: An early-return tick leaves the issue time unchanged

- **WHEN** `run_live_testnet_tick()` returns before placing an order because the exchange is not authenticated or because no pod is active
- **THEN** the active envelope's `issued_at_ms` and `ttl_seconds` are unchanged

#### Scenario: A raising tick leaves the issue time unchanged

- **WHEN** `run_live_testnet_tick()` raises before placing an order and the caller catches the exception
- **THEN** the active envelope's `issued_at_ms` and `ttl_seconds` are unchanged

#### Scenario: Repeated ticks cannot outlive the TTL

- **WHEN** an envelope issued at `T0` with `ttl_seconds = 900` is active, the kill switch is inactive, and the live worker executes ticks every 10 seconds across `T0 + 900_000`
- **THEN** at `T0 + 900_001` `get_effective_policy()` returns the safe baseline envelope
- **THEN** no tick has rewritten `issued_at_ms`

### Requirement: Liveness signals are separate from policy authority

A liveness signal that does not itself issue a new envelope MUST NOT extend the active envelope's authority. Any liveness timestamp or heartbeat the warm path records MUST be stored outside `PolicyEnvelope` and MUST NOT be an input to `is_expired`, `get_effective_policy`, or any other expiry calculation. The `PolicyEnvelope` wire shape MUST remain exactly the six existing keys: `envelope_id`, `issued_at_ms`, `ttl_seconds`, `global_regime`, `pod_allocations`, and `asset_overrides`. A liveness signal MUST NOT be serialized into the policy envelope or persisted as policy authority, and it MUST NOT add a Redis key, a field to the persisted state payload, or a REST/WS field.

#### Scenario: A liveness tick does not change the expiry verdict

- **WHEN** `is_expired(now)` and `get_effective_policy(now)` are evaluated for a fixed `now`, before and after a live-worker tick records liveness
- **THEN** both results are identical before and after the tick

#### Scenario: Envelope wire shape is unchanged

- **WHEN** the active envelope is serialized with `to_dict()`
- **THEN** its key set is exactly the six existing keys
- **THEN** no liveness, heartbeat, or freshness field is present

#### Scenario: Liveness after expiry does not revive the envelope

- **WHEN** the active envelope's TTL has elapsed and the live worker records a liveness tick
- **THEN** `get_effective_policy()` still returns `safe_baseline_fallback`

#### Scenario: Liveness state does not alter the persistence shape

- **WHEN** the store persists state after a live-worker tick
- **THEN** the persisted JSON payload has the same key set as before the change
- **THEN** no liveness or heartbeat key is present in the payload or in the nested `policy` object

### Requirement: Expiry boundary semantics are unchanged

`PolicyEnvelope.is_expired(now)` MUST continue to return true if and only if `now` is strictly greater than `issued_at_ms + ttl_seconds * 1000`. At the exact boundary instant the envelope MUST remain effective. This comparison MUST be the only expiry rule applied by `get_effective_policy`, independently of how many live ticks have run.

#### Scenario: The boundary instant is not expired

- **WHEN** an envelope is issued at `T0` with `ttl_seconds = 900`, the kill switch is inactive, and `is_expired(T0 + 900_000)` is evaluated
- **THEN** the result is false
- **THEN** `get_effective_policy(T0 + 900_000)` returns that envelope, not the safe baseline

#### Scenario: One millisecond after the boundary is expired

- **WHEN** the kill switch is inactive and `is_expired(T0 + 900_001)` is evaluated for the same envelope
- **THEN** the result is true
- **THEN** `get_effective_policy(T0 + 900_001)` returns `safe_baseline_fallback`

#### Scenario: Tick count does not alter the boundary

- **WHEN** the live worker has run any number of ticks before the boundary is evaluated
- **THEN** the verdict at `T0 + 900_000` is still false and the verdict at `T0 + 900_001` is still true

### Requirement: Restore preserves the persisted issue time

When the store restores a persisted `PolicyEnvelope` whose `issued_at_ms` is present as a valid positive integer and whose TTL has not elapsed, the restored envelope MUST keep that exact `issued_at_ms`, `envelope_id`, and `ttl_seconds`; the restore instant MUST NOT replace them. A persisted policy object that omits `issued_at_ms`, specifies an explicit `null`, boolean value, non-numeric value, non-positive value (`<= 0`), or is unparseable by `PolicyEnvelope.from_dict` MUST NOT be treated as fresh and MUST NOT leave the store in `default_active`; it MUST immediately set the active policy to `safe_baseline` (`safe_baseline_fallback`).

#### Scenario: A fresh restored envelope keeps its original issue time

- **WHEN** the persisted policy was issued at `T0` with `ttl_seconds = 900` and the store restores it at `T0 + 60_000`
- **THEN** the effective policy's `issued_at_ms` is `T0`, not `T0 + 60_000`
- **THEN** its `envelope_id` and `ttl_seconds` equal the persisted values

#### Scenario: A persist-and-restore round trip preserves the issue time

- **WHEN** an envelope issued at `T0` is persisted and a new store instance restores that payload before the TTL elapses
- **THEN** the restored effective policy carries `issued_at_ms = T0`

#### Scenario: A restored payload without an issue time is not fresh

- **WHEN** the persisted policy object omits `issued_at_ms`
- **THEN** the effective policy is `safe_baseline_fallback`
- **THEN** the missing value is not replaced by the restore instant as policy authority

#### Scenario: Explicit null issue time restores safe baseline

- **WHEN** the persisted policy object contains `issued_at_ms: null`
- **THEN** the effective policy is `safe_baseline_fallback`
- **THEN** the active policy is not left in `default_active`

#### Scenario: Non-numeric issue time restores safe baseline

- **WHEN** the persisted policy object contains `issued_at_ms: "not-a-number"`
- **THEN** the effective policy is `safe_baseline_fallback`
- **THEN** the active policy is not left in `default_active`

#### Scenario: Boolean or non-positive issue time restores safe baseline

- **WHEN** the persisted policy object contains `issued_at_ms: true` or `issued_at_ms: 0` or a negative integer
- **THEN** the effective policy is `safe_baseline_fallback`
- **THEN** the active policy is not left in `default_active`

#### Scenario: Malformed policy payload restores safe baseline

- **WHEN** the persisted policy object has invalid types or missing fields causing `PolicyEnvelope.from_dict` to raise an exception
- **THEN** the effective policy is `safe_baseline_fallback`
- **THEN** the active policy is not left in `default_active`

### Requirement: Restore past TTL starts from the safe baseline

When the store restores a persisted `PolicyEnvelope` whose TTL has elapsed at the restore instant, the store MUST NOT make that envelope the effective policy. The effective policy MUST be `safe_baseline_fallback` with `ttl_seconds` resolved from `SAFE_BASELINE_TTL_SECONDS`. The restore MUST NOT rewrite the stale envelope's `issued_at_ms` to the restore instant and then serve it as fresh.

#### Scenario: A stale restored envelope yields the safe baseline

- **WHEN** the persisted policy was issued at `T0` with `ttl_seconds = 60` and the store restores it at `T0 + 60_001`
- **THEN** `get_effective_policy()` returns an envelope whose `envelope_id` is `safe_baseline_fallback`
- **THEN** `global_regime` is `LOW_VOL_CARRY` and `pod_sniper` is disabled

#### Scenario: A stale restore is not restamped as fresh

- **WHEN** the persisted policy was issued at `T0` with `ttl_seconds = 60` and the store restores it at `T0 + 86_400_000`
- **THEN** the restored envelope is not served with `issued_at_ms` equal to the restore instant
- **THEN** the effective policy is the safe baseline

#### Scenario: The safe baseline TTL comes from the shared contract

- **WHEN** the safe baseline is returned after a stale restore
- **THEN** its `ttl_seconds` equals `SAFE_BASELINE_TTL_SECONDS`
- **THEN** that value equals `900`

### Requirement: Kill-switch behaviour is unchanged

The kill switch MUST continue to take precedence over every expiry and liveness rule. While the kill switch is active, `get_effective_policy` MUST return the all-disabled lockdown envelope regardless of the stored envelope's age or tick count. Deactivating the kill switch MUST NOT renew the stored envelope: if it is still within its TTL it becomes effective again with its original `issued_at_ms`, and if it is expired the effective policy is the safe baseline.

#### Scenario: Active kill switch overrides a fresh envelope

- **WHEN** the kill switch is active and the stored envelope is within its TTL
- **THEN** `get_effective_policy()` returns `kill_switch_lockdown`
- **THEN** every pod is disabled with `capital_weight = 0.0`

#### Scenario: Active kill switch overrides an expired envelope

- **WHEN** the kill switch is active and the stored envelope is past its TTL
- **THEN** `get_effective_policy()` returns `kill_switch_lockdown`

#### Scenario: Deactivation restores an unexpired envelope

- **WHEN** the kill switch is deactivated and the stored envelope issued at `T0` is still within its TTL
- **THEN** the effective policy is that envelope
- **THEN** its `issued_at_ms` is still `T0`

#### Scenario: Deactivation after expiry yields the safe baseline

- **WHEN** the kill switch is deactivated after the stored envelope's TTL has elapsed
- **THEN** `get_effective_policy()` returns `safe_baseline_fallback`


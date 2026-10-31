## MODIFIED Requirements

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

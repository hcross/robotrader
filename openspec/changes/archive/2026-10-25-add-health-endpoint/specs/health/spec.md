## ADDED Requirements

### Requirement: Read-only health endpoint

The backend SHALL expose `GET /api/v1/health` as a read-only endpoint that returns HTTP status 200 and a JSON object whose only top-level fields are `status`, `service`, and `timestamp`. `status` MUST equal the string `ok`; `service` MUST equal the string `robotrader`; the response MUST use the `application/json` content type. The endpoint MUST be reachable without credentials and MUST NOT mutate application state.

#### Scenario: Healthy probe returns the contract

- **WHEN** a client sends `GET /api/v1/health` without credentials
- **THEN** the response has HTTP status 200, content type `application/json`, and exactly the top-level keys `status`, `service`, and `timestamp`
- **THEN** `status` equals `ok` and `service` equals `robotrader`

#### Scenario: Probe payload excludes undeclared data

- **WHEN** a client sends `GET /api/v1/health`
- **THEN** the response body contains no field other than `status`, `service`, and `timestamp`
- **THEN** the body contains no engine metrics, hierarchy, cost-guard, catalyst, or policy data

#### Scenario: Non-GET method is rejected

- **WHEN** a client sends `POST /api/v1/health`, or any method other than `GET`, to that path
- **THEN** the service returns HTTP status 405 and does not build or return a health snapshot

#### Scenario: Repeated probes are idempotent

- **WHEN** a client sends `GET /api/v1/health` twice in succession
- **THEN** both responses have HTTP status 200 with identical `status` and `service` values, and differ only possibly in `timestamp`
- **THEN** neither request writes application state

### Requirement: UTC timestamp freshness

The `timestamp` field MUST be an ISO-8601 UTC instant matching `YYYY-MM-DDTHH:MM:SS` with an optional fractional part and a trailing `Z`. It MUST represent the time the snapshot is built, within 5 seconds of the current UTC clock.

#### Scenario: Timestamp is an ISO-8601 UTC instant

- **WHEN** a client sends `GET /api/v1/health`
- **THEN** `timestamp` matches `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$`
- **THEN** parsing `timestamp` yields a timezone-aware UTC instant

#### Scenario: Timestamp is fresh

- **WHEN** a client sends `GET /api/v1/health`
- **THEN** the absolute difference between the parsed `timestamp` and the current UTC time is at most 5 seconds

### Requirement: Pure, independently testable snapshot

The health snapshot and its route MUST be importable and exercisable by a test process that never imports `backend.server`, starts no background worker or cognitive scheduler, and performs no application I/O: no Redis access, no network call, no state-store read or write, and no configuration read.

#### Scenario: Import and call do not load the heavy server

- **WHEN** a test process imports the health snapshot and route module and exercises the endpoint with a minimal test application
- **THEN** `backend.server` is absent from `sys.modules`
- **THEN** no live state worker, background worker, or cognitive scheduler is started

#### Scenario: Dependency outage does not change the probe

- **WHEN** Redis or the state store is unreachable
- **THEN** `GET /api/v1/health` still returns HTTP status 200 with `status` equal to `ok`
- **THEN** the snapshot performs no Redis or state-store read or write

## ADDED Requirements

### Requirement: CORS configuration adheres to Fetch specification

The control plane FastAPI application MUST configure `CORSMiddleware` using origins parsed from the `CORS_ALLOWED_ORIGINS` environment variable (a comma-separated string of allowed origins, defaulting to `"*"` when unset or whitespace). When `allow_origins` contains `"*"`, `allow_credentials` MUST be `False` to comply with the W3C/WHATWG Fetch specification. When `CORS_ALLOWED_ORIGINS` contains one or more explicit origins (and does not contain `"*"`), `allow_credentials` MUST be `True` to allow credentialed cross-origin requests from configured origins.

#### Scenario: Default CORS configuration disables credentials with wildcard origin

- **WHEN** `CORS_ALLOWED_ORIGINS` is unset, empty, or whitespace
- **THEN** `CORSMiddleware` is configured with `allow_origins=["*"]` and `allow_credentials=False`

#### Scenario: Explicit CORS origins enable credentials

- **WHEN** `CORS_ALLOWED_ORIGINS` is set to `"http://localhost:5173,http://127.0.0.1:5173"`
- **THEN** `CORSMiddleware` is configured with `allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"]` and `allow_credentials=True`

#### Scenario: Explicit wildcard among origins disables credentials

- **WHEN** `CORS_ALLOWED_ORIGINS` is set to `"http://localhost:5173,*"`
- **THEN** `CORSMiddleware` is configured with `allow_credentials=False`

### Requirement: Optional Bearer token authentication on mutating endpoints

When `ROBOTRADER_API_TOKEN` is configured as a non-empty string in the environment, all mutating `POST` endpoints under `/api/v1/` MUST require an `Authorization: Bearer <token>` header matching `ROBOTRADER_API_TOKEN`. Token equality MUST be verified using constant-time string comparison (`hmac.compare_digest`). If the `Authorization` header is missing, does not use the `Bearer` scheme, or contains an invalid token, the endpoint MUST immediately return HTTP `401 Unauthorized` (`{"detail": "Invalid or missing API token"}`) and MUST NOT execute any state mutation or trigger LLM reflection. When `ROBOTRADER_API_TOKEN` is unset or empty, mutating `POST` endpoints MUST remain accessible without an `Authorization` header. Read-only endpoints `GET /api/v1/health` and `GET /api/v1/status` MUST remain accessible without authentication regardless of whether `ROBOTRADER_API_TOKEN` is configured.

#### Scenario: Valid Bearer token allows mutating POST request

- **WHEN** `ROBOTRADER_API_TOKEN` is set to `"secret-token-123"` and a client sends a `POST` request to `/api/v1/risk/kill` with `Authorization: Bearer secret-token-123`
- **THEN** the request is accepted and executes normally

#### Scenario: Missing Authorization header is rejected with 401

- **WHEN** `ROBOTRADER_API_TOKEN` is set to `"secret-token-123"` and a client sends a `POST` request to `/api/v1/risk/kill` without an `Authorization` header
- **THEN** the response status is 401 Unauthorized with detail `Invalid or missing API token`
- **THEN** no state mutation is performed

#### Scenario: Invalid Bearer token is rejected with 401

- **WHEN** `ROBOTRADER_API_TOKEN` is set to `"secret-token-123"` and a client sends a `POST` request to `/api/v1/treasury/deposit` with `Authorization: Bearer wrong-token`
- **THEN** the response status is 401 Unauthorized with detail `Invalid or missing API token`
- **THEN** no deposit or balance modification occurs

#### Scenario: Malformed Authorization scheme is rejected with 401

- **WHEN** `ROBOTRADER_API_TOKEN` is set to `"secret-token-123"` and a client sends a `POST` request with `Authorization: Basic secret-token-123`
- **THEN** the response status is 401 Unauthorized with detail `Invalid or missing API token`

#### Scenario: Unset API token allows unauthenticated requests in local dev

- **WHEN** `ROBOTRADER_API_TOKEN` is unset or empty and a client sends a `POST` request to any `/api/v1/` endpoint without an `Authorization` header
- **THEN** the request is accepted without authentication check

#### Scenario: GET health and status endpoints remain unauthenticated

- **WHEN** `ROBOTRADER_API_TOKEN` is set to `"secret-token-123"` and a client sends a `GET` request to `/api/v1/health` or `/api/v1/status` without an `Authorization` header
- **THEN** the response status is 200 OK without requiring authentication

### Requirement: Redis persistence contract documentation honesty

`docs/adr/0001-hybrid-quant-agentic-architecture.md` and `README.md` MUST accurately describe the implemented Redis persistence contract as a single-key JSON snapshot (`robotrader:v2:state`) with in-memory fallback and application-level TTL checks on restore and access. References to Redis Streams, Pub/Sub, or per-key `EX` expiration MUST be explicitly labelled as future roadmap items rather than implemented architecture.

#### Scenario: ADR-0001 documents state snapshot and marks streams as roadmap

- **WHEN** `docs/adr/0001-hybrid-quant-agentic-architecture.md` is inspected
- **THEN** §4.2 describes `robotrader:v2:state` as a JSON snapshot with in-memory fallback and explicit TTL evaluation
- **THEN** Redis Streams and Pub/Sub are explicitly distinguished as future roadmap architecture

#### Scenario: README accurately reflects state persistence architecture

- **WHEN** `README.md` is inspected
- **THEN** the IPC & State Bus section describes Redis 7 single-key state snapshot persistence with in-memory fallback without claiming active Redis Streams or Pub/Sub

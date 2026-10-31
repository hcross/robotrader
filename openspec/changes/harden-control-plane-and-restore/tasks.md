# Tasks — harden-control-plane-and-restore

> Spec: [`specs/policy-ttl/spec.md`](specs/policy-ttl/spec.md) and [`specs/control-plane-security/spec.md`](specs/control-plane-security/spec.md). Proposal: [`proposal.md`](proposal.md). This list orders the work; the specs define the contract.

## 1. Policy restore fail-safe hardening

- [ ] 1.1 Add test cases to `backend/tests/test_policy_ttl_heartbeat.py` covering explicit `null` issue time, non-numeric issue time (`"not-a-number"`), boolean issue time (`True`), non-positive issue time (`<= 0`), and unparseable policy dictionaries. (covers: "Explicit null issue time restores safe baseline", "Non-numeric issue time restores safe baseline", "Boolean or non-positive issue time restores safe baseline", "Malformed policy payload restores safe baseline")
- [ ] 1.2 Update `HybridStateStore._load_persisted_state` in `backend/core/state_store.py` to validate `issued_at_ms` as a positive integer and fail closed to `PolicyEnvelope.safe_baseline(restore_now_ms)` on any missing, null, wrong-type, non-positive, or unparseable policy payload. (covers: "Restore preserves the persisted issue time")

## 2. Control plane CORS compliance

- [ ] 2.1 Add test cases in `backend/tests/test_control_plane_security.py` verifying CORS headers under default wildcard origins (`allow_credentials=False`), explicit origins (`allow_credentials=True`), and wildcard with explicit origins (`allow_credentials=False`). (covers: "Default CORS configuration disables credentials with wildcard origin", "Explicit CORS origins enable credentials", "Explicit wildcard among origins disables credentials")
- [ ] 2.2 Configure `CORSMiddleware` in `backend/server.py` to parse `CORS_ALLOWED_ORIGINS`, default to `["*"]` with `allow_credentials=False`, and set `allow_credentials=True` only when explicit non-wildcard origins are configured. (covers: "CORS configuration adheres to Fetch specification")

## 3. Optional Bearer token authentication

- [ ] 3.1 Add test cases in `backend/tests/test_control_plane_security.py` verifying mutating `POST` routes when `ROBOTRADER_API_TOKEN` is set (valid token accepted, missing or invalid token rejected with 401 Unauthorized via constant-time check) and when unset (open access). (covers: "Valid Bearer token allows mutating POST request", "Missing Authorization header is rejected with 401", "Invalid Bearer token is rejected with 401", "Malformed Authorization scheme is rejected with 401", "Unset API token allows unauthenticated requests in local dev")
- [ ] 3.2 Add test cases in `backend/tests/test_control_plane_security.py` verifying that `GET /api/v1/health` and `GET /api/v1/status` remain accessible without authentication regardless of `ROBOTRADER_API_TOKEN`. (covers: "GET health and status endpoints remain unauthenticated")
- [ ] 3.3 Implement authentication dependency/middleware in `backend/server.py` protecting all mutating `POST` endpoints under `/api/v1/` using constant-time token verification via `hmac.compare_digest`. (covers: "Optional Bearer token authentication on mutating endpoints")

## 4. Redis persistence contract documentation honesty

- [ ] 4.1 Update `docs/adr/0001-hybrid-quant-agentic-architecture.md` to accurately describe single-key `robotrader:v2:state` JSON snapshot persistence and mark Redis Streams and native per-key `EX` expiration as roadmap. (covers: "ADR-0001 documents state snapshot and marks streams as roadmap")
- [ ] 4.2 Update `README.md` IPC & State Bus section to reflect the implemented single-key state snapshot with in-memory fallback without claiming active Redis Streams or Pub/Sub. (covers: "README accurately reflects state persistence architecture")

## 5. Regression and integration verification

- [ ] 5.1 Run the full Python test suite (`python -m unittest discover -s backend/tests -v`) and verify all tests pass. (covers: "Restore preserves the persisted issue time", "Optional Bearer token authentication on mutating endpoints")
- [ ] 5.2 Verify that `engine-rs` workspace tests and frontend build remain green with no unexpected diffs. (covers: "Zero hot-path impact")

## Verification

- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` → expected: Rust node binary builds successfully.
- `PYTHONPATH=. python3 -m unittest backend.tests.test_policy_ttl_heartbeat -v` → expected: all policy TTL tests pass including null, non-numeric, boolean, and malformed restore cases.
- `PYTHONPATH=. python3 -m unittest backend.tests.test_control_plane_security -v` → expected: all CORS and Bearer token security tests pass.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: full backend test discovery passes.
- `cd engine-rs && cargo test --all-targets` → expected: all Rust unit and integration tests pass.
- `cd frontend && npm run build` → expected: frontend production build succeeds.
- `git diff --name-only origin/master...HEAD -- engine-rs` → expected: empty diff for Rust hot path.
- `openspec validate harden-control-plane-and-restore --strict` → expected: change validates strictly.
- `python3 scripts/sdlc/spec-lint.py --change harden-control-plane-and-restore` → expected: spec lint passes.

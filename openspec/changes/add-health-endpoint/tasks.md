## 1. Pure snapshot contract

- [x] 1.1 Add a pure health snapshot builder returning exactly `status` (`ok`), `service` (`robotrader`), and `timestamp` (covers: `Read-only health endpoint` / `Healthy probe returns the contract`; `UTC timestamp freshness` / `Timestamp is an ISO-8601 UTC instant`)
- [x] 1.2 Build `timestamp` from the current UTC clock with a trailing `Z` and optional fractional seconds (covers: `UTC timestamp freshness` / `Timestamp is an ISO-8601 UTC instant`, `Timestamp is fresh`)
- [x] 1.3 Keep the snapshot module free of `backend.server`, `backend.core.state_store`, Redis, network, and configuration access (covers: `Pure, independently testable snapshot` / `Import and call do not load the heavy server`, `Dependency outage does not change the probe`)

## 2. Route exposure

- [x] 2.1 Mount `GET /api/v1/health` so it returns the snapshot with HTTP status 200, `application/json`, and no extra top-level fields (covers: `Read-only health endpoint` / `Healthy probe returns the contract`, `Probe payload excludes undeclared data`)
- [x] 2.2 Register the route in `backend/server.py` without changing existing routes or startup behavior (covers: `Read-only health endpoint` / `Repeated probes are idempotent`)
- [x] 2.3 Confirm non-`GET` methods on `/api/v1/health` return HTTP status 405 (covers: `Read-only health endpoint` / `Non-GET method is rejected`)
- [x] 2.4 Ensure the route module can be mounted by a minimal FastAPI app without importing `backend.server` (covers: `Pure, independently testable snapshot` / `Import and call do not load the heavy server`)

## 3. Unit tests

- [x] 3.1 Test the 200 response: content type, exact top-level key set, and constant values (covers: `Read-only health endpoint` / `Healthy probe returns the contract`, `Probe payload excludes undeclared data`)
- [x] 3.2 Test the timestamp against the ISO-8601 UTC pattern and its freshness within 5 seconds (covers: `UTC timestamp freshness` / `Timestamp is an ISO-8601 UTC instant`, `Timestamp is fresh`)
- [x] 3.3 Test that repeated probes return identical static fields and do not mutate state (covers: `Read-only health endpoint` / `Repeated probes are idempotent`)
- [x] 3.4 Test that `POST /api/v1/health` returns HTTP status 405 using the minimal test app (covers: `Read-only health endpoint` / `Non-GET method is rejected`)
- [x] 3.5 Assert that `backend.server` and `backend.core.state_store` are absent from `sys.modules` after importing the route module and calling the endpoint (covers: `Pure, independently testable snapshot` / `Import and call do not load the heavy server`)
- [x] 3.6 Make Redis and state-store access unavailable, then assert the probe still returns HTTP status 200 with `status` equal to `ok` (covers: `Pure, independently testable snapshot` / `Dependency outage does not change the probe`)

## Verification

- `PYTHONPATH=. python3 -m unittest backend.tests.test_health -v` → expected: every health scenario test passes, exit 0.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: the full backend suite passes, exit 0.
- `PYTHONPATH=. python3 -c "import backend.tests.test_health, sys; assert 'backend.server' not in sys.modules; print('import-isolated')"` → expected: prints `import-isolated`, exit 0.
- `docker compose up --build -d && curl -fsS -D - http://localhost:8000/api/v1/health` → expected: `HTTP/1.1 200`, `content-type: application/json`, and a body with only `status`, `service`, and `timestamp`.
- `curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/api/v1/health` → expected: `405`.
- `openspec validate add-health-endpoint --strict` → expected: pass with no errors.
- `scripts/sdlc/sdlc.sh check add-health-endpoint` → expected: `check: PASS`.

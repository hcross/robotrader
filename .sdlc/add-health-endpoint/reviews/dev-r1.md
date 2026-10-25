# DEV Review — Round 1

## Summary

The DEV change is approved. `backend/core/health.py` adds a dependency-free snapshot returning exactly `status`, `service`, and an ISO-8601 UTC `Z` timestamp; `backend/server.py` only registers the router; `backend/tests/test_health.py` covers every scenario. I independently ran the health suite (9/9), the import-isolation guard, the full backend suite (41 tests, only the three known `cargo`-missing errors), CI checks (all four green), OpenSpec strict validation, the SDLC check, and a live probe of the built image (200, `application/json`, three keys; POST/HEAD/OPTIONS 405). No scope creep, no secrets, no hot-path, `PolicyEnvelope`, money, risk, vault, or chain change. Two non-blocking test-quality observations remain: the 405 test omits HEAD/OPTIONS and does not assert the handler is not invoked; the in-process `sys.modules` assertion is coupled to full-suite module loading.

## Findings

### DEV-R1-F01 — [minor] 405 scenario assertions are incomplete

- Location: `backend/tests/test_health.py:66-70`
- Evidence: `test_non_get_method_is_rejected` loops only `post`, `put`, `patch`, `delete` and asserts only `status_code == 405`. The approved scenario (`openspec/changes/add-health-endpoint/specs/health/spec.md`, "Non-GET method is rejected") also requires that the service "does not build or return a health snapshot" and covers "any method other than GET". The behavior is correct — a live minimal-app probe returned 405 for `HEAD` and `OPTIONS` too — but neither the extra methods nor the handler-not-invoked property is asserted, so a regression that invoked the handler on a rejected method would not be caught.
- Required fix: add `head` and `options` to the subTest loop, and wrap the non-GET requests in `mock.patch("backend.core.health.health_snapshot")` with `assert_not_called()` to prove no snapshot is built.
- Status: open
- Origin: initial

### DEV-R1-F02 — [nit] In-process `sys.modules` assertion is coupled to suite composition

- Location: `backend/tests/test_health.py:116`
- Evidence: `self.assertNotIn("backend.server", sys.modules)` runs in the same interpreter as the whole discovered suite. `unittest discover` imports every test module before execution, so this line currently passes only because no sibling test module imports `backend.server` at import time. A future sibling test that does would make this health test fail for an unrelated reason. The subprocess block at lines 118-138 already proves the real property in a clean interpreter.
- Required fix: remove the in-process assertion at line 116, or move it entirely inside the subprocess script; keep the subprocess check as the authoritative isolation proof.
- Status: open
- Origin: initial

## Checklist audit

| Section | Result | Evidence |
|---|---|---|
| 0. Scope | PASS | `git diff --name-status master...f083164` lists 3 code files (`backend/core/health.py`, `backend/server.py`, `backend/tests/test_health.py`) plus approved SDLC/OpenSpec artifacts. `proposal.md` and `specs/health/spec.md` are byte-identical to approved SHA `8aa620f`; `tasks.md` differs only by 13 checkbox flips (`- [ ]` → `- [x]`). |
| 1. Correctness | PASS | Exactly three top-level keys; `status="ok"`, `service="robotrader"`; ISO-8601 UTC `Z` timestamp; method rejection delegated to FastAPI routing. No error path, shared state, or unit ambiguity introduced. |
| 2. Robotrader invariants | N/A | No `engine-rs`, `PolicyEnvelope`, hot-path, capital, vault, chain, or `backend/core/` infrastructure change; health module imports only `datetime`, `typing`, `fastapi.APIRouter`. |
| 3. Contracts | PASS | Additive REST route only; `/api/v1/status` untouched; frontend CI build passes. |
| 4. Security | PASS | No secret/key/token on added lines (regex scan of the diff); endpoint is read-only and exposes no internal data, as the approved spec requires it to be credential-free. |
| 5. Tests and evidence | PASS (with F01/F02) | Every scenario maps to at least one test; all 9 health tests pass; isolation proven in a clean subprocess; live endpoint probed. |
| 6. Performance and cost | PASS | No hot-path allocation, LLM call, scheduler, or per-tick cost. |
| 7. Maintainability | PASS | Focused module, docstring states the isolation contract, no dead code or debug print. |
| 8. Operations | PASS | No config, migration, or startup change; rollback is route removal. |

## Checks run

- `docker run --rm -v "$PWD":/app -w /app -e PYTHONPATH=. robotrader-backend:latest python -m unittest backend.tests.test_health -v` → `Ran 9 tests in 0.241s` — `OK`
- `docker run --rm ... python -c "import backend.tests.test_health, sys; assert 'backend.server' not in sys.modules; assert 'backend.core.state_store' not in sys.modules; print('import-isolated')"` → `import-isolated` (exit 0)
- `docker run --rm ... python -m unittest discover -s backend/tests -v` → `Ran 41 tests in 5.063s` — `FAILED (errors=3)`. All 9 health tests pass. The 3 errors are the known pre-existing environmental `cargo` errors, not attributable to this change: `FileNotFoundError: [Errno 2] No such file or directory: 'cargo'` in `test_architecture.TestHybridArchitectureV2.test_python_to_rust_backtest_bridge_and_regime_switching`, `test_hierarchy_v3.TestHierarchicalArchitectureV3.test_26_leaf_ecosystem_catalog_and_isolated_rss_feeds`, and `test_hierarchy_v3.TestHierarchicalArchitectureV3.test_solana_leaf_purification_excludes_non_solana_assets`.
- Live probe of the built image with the reviewed worktree mounted (`docker run -p 18080:8000 ... robotrader-backend:latest`, then `docker stop`) → `GET /api/v1/health`: `HTTP/1.1 200 OK`, `content-type: application/json`, body `{"status":"ok","service":"robotrader","timestamp":"2026-10-25T21:48:45.800515Z"}`; `POST` → `405`; `HEAD` → `405`; `OPTIONS` → `405`. (CORS preflight `OPTIONS` returns 200 via the pre-existing app-wide middleware, not the health route.)
- `gh pr checks 12` → `frontend pass`, `python pass`, `rust pass`, `sdlc pass`
- `gh pr view 12 --json isDraft,headRefOid,mergeable,state,title` → `isDraft: true`, `headRefOid: f083164fa29f39f1a012aa3898f77f2864445d76`, `mergeable: MERGEABLE`, `state: OPEN`
- `openspec validate add-health-endpoint --strict` → `Change 'add-health-endpoint' is valid` (exit 0)
- `scripts/sdlc/sdlc.sh check add-health-endpoint` → `check: PASS` (exit 0); spec-lint: 13 tasks done, 0 open; spec-r1 APPROVE

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "add-health-endpoint",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "f083164fa29f39f1a012aa3898f77f2864445d76",
  "verdict": "APPROVE",
  "summary": "The health endpoint implements the approved spec with full scenario coverage and isolation verified in a clean process; two non-blocking test-quality observations remain.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_health.py:66-70",
      "evidence": "The 405 test loops only post/put/patch/delete and asserts only status 405; the approved scenario also requires HEAD/OPTIONS rejection and that no snapshot is built. Verified behavior is correct (HEAD and OPTIONS return 405).",
      "required_fix": "Add head and options to the subTest loop and assert health_snapshot is not called under mock.patch."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_health.py:116",
      "evidence": "The in-process assertNotIn('backend.server', sys.modules) tests suite composition, not the module: discover imports all test modules first, so a future sibling import would break this test spuriously.",
      "required_fix": "Drop the in-process assertion or move it into the subprocess script, which already proves isolation in a clean interpreter."
    }
  ],
  "closed": []
}
```

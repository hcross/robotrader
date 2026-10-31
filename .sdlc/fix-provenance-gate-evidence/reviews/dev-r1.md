# DEV Review — Round 1

## Summary

APPROVE. The diff closes all five DEV-R1 findings from #15 plus PLAN-R2-F01 within the approved spec. The `rust_leaf_backtest` comment token is removed (the three documented grep gates exit 1), production-module and state-store absence tests are added, `formatMetric` returns an em dash for unknown sources, the recursive `/api/v1/status` provenance walk runs against the real payload, and the JSONL-only round-trip and bootstrap-only prompt scenarios are directly asserted. The uncropped `offline.png` (1600×1200) shows `OFFLINE — last success 22:06:39`. I independently ran `cargo test` (58 passed), the Python suite (196 passed in an isolated venv), `npm run build`, `check-provenance.mjs`, the three grep gates, and `sdlc.sh check`; all green, and `gh pr checks` is green. No invariant, contract, vault, or hot-path risk. Two non-blocking nits follow up.

## Findings

### DEV-R1-F01 — [nit] New frontend regression assertion is not enforced by CI
- Location: `.github/workflows/ci.yml:131-145` (frontend job), `frontend/scripts/check-provenance.mjs:19-20`
- Evidence: the frontend CI job runs only `npm ci` and `npm run build`; `node frontend/scripts/check-provenance.mjs` is listed in `tasks.md` → Verification but is never invoked by CI. The new `formatMetric(10, 'BOGUS')` / `badgeFor('BOGUS')` assertions therefore only fire on a manual run.
- Required fix: follow-up (outside this change's approved scope) — add a `node frontend/scripts/check-provenance.mjs` step to the frontend CI job so the guard is automated.
- Status: open
- Origin: initial

### DEV-R1-F02 — [nit] `walk_payload_provenance` duplicated verbatim in the child script
- Location: `backend/tests/test_integrity_provenance.py:50-100` and `:1162-1210`
- Evidence: the function body and the `VALID_METRIC_SOURCES`, `VALID_DRAWER_SOURCES`, and `PERFORMANCE_NUMERIC_KEYS` definitions appear twice — once at module level, once inside the `SERVER_CHILD_SCRIPT` raw string — with identical content. A future edit to one copy can silently desynchronise the end-to-end walk from the in-process test.
- Required fix: follow-up — have `SERVER_CHILD_SCRIPT` import the shared helper/constants, or add an assertion that the two copies are identical.
- Status: open
- Origin: initial

## Checks run

- `cd engine-rs && cargo test` → ok, 58 passed / 0 failed across all crates.
- `PYTHONPATH=.. python -m unittest discover -s tests -v` (isolated Python 3.11 venv at `/tmp/robotrader-devrev-venv`, deps from `backend/pyproject.toml`) → `Ran 196 tests … OK`. The six new/changed provenance tests pass explicitly.
  - Note: my default pyenv 3.11.1 interpreter has a broken `_ssl` (`libssl.1.1.dylib` missing), which makes every child-process test fail with `ImportError: dlopen … _ssl`. That is an environment defect, not a code defect; the isolated venv reproduces the CI result.
- `cd frontend && npm run build` → built in ~418 ms, exit 0.
- `node frontend/scripts/check-provenance.mjs` → `provenance wiring OK`, exit 0.
- `git grep -n 'rust_leaf_backtest' -- backend/core backend/agents backend/server.py` → exit 1 (no occurrences).
- `git grep -n 'solana_onchain_pnl_sol' -- backend/core/state_store.py` → exit 1.
- `git grep -n 'simulated_model_pnl_usd' -- backend/core/state_store.py` → exit 1.
- `scripts/sdlc/sdlc.sh check fix-provenance-gate-evidence` → `check: PASS` (spec-lint PASS; `openspec validate --strict` pass; 9 tasks done, 0 open).
- `gh pr checks 22` → rust pass, python pass, frontend pass, helm pass, sdlc pass.
- Evidence: `.sdlc/fix-provenance-gate-evidence/evidence/offline.png` present (gitignored), PNG 1600×1200, header shows `OFFLINE — last success 22:06:39`.
- `docker compose up --build -d` (`.env` provisioned by the conductor) → backend, redis, and frontend images all built; `redis` and `backend` started. `GET http://localhost:8000/api/v1/status` → HTTP 200, `contract_version=3`, `engine_metrics.backtest_fixture.source=FIXTURE`, `hierarchy.treasury.source=BOOTSTRAP`. The `frontend` container could not start: `error mounting ".../app/node_modules" ... openat2 ... operation not permitted` (anonymous `/app/node_modules` volume), reproducible on retry; `http://localhost:5173` was therefore not served. This is a Docker-runtime mount restriction, not the diff (compose file and frontend Dockerfile are untouched, and the frontend image built). `docker compose down` → all containers and the network removed; none left running.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-provenance-gate-evidence",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "682af1a12a01ab873973585c81b4a2e352728269",
  "verdict": "APPROVE",
  "summary": "All approved-scope findings are implemented and verified; Rust and Python suites, frontend build, provenance check, grep gates, and CI are green, with two non-blocking nits recorded.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": ".github/workflows/ci.yml:131-145",
      "evidence": "The frontend CI job runs only `npm ci` and `npm run build`; `node frontend/scripts/check-provenance.mjs` is never invoked, so the new formatMetric/badgeFor assertions are manual-only.",
      "required_fix": "Follow-up (outside this change's approved scope): add a `node frontend/scripts/check-provenance.mjs` step to the frontend CI job."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_integrity_provenance.py:50-100 and :1162-1210",
      "evidence": "walk_payload_provenance and its VALID_METRIC_SOURCES / VALID_DRAWER_SOURCES / PERFORMANCE_NUMERIC_KEYS constants are duplicated verbatim inside SERVER_CHILD_SCRIPT; the two copies can drift silently.",
      "required_fix": "Follow-up: have SERVER_CHILD_SCRIPT import the shared helper/constants, or add an assertion that the two copies are identical."
    }
  ],
  "closed": []
}
```

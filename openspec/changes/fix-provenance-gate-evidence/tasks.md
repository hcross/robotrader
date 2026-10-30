# Tasks: Fix Provenance Gate Evidence

## 1. Grep Gate & Production Module Absence

- [ ] 1.1 Remove literal `rust_leaf_backtest` token from explanatory comment in `backend/core/provenance.py` (covers: Scenario: Production modules exclude deprecated producer tokens)
- [ ] 1.2 Add production-absence test in `backend/tests/test_integrity_provenance.py` asserting `rust_leaf_backtest` does not appear in `backend/core`, `backend/agents`, or `backend/server.py` (covers: Scenario: Production modules exclude deprecated producer tokens)
- [ ] 1.3 Add production-absence test in `backend/tests/test_integrity_provenance.py` asserting `solana_onchain_pnl_sol` and `simulated_model_pnl_usd` do not appear in `backend/core/state_store.py` (covers: Scenario: State store excludes deprecated telemetry fields)

## 2. Frontend Provenance Alignment & Evidence

- [ ] 2.1 Update `formatMetric` in `frontend/src/lib/provenance.js` to return `EM_DASH` for unknown or non-enum source tokens (covers: Scenario: Unattributed block renders an em dash with an unattributed badge)
- [ ] 2.2 Add assertion to `frontend/scripts/check-provenance.mjs` verifying `formatMetric` returns `—` for unknown sources such as `'BOGUS'` (covers: Scenario: Unattributed block renders an em dash with an unattributed badge)
- [ ] 2.3 Recapture uncropped `offline.png` in `.sdlc/fix-provenance-gate-evidence/evidence/` showing the header `OFFLINE` badge and timestamp (covers: Scenario: Failed poll replaces retained values with an em dash)

## 3. Backend Regression Assertions

- [ ] 3.1 Implement recursive payload traversal in `backend/tests/test_integrity_provenance.py` verifying every numeric performance field carries an enum source (covers: Scenario: Recursive payload walk rejects unattributed numeric performance)
- [ ] 3.2 Add test asserting JSONL-only drawer round-trip without Redis in `backend/tests/test_integrity_provenance.py` (covers: Scenario: Drawer source survives persistence)
- [ ] 3.3 Add test asserting the "no previous thesis is recorded" prompt message on a bootstrap-only palace in `backend/tests/test_integrity_provenance.py` (covers: Scenario: Bootstrap drawers are absent from the continuity prompt)

## Verification

- `cd engine-rs && cargo test`
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v`
- `cd frontend && npm run build`
- `node frontend/scripts/check-provenance.mjs`
- `git grep -n 'rust_leaf_backtest' -- backend/core backend/agents backend/server.py` → expected: exit 1 (no occurrences)
- `git grep -n 'solana_onchain_pnl_sol' -- backend/core/state_store.py` → expected: exit 1 (no occurrences)
- `git grep -n 'simulated_model_pnl_usd' -- backend/core/state_store.py` → expected: exit 1 (no occurrences)
- `scripts/sdlc/sdlc.sh check fix-provenance-gate-evidence`

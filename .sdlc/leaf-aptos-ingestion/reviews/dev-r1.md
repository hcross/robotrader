# DEV Review — Round 1

## Summary

Cold review of PR #228 (head `d8d07d7`) covering the Aptos leaf TA metrics block added to
`backend/tools/ta_tools.py` and the matching test added to `backend/tests/test_hierarchy_v3.py`.
The change mirrors the established per-leaf pattern (Tron/Avalanche/...): class constants,
`compute_aptos_ta_metrics`, and `ingest_aptos_market_snapshot`, appended after the last
existing leaf block. Scope matches lane M (two files). The provided test passes and all CI
checks on the PR are green. No invariant violation, contract change, or hot-path impact
found.

## Findings

(none)

## Checks run

- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` → succeeded (0.08s)
- `cargo test` (engine-rs) → all suites ok (0 failures)
- `PYTHONPATH=. python3 -m unittest backend.tests.test_hierarchy_v3.TestHierarchicalArchitectureV3.test_aptos_leaf_ta_metrics_computation_and_fallback` → OK (1 test, 0.009s)
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests` → 249 tests; 10 failures + 7 errors identical to base `9e90ea6` (environmental: missing `httpx2`, `ccxt`, test binary discovery), unrelated to this change
- `gh pr checks 228` → frontend, helm, python, rust all pass
- `npm run build` (frontend) → not run, `node_modules` absent in worktree; no frontend files changed
- reviewed SHA `d8d07d79e82f4bf7c80abff9762fa5c804bb1d55` == PR #228 head SHA

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-aptos-ingestion",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "d8d07d79e82f4bf7c80abff9762fa5c804bb1d55",
  "verdict": "APPROVE",
  "summary": "Aptos leaf TA metrics block and test follow the established per-leaf pattern; tests pass and PR CI is green with no invariant violations.",
  "findings": [],
  "closed": []
}
```
# DEV Review — Round 1

## Summary

Warm-path wiring for `leaf-avalanche` mirrors the established BNB/XRP leaf
pattern: catalyst/pod/tp-bps blocks, `default_interval`, shared-file insertion,
and wing seeding are consistent, and CI is green. One coverage gap remains: the
new reflection/policy-compilation path has no dedicated test.

## Findings

### DEV-R1-F01 — [major] No test covers the new leaf-avalanche warm-path reflection and policy compilation
- Location: `backend/tests/test_hierarchy_v3.py` (test suite gap; change in `backend/agents/orchestrator.py`, `backend/core/hierarchy.py`)
- Evidence: `grep -rn "leaf-avalanche" backend/tests/` finds only catalog/RSS/TA assertions; no test calls `run_leaf_agent_reflection("leaf-avalanche", ...)`, unlike the `leaf-bitcoin`, `leaf-ethereum`, `leaf-sui`, `leaf-hyperliquid`, `leaf-xrp`, and `leaf-bnb` warm-path tests. Manual run succeeded: `status=completed`, `wing=leaf_avalanche`, `next_wakeup_sec=900`, overrides `{"AVAX-USDC","JOE-AVAX"}`, 11 keys each, HMAC valid.
- Required fix: Add `test_avalanche_warm_path_reflection_and_policy_compilation` mirroring the established leaf tests: exhaust `CostGuard` budget, call `run_leaf_agent_reflection("leaf-avalanche", trigger_source="UNIT_TEST")`, assert `status=completed`, `wing=leaf_avalanche`, `next_wakeup_sec=900`, `ttl_seconds=900`, override keys exactly `{"AVAX-USDC","JOE-AVAX"}` with all 11 `AssetOverride` keys, `AVAX-USDC` support/resistance/invalidation around `27.80`, and HMAC verification.
- Status: open
- Origin: initial

## Checks run
- `cd engine-rs && cargo test` → PASS, all crates 0 failures (59 unit + integration tests).
- `PYTHONPATH=. python3.11 -m unittest discover -s backend/tests -v` → `Ran 309 tests`, `OK`.
- `cd frontend && npm run build` → PASS (1694 modules, built in 526ms).
- `gh pr checks 221` → frontend PASS, helm PASS, python PASS, rust PASS.
- Manual verification: `run_leaf_agent_reflection("leaf-avalanche", trigger_source="UNIT_TEST")` → `status=completed`, `wing=leaf_avalanche`, `next_wakeup_sec=900`, `ttl_seconds=900`, overrides `{"AVAX-USDC","JOE-AVAX"}`, all 11 keys, HMAC valid.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-avalanche-warm-path",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "daf61dc9339e689fcb4ab069bab19af68162b6fa",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Warm-path wiring is consistent and all checks pass, but leaf-avalanche lacks a dedicated reflection/policy-compilation test.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_hierarchy_v3.py",
      "evidence": "No test invokes run_leaf_agent_reflection('leaf-avalanche'); only catalog/RSS/TA assertions reference leaf-avalanche.",
      "required_fix": "Add a leaf-avalanche warm-path test mirroring the established leaf warm-path tests."
    }
  ],
  "closed": []
}
```
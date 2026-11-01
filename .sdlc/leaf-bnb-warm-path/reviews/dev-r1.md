# DEV Review — Round 1

## Summary

BNB warm-path wiring mirrors the established leaf pattern and the compiled
`PolicyEnvelope` now derives pod slot ids, all-leaf checks pass, and CI is
green. One coverage gap remains: the new `leaf-bnb` reflection/policy
compilation path has no dedicated test, unlike prior leaves.

## Findings

### DEV-R1-F01 — major No test covers the new leaf-bnb warm-path reflection and policy compilation
- Location: `backend/tests/test_hierarchy_v3.py` (test suite gap; change in `backend/agents/orchestrator.py`, `backend/core/hierarchy.py`)
- Evidence: `grep -rn "leaf-bnb" backend/tests/` finds only catalog/pod-parity/RSS assertions; no test calls `run_leaf_agent_reflection("leaf-bnb", ...)`, unlike the `leaf-bitcoin`, `leaf-ethereum`, `leaf-sui`, `leaf-hyperliquid`, and `leaf-xrp` warm-path tests. A manual run succeeded (status `completed`, wing `leaf_bnb`, `next_wakeup_sec=900`, overrides `BNB-USDT`/`CAKE-BNB`, 11 keys each, HMAC valid), but no automated assertion protects it.
- Required fix: Add a `test_bnb_warm_path_reflection_and_policy_compilation` test mirroring the established leaf tests: exhaust `CostGuard` budget, call `run_leaf_agent_reflection("leaf-bnb", trigger_source="UNIT_TEST")`, assert `status=completed`, `wing=leaf_bnb`, `next_wakeup_sec=900`, `ttl_seconds=900`, override keys exactly `{"BNB-USDT", "CAKE-BNB"}`, all 11 `AssetOverride` keys, `BNB-USDT` support/resistance/invalidation around `598.0`, and HMAC verification.
- Status: open
- Origin: initial

### DEV-R1-F02 — minor Pod slot normalization lacks the hardened form used after XRP
- Location: `backend/agents/orchestrator.py:318-323`
- Evidence: The current code uses `pod_slot_ids = {p.get("slot_id") if isinstance(p, dict) else p for p in rust_pods_list}`. The post-R1 XRP implementation additionally falls back to `pod_code`, stringifies entries, and defaults the set when empty; the BNB path does not. Real BNB pods contain `slot_id`, so the compiled `PolicyEnvelope` is correct today (verified: `pod_carry`, `pod_momentum`, `pod_onchain_alpha` enabled with weight `0.33`, `pod_sniper` disabled), but the simpler form is less defensive against malformed/alternate fixtures.
- Required fix: Align the normalization with the XRP post-R1 implementation: derive `slot_id` then `pod_code`, stringify, and use the three default slots when the set is empty.
- Status: open
- Origin: initial

## Checks run

- `cd engine-rs && cargo test` → 122 tests passed, 0 failed (all crates ok).
- `PYTHONPATH=. python3.11 -m unittest discover -s backend/tests -v` → 304 tests OK.
- `cd frontend && npm run build` → not runnable locally (`sh: vite: not installed`); frontend unchanged by this PR; `gh pr checks 211` shows frontend PASS.
- `gh pr checks 211` → frontend, helm, python, rust all PASS.
- Manual verification: `run_leaf_agent_reflection("leaf-bnb", trigger_source="UNIT_TEST")` → `status=completed`, `wing=leaf_bnb`, `next_wakeup_sec=900`, `ttl_seconds=900`, overrides `{"BNB-USDT","CAKE-BNB"}`, all 11 keys, pod allocations as above, HMAC valid.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-bnb-warm-path",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "ea9a70ffc51ccb3ebbd19c75f29d1768bd34f766",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Warm-path wiring is consistent and functional checks pass, but leaf-bnb lacks a dedicated reflection/policy-compilation test and pod-slot normalization is less defensive than the XRP implementation.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_hierarchy_v3.py",
      "evidence": "No test invokes run_leaf_agent_reflection('leaf-bnb'); only catalog/pod-parity/RSS assertions reference leaf-bnb.",
      "required_fix": "Add a leaf-bnb warm-path test mirroring the established leaf warm-path tests."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/agents/orchestrator.py:318-323",
      "evidence": "Normalization only reads slot_id and has no pod_code fallback, str() coercion, or empty-set default.",
      "required_fix": "Align pod_slot_ids derivation with the post-R1 XRP implementation."
    }
  ],
  "closed": []
}
```

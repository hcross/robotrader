# DEV Review — Round 1

## Summary

The Sui warm-path wiring is functionally correct: Rust, Python (290 tests), and the frontend build pass, and a manual reflection run produced a valid `PolicyEnvelope` with all three Sui assets and a verified HMAC. The one substantiated gap is test coverage: unlike the prior Ethereum wiring commit (`e263b29`), this PR adds `orchestrator.py` branches only and no test exercising them, so a regression in the new `leaf-sui` branches would not be caught. Request a dedicated Sui warm-path test before approval.

## Findings

### DEV-R1-F01 — [blocker] New leaf-sui warm-path branches are not covered by a test

- Location: `backend/agents/orchestrator.py:349-416` (`compile_leaf_policy_envelope` `elif leaf_id == "leaf-sui"` branches) and `backend/agents/orchestrator.py:1114` (`default_interval`)
- Evidence: PR diff (base `6f1f3d5` → reviewed SHA `f3b9a2f`) touches only `backend/agents/orchestrator.py` plus SDLC ledger/brief; it adds no test. `backend/tests/test_hierarchy_v3.py` contains `test_ethereum_warm_path_reflection_and_policy_compilation` but no analogous `leaf-sui` case. The prior Ethereum wiring commit (`e263b29`) added 48 lines of tests alongside the same surface. A manual run of `run_leaf_agent_reflection("leaf-sui")` succeeded, but it is not committed coverage.
- Required fix: Add a test analogous to `test_ethereum_warm_path_reflection_and_policy_compilation` for `leaf-sui` asserting `wing == "leaf_sui"`, `next_wakeup_sec == 900`, `asset_overrides` keys exactly `{"SUI-USDC", "DEEP-SUI", "CETUS-SUI"}`, all 11 `AssetOverride` fields populated, representative zone values, and `verify_policy_hmac(...)` returning `True`.
- Status: open
- Origin: initial

## Checks run

- `cargo test --manifest-path engine-rs/Cargo.toml` → PASS (all workspace crates; backtest/risk-gate/common/strategies/exec-router/node doc-tests ok)
- `PYTHONPATH=. python3.12 -m unittest discover -s backend/tests` (poetry py3.12 env) → Ran 290 tests, OK
- `cd frontend && npm run build` → PASS (1694 modules transformed, built in 855 ms)
- `docker compose up --build -d` → images built successfully; startup failed because host port 6379 was already allocated (environment, not the change); containers torn down afterward
- `gh pr checks 194` → not run (no network route to api.github.com from this host)
- Manual functional check `run_leaf_agent_reflection("leaf-sui")` → PASS (wing `leaf_sui`, next_wakeup 900, 3 assets, HMAC valid)

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-sui-warm-path",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "f3b9a2fc30912e4a72faacfee6477e835c757573",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Warm-path wiring builds and unit tests pass, but the new leaf-sui branches in compile_leaf_policy_envelope and the 900s default wakeup are untested.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "backend/agents/orchestrator.py:349-416 and backend/agents/orchestrator.py:1114",
      "evidence": "The PR adds orchestrator branches for leaf-sui without an analogous dedicated test; test_hierarchy_v3.py has no leaf-sui reflection/policy case, unlike the prior Ethereum wiring commit e263b29.",
      "required_fix": "Add a test analogous to test_ethereum_warm_path_reflection_and_policy_compilation for leaf-sui covering wing, 900s wakeup, exact asset set, all 11 AssetOverride fields, representative zones, and HMAC verification."
    }
  ],
  "closed": []
}
```
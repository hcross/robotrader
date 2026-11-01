# Merge Dossier — leaf-bnb-ingestion

## Decision Card (≤ 5 min)

| Field | Value |
|---|---|
| What ships | BNB Chain leaf TA metrics computation, market snapshot ingestion, and unit tests. |
| Why | Issue #52 Dimension 1: replace `CATALOG_FIXTURE` telemetry for `leaf-bnb` with live-computed TA metrics. |
| Blast radius | `backend/tools/ta_tools.py`, `backend/tests/test_hierarchy_v3.py`. No contract, risk, vault, or frontend surface. |
| Worst failure | Stale/incorrect BNB TA metrics if computation regresses; detected by `test_bnb_leaf_ta_metrics_computation_and_fallback`. |
| Rollback | Revert PR commit `3e679b1b` (or `git revert` on master). |
| Risk | Low |
| Recommendation | Do not merge (NOT_READY) |

```mermaid
flowchart LR
  A["CATALOG_FIXTURE"] --> B["compute_bnb_ta_metrics"] --> C["LIVE_COMPUTED"]
```

## Evidence

| Gate | Result | Evidence |
|---|---|---|
| SPEC | N/A (lane M; spec skipped) | `state.json` stages.spec.status = skipped |
| PLAN | N/A (lane M; plan skipped) | `state.json` stages.plan.status = skipped |
| DEV | APPROVE (round 1) | `.sdlc/leaf-bnb-ingestion/reviews/dev-r1.md` @ `3e679b1b391e37b8a314f995f4b950a4788b9211` |
| CI | green | `gh pr checks 197` → rust, python, frontend, helm all pass |
| Tests | pass (claimed/CI) | BNB targeted test: `PYTHONPATH=. $VENV/python -m unittest backend.tests.test_hierarchy_v3 -k bnb` → 1 test OK |
| Lints | pass | `scripts/sdlc/sdlc.sh check leaf-bnb-ingestion` → PASS |
| PR mergeability | CONFLICTING (FAIL) | `gh pr view 197` → `mergeable: CONFLICTING`, head `3e679b1b...` |

## Diff

- Files: 2 | +176 / -0
- Areas: `backend/tools`, `backend/tests`
- New dependencies: none

## Residual risk and follow-ups

- **Blocker:** PR is not mergeable. `origin/master` advanced (`031f32c6…` → `05d9d7a9…`) and now carries TON leaf tests in the same `backend/tests/test_hierarchy_v3.py` insertion anchor; rebase/resolution is required before merge. Evidence: `git merge --no-commit origin/master` → conflict in `backend/tests/test_hierarchy_v3.py`.
- Follow-up: confirm the full Python suite in the canonical Poetry venv after optional dependency availability (e.g. `python-dotenv`), separate from this change's BNB test, which passes.

## Human decision

- [ ] Merge
- [ ] Merge with follow-up
- [ ] Request changes
- [ ] Abandon
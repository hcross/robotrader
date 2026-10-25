# DEV Review — Round 1

## Summary

APPROVE. The diff removes the two writers that neutralised the policy TTL — the unconditional live-tick renewal and the restore-time restamp — and fails closed to `safe_baseline` when the persisted issue time is missing or null. `is_expired`, `get_effective_policy`, kill-switch precedence, the six-key wire shape, and the Redis payload shape are unchanged. I reproduced the red proof independently: the 22 new tests fail 13 on the pre-change `state_store.py` and pass at the reviewed SHA; the shipping image runs 125 tests `OK (skipped=9)`, Rust is green, OpenSpec strict and SDLC checks pass, and all five CI checks are green at `11affbc`, which equals the PR head. Two non-blocking follow-ups: a malformed non-numeric `issued_at_ms` still falls through the broad restore `except` into the constructor's `default_active()`, and the explicit-null variant is verified but untested.

## Findings

### DEV-R1-F01 — minor — Malformed `issued_at_ms` falls open to `default_active()` on restore
- Location: `backend/core/state_store.py:201` (`PolicyEnvelope.from_dict(raw_policy)`) and `backend/core/state_store.py:267-268` (broad `except Exception`)
- Evidence: Reviewer probe in the shipping image with `{"policy": {..., "issued_at_ms": "not-a-number"}}` prints `[HybridStateStore] Redis state restore warning: invalid literal for int() with base 10: 'not-a-number'` and leaves `store._policy = env_1792969890057` (the constructor's `default_active()`), not `safe_baseline_fallback`. The approved spec scopes fail-closed restore to an omitted/null issue time; a wrong-type value is outside it and the broad handler is pre-existing and unchanged.
- Required fix: Not required in this round. File a follow-up on issue #8 (naturally in the signing/auth slice #8.3/#8.5) to validate that `issued_at_ms` is an integer and fail closed to `safe_baseline` on any malformed persisted policy.
- Status: open
- Origin: initial

### DEV-R1-F02 — nit — No explicit JSON-null restore test
- Location: `backend/tests/test_policy_ttl_heartbeat.py:379-388`
- Evidence: `test_restore_without_issue_time_is_not_fresh` covers only key omission (`raw_policy.pop("issued_at_ms")`). The explicit `"issued_at_ms": null` path is exercised only by the reviewer probe, which returns `safe_baseline_fallback`; the implementation's `raw_policy.get("issued_at_ms") is None` check covers both.
- Required fix: Optional follow-up: add a null-payload case to the same test class. The spec's scenario is omission, so this is non-blocking.
- Status: open
- Origin: initial

## Checklist walk (`sdlc/checklists/dev.md`)

| § | Item | Status | Evidence |
|---|---|---|---|
| 0 | Implements only the approved spec/plan | PASS | `git diff --name-status master...HEAD` = `state_store.py`, new test, OpenSpec artifacts, `.sdlc` ledger only. |
| 0 | No unrelated refactor, formatting sweep, dependency bump | PASS | Core/agent/frontend/Rust/dependency scoped diff: only `backend/core/state_store.py` (24+/16-). |
| 0 | Diff matches PR description and issue logbook | PASS | Issue scope comment 8.1/8.2; PR body describes both removals; head `11affbc`. |
| 0 | No generated artifacts, secrets, or local data committed | PASS | Secret scan over the diff (password/secret/api key/token/bearer/private key) returned nothing. |
| 1 | Every changed behaviour maps to a scenario or invariant | PASS | 6 requirements / 21 scenarios; the 22 tests map to tasks 1.1–1.8 and their `(covers: ...)` tags. |
| 1 | Error paths return correct, typed failure; no silent `unwrap`/broad `except` | PASS (new path) | New branch is explicit (`if raw_policy.get("issued_at_ms") is None`). Pre-existing broad handler is noted in DEV-R1-F01. |
| 1 | Boundary conditions handled | PASS | Boundary and boundary+1 tests; unauthenticated, no-active-pod, and raising ticks; stale/fresh/missing restore. |
| 1 | Concurrency: no data race, lock-order inversion, unbounded queue | PASS | The tick no longer writes shared state; `test_concurrent_explicit_issuance_survives_the_tick` proves a concurrent `set_policy` survives. |
| 1 | Time and units explicit | PASS | `issued_at_ms` in ms, `ttl_seconds * 1000`; injected `FakeClock` in ms. |
| 2 | Zero LLM/blocking I/O/unbounded sleeps in hot path | N/A | No `engine-rs` change; `git diff --name-only master...HEAD -- engine-rs` empty. |
| 2 | `HardRiskGate::validate` within 50µs | N/A | Risk gate untouched. |
| 2 | `PolicyEnvelope` Rust/Python parity | PASS | `backend/core/schemas.py` unchanged; `test_contract_roundtrip` and `test_contract_single_source` pass in the 125. |
| 2 | Capital protection intact (dry powder, Kelly, kill switch, CostGuard) | PASS | No weight/Kelly/kill-switch/CostGuard change; 4 kill-switch tests pass. |
| 2 | No unbounded wallet/credit refill | N/A | Untouched. |
| 2 | Vault zeroization, whitelist, no key material | N/A | Untouched; no key material in diff/evidence. |
| 2 | Backtest == paper == live | PASS | No strategy/backtest code change; only the effective policy after TTL changes, per the approved spec. |
| 2 | Leaf robot chain/wing isolation | N/A | Untouched. |
| 2 | `backend/core/` holds warm-path infra; `import strands` not shadowed | PASS | Change stays in `backend/core/state_store.py`; no new module. |
| 3 | Rust/Python schemas agree field-for-field | PASS | `schemas.py` unchanged; `to_dict()` key-set test asserts exactly six keys. |
| 3 | Redis keys, TTLs, payload shapes backward compatible | PASS | `REDIS_STATE_KEY` and `_persist_state` untouched; `test_persisted_payload_shape_is_unchanged_by_a_tick` asserts no new key. |
| 3 | REST/WS documented; frontend still builds | PASS | No REST/WS change; frontend CI job passes. |
| 3 | Serialization has no precision loss | PASS | Integer ms/seconds; no float timestamps. |
| 3 | Existing consumers updated or additive | PASS | `run_live_testnet_tick`, `is_expired`, `get_effective_policy` signatures and semantics unchanged. |
| 4 | Trust-boundary inputs validated | PASS (scoped) | Missing/null issue time now fails closed; wrong-type residual in DEV-R1-F01. |
| 4 | No secret, private key, API token, or production address | PASS | Diff scan clean; tests use offline fakes only. |
| 4 | On-chain safety checks not bypassed | N/A | Untouched. |
| 4 | Dependencies pinned, no critical advisory | N/A | No dependency change. |
| 4 | File/network access least privilege | N/A | No new access; tests inject fakes. |
| 5 | New behaviour has a test that fails without the change | PASS | Red proof: pre-change `state_store.py` → `FAILED (failures=13)` on the same 22 tests. |
| 5 | Negative and boundary tests where risk warrants | PASS | Expired/boundary, stale restore, missing issue time, unauthenticated, no pod, raising tick, kill switch. |
| 5 | Tests deterministic (no wall-clock/network/random) | PASS | Clock, venue, and Redis injected; 22 tests in 0.997 s; no network. |
| 5 | Reviewer ran the commands and captured output | PASS | This document, "Checks run". |
| 5 | Hot-path benchmark attached | N/A | No hot-path change. |
| 5 | Backend/frontend compose and reachability | PASS | Built image booted in isolation: `/api/v1/health` 200, `/api/v1/status` 200; one transient empty reply before startup then 200, matching the PR note. |
| 5 | UI screenshot/recording | N/A | No UI change. |
| 6 | No per-tick allocation/clone/`format!` in hot path | N/A | No hot-path change; the tick loses a write rather than gaining work. |
| 6 | Complexity bounded and documented | PASS | No new loops or data structures. |
| 6 | LLM calls warm, budgeted, timeout-bounded | N/A | Untouched. |
| 6 | New schedulers off by default and costed | N/A | Untouched. |
| 7 | Names describe the domain | PASS | `restore_now_ms`, `safe_baseline`, `raw_policy`. |
| 7 | Errors carry context; no swallowed error | PASS | New branch documents the fail-closed rule; the pre-existing restore warning is unchanged. |
| 7 | No dead code, commented-out block, debug print | PASS | Renewal block and its comment removed cleanly. |
| 7 | Reads like surrounding code | PASS | Same comment density and idiom. |
| 7 | Public APIs documented where non-obvious | PASS | Existing docstring retained; new comment explains the authority boundary. |
| 8 | Config documented with safe defaults | N/A | No new config. |
| 8 | Observability adequate | PASS | No liveness marker by design (task 2.2 permits); the effective policy is observable via `GET /api/v1/status`. |
| 8 | Rollback possible without data restore | PASS | Revert of `3a06dfe`; no migration, no schema/wire change. |
| 8 | No implicit startup migration without a guard | PASS | Restore only reads the existing payload shape. |

## Notes and residual risk (non-blocking)

- **SPEC-R1-F01/F02** (spec stage) remain open minors on an unchanged, approved spec. F02 is satisfied vacuously because the change records no liveness state at all; F01 is covered by the concurrent-issuance test. They do not transfer into this stage.
- **Fail-safe downgrades, it does not halt.** After expiry, `get_effective_policy()` returns the safe baseline, which keeps `pod_carry` (0.50) and `pod_momentum` (0.25) enabled. This is the approved contract (proposal "Impact"), and the dry-powder floor stays satisfied, but operators should expect a downgrade rather than a stop.
- **Explicit cognitive issuance still renews.** `backend/agents/orchestrator.py:477` and `backend/agents/trading.py:78` remain the only `issued_at_ms` writers. This is the intended issuance path; the proposal's Non-goals explicitly leave the deterministic-fallback stamping policy out of this slice.
- **Scheduler cadence.** If `ENABLE_AUTO_LLM_SCHEDULER` is enabled, a cognitive cycle can still issue a fresh envelope on its own cadence. That is policy issuance, not a heartbeat, and is out of scope here.

## Checks run

- `docker build -f Dockerfile.backend -t robotrader-backend:ttl-review .` → exit 0 (image built with the release Rust binary).
- `docker run --rm -e PYTHONPATH=. robotrader-backend:ttl-review python -m unittest discover -s backend/tests -v` → `Ran 125 tests in 6.300s` / `OK (skipped=9)`, exit 0. The 22 new tests are present in the run (22 `test_policy_ttl_heartbeat` lines).
- `docker run --rm -e PYTHONPATH=. robotrader-backend:ttl-review python -m unittest backend.tests.test_policy_ttl_heartbeat -v` → `Ran 22 tests in 0.997s` / `OK`, exit 0.
- Red proof (independent): derived image with `master:backend/core/state_store.py` (sha256 verified identical) and the new tests → `Ran 22 tests in 0.984s` / `FAILED (failures=13)`, exit 1. Failures cover tick renewal (successful, unauthenticated, no-pod, raising, repeated), liveness/expiry, boundary-after-ticks, and all restore cases. Matches the PR claim.
- Edge probe (derived image): explicit JSON `null` → `safe_baseline_fallback`; `0` → `safe_baseline_fallback`; numeric string fresh → preserved; `"not-a-number"` → constructor `default_active()` (DEV-R1-F01).
- `cd engine-rs && cargo test --all-targets` → exit 0; 40 passed, 0 failed across 8 targets (2 + 1 + 14 + 5 + 18).
- `openspec validate fix-policy-ttl-heartbeat --strict` → `Change 'fix-policy-ttl-heartbeat' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check fix-policy-ttl-heartbeat` → `check: PASS`, exit 0 (18 done / 0 open; spec-r1 `APPROVE`, 2 findings; Review Card 152 words, 1 diagram, ~1.3 min).
- `gh pr checks 17` → rust pass, python pass, helm pass, frontend pass, sdlc pass.
- `gh api repos/hcross/robotrader/commits/11affbc.../check-runs` → all five check-runs `completed/success` with `head_sha=11affbc8947b4dc6882fe2894a07a87ab9283087`.
- `gh pr view 17 --json isDraft,headRefOid,mergeable` → `isDraft: true`, `headRefOid: 11affbc8947b4dc6882fe2894a07a87ab9283087`, `mergeable: MERGEABLE`.
- `git rev-parse HEAD` → `11affbc8947b4dc6882fe2894a07a87ab9283087` (equals PR head).
- Isolated boot: `/api/v1/health` → `200 {"status":"ok",...}`; `/api/v1/status` → `200`, `policy_envelope` keys exactly `asset_overrides`, `envelope_id`, `global_regime`, `issued_at_ms`, `pod_allocations`, `ttl_seconds`.
- Scope: `git diff --name-only master...HEAD -- engine-rs` → empty; `-- backend/core/schemas.py` → empty; no dependency files changed.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-policy-ttl-heartbeat",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "11affbc8947b4dc6882fe2894a07a87ab9283087",
  "verdict": "APPROVE",
  "summary": "The TTL fail-safe now holds: ticks and restores no longer extend policy authority, all required checks pass at the PR head, and only two non-blocking follow-ups remain.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/core/state_store.py:201,267-268",
      "evidence": "A persisted policy with a non-numeric issued_at_ms raises in PolicyEnvelope.from_dict; the broad restore except logs 'invalid literal for int()' and leaves the constructor's default_active() in place instead of safe_baseline_fallback. The approved spec scopes fail-closed restore to an omitted/null issue time.",
      "required_fix": "Not required in this round. File a follow-up on issue #8 (signing/auth slice #8.3/#8.5) to validate that issued_at_ms is an integer and fail closed to safe_baseline on any malformed persisted policy."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_policy_ttl_heartbeat.py:379-388",
      "evidence": "Only the key-omission case is tested; the explicit JSON null path is covered by the implementation's 'is None' check and verified by the reviewer probe but has no test.",
      "required_fix": "Optional follow-up: add a null-payload case to the same test class. The spec's scenario is omission, so this is non-blocking."
    }
  ],
  "closed": []
}
```

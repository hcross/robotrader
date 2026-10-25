# SPEC Review — Round 1

## Summary

APPROVE. The delta spec pins the two writers that defeat the TTL — the unconditional `issued_at_ms` renewal in `run_live_testnet_tick` (`state_store.py:528-531`) and the restore-time overwrite (`state_store.py:194-195`) — and folds the missing-`issued_at_ms` payload into the same fail-open class as a stricter safe default. The 6 requirements and 21 scenarios are unique, observable, and mapped one-to-one by tasks 1.1–1.8; signing, Redis shape, auth/CORS, and kill-switch wiring stay out of scope. All three checks pass. Two non-blocking wording minors concern concurrency and the optional liveness record; neither affects the stated outcome. Lane S remains defensible: two warm-path files plus tests, no wire, Redis, or Rust change.

## Findings

### SPEC-R1-F01 — minor — Tick immutability clause is not concurrency-safe
- Location: `openspec/changes/fix-policy-ttl-heartbeat/specs/policy-ttl/spec.md#L5` (Requirement: Live ticks preserve policy issue time)
- Evidence: The requirement states that "after any `run_live_testnet_tick()` call ... those two fields MUST equal their values before the call". The tick runs on a daemon thread (`backend/core/state_store.py:424-425`) while `OrchestratorAgent` can persist a new envelope via `set_policy` (`backend/agents/orchestrator.py:477-478`), so a concurrent explicit issuance can legitimately change the fields mid-call without the tick writing them.
- Required fix: Scope the equality assertion to the absence of a concurrent explicit issuance (e.g. "the tick itself MUST NOT write `issued_at_ms`/`ttl_seconds`; absent a concurrent `set_policy`, they are unchanged"), or reduce it to a pure no-write obligation.
- Status: open
- Origin: initial

### SPEC-R1-F02 — minor — Liveness scenarios assume a record the tasks make optional
- Location: `openspec/changes/fix-policy-ttl-heartbeat/specs/policy-ttl/spec.md#L33-53`; `openspec/changes/fix-policy-ttl-heartbeat/tasks.md#L19`
- Evidence: Scenario "A liveness tick does not change the expiry verdict" is conditioned on "a live-worker tick records liveness", while task 2.2 says "If a liveness timestamp is retained ... otherwise record no liveness state". With no liveness state recorded, the separation property is only vacuously satisfied and there is no marker to inspect.
- Required fix: Either state in the spec/tasks that this change records no liveness state (making Requirement 2 a forward-looking guardrail), or require an in-memory marker and assert its existence outside the envelope and persisted payload.
- Status: open
- Origin: initial

## Scope ruling — persisted policy without `issued_at_ms`

- **In scope.** `PolicyEnvelope.from_dict` defaults a missing `issued_at_ms` to the decode clock (`backend/core/schemas.py:95`), and restore overwrites it with the restore instant (`backend/core/state_store.py:194-195`). A payload omitting the key therefore resurrects as freshly issued — the same fail-open class as #8.2, not a distinct change.
- **Lane S fits.** One warm-path method plus tests; no `PolicyEnvelope` wire shape, Redis key/payload, REST/WS, or Rust change.
- **Testable.** Seed a fake Redis payload whose `policy` object lacks `issued_at_ms`, assert `get_effective_policy().envelope_id == "safe_baseline_fallback"` (already task 1.6). The guard belongs in `_load_persisted_state` reading the raw dict; changing `from_dict`'s generic default is unnecessary and would conflict with the exemption at `openspec/specs/contract/spec.md:216`.
- **Not a creep vector.** An omitted `ttl_seconds` is deliberately not covered (generic decode default, contract-exempt); keeping it out avoids expanding the slice.

## Checks run

- `openspec validate fix-policy-ttl-heartbeat --strict` → valid, exit 0.
- `scripts/sdlc/spec-lint.py --change fix-policy-ttl-heartbeat` → PASS (Review Card 152 words, 1 diagram, ~1.3 min; 18 open tasks).
- `scripts/sdlc/sdlc.sh check fix-policy-ttl-heartbeat` → `check: PASS`.
- Structural verification: 6 requirements / 21 scenarios, all names unique, every scenario has WHEN and THEN, all 21 mapped by tasks 1.1–1.8.
- Code verified at reviewed SHA: renewal `state_store.py:528-531`; restore overwrite `state_store.py:194-195`; strict `>` at `schemas.py:67-69`; safe baseline `safe_baseline_fallback` / `LOW_VOL_CARRY` / sniper disabled at `schemas.py:103-138`; no other unconditional `issued_at_ms` writer outside the out-of-scope cognitive cycle.
- Review Card read time: 1.3 min (≤ 5.0).

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-policy-ttl-heartbeat",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "30525f67ca738e754f3fe8301e578b03f58c1ad0",
  "verdict": "APPROVE",
  "summary": "TTL immutability and restore semantics are correctly and testably specified; two non-blocking wording minors remain.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-policy-ttl-heartbeat/specs/policy-ttl/spec.md#L5",
      "evidence": "Requirement asserts fields MUST equal their pre-call values after any tick, but the tick runs on a daemon thread while OrchestratorAgent can legitimately call set_policy concurrently (orchestrator.py:477-478).",
      "required_fix": "Scope the equality assertion to the absence of a concurrent explicit issuance, or reduce it to a no-write obligation on the tick."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-policy-ttl-heartbeat/specs/policy-ttl/spec.md#L33-53; tasks.md#L19",
      "evidence": "The liveness scenario presumes a recorded liveness tick, while task 2.2 permits recording no liveness state, making the separation property vacuous.",
      "required_fix": "State that this change records no liveness state, or require an in-memory marker and assert it exists outside the envelope and persisted payload."
    }
  ],
  "closed": []
}
```

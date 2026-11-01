# PLAN Review — Round 1

## Summary
APPROVED. The plan for change `sign-policy-and-flatten-killswitch` is sound, complete, and fully traceable to the approved specification at `5d5d3c11836fe2ec359ee73691cb7e4dfc0a8b21`. All 8 design decisions (D1–D8) trace directly to normative requirements and platform invariants, with concrete technical justifications for rejected alternatives. The architecture preserves the strict 6-key wire shape of `PolicyEnvelope` via detached `SignedPolicyBundle` wrapping, enforces pure-Rust zero-dependency cryptography within the 50 µs `HardRiskGate` budget, and produces deterministic reduce-only flatten intents upon kill-switch activation. 26 verifiable checkbox tasks across 6 groups cover every requirement and scenario in strict dependency order, supported by a 4-phase migration plan, a concrete 4-step rollback procedure, and robust verification commands. Zero open blocker or major findings.

## Assessed as sound

### 1. Traceability
- Every design decision (D1 through D8) traces directly to a normative requirement in `specs/control-plane-security/spec.md` or a core platform invariant.
- All 6 requirements (5 ADDED, 1 MODIFIED) across 19 scenarios are covered by specific tasks in `tasks.md`.
- No task introduces behavior beyond the approved specification; no hidden spec gaps in design.

### 2. Decisions & Architecture
- Decisions D1 through D8 include explicit alternatives considered and concrete technical rationales for rejections (avoiding circular hashing paradoxes, zero dependency overhead, DoS avoidance, hot-path budget protection).
- Wire shape invariance is strictly preserved: `PolicyEnvelope` retains its exact six keys, using detached `SignedPolicyBundle` for signature transport.
- Pure-Rust FIPS 180-4 SHA-256 and RFC 2104 HMAC-SHA256 implementations in `robotrader-common` introduce zero external crate dependencies and execute well under the 50 µs `HardRiskGate` budget (measured baseline ~0.244 µs).

### 3. Contracts, Safety & Security
- `MinimalRedisClient.set_with_ex` fulfills the documented `robotrader:policy:active` per-key `EX` TTL contract alongside the snapshot key `robotrader:v2:state`.
- State store signature verification failure fails closed to `PolicyEnvelope.safe_baseline()` (`safe_baseline_fallback`), logging security warnings without unhandled crash loops.
- `HardRiskGate.validate_signed_envelope` short-circuits immediately on signature failure with `Err(RiskRejection::InvalidPolicySignature)` without modifying gate state.
- `HardRiskGate.trigger_kill_switch_with_flatten` emits opposite-side reduce-only market orders sorted deterministically by asset symbol, preventing position expansion.

### 4. Test Strategy & Verification
- Unit and integration tests cover cross-language HMAC parity, tampering rejections, corrupted signatures, safe baseline fallback, Redis `SET ... EX` transport, socket exception resilience, and kill-switch intent emission/deactivation.
- Verification commands explicitly validate Rust unit/integration suites, node compilation, risk-gate latency benchmarks, Python unit/integration tests, OpenSpec strict validation, and spec-lint.

### 5. Migration & Rollback
- 4-phase migration sequence cleanly stages Rust hot-path engine, Python control plane, documentation alignment, and full-stack verification.
- 4-step rollback procedure defines concrete rollback actions and accounts for natural Redis TTL eviction without persistent residue.

## Findings

None.

## Checks run
- `git rev-parse HEAD` → `5d5d3c11836fe2ec359ee73691cb7e4dfc0a8b21`
- `openspec validate sign-policy-and-flatten-killswitch --strict` → `Change 'sign-policy-and-flatten-killswitch' is valid`
- `python3 scripts/sdlc/spec-lint.py --change sign-policy-and-flatten-killswitch` → `PASS` (122 words, 1 diagram, ~1.1 min)
- Checklist `sdlc/checklists/plan.md` walked item-by-item: all items `PASS`.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "sign-policy-and-flatten-killswitch",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "5d5d3c11836fe2ec359ee73691cb7e4dfc0a8b21",
  "verdict": "APPROVE",
  "summary": "Plan is comprehensively specified, fully traceable to requirements, preserves the 6-key wire shape and hot-path budget, and defines complete test, migration, and rollback strategies.",
  "findings": [],
  "closed": []
}
```

# PLAN Review — Round 1

## Summary

APPROVE. The implementation plan for change `fix-leaf-fleet-parity-honesty` (`design.md` and `tasks.md`) at commit `03a22fbd52d1353a80134533d95b94e3f074ee03` is architecturally sound, comprehensive, and fully traceable to the approved specifications (`proposal.md` and `specs/**`). Design decisions (D1–D6) provide explicit alternatives and technical rationales, data contracts preserve strict backward compatibility, and the 28 discrete tasks cover every requirement and scenario across 6 logical phases. Hot-path execution, the 50µs `HardRiskGate` budget, and `SimulatedVault` invariants are completely preserved.

## Checklist Walkthrough (`sdlc/checklists/plan.md`)

### 1. Traceability — PASS
- **Decision to requirement tracing**: Every design decision (D1: dual code definition with CI gate; D2: explicit `execution_mode`; D3: `ta_metrics_source`; D4: lowercase `"composite_sentiment"` with legacy alias; D5: dynamic confluence averaging with 0.0 neutral fallback; D6: fixed fixture timestamps with feed summary) maps directly to requirements in `specs/**`.
- **Requirement coverage**: Every requirement across `pod-catalog-parity`, `fleet-execution-honesty`, and `feed-panorama-provenance` is mapped to tasks in `tasks.md` with explicit `(covers: ...)` citations.
- **Scope discipline**: No task introduces behavior outside the approved SPEC.
- **Spec integrity**: No spec gaps exist; `design.md` adheres strictly to the approved specification scope.

### 2. Decisions — PASS
- **Alternatives considered**: Each decision (D1–D6) records three concrete alternatives considered.
- **Technical rationales**: Rejections cite specific technical reasons (startup subprocess latency, hot-path build-time codegen overhead, frontend state coupling, breaking API changes, ZeroDivisionError/denominator skew, deceptive synthetic timestamps).
- **Reversibility**: Additive attributes and backward-compatibility aliases are noted as low-risk and easily reversible.
- **Simplicity**: Code-level dual definition locked by automated CI assertions was selected over heavyweight IPC/FFI/codegen bridging.
- **Dependencies**: Zero new dependencies introduced in Rust, Python, or frontend.

### 3. Contracts and Data — PASS
- **`PolicyEnvelope` parity**: `PolicyEnvelope` is not modified and non-Solana policy compilation is explicitly a non-goal, preserving Rust/Python contract parity.
- **Backward compatibility**: All API additions (`execution_mode`, `scheduler_active`, `ta_metrics_source`, `source_kind`, `curated`, `feed_mode`, `live_count`, `curated_count`) are purely additive; legacy `"Composite_sentiment"` key and `/api/v1/hierarchy/overview` alias are preserved.
- **Serialization boundaries**: Output contracts on `robotrader-node --dump-pod-catalog` (stdout JSON), FastAPI endpoints, and RSS dictionaries are explicitly defined.
- **Data isolation**: Per-leaf boundaries and isolated pod specs are maintained across all 26 ecosystems.

### 4. Hot Path and Performance — PASS
- **Zero hot-path impact**: No LLM calls, blocking I/O, or unbounded loops in `StrategyPod::on_market_event` or `HardRiskGate::validate`.
- **Latency budget**: The 50µs risk gate budget is unaffected.
- **Complexity bounds**: Confluence averaging ($N \le 10$), RSS feed summarization ($N \le 5$), and 26-leaf iteration are bounded with $O(N)$ / $O(1)$ complexity.
- **Failure modes**: Empty technical snapshots fall back to 0.0 without ZeroDivisionError; offline network falls back to `CURATED_FALLBACK` mode; unknown CLI leaf IDs exit with non-zero status.

### 5. Safety and Security — PASS
- **Capital protection**: Sizing, 20% dry powder reserve, drawdown kill switch, and CostGuard limits are untouched.
- **Vault simulation**: `SimulatedVault` is untouched; zero Python key custody and simulated address whitelists remain invariant.
- **Boundary validation**: CLI `--leaf-id` is validated against the 26 canonical IDs.
- **No secrets**: No secret material in logs, transcripts, or fixtures.

### 6. Test Strategy — PASS
- **Scenario mapping**: Tasks 5.1–5.3 map all normative scenarios to automated tests in `backend/tests/test_hierarchy_v3.py`.
- **Dual parity gate**: Parity between Python `_build_rust_pods_for_leaf` and Rust `ecosystem_pod_specs` is asserted for 100% attribute equality across all 26 leaves.
- **Negative testing**: Tests cover invalid CLI leaf ID rejection, pod attribute mismatch detection, and empty snapshot fallback.
- **Determinism**: Elimination of synthetic timestamps (`now_ms - idx * 420_000`) in favor of fixed fixture timestamps ensures deterministic RSS fixture testing.

### 7. Rollout and Rollback — PASS
- **Deployment sequencing**: Explicit 4-phase rollout: Rust Engine -> Backend Parity & Provenance -> Frontend Badges -> Documentation Updates.
- **Concrete rollback**: Documented procedure using `git revert <commit-sha>`, binary rebuild, and `docker compose up --build -d`.
- **Observability**: Execution mode and telemetry classification badges surfaced in `MasterOverview` and `LeafAgentView`.
- **Cost assessment**: Non-Solana leaves remain unscheduled, ensuring zero unplanned LLM spend.

### 8. Tasks — PASS
- **Task formatting**: 28 tasks formatted as `- [ ] X.Y` under 6 numbered dependency-ordered groups.
- **Granularity & sizing**: Each task is verifiable, constrained to specific source files, and sized for single-session execution.
- **Verification commands**: Section `## Verification` lists exact commands for Rust test, node CLI build, Python test suite, frontend build, and OpenSpec validation.

## Findings

None. Zero open blockers or majors.

## Checks Run
- `openspec validate fix-leaf-fleet-parity-honesty --strict` → pass (exit 0)
- `python3 scripts/sdlc/spec-lint.py --change fix-leaf-fleet-parity-honesty` → pass (Review Card 152 words, 1 diagram, ~1.3 min, lane L)
- `git rev-parse HEAD` → `03a22fbd52d1353a80134533d95b94e3f074ee03`

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-leaf-fleet-parity-honesty",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "03a22fbd52d1353a80134533d95b94e3f074ee03",
  "verdict": "APPROVE",
  "summary": "The plan is approved. Design decisions, data contracts, failure modes, and 28 tasks map with complete traceability to the approved SPEC without modifying hot-path, risk-gate, or simulated vault invariants.",
  "findings": [],
  "closed": []
}
```

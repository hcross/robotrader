# DEV Review — Round 1

## Summary

**APPROVE.** The cost-aware hurdle is implemented as approved: one canonical cost model in `common`, `SmartExecutionRouter` delegating to it, and `validate` rejecting unless `edge > 2 × fee + spread + max_slippage_bps + sanitized buffer`, with the safety-first gate order preserved. The SCAM-SOL fixture still returns `OnChainRugCheckFailed`, the Solana baseline regenerated to 4 trades / 3 rejections / 2 pods from real node JSON, and all 26 leaf assertions are exact. The workspace tests, the Python image suite (191 tests, 9 skipped), the frontend build, the contract check, OpenSpec, the SDLC check, and all five CI jobs pass. The benchmark reproduces at ~262 ns (published 244 ns), far inside 50 µs. Three minor and two nit items remain, none blocking; issue #4 remains open for the out-of-scope items.

## Findings

### DEV-R1-F01 — [minor] Criterion's MSRV is recorded only in the PR body, not in the repository

- Location: `engine-rs/crates/risk-gate/Cargo.toml:17-20`; PR #20 body, "New dependencies".
- Evidence: The dev-dependency comment records `default-features = false`, `features = ["cargo_bench_support"]`, dev-only status, and the no-cycle rationale, but not the MSRV. `grep -rn "1.86" engine-rs docs README.md AGENTS.md .github/` returns no hit; the only statement is the PR body ("MSRV 1.86, Apache-2.0 OR MIT"). PLAN-R1-F07 required the MSRV to be recorded, and `sdlc/PROTOCOL.md` makes repository artifacts canonical for content.
- Required fix: Add the `criterion` MSRV (`1.86`) and the toolchain used for the published benchmark to the `Cargo.toml` dev-dependency comment (or a committed docs note).
- Status: open
- Origin: initial

### DEV-R1-F02 — [minor] The audit's per-rejection breakdown has no node-JSON or test provenance

- Location: `docs/PERFORMANCE_AND_COST_AUDIT.md:91,97`; `engine-rs/crates/backtest/src/lib.rs:526,565-593`.
- Evidence: `cargo run --quiet --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id leaf-solana` exposes `rejected_orders: 3` but no rejection reasons; the new fixture test asserts the count and the SCAM-SOL variant, not the two hurdle rejections. The audit's `70.2/87.2` (JUP-SOL) and `95.0/151.4` (AIX-SOL) and the `leaf-bitcoin` "1 rejection by the cost hurdle" are correct when derived from the frozen fixture (`engine-rs/crates/strategies/src/lib.rs:340,353,418-419`) and the canonical helpers, but the spec's rule that every `[FIXTURE]` figure matches the node JSON cannot be checked for them.
- Required fix: Add a targeted test that drives the JUP-SOL smart-money and AIX-SOL sniper fixture intents (and the Bitcoin leaf rejection) through `HardRiskGate::validate` and asserts `InsufficientEdge` with those hurdles, or reduce the audit to the figures the JSON exposes.
- Status: open
- Origin: initial

### DEV-R1-F03 — [minor] Regenerated audit prose remains French, contrary to the English-only repository rule

- Location: `docs/PERFORMANCE_AND_COST_AUDIT.md:4,39-40,67,81,91,145`.
- Evidence: New/regenerated lines such as "`3` rejets critiques — `2` par le hurdle de coût …" and "mesuré à `0.244 µs` en moyenne" are French. `openspec/config.yaml` requires English-only repository content; the audit's language note covers the pre-existing French body and the earlier integrity change, and PLAN-R1-F08 required new/regenerated annotations to be English. Only the benchmark note at line 27 is English.
- Required fix: Translate the new/regenerated annotation prose to English, leaving untouched pre-existing French text, or extend the recorded legacy exception explicitly to these lines.
- Status: open
- Origin: initial

### DEV-R1-F04 — [nit] Residual bare `<50µs` claims remain outside the spec's four-file inventory

- Location: `docs/adr/0001-hybrid-quant-agentic-architecture.md:140`; `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md:40`; `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md:63`; `backend/core/hierarchy.py:141`; `backend/agents/orchestrator.py:29,237`; `frontend/src/components/Dashboard.jsx:158`; `frontend/src/App.jsx:187`; `frontend/src/components/LeafAgentView.jsx:356`.
- Evidence: `grep -rnE "< ?50 ?µs" README.md AGENTS.md docs/ backend/ frontend/` finds these occurrences after the change. The approved delta spec's scenario named only `README.md`, `AGENTS.md`, `docs/architecture.md`, and `docs/PERFORMANCE_AND_COST_AUDIT.md`; those four are clean. The residual claims are not false (`0.244 µs < 50 µs`) but remain unannotated, and frontend/backend copy is outside this change's approved scope.
- Required fix: Track them as a follow-up in issue #4 (or a separate docs/UI change) to annotate or remove; do not expand this PR's scope.
- Status: open
- Origin: initial

### DEV-R1-F05 — [nit] PR / Review Card metadata is stale

- Location: PR #20 body; `openspec/changes/fix-risk-gate-cost-hurdle/proposal.md`, Review Card Effort cell (approved at `3a05029`).
- Evidence: The approved Review Card still says "one SPEC round" while the history has two; the PR body already notes this for the conductor. The PR body's DEV delta stat says 18 files, +1575/−140 while `git diff --stat 6ed356c...e349886` reports +1576/−141, and its test counts ("3 node", "14 common") differ from the observed 1 node and 15 common. Every command still passes.
- Required fix: The conductor annotates the issue/PR metadata and the Review Card wording in the status surface; no code change is required or permitted in this stage.
- Status: open
- Origin: initial

## Checklist (sdlc/checklists/dev.md)

### 0. Scope
- Diff implements only the approved spec/plan — **PASS**. `git diff --stat master...e349886` = 29 files (18-file DEV delta); `proposal.md`, `specs/**` unchanged since `3a05029`, `design.md` unchanged since `6ed356c`, `tasks.md` only checkboxes ticked.
- No unrelated refactor, formatting sweep, or dependency bump — **PASS**. Only the criterion dev-dependency and the test-only exec-router edge are added; docs changes are the specified regeneration.
- Diff matches the PR description and issue logbook — **PASS**, with the metadata discrepancies recorded in DEV-R1-F05.
- No generated artifacts, secrets, or local data committed — **PASS**. `Cargo.lock` is intentionally committed; evidence stays gitignored; diff scan found no key material.

### 1. Correctness
- Every changed behavior maps to a scenario or invariant — **PASS**. All nine delta-spec requirements have tests (hurdle, canonical cost, buffer, strict boundary, precedence, non-regression, fixture regeneration, benchmark, report value).
- Error paths return a typed failure; no silent `unwrap`/broad `except` — **PASS**. The new gate code returns `RiskRejection::InsufficientEdge`; no `unwrap` in the new production code.
- Boundary conditions handled (empty, zero, negative, overflow, partial fill) — **PASS**. Edges 4.4/4.5/6.5/6.6, zero/negative/NaN buffer, NaN edge, zero Kelly, equality rejection are all asserted.
- Concurrency — **N/A**. `validate` is synchronous and stateful only through the kill switch.
- Time and units explicit — **PASS**. bps, µs, ns, `u32`, `f64`, and `u64` timestamps are explicit.

### 2. Robotrader hard invariants
- Zero LLM calls, blocking I/O, or unbounded sleeps in the hot path — **PASS**. The hurdle is pure `f64` arithmetic over `Copy` enums.
- `HardRiskGate::validate` within 50 µs; no allocation or logging — **PASS**. Measured 261.54 ns mean; the diff adds no allocation, log, I/O, sleep, or loop; the pre-existing envelope and `ApprovedOrder` clones are unchanged.
- `PolicyEnvelope` Rust/Python parity — **PASS**. `python3 scripts/check_contract_single_source.py --root .` → `contract single source: OK`; no PolicyEnvelope field changed.
- Capital protection intact (dry powder ≥ 20%, Kelly, drawdown kill-switch, CostGuard cap) — **PASS**. No threshold changed; drawdown, Kelly, leverage, and refill tests pass.
- No unbounded refill reintroduced — **PASS**. Both `validate_inference_refill` scenarios pass.
- Vault labelled `SIMULATED` at every surface — **N/A / PASS**. No vault or signing surface touched; vault contract tests pass.
- Python holds no key custody — **PASS**. The Python change is a test assertion only; the suite passes.
- `destination_whitelisted` / `key_zeroized_after_sign` derived from the call — **N/A**. No vault change.
- No docstring/comment/document claims real derivation, chain-valid signing, or mainnet custody — **PASS**. No such claim added.
- Backtest == paper == live — **PASS**. The hurdle lives in the single shared `validate`; no live-only branch.
- Leaf isolation — **PASS**. The hurdle reads only the intent and `RiskLimits`.
- `backend/core/` warm-path infrastructure; `import strands` not shadowed — **PASS**. No production backend change; the Python suite passes.

### 3. Contracts and compatibility
- Rust/Python schemas agree field-for-field — **PASS**. Contract check green; no serialized contract changed.
- Redis IPC keys, TTLs, payload shapes backward compatible — **PASS**. No Redis code touched.
- REST/WS documented; frontend still builds — **PASS**. No REST/WS change; `npm --prefix frontend run build` succeeds.
- Serialization has no precision loss — **PASS**. No serialized type changed; `RiskLimits` is Rust-only with no in-repo serializer/consumer.
- Existing consumers updated or additive — **PASS**. `SmartExecutionRouter::fee_bps_for` / `slippage_bps_for` signatures and behavior are unchanged (delegation only).

### 4. Security
- Trust-boundary inputs validated — **PASS**. No new trust boundary.
- No secret/private key/API token/production address — **PASS**. Diff scan clean.
- On-chain safety checks not bypassed — **PASS**. Token safety runs before the hurdle; the SCAM-SOL rug test passes.
- Dependencies pinned, no critical advisory — **PASS**. `criterion 0.8.2` is locked and dev-only; exec-router is a path dev-dependency.
- Least privilege — **PASS**. No file/network permission change.

### 5. Tests and evidence
- New behavior has a test that would fail without the change — **PASS**. Hurdle, buffer, boundary, NaN, precedence, parity, and SCAM-SOL tests are new.
- Negative and boundary tests exist where the risk warrants — **PASS**. See above.
- Tests deterministic — **PASS**. Fixed fixtures, no wall clock/network/random.
- Reviewer ran the commands and captured the output — **PASS**. See "Checks run".
- Hot-path benchmark/latency measurement attached — **PASS**. Criterion measured 0.262 µs approved / 0.191 µs rejected.
- Backend/frontend `docker compose up --build -d` — **N/A**. The Python change is test-only and the frontend production code is unchanged; the backend image suite and the frontend build were run instead.
- UI screenshot/recording — **N/A**. No UI change.

### 6. Performance and cost
- No new per-tick allocation, clone, or `format!` — **PASS**. Pure helpers; pre-existing clones unchanged.
- Complexity bounded and documented — **PASS**. Constant-time match over `Venue` × `OrderType`.
- LLM calls warm-path, budgeted, timeout-bounded — **N/A**. No LLM change.
- New schedulers off by default and costed — **N/A**. No scheduler change.

### 7. Maintainability
- Names describe the domain — **PASS**. `fee_bps_for`, `spread_bps_for`, `min_edge_buffer_bps`, `hurdle_bps`.
- Errors carry context — **PASS**. `InsufficientEdge` reports edge and computed hurdle.
- No dead code, commented-out block, or debug print — **PASS**.
- Reads like the surrounding code — **PASS**.
- Public APIs documented where the contract is non-obvious — **PASS**. Cost helpers, `RiskLimits`, and `validate` carry Rustdoc.

### 8. Operations
- Config documented with safe defaults — **PASS**. `min_edge_buffer_bps = 2.0`, sanitized to `0.0` for negative/non-finite values, documented.
- Observability adequate — **PASS**. The rejection payload now carries the computed hurdle; no hot-path logging added.
- Rollback possible without a data restore — **PASS**. PR body rollback is revert-only; no schema/IPC/policy migration.
- No implicit migration on startup — **PASS**. No migration introduced.

## Checks run

- `cargo test --manifest-path engine-rs/Cargo.toml --workspace --all-targets` → **PASS**. `robotrader-backtest` 3; `robotrader-common` 1 + `asset_override_contract` 14; `robotrader-exec-router` 3; `robotrader-node` 0 + `simulated_vault_contract` 1; `robotrader-risk-gate` 17; `robotrader-strategies` 0 + `momentum_rules` 18. The bench target ran in criterion test mode (`Testing validate/approved` / `Testing validate/rejected_hurdle` / `Success`). No compiler warnings.
- `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` → **PASS**. `validate/approved` [251.11 ns, 261.54 ns, 279.07 ns], mean **261.54 ns (0.262 µs)**; `validate/rejected_hurdle` [189.29, 190.87, 192.82] ns, mean 190.87 ns. Both far below 50 µs. The published 244.15 ns is within run-to-run variance (criterion flagged +4.68 % versus its stored baseline).
- `cargo run --quiet --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id leaf-solana` → **PASS**. `total_trades: 4`, `rejected_orders: 3`, `pod_pnl_attribution: {pod_momentum: 11.112960524076215, pod_carry: 13.614211628444282}`, `net_profit_usd: 24.727172152519415`, `sharpe_ratio: 128.52308889884674`, `total_fees_usd: 1.4711945828105164`, `max_drawdown_pct: 0.0`. Matches the audit and the Python assertion.
- `cargo run --quiet --manifest-path engine-rs/Cargo.toml -p robotrader-node -- --leaf-id leaf-bitcoin` → **PASS**. `total_trades: 3`, `rejected_orders: 1`, `net_profit_usd: 19.58224799920572`, `sharpe_ratio: 238.9725417073524`, win rate 100.0 %, max drawdown 0.0 %. Matches the audit.
- `cargo test -p robotrader-backtest -- --nocapture` (covered by the workspace run) → **PASS**. Solana 4/3/2; SCAM-SOL `OnChainRugCheckFailed`; 26-leaf exact assertions.
- `python3 scripts/check_contract_single_source.py --root .` → **PASS**. `contract single source: OK (contracts/policy_contract.conf)`; exit 0.
- `docker compose build backend` → **PASS** (image `4-fix-risk-gate-cost-hurdle-backend`). `docker run --rm -e PYTHONPATH=/app -w /app 4-fix-risk-gate-cost-hurdle-backend python -m unittest discover -s backend/tests -v` → **PASS**. `Ran 191 tests in 7.652s`, `OK (skipped=9)`, exit 0.
- `npm --prefix frontend run build` → **PASS**. Vite/Rolldown built 1694 modules in 400 ms; no errors.
- `openspec validate fix-risk-gate-cost-hurdle --strict` → **PASS**. `Change 'fix-risk-gate-cost-hurdle' is valid`.
- `scripts/sdlc/sdlc.sh check fix-risk-gate-cost-hurdle` → **PASS**. `check: PASS`; 35 tasks done, 0 open; spec-lint PASS; plan-r1/spec-r1/spec-r2 verdict-lint PASS.
- `gh pr checks 20` → **PASS**. rust pass 19 s; sdlc pass 9 s; python pass 44 s; frontend pass 11 s; helm pass 7 s. (The first query showed python pending; the re-query after the local suite completed showed it passing.)
- `gh pr view 20 --json isDraft,headRefOid,mergeable` → `isDraft: true`, `headRefOid: e3498862655c265bcfc431e5407b5e5158fe1df6`, `mergeable: MERGEABLE`. `reviewed_sha` equals the PR head.
- Greps: `grep -rn "min_edge_over_cost_bps" engine-rs` → no hits; `grep -n "50µs" README.md AGENTS.md docs/architecture.md docs/PERFORMANCE_AND_COST_AUDIT.md` → no hits; `grep -rn "AntiRugRejected"` in `README.md`/`docs/` → no hits; stale figures (`22.78`, `28.22`, `6 trades`, `6 gains`, `$1.67`, `34.25`, `20.47`, `$9.70`, `$11.91`) → no hits. A secrets regex over the diff produced only false positives (`risk-gate` matching `sk-`); no key material.
- Scope/inputs: `git diff master...e349886 -- engine-rs/crates/strategies/src/lib.rs` → empty; the backtest diff is confined to the test module; `BacktestSummary` is unchanged; the new SCAM-SOL test drives `HardRiskGate::validate` directly. `proposal.md`/`specs/**` unchanged since `3a05029`; `design.md` unchanged since `6ed356c`.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-risk-gate-cost-hurdle",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "e3498862655c265bcfc431e5407b5e5158fe1df6",
  "verdict": "APPROVE",
  "summary": "Cost-aware hurdle implemented as approved; safety gate order and SCAM-SOL anti-rug preserved; 4/3/2 Solana baseline and 26-leaf assertions regenerated; full workspace, Python image suite, frontend build, contract check, OpenSpec, SDLC check, and all CI jobs pass; benchmark measures 0.262 µs. Three minor and two nit findings remain, none blocking.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/risk-gate/Cargo.toml:17-20; PR #20 body (New dependencies)",
      "evidence": "The dev-dependency comment records default-features=false, cargo_bench_support, dev-only status, and the no-cycle rationale, but not the MSRV. grep -rn \"1.86\" engine-rs docs README.md AGENTS.md .github/ returns no hit; the only statement is the PR body (MSRV 1.86, Apache-2.0 OR MIT).",
      "required_fix": "Add the criterion MSRV (1.86) and the benchmark toolchain to the Cargo.toml dev-dependency comment or a committed docs note."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "docs/PERFORMANCE_AND_COST_AUDIT.md:91,97; engine-rs/crates/backtest/src/lib.rs:526,565-593",
      "evidence": "The leaf-solana node JSON exposes rejected_orders=3 but no rejection reasons; the new test asserts the count and the SCAM-SOL variant, not the two hurdle rejections. The audit's 70.2/87.2, 95.0/151.4, and leaf-bitcoin rejection reason are correct by deriving from the frozen fixture and canonical helpers, but cannot be checked against the node JSON.",
      "required_fix": "Add a targeted test that drives the JUP-SOL, AIX-SOL, and Bitcoin fixture intents through HardRiskGate::validate and asserts InsufficientEdge with those hurdles, or reduce the audit to the figures the JSON exposes."
    },
    {
      "id": "DEV-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "docs/PERFORMANCE_AND_COST_AUDIT.md:4,39-40,67,81,91,145",
      "evidence": "New/regenerated lines such as '3 rejets critiques — 2 par le hurdle de coût' and 'mesuré à 0.244 µs en moyenne' are French, while openspec/config.yaml requires English-only repository content and PLAN-R1-F08 required new/regenerated annotations to be English. Only the benchmark note at line 27 is English.",
      "required_fix": "Translate the new/regenerated annotation prose to English, leaving untouched pre-existing French text, or extend the recorded legacy exception explicitly to these lines."
    },
    {
      "id": "DEV-R1-F04",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "docs/adr/0001-hybrid-quant-agentic-architecture.md:140; docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md:40; docs/adr/0003-hierarchical-multi-ecosystem-architecture.md:63; backend/core/hierarchy.py:141; backend/agents/orchestrator.py:29,237; frontend/src/components/Dashboard.jsx:158; frontend/src/App.jsx:187; frontend/src/components/LeafAgentView.jsx:356",
      "evidence": "grep -rnE \"< ?50 ?µs\" over README.md, AGENTS.md, docs/, backend/, and frontend/ still finds these claims. The approved delta spec named only README.md, AGENTS.md, docs/architecture.md, and docs/PERFORMANCE_AND_COST_AUDIT.md; those four are clean. The residual claims are not false (0.244 µs < 50 µs) but are unannotated, and frontend/backend copy is outside this change's approved scope.",
      "required_fix": "Track the residual claims as a follow-up in issue #4 or a separate docs/UI change to annotate or remove them; do not expand this PR's scope."
    },
    {
      "id": "DEV-R1-F05",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "PR #20 body; openspec/changes/fix-risk-gate-cost-hurdle/proposal.md Review Card Effort cell (approved at 3a05029)",
      "evidence": "The approved Review Card still says 'one SPEC round' while the history has two; the PR body already notes this for the conductor. The PR body's DEV delta stat says 18 files, +1575/-140 while git diff --stat 6ed356c...e349886 reports +1576/-141, and its test counts (3 node, 14 common) differ from the observed 1 node and 15 common. Every command still passes.",
      "required_fix": "The conductor annotates the issue/PR metadata and the Review Card wording in the status surface; no code change is required or permitted in this stage."
    }
  ],
  "closed": []
}
```

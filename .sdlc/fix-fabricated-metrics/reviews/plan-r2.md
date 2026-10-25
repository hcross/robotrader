# PLAN Review — Round 2 (closure)

## Summary

Verdict: **APPROVE**. All 17 R1 findings are closed at `fd9eff5`. The revision removes the mixed `testnet_telemetry` values, adds `contract_version: 2` and its communication, labels all four real-call drawer sites, scopes the `rust_leaf_backtest` gate to production modules, discloses and tests the 200-row window basis, completes the Redis compaction payload, labels both backtest branches, splits performance from operational rendering with an executable static check, derives performance on every leaf-detail path, and splits the oversized test tasks. No open blocker/major remains. One new minor regression is recorded: the `solana_onchain_pnl_sol` grep gate spans `backend/tests/` while the design promises an absence test that would contain the token. Non-blocking follow-ups are listed after the table.

## Prior findings (closure)

| ID | Status | Evidence at `fd9eff5` |
|---|---|---|
| PLAN-R1-F01 | closed | `tasks.md#L13` removes `simulated_model_pnl_usd` and `solana_onchain_pnl_sol`; `design.md#L87` (D17) and `#L177` keep one `MEASURED` population; the `curl` at `tasks.md#L124` asserts both keys absent and `tasks.md#L104` greps both names. |
| PLAN-R1-F02 | closed | `tasks.md#L23` (2.4) emits `contract_version: 2` in `get_system_status`; `tasks.md#L82` (8.7) records the `BREAKING CHANGE:` footer and issue note; `design.md#L244` maps D14 to 2.4/8.7; the status `curl` asserts the value. |
| PLAN-R1-F03 | closed | `design.md#L191` enumerates all four sites (`strategy_ledger` ~L479, `leaf_solana` mirror ~L501, `master_orchestrator` ~L743, per-leaf ~L910) with `LLM` vs `DETERMINISTIC_FALLBACK`; `tasks.md#L44` (4.5) labels them and `#L47` (4.8) tests a `strategy_ledger` `LLM` write. |
| PLAN-R1-F04 | closed | `tasks.md#L101` scopes the gate to `backend/core backend/agents backend/server.py`; `design.md#L139` (D4) and `tasks.md#L8` state that `backend/tests/` is excluded because the rejection test contains the token. |
| PLAN-R1-F05 | closed | `design.md#L127` discloses the recent 200-row basis and the divergence from `cumulative_cex_pnl_usd`; `#L254` records the risk; `tasks.md#L21` (2.2) names the window in `source_detail`, `#L30` (2.11) adds the >200-row eviction test, `#L71` (7.2) puts the basis in the audit legend. |
| PLAN-R1-F06 | closed | `design.md#L143-L155` (D7) defines `_persisted_payload()` as the complete payload (capital, thesis, five-key leaves, deposit/checkout histories); `tasks.md#L35-L36` (3.2/3.3) share it with `persist()` and assert all four top-level fields survive compaction. |
| PLAN-R1-F07 | closed | `tasks.md#L11` (1.5) sets `source = FIXTURE` in `run_rust_backtest`, so the `leaf-solana` early return is labelled; `#L16` (1.10) tests `run_rust_backtest_for_leaf("leaf-solana")` and the POST summary; `design.md#L139` matches. |
| PLAN-R1-F08 | closed | `design.md#L82` (D12) and `#L202-L213` define `formatMetric` (source gate first) and `formatOperational` (null-aware, badge-free); `tasks.md#L58` (6.1), `#L61` (6.4), `#L65` (6.8) implement and assert `0.0 -> $0.00`, `null -> —`. |
| PLAN-R1-F09 | closed | `tasks.md#L61-L63` (6.4-6.6) enumerate every spec surface and remove the coercions; `#L64` (6.7) creates `frontend/scripts/check-provenance.mjs` (import/invocation plus forbidden defaults); `#L66` (6.9) enumerates the null-state screenshots. |
| PLAN-R1-F10 | closed | `tasks.md#L22` (2.3) requires the snapshot, `GET /api/v1/leaf/{leaf_id}`, and the mandate response to pass `get_population_metrics()`; `#L29` (2.10) tests both endpoints; `design.md#L129` states the defensive null path. |
| PLAN-R1-F11 | closed | `tasks.md#L15` (1.9) creates `backend/tests/test_integrity_provenance.py` with the auditor-source test; `#L76` (8.1) names the same file; `#L89` requires `Ran [1-9][0-9]* test` and `OK`, so zero discovery fails. |
| PLAN-R1-F12 | closed | `design.md#L79` (D9) and `#L189` require filtering the full drawer list by wing/source before the limit; `tasks.md#L42` (4.3) states the order and `#L46` (4.7) tests an eligible `LLM` drawer behind newer `BOOTSTRAP` drawers. |
| PLAN-R1-F13 | closed | `tasks.md#L25` (2.6) removes `active_positions_count = 0` from `emergency_liquidate_leaf`; `#L27` (2.8) tests the post-liquidation leaf is `null`. |
| PLAN-R1-F14 | closed | `tasks.md#L63` (6.6) treats a missing `executions_source` as `UNATTRIBUTED`; `#L64` (6.7) rejects `|| 'backtest_fixture'` in the static script. |
| PLAN-R1-F15 | closed | `design.md#L86` (D16) scopes figure blocks to §1/§3 trading-performance figures, labels §2/§4 cost tables as operational, and records the English/legacy-French rule; `tasks.md#L70-L71` (7.1/7.2) implement it. |
| PLAN-R1-F16 | closed | `tasks.md#L9`, `#L11-L14`, `#L40` reference `provenance.METRIC_SOURCES` / `DRAWER_SOURCES` / mapping helpers; `design.md#L244-L245` adds the D14 and D15 traceability rows. |
| PLAN-R1-F17 | closed | `tasks.md#L26-L30` split old 2.6 into 2.7-2.11; `#L45-L47` split 4.6 into 4.6-4.8; `#L76` limits 8.1 to the recursive payload test, with evidence/rollout in 8.2-8.8. |

## New findings

### PLAN-R2-F01 — [minor, regression] `solana_onchain_pnl_sol` gate spans `backend/tests/` while the design promises a test containing it

- Location: `tasks.md#L104`; `design.md#L253`; `tasks.md#L15` (1.9).
- Evidence: The D17 gate is `git grep -n 'solana_onchain_pnl_sol' -- backend`, which includes `backend/tests/`. The same revision's risk statement says "a test asserts no `simulated_model_pnl_usd` or `solana_onchain_pnl_sol` remains". Any such test in `backend/tests/test_integrity_provenance.py` necessarily contains the literal and fails the gate. The sibling `simulated_model_pnl_usd` gate is correctly scoped to `backend/core/state_store.py`; F04 fixed the identical contradiction for `rust_leaf_backtest`. The contradiction is latent because no task currently assigns the absence test, so a strict task-by-task DEV can pass.
- Required fix: Scope the `solana_onchain_pnl_sol` grep to `backend/core/state_store.py` (mirroring its sibling) or exclude `backend/tests`, and either assign the absence assertion to task 1.9/8.1 or drop the "a test asserts" sentence from the Risks section.
- Status: open · Origin: regression

## Checklist walk

1. **Traceability** — PASS. D1-D17 each have a rationale; `design.md#L226-L245` maps every one of the 14 requirements to decisions and tasks; `contract_version` is authorized by D14 as the breaking-change mechanism; the spec/proposal are unchanged since `a17d3a2`.
2. **Decisions** — PASS. Every decision has alternatives and a technical rejection reason; D1 and D15 explicitly avoid new dependencies; reversible cache handling is separated from the one-way payload break (D14).
3. **Contracts and data** — PASS. `PolicyEnvelope` untouched (`N/A` for parity); `contract_version: 2` plus the PR/issue note covers the breaking shape; D7 defines JSON payload contents and the disposable-cache migration; attribution is a single constant (`leaf-solana`), preserving chain isolation.
4. **Hot path and performance** — PASS. Warm path only; no `engine-rs` change (task 8.4); `HardRiskGate` untouched (`N/A`); the 200-row window and filter-before-limit have explicit bounds.
5. **Safety and security** — PASS. Refill now uses measured non-null PnL with no floor (`max(125.0)` removed) and fails closed on `0.0`; vault is untouched (`N/A`); provenance normalisers fail closed to `BOOTSTRAP`; no secrets in artifacts or evidence.
6. **Test strategy** — PASS. Tasks 2.7-2.11, 3.3, 4.6-4.8, 5.4, 6.7-6.9, 7.2 and 8.1 plus the executable `## Verification` cover the scenarios; negative/boundary cases include nulls, single-row Sharpe, and >200-row eviction.
7. **Rollout and rollback** — PASS. Migration Plan orders backend → frontend → docs → deploy; rollback is concrete (revert, redeploy, optional Redis key deletes) with a confirm curl; badges/`source_detail` are the observability surface; no new recurring cost.
8. **Tasks** — PASS. 56 checkboxes in 8 numbered groups; no circular dependency (1.2 may create the test file it names before 1.9 formalizes it); `## Verification` commands are root-runnable and produce observable evidence; no task hides a spec change.

## Non-blocking follow-ups (not in the machine verdict)

- `backend/tests/test_metrics_populations.py:148` still asserts the old free-text `backtest_fixture.source`. Task 1.3 changes it to the enum; task 8.3 permits deliberate shape changes, but the edit is not named.
- `MasterOverview.jsx#L354` / `#L368` use `dry_powder_ratio || 0.23` and `min_dry_powder_ratio || 0.2`; the static script rejects `0.232` but not these derived defaults.
- `LeafAgentView.jsx#L501` (`tokens_used || 0`) is not explicitly routed through `formatMetric`, although D12 says `BOOTSTRAP` telemetry renders `—`.
- The orchestrator's internal `get_hierarchy_snapshot(cost_status=...)` call does not pass populations; its `active_leaves_summary` will be null for `leaf-solana`. Task 2.5's null-safe read makes this acceptable but the prompt loses measured context.
- Task 1.5 says the non-Solana branch "keeps `executions_source = "backtest_fixture"`" while the code currently sets `rust_leaf_backtest`; the wording should say "changes". The intent is clear from D4 and the grep gate.
- The spec scenario "Free text moves to source detail" has no explicitly assigned assertion (`curl` checks the enum, not `source_detail`).
- `parsed_from_llm` is not an existing variable; DEV must introduce it. The intent is clear from task 4.5.

## Checks run

- `git rev-parse HEAD` → `fd9eff5609b76affbb4053c7d919500575a92d84`.
- `openspec validate fix-fabricated-metrics --strict` → PASS: `Change 'fix-fabricated-metrics' is valid`.
- `scripts/sdlc/sdlc.sh check fix-fabricated-metrics` → PASS: `spec-lint` PASS (Review Card 183 words, 1 diagram, ~1.4 min, 56 open tasks), `verdict-lint` PASS (spec-r1 `CHANGES_REQUESTED`, spec-r2 `APPROVE`, plan-r1 `CHANGES_REQUESTED`).
- Inspected the revision diff `e81e2a5..fd9eff5` and verified the code sites cited by the findings: `backend/core/state_store.py#L348-L372`, `#L760-L935`; `backend/core/hierarchy.py#L1400-L1600`, `#L1800-L1935`; `backend/agents/orchestrator.py#L479`, `#L501`, `#L576-L597`, `#L743`, `#L910`; `backend/core/memory_palace.py`; `backend/server.py#L100-L240`; `backend/agents/analysis.py#L53-L71`; `frontend/src/components/{MasterOverview,LeafAgentView,Dashboard}.jsx`; `backend/tests/test_metrics_populations.py`.
- Confirmed `proposal.md` and `specs/**` unchanged since the approved spec SHA `a17d3a2`.
- No plan artifact was edited.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-fabricated-metrics",
  "stage": "plan",
  "round": 2,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "fd9eff5609b76affbb4053c7d919500575a92d84",
  "verdict": "APPROVE",
  "summary": "All 17 R1 findings are closed at fd9eff5. The revision removes the mixed testnet_telemetry fields, adds contract_version 2 and its communication, labels all four drawer sites, scopes the rust_leaf_backtest gate, discloses and tests the 200-row basis, completes the Redis payload, labels both backtest branches, splits performance from operational rendering with an executable static check, derives performance on every leaf-detail path, and splits the test tasks. Zero open blocker/major. One new minor regression: the solana_onchain_pnl_sol grep spans backend/tests while the design promises an absence test that would contain the token.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L13, tasks.md#L104, tasks.md#L124; design.md#L87, design.md#L177",
      "evidence": "Task 1.7 removes simulated_model_pnl_usd and solana_onchain_pnl_sol and keeps one MEASURED source/detail; the curl asserts both keys absent; the grep gates cover both names.",
      "required_fix": "Closed at fd9eff5: the mixed fields are removed and the remaining block declares one MEASURED population."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L23, tasks.md#L82; design.md#L244",
      "evidence": "Task 2.4 emits contract_version: 2 in get_system_status; task 8.7 records the BREAKING CHANGE footer and issue note; the traceability row maps D14 to 2.4/8.7.",
      "required_fix": "Closed at fd9eff5: the field, its communication, and the traceability row exist."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L191; tasks.md#L44, tasks.md#L47",
      "evidence": "All four real-call sites (strategy_ledger ~L479, leaf_solana mirror ~L501, master_orchestrator ~L743, per-leaf ~L910) are enumerated with source selection; task 4.8 tests a strategy_ledger LLM write.",
      "required_fix": "Closed at fd9eff5: all four sites and the strategy_ledger test are specified."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L101, tasks.md#L8; design.md#L139",
      "evidence": "The gate is scoped to backend/core, backend/agents, backend/server.py; the text excludes backend/tests where the rejection test contains the token.",
      "required_fix": "Closed at fd9eff5: the production-only scope and the exclusion rationale are recorded."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L127, design.md#L254; tasks.md#L21, tasks.md#L30, tasks.md#L71",
      "evidence": "D2 discloses the recent 200-row basis and the divergence from cumulative_cex_pnl_usd; source_detail, the audit legend, the Risks list, and the task 2.11 eviction test record it.",
      "required_fix": "Closed at fd9eff5: option (a) is implemented and tested."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L143-L155; tasks.md#L35-L36",
      "evidence": "_persisted_payload() is the complete payload (capital, thesis, five-key leaves, deposit/checkout histories); task 3.3 asserts all four top-level fields survive compaction.",
      "required_fix": "Closed at fd9eff5: the payload is complete and the preservation test is assigned."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L11, tasks.md#L16; design.md#L139",
      "evidence": "Task 1.5 labels run_rust_backtest with source=FIXTURE, covering the leaf-solana early return; task 1.10 tests run_rust_backtest_for_leaf('leaf-solana') and the POST summary.",
      "required_fix": "Closed at fd9eff5: both branches are labelled and tested."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L82, design.md#L202-L213; tasks.md#L58, tasks.md#L61, tasks.md#L65",
      "evidence": "D12 defines formatMetric (source gate) and formatOperational (null-aware, badge-free); tasks 6.1/6.4 use both and 6.8 asserts 0.0 -> $0.00 and null -> em dash.",
      "required_fix": "Closed at fd9eff5: performance and operational rendering are split and asserted."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L61-L66; design.md#L215",
      "evidence": "Tasks 6.4-6.6 enumerate the spec surfaces and coercion removal; task 6.7 creates check-provenance.mjs; task 6.9 enumerates the null-state screenshots.",
      "required_fix": "Closed at fd9eff5: every surface, the static wiring check, and the evidence are specified."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L22, tasks.md#L29; design.md#L129",
      "evidence": "Task 2.3 requires the snapshot, direct endpoint, and mandate response to pass get_population_metrics(); task 2.10 tests the direct endpoint and mandate response.",
      "required_fix": "Closed at fd9eff5: every get_leaf_detail path is covered and tested."
    },
    {
      "id": "PLAN-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L15, tasks.md#L76, tasks.md#L89",
      "evidence": "Task 1.9 creates the named test file with an auditor-source test; task 8.1 names the same file; the Verification requires a non-zero test count and OK.",
      "required_fix": "Closed at fd9eff5: the file, auditor assertion, and non-zero-count check exist."
    },
    {
      "id": "PLAN-R1-F12",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L79, design.md#L189; tasks.md#L42, tasks.md#L46",
      "evidence": "D9 and task 4.3 scan the full drawer list by wing/source before the limit; task 4.7 tests an eligible LLM drawer behind newer BOOTSTRAP drawers.",
      "required_fix": "Closed at fd9eff5: filter-before-limit and its regression test are specified."
    },
    {
      "id": "PLAN-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L25, tasks.md#L27",
      "evidence": "Task 2.6 removes the liquidation assignment; task 2.8 tests the post-liquidation leaf is null.",
      "required_fix": "Closed at fd9eff5: the internal zero is removed and tested."
    },
    {
      "id": "PLAN-R1-F14",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L63, tasks.md#L64",
      "evidence": "Task 6.6 treats a missing executions_source as UNATTRIBUTED; task 6.7's static script rejects the || 'backtest_fixture' default.",
      "required_fix": "Closed at fd9eff5: the invented default is removed and statically rejected."
    },
    {
      "id": "PLAN-R1-F15",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L86; tasks.md#L70-L71",
      "evidence": "D16 scopes figure blocks to trading-performance figures, labels the inference-cost tables as operational, and records the English/legacy-French rule; tasks 7.1-7.2 implement it.",
      "required_fix": "Closed at fd9eff5: scope and language are defined."
    },
    {
      "id": "PLAN-R1-F16",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L9, tasks.md#L11-L14, tasks.md#L40; design.md#L244-L245",
      "evidence": "Tasks 1.3, 1.5-1.8, and 4.1 reference provenance constants; the traceability table adds D14 and D15 rows.",
      "required_fix": "Closed at fd9eff5: the vocabulary is referenced and the missing rows are added."
    },
    {
      "id": "PLAN-R1-F17",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L26-L30, tasks.md#L45-L47, tasks.md#L76",
      "evidence": "Old 2.6 is split into 2.7-2.11; 4.6 into 4.6-4.8; 8.1 is a single recursive payload test with evidence/rollout in 8.2-8.8.",
      "required_fix": "Closed at fd9eff5: the oversized tasks are split."
    },
    {
      "id": "PLAN-R2-F01",
      "severity": "minor",
      "origin": "regression",
      "status": "open",
      "location": "tasks.md#L104, tasks.md#L15; design.md#L253",
      "evidence": "The D17 gate git grep -n 'solana_onchain_pnl_sol' -- backend includes backend/tests/, while the design says a test asserts the field is absent; any such test in backend/tests contains the literal and fails the gate. The sibling simulated_model_pnl_usd gate is scoped to backend/core/state_store.py, and F04 fixed the same class for rust_leaf_backtest.",
      "required_fix": "Scope the solana_onchain_pnl_sol grep to backend/core/state_store.py or exclude backend/tests, and either assign the absence assertion to task 1.9/8.1 or drop the 'a test asserts' sentence."
    }
  ],
  "closed": [
    "PLAN-R1-F01",
    "PLAN-R1-F02",
    "PLAN-R1-F03",
    "PLAN-R1-F04",
    "PLAN-R1-F05",
    "PLAN-R1-F06",
    "PLAN-R1-F07",
    "PLAN-R1-F08",
    "PLAN-R1-F09",
    "PLAN-R1-F10",
    "PLAN-R1-F11",
    "PLAN-R1-F12",
    "PLAN-R1-F13",
    "PLAN-R1-F14",
    "PLAN-R1-F15",
    "PLAN-R1-F16",
    "PLAN-R1-F17"
  ]
}
```

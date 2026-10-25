# PLAN Review — Round 1

## Summary

Verdict: **CHANGES_REQUESTED**. The plan is well-shaped and traces most requirements,
but one blocker and nine majors remain. `testnet_telemetry` would still label a
hardcoded `solana_onchain_pnl_sol = 0.0` and the simulated `simulated_model_pnl_usd`
as `MEASURED`. The breaking `contract_version: 2` decision has no task though the
verification asserts it. Task 4.5 names three real-call drawer sites; the code has
four, leaving the `strategy_ledger` thesis fail-closed `BOOTSTRAP`. The
`rust_leaf_backtest` grep gate cannot pass while the required rejection test contains
the token. The 200-row window vs lifetime PnL divergence is undisclosed and untested.
The Redis compaction payload is ambiguous and may drop capital/history. The leaf-solana
backtest summary and the direct leaf-detail endpoint are not labelled/derived. The UI
task conflates provenance with operational values and leaves several `|| 0` coercions
and surfaces uncovered. Minors/nits cover the verification file, filter order,
liquidation zero, Dashboard source default, audit figure scope, and task granularity.

## Findings

### PLAN-R1-F01 — [blocker] `testnet_telemetry` would be labelled `MEASURED` while carrying invented/simulated values
- Location: `openspec/changes/fix-fabricated-metrics/tasks.md#L13`; `backend/core/state_store.py#L348-L372` (L362 `solana_onchain_pnl_sol: 0.0`, L371 `simulated_model_pnl_usd`); `openspec/changes/fix-fabricated-metrics/specs/integrity/spec.md#L98-L101`.
- Evidence: The spec table requires `testnet_telemetry` source `MEASURED` and says every performance number must declare a source or be null. `get_testnet_telemetry` returns `solana_onchain_pnl_sol: 0.0` (a hardcoded value, never measured) and `simulated_model_pnl_usd` (the paper-model accumulator) inside the same block. Task 1.7 only adds a block-level `source = "MEASURED"` and `source_detail`; it neither removes nor re-provenances those fields. The design's D3 ("Mixed populations are never described by a block-level source") is therefore violated for this payload, and the change would ship a simulated/hardcoded number labelled measured — the exact defect class targeted.
- Required fix: In task 1.7, remove `solana_onchain_pnl_sol` and `simulated_model_pnl_usd` from `testnet_telemetry` (the paper value is already at `engine_metrics.paper_model`), or split them into a `SIMULATED` sub-block and an unattributed/absent field. Add an assertion that every numeric performance field in the payload is genuinely measured; if the table's `MEASURED` label is intended only for the CEX fields, state that explicitly.
- Status: open
- Origin: initial

### PLAN-R1-F02 — [major] The breaking `contract_version: 2` decision has no implementing task
- Location: `design.md#L84` (D14), `design.md#L169-L171`; `tasks.md#L18-L23` (group 2), `tasks.md#L93-L96` (Verification), `tasks.md#L65` (task 8.1).
- Evidence: D14 decides an additive `contract_version: 2` marker on `/api/v1/status`; the Verification asserts `d["contract_version"] == 2`. No task creates the field: tasks 2.1–2.6 never mention it, and task 8.1 cites D14 only for a recursive payload test. Following `tasks.md` literally leaves the Verification `curl` failing, and the traceability table has no D14 row.
- Required fix: Add a task (group 2) to emit `contract_version: 2` in `get_system_status`, and a task to record the `BREAKING CHANGE:` PR footer and issue-logbook note required by D14. Add the D14 row to the traceability table.
- Status: open
- Origin: initial

### PLAN-R1-F03 — [major] Four real-call `PalaceDrawer` sites exist; task 4.5 labels only three
- Location: `tasks.md#L37` (task 4.5); `backend/agents/orchestrator.py#L479` (`wing=strategy_ledger`), `#L501` (`leaf_solana` mirror), `#L743` (`master_orchestrator`), `#L910` (per-leaf); `design.md#L141` (D8).
- Evidence: Task 4.5 says "Set `source=\"LLM\"` on the three real-call construction sites (Master drawer, leaf drawer, leaf_solana mirror)". The code has four sites; the `strategy_ledger` drawer at L479 is not named. With D8's fail-closed default it becomes `BOOTSTRAP` even after a successful LLM call, so `format_continuity_prompt` excludes the primary strategy thesis and `fallback_continuity` cannot see an `LLM` drawer in that wing, breaking the spec scenario "Fallback with a prior LLM drawer carries its continuity".
- Required fix: Enumerate all four construction sites by function/line and specify the source for each (`LLM` when a parsed model response was billed, `DETERMINISTIC_FALLBACK` otherwise), including the `strategy_ledger` site explicitly. Add a test that a successful strategic reflection writes an `LLM` drawer in `strategy_ledger`.
- Status: open
- Origin: initial

### PLAN-R1-F04 — [major] The `rust_leaf_backtest` grep gate contradicts the required rejection test
- Location: `tasks.md#L87` (Verification: `git grep -n 'rust_leaf_backtest' -- backend`), `tasks.md#L8` (task 1.2), `design.md#L134`.
- Evidence: Task 1.2 requires a unit test of the `rust_leaf_backtest` rejection; that test will live under `backend/tests/` and must contain the literal token. The Verification greps the whole `backend` tree and expects no output. The gate therefore cannot pass while the required test exists, unless the test deliberately obfuscates the token.
- Required fix: Scope the gate to production source (`git grep -n 'rust_leaf_backtest' -- backend/core backend/agents backend/server.py`) or exclude tests (`-- backend ':!backend/tests'`), and state the exclusion in the Verification.
- Status: open
- Origin: initial

### PLAN-R1-F05 — [major] Leaf/treasury live PnL silently switches from lifetime to the 200-row window
- Location: `design.md#L112-L124` (D2 derivation), `tasks.md#L19` (task 2.2); `backend/core/state_store.py#L715-L718` (200-row cap), `#L922-L926` (`cumulative_cex_pnl_usd` and `recent`); `backend/core/hierarchy.py#L1874-L1880` (today uses lifetime `cumulative_cex_pnl_usd`); `docs/PERFORMANCE_AND_COST_AUDIT.md#L95-L99` (reports both).
- Evidence: D2 derives leaf `live_testnet.realized_pnl_usd` from `live_testnet.recent.pnl_usd`, the newest 200 rows. The audit's measured §3.3 reports lifetime `-$4.6036` and recent `-$0.1539` separately, and today's leaf detail uses the lifetime accumulator. The treasury field is named `total_realized_pnl_usd`. After 200 rows the leaf/treasury value diverges from the audit's lifetime figure; the plan does not label the basis in `source_detail`, does not state the trade-off in Risks, and has no eviction test. The spec scenario ("equals the sum of those rows") supports the window reading, so this is defensible, not a blocker — but the semantic change is undisclosed.
- Required fix: Decide and document the basis. Either (a) keep the 200-row window, state "recent 200-row window" in the live `source_detail` and the audit legend, add a >200-row eviction test, and avoid presenting the treasury value as a lifetime total; or (b) use `cumulative_cex_pnl_usd` for the lifetime value and escalate the spec scenario as a `spec-gap`. Record the choice in Risks/Trade-offs.
- Status: open
- Origin: initial

### PLAN-R1-F06 — [major] The Redis compaction payload is ambiguous and can drop top-level state
- Location: `tasks.md#L27-L29` (tasks 3.1–3.3); `backend/core/hierarchy.py#L1528-L1594`; `specs/integrity/spec.md#L169-L184`.
- Evidence: Task 3.2 says "Factor the persisted leaf object into one `_persisted_payload()` ... rewrite the `robotrader:v3:hierarchy` value once with that payload." The current `persist()` payload also carries `total_capital_usd`, `long_term_strategy_thesis`, `deposit_history`, and `checkout_history`. If `_persisted_payload()` is only the leaves object (as "persisted leaf object" reads), the one-time compaction drops those top-level fields on upgraded installs. Task 3.3 only checks leaf keys and "allowed keys".
- Required fix: Define `_persisted_payload()` as the complete hierarchy payload (top-level fields + leaves with only allowed keys + histories), and add a test asserting `total_capital_usd`, `long_term_strategy_thesis`, `deposit_history`, and `checkout_history` survive the compaction.
- Status: open
- Origin: initial

### PLAN-R1-F07 — [major] `POST /api/v1/leaf/leaf-solana/backtest` summary would carry no `source`
- Location: `tasks.md#L11` (task 1.5); `backend/core/state_store.py#L781-L830` (early return at L786-L787); `backend/server.py#L229-L240`; `specs/integrity/spec.md#L96` and `#L116-L120`.
- Evidence: `run_rust_backtest_for_leaf("leaf-solana")` returns `self.run_rust_backtest()` before the code task 1.5 modifies; `run_rust_backtest` sets `executions_source` but no `source`/`source_detail`. The POST endpoint returns `{"summary": bt}`. The spec table requires the POST summary to carry `source = FIXTURE`, so the leaf-solana path is uncovered.
- Required fix: Label both branches — set `source="FIXTURE"` and the leaf-replay `source_detail` in `run_rust_backtest` (or before the early return) — and add a test for `POST /api/v1/leaf/leaf-solana/backtest`.
- Status: open
- Origin: initial

### PLAN-R1-F08 — [major] `formatMetric`'s source gate contradicts the operational-value tiles
- Location: `design.md#L76` (D6), `design.md#L150-L162` (D12); `tasks.md#L52` (task 6.4); `frontend/src/components/MasterOverview.jsx#L333-L388`; `specs/integrity/spec.md#L384-L388`.
- Evidence: D12's `formatMetric(value, source, kind)` renders `—` whenever `source` is null/undefined, before formatting the value. D6 says capital, deployed, and dry-powder stay numeric and unbadged, and the OpenRouter balance has no `source` field. Task 6.4 says "render each governed value through `formatMetric` with its `SourceBadge`", which would pass no source for those operational tiles and blank real capital/credit values; if they bypass `formatMetric`, the task's "each governed value" is not met and the spec's MasterOverview bullet ("Every rendered metric block MUST display its source label") is unmet. The existing `|| 0` / `|| 0.23` coercions also render plausible defaults offline.
- Required fix: Split the rule in task 6.4: performance values use `formatMetric` + `SourceBadge`; operational values (capital, deployed, dry-powder, active-leaf count, OpenRouter balance) use a null-aware formatter that renders `—` for null/undefined and the value (including `0.00`) otherwise, with no badge, as a recorded interpretation of D6. Remove the `|| 0` / `|| 0.23` coercions; add tests for measured `0.0` → `$0.00` and null → `—`.
- Status: open
- Origin: initial

### PLAN-R1-F09 — [major] Several spec-listed UI surfaces and verification states are not explicitly covered
- Location: `tasks.md#L52-L55` (tasks 6.4–6.6), `tasks.md#L113` (evidence); `frontend/src/components/LeafAgentView.jsx#L280-L288`, `#L391`, `#L411-L412`; `frontend/src/components/MasterOverview.jsx#L699-L705`; `frontend/src/components/Dashboard.jsx#L141-L160`, `#L148`, `#L230-L236`, `#L380-L381`; `specs/integrity/spec.md#L288-L337`.
- Evidence: The spec enumerates the leaf PnL/Sharpe/win-rate tile, the Rust backtest panel, and the execution rows; the Master leaf-table PnL/Sharpe column; and the Dashboard fixture/HardRiskGate/testnet tiles and execution PnL columns. Tasks 6.4/6.5 say "badge" the Rust panel/rows and "render each governed value", but do not explicitly remove the `|| 0` coercions in `rustBacktestResult.sharpe_ratio` (L391), `ex.realized_pnl_usd` (L411-L412), `lf.realized_pnl_usd` / `lf.sharpe_ratio` (L699-L705), the Dashboard `?? 0` counts (L141-L160), or the Dashboard HardRiskGate fixture tile (L148). A null therefore still renders `0.00`/`0` on those surfaces. The evidence step attaches only `offline.png` and `bootstrap-drawer.png`; no evidence covers the leaf-view nulls, Master table null rows, or Dashboard population tiles.
- Required fix: Enumerate every spec-listed surface in tasks 6.4–6.6 and require `formatMetric`/`SourceBadge` (or the operational formatter per F08) plus removal of every `|| 0` / `?? 0` on those performance values. Add evidence steps/screenshots for the leaf view (null live+paper), Master table (non-solana null rows), and Dashboard population/testnet tiles; add a static assertion that each component imports and calls `provenance.js`.
- Status: open
- Origin: initial

### PLAN-R1-F10 — [major] The direct leaf-detail endpoint cannot derive `performance` after the flat keys are removed
- Location: `tasks.md#L20` (task 2.3); `backend/core/hierarchy.py#L1867-L1885`; `backend/server.py#L201-L203`; `frontend/src/components/LeafAgentView.jsx#L24-L32`.
- Evidence: `get_leaf_detail(leaf_id)` is called by `GET /api/v1/leaf/{leaf_id}` and by `update_leaf_mandate` without `solana_live_metrics`. The design's `leaf_performance(leaf_id, populations)` requires the populations; task 2.3 says "populate `leaf[\"performance\"]`" but does not pass or obtain them on these paths. After the flat keys are removed, the direct leaf endpoint (the primary `LeafAgentView` data source) would return null live/paper performance for `leaf-solana` even when the snapshot has measured values, and `POST /mandate` would return an inconsistent leaf.
- Required fix: Make the populations available on every `get_leaf_detail` call (accept a required populations argument, or have the endpoint and `update_leaf_mandate` pass `state_store.get_population_metrics()`); add tests for `GET /api/v1/leaf/leaf-solana` and the mandate response.
- Status: open
- Origin: initial

### PLAN-R1-F11 — [minor] The primary test command can pass with zero tests, and the auditor `source` has no verification
- Location: `tasks.md#L76` (Verification), `tasks.md#L23`, `#L29`, `#L38`, `#L45`, `#L65`; `backend/agents/analysis.py#L53-L71`.
- Evidence: The Verification runs `unittest discover -p 'test_integrity_provenance.py'`, but no task names that file. If the dev adds the tests to `test_metrics_populations.py` or `test_architecture.py`, the command discovers 0 tests and exits 0. The expected evidence text is human-readable but the command is not self-checking. Separately, no command exercises `QuantAuditorAgent.audit_latest_backtest`'s `source = FIXTURE`; task 8.1 covers only the `/status` payload.
- Required fix: Name `backend/tests/test_integrity_provenance.py` in task 8.1 (or add a task to create it), make the Verification assert a non-zero test count, and add an auditor-source assertion.
- Status: open
- Origin: initial

### PLAN-R1-F12 — [minor] Prompt builders must filter before applying `limit`
- Location: `tasks.md#L35` (task 4.3), `design.md#L79` (D9); `backend/core/memory_palace.py#L129-L178`; `backend/agents/orchestrator.py#L1089`.
- Evidence: Task 4.3 says add an eligibility filter to the prompt builders but does not specify filtering before the `recall_recent(limit=...)` slice. If implemented as `recall_recent(limit=N)` then filter, a top-N set consisting of `BOOTSTRAP` drawers hides an older `LLM` drawer, and the ADR depth-profile maxima are not "filled only by eligible drawers". The no-wing call at `orchestrator.py#L1089` is especially exposed.
- Required fix: State that the builders select eligible drawers before applying the limit (or fetch all and slice after filtering), and add a test with an eligible drawer behind bootstrap drawers.
- Status: open
- Origin: initial

### PLAN-R1-F13 — [minor] `emergency_liquidate_leaf` still writes `active_positions_count = 0`
- Location: `backend/core/hierarchy.py#L1818`; `tasks.md#L18` (task 2.1), `#L20` (task 2.3).
- Evidence: `emergency_liquidate_leaf` sets `leaf["active_positions_count"] = 0` internally; task 2.1 removes the field from `_init_leaves` but does not remove this assignment. The API masks it with `None` in `get_leaf_detail`, but any internal consumer reading the leaf dict sees `0`, contradicting the spec's "never 2, 1, or 0".
- Required fix: Remove the liquidation assignment (or set it to `None`) and add a test on the post-liquidation internal leaf.
- Status: open
- Origin: initial

### PLAN-R1-F14 — [minor] `Dashboard` invents a `backtest_fixture` attribution when `executions_source` is null
- Location: `frontend/src/components/Dashboard.jsx#L65`, `#L319-L326`; `tasks.md#L54` (task 6.6).
- Evidence: `const executionsSource = metrics.executions_source || 'backtest_fixture'` invents a FIXTURE attribution when the offline skeleton carries `executions_source: null`; the header then reads "Replay Déterministe (`engine-rs`)". Task 6.6 only removes `|| 0` coercions and does not remove this default.
- Required fix: Treat a missing `executions_source` as unattributed (`—`/`UNATTRIBUTED`), not fixture; update task 6.6 and add an offline assertion.
- Status: open
- Origin: initial

### PLAN-R1-F15 — [minor] Audit figure-block scope and language are undefined
- Location: `tasks.md#L59-L61` (tasks 7.1–7.2); `docs/PERFORMANCE_AND_COST_AUDIT.md#L20-L40` (§2.1 cost table), `#L112-L120` (§4 adjustments table); `openspec/config.yaml#L29-L33` (English-only).
- Evidence: Task 7.2 says "Label every figure block in the document" and D16 says "a Source column on numeric tables." The document has non-trading numeric tables (§2.1 token/cost by model, §4 token/cost adjustments) that are not `FIXTURE`/`SIMULATED`/`MEASURED` trading populations; applying those labels would misattribute inference cost. The document is French while `openspec/config.yaml` says repository content is English-only; the plan does not state the language of the new legend/labels.
- Required fix: Define that figure blocks are trading-performance figures per the spec definition, and state how §2/§4 cost tables are labelled (or excluded) from the three trading sources. State that new text follows the English-only convention (or record a deliberate exception for this legacy document).
- Status: open
- Origin: initial

### PLAN-R1-F16 — [nit] Provenance constants are not referenced by the tasks; D14/D15 are missing from traceability
- Location: `design.md#L71` (D1), `design.md#L173-L190` (traceability); `tasks.md#L7-L14`.
- Evidence: D1 creates `backend/core/provenance.py` as the single vocabulary, but tasks 1.3–1.8, 2.4, and group 4 specify string literals (`"MEASURED"`, `"FIXTURE"`, etc.) rather than the module constants. The traceability table has no row for D14 or D15.
- Required fix: Reference the `provenance` constants in the tasks and add D14/D15 rows to the traceability table.
- Status: open
- Origin: initial

### PLAN-R1-F17 — [nit] Oversized test tasks
- Location: `tasks.md#L23` (2.6), `#L38` (4.6), `#L65` (8.1).
- Evidence: Task 2.6 bundles 11 test areas, task 4.6 six areas, and task 8.1 a full recursive payload test; the checklist requires each task to fit one session.
- Required fix: Split the large test tasks into per-group tasks.
- Status: open
- Origin: initial

## Checks run

- `git rev-parse HEAD` → `e81e2a5efb7800ff641058cc8756ae3336f4a933`.
- `openspec validate fix-fabricated-metrics --strict` → PASS: `Change 'fix-fabricated-metrics' is valid`.
- `scripts/sdlc/sdlc.sh check fix-fabricated-metrics` → PASS: `spec-lint` PASS (Review Card 183 words, 1 diagram, ~1.4 min), `verdict-lint` PASS (spec-r1 `CHANGES_REQUESTED`, spec-r2 `APPROVE`).
- Reviewed `design.md` and `tasks.md` at the SHA above; verified the code references cited in the findings (`state_store.py`, `hierarchy.py`, `memory_palace.py`, `orchestrator.py`, `server.py`, `analysis.py`, `frontend/src`).
- No plan artifact was edited.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-fabricated-metrics",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "e81e2a5efb7800ff641058cc8756ae3336f4a933",
  "verdict": "CHANGES_REQUESTED",
  "summary": "One blocker and nine majors remain: testnet_telemetry would label a hardcoded zero and a simulated paper value as MEASURED; contract_version 2 has no task; four real-call drawer sites exist but task 4.5 names three; the rust_leaf_backtest grep gate contradicts the required test; the window-vs-lifetime PnL basis is undisclosed and untested; the Redis compaction may drop top-level state; the leaf-solana backtest summary and direct leaf-detail endpoint are uncovered; the UI task conflates provenance and operational values and leaves several surfaces and coercions unaddressed.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L13; backend/core/state_store.py#L348-L372; specs/integrity/spec.md#L98-L101",
      "evidence": "get_testnet_telemetry returns hardcoded solana_onchain_pnl_sol=0.0 and simulated_model_pnl_usd, but task 1.7 only adds a block-level source=MEASURED, so a simulated/hardcoded value would be served as measured.",
      "required_fix": "Remove solana_onchain_pnl_sol and simulated_model_pnl_usd from testnet_telemetry or split them into a SIMULATED sub-block/unattributed field; assert every numeric performance field is genuinely measured."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L84, design.md#L169-L171; tasks.md#L18-L23, tasks.md#L93-L96",
      "evidence": "D14 requires contract_version=2 and the Verification asserts it, but no task creates the field; the traceability table has no D14 row.",
      "required_fix": "Add a task to emit contract_version=2 in get_system_status, a task for the BREAKING CHANGE footer/issue note, and the D14 traceability row."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L37; backend/agents/orchestrator.py#L479, #L501, #L743, #L910; design.md#L141",
      "evidence": "Four PalaceDrawer construction sites exist; task 4.5 names three and leaves the strategy_ledger site (L479) to default BOOTSTRAP, excluding the primary thesis from continuity and fallback.",
      "required_fix": "Enumerate all four sites with their sources (LLM vs DETERMINISTIC_FALLBACK) including strategy_ledger, and test a successful reflection writes source=LLM there."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L8, tasks.md#L87; design.md#L134",
      "evidence": "Task 1.2 requires a test containing the literal rust_leaf_backtest; the Verification greps all of backend for that token and expects no output, so the gate cannot pass while the test exists.",
      "required_fix": "Scope the grep to production modules or exclude backend/tests, and state the exclusion in the Verification."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L112-L124; tasks.md#L19; backend/core/state_store.py#L715-L718, #L922-L926; backend/core/hierarchy.py#L1874-L1880; docs/PERFORMANCE_AND_COST_AUDIT.md#L95-L99",
      "evidence": "D2 uses live_testnet.recent.pnl_usd (200-row window) while today's leaf uses lifetime cumulative_cex_pnl_usd; the audit reports both and the treasury field is named total_realized_pnl_usd. The basis and divergence are not disclosed or tested.",
      "required_fix": "Document the 200-row basis in source_detail and the audit legend and add an eviction test, or use the lifetime cumulative and escalate the spec scenario as spec-gap; record the choice in Risks/Trade-offs."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L27-L29; backend/core/hierarchy.py#L1528-L1594",
      "evidence": "Task 3.2 says the one-time compaction writes the 'persisted leaf object'; the current persist payload also contains total_capital_usd, long_term_strategy_thesis, deposit_history, and checkout_history, which could be dropped.",
      "required_fix": "Define _persisted_payload() as the full hierarchy payload and test that top-level capital, thesis, and histories survive compaction."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L11; backend/core/state_store.py#L781-L830; backend/server.py#L229-L240; specs/integrity/spec.md#L96, #L116-L120",
      "evidence": "run_rust_backtest_for_leaf('leaf-solana') returns run_rust_backtest() before task 1.5's labelling code, and run_rust_backtest sets no source, so the POST summary for leaf-solana lacks source=FIXTURE.",
      "required_fix": "Label both branches (including run_rust_backtest or before the early return) and test POST /api/v1/leaf/leaf-solana/backtest."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L76, design.md#L150-L162; tasks.md#L52; frontend/src/components/MasterOverview.jsx#L333-L388; specs/integrity/spec.md#L384-L388",
      "evidence": "formatMetric renders an em dash for any null/undefined source before formatting, while D6 says capital/dry-powder/credit stay numeric and unbadged; task 6.4 says all governed values go through formatMetric, which would blank real values or leave the operational rule unmet. The || 0 / || 0.23 coercions also invent offline defaults.",
      "required_fix": "Split performance values (formatMetric + badge) from operational values (null-aware formatter, no badge), remove the coercions, and test measured 0.0 -> $0.00 and null -> em dash."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L52-L55, tasks.md#L113; frontend/src/components/LeafAgentView.jsx#L280-L288, #L391, #L411-L412; frontend/src/components/MasterOverview.jsx#L699-L705; frontend/src/components/Dashboard.jsx#L141-L160, #L148, #L230-L236, #L380-L381; specs/integrity/spec.md#L288-L337",
      "evidence": "The Rust backtest panel, execution rows, Master leaf-table column, Dashboard counts, and HardRiskGate tile retain || 0 / ?? 0 coercions and are not named in tasks 6.4-6.6; the only UI evidence is two screenshots.",
      "required_fix": "Enumerate every spec-listed surface, route performance values through formatMetric/SourceBadge, remove the coercions, add screenshots for leaf/Master/Dashboard null states, and assert each component calls provenance.js."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L20; backend/core/hierarchy.py#L1867-L1885; backend/server.py#L201-L203; frontend/src/components/LeafAgentView.jsx#L24-L32",
      "evidence": "get_leaf_detail is called by GET /api/v1/leaf/{leaf_id} and update_leaf_mandate without populations; leaf_performance needs populations, so the direct endpoint would serve null performance for leaf-solana after the flat keys are removed.",
      "required_fix": "Pass or obtain populations on every get_leaf_detail path and test the direct leaf endpoint and mandate response."
    },
    {
      "id": "PLAN-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L76, #L23, #L29, #L38, #L45, #L65; backend/agents/analysis.py#L53-L71",
      "evidence": "Verification discovers test_integrity_provenance.py but no task names that file, so 0 tests can pass with exit 0; no command asserts the auditor source.",
      "required_fix": "Name the test file in task 8.1, assert a non-zero test count, and add an auditor-source assertion."
    },
    {
      "id": "PLAN-R1-F12",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L35; design.md#L79; backend/core/memory_palace.py#L129-L178; backend/agents/orchestrator.py#L1089",
      "evidence": "Task 4.3 does not state whether filtering happens before the recall limit; filtering after the top-N slice can hide an eligible LLM drawer behind bootstrap drawers.",
      "required_fix": "Filter before applying the limit and add a test with an eligible drawer behind bootstrap drawers."
    },
    {
      "id": "PLAN-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/core/hierarchy.py#L1818; tasks.md#L18, #L20",
      "evidence": "emergency_liquidate_leaf writes active_positions_count=0 internally; the API masks it, but any internal consumer still sees the forbidden zero.",
      "required_fix": "Remove the liquidation assignment or set it to None, and test the post-liquidation internal leaf."
    },
    {
      "id": "PLAN-R1-F14",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "frontend/src/components/Dashboard.jsx#L65, #L319-L326; tasks.md#L54",
      "evidence": "executionsSource defaults to backtest_fixture when executions_source is null, inventing a fixture attribution in the offline skeleton.",
      "required_fix": "Treat a missing executions_source as unattributed and add an offline assertion."
    },
    {
      "id": "PLAN-R1-F15",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L59-L61; docs/PERFORMANCE_AND_COST_AUDIT.md#L20-L40, #L112-L120; openspec/config.yaml#L29-L33",
      "evidence": "Task 7.2 says label every figure block, but the document's inference-cost tables are not trading populations; the plan also does not state the English-only language convention for new text.",
      "required_fix": "Define figure blocks as trading-performance figures, state how cost tables are labelled or excluded, and state the language of new text."
    },
    {
      "id": "PLAN-R1-F16",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L71, design.md#L173-L190; tasks.md#L7-L14",
      "evidence": "D1 creates provenance.py as the single vocabulary, but tasks use string literals; the traceability table omits D14 and D15.",
      "required_fix": "Reference the provenance constants in the tasks and add D14/D15 rows."
    },
    {
      "id": "PLAN-R1-F17",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L23, #L38, #L65",
      "evidence": "Tasks 2.6, 4.6, and 8.1 bundle many test areas into single tasks, exceeding the one-session guideline.",
      "required_fix": "Split the large test tasks into per-group tasks."
    }
  ],
  "closed": []
}
```

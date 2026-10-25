# SPEC Review — Round 1

## Summary

Verdict: **CHANGES_REQUESTED**. The spec is correctly shaped for a lane-L integrity
change, and 9 requirements / 32 scenarios is proportionate rather than
over-specified. Two things block approval. First, nullable leaf PnL is not traced
to the OpenRouter refill consumers (`server.py:243-250`, `orchestrator.py:575-580`);
`float(None)` will raise on a fresh install, and the `max(125.0, pnl)` fabricated
profit floor is neither scoped in nor declared as a follow-up. Second, provenance
is under-defined: a leaf block mixes `MEASURED` live and `SIMULATED` paper values,
the per-leaf execution-row source does not exist for 25 of 26 leaves, and legacy
Redis performance fields are rehydrated unchanged. The legacy-drawer relabelling
trade-off, the `DETERMINISTIC_FALLBACK` continuity fabrication, and the ADR-0002
contradiction are also undisclosed.

## Findings

### SPEC-R1-F01 — [blocker] Nullable leaf PnL breaks the OpenRouter refill consumers
- Location: `backend/server.py#L243-L250`, `backend/agents/orchestrator.py#L575-L580`; `openspec/changes/fix-fabricated-metrics/proposal.md#L62`
- Evidence: `Requirement: Leaf performance requires execution evidence` makes `realized_pnl_usd` `null` for every leaf without live rows. Both refill call sites still execute `float(lf.get("realized_pnl_usd", 0.0))`; because the key is present with value `None`, `float(None)` raises `TypeError`. The `/api/v1/openrouter/refill` endpoint and `run_master_orchestrator_reflection` therefore fail on a fresh install. `Impact` lists `orchestrator.py` only for the "null-safe Master prompt" and does not name the refill paths.
- Required fix: Add both call sites to `Impact` and add a requirement (with a scenario) that refill gating derives from measured, null-safe values and never coerces `None` to `0.0`.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [major] The `max(125.0, pnl)` profit floor and paper-PnL mixing on the refill gate are unscoped
- Location: `backend/server.py#L250`, `backend/agents/orchestrator.py#L580`, `backend/agents/monitor.py#L358-L380`; `openspec/changes/fix-fabricated-metrics/proposal.md#L51-L58`
- Evidence: Both callers pass `realized_trading_pnl_usd=max(125.0, total_pnl)` into `trigger_openrouter_refill`, whose profit gate rejects only when the argument is `<= 0.0` and whose cap is 10% of it. With zero realized profit the gate sees `$125.00`, so a refill up to `$12.50` is permitted. `total_pnl` also adds `self.store.live_pnl_usd`, the `paper_model` (simulated) population. No `## Non-goals` entry names this fabricated value, so a reader concludes the change removes all fabricated metrics.
- Required fix: Add an explicit out-of-scope entry naming `max(125.0, …)` and the paper-PnL mixing, cite the follow-up issue (#5), and state whether removing simulated PnL from the gate is in scope; if in scope, add a scenario.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [major] The `source` field already exists as free text; the contract impact is misstated as additive
- Location: `openspec/changes/fix-fabricated-metrics/proposal.md#L64`, `specs/integrity/spec.md#L31-L33`; evidence `backend/core/state_store.py#L897`, `#L911`, `#L923`, `backend/server.py#L131`
- Evidence: `get_population_metrics` already emits `"source": "engine-rs deterministic replay (synthetic scenario)"`, `"source": "simulated_pnl_usd (L2 slippage + adverse-selection paper model)"`, and `"source": "realized_pnl_usd (testnet/devnet orders)"`. The spec redefines `source` as an enum, a type change. `server.py:131` also emits `executions_source` with a third vocabulary. The proposal claims the shape changes "additively (`source` fields)", which is false for `engine_metrics.*.source`.
- Required fix: Reclassify `engine_metrics.*.source` as a breaking type change, state whether the descriptive text moves to a `source_detail` field or is dropped, and define the relationship between `source`, `executions_source`, and the `executions` array.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [major] A single block-level `source` cannot describe a leaf block that mixes populations; assignment rules are missing
- Location: `specs/integrity/spec.md#L31-L53`, `#L3-L5`; evidence `backend/core/hierarchy.py#L1429-L1430`, `#L1874-L1880`
- Evidence: A leaf block carries both `realized_pnl_usd` (live population) and `paper_pnl_usd` (paper population). Requirement 2 mandates one block-level `source` from a set whose values denote populations. There is no rule for a leaf with zero rows, exactly one row, only paper rows, or both live and paper rows; scenario 1 asserts nulls but not `source`. `BOOTSTRAP` (all values null) and `source = null` (unattributed, all values null) are observationally identical, yet requirement 6 renders them with different badges. Requirement 3 also forces `treasury.source = MEASURED` even when `total_realized_pnl_usd` is null.
- Required fix: Define per-field provenance, or split each leaf performance block into per-population sub-blocks each carrying its own `source`; specify the exact source for each row-count/population combination; define when `BOOTSTRAP` is used versus `null`; and define `treasury.source` when the aggregate is null.
- Status: open
- Origin: initial

### SPEC-R1-F05 — [major] Per-leaf execution rows do not exist for 25 of 26 leaves; `paper_pnl_usd` and `active_positions_count` derivations are undefined
- Location: `specs/integrity/spec.md#L3-L29`; evidence `backend/core/state_store.py#L141-L144`, `#L183-L188`, `backend/core/hierarchy.py#L48` (26-entry catalog), `#L1818`
- Evidence: Requirement 1 requires values "computed from the leaf's own execution rows", but the only execution ledger is one global `live_executions` list, filtered to Solana-ecosystem symbols at load. Only `leaf-solana` is wired to it (`hierarchy.py#L1874-L1880`). The spec never defines how a row is attributed to one of the 26 leaves. Scenarios cover realized PnL, win rate, and Sharpe only; `paper_pnl_usd` and `active_positions_count` have no derivation and no scenario. `active_positions_count` is currently a seeding constant, set to `0` only on liquidation.
- Required fix: State the per-leaf data source and mapping, or state explicitly that only `leaf-solana` derives and the other 25 remain null; define `paper_pnl_usd` and `active_positions_count` computation; add a scenario for each.
- Status: open
- Origin: initial

### SPEC-R1-F06 — [major] Persisted Redis hierarchy rehydrates the fabricated leaf values
- Location: `backend/core/hierarchy.py#L1528-L1562`, `#L1566-L1584`; scenario `specs/integrity/spec.md#L7-L10`
- Evidence: `_load_persisted` copies `realized_pnl_usd`, `paper_pnl_usd`, and `active_positions_count` from Redis into each leaf, and `persist` writes them back. On an upgraded install the legacy constants reappear after restart, so the "no executions → null" scenario fails. The proposal's `Impact` mentions `hierarchy.py` but no requirement or scenario covers the persisted-state migration.
- Required fix: Add a requirement and scenario that legacy persisted performance keys are ignored or dropped at load and are no longer persisted, with the expected observable snapshot after reload.
- Status: open
- Origin: initial

### SPEC-R1-F07 — [major] `DETERMINISTIC_FALLBACK` drawers still fabricate continuity and LLM telemetry
- Location: `specs/integrity/spec.md#L98-L124`; evidence `backend/agents/orchestrator.py#L392-L395`, `#L890-L895`, `#L910-L931`, `backend/core/memory_palace.py#L48`
- Evidence: Requirement 5 constrains only `BOOTSTRAP` drawers. The deterministic fallback path sets `thesis_continuity` to `"CONFIRMED" if self.store.palace.drawers else "INITIAL"` — seeded `BOOTSTRAP` drawers make it `CONFIRMED` on a fresh install — and the leaf fallback hardcodes `"CONFIRMED"`. The resulting drawer is then created with `model_used=used_model`, `tokens_used=p_tok + c_tok`, and `cost_usd=call_cost`. A labelled `DETERMINISTIC_FALLBACK` drawer therefore still claims prior confirmation and displays model telemetry, which is the fabrication pattern the issue targets.
- Required fix: Extend requirement 5 (or add one) so `DETERMINISTIC_FALLBACK` drawers carry `INITIAL` continuity unless a real `LLM` drawer exists, and define their model/token/cost values; add a scenario.
- Status: open
- Origin: initial

### SPEC-R1-F08 — [major] Re-labelling all legacy drawers `BOOTSTRAP` is not an explicit accepted trade-off
- Location: `proposal.md#L58`, `specs/integrity/spec.md#L79-L96`, `#L100`; evidence `backend/core/memory_palace.py#L40-L60`
- Evidence: Every pre-change drawer lacks `source`, so requirement 4 serves it as `BOOTSTRAP` with empty `model_used` and zero telemetry, and requirement 5 excludes it from the continuity prompt and cross-wing digest. Genuine LLM theses written before the change therefore disappear from the Master prompt and lose their real telemetry, with no way to distinguish them from seeds. The proposal's `Non-goals` says only "conservatively re-labelled … and not reconstructed"; the Review Card `Risk` does not mention the loss of genuine continuity, and no scenario asserts the post-upgrade observable behaviour.
- Required fix: State the accepted trade-off explicitly in the Review Card `Risk` and `Non-goals` (existing genuine LLM theses become invisible to the Master prompt), and add a scenario covering the post-upgrade read of a genuine pre-change drawer.
- Status: open
- Origin: initial

### SPEC-R1-F09 — [major] Contradiction with ADR-0002's continuity guarantee
- Location: `specs/integrity/spec.md#L98-L124`; evidence `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md#L37`, `#L61-L62`
- Evidence: ADR-0002 states "Every LLM prompt injects the latest drawers from `strategy_ledger` so the strategist must explicitly CONFIRM, REFINE, or INVALIDATE its prior thesis". Requirement 5 excludes `BOOTSTRAP` drawers from the continuity prompt and digest, and the ADR's depth profiles ("5 memory drawers", "2 memory drawers") assume drawer content exists. The spec neither cites nor amends the ADR.
- Required fix: Reconcile the two — either amend ADR-0002 in this change or state that only non-`BOOTSTRAP` drawers are injected and record the ADR impact in `Impact` and the plan.
- Status: open
- Origin: initial

### SPEC-R1-F10 — [major] Several backend performance payloads are unenumerated and would be nulled by the unattributed rule
- Location: `specs/integrity/spec.md#L31-L53`; evidence `backend/core/state_store.py#L823`, `backend/server.py#L109`, `#L131`, `#L233-L237`, `frontend/src/components/LeafAgentView.jsx#L335`, `#L391`
- Evidence: Requirement 2 enumerates only the three `engine_metrics` populations, leaf blocks, and the treasury block. `leaf.last_rust_backtest` carries `sharpe_ratio`, `win_rate_pct`, and `net_profit_usd` with no `source`; `POST /api/v1/leaf/{leaf_id}/backtest` returns that raw fixture summary; and `engine_metrics.executions` falls back to fixture rows when no live rows exist (`executions = live_window if live_window else list(bt.get("executions", []))`). Under requirement 2's unattributed rule these become null, blanking the leaf backtest and pod-attribution views, or they remain unlabelled fixture numbers.
- Required fix: Enumerate these payloads with their source (`FIXTURE`/`SIMULATED`/`MEASURED`) or explicitly exclude them with a reason; add a scenario for the execution table and leaf backtest provenance.
- Status: open
- Origin: initial

### SPEC-R1-F11 — [major] UI scope is unbounded and `Impact` omits `Dashboard.jsx`
- Location: `specs/integrity/spec.md#L128`, `proposal.md#L62-L63`; evidence `frontend/src/components/Dashboard.jsx#L148`, `#L230-L236`, `#L380-L381`, `backend/agents/analysis.py#L66-L70`
- Evidence: Requirement 6 says "every other metric tile", with no definition or list. `Impact` names only `App.jsx`, `LeafAgentView.jsx`, and `MasterOverview.jsx`. `Dashboard.jsx` coerces `bt.sharpe_ratio || 0` and `binance_realized_pnl_usd || 0` to numeric zero. `QuantAuditorAgent.audit_latest_backtest` converts a fixture Sharpe into a `HEALTHY_EDGE` verdict with `float(bt.get("sharpe_ratio", 0.0))`.
- Required fix: Replace "every other metric tile" with an enumerated list of components/tiles and add them to `Impact`; state whether the QuantAuditor verdict is in scope or explicitly excluded.
- Status: open
- Origin: initial

### SPEC-R1-F12 — [major] "Retained prior values MUST NOT be presented as current measurements" is unverifiable
- Location: `specs/integrity/spec.md#L157`, `#L177-L181`; evidence `frontend/src/App.jsx#L32`, `#L68`, `#L84-L86`
- Evidence: The app keeps `statusData` after a failed poll and only flips `backendConnected`; the spec does not define what observable makes a retained value "marked as not current". The scenario's THEN ("is marked as not current and is not presented as a measurement") cannot be asserted by a dev reviewer.
- Required fix: Define an observable treatment (for example values replaced with `—`, or a persistent `OFFLINE — stale since <timestamp>` badge per tile) and assert it in the scenario.
- Status: open
- Origin: initial

### SPEC-R1-F13 — [minor] The provenance-badge scenario bundles two behaviours
- Location: `specs/integrity/spec.md#L148-L153`
- Evidence: The scenario contains two `WHEN`/`THEN` pairs: one for an attributed block, one for `source = null` rendering `—` with `UNATTRIBUTED`. The checklist requires one behaviour per scenario.
- Required fix: Split into two scenarios.
- Status: open
- Origin: initial

### SPEC-R1-F14 — [minor] Audit-document scenarios depend on hard-coded figures and an undefined "figure block"
- Location: `specs/integrity/spec.md#L209-L225`
- Evidence: The scenarios assert `28.22`, `+$22.78`, `+$1,155.52`, and `-$4.6036`, and require "every figure block" to be labelled without defining a figure block. The figures are tied to the current document revision and will drift.
- Required fix: Define "figure block" (for example a table row, bullet, or section) and either reference the population label generically or state that the named figures are those present at the reviewed SHA.
- Status: open
- Origin: initial

### SPEC-R1-F15 — [minor] Requirement 4 cites a WebSocket drawer snapshot that does not exist
- Location: `specs/integrity/spec.md#L79`; evidence `backend/server.py#L370`
- Evidence: The only WebSocket route is `/ws/chat`; drawers are served through `/api/v1/status` (`hierarchy.leaves[].palace_drawers`, `master_orchestrator.palace_drawers`) and `cognitive_engine.palace_drawers`.
- Required fix: Name the actual REST surfaces and drop the WebSocket reference, or add the WebSocket surface to the change.
- Status: open
- Origin: initial

### SPEC-R1-F16 — [nit] Review Card `## Why` paragraph exceeds two sentences
- Location: `proposal.md#L27`
- Evidence: The first `## Why` paragraph has three sentences; the artifact rule caps paragraphs at two sentences.
- Required fix: Split it into two paragraphs.
- Status: open
- Origin: initial

## Checklist walk

| Section | Result | Notes |
|---|---|---|
| 1. Decision surface | PASS (one nit) | Lint: 141 words, 1 Mermaid diagram, ~1.2 min. Outcome, why, blast radius, risk, effort, decision all present. Non-goals meaningful. Paragraph-length nit: F16. |
| 2. Problem and scope | FAIL | Problem is an observed fact with code citations. Boundary omits the refill path and the `$125` floor (F01, F02). Lane L is correct: breaking, cross-stack backend/frontend/docs. |
| 3. Capabilities and deltas | PASS | One capability (`integrity`) → one delta file. Only `ADDED Requirements`; no MODIFIED/REMOVED/RENAMED. 9 requirement names and 32 scenario names are unique. |
| 4. Requirement quality | FAIL | SHALL/MUST used throughout; no TBD/TODO. Untestable or unbounded clauses: single block `source` (F04), per-leaf data source (F05), "every other metric tile" (F11), "marked as not current" (F12), "every figure block" (F14). |
| 5. Scenarios | FAIL | Every requirement has ≥1 scenario with WHEN and THEN. Missing failure paths: `paper_pnl_usd`, `active_positions_count`, persisted-state reload, post-upgrade legacy drawer, refill null-safety/profit gate. One bundled scenario: F13. 32 scenarios for 9 requirements is proportionate, not over-specified. |
| 6. Consistency and risk | FAIL | Contract impact is misstated (F03). Money-adjacent refill path is uncovered (F01, F02). Contradiction with ADR-0002 (F09). No contradiction with `openspec/specs/health`. Backtest/paper/live implications are identified; multi-chain isolation is stated as preserved; no Rust/vault/`PolicyEnvelope` creep. |
| 7. Traceability | FAIL | `Impact` omits the refill call sites (F01), persisted-state keys (F06), `last_rust_backtest`/backtest endpoint/executions (F10), and `Dashboard.jsx`/QuantAuditor (F11). `tasks.md` is N/A for the SPEC stage at lane L (PLAN artifact per PROTOCOL §3); `design.md` likewise. Artifact is self-contained. |

## Checks run

- `openspec validate fix-fabricated-metrics --strict` → PASS (`Change 'fix-fabricated-metrics' is valid`)
- `scripts/sdlc/spec-lint.py --change fix-fabricated-metrics` → PASS (141 words, 1 diagram, ~1.2 min; `design.md`/`tasks.md` absent at PLAN stage)
- `scripts/sdlc/sdlc.sh check fix-fabricated-metrics` → PASS
- Reviewed SHA: `777656de97303a6247f2cb9be7f54f6dcf0e5dc3`; artifacts at HEAD (working tree clean for `openspec/`).
- Read time: ~34 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-fabricated-metrics",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "777656de97303a6247f2cb9be7f54f6dcf0e5dc3",
  "verdict": "CHANGES_REQUESTED",
  "summary": "CHANGES_REQUESTED: the spec is proportionate, but nullable leaf PnL breaks the untraced OpenRouter refill consumers, provenance is under-defined for mixed-population leaf blocks and per-leaf data sources, and the $125 refill floor, legacy-drawer trade-off, DETERMINISTIC_FALLBACK continuity, and ADR-0002 contradiction are undisclosed.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "backend/server.py#L243-L250, backend/agents/orchestrator.py#L575-L580, proposal.md#L62",
      "evidence": "Requirement 1 makes realized_pnl_usd null; both refill call sites still run float(lf.get(\"realized_pnl_usd\", 0.0)) and raise TypeError when the key holds None. Impact does not list the refill path.",
      "required_fix": "Add both call sites to Impact and add a requirement with a scenario for null-safe, measured-only refill inputs."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/server.py#L250, backend/agents/orchestrator.py#L580, backend/agents/monitor.py#L358-L380, proposal.md#L51-L58",
      "evidence": "Callers pass max(125.0, total_pnl) into a profit gate that rejects only when <= 0.0 and caps at 10%, so zero realized profit is presented as $125; total_pnl also adds the paper_model live_pnl_usd.",
      "required_fix": "Declare the max(125.0, pnl) floor and paper-PnL mixing explicitly out of scope with the issue #5 follow-up, or bring them in scope with a scenario."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L64, specs/integrity/spec.md#L31-L33, backend/core/state_store.py#L897",
      "evidence": "engine_metrics.*.source already exists as free text at state_store.py:897, 911, 923, and server.py:131 emits executions_source; the spec redefines source as an enum while the proposal calls the change additive.",
      "required_fix": "Reclassify engine_metrics.*.source as a breaking type change, state where the descriptive text moves, and define the relationship to executions_source and the executions array."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L31-L53, backend/core/hierarchy.py#L1429-L1430",
      "evidence": "A leaf block carries both realized_pnl_usd (live) and paper_pnl_usd (paper) under one block-level source; no mapping rule exists, and BOOTSTRAP versus source=null are observationally identical; treasury.source is forced MEASURED even when the aggregate is null.",
      "required_fix": "Define per-field provenance or per-population sub-blocks, specify the source for every row-count/population combination, distinguish BOOTSTRAP from null, and define treasury.source when the aggregate is null."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L3-L29, backend/core/state_store.py#L183-L188, backend/core/hierarchy.py#L48",
      "evidence": "The only execution ledger is one global Solana-filtered live_executions list; 25 of 26 leaves have no per-leaf rows. paper_pnl_usd and active_positions_count have no derivation and no scenario.",
      "required_fix": "Define the per-leaf data source and mapping (or state only leaf-solana derives), define paper PnL and active position count, and add scenarios for both."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/core/hierarchy.py#L1528-L1562, backend/core/hierarchy.py#L1566-L1584",
      "evidence": "_load_persisted restores realized_pnl_usd, paper_pnl_usd, and active_positions_count from Redis, and persist writes them back; legacy constants reappear after restart, defeating the null guarantee.",
      "required_fix": "Add a requirement and scenario that persisted legacy performance keys are ignored or dropped at load and no longer persisted."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L98-L124, backend/agents/orchestrator.py#L392-L395, backend/agents/orchestrator.py#L890-L895",
      "evidence": "Requirement 5 constrains only BOOTSTRAP drawers. The fallback path sets CONFIRMED when any drawer exists (seeded BOOTSTRAP qualifies) or unconditionally for leaves, and the resulting DETERMINISTIC_FALLBACK drawer carries model_used, tokens_used, and cost_usd.",
      "required_fix": "Constrain DETERMINISTIC_FALLBACK continuity to INITIAL unless a real LLM drawer exists, define its telemetry, and add a scenario."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L58, specs/integrity/spec.md#L79-L96, specs/integrity/spec.md#L100",
      "evidence": "All pre-change drawers lack source, so they become BOOTSTRAP, lose model telemetry, and are excluded from the continuity prompt and digest; genuine LLM theses vanish with no way to distinguish them from seeds, and the Review Card Risk omits this.",
      "required_fix": "State the accepted trade-off in Risk and Non-goals and add a scenario for reading a genuine pre-change drawer after upgrade."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L98-L124, docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md#L37",
      "evidence": "ADR-0002 requires every LLM prompt to inject the latest strategy_ledger drawers and specifies 5/2 drawers per depth; requirement 5 excludes BOOTSTRAP drawers and the spec neither cites nor amends the ADR.",
      "required_fix": "Reconcile with ADR-0002, either by amending it in this change or by stating the injection rule and recording the ADR impact."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L31-L53, backend/core/state_store.py#L823, backend/server.py#L109, backend/server.py#L233-L237",
      "evidence": "leaf.last_rust_backtest, POST /api/v1/leaf/{leaf_id}/backtest, and the fixture fallback in engine_metrics.executions carry performance numbers without a source; requirement 2 does not enumerate them and its unattributed rule would null them.",
      "required_fix": "Enumerate these payloads with their source or explicitly exclude them, and add a scenario for the execution table and leaf backtest provenance."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L128, proposal.md#L62-L63, frontend/src/components/Dashboard.jsx#L148",
      "evidence": "Requirement 6 says \"every other metric tile\" without a definition; Impact omits Dashboard.jsx, which coerces bt.sharpe_ratio and binance_realized_pnl_usd with || 0; QuantAuditor derives HEALTHY_EDGE from fixture Sharpe.",
      "required_fix": "Enumerate the components and tiles, add them to Impact, and state whether the QuantAuditor verdict is in scope."
    },
    {
      "id": "SPEC-R1-F12",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L157, specs/integrity/spec.md#L177-L181, frontend/src/App.jsx#L68-L86",
      "evidence": "The app retains statusData after a failed poll and only flips backendConnected; the spec does not define what observable marks a retained value as not current.",
      "required_fix": "Define an observable offline/stale treatment and assert it in the scenario."
    },
    {
      "id": "SPEC-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L148-L153",
      "evidence": "The provenance-badge scenario contains two WHEN/THEN pairs covering two behaviours.",
      "required_fix": "Split it into two scenarios."
    },
    {
      "id": "SPEC-R1-F14",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L209-L225",
      "evidence": "Scenarios hard-code 28.22, +$22.78, +$1,155.52, and -$4.6036 and require every \"figure block\" to be labelled without defining a figure block.",
      "required_fix": "Define \"figure block\" and anchor the named figures to the reviewed revision or use population labels generically."
    },
    {
      "id": "SPEC-R1-F15",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/integrity/spec.md#L79, backend/server.py#L370",
      "evidence": "The only WebSocket route is /ws/chat; drawers are served through /api/v1/status and cognitive_engine, not a WebSocket snapshot.",
      "required_fix": "Name the actual REST surfaces and drop the WebSocket reference, or add that surface to the change."
    },
    {
      "id": "SPEC-R1-F16",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L27",
      "evidence": "The first ## Why paragraph has three sentences; the artifact rule caps paragraphs at two.",
      "required_fix": "Split the paragraph."
    }
  ],
  "closed": []
}
```

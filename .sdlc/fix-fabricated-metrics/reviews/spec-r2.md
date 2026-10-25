# SPEC Review — Round 2

## Summary

Verdict: **APPROVE**. All 16 R1 findings are closed at `a17d3a2`. The revision brings
the null-safe refill callers and the `max(125.0, …)` floor into scope with an explicit
#5 boundary, makes `source`/`source_detail` BREAKING, splits leaf performance into
`live_testnet`/`paper_model` sub-blocks, states Solana-only attribution, and defines
paper PnL, `active_positions_count = null`, persisted-key handling, fallback continuity,
the legacy-drawer trade-off, and the ADR-0002 amendment. The traceability, UI, offline,
badge, and audit gaps are closed. No regression or unimplementable requirement was
introduced. Two non-blocking follow-ups are noted for PLAN/DEV (see below). Checks pass.

## Findings

### SPEC-R1-F01 — [blocker] Nullable leaf PnL breaks the OpenRouter refill consumers
- Location: `proposal.md#L67`, `proposal.md#L69`, `specs/integrity/spec.md#L261-L286`; `backend/server.py#L243-L250`, `backend/agents/orchestrator.py#L575-L580`
- Evidence: `Impact` now names `/api/v1/openrouter/refill` and the Master reflection caller. Requirement "Refill gating consumes null-safe measured PnL only" forbids passing `null` to a numeric conversion and requires the sum of non-null `MEASURED` values; scenarios L265-L286 cover the fresh-install null case and the measured `0.0` total.
- Required fix: (resolved) Both call sites traced and null handling specified with scenarios.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [major] The `max(125.0, pnl)` floor and paper-PnL mixing on the refill gate are unscoped
- Location: `proposal.md#L23`, `proposal.md#L59`, `specs/integrity/spec.md#L261-L286`; `backend/agents/monitor.py#L358-L364`
- Evidence: Requirement L263 mandates the actual measured sum, including `0.0`, forbids the floor and the simulated `paper_model` `live_pnl_usd`, and names the remaining #5 defects as out of scope. `Non-goals` L59 cites issue #5 (confirmed OPEN, "CostGuard auto-refill bypasses the profit gate…"). Scenario L276 asserts the gate receives `0.00` and rejects with `rejected_no_realized_profit`, matching `monitor.py#L358-L364`.
- Required fix: (resolved) Floor and paper mixing are in scope for both callers; the #5 boundary is explicit.
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [major] The `source` field already exists as free text; the contract impact is misstated as additive
- Location: `proposal.md#L34`, `proposal.md#L69`, `specs/integrity/spec.md#L83-L133`; `backend/core/state_store.py#L897`, `#L911`, `#L923`, `backend/server.py#L131`
- Evidence: `engine_metrics.*.source` is reclassified **BREAKING** (proposal L34, L69; spec L101). The descriptive strings move to `source_detail` (scenario L129-L133). `executions_source` is fixed to `backtest_fixture | paper_model | live_testnet`, every execution row carries the mapped enum, and fixture/live rows cannot interleave (L101).
- Required fix: (resolved) Breaking type change, `source_detail` destination, and the `source`/`executions_source`/`executions` relationship are defined.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [major] A single block-level `source` cannot describe a leaf block that mixes populations
- Location: `specs/integrity/spec.md#L59-L81`, `#L141-L167`; `backend/core/hierarchy.py#L1429-L1430`
- Evidence: Requirement L59 splits the leaf into `performance.live_testnet` and `performance.paper_model`, each with a mandatory source; L61 fixes the source per population regardless of row count, defines the flat-mirror rule, forbids `BOOTSTRAP`/`null` for a known population, and L143 defines `treasury.source` as `MEASURED` when non-null and `BOOTSTRAP` when null. Scenarios L63-L81 and L145-L167 assert each state.
- Required fix: (resolved) Per-population sub-blocks, flat-mirror rule, empty-population source, and treasury null-source are defined.
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [major] Per-leaf execution rows do not exist for 25 of 26 leaves; paper/position derivations undefined
- Location: `specs/integrity/spec.md#L3-L57`; `backend/core/state_store.py#L141-L144`, `#L183-L188`, `backend/core/hierarchy.py#L1874-L1880`
- Evidence: Requirement L5 states `leaf-solana` is the only attributed leaf because the persisted ledger is Solana-filtered and the other 25 stay `null` (scenario L12-L16). Requirement L37-L39 defines paper PnL/win rate from the `paper_model` population for `leaf-solana`, paper Sharpe `null`, and `active_positions_count = null` for every leaf; scenarios L41-L57 cover both. This matches the existing attribution wiring at `hierarchy.py#L1874-L1880`.
- Required fix: (resolved) Per-leaf source/mapping stated, paper PnL and position count defined with scenarios.
- Status: closed
- Origin: initial

### SPEC-R1-F06 — [major] Persisted Redis hierarchy rehydrates the fabricated leaf values
- Location: `specs/integrity/spec.md#L169-L184`; `backend/core/hierarchy.py#L1528-L1584`
- Evidence: Requirement L171 requires load to ignore the five performance keys and persist to stop writing them, while retaining allocation/weight/posture/enabled/objective/thesis/history. Scenarios L173-L184 assert both the load and persist observables.
- Required fix: (resolved) Migration requirement and scenarios added.
- Status: closed
- Origin: initial

### SPEC-R1-F07 — [major] `DETERMINISTIC_FALLBACK` drawers still fabricate continuity and LLM telemetry
- Location: `specs/integrity/spec.md#L241-L259`; `backend/agents/orchestrator.py#L392-L395`, `#L890-L895`, `#L910-L931`
- Evidence: Requirement L243 sets `INITIAL` unless the same wing already holds an `LLM` drawer, forbids escalation beyond that drawer's state, and defines telemetry as empty/0/0 when no call was attempted (recorded usage when billed). Scenarios L245-L259 cover fresh install, prior LLM drawer, and no-call telemetry.
- Required fix: (resolved) Fallback continuity and telemetry are constrained with scenarios.
- Status: closed
- Origin: initial

### SPEC-R1-F08 — [major] Re-labelling all legacy drawers `BOOTSTRAP` is not an explicit accepted trade-off
- Location: `proposal.md#L8`, `proposal.md#L60`, `specs/integrity/spec.md#L207-L211`
- Evidence: Review Card `Risk` L8 states the accepted trade-off (genuine pre-change LLM theses become invisible to the continuity prompt); `Non-goals` L60 states it is not a reconstruction task; scenario L207-L211 asserts a genuine pre-change LLM drawer is excluded from injection while remaining visible as `BOOTSTRAP`.
- Required fix: (resolved) Trade-off disclosed and post-upgrade observable asserted.
- Status: closed
- Origin: initial

### SPEC-R1-F09 — [major] Contradiction with ADR-0002's continuity guarantee
- Location: `specs/integrity/spec.md#L213-L239`, `proposal.md#L70`; `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md#L37`, `#L61-L62`
- Evidence: Requirement L215 restricts injection to `LLM`/`DETERMINISTIC_FALLBACK`, states the depth-profile counts are maxima, and requires ADR-0002 to be amended. `Impact` L70 lists the ADR amendment as a deliverable.
- Required fix: (resolved) Contradiction reconciled by an explicit injection rule plus an ADR-0002 amendment deliverable.
- Status: closed
- Origin: initial

### SPEC-R1-F10 — [major] Several backend performance payloads are unenumerated
- Location: `specs/integrity/spec.md#L83-L139`; `backend/core/state_store.py#L823`, `backend/server.py#L109`, `#L131`, `#L233-L237`
- Evidence: Requirement L87-L99 enumerates `last_rust_backtest`, the leaf backtest summary, `engine_metrics.executions[]`, `testnet_telemetry`, and the QuantAuditor output with required sources. Scenarios L109-L127 cover the fixture execution fallback, leaf backtest surfaces, and testnet/auditor labelling.
- Required fix: (resolved) Payloads enumerated and scenarios added.
- Status: closed
- Origin: initial

### SPEC-R1-F11 — [major] UI scope is unbounded and `Impact` omits `Dashboard.jsx`
- Location: `specs/integrity/spec.md#L288-L337`, `proposal.md#L67-L68`; `frontend/src/components/Dashboard.jsx#L148`, `backend/agents/analysis.py#L66-L70`
- Evidence: Requirement L290-L294 enumerates the exact LeafAgentView, MasterOverview, and Dashboard surfaces. `Impact` L68 adds `Dashboard.jsx` and L67 adds `backend/agents/analysis.py`; the QuantAuditor output is in scope as `FIXTURE` (table L99, scenario L122-L127).
- Required fix: (resolved) UI scope enumerated and backend surfaces added to `Impact`.
- Status: closed
- Origin: initial

### SPEC-R1-F12 — [major] "Retained prior values MUST NOT be presented as current measurements" is unverifiable
- Location: `specs/integrity/spec.md#L339-L366`; `frontend/src/App.jsx#L68-L86`
- Evidence: Requirement L341 defines the observable: on a failed poll after success, an `OFFLINE` badge with the last-success timestamp and `—` for every performance/treasury figure, with no retained numeric value. Scenario L361-L366 asserts all three.
- Required fix: (resolved) Observable offline/stale treatment defined and asserted.
- Status: closed
- Origin: initial

### SPEC-R1-F13 — [minor] The provenance-badge scenario bundles two behaviours
- Location: `specs/integrity/spec.md#L322-L337`
- Evidence: Three scenarios now exist: attributed badge (L322), `BOOTSTRAP` badge (L327), `UNATTRIBUTED` badge (L333).
- Required fix: (resolved) Split into one behaviour per scenario.
- Status: closed
- Origin: initial

### SPEC-R1-F14 — [minor] Audit-document scenarios depend on hard-coded figures and an undefined "figure block"
- Location: `specs/integrity/spec.md#L390-L421`
- Evidence: Requirement L392 defines a figure block as any table row, bullet, or paragraph stating a numeric performance value, uses generic population/source labels, and scenario L399-L403 anchors named figures to the document "at the reviewed SHA".
- Required fix: (resolved) Figure block defined and figures anchored.
- Status: closed
- Origin: initial

### SPEC-R1-F15 — [minor] Requirement 4 cites a WebSocket drawer snapshot that does not exist
- Location: `specs/integrity/spec.md#L186-L211`; `backend/core/hierarchy.py#L1873`, `#L1884`, `#L1920`, `backend/agents/orchestrator.py#L969`
- Evidence: Requirement L188 names only `/api/v1/status` surfaces — `hierarchy.master_orchestrator.palace_drawers`, `hierarchy.leaves[].palace_drawers`, `hierarchy.leaves[].mempalace_drawers`, `cognitive_engine.palace_drawers` — all confirmed in code. The WebSocket reference is gone.
- Required fix: (resolved) Real REST surfaces named; non-existent surface removed.
- Status: closed
- Origin: initial

### SPEC-R1-F16 — [nit] Review Card `## Why` paragraph exceeds two sentences
- Location: `proposal.md#L27-L29`
- Evidence: `## Why` now has two paragraphs of two sentences each.
- Required fix: (resolved) Paragraph split.
- Status: closed
- Origin: initial

## Non-blocking follow-ups (not findings)

- `backend/core/state_store.py#L818` sets `executions_source = "rust_leaf_backtest"` on the leaf backtest result. The spec fixes the enum only for `engine_metrics.executions_source` and labels the leaf summary `FIXTURE`; PLAN/DEV should reconcile this extra `executions_source` value rather than leave a fourth vocabulary beside the summary `source`.
- The `BOOTSTRAP` UI scenario (L327-L331) asserts "every value renders as `—`", while requirement L215 mandates seeded-drawer `tokens_used = 0` and `cost_usd = 0` (non-null). Clarify in PLAN whether zero telemetry renders as `0` or `—` so DEV has one observable.

## Checks run

- `openspec validate fix-fabricated-metrics --strict` → PASS (`Change 'fix-fabricated-metrics' is valid`)
- `scripts/sdlc/spec-lint.py --change fix-fabricated-metrics` → PASS (183 words, 1 diagram, ~1.4 min; `design.md`/`tasks.md` absent at PLAN stage)
- `scripts/sdlc/sdlc.sh check fix-fabricated-metrics` → PASS
- Reviewed SHA: `a17d3a240d7ef85a931157c2fe44227b370e8873`; `openspec/` artifacts clean at this SHA.
- Read time: ~22 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-fabricated-metrics",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "a17d3a240d7ef85a931157c2fe44227b370e8873",
  "verdict": "APPROVE",
  "summary": "All 16 R1 findings are closed at a17d3a2; the revision introduces no regression, security, or critical defect, and the spec is coherent and implementable.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L67, proposal.md#L69, specs/integrity/spec.md#L261-L286",
      "evidence": "Impact names both refill call sites; the null-safe measured-only refill requirement and scenarios are present.",
      "required_fix": "Resolved: both call sites traced and null handling specified."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L23, proposal.md#L59, specs/integrity/spec.md#L261-L286",
      "evidence": "Floor and paper-PnL mixing are in scope for both callers; issue #5 is cited as the explicit boundary and confirmed open.",
      "required_fix": "Resolved: floor and mixing scoped in, #5 boundary explicit."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L34, proposal.md#L69, specs/integrity/spec.md#L83-L133",
      "evidence": "engine_metrics.*.source is BREAKING, descriptive text moves to source_detail, and executions_source/executions are defined.",
      "required_fix": "Resolved: breaking type change and field relationship defined."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L59-L81, specs/integrity/spec.md#L141-L167",
      "evidence": "Per-population sub-blocks with own source, flat-mirror rule, empty-population rule, and treasury null-source are defined.",
      "required_fix": "Resolved: per-population provenance and treasury null-source defined."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L3-L57",
      "evidence": "Solana-only attribution is stated; paper PnL/win rate and active_positions_count null are defined with scenarios.",
      "required_fix": "Resolved: per-leaf mapping and derivations defined."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L169-L184",
      "evidence": "Load ignores and persist stops writing the five performance keys; both observables are asserted.",
      "required_fix": "Resolved: persisted-key migration specified with scenarios."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L241-L259",
      "evidence": "Fallback continuity constrained to INITIAL unless a same-wing LLM drawer exists; telemetry defined with scenarios.",
      "required_fix": "Resolved: fallback continuity and telemetry constrained."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L8, proposal.md#L60, specs/integrity/spec.md#L207-L211",
      "evidence": "Risk and Non-goals disclose the legacy-thesis loss; scenario asserts the post-upgrade read.",
      "required_fix": "Resolved: trade-off disclosed and scenario added."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L213-L239, proposal.md#L70",
      "evidence": "Injection rule and depth-count maxima are stated; ADR-0002 amendment is a listed deliverable.",
      "required_fix": "Resolved: ADR-0002 reconciled and amendment required."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L83-L139",
      "evidence": "All cited payloads are enumerated with sources; execution, leaf backtest, testnet, and auditor scenarios exist.",
      "required_fix": "Resolved: payloads enumerated with scenarios."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L288-L337, proposal.md#L67-L68",
      "evidence": "UI surfaces are enumerated; Dashboard.jsx and analysis.py are in Impact; QuantAuditor is in scope as FIXTURE.",
      "required_fix": "Resolved: UI scope enumerated and traced."
    },
    {
      "id": "SPEC-R1-F12",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L339-L366",
      "evidence": "OFFLINE badge with last-success timestamp and em-dash replacement are the asserted observable.",
      "required_fix": "Resolved: observable stale treatment defined."
    },
    {
      "id": "SPEC-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L322-L337",
      "evidence": "The badge scenario is split into attributed, bootstrap, and unattributed scenarios.",
      "required_fix": "Resolved: scenarios split."
    },
    {
      "id": "SPEC-R1-F14",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L390-L421",
      "evidence": "Figure block is defined and named figures are anchored to the reviewed SHA.",
      "required_fix": "Resolved: figure block defined."
    },
    {
      "id": "SPEC-R1-F15",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/integrity/spec.md#L186-L211",
      "evidence": "Only real REST drawer surfaces are named; the WebSocket reference is removed.",
      "required_fix": "Resolved: REST surfaces named."
    },
    {
      "id": "SPEC-R1-F16",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L27-L29",
      "evidence": "The Why section is split into two two-sentence paragraphs.",
      "required_fix": "Resolved: paragraph split."
    }
  ],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04",
    "SPEC-R1-F05",
    "SPEC-R1-F06",
    "SPEC-R1-F07",
    "SPEC-R1-F08",
    "SPEC-R1-F09",
    "SPEC-R1-F10",
    "SPEC-R1-F11",
    "SPEC-R1-F12",
    "SPEC-R1-F13",
    "SPEC-R1-F14",
    "SPEC-R1-F15",
    "SPEC-R1-F16"
  ]
}
```

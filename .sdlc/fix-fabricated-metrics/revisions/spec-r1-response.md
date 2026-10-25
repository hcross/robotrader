stage: spec
round: 1
head_sha: 777656de97303a6247f2cb9be7f54f6dcf0e5dc3
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: "proposal.md §Impact now names both refill call sites (`backend/server.py` `/api/v1/openrouter/refill` and the `backend/agents/orchestrator.py` Master reflection caller). New requirement 'Refill gating consumes null-safe measured PnL only' forbids numeric conversion of null and adds scenario 'Null leaf PnL does not raise in the refill path'."
  - id: SPEC-R1-F02
    action: fixed
    evidence: "Brought both caller defects into scope: 'Refill gating consumes null-safe measured PnL only' removes the max(125.0, …) floor and excludes simulated paper PnL, with scenarios 'Refill sum excludes simulated PnL' and 'No fabricated profit floor'. proposal.md §Non-goals names the remaining issue #5 defects (automatic path bypass, Rust validator, balance source, daily rollover, low-watermark) as out of scope."
  - id: SPEC-R1-F03
    action: fixed
    evidence: "proposal.md §Impact reclassifies `engine_metrics.*.source` as a BREAKING type change. Requirement 'Every performance payload declares its provenance' moves descriptive text to `source_detail`, fixes `executions_source` as a population identifier, and requires each execution row to carry the mapped enum."
  - id: SPEC-R1-F04
    action: fixed
    evidence: "Requirement 'Leaf performance blocks are split by population' introduces per-population sub-blocks each with its own source, defines the flat-mirror rule, states that an empty population keeps MEASURED/SIMULATED, and reserves BOOTSTRAP for declared non-population placeholders. 'Master aggregate derives only from declared evidence' defines treasury.source as MEASURED when non-null and BOOTSTRAP when null."
  - id: SPEC-R1-F05
    action: fixed
    evidence: "'Leaf live performance requires execution evidence' states that only leaf-solana is attributed because the ledger is Solana-filtered, and that the other 25 leaves stay null (scenario 'Only solana is attributed from the ledger'). 'Leaf paper performance and position count derive only from declared evidence' defines paper PnL/win rate from `paper_model` and makes `active_positions_count` null for every leaf, with scenarios for both."
  - id: SPEC-R1-F06
    action: fixed
    evidence: "New requirement 'Persisted leaf performance is not rehydrated' requires load to ignore persisted performance keys and persist to stop writing them, with scenarios 'Legacy persisted performance is ignored on load' and 'Persisted payload no longer carries performance keys'. proposal.md §Impact names the Redis load/persist path."
  - id: SPEC-R1-F07
    action: fixed
    evidence: "New requirement 'Deterministic fallback drawers claim no unfounded continuity' requires INITIAL unless a real LLM drawer exists in the wing, forbids escalation, and defines telemetry (empty/0/0 when no call was attempted), with three scenarios including 'Fallback on a fresh install claims no confirmation'."
  - id: SPEC-R1-F08
    action: fixed
    evidence: "proposal.md Review Card Risk and §Non-goals now state that genuine pre-change LLM theses become invisible to the continuity prompt. Requirement 'Palace drawers declare provenance' adds scenario 'Pre-change LLM thesis loses continuity injection'."
  - id: SPEC-R1-F09
    action: fixed
    evidence: "Requirement 'Bootstrap drawers carry no LLM telemetry and no prior-thesis claim' records the ADR-0002 rule: only LLM and DETERMINISTIC_FALLBACK drawers are injected and depth-profile counts are maxima. proposal.md §Impact lists the ADR-0002 amendment as a deliverable."
  - id: SPEC-R1-F10
    action: fixed
    evidence: "Requirement 'Every performance payload declares its provenance' enumerates `leaf.last_rust_backtest`, `POST /api/v1/leaf/{leaf_id}/backtest`, `engine_metrics.executions` rows, `testnet_telemetry`, and the QuantAuditor output, with scenarios 'Fixture execution fallback is labelled', 'Leaf backtest surfaces are labelled', and 'Testnet telemetry and auditor are labelled'."
  - id: SPEC-R1-F11
    action: fixed
    evidence: "Requirement 'UI renders absent metrics as an em dash with provenance' replaces 'every other metric tile' with an enumerated list of LeafAgentView, MasterOverview, and Dashboard surfaces. proposal.md §Impact adds `frontend/src/components/Dashboard.jsx` and `backend/agents/analysis.py`; the QuantAuditor output is in scope and must carry source FIXTURE."
  - id: SPEC-R1-F12
    action: fixed
    evidence: "Requirement 'Offline UI state invents no portfolio and replaces stale values' defines the observable: an `OFFLINE` badge with the last-success timestamp and every performance/treasury figure rendered as `—`, asserted by scenario 'Failed poll replaces retained values with an em dash'."
  - id: SPEC-R1-F13
    action: fixed
    evidence: "The bundled badge scenario is split into 'Attributed provenance badge is visible', 'Bootstrap block renders an em dash with a bootstrap badge', and 'Unattributed block renders an em dash with an unattributed badge'."
  - id: SPEC-R1-F14
    action: fixed
    evidence: "Requirement 'Audit document separates fixture from measured' defines a figure block as any table row, bullet, or paragraph stating a numeric performance value, uses generic population/source labels, and anchors named figures to the document at the reviewed SHA."
  - id: SPEC-R1-F15
    action: fixed
    evidence: "Requirement 'Palace drawers declare provenance' names only the REST surfaces `/api/v1/status` (`hierarchy.master_orchestrator.palace_drawers`, `hierarchy.leaves[].palace_drawers`, `hierarchy.leaves[].mempalace_drawers`, `cognitive_engine.palace_drawers`) and drops the non-existent WebSocket drawer reference."
  - id: SPEC-R1-F16
    action: fixed
    evidence: "proposal.md §Why is split into two two-sentence paragraphs."

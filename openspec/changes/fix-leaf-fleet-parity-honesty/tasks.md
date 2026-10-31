# Tasks: Fix Leaf Fleet Parity & Execution Honesty

## 1. Rust Strategy Pod Catalog & CLI Export

- [ ] 1.1 Align `ecosystem_pod_specs` in `engine-rs/crates/strategies/src/lib.rs` for all 26 leaf ecosystems with valid weights, slots, and descriptions (covers: `Requirement: Full 26-leaf pod catalog parity across Rust and Python`, `Scenario: All 26 leaves exhibit identical pod definitions in Python and Rust`, `Scenario: Pod default weights form a valid allocation`).
- [ ] 1.2 Implement canonical specs for the 7 previously divergent audit leaves (`leaf-bnb`, `leaf-xrp`, `leaf-ton`, `leaf-tron`, `leaf-avalanche`, `leaf-cosmos`, `leaf-binance-cex`) in `engine-rs/crates/strategies/src/lib.rs` (covers: `Scenario: Divergent audit leaves match Rust canonical specs`).
- [ ] 1.3 Add CLI flag `--dump-pod-catalog` (with alias `--export-pod-catalog`) to `robotrader-node` in `engine-rs/crates/node/src/main.rs` to export the full 26-leaf Strategy Pod catalog as JSON (covers: `Requirement: Node CLI exports deterministic pod catalog`, `Scenario: CLI exports full fleet pod catalog as valid JSON`).
- [ ] 1.4 Support single-leaf export with `--leaf-id <id>` in `robotrader-node --dump-pod-catalog`, outputting a JSON array with exit code 0 (covers: `Scenario: CLI exports single leaf pod catalog`).
- [ ] 1.5 Enforce non-zero exit code and stderr error diagnostic on unrecognized `--leaf-id` in `robotrader-node --dump-pod-catalog` (covers: `Scenario: CLI rejects unrecognized leaf identifier`).

## 2. Python Fleet Manager Parity & Execution Classification

- [ ] 2.1 Update `HierarchicalFleetManager._build_rust_pods_for_leaf` in `backend/core/hierarchy.py` to match `ecosystem_pod_specs` across all 26 leaves with 100% attribute equality (covers: `Requirement: Full 26-leaf pod catalog parity across Rust and Python`, `Scenario: All 26 leaves exhibit identical pod definitions in Python and Rust`, `Scenario: Divergent audit leaves match Rust canonical specs`).
- [ ] 2.2 Add `execution_mode: "ACTIVE_SOLANA"` and `scheduler_active` reflecting scheduler state to `leaf-solana` in `backend/core/hierarchy.py` (covers: `Requirement: Leaf execution mode and scheduling classification`, `Scenario: Solana leaf declares active execution mode`).
- [ ] 2.3 Add `execution_mode: "PASSIVE_CATALOG"` and `scheduler_active: False` to the 25 non-Solana leaves in `backend/core/hierarchy.py` (covers: `Requirement: Leaf execution mode and scheduling classification`, `Scenario: Non-Solana leaves declare passive catalog execution mode`).
- [ ] 2.4 Preserve `execution_mode` and `scheduler_active` across all 26 leaves in `HierarchicalFleetManager.get_hierarchy_snapshot` and add endpoint `GET /api/v1/hierarchy/overview` in `backend/server.py` (covers: `Scenario: Hierarchy overview preserves execution mode across all 26 leaves`).
- [ ] 2.5 Add `ta_metrics_source: "CATALOG_FIXTURE"` for non-Solana leaves and classify `leaf-solana` telemetry in `backend/core/hierarchy.py` (covers: `Requirement: Telemetry source classification for leaf metrics`, `Scenario: Non-Solana leaf declares catalog fixture telemetry source`).
- [ ] 2.6 Propagate `ta_metrics_source` consistently across `get_leaf_detail`, `get_hierarchy_snapshot`, and REST endpoints in `backend/core/hierarchy.py` and `backend/server.py` (covers: `Scenario: Telemetry source persists across leaf detail and summary endpoints`).

## 3. Social Panorama & RSS Feed Provenance Stamping

- [ ] 3.1 Emit `"composite_sentiment"` (lowercase) and `"Composite_sentiment"` (legacy alias) in `SocialMacroPanoramaTool.build_panorama` in `backend/tools/ta_tools.py` (covers: `Requirement: Social/macro panorama composite sentiment casing`, `Scenario: Panorama returns lowercase composite sentiment`, `Scenario: Legacy uppercase key remains available for backward compatibility`).
- [ ] 3.2 Update `OrchestratorAgent._build_reflection_prompts` in `backend/agents/orchestrator.py` to read `"composite_sentiment"` without receiving null (covers: `Scenario: Orchestrator reflection prompt receives non-null composite sentiment`).
- [ ] 3.3 Compute multi-symbol confluence as arithmetic mean over present symbols in `SocialMacroPanoramaTool.build_panorama` without hardcoded BTC/ETH keys or arbitrary fixed denominators (covers: `Requirement: Dynamic confluence calculation over present symbol snapshots`, `Scenario: Confluence calculated from available Solana symbols`, `Scenario: Single-symbol snapshot computes exact single score`).
- [ ] 3.4 Fall back to neutral `0.0` confluence on empty or invalid snapshots in `SocialMacroPanoramaTool.build_panorama` without `ZeroDivisionError` (covers: `Scenario: Empty snapshot yields neutral fallback`).
- [ ] 3.5 Attach `source_kind: "SYNTHETIC_FIXTURE"` to all static narrative items and social signals in `SocialMacroPanoramaTool.build_panorama` (covers: `Requirement: Static social and macro narrative fields declare synthetic provenance`, `Scenario: Social signals declare synthetic fixture provenance`, `Scenario: Panorama root payload declares narrative provenance`).
- [ ] 3.6 Stamp live fetched items with `source_kind: "LIVE_RSS"` and `curated: False` in `EcosystemRSSAggregator.get_feed_for_agent` in `backend/tools/rss_tools.py` (covers: `Requirement: Ecosystem RSS feed provenance stamping`, `Scenario: Live RSS items declare live RSS provenance`).
- [ ] 3.7 Stamp curated fallback items with `source_kind: "CURATED_FIXTURE"` and `curated: True`, replacing dynamic fake timestamps with fixed fixture timestamps in `EcosystemRSSAggregator.get_feed_for_agent` (covers: `Requirement: Ecosystem RSS feed provenance stamping`, `Scenario: Curated fallback items declare curated fixture provenance`, `Scenario: Curated items do not fabricate real-time fresh timestamps`).
- [ ] 3.8 Compute feed-level summary metrics `feed_mode` (`"LIVE"`, `"MIXED"`, `"CURATED_FALLBACK"`), `live_count`, and `curated_count` in `EcosystemRSSAggregator.get_feed_for_agent` (covers: `Requirement: Ecosystem RSS feed provenance stamping`, `Scenario: Empty feed items collection defaults to curated fallback mode`).

## 4. Frontend Execution & Telemetry Transparency

- [ ] 4.1 Update `frontend/src/components/MasterOverview.jsx` to display `ACTIVE_SOLANA` badge for `leaf-solana` and `PASSIVE_CATALOG` badges for the 25 other leaves in the fleet table (covers: `Requirement: Frontend surfaces execution and telemetry honesty`, `Scenario: Master overview table distinguishes active leaf from passive fleet`).
- [ ] 4.2 Update `frontend/src/components/LeafAgentView.jsx` header to render a `PASSIVE_CATALOG` badge for non-Solana leaves, indicating background scheduling is inactive (covers: `Requirement: Frontend surfaces execution and telemetry honesty`, `Scenario: Leaf view renders passive catalog badge for non-Solana leaf`).
- [ ] 4.3 Update the Technical Analysis & On-chain metrics panel in `frontend/src/components/LeafAgentView.jsx` to render a `CATALOG_FIXTURE` badge and explanatory caption for non-Solana leaves (covers: `Requirement: Frontend surfaces execution and telemetry honesty`, `Scenario: Leaf view renders catalog fixture badge on technical metrics`).

## 5. Automated Parity Verification Suite & Integration Testing

- [ ] 5.1 Implement automated parity test suite asserting 100% attribute equality between Python `_build_rust_pods_for_leaf` and Rust `ecosystem_pod_specs` across all 26 leaves in `backend/tests/test_hierarchy_v3.py` (covers: `Requirement: Automated parity verification gate`, `Scenario: Automated test asserts full fleet catalog parity`).
- [ ] 5.2 Add negative assertion test verifying that any pod attribute mismatch (name, weight, slot, description) triggers an explicit test failure (covers: `Requirement: Automated parity verification gate`, `Scenario: Discrepancy in any attribute triggers test failure`).
- [ ] 5.3 Add unit and integration tests in `backend/tests/test_hierarchy_v3.py` verifying `execution_mode`, `ta_metrics_source`, `composite_sentiment` non-null propagation, dynamic confluence averaging, and RSS feed provenance stamping (covers: `Requirement: Leaf execution mode and scheduling classification`, `Requirement: Telemetry source classification for leaf metrics`, `Requirement: Social/macro panorama composite sentiment casing`, `Requirement: Dynamic confluence calculation over present symbol snapshots`, `Requirement: Ecosystem RSS feed provenance stamping`).

## 6. Platform Documentation Honesty Updates

- [ ] 6.1 Update `AGENTS.md` to state that `leaf-solana` is the single active scheduled leaf with hot-path policy compilation and that the 25 non-Solana leaves are passive catalog rows (covers: `Requirement: Documentation honestly describes single-active-leaf implementation status`, `Scenario: AGENTS document states single-active-leaf status`).
- [ ] 6.2 Update `README.md` to clarify the single-active-leaf implementation status of the 26-leaf fleet (covers: `Requirement: Documentation honestly describes single-active-leaf implementation status`).
- [ ] 6.3 Add an amendment note in `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` clarifying the single-active-leaf implementation phase, `ACTIVE_SOLANA` vs `PASSIVE_CATALOG` execution classification, and provenance stamping (covers: `Requirement: Documentation honestly describes single-active-leaf implementation status`, `Scenario: ADR-0003 status note clarifies current implementation phase`).

## Verification

- `cd engine-rs && cargo test` → expected: All Rust unit and integration tests pass with zero failures.
- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` → expected: Node binary builds cleanly and `--dump-pod-catalog` emits valid 26-leaf JSON on stdout.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: All Python unit, architecture, and parity tests pass with zero failures.
- `cd frontend && npm run build` → expected: Production frontend bundle compiles without JSX, CSS, or TypeScript errors.
- `openspec validate fix-leaf-fleet-parity-honesty --strict` → expected: Schema validation passes with exit code 0.
- `python3 scripts/sdlc/spec-lint.py --change fix-leaf-fleet-parity-honesty` → expected: Spec lint checks pass with exit code 0.

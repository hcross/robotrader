# Tasks — fix-fabricated-metrics

> Design: [`design.md`](design.md). Spec: [`specs/integrity/spec.md`](specs/integrity/spec.md). Reference the spec for *what*; this list only orders *how*.

## 1. Provenance contract foundation

- [ ] 1.1 Create `backend/core/provenance.py` with `METRIC_SOURCES = ("MEASURED", "SIMULATED", "FIXTURE", "BOOTSTRAP")`, `DRAWER_SOURCES = ("LLM", "DETERMINISTIC_FALLBACK", "BOOTSTRAP")`, `execution_rows_source()`, `eligible_drawer_source()`, and fail-closed normalisers. No third-party dependency. (covers: "Every performance payload declares its provenance"; design D1)
- [ ] 1.2 Map `backtest_fixture -> FIXTURE`, `paper_model -> SIMULATED`, `live_testnet -> MEASURED`; reject every other population token. Unit-test the mapping and the `rust_leaf_backtest` rejection. (covers: "Engine populations and executions map to enum sources"; design D4)
- [ ] 1.3 In `backend/core/state_store.py#get_population_metrics`, replace the free-text `source` on `backtest_fixture`, `paper_model`, and `live_testnet` with the enum and move each existing description to `source_detail`. (covers: "Free text moves to source detail"; design D5)
- [ ] 1.4 Extend `HybridStateStore._sample_stats` with a per-trade `sharpe_ratio` (mean divided by sample standard deviation of the PnL column) that is `None` when there are fewer than two rows or zero variance; leave the existing fields unchanged. (covers: "Undefined statistic is null"; "Measured live metrics derive from attributed rows"; design D3)
- [ ] 1.5 In `run_rust_backtest_for_leaf`, replace `executions_source = "rust_leaf_backtest"` with `"backtest_fixture"`, add `source = "FIXTURE"` and a leaf-replay `source_detail`, and store `source = "FIXTURE"` plus the same detail on `hierarchy.leaves[leaf_id]["last_rust_backtest"]`. (covers: R2 follow-up 1; "Leaf backtest surfaces are labelled"; design D4)
- [ ] 1.6 In `backend/server.py#get_system_status`, derive `executions_source` once, attach the mapped enum as `source` to a copied row object for every `engine_metrics.executions` row, and never mutate the store's rows. (covers: "Fixture execution fallback is labelled"; design D4)
- [ ] 1.7 In `HybridStateStore.get_testnet_telemetry`, add `source = "MEASURED"` and a `source_detail`, including the `enabled: False` branch; when disabled, return no numeric performance field. (covers: "Testnet telemetry and auditor are labelled"; design D5)
- [ ] 1.8 In `QuantAuditorAgent.audit_latest_backtest`, add `source = "FIXTURE"` and a `source_detail` that names the deterministic replay, and expose the verdict as a fixture verdict. (covers: "Testnet telemetry and auditor are labelled"; design D5)

## 2. Leaf performance API shape

- [ ] 2.1 Delete the five fabricated fields from `HierarchicalFleetManager._init_leaves` (`sharpe_ratio`, `win_rate_pct`, `realized_pnl_usd`, `paper_pnl_usd`, `active_positions_count`). Keep allocation, weight, posture, enabled, interval, objective, and thesis fields untouched. (covers: "Leaf live performance requires execution evidence"; design D2)
- [ ] 2.2 Add `ATTRIBUTED_LIVE_LEAF_IDS = ("leaf-solana",)` and a pure `leaf_performance(leaf_id, populations)` helper returning the two sub-blocks from design D2/D3, with population sources kept even when every value is `null`. (covers: "Leaf performance blocks are split by population"; "Only solana is attributed from the ledger"; design D2, D3)
- [ ] 2.3 Make `get_leaf_detail` populate `leaf["performance"]` from `leaf_performance`, remove the flat `realized_pnl_usd` / `paper_pnl_usd` / `sharpe_ratio` / `win_rate_pct` keys, and set `active_positions_count` to `None` on every returned leaf. (covers: "Leaf with no attributed executions reports null live metrics"; "Position count is never synthesized"; design D2)
- [ ] 2.4 In `get_hierarchy_snapshot`, compute `total_realized_pnl_usd` as the sum of non-null `performance.live_testnet.realized_pnl_usd` values and `null` when none exists; add `treasury.source` (`MEASURED` or `BOOTSTRAP`) and `treasury.source_detail`; expose `active_leaves_count` as `null` when the leaf list is empty; replace the `openrouter_credit` default `24.5` with `null` while preserving a measured `0.0`. (covers: "No measured evidence yields a null aggregate"; "Aggregate sums measured values only"; "Missing credit balance is null"; "Missing active-leaf count is null"; "Measured zero stays zero"; design D6)
- [ ] 2.5 Update the Master prompt's `active_leaves_summary` in `backend/agents/orchestrator.py` to read `performance.live_testnet.realized_pnl_usd` and `.sharpe_ratio` null-safely (`None` serialises as `null`), instead of indexing the removed flat keys. (covers: "Master aggregate derives only from declared evidence"; design D2)
- [ ] 2.6 Add unit tests for: non-solana nulls, solana-only attribution, deposit not synthesising a value, measured derivation from rows, single-row Sharpe null, paper derivation and null Sharpe, position count always null, sub-block sources on empty populations, absent flat mirror, treasury aggregate across measured/simulated/null leaves, and the two removed API defaults. (covers: all of group 2 and requirement "Every performance payload declares its provenance")

## 3. Persisted hierarchy state

- [ ] 3.1 In `_load_persisted`, restrict the copied key set to `allocated_capital_usd`, `capital_weight`, `risk_posture`, `enabled`, and `objective_summary`; detect whether any legacy performance key was present. (covers: "Legacy persisted performance is ignored on load"; design D7)
- [ ] 3.2 Factor the persisted leaf object into one `_persisted_payload()` used by `persist()`, containing no performance key; when `_load_persisted` detected legacy keys, rewrite the `robotrader:v3:hierarchy` value once with that payload inside the existing best-effort `try/except`. (covers: "Persisted payload no longer carries performance keys"; design D7)
- [ ] 3.3 Add tests with an in-memory fake Redis function: legacy performance values (`999`, `888`, `2`) are absent after load; a non-Solana leaf reports all-null performance; allocation, weight, posture, enabled, and objective survive; a post-change persist payload has none of the five keys; the one-time compaction leaves the allowed keys intact. (covers: group 3 and requirement "Persisted leaf performance is not rehydrated")

## 4. Palace drawer provenance

- [ ] 4.1 Add `source: str = "BOOTSTRAP"` to `PalaceDrawer`; normalise in `from_dict` (missing, unknown, or `BOOTSTRAP` with telemetry becomes `BOOTSTRAP` with `model_used=""`, `tokens_used=0`, `cost_usd=0.0`, `thesis_continuity="INITIAL"`) and in `add_drawer` before append and Redis mirror. (covers: "Legacy untyped drawer is read as bootstrap"; design D8)
- [ ] 4.2 Change `_seed_initial_palace_drawers` so every seeded Master and leaf drawer is `source="BOOTSTRAP"`, `model_used=""`, `tokens_used=0`, `cost_usd=0.0`, and `thesis_continuity="INITIAL"`. (covers: "Seeded drawer carries no model telemetry"; "Seeded drawer claims no prior confirmation"; design D8)
- [ ] 4.3 Add an eligibility filter to `StrategyMemoryPalace.format_continuity_prompt` and `format_cross_wing_digest` so only `LLM` and `DETERMINISTIC_FALLBACK` drawers are rendered; leave `recall_recent` unfiltered so the REST surfaces still return bootstrap drawers with their badge. (covers: "Bootstrap drawers are absent from the continuity prompt"; "Bootstrap drawers are absent from the cross-wing digest"; "Pre-change LLM thesis loses continuity injection"; design D9)
- [ ] 4.4 Add `fallback_continuity(wing)` returning `INITIAL` unless the same wing holds an `LLM` drawer, in which case it returns that drawer's state; use it in the Master and leaf fallback paths, and set `source="DETERMINISTIC_FALLBACK"` with telemetry recorded only when `p_tok + c_tok > 0` (otherwise `""` / `0` / `0.0`). (covers: "Fallback on a fresh install claims no confirmation"; "Fallback with a prior LLM drawer carries its continuity"; "Fallback without a model call carries no telemetry"; design D10)
- [ ] 4.5 Set `source="LLM"` on the three real-call construction sites (Master drawer, leaf drawer, `leaf_solana` mirror) and inherit the parent's source and continuity on the mirror. (covers: "Every REST drawer declares a source"; design D8)
- [ ] 4.6 Add tests for: every `/api/v1/status` drawer surface (`master_orchestrator.palace_drawers`, `leaves[].palace_drawers`, `leaves[].mempalace_drawers`, `cognitive_engine.palace_drawers`) carrying a source; a `BOOTSTRAP` append surviving the JSONL-plus-Redis round trip; a legacy untyped line read as bootstrap; bootstrap text absent from both prompt builders; the fallback continuity and telemetry scenarios; and all seeded drawers matching the bootstrap row of design D8. (covers: group 4 and requirements 7–9)

## 5. Refill gate call sites

- [ ] 5.1 Add `HybridStateStore.measured_realized_pnl_usd()` returning the sum of non-null `realized_pnl_usd` over rows attributed to `ATTRIBUTED_LIVE_LEAF_IDS`, and `0.0` when there is no row; no paper PnL term and no floor. (covers: "Null leaf PnL does not raise in the refill path"; design D11)
- [ ] 5.2 Replace the sum and `max(125.0, …)` in `backend/server.py#trigger_openrouter_refill` with `state_store.measured_realized_pnl_usd()`. (covers: "Refill sum excludes simulated PnL"; "No fabricated profit floor"; design D11)
- [ ] 5.3 Replace the sum, `float(self.store.live_pnl_usd)` term, and `max(125.0, …)` in `OrchestratorAgent.run_master_orchestrator_reflection` with `state_store.measured_realized_pnl_usd()`. (covers: "Negative measured profit is rejected"; design D11)
- [ ] 5.4 Add tests: all-null leaves give `0.0` and no `TypeError`; measured `10.00` plus simulated `100.00` passes `10.00`; zero measured profit rejects with `rejected_no_realized_profit`; `-4.00` rejects; the helper equals the snapshot's non-null measured sum. (covers: group 5 and requirement "Refill gating consumes null-safe measured PnL only")

## 6. Frontend provenance rendering

- [ ] 6.1 Create `frontend/src/lib/provenance.js` (plain ESM, no JSX) exporting `METRIC_SOURCES`, `DRAWER_SOURCES`, `EM_DASH`, `badgeFor(source)`, and `formatMetric(value, source, kind)` implementing design D12 exactly: source gate before value formatting. (covers: "UI renders absent metrics as an em dash with provenance"; design D12)
- [ ] 6.2 Create `frontend/src/components/SourceBadge.jsx` rendering the label from `badgeFor`, with visibly different styling for `BOOTSTRAP` and `UNATTRIBUTED`. (covers: "Bootstrap block renders an em dash with a bootstrap badge"; "Unattributed block renders an em dash with an unattributed badge")
- [ ] 6.3 In `frontend/src/App.jsx`: replace the `FALLBACK_STATUS` treasury block with `null` capital, deployed, dry powder, and ratio (keep `min_dry_powder_ratio` as the configured policy constant); track `lastSuccessAt`; on a failed poll after a success render the skeleton instead of `statusData` and pass `offlineSince`; render the header badge as `OFFLINE — last success HH:MM:SS`. (covers: "Cold offline render shows no model portfolio"; "Failed poll replaces retained values with an em dash"; design D13)
- [ ] 6.4 In `frontend/src/components/MasterOverview.jsx`: delete the local treasury fallback (`25000`, `19200`, `5800`, `0.232`), the `|| 11` active-leaf default, and the `?? 24.5` credit default; render each governed value through `formatMetric` with its `SourceBadge`; scope the treasury badge to `total_realized_pnl_usd`; badge the drawer cards and suppress their telemetry for `BOOTSTRAP`. (covers: "Master aggregate renders an em dash when null"; "Missing active-leaf count renders as unknown"; "Missing OpenRouter balance renders as unknown"; design D6, D12)
- [ ] 6.5 In `frontend/src/components/LeafAgentView.jsx`: read the PnL/Sharpe/win-rate tile from `performance.live_testnet` and `performance.paper_model` with their badges; render `active_positions_count` as `—`; badge the Rust backtest panel as `FIXTURE`; badge each execution row from its `source`; ignore cached `leafDetail` and `rustBacktestResult` when `offlineSince` is set; badge the drawer cards. (covers: "Leaf view renders an em dash for null metrics"; "Leaf backtest surfaces are labelled"; design D12, D13)
- [ ] 6.6 In `frontend/src/components/Dashboard.jsx`: route the three population tiles, the testnet CEX PnL tile, the execution-table PnL columns, and the cognitive drawer list through `formatMetric`/`SourceBadge`; remove the `|| 0` coercions on performance values while leaving operational fields (weights, notionals) unchanged. (covers: "Dashboard tiles render an em dash for null populations"; "Attributed provenance badge is visible"; design D12)
- [ ] 6.7 Run the pure-helper assertion, `npm run lint`, and `npm run build`; fix any lint or build regression introduced by the new module and badges. (covers: design D15; verification section)

## 7. Documentation and ADR

- [ ] 7.1 In `docs/PERFORMANCE_AND_COST_AUDIT.md`, add a provenance legend (population, source enum, meaning) and restate the spec's figure-block definition at the top of the performance sections. (covers: "Every figure block carries its population and source"; design D16)
- [ ] 7.2 Label every figure block in the document: section headings carry the population and `FIXTURE` / `SIMULATED` / `MEASURED`; numeric tables gain a `Source` column; the executive summary states that only the `live_testnet` figures in §3.3 are measured and that fixture figures are not product performance. (covers: "Fixture figures are not presented as product performance"; "Paper figures are labelled simulated"; "Live figures are labelled measured"; "Executive summary makes no measured claim from a fixture")
- [ ] 7.3 Amend `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md`: qualify Pillar 2's injection promise to `LLM` and `DETERMINISTIC_FALLBACK` drawers only, state that the `5` / `2` depth-profile counts are maxima filled by eligible drawers, and add a dated amendment note pointing at this change. (covers: requirement "Bootstrap drawers carry no LLM telemetry and no prior-thesis claim"; design D9, D10)

## 8. Integration evidence and rollout

- [ ] 8.1 Add an architecture-style test that builds the full `/api/v1/status` payload from a patched store and recursively asserts: every `source` is in its enum, every performance payload in the spec's table carries one, no `engine_metrics.executions` row lacks `source`, and no performance key carries a numeric value without a source. (covers: "Unattributed numeric performance is not served"; design D14)
- [ ] 8.2 Run the grep gates in the verification section and confirm every fabricated constant, the fourth `executions_source` token, and both `max(125.0, …)` sites are gone. (covers: design D4, D11, D16)
- [ ] 8.3 Run the full Python suite and the Rust regression suite; confirm no pre-existing test changed expectations except where the spec deliberately changes the shape. (covers: design D15)
- [ ] 8.4 Run `openspec validate fix-fabricated-metrics --strict` and `scripts/sdlc/sdlc.sh check fix-fabricated-metrics`; both pass. (covers: PLAN quality gate)
- [ ] 8.5 Deploy with `docker compose up --build -d`, run the status and refill smoke assertions, and attach the offline and bootstrap-drawer screenshots to the issue or PR. (covers: all UI requirements and the AGENTS.md deployment check)
- [ ] 8.6 Record the rollback commands from design's Migration Plan in the PR body and confirm the optional Redis cache-delete commands are accurate for the deployed key names. (covers: rollback requirement)

## Verification

Run from the worktree root unless a step changes directory.

- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -p 'test_integrity_provenance.py' -v` -> expected: every new test passes; the output lists the group 1–5 and group 8 assertions.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -p 'test_metrics_populations.py' -v` -> expected: all existing population tests pass, plus the added live-Sharpe and provenance assertions.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` -> expected: the full warm-path suite passes with no error or failure.
- `cd engine-rs && cargo test` -> expected: all Rust tests pass; no file under `engine-rs/` is modified by this change.
- `openspec validate fix-fabricated-metrics --strict` -> expected: `Change 'fix-fabricated-metrics' is valid`.
- `scripts/sdlc/sdlc.sh check fix-fabricated-metrics` -> expected: `spec-lint` PASS and `verdict-lint` PASS.
- `cd frontend && npm run lint` -> expected: exit 0, no new error.
- `cd frontend && npm run build` -> expected: Rolldown build succeeds and writes `dist/`.
- `cd frontend && node --input-type=module -e 'import assert from "node:assert/strict"; import { formatMetric, badgeFor } from "./src/lib/provenance.js"; assert.equal(formatMetric(null, "MEASURED", "money"), "—"); assert.equal(formatMetric(0, "MEASURED", "money"), "$0.00"); assert.equal(formatMetric(0, "BOOTSTRAP", "money"), "—"); assert.equal(formatMetric(undefined, null, "number"), "—"); assert.equal(badgeFor(null), "UNATTRIBUTED"); assert.equal(badgeFor("BOOTSTRAP"), "BOOTSTRAP"); console.log("provenance helper OK")'` -> expected: `provenance helper OK`.
- `git grep -nE '2\.45|64\.5|alloc_usd \* 0\.018|alloc_usd \* 0\.022' -- backend/core/hierarchy.py` -> expected: no output (exit 1).
- `git grep -nE 'tokens_used=1420|tokens_used=620|cost_usd=0\.00048' -- backend` -> expected: no output (exit 1).
- `git grep -n 'rust_leaf_backtest' -- backend` -> expected: no output (exit 1).
- `git grep -nE 'max\(125\.0' -- backend` -> expected: no output (exit 1).
- `git grep -nE 'float\(lf\.get\("realized_pnl_usd"' -- backend` -> expected: no output (exit 1).
- `git grep -nE '\|\| 11|\?\? 24\.5' -- 'frontend/src/**/*.jsx' 'frontend/src/*.jsx'` -> expected: no output (exit 1).
- `git grep -nE '25000|19200|5800|0\.232' -- 'frontend/src/**/*.jsx' 'frontend/src/*.jsx'` -> expected: no output (exit 1).
- `docker compose up --build -d` -> expected: backend and frontend containers healthy.
- `curl -s http://localhost:8000/api/v1/status | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["contract_version"] == 2
assert d["engine_metrics"]["backtest_fixture"]["source"] == "FIXTURE"
assert d["engine_metrics"]["paper_model"]["source"] == "SIMULATED"
assert d["engine_metrics"]["live_testnet"]["source"] == "MEASURED"
row_source = "MEASURED" if d["engine_metrics"]["executions_source"] == "live_testnet" else "FIXTURE"
assert all(row["source"] == row_source for row in d["engine_metrics"]["executions"])
leaf = next(l for l in d["hierarchy"]["leaves"] if l["id"] == "leaf-bitcoin")
assert leaf["performance"]["live_testnet"]["source"] == "MEASURED"
assert leaf["performance"]["live_testnet"]["realized_pnl_usd"] is None
assert leaf["performance"]["paper_model"]["source"] == "SIMULATED"
assert leaf["active_positions_count"] is None
assert d["hierarchy"]["treasury"]["source"] in ("MEASURED", "BOOTSTRAP")
assert d["testnet_telemetry"]["source"] == "MEASURED"
assert all(drw["source"] in ("LLM", "DETERMINISTIC_FALLBACK", "BOOTSTRAP") for drw in d["cognitive_engine"]["palace_drawers"])
print("status payload provenance OK")
'` -> expected: `status payload provenance OK`.
- `curl -s -X POST http://localhost:8000/api/v1/openrouter/refill -H 'Content-Type: application/json' -d '{"force": true}'` -> expected on an install with no measured profit: HTTP 200 with `"status": "rejected_no_realized_profit"`, never a `TypeError`.
- Attach to the issue or PR: `evidence/status-payload.txt` (the curl output), `evidence/offline.png` (cold and degraded header), and `evidence/bootstrap-drawer.png` (a seeded drawer showing the `BOOTSTRAP` badge and `—` telemetry).

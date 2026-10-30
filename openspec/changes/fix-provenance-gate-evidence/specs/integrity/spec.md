# integrity Specification

## MODIFIED Requirements

### Requirement: Every performance payload declares its provenance

Every performance payload listed below MUST carry a `source` whose value is exactly one of `MEASURED`, `SIMULATED`, `FIXTURE`, or `BOOTSTRAP`.

| Payload | Required `source` |
|---|---|
| `engine_metrics.backtest_fixture` | `FIXTURE` |
| `engine_metrics.paper_model` | `SIMULATED` |
| `engine_metrics.live_testnet` | `MEASURED` |
| `engine_metrics.executions[]` | the enum mapped from `executions_source` |
| `leaf.performance.live_testnet` | `MEASURED` |
| `leaf.performance.paper_model` | `SIMULATED` |
| `leaf.last_rust_backtest` | `FIXTURE` |
| `POST /api/v1/leaf/{leaf_id}/backtest` summary | `FIXTURE` |
| `hierarchy.treasury` performance aggregate | `MEASURED` or `BOOTSTRAP` per the aggregate rule |
| `testnet_telemetry` | `MEASURED` |
| QuantAuditor `audit_latest_backtest` output | `FIXTURE` |

`engine_metrics.executions_source` MUST remain one of `backtest_fixture`, `paper_model`, or `live_testnet`, and every row in `engine_metrics.executions` MUST come from that one population, with a row `source` equal to the mapped enum (`FIXTURE`, `SIMULATED`, or `MEASURED`). Fixture and live rows MUST NOT be interleaved. The free-text description currently held in `engine_metrics.*.source` MUST move to `source_detail`; replacing it with an enum is a **BREAKING** type change. A performance number outside the table MUST either declare a source or be `null`; an unattributed numeric performance value MUST NOT be served. The deprecated producer token `rust_leaf_backtest` MUST NOT appear in production backend modules (`backend/core`, `backend/agents`, `backend/server.py`), and the deprecated telemetry fields `simulated_model_pnl_usd` and `solana_onchain_pnl_sol` MUST NOT appear in `backend/core/state_store.py`.

#### Scenario: Engine populations and executions map to enum sources

- **WHEN** a client sends `GET /api/v1/status`
- **THEN** `engine_metrics.backtest_fixture.source` is `FIXTURE`, `paper_model.source` is `SIMULATED`, and `live_testnet.source` is `MEASURED`
- **THEN** every row in `engine_metrics.executions` carries the enum mapped from `executions_source`

#### Scenario: Fixture execution fallback is labelled

- **WHEN** no live execution rows exist and `engine_metrics.executions` is populated from the fixture backtest
- **THEN** `executions_source` equals `backtest_fixture`
- **THEN** every execution row carries `source` equal to `FIXTURE`
- **THEN** no row carries `MEASURED`

#### Scenario: Leaf backtest surfaces are labelled

- **WHEN** `leaf.last_rust_backtest` is populated, or `POST /api/v1/leaf/{leaf_id}/backtest` returns a summary
- **THEN** the payload carries `source` equal to `FIXTURE`
- **THEN** its Sharpe, win rate, and net profit remain numeric because they are attributed, not nulled

#### Scenario: Testnet telemetry and auditor are labelled

- **WHEN** the status snapshot includes `testnet_telemetry`, or `QuantAuditorAgent.audit_latest_backtest` returns a result
- **THEN** `testnet_telemetry` carries `source` equal to `MEASURED`
- **THEN** the auditor output carries `source` equal to `FIXTURE`
- **THEN** its verdict is presented as a fixture verdict, not a live-edge verdict

#### Scenario: Free text moves to source detail

- **WHEN** a client reads `engine_metrics.backtest_fixture`
- **THEN** `source` is the enum `FIXTURE`
- **THEN** the former descriptive string is available as `source_detail`

#### Scenario: Unattributed numeric performance is not served

- **WHEN** a performance payload has no recognizable source
- **THEN** its performance values are served as `null`
- **THEN** its `source` is `null` and it is not readable as `MEASURED`, `SIMULATED`, or `FIXTURE`

#### Scenario: Production modules exclude deprecated producer tokens

- **WHEN** production backend modules (`backend/core`, `backend/agents`, `backend/server.py`) are scanned
- **THEN** the token `rust_leaf_backtest` is absent from all code and comments

#### Scenario: State store excludes deprecated telemetry fields

- **WHEN** `backend/core/state_store.py` and the telemetry payload are inspected
- **THEN** neither `simulated_model_pnl_usd` nor `solana_onchain_pnl_sol` is present

#### Scenario: Recursive payload walk rejects unattributed numeric performance

- **WHEN** the entire `/api/v1/status` JSON response is traversed recursively
- **THEN** every numeric performance field belongs to a block declaring a valid enum source
- **THEN** no unattributed numeric performance value exists anywhere in the payload hierarchy

### Requirement: Palace drawers declare provenance

Every Palace drawer served through `GET /api/v1/status` — at `hierarchy.master_orchestrator.palace_drawers`, `hierarchy.leaves[].palace_drawers`, `hierarchy.leaves[].mempalace_drawers`, and `cognitive_engine.palace_drawers` — MUST carry a `source` whose value is exactly one of `LLM`, `DETERMINISTIC_FALLBACK`, or `BOOTSTRAP`. The value MUST survive an append/read round-trip through the JSONL log and the Redis mirror. A drawer persisted before this change without a `source` field MUST be read back as `BOOTSTRAP`, with an empty `model_used`, `tokens_used` equal to `0`, and `cost_usd` equal to `0`, and MUST be excluded from continuity injection.

#### Scenario: Every REST drawer declares a source

- **WHEN** a client reads the Master drawer list, a leaf drawer list, or the cognitive engine drawer list
- **THEN** every drawer carries a `source` equal to `LLM`, `DETERMINISTIC_FALLBACK`, or `BOOTSTRAP`
- **THEN** no drawer is returned with an absent `source`

#### Scenario: Drawer source survives persistence

- **WHEN** a `BOOTSTRAP` drawer is appended and the Palace is reloaded from its JSONL log independently and from its Redis mirror
- **THEN** the reloaded drawer still has `source` equal to `BOOTSTRAP`

#### Scenario: Legacy untyped drawer is read as bootstrap

- **WHEN** the Palace loads a JSONL line written before this change that has no `source` field
- **THEN** the drawer is served with `source` equal to `BOOTSTRAP`
- **THEN** its `model_used` is empty and its `tokens_used` and `cost_usd` are `0`

#### Scenario: Pre-change LLM thesis loses continuity injection

- **WHEN** an upgraded install has a genuine pre-change LLM drawer in a wing and no post-change `LLM` drawer
- **THEN** that drawer is not injected into the continuity prompt
- **THEN** the prompt reports that no previous thesis is recorded, even though the legacy drawer remains visible with a `BOOTSTRAP` badge

### Requirement: Bootstrap drawers carry no LLM telemetry and no prior-thesis claim

A drawer whose `source` is `BOOTSTRAP` MUST have an empty `model_used`, `tokens_used` equal to `0`, and `cost_usd` equal to `0`. Its `thesis_continuity` MUST be `INITIAL` and MUST NOT be `CONFIRMED`, `REFINED`, or `INVALIDATED`. The continuity prompt and the cross-wing digest used to build the Master prompt MUST exclude `BOOTSTRAP` drawers, so a first-cycle prompt contains no prior thesis it never wrote. Only `LLM` and `DETERMINISTIC_FALLBACK` drawers are eligible for continuity injection, and the ADR-0002 depth-profile drawer counts are maxima, filled only by eligible drawers; ADR-0002 MUST be amended to record this rule.

#### Scenario: Seeded drawer carries no model telemetry

- **WHEN** the hierarchy seeds its initial Palace drawers on a fresh install
- **THEN** each seeded drawer has `source` equal to `BOOTSTRAP`
- **THEN** each has an empty `model_used`, `tokens_used` equal to `0`, and `cost_usd` equal to `0`

#### Scenario: Seeded drawer claims no prior confirmation

- **WHEN** a seeded drawer is inspected
- **THEN** its `thesis_continuity` equals `INITIAL`
- **THEN** it is not `CONFIRMED`, `REFINED`, or `INVALIDATED`

#### Scenario: Bootstrap drawers are absent from the continuity prompt

- **WHEN** the continuity prompt is built on a fresh install where only `BOOTSTRAP` drawers exist
- **THEN** the prompt contains none of their `hypothesis`, `panorama_summary`, or `ta_confluence_notes` text
- **THEN** the prompt reports that no previous thesis is recorded

#### Scenario: Bootstrap drawers are absent from the cross-wing digest

- **WHEN** the cross-wing digest is built while the leaf wings contain only `BOOTSTRAP` drawers
- **THEN** the digest contains no `BOOTSTRAP` drawer hypothesis
- **THEN** the digest does not attribute a model to any bootstrap entry

### Requirement: UI renders absent metrics as an em dash with provenance

Each component below MUST render a `null`, `undefined`, or absent performance value as `—` (U+2014) and MUST NOT coerce it to `0`, `+$0.00`, `0.0%`, or any plausible number. Every rendered metric block MUST display its `source` label beside the value.

- `LeafAgentView`: the leaf PnL/Sharpe/win-rate tile, the Rust backtest panel, and the execution rows.
- `MasterOverview`: the total-capital, deployed/active-leaf, dry-powder, and OpenRouter-credit tiles; the leaf-table PnL/Sharpe column; the drawer list.
- `Dashboard`: the `backtest_fixture`, `paper_model`, and `live_testnet` tiles; the testnet CEX PnL tile; the execution-table PnL columns.

A block with `source` equal to `null`, `undefined`, or any token outside the known provenance vocabulary MUST render `—` and an `UNATTRIBUTED` badge. A block with `source` equal to `BOOTSTRAP` MUST render all-null values as `—` with a `BOOTSTRAP` badge, which MUST be distinguishable from the `UNATTRIBUTED` badge.

#### Scenario: Leaf view renders an em dash for null metrics

- **WHEN** a leaf has `null` realized PnL, Sharpe, win rate, or position count
- **THEN** the leaf view renders `—` for each of those metrics
- **THEN** it renders neither `0`, `+$0.00`, `0.0%`, nor `2.45` / `64.5`

#### Scenario: Master table renders an em dash per null leaf

- **WHEN** a row in the Master leaf table has `null` realized PnL or `null` Sharpe
- **THEN** the row renders `—` in place of each null value
- **THEN** no leaf row displays `SR 2.45` or a numeric PnL derived from allocation

#### Scenario: Master aggregate renders an em dash when null

- **WHEN** `treasury.total_realized_pnl_usd` is `null`
- **THEN** the treasury tile renders `—`
- **THEN** it does not render `+$0.00`

#### Scenario: Dashboard tiles render an em dash for null populations

- **WHEN** a dashboard population tile or the testnet CEX PnL tile has a `null` value
- **THEN** the tile renders `—`
- **THEN** `Dashboard` does not coerce it with `|| 0` and does not display `0.00`

#### Scenario: Attributed provenance badge is visible

- **WHEN** a metric block is rendered with `source` equal to `MEASURED`, `SIMULATED`, or `FIXTURE`
- **THEN** the corresponding label is visible beside the value

#### Scenario: Bootstrap block renders an em dash with a bootstrap badge

- **WHEN** a metric block is rendered with `source` equal to `BOOTSTRAP`
- **THEN** every value renders as `—`
- **THEN** the `BOOTSTRAP` badge is visible and differs from the `UNATTRIBUTED` badge

#### Scenario: Unattributed block renders an em dash with an unattributed badge

- **WHEN** a metric block is rendered with `source` equal to `null` or an unknown token outside the provenance vocabulary
- **THEN** every value renders as `—`
- **THEN** the `UNATTRIBUTED` badge is visible

### Requirement: Offline UI state invents no portfolio and replaces stale values

The UI fallback state used before any successful backend poll MUST contain no invented portfolio: `total_capital_usd`, `deployed_capital_usd`, `dry_powder_usd`, and `dry_powder_ratio` MUST be `0` or `null`. It MUST NOT contain `25000`, `19200`, `5800`, or `0.232`. When a treasury, active-leaf, or OpenRouter field is absent, the UI MUST render `—` instead of a default; the active-leaf count MUST NOT default to `11` and the OpenRouter balance MUST NOT default to `24.5`. When a poll fails after a successful poll, the UI MUST display an `OFFLINE` badge stating the timestamp of the last successful poll, MUST render `—` for every performance and treasury figure, and MUST NOT render the retained values.

#### Scenario: Cold offline render shows no model portfolio

- **WHEN** the application loads with the backend unreachable and no prior successful poll
- **THEN** the treasury header shows `0` or `—` for total capital, deployed capital, dry powder, and dry-powder ratio
- **THEN** no tile displays `$25,000`, `$19,200`, `$5,800`, or `23.2%`

#### Scenario: Missing active-leaf count renders as unknown

- **WHEN** `active_leaves_count` is absent from the treasury payload
- **THEN** the Master header renders `—` for the active-leaf count
- **THEN** it does not render `11`

#### Scenario: Missing OpenRouter balance renders as unknown

- **WHEN** `openrouter_credit.credit_balance_usd` is absent or `null`
- **THEN** the OpenRouter tile renders `—`
- **THEN** it does not render `$24.50`

#### Scenario: Failed poll replaces retained values with an em dash

- **WHEN** the backend becomes unreachable after at least one successful poll
- **THEN** the `OFFLINE` badge is visible with the last-success timestamp
- **THEN** every performance and treasury figure renders `—`
- **THEN** no retained numeric value remains on screen

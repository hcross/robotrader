# integrity Specification

## Purpose
TBD - created by archiving change fix-fabricated-metrics. Update Purpose after archive.
## Requirements
### Requirement: Leaf live performance requires execution evidence

A leaf's `performance.live_testnet.realized_pnl_usd`, `win_rate_pct`, and `sharpe_ratio` MUST be `null` unless that leaf has execution rows attributed to it from the `live_testnet` population. In this change the only attributed leaf is `leaf-solana`, because the persisted execution ledger is filtered to Solana-ecosystem symbols at load; the other 25 leaves therefore report `null` live performance even when the global ledger is non-empty. A non-null value MUST be computed from the attributed rows and MUST NOT be a constant, an allocation-derived formula, or a default. Capital allocation, deposits, and posture changes MUST NOT create or modify a performance value. A statistic with no defined value for the available sample — a Sharpe ratio over fewer than two returns — MUST be `null`.

#### Scenario: Leaf with no attributed executions reports null live metrics

- **WHEN** `leaf-bitcoin` has no execution rows attributed to it and the status snapshot is built
- **THEN** its `performance.live_testnet.realized_pnl_usd`, `win_rate_pct`, and `sharpe_ratio` are all `null`

#### Scenario: Only solana is attributed from the ledger

- **WHEN** the global `live_testnet` ledger contains Solana-ecosystem rows
- **THEN** `leaf-solana` derives live metrics from those rows
- **THEN** every other leaf reports `null` live metrics

#### Scenario: Deposit does not synthesize live performance

- **WHEN** an operator deposits funds and a leaf's `allocated_capital_usd` increases while the leaf still has no attributed execution rows
- **THEN** the leaf's live performance fields remain `null`
- **THEN** no field changes value as a function of the allocation amount

#### Scenario: Measured live metrics derive from attributed rows

- **WHEN** `leaf-solana` has at least two attributed `live_testnet` rows with non-null `realized_pnl_usd`
- **THEN** its `realized_pnl_usd` equals the sum of those rows
- **THEN** its `win_rate_pct` equals `100 * wins / trades` computed on those rows
- **THEN** its `sharpe_ratio` is computed from those rows and is not `2.45`

#### Scenario: Undefined statistic is null

- **WHEN** `leaf-solana` has exactly one attributed execution row
- **THEN** its realized PnL and win rate are computed from that row
- **THEN** its `sharpe_ratio` is `null` because a single return has no defined standard deviation

### Requirement: Leaf paper performance and position count derive only from declared evidence

A leaf's `performance.paper_model.paper_pnl_usd` and `win_rate_pct` MUST equal the `paper_model` population's cumulative PnL and lifetime win rate for `leaf-solana`, and MUST be `null` for every other leaf. The paper `sharpe_ratio` MUST be `null` because the paper population records no Sharpe. `active_positions_count` MUST be `null` for every leaf because no position ledger exists; seeding, allocation, deposit, and liquidation MUST NOT substitute a numeric count.

#### Scenario: Paper metrics derive from the paper population

- **WHEN** the `paper_model` population reports a cumulative PnL and a lifetime win rate for `leaf-solana`
- **THEN** `leaf-solana.performance.paper_model.paper_pnl_usd` equals that cumulative PnL
- **THEN** its paper `win_rate_pct` equals that lifetime win rate
- **THEN** its paper `sharpe_ratio` is `null`

#### Scenario: Non-solana leaves report null paper metrics

- **WHEN** `leaf-bitcoin` has no `paper_model` attribution
- **THEN** its paper `paper_pnl_usd`, `win_rate_pct`, and `sharpe_ratio` are all `null`

#### Scenario: Position count is never synthesized

- **WHEN** a leaf is allocated capital on a fresh install, and again after an emergency liquidation
- **THEN** its `active_positions_count` is `null` in both states
- **THEN** it is never `2`, `1`, or `0`

### Requirement: Leaf performance blocks are split by population

The leaf block MUST expose two performance sub-blocks, `performance.live_testnet` and `performance.paper_model`, and each MUST carry its own `source`. The live sub-block MUST declare `MEASURED` and the paper sub-block MUST declare `SIMULATED`, including when all their values are `null` because the population has no rows. A flat performance key, if retained, MUST mirror exactly one sub-block and inherit that sub-block's `source`; it MUST NOT be served as an unattributed value. `BOOTSTRAP` MUST NOT be used for a live or paper sub-block, and `source` MUST NOT be `null` for a sub-block whose population is known.

#### Scenario: Each sub-block declares its own source

- **WHEN** `leaf-solana` reports both live and paper performance
- **THEN** `performance.live_testnet.source` equals `MEASURED`
- **THEN** `performance.paper_model.source` equals `SIMULATED`
- **THEN** no single block-level source describes both populations

#### Scenario: Empty population keeps its population source

- **WHEN** `leaf-bitcoin` has zero rows in both populations
- **THEN** `performance.live_testnet.source` equals `MEASURED` with all values `null`
- **THEN** `performance.paper_model.source` equals `SIMULATED` with all values `null`
- **THEN** neither source is `BOOTSTRAP` or `null`

#### Scenario: Flat mirror inherits the sub-block source

- **WHEN** a flat key such as `realized_pnl_usd` is retained on the leaf block
- **THEN** it equals the value of exactly one sub-block field
- **THEN** any provenance attached to it equals that sub-block's `source`

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

`engine_metrics.executions_source` MUST remain one of `backtest_fixture`, `paper_model`, or `live_testnet`, and every row in `engine_metrics.executions` MUST come from that one population, with a row `source` equal to the mapped enum (`FIXTURE`, `SIMULATED`, or `MEASURED`). Fixture and live rows MUST NOT be interleaved. The free-text description currently held in `engine_metrics.*.source` MUST move to `source_detail`; replacing it with an enum is a **BREAKING** type change. A performance number outside the table MUST either declare a source or be `null`; an unattributed numeric performance value MUST NOT be served.

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

### Requirement: Master aggregate derives only from declared evidence

`treasury.total_realized_pnl_usd` MUST equal the sum of the non-null `realized_pnl_usd` values of leaves whose live sub-block is `MEASURED`, and MUST be `null` when no leaf has measured realized PnL. The treasury performance aggregate MUST declare `source` equal to `MEASURED` when the aggregate is non-null and `BOOTSTRAP` when it is `null`; it MUST NOT declare `source` as `null`. The aggregate MUST NOT include a simulated or fixture value, and MUST NOT be synthesized from allocation weights.

#### Scenario: No measured evidence yields a null aggregate

- **WHEN** every leaf has `realized_pnl_usd` equal to `null`
- **THEN** `treasury.total_realized_pnl_usd` is `null`
- **THEN** `treasury.source` equals `BOOTSTRAP`

#### Scenario: Aggregate sums measured values only

- **WHEN** one leaf reports measured realized PnL of `10.00`, another reports measured `-4.00`, and a third reports only simulated paper PnL of `100.00`
- **THEN** `treasury.total_realized_pnl_usd` equals `6.00`
- **THEN** `treasury.source` equals `MEASURED`

#### Scenario: Treasury source reflects the aggregate state

- **WHEN** the aggregate changes from a null state to a measured non-null state
- **THEN** `treasury.source` changes from `BOOTSTRAP` to `MEASURED`
- **THEN** it is never `null` and never carries a population it did not aggregate

#### Scenario: Allocation does not resurrect a removed constant

- **WHEN** all leaves are fully allocated but none has execution evidence
- **THEN** `treasury.total_realized_pnl_usd` is `null`
- **THEN** it does not equal `1.8%` of deployed capital or any other allocation-derived value

### Requirement: Persisted leaf performance is not rehydrated

On construction, the hierarchy MUST ignore any persisted `realized_pnl_usd`, `paper_pnl_usd`, `sharpe_ratio`, `win_rate_pct`, or `active_positions_count` value, and MUST recompute performance from execution evidence only. The persist path MUST NOT write those performance keys. Allocation, weight, posture, enabled state, objective summary, thesis, and deposit/checkout history MAY still persist.

#### Scenario: Legacy persisted performance is ignored on load

- **WHEN** Redis holds leaf performance values written before this change — for example `realized_pnl_usd = 999`, `paper_pnl_usd = 888`, and `active_positions_count = 2`
- **THEN** after loading, `leaf-solana` reports only values derived from its execution rows
- **THEN** every non-Solana leaf reports `null` performance
- **THEN** no leaf reports `999`, `888`, or `2`

#### Scenario: Persisted payload no longer carries performance keys

- **WHEN** the hierarchy persists its state after this change
- **THEN** the persisted leaf objects contain no `realized_pnl_usd`, `paper_pnl_usd`, `sharpe_ratio`, `win_rate_pct`, or `active_positions_count`
- **THEN** allocation, weight, posture, and enabled state are still persisted

### Requirement: Palace drawers declare provenance

Every Palace drawer served through `GET /api/v1/status` — at `hierarchy.master_orchestrator.palace_drawers`, `hierarchy.leaves[].palace_drawers`, `hierarchy.leaves[].mempalace_drawers`, and `cognitive_engine.palace_drawers` — MUST carry a `source` whose value is exactly one of `LLM`, `DETERMINISTIC_FALLBACK`, or `BOOTSTRAP`. The value MUST survive an append/read round-trip through the JSONL log and the Redis mirror. A drawer persisted before this change without a `source` field MUST be read back as `BOOTSTRAP`, with an empty `model_used`, `tokens_used` equal to `0`, and `cost_usd` equal to `0`, and MUST be excluded from continuity injection.

#### Scenario: Every REST drawer declares a source

- **WHEN** a client reads the Master drawer list, a leaf drawer list, or the cognitive engine drawer list
- **THEN** every drawer carries a `source` equal to `LLM`, `DETERMINISTIC_FALLBACK`, or `BOOTSTRAP`
- **THEN** no drawer is returned with an absent `source`

#### Scenario: Drawer source survives persistence

- **WHEN** a `BOOTSTRAP` drawer is appended and the Palace is reloaded from its JSONL log and its Redis mirror
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

### Requirement: Deterministic fallback drawers claim no unfounded continuity

A drawer whose `source` is `DETERMINISTIC_FALLBACK` MUST set `thesis_continuity` to `INITIAL` unless the same wing already contains at least one `LLM` drawer. When an `LLM` drawer exists in that wing, the fallback MAY carry that drawer's continuity state and MUST NOT escalate it beyond that state. When no model call was attempted, the drawer MUST have an empty `model_used`, `tokens_used` equal to `0`, and `cost_usd` equal to `0`; when a model call was attempted and billed, it MUST report that call's recorded usage and MUST NOT inherit telemetry from another drawer.

#### Scenario: Fallback on a fresh install claims no confirmation

- **WHEN** a wing contains only `BOOTSTRAP` drawers and the LLM call fails, producing a `DETERMINISTIC_FALLBACK` drawer
- **THEN** its `thesis_continuity` equals `INITIAL`
- **THEN** it is not `CONFIRMED`

#### Scenario: Fallback with a prior LLM drawer carries its continuity

- **WHEN** the same wing contains one `LLM` drawer with continuity `CONFIRMED` and a fallback is produced
- **THEN** the fallback's `thesis_continuity` is `CONFIRMED` or less, never `REFINED` or `INVALIDATED` without a corresponding LLM drawer

#### Scenario: Fallback without a model call carries no telemetry

- **WHEN** a `DETERMINISTIC_FALLBACK` drawer is produced without any attempted model call
- **THEN** its `model_used` is empty, `tokens_used` is `0`, and `cost_usd` is `0`

### Requirement: Refill gating consumes null-safe measured PnL only

The OpenRouter refill callers — `POST /api/v1/openrouter/refill` and the Master reflection — MUST sum only non-null `MEASURED` leaf `realized_pnl_usd` values, MUST treat a `null` as no contribution, and MUST NOT pass a `null` to a numeric conversion. They MUST NOT add the simulated `paper_model` `live_pnl_usd`. The measured total passed to the profit gate MUST be the actual sum, including `0.0` when no measured profit exists; the `max(125.0, …)` floor MUST NOT be applied. The remaining `CostGuard` defects tracked in issue #5 — the automatic path bypass, the unused Rust validator, the balance source, daily rollover, and the low-watermark constants — are out of scope.

#### Scenario: Null leaf PnL does not raise in the refill path

- **WHEN** a fresh install has every leaf `realized_pnl_usd` equal to `null` and a client calls `POST /api/v1/openrouter/refill`
- **THEN** the endpoint returns a structured response and does not raise `TypeError`
- **THEN** the measured total passed to the gate is `0.0`

#### Scenario: Refill sum excludes simulated PnL

- **WHEN** measured leaf PnL is `10.00` and simulated paper PnL is `100.00`
- **THEN** the profit gate receives `10.00`, not `110.00`

#### Scenario: No fabricated profit floor

- **WHEN** measured realized PnL is `0.00` and a refill is requested
- **THEN** the gate receives `0.00` and rejects with `rejected_no_realized_profit`
- **THEN** it does not receive `125.0` and does not authorise a `$12.50` refill

#### Scenario: Negative measured profit is rejected

- **WHEN** measured realized PnL is `-4.00`
- **THEN** the gate rejects the refill and reports the negative measured value
- **THEN** no floor replaces it

### Requirement: UI renders absent metrics as an em dash with provenance

Each component below MUST render a `null`, `undefined`, or absent performance value as `—` (U+2014) and MUST NOT coerce it to `0`, `+$0.00`, `0.0%`, or any plausible number. Every rendered metric block MUST display its `source` label beside the value.

- `LeafAgentView`: the leaf PnL/Sharpe/win-rate tile, the Rust backtest panel, and the execution rows.
- `MasterOverview`: the total-capital, deployed/active-leaf, dry-powder, and OpenRouter-credit tiles; the leaf-table PnL/Sharpe column; the drawer list.
- `Dashboard`: the `backtest_fixture`, `paper_model`, and `live_testnet` tiles; the testnet CEX PnL tile; the execution-table PnL columns.

A block with `source` equal to `null` MUST render `—` and an `UNATTRIBUTED` badge. A block with `source` equal to `BOOTSTRAP` MUST render all-null values as `—` with a `BOOTSTRAP` badge, which MUST be distinguishable from the `UNATTRIBUTED` badge.

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

- **WHEN** a metric block is rendered with `source` equal to `null`
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

### Requirement: API substitutes no plausible default

Backend snapshot builders MUST NOT substitute a numeric default for an absent value. When the cost status carries no OpenRouter balance, the snapshot MUST expose `credit_balance_usd` as `null` and MUST NOT synthesize `24.5`. When the active-leaf count cannot be computed, the snapshot MUST expose it as `null` and MUST NOT synthesize `11`. A measured zero MUST remain `0`, distinct from an absent value.

#### Scenario: Missing credit balance is null

- **WHEN** the cost status carries no `credit_balance_usd` or `balance_usd`
- **THEN** the status snapshot exposes `openrouter_credit.credit_balance_usd` as `null`
- **THEN** it does not expose `24.5`

#### Scenario: Missing active-leaf count is null

- **WHEN** the hierarchy snapshot cannot compute an active-leaf count
- **THEN** `treasury.active_leaves_count` is `null`
- **THEN** it is not `11`

#### Scenario: Measured zero stays zero

- **WHEN** the cost status reports a measured balance of `0.0`
- **THEN** the snapshot exposes `credit_balance_usd` equal to `0.0`
- **THEN** the UI renders `$0.00`, not `—`

### Requirement: Audit document separates fixture from measured

In `docs/PERFORMANCE_AND_COST_AUDIT.md`, a figure block is any table row, bullet item, or paragraph that states at least one numeric performance value. Every figure block MUST carry its population and source label: `backtest_fixture` as `FIXTURE`, `paper_model` as `SIMULATED`, and `live_testnet` as `MEASURED`. Fixture and simulated figures MUST NOT be presented as product performance, realized returns, or live trading results. The document MUST state that the live-testnet figures are the only measured results, and MUST NOT attribute a Sharpe ratio or PnL to live trading unless it derives from live-testnet execution evidence.

#### Scenario: Every figure block carries its population and source

- **WHEN** a reader scans the performance sections of the document
- **THEN** every table row, bullet, and paragraph stating a numeric performance value carries or is grouped under its population and `FIXTURE`, `SIMULATED`, or `MEASURED` label

#### Scenario: Fixture figures are not presented as product performance

- **WHEN** a reader reads the fixture section, including the Sharpe ratio and net PnL figures present in the document at the reviewed SHA
- **THEN** those figures are labelled `FIXTURE`
- **THEN** they are not described as realized, live, or product performance

#### Scenario: Paper figures are labelled simulated

- **WHEN** a reader reads the paper-model section
- **THEN** every figure block is labelled `SIMULATED`
- **THEN** the cumulative paper PnL is not described as realized or live profit

#### Scenario: Live figures are labelled measured

- **WHEN** a reader reads the live-testnet section
- **THEN** every figure block is labelled `MEASURED`
- **THEN** the CEX testnet PnL is identified as measured

#### Scenario: Executive summary makes no measured claim from a fixture

- **WHEN** a reader reads the executive summary
- **THEN** no fixture or simulated figure is described as measured, as product performance, or as a realized return
- **THEN** the summary states that the live-testnet figures are the only measured results


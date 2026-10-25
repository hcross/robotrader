## ADDED Requirements

### Requirement: Leaf performance requires execution evidence

A leaf agent's performance fields — `sharpe_ratio`, `win_rate_pct`, `realized_pnl_usd`, `paper_pnl_usd`, and `active_positions_count` — MUST be `null` when that leaf has no execution evidence in the population the field reports on. A non-null value MUST be computed from the leaf's own execution rows and MUST NOT be a constant, an allocation-derived formula, or a default. Capital allocation, deposits, and posture changes MUST NOT create or modify a performance value. A statistic that has no defined value for the available sample — a Sharpe ratio over fewer than two returns — MUST be `null`.

#### Scenario: Leaf with no executions reports null metrics

- **WHEN** a leaf has zero execution rows in both the `live_testnet` and `paper_model` populations and the status snapshot is built
- **THEN** that leaf's `sharpe_ratio`, `win_rate_pct`, `realized_pnl_usd`, `paper_pnl_usd`, and `active_positions_count` are all `null`

#### Scenario: Allocation and deposit do not synthesize performance

- **WHEN** an operator deposits funds and the leaf's `allocated_capital_usd` increases while the leaf still has zero execution rows
- **THEN** the leaf's performance fields remain `null`
- **THEN** no field changes value as a function of the allocation amount

#### Scenario: Measured metrics derive from the leaf's own rows

- **WHEN** a leaf has at least two measured `live_testnet` execution rows with non-null `realized_pnl_usd`
- **THEN** the leaf's `realized_pnl_usd` equals the sum of those rows
- **THEN** the leaf's `win_rate_pct` equals `100 * wins / trades` computed on those rows
- **THEN** two leaves with different execution rows report different values

#### Scenario: Undefined statistic is null, not fabricated

- **WHEN** a leaf has exactly one execution row
- **THEN** its realized PnL and win rate are computed from that row
- **THEN** its `sharpe_ratio` is `null` because a single return has no defined standard deviation

### Requirement: Every metric block declares its provenance

Every performance metric block exposed by the backend — each of the three `engine_metrics` populations, each leaf performance block, and the Master treasury performance block — MUST carry a `source` field whose value is exactly one of `MEASURED`, `SIMULATED`, `FIXTURE`, or `BOOTSTRAP`. The three engine populations MUST declare `FIXTURE`, `SIMULATED`, and `MEASURED` respectively. A block whose `source` is absent, empty, or outside that set MUST NOT be presented as a performance block: its performance fields MUST be `null` and its `source` MUST be `null` (unattributed). A block whose `source` is `BOOTSTRAP` MUST report every performance value as `null`.

#### Scenario: Engine populations declare their provenance

- **WHEN** a client sends `GET /api/v1/status`
- **THEN** `engine_metrics.backtest_fixture.source` equals `FIXTURE`
- **THEN** `engine_metrics.paper_model.source` equals `SIMULATED`
- **THEN** `engine_metrics.live_testnet.source` equals `MEASURED`
- **THEN** every leaf performance block and the Master treasury performance block carries a `source` inside the allowed set

#### Scenario: Bootstrap block carries no numeric performance

- **WHEN** a metric block declares `source` equal to `BOOTSTRAP`
- **THEN** every performance value in that block is `null`
- **THEN** no Sharpe ratio, win rate, PnL, or position count is present as a number

#### Scenario: Unattributed block is not presented as measured

- **WHEN** an internal metric block has no `source` or an unrecognized one
- **THEN** the served block exposes `source` as `null` and its performance values as `null`
- **THEN** no consumer can read it as `MEASURED`, `SIMULATED`, or `FIXTURE`

### Requirement: Master aggregate derives only from declared evidence

`treasury.total_realized_pnl_usd` MUST equal the sum of the non-null `realized_pnl_usd` values of leaves whose performance block is `MEASURED`, and MUST be `null` when no leaf has measured realized PnL. The Master treasury performance block MUST declare `source` equal to `MEASURED`. The aggregate MUST NOT include a simulated or fixture value, and MUST NOT be synthesized from allocation weights when no measured value exists.

#### Scenario: No measured evidence yields a null aggregate

- **WHEN** every leaf has `realized_pnl_usd` equal to `null`
- **THEN** `treasury.total_realized_pnl_usd` is `null`
- **THEN** the UI renders the aggregate as `—`

#### Scenario: Aggregate sums measured values only

- **WHEN** one leaf reports measured realized PnL of `10.00`, another reports measured `-4.00`, and a third reports only simulated paper PnL of `100.00`
- **THEN** `treasury.total_realized_pnl_usd` equals `6.00`
- **THEN** `treasury.source` equals `MEASURED`

#### Scenario: Allocation does not resurrect a removed constant

- **WHEN** all leaves are fully allocated but none has execution evidence
- **THEN** `treasury.total_realized_pnl_usd` is `null`
- **THEN** it does not equal `1.8%` of deployed capital or any other allocation-derived value

### Requirement: Palace drawers declare provenance

Every Palace drawer — persisted to the JSONL log and Redis mirror and returned by the REST or WebSocket snapshot — MUST carry a `source` field whose value is exactly one of `LLM`, `DETERMINISTIC_FALLBACK`, or `BOOTSTRAP`. The value MUST survive an append/read round-trip through both persistence layers. A drawer persisted before this change without a `source` field MUST be read back as `BOOTSTRAP` and MUST NOT be attributed to a model.

#### Scenario: Every returned drawer declares an allowed source

- **WHEN** a client reads the Master or leaf drawer list from the status or cognitive snapshot
- **THEN** every drawer has a `source` whose value is `LLM`, `DETERMINISTIC_FALLBACK`, or `BOOTSTRAP`
- **THEN** no drawer is returned with an absent `source`

#### Scenario: Source survives persistence

- **WHEN** a `BOOTSTRAP` drawer is appended and the Palace is reloaded from its JSONL log and Redis mirror
- **THEN** the reloaded drawer still has `source` equal to `BOOTSTRAP`

#### Scenario: Legacy untyped drawer is not attributed to a model

- **WHEN** the Palace loads a JSONL line written before this change that has no `source` field
- **THEN** the drawer is served with `source` equal to `BOOTSTRAP`
- **THEN** its `model_used` is empty and its `tokens_used` and `cost_usd` are `0`

### Requirement: Bootstrap drawers carry no LLM telemetry

A drawer whose `source` is `BOOTSTRAP` MUST have an empty `model_used`, `tokens_used` equal to `0`, and `cost_usd` equal to `0`. It MUST NOT assert thesis continuity `CONFIRMED`, `REFINED`, or `INVALIDATED`; its continuity MUST be `INITIAL`. The continuity prompt and the cross-wing digest used to build the Master prompt MUST exclude `BOOTSTRAP` drawers, so a first-cycle Master prompt contains no prior thesis it never wrote.

#### Scenario: Seeded drawer carries no model telemetry

- **WHEN** the hierarchy seeds its initial Palace drawers on a fresh install
- **THEN** each seeded drawer has `source` equal to `BOOTSTRAP`
- **THEN** each seeded drawer has an empty `model_used`, `tokens_used` equal to `0`, and `cost_usd` equal to `0`

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

`LeafAgentView`, `MasterOverview` (aggregate and leaf table), and every other metric tile MUST render a `null`, `undefined`, or absent performance value as `—` (U+2014). They MUST NOT coerce it to `0`, `+$0.00`, `0.0%`, or any plausible number. Every rendered metric block MUST display its `source` label next to the value. A block with `source` equal to `null` MUST render `—` and an `UNATTRIBUTED` badge instead of a value.

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

#### Scenario: Provenance badge is visible and unattributed is explicit

- **WHEN** a metric block is rendered with `source` equal to `MEASURED`, `SIMULATED`, `FIXTURE`, or `BOOTSTRAP`
- **THEN** the corresponding label is visible beside the value
- **WHEN** the `source` is `null`
- **THEN** the value renders as `—` with an `UNATTRIBUTED` badge

### Requirement: Offline UI state invents no portfolio

The UI fallback state used before any successful backend poll MUST contain no invented portfolio: `total_capital_usd`, `deployed_capital_usd`, `dry_powder_usd`, and `dry_powder_ratio` MUST be `0` or `null`. It MUST NOT contain `25000`, `19200`, `5800`, or `0.232`. When a treasury, active-leaf, or OpenRouter field is absent, the UI MUST render `—` instead of a default; the active-leaf count MUST NOT default to `11` and the OpenRouter balance MUST NOT default to `24.5`. While the backend is unreachable, the offline indicator MUST be visible and retained prior values MUST NOT be presented as current measurements.

#### Scenario: Cold offline render shows no model portfolio

- **WHEN** the application loads with the backend unreachable and no prior successful poll
- **THEN** the treasury header shows `0` or `—` for total capital, deployed capital, dry powder, and dry-powder ratio
- **THEN** no tile displays `$25,000`, `$19,200`, `$5,800`, or `23.2%`

#### Scenario: Missing active-leaf count renders as unknown

- **WHEN** `active_leaves_count` is absent from the treasury payload
- **THEN** the Master header renders `—` for the active-leaf count
- **THEN** it does not render `11`

#### Scenario: Missing OpenRouter balance renders as unknown

- **WHEN** `openrouter_credit.credit_balance_usd` is absent
- **THEN** the OpenRouter tile renders `—`
- **THEN** it does not render `$24.50`

#### Scenario: Offline indicator distinguishes retained values

- **WHEN** the backend becomes unreachable after at least one successful poll
- **THEN** the offline indicator is visible
- **THEN** any retained treasury or metric value is marked as not current and is not presented as a measurement

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

`docs/PERFORMANCE_AND_COST_AUDIT.md` MUST label every performance figure with its population and source: `backtest_fixture` figures as `FIXTURE`, `paper_model` figures as `SIMULATED`, and `live_testnet` figures as `MEASURED`. Fixture and simulated figures MUST NOT be presented as product performance, realized returns, or live trading results. The document MUST state that the live-testnet figures are the only measured results, and MUST NOT attribute a Sharpe ratio or PnL to live trading unless the figure derives from live-testnet execution evidence.

#### Scenario: Fixture section is labelled FIXTURE

- **WHEN** a reader opens the `backtest_fixture` performance section
- **THEN** every figure block in that section is labelled `FIXTURE`
- **THEN** the figures `28.22` Sharpe and `+$22.78` appear only inside a fixture context

#### Scenario: Paper section is labelled SIMULATED

- **WHEN** a reader opens the `paper_model` performance section
- **THEN** every figure block in that section is labelled `SIMULATED`
- **THEN** the `+$1,155.52` figure is not described as realized or live profit

#### Scenario: Live section is labelled MEASURED

- **WHEN** a reader opens the `live_testnet` performance section
- **THEN** every figure block in that section is labelled `MEASURED`
- **THEN** the `-$4.6036` CEX testnet figure is identified as measured

#### Scenario: Executive summary makes no measured claim from a fixture

- **WHEN** a reader reads the executive summary
- **THEN** no fixture or simulated figure is described as measured, as product performance, or as a realized return
- **THEN** the summary states that the live-testnet figures are the only measured results

## ADDED Requirements

### Requirement: The deterministic execution artefact declares a policy-sanity-check kind

Every summary produced by the deterministic execution path MUST carry three machine-readable fields: `artifact_kind` equal to the exact string `policy_sanity_check`, `source` equal to the exact string `FIXTURE`, and `fill_simulation` equal to the boolean `false`. The rule applies to the `robotrader-node` stdout JSON, the in-process `BacktestEngine` summary, `POST /api/v1/backtest/run`, `POST /api/v1/leaf/{leaf_id}/backtest`, `POST /api/v1/policy/regime`, `POST /api/v1/risk/kill`, `GET /api/v1/status` under `engine_metrics.backtest_fixture`, `GET /api/v1/hierarchy`, `leaf.last_rust_backtest`, and the QuantAuditor output. The legacy wire keys `backtest_fixture` and `last_rust_backtest`, and the `/backtest` route paths, MAY remain; they are identifiers, not human-facing artefact names. A payload that contains a deterministic summary without all three fields MUST NOT be served as a completed result.

#### Scenario: Node summary is a policy sanity check

- **WHEN** `robotrader-node --leaf-id <leaf>` completes for any of the 26 leaf identifiers
- **THEN** its stdout JSON carries `artifact_kind` equal to `policy_sanity_check`
- **THEN** it carries `source` equal to `FIXTURE`
- **THEN** it carries `fill_simulation` equal to `false`

#### Scenario: Every API surface propagates the kind

- **WHEN** a client reads `GET /api/v1/status`, `GET /api/v1/hierarchy`, `POST /api/v1/backtest/run`, `POST /api/v1/leaf/{leaf_id}/backtest`, `POST /api/v1/policy/regime`, or `POST /api/v1/risk/kill`, or invokes the QuantAuditor
- **THEN** every embedded deterministic summary carries the three fields with the specified values
- **THEN** `leaf.last_rust_backtest` carries the same three fields

#### Scenario: Fixture metrics remain numeric under the new kind

- **WHEN** the fixture summary is served with `artifact_kind` equal to `policy_sanity_check`
- **THEN** `net_profit_usd`, `sharpe_ratio`, `win_rate_pct`, `max_drawdown_pct`, and `total_trades` remain the fixture's numeric values
- **THEN** none of those values is nulled solely because the artefact is relabelled

### Requirement: No surface presents fixture PnL or Sharpe as backtest performance

Across the API payload, the UI, `README.md`, `AGENTS.md`, `docs/architecture.md`, and `docs/PERFORMANCE_AND_COST_AUDIT.md`, the fixture's PnL, Sharpe, win rate, drawdown, trade count, and per-pod attribution MUST be labelled as the output of a deterministic policy sanity check with source `FIXTURE`. No such surface SHALL describe those values as measured, realized, live, product, market, or backtest performance, as strategy edge, or as a validated return. The fixture MUST NOT be presented as satisfying ADR-0001's `Backtest == Paper == Live` target, because no fill simulation exists; the shared strategy-and-risk code path MAY still be described as a single deterministic path.

#### Scenario: Status payload does not claim performance

- **WHEN** `GET /api/v1/status` returns `engine_metrics.backtest_fixture`
- **THEN** the block carries `artifact_kind` equal to `policy_sanity_check`, `source` equal to `FIXTURE`, and `fill_simulation` equal to `false`
- **THEN** no field, `source_detail`, or verdict in that block describes its PnL or Sharpe as measured, realized, live, or backtest performance
- **THEN** `source_detail` states that the artefact is a synthetic deterministic rule and plumbing check, not a fill simulation

#### Scenario: UI fixture surfaces name the policy sanity check

- **WHEN** an operator views the dashboard fixture tile, the leaf replay result, or the per-pod attribution
- **THEN** the visible fixture label contains `Policy sanity check` and the `FIXTURE` badge
- **THEN** no fixture surface describes its PnL or Sharpe as backtest performance, realized PnL, or a measured result

#### Scenario: README and AGENTS do not claim measured backtest performance

- **WHEN** a reader reads `README.md` and `AGENTS.md`
- **THEN** neither document presents fixture PnL or Sharpe as product performance, a realized return, or a measured backtest result
- **THEN** the `backtest` crate description names the current artefact as a deterministic policy sanity check
- **THEN** any `Backtest == Paper == Live` or `Replay == Paper == Live` statement is qualified as an intended target not demonstrated by the current fixture, or is removed

#### Scenario: Architecture documentation does not claim an implemented historical replay

- **WHEN** a reader reads `docs/architecture.md`
- **THEN** it does not describe the current artefact as a Parquet/DuckDB historical replay engine producing Sharpe, Sortino, or drawdown performance
- **THEN** it names the current artefact as a deterministic policy sanity check and leaves the real replay engine to issue #3

#### Scenario: Audit document presents the fixture as a policy sanity check

- **WHEN** a reader reads §1 and §3.1 of `docs/PERFORMANCE_AND_COST_AUDIT.md`
- **THEN** every fixture figure block is labelled `policy_sanity_check` and `FIXTURE`
- **THEN** no fixture figure is described as backtest performance, measured, realized, or live
- **THEN** the live-testnet figures remain the only measured results in the document

### Requirement: The fixture is explicitly a rule and plumbing sanity check, not a fill simulation

Every description of the fixture, including the API `source_detail`, UI text, `README.md`, `AGENTS.md`, `docs/architecture.md`, and the audit, MUST state that it is a deterministic rule and plumbing sanity check. The same description MUST state that it is not a fill simulation, and MUST NOT claim L2 order-book replay, historical market ingest, queue position, fill probability, latency modelling, partial fills, adverse selection, or exit pricing from a later `MarketEvent`. The declared-edge arithmetic MAY be described as `notional × (expected_edge_bps − modelled round-trip fees − modelled spread)`, but MUST NOT be described as market-derived or realized.

#### Scenario: The description denies fill simulation

- **WHEN** a reader or client reads any fixture description
- **THEN** the description contains the phrases `policy sanity check` and `not a fill simulation`
- **THEN** it does not claim L2 replay, queue position, latency, fill probability, partial fill, adverse selection, or later-market-event exit pricing

#### Scenario: The PnL model is described as declared-edge arithmetic

- **WHEN** the fixture PnL is described in any surface
- **THEN** the description states that PnL derives from the intent's declared `expected_edge_bps` minus modelled fees and spread
- **THEN** the description does not state or imply that PnL derives from a market price path or a realized exit

#### Scenario: The shared strategy and risk code path is unchanged

- **WHEN** the change diff is inspected
- **THEN** `StrategyPod::on_market_event`, `HardRiskGate::validate`, the fixture event inputs, the pod edge formulas, and the declared `max_slippage_bps` values are unchanged
- **THEN** the same pod trait and risk gate process the fixture events with no live-only branch

### Requirement: Fixture acceptance asserts rule and plumbing invariants, not profitability

Automated tests for the fixture MUST assert determinism and rule/plumbing outcomes: the exact Solana and 26-leaf numeric baselines, trade and rejection counts, the SCAM-SOL `OnChainRugCheckFailed` rejection, the `InsufficientEdge` cost hurdle, the `<= 4` pods-per-chain bound, and the accounting identity between per-pod attribution and net profit. A test MUST NOT use a positive `net_profit_usd` or a Sharpe above a threshold as evidence that a pod has edge, quality, or health. The fixture's Sharpe MUST NOT be an acceptance criterion.

#### Scenario: A repeated run is byte-identical

- **WHEN** the fixture runs twice for the same leaf identifier and the same `PolicyEnvelope`
- **THEN** the two summaries are identical in every numeric field

#### Scenario: Rule outcomes remain asserted

- **WHEN** the fixture test suite runs
- **THEN** the Solana baseline reports 4 trades, 3 rejections, and 2 attributed pods
- **THEN** SCAM-SOL is rejected as `OnChainRugCheckFailed`
- **THEN** each leaf has between 1 and 4 pods inclusive
- **THEN** the sum of `pod_pnl_attribution` equals `net_profit_usd` within the fixture's floating-point tolerance

#### Scenario: Profitability is not an acceptance criterion

- **WHEN** the Rust and Python test suites are inspected
- **THEN** no test treats `net_profit_usd > 0` or a Sharpe threshold as proof of strategy edge, health, or quality
- **THEN** any exact PnL assertion is described as a fixture determinism baseline, not a performance target

### Requirement: Labels are consistent and no numeric baseline is silently re-derived

Every machine-readable surface MUST use `artifact_kind` equal to the exact value `policy_sanity_check` and `source` equal to the exact value `FIXTURE`. Every human-facing surface MUST use the phrase `Policy sanity check` and the `FIXTURE` badge. No synonym such as `sanity backtest`, `synthetic backtest`, `simulated backtest`, `paper`, or `measured` SHALL describe it. Legacy wire keys and route paths are exempt because they are identifiers, not human-facing artefact names. The change MUST NOT alter the fixture's event inputs, pod edge formulas, `max_slippage_bps` values, PnL arithmetic, Sharpe arithmetic, or any published numeric figure. The post-change `robotrader-node` JSON for every leaf MUST equal the pre-change JSON in every numeric field. A numeric difference is not accepted as a re-baseline unless the delta spec is amended; it MUST NOT be updated silently.

#### Scenario: One canonical pair is used

- **WHEN** the API, UI, tests, `README.md`, `AGENTS.md`, `docs/architecture.md`, and the audit are searched for fixture labels
- **THEN** every machine-readable fixture label is `policy_sanity_check` with source `FIXTURE`
- **THEN** every human-facing fixture label is `Policy sanity check` with the `FIXTURE` badge
- **THEN** no surface uses a different artefact name for the fixture

#### Scenario: Tests assert the canonical pair

- **WHEN** the Rust and Python suites run
- **THEN** they assert `artifact_kind` equal to `policy_sanity_check`, `source` equal to `FIXTURE`, and `fill_simulation` equal to `false` on every fixture payload
- **THEN** they assert the updated `source_detail` text that names the artefact a policy sanity check and denies fill simulation

#### Scenario: Numbers are unchanged

- **WHEN** the pre-change and post-change `robotrader-node --leaf-id <leaf>` JSON are compared for all 26 leaves
- **THEN** every numeric field is identical
- **THEN** every `[FIXTURE]` figure in the audit still matches the run output

#### Scenario: A numeric drift is explicit, never silent

- **WHEN** any fixture numeric field differs from the recorded baseline
- **THEN** the change evidence records the before and after value and the reason
- **THEN** the change is not merge-ready until the delta spec records the new baseline

### Requirement: Existing provenance and risk-hurdle contracts are preserved

The `MEASURED` / `SIMULATED` / `FIXTURE` / `BOOTSTRAP` enum, the `#7` provenance table, the fixture/live execution split, and the null-for-unattributed rule MUST remain unchanged. The `#4a` risk-hurdle contracts MUST remain unchanged: SCAM-SOL is rejected as `OnChainRugCheckFailed`, the hurdle is computed from the canonical cost model, the strict boundary holds, and the 26-leaf `<= 4` pod bound remains. No fixture or paper value SHALL enter the measured live population.

#### Scenario: The provenance enum and #7 labels are unchanged

- **WHEN** a client reads `GET /api/v1/status`
- **THEN** the four source enum values are unchanged
- **THEN** `engine_metrics.backtest_fixture.source` is `FIXTURE`, `paper_model.source` is `SIMULATED`, and `live_testnet.source` is `MEASURED`
- **THEN** fixture and live execution rows remain un-interleaved

#### Scenario: The anti-rug and edge-hurdle assertions remain green

- **WHEN** `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest` and `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` run
- **THEN** SCAM-SOL is rejected as `OnChainRugCheckFailed`
- **THEN** the `InsufficientEdge` boundary and venue-specific hurdle assertions pass
- **THEN** the 26-leaf exact baselines and the `<= 4` pod bound pass

#### Scenario: No fixture value enters the measured population

- **WHEN** population metrics and the treasury aggregate are assembled
- **THEN** the measured live PnL excludes fixture rows
- **THEN** no fixture PnL is summed into the treasury aggregate

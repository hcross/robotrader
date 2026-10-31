## ADDED Requirements

### Requirement: Leaf execution mode and scheduling classification

Every leaf status object returned by `HierarchicalFleetManager` — including in `GET /api/v1/hierarchy/overview`, `GET /api/v1/hierarchy`, and `GET /api/v1/leaf/{leaf_id}` — MUST declare an `execution_mode` field whose value is exactly one of `ACTIVE_SOLANA` or `PASSIVE_CATALOG`.
For `leaf-solana`, `execution_mode` MUST be `ACTIVE_SOLANA`, reflecting that it is scheduled for autonomous background reflection and compiles policy overrides for hot-path execution.
For all other 25 leaves, `execution_mode` MUST be `PASSIVE_CATALOG`, reflecting that they are catalog specifications with manual reflection triggers only and do not compile hot-path policies.
Additionally, each leaf object MUST include `scheduler_active`: `true` for `leaf-solana` when background scheduling is enabled, and `false` for all other 25 leaves.

#### Scenario: Solana leaf declares active execution mode
- **WHEN** a client inspects `leaf-solana` in `GET /api/v1/leaf/leaf-solana` or the hierarchy snapshot
- **THEN** `execution_mode` is `ACTIVE_SOLANA`
- **THEN** `scheduler_active` matches the scheduler's active state

#### Scenario: Non-Solana leaves declare passive catalog execution mode
- **WHEN** a client inspects `leaf-bitcoin` or any of the other 24 non-Solana leaves
- **THEN** `execution_mode` is `PASSIVE_CATALOG`
- **THEN** `scheduler_active` is `false`

#### Scenario: Hierarchy overview preserves execution mode across all 26 leaves
- **WHEN** a client reads `GET /api/v1/hierarchy` or `GET /api/v1/hierarchy/overview`
- **THEN** every leaf in `leaves` contains an `execution_mode` field
- **THEN** exactly one leaf has `ACTIVE_SOLANA` and 25 leaves have `PASSIVE_CATALOG`

### Requirement: Telemetry source classification for leaf metrics

Every leaf status object MUST declare `ta_metrics_source`.
When `ta_metrics` is populated from static configuration literals (`LeafEcosystemConfig.ta_specific_metrics`), `ta_metrics_source` MUST be `CATALOG_FIXTURE`.
When `ta_metrics` is dynamically computed from live market candles, `ta_metrics_source` MUST be `LIVE_COMPUTED`.
For the 25 non-Solana leaves, `ta_metrics_source` MUST be `CATALOG_FIXTURE`.
Static baseline metrics MUST NOT be served without declaring `ta_metrics_source: "CATALOG_FIXTURE"`.

#### Scenario: Non-Solana leaf declares catalog fixture telemetry source
- **WHEN** `GET /api/v1/leaf/{leaf_id}` is called for any non-Solana leaf such as `leaf-ethereum`
- **THEN** `ta_metrics_source` equals `CATALOG_FIXTURE`
- **THEN** the metrics are not presented as live telemetry

#### Scenario: Telemetry source persists across leaf detail and summary endpoints
- **WHEN** `GET /api/v1/hierarchy` and `GET /api/v1/leaf/{leaf_id}` are queried
- **THEN** `ta_metrics_source` is present in both payloads and equals `CATALOG_FIXTURE` for non-Solana leaves

### Requirement: Frontend surfaces execution and telemetry honesty

The web frontend — specifically `MasterOverview` and `LeafAgentView` — MUST visually surface the leaf's `execution_mode` and `ta_metrics_source`:
1. In `MasterOverview`, the fleet table and summary cards MUST display a visual distinction (such as a `PASSIVE_CATALOG` badge) for non-Solana leaves, and MUST NOT describe the 25 non-Solana leaves as autonomously running.
2. In `LeafAgentView`, the header banner for non-Solana leaves MUST display a `PASSIVE_CATALOG` badge and state that background scheduling is inactive.
3. In `LeafAgentView`, the technical analysis & on-chain metrics section for non-Solana leaves MUST render a `CATALOG_FIXTURE` badge alongside an explanatory caption stating that the metrics are catalog baseline fixtures rather than live streaming telemetry.

#### Scenario: Leaf view renders passive catalog badge for non-Solana leaf
- **WHEN** an operator navigates to `LeafAgentView` for `leaf-bitcoin`
- **THEN** the header displays a `PASSIVE_CATALOG` badge
- **THEN** the banner indicates that autonomous scheduling is not active

#### Scenario: Leaf view renders catalog fixture badge on technical metrics
- **WHEN** an operator views the technical and on-chain metrics panel of `leaf-sui`
- **THEN** a `CATALOG_FIXTURE` badge is visibly rendered beside the section title
- **THEN** the panel contains a notice that metrics reflect catalog fixture data

#### Scenario: Master overview table distinguishes active leaf from passive fleet
- **WHEN** an operator views the fleet table in `MasterOverview`
- **THEN** `leaf-solana` is badged as `ACTIVE_SOLANA`
- **THEN** the other 25 leaves are badged as `PASSIVE_CATALOG`

### Requirement: Documentation honestly describes single-active-leaf implementation status

`AGENTS.md`, `README.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` MUST explicitly document that `leaf-solana` is the single autonomously scheduled leaf with hot-path policy compilation in the current system, and that the remaining 25 leaves exist as catalog configurations with on-demand manual reflection capabilities. Documentation SHALL NOT claim that 26 independent execution loops are currently operating autonomously in live or paper environments.

#### Scenario: AGENTS document states single-active-leaf status
- **WHEN** a reader reads `AGENTS.md`
- **THEN** it states that `leaf-solana` is the active scheduled leaf
- **THEN** it identifies the 25 non-Solana leaves as passive catalog entries awaiting live ingestion pipelines

#### Scenario: ADR-0003 status note clarifies current implementation phase
- **WHEN** a reader reads `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md`
- **THEN** it contains a status note stating that the 26-leaf architecture currently operates with Solana as the sole active warm-path driver while the remaining 25 leaves are passive catalog rows

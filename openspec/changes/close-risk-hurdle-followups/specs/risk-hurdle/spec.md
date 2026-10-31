## ADDED Requirements

### Requirement: Risk-gate dev-dependencies specify MSRV metadata

The `engine-rs/crates/risk-gate/Cargo.toml` manifest MUST document the `criterion = "0.8.2"` dev-dependency MSRV requirement (`1.86`) and the benchmark execution toolchain either via package `rust-version = "1.86"` or via an explicit comment preceding `[dev-dependencies]`.

#### Scenario: Criterion MSRV is explicitly documented in Cargo.toml

- **WHEN** `engine-rs/crates/risk-gate/Cargo.toml` is inspected
- **THEN** it explicitly states the MSRV requirement of `1.86` for the `criterion` dev-dependency

### Requirement: Per-intent hurdle rejections are asserted in the test suite

The test suite in `engine-rs/crates/backtest/src/lib.rs` (or `engine-rs/crates/risk-gate/src/lib.rs`) MUST assert the individual `RiskRejection::InsufficientEdge` rejections and hurdle values documented in the performance audit fixture summary. Specifically, it MUST assert that the JUP smart-money intent with `expected_edge_bps = 70.2` is rejected against `min_bps = 87.2`, that the AIX-SOL sniper intent with `expected_edge_bps = 95.0` is rejected against `min_bps = 151.4`, and that the `leaf-bitcoin` fixture execution produces exactly one hurdle rejection matching the fixture audit table.

#### Scenario: Solana smart-money hurdle rejection is verified

- **WHEN** the JUP smart-money fixture intent is evaluated by `HardRiskGate::validate`
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`
- **THEN** the reported `edge_bps` is `70.2` and `min_bps` is `87.2`

#### Scenario: Solana sniper hurdle rejection is verified

- **WHEN** the AIX-SOL sniper fixture intent is evaluated by `HardRiskGate::validate`
- **THEN** `validate` returns `RiskRejection::InsufficientEdge`
- **THEN** the reported `edge_bps` is `95.0` and `min_bps` is `151.4`

#### Scenario: Leaf-bitcoin fixture hurdle rejection is verified

- **WHEN** the `leaf-bitcoin` fixture intents are evaluated through the test engine or `HardRiskGate::validate`
- **THEN** exactly one intent is rejected by `InsufficientEdge` matching the audit table

### Requirement: Performance and cost audit document is English-only

The document `docs/PERFORMANCE_AND_COST_AUDIT.md` MUST be written entirely in English. All French section titles, table labels, headers, and body prose paragraphs MUST be translated to English. All numeric `[FIXTURE]`, `[SIMULATED]`, and `[MEASURED]` figures, benchmark values, and table layouts MUST be preserved verbatim.

#### Scenario: Performance audit contains no residual French prose

- **WHEN** `docs/PERFORMANCE_AND_COST_AUDIT.md` is inspected
- **THEN** all section headers, table headers, and body sentences are in English
- **THEN** all `[FIXTURE]` numbers, Sharpe ratios, PnL values, and token counts are preserved without modification

### Requirement: Hot-path latency claims cite measured benchmark evidence across ADRs

Every occurrence of `<50µs` or `<50 µs` hot-path latency claims in `docs/adr/0001-hybrid-quant-agentic-architecture.md`, `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` MUST cite the measured mean (`0.244 µs`) and the benchmark command `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`. Across `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/PERFORMANCE_AND_COST_AUDIT.md`, and `docs/adr/0001..0003`, zero bare `<50µs` or `<50 µs` claims SHALL remain.

#### Scenario: Architecture ADRs cite benchmark command and measured latency

- **WHEN** `docs/adr/0001-hybrid-quant-agentic-architecture.md`, `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` are inspected
- **THEN** every hot-path latency claim states the measured mean of `0.244 µs` and the benchmark command `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`

#### Scenario: Zero bare 50µs claims across documentation corpus

- **WHEN** a regex search for `< ?50 ?[uµ]s` without measured benchmark citation is executed over `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/PERFORMANCE_AND_COST_AUDIT.md`, and `docs/adr/*.md`
- **THEN** zero unannotated bare claims are found

## 1. Criterion MSRV Metadata (DEV-R1-F01)

- [ ] 1.1 Document Criterion MSRV requirement (`1.86`) and benchmark toolchain in `engine-rs/crates/risk-gate/Cargo.toml` dev-dependency comments (satisfies: `Criterion MSRV is explicitly documented in Cargo.toml`)

## 2. Per-Intent Rejection Breakdown Tests (DEV-R1-F02)

- [ ] 2.1 Add unit tests asserting JUP smart-money fixture intent rejection with `expected_edge_bps = 70.2` and `min_bps = 87.2` (satisfies: `Solana smart-money hurdle rejection is verified`)
- [ ] 2.2 Add unit tests asserting AIX-SOL sniper fixture intent rejection with `expected_edge_bps = 95.0` and `min_bps = 151.4` (satisfies: `Solana sniper hurdle rejection is verified`)
- [ ] 2.3 Add unit test asserting `leaf-bitcoin` fixture hurdle rejection breakdown matching the audit table (satisfies: `Leaf-bitcoin fixture hurdle rejection is verified`)

## 3. English-Only Audit Document Translation (DEV-R1-F03)

- [ ] 3.1 Translate executive summary and operational cost sections in `docs/PERFORMANCE_AND_COST_AUDIT.md` to English (satisfies: `Performance audit contains no residual French prose`)
- [ ] 3.2 Translate three-population trading performance and structural adjustments sections in `docs/PERFORMANCE_AND_COST_AUDIT.md` to English, preserving all numeric figures, table structures, and benchmark values verbatim (satisfies: `Performance audit contains no residual French prose`)

## 4. Extended ADR `<50µs` Latency Sweep (DEV-R1-F04)

- [ ] 4.1 Update hot-path latency claims in `docs/adr/0001-hybrid-quant-agentic-architecture.md`, `docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md`, and `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` with measured mean (`0.244 µs`) and benchmark command (satisfies: `Architecture ADRs cite benchmark command and measured latency`)
- [ ] 4.2 Verify zero bare `<50µs` or `<50 µs` claims remain across `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/PERFORMANCE_AND_COST_AUDIT.md`, and `docs/adr/*.md` (satisfies: `Zero bare 50µs claims across documentation corpus`)

## Verification

Run the following commands to verify the change:
- `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-backtest` -> verifies all fixture tests including per-intent rejection assertions pass.
- `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate -- --test` -> verifies benchmark harness compiles and runs.
- `git grep -n -E "< ?50 ?[uµ]s" docs/adr/` -> verifies all ADR hot-path claims cite the benchmark command and measured mean.
- `git grep -n -E "< ?50 ?[uµ]s" README.md AGENTS.md docs/architecture.md docs/PERFORMANCE_AND_COST_AUDIT.md docs/adr/` -> verifies zero bare `<50µs` claims remain across documentation.
- `python3 scripts/sdlc/spec-lint.py --change close-risk-hurdle-followups` -> passes with zero errors.
- `openspec validate close-risk-hurdle-followups --strict` -> passes strict OpenSpec validation.

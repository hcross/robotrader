# ADR-0003: Hierarchical Multi-Ecosystem Architecture, Master Treasury & Cross-Wing MemPalace

- **Status**: Accepted
- **Date**: 2026-10-24
- **Supersedes / Extends**: [ADR-0001](0001-hybrid-quant-agentic-architecture.md), [ADR-0002](0002-autonomous-cognitive-warm-path-and-ta-memory.md)

## Context & Problem Statement

In Robotrader v2 (ADR-0001 / ADR-0002), a single Warm-Path agent (`OrchestratorAgent`) combined macro portfolio allocation with tactical technical analysis across multiple ecosystems (`SOL/USDT`, `ETH/USDT`, `BTC/USDT`) while driving a primarily Solana-centric execution engine.

As the platform scales to cover the broader cryptocurrency landscape, mixing cross-chain macro treasury management with blockchain-specific microstructure and technical analysis inside a single flat agent introduces three structural bottlenecks:
1. **Context Pollution**: Blockchain-specific catalysts, validator/mempool telemetry, and technical indicators from 20+ heterogeneous L1s/L2s cannot fit cleanly into a single tactical prompt without diluting signal quality or exploding token costs.
2. **Capital & Cross-Chain Friction Blindness**: Moving liquidity across blockchains incurs gas fees, bridge protocol fees (Wormhole, LayerZero, CCIP, IBC), DEX swap slippage, and finality latency. Without an explicit top-level Treasury Controller pricing transfer viability (`hurdle_rate_bps`), agents risk churning capital across chains.
3. **Cognitive Continuity & Inference Autonomy**: A multi-agent fleet requires both isolated per-ecosystem memory and global cross-ecosystem observability, as well as a safe, bounded mechanism to keep the OpenRouter inference credit account funded before exhaustion.

## Decision

We evolve Robotrader into a **Two-Tier Hierarchical Multi-Ecosystem System (Robotrader v3)**:

### 1. Tier 1 — Master Orchestrator & Treasury Controller (`moonshotai/kimi-k3.1-pro`)
- **Role**: Chief Investment Officer (CIO) and holder of the **Master Portfolio (`Master Treasury`)**.
- **Long-Term Horizon**: Operates on a macro reflection cycle (default `3600s` / 1h) fed by **multi-channel macro RSS feeds** (institutional ETF flows, central bank liquidity, regulatory catalysts, cross-chain TVL flows).
- **Dry Powder Reserve**: Always maintains a liquid safety and opportunity reserve (`Dry Powder >= 20%` of total capital, target `22%`) to absorb drawdowns, fund high-conviction dislocations, or serve operator withdrawals immediately.
- **Capital Allocation & Risk Mandates**: Allocates capital according to total portfolio scale (`< $5k` concentrated P0, `$5k-$50k` P0+P1+CEX, `> $50k` full multi-chain deployment) and assigns a dynamic risk posture (`AGGRESSIVE`, `BALANCED`, `DEFENSIVE`, `HIBERNATION`) to each leaf robot.
- **Emergency Liquidation & Repatriation**: Can immediately close a leaf robot's positions and repatriate 100% of its capital into Dry Powder (`POST /api/v1/leaf/{leaf_id}/liquidate`) if its blockchain experiences security/bridge distress or notable underperformance.
- **Cross-Chain Transfer Viability (`CrossChainTreasuryRouter`)**: Before moving funds from chain $A$ to chain $B$, computes the exact one-way and round-trip cost (`gas_fee + bridge_fee + dex_swap_slippage`) and enforces a strict hurdle rate:
  $$\text{Expected Alpha (bps)} \ge 2.5 \times \text{Round-Trip Transfer Cost (bps)}$$
- **Multi-Chain / Multi-Token Operator Checkout (`POST /api/v1/treasury/checkout`)**: Allows the operator to request a withdrawal of any USD amount delivered in a target token (`SOL`, `BTC`, `ETH`, `USDC`, `USDT`, `SUI`, `HYPE`, `ATOM`, etc.) on any supported blockchain, quoting fees/finality and drawing from Dry Powder first.
- **Cross-Wing MemPalace Access**: Persists its own macro reflections in `wing="master_orchestrator"` (plus raw LLM transcripts in `TranscriptPalace`) and has **read access across all 26 leaf agents' MemPalace wings** (`StrategyMemoryPalace.format_cross_wing_digest`).
- **Profit-Gated & Epoch-Capped OpenRouter Auto-Refill**: Monitors the OpenRouter credit balance (`low_watermark_usd = $2.00`, resolved from `OPENROUTER_LOW_WATERMARK_USD`) and automatically tops up credits before exhaustion. The four conditions are enforced by the Python `CostGuard` gate until the Rust routing follow-up lands: `measured realized_trading_pnl_usd > 0`, `refill <= 10%` of measured PnL, a fixed single-refill bound `(0, $25.00]` plus a configured epoch cap `<= $25/24h` maintained as a rolling 24 h window, and `kill_switch_active == false` (see [`design.md`](../../openspec/changes/fix-costguard-python-gate/design.md)).

### 2. Tier 2 — 26 Specialized Blockchain & Venue Leaf Robots (`deepseek/deepseek-v4.1-flash-1017`)
- **Strict Single-Ecosystem Isolation**: Each leaf agent monitors and trades **exclusively** its assigned blockchain (or dedicated multi-crypto/paper venue), reads **only** its ecosystem-scoped RSS feeds (`EcosystemRSSAggregator`), computes ecosystem-specific TA/on-chain metrics, and writes to its dedicated MemPalace wing (`wing="leaf_<slug>"`).
- **Ecosystem-Adapted Rust Strategy Pods (`<= 4` per Blockchain)**: Each of the 26 blockchains has its own tailored Rust execution pods in `engine-rs` (`crates/strategies/src/lib.rs`, `build_pods_for_leaf(leaf_id)`, hard-capped at `1..=4` pods per ecosystem) and can run deterministic Rust backtests (`POST /api/v1/leaf/{leaf_id}/backtest`).
- **Simulated Vault & 26-Chain Target Metadata ([`docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md`](../CRYPTO_VAULT_AND_KEY_MANAGEMENT.md))**: `engine-rs` exposes a `SimulatedVault` whose manifest is always `SIMULATED`: addresses are non-spendable, receipts are not chain-valid, and the whitelist is a simulated prefix filter. Curve names, target derivation paths, and target SLIP-44 values are target metadata only; no real derivation, address encoding, chain signature, or mainnet custody is implemented. Python LLM agents hold no key and never broadcast. See [ADR-0005](0005-vault-is-simulated.md).
- **15m Candle-Aligned Cadence & Default-Paused Scheduler**: Active leaf agents align their cognitive wakeup floor with 15-minute candle closes (`900s`), hibernating leaves use `3600s`, and the automatic background LLM scheduler defaults to paused (`ENABLE_AUTO_LLM_SCHEDULER=false`, `$0.00/h`) until explicitly enabled via the UI/API (`POST /api/v1/cognitive/scheduler`). See [Performance & Cost Audit](../PERFORMANCE_AND_COST_AUDIT.md).
- **Purification of `leaf-solana`**: All non-Solana trading (`BTC/USDT`, `ETH/USDT`) is stripped from the Solana branch (`state_store.py`, `orchestrator.py`, `engine-rs/crates/backtest`, `Dashboard.jsx`). `leaf-solana` now exclusively trades Solana ecosystem pairs (`SOL/USDT`, `JUP/USDT`, `RAY/USDT`, `SOL-DEVNET`).
- **26-Agent Fleet Taxonomy**:
  - **P0 Core High-Velocity L1s**: `leaf-solana` (SOL/JUP/RAY), `leaf-bitcoin` (BTC), `leaf-ethereum` (ETH), `leaf-sui` (SUI), `leaf-hyperliquid` (HYPE).
  - **P1 Major L1s**: `leaf-bnb` (BNB), `leaf-xrp` (XRP), `leaf-ton` (TON / ex-Gram), `leaf-tron` (TRX), `leaf-avalanche` (AVAX), `leaf-cosmos` (ATOM / IBC).
  - **P2 Specialized Infra & Oracles**: `leaf-aptos` (APT), `leaf-chainlink` (LINK), `leaf-stacks` (STX / ex-Blockstack), `leaf-near` (NEAR), `leaf-cardano` (ADA), `leaf-polkadot` (DOT), `leaf-dogecoin` (DOGE), `leaf-icp` (ICP).
  - **P3 Tactical / Institutional Watch**: `leaf-canton` (CC), `leaf-celo` (CELO), `leaf-tezos` (XTZ), `leaf-flow` (FLOW), `leaf-eos` (EOS / Vaulta).
  - **Dedicated Multi-Crypto & Paper Venues**: `leaf-binance-cex` (absorbs multi-pair CEX trading removed from `leaf-solana`), `leaf-paper-sandbox`.

### 3. Tabbed Command Center UI (`frontend/`)
- **Home Tab (`MasterOverview.jsx`)**: Minimalist executive control plane centered on three operator actions:
  1. Deposit funds to the Master Orchestrator (`Confier des capitaux`).
  2. Request a multi-chain / multi-token withdrawal (`Checkout`).
  3. Inspect current portfolio allocation, Dry Powder reserve, OpenRouter credit auto-refill status, cross-chain bridge hurdle pricer, and the long-term strategy formulated by `moonshotai/kimi-k3.1-pro`.
- **26 Leaf Tabs (`LeafAgentView.jsx` & `Dashboard.jsx`)**: Dedicated per-ecosystem tabs displaying the leaf's Master mandate, exclusive assets, specific TA/on-chain indicators, ecosystem RSS feed, and `wing="leaf_<slug>"` MemPalace drawers.

## Amendment — 2026-10-26 (fix-costguard-python-gate)

The auto-refill bullet above is corrected to match the gate that actually runs. Full design: [`design.md`](../../openspec/changes/fix-costguard-python-gate/design.md).

- **Low watermark**: `$2.00`, resolved from `OPENROUTER_LOW_WATERMARK_USD`. The previous `$5.00` contradicted both the backend default and the operator-facing threshold.
- **Gate ownership**: the four conditions are enforced by the Python `CostGuard` (`backend/agents/monitor.py`) on both the automatic and operator paths. Routing the gate through `HardRiskGate::validate_inference_refill` remains a follow-up on issue #5.
- **Measured source**: realized PnL is injected from the orchestrator's own state store; there is no module-global fallback and no fabricated profit floor.
- **Epoch cap**: a rolling 24 h window of refill events (`(timestamp_ms, amount_usd)`), so headroom returns within the process without a restart. The window is in memory: a restart starts a new window, and persistence across restarts is a follow-up on issue #5.

## Amendment — 2026-10-31 (fix-leaf-fleet-parity-honesty)

The execution status of the 26-leaf fleet is clarified to honestly reflect the current implementation phase:

- **Single Active Warm-Path Driver**: `leaf-solana` is currently the sole autonomously scheduled leaf robot (`execution_mode: "ACTIVE_SOLANA"`), compiling policy overrides for hot-path execution in `engine-rs`.
- **Passive Catalog Fleet**: The remaining 25 non-Solana leaves operate as catalog specifications (`execution_mode: "PASSIVE_CATALOG"`, `scheduler_active: false`), with baseline indicators tagged with `ta_metrics_source: "CATALOG_FIXTURE"`. They support on-demand manual reflection triggers and deterministic policy sanity check fixtures, but do not autonomously compile hot-path policies or execute live trades until live ingestion pipelines are connected.
- **Pod Catalog Parity**: Strategy Pod definitions across all 26 leaves are strictly aligned between Python `HierarchicalFleetManager` and Rust `engine-rs/crates/strategies` with 100% attribute equality, verifiable via `robotrader-node --dump-pod-catalog`.
- **Provenance Stamping**: Ecosystem RSS feeds declare machine-readable item and feed provenance (`LIVE_RSS` vs `CURATED_FIXTURE`, `feed_mode`), and static macro narratives declare `SYNTHETIC_FIXTURE`.

## Consequences

- **Positive**: Complete elimination of cross-ecosystem contamination inside `leaf-solana`; crystal-clear separation between macro capital allocation (`Kimi K3.1 Pro`) and high-frequency ecosystem execution (`DeepSeek v4.1 Flash 1017` + Rust pods under the `<50µs` budget, measured mean: `0.244 µs`; bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`); deterministic protection against unprofitable cross-chain bridging and unbounded inference refills.
- **Trade-offs**: Higher number of logical wings in `StrategyMemoryPalace`, mitigated by `recall_across_wings` and compact cross-wing digests.

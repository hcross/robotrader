# Robotrader v3 Architecture: Hierarchical Multi-Ecosystem Quant + Agentic Meta-Controller

> **Reference Decisions**:
> - [ADR-0001: Hybrid Rust/Python Event-Driven Quant & Agentic Meta-Controller Architecture](adr/0001-hybrid-quant-agentic-architecture.md)
> - [ADR-0002: Autonomous Cognitive Warm-Path, Pro TA & Strategy Palace](adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md)
> - [ADR-0003: Hierarchical Multi-Ecosystem Architecture, Master Treasury & Cross-Wing MemPalace](adr/0003-hierarchical-multi-ecosystem-architecture.md)
> - [Quantitative Performance & LLM Inference Cost Audit](PERFORMANCE_AND_COST_AUDIT.md)

## 1. Architectural Philosophy

Robotrader v2 separates **deterministic low-latency execution** from **asynchronous AI reasoning**:

1. **Zero LLM in the Hot Path**: Market data ingestion, orderbook state, quantitative signal calculation, pre-trade risk enforcement, and order routing execute deterministically in **Rust (`engine-rs`)** in `<1ms`.
2. **AI as Warm-Path Meta-Controller**: Python AI agents (`backend/`) ingest unstructured real-time catalysts (listings, macro events, governance, whale clusters), classify market regimes, and publish TTL-bounded **`PolicyEnvelope`** states to Redis.
3. **Zero Code Drift (`Backtest == Paper == Live`)**: Strategy pods implement a unified Rust trait (`StrategyPod`) that processes identical `MarketEvent` streams whether replaying historical Parquet/DuckDB ticks, paper-trading live WebSockets, or executing with real capital.
4. **Synchronous Hard Risk Firewall**: No order reaches an exchange or Solana RPC without passing through `HardRiskGate`, which enforces fractional Kelly sizing, daily drawdown kill-switches, fee/slippage bounds, and on-chain token safety checks.

---

## 2. System Topology

```mermaid
flowchart TB
    subgraph Client["Presentation Layer (React 19 + Tailwind v4)"]
        UI["Real-Time Dashboard, Equity Curve, Pod Controls & Copilot Chat"]
    end

    subgraph ControlAndWarm["Warm Path & Control Plane (Python 3.11+ / FastAPI / Strands)"]
        API["FastAPI + WebSocket Telemetry & Command Gateway"]
        Orch["Orchestrator Agent (User Copilot & Swarm Coordinator)"]
        Scout["CatalystScout Agent (Listings, News, Social Velocity, Whale Flows)"]
        Meta["MetaAllocator Agent (Regime Classification & Dynamic Pod Weighting)"]
        Auditor["QuantAuditor Agent (Execution Slippage & Alpha Decay Analyzer)"]
        Cost["CostGuard (Tiered LLM Routing & Hard Daily Token Budget)"]
    end

    subgraph Bus["Low-Latency IPC & Persistence"]
        Redis[("Redis 7 (Streams: Events/Fills | KV: TTL PolicyEnvelope)")]
        Storage[("DuckDB / Parquet (Historical Ticks, Candles & Trade Ledger)")]
    end

    subgraph HotPath["Hot Path Execution & Replay Engine (Rust / Tokio Workspace)"]
        Feed["Market Data Multiplexer (Binance/Hyperliquid WS + Solana Geyser/RPC)"]
        
        subgraph Pods["Deterministic Strategy Pods (1..=4 per Blockchain)"]
            P1["Pod 1: pod_carry (Funding Rate & Native Yield / Basis Arbitrage)"]
            P2["Pod 2: pod_momentum (Orderbook Imbalance, CVD & Volatility Breakout)"]
            P3["Pod 3: pod_onchain_alpha (On-Chain Smart-Money & Catalyst Flow)"]
            P4["Pod 4: pod_sniper (Atomic DEX Pool & MEV Liquidation Sniper)"]
        end

        Risk["HardRiskGate (<50µs: Drawdown Kill-Switch, Kelly Sizing, OnChainTokenSafety, SimulatedVault (SIMULATED))"]
        Exec["Smart Execution Router (Post-Only CEX Maker / OnchainDexAggregator + MevBundleAtomic)"]
        Replay["Deterministic Backtest & Walk-Forward Runner"]
    end

    subgraph Venues["External Venues & Networks"]
        CEX["CEX Spot & Perps (Binance / Bybit / Hyperliquid)"]
        Solana["Solana Mainnet + Jito Block Engine + Jupiter v6 API"]
    end

    UI <-->|"WebSocket (JSON)"| API
    API <--> Orch
    Scout --> Meta
    Auditor --> Meta
    Meta -->|"SET policy:active (TTL 15m)"| Redis
    API <-->|"XREAD / PubSub"| Redis

    Feed -->|"MarketEvent"| Pods
    Redis -.->|"Watch PolicyEnvelope"| Pods
    Pods -->|"OrderIntent"| Risk
    Risk -->|"ApprovedOrder"| Exec
    Exec -->|"ExecutionReport"| Redis
    Exec --> Storage
    Exec <--> CEX
    Exec <--> Solana
    Storage --> Replay
    Replay -.->|"Identical StrategyPod Trait"| Pods
```

---

## 3. Repository Layout (Target Structure)

```text
.
├── engine-rs/                  # Rust Hot-Path & Backtest Workspace (Cargo)
│   ├── Cargo.toml
│   ├── crates/
│   │   ├── common/             # Shared types: MarketEvent, OrderIntent, PolicyEnvelope, Venue
│   │   ├── ingest/             # CEX WebSockets (Binance/Hyperliquid) & Solana RPC/Geyser streams
│   │   ├── risk-gate/          # Synchronous HardRiskGate, Kelly sizer, Drawdown kill-switch, Rug filter
│   │   ├── strategies/         # StrategyPod trait + Pod 1 (Carry), Pod 2 (Momentum), Pod 3 (Solana), Pod 4 (Sniper)
│   │   ├── exec-router/        # Post-only CEX router, Jupiter v6 client, Jito bundle signer, Paper simulator
│   │   ├── backtest/           # Historical Parquet/DuckDB replay engine & performance metrics (Sharpe/Sortino/DD)
│   │   └── node/               # Main hot-path binary connecting Ingest -> Pods -> Risk -> Exec <-> Redis
├── backend/                    # Python Warm-Path AI Meta-Controller & Control Plane (Poetry)
│   ├── core/                   # Redis IPC client, Pydantic schemas (matching engine-rs/common), LLM router
│   ├── agents/                 # Strands-based Warm-Path Agents (Orchestrator, CatalystScout, MetaAllocator, QuantAuditor, CostGuard)
│   ├── api/                    # FastAPI REST + WebSocket hub for UI telemetry, backtest triggers & manual kill-switch
│   ├── server.py               # FastAPI + Warm-Path Agent lifecycle entrypoint
│   └── tests/                  # Pytest suite for IPC contracts, agent policies & API endpoints
├── frontend/                   # React 19 + Vite + Tailwind v4 Command Center
│   └── src/
│       ├── components/         # Live PnL Dashboard, Pod Allocation Matrix, Risk Kill-Switch, Orchestrator Chat
│       └── hooks/              # Real-time WebSocket state synchronization hook
├── docs/
│   ├── adr/                    # Architecture Decision Records
│   ├── architecture.md         # System topology & component contracts
│   └── agents.md               # Warm-Path AI Agents & Hot-Path Strategy Pods specification
└── docker-compose.yml          # Orchestrates redis, engine-rs, backend, and frontend
```

---

## 4. Core Component Specifications

### 4.1. Rust Hot-Path Engine (`engine-rs`)

1. **`crates/common`**:
   - Defines canonical chain-agnostic types serialized via `serde`: `MarketEvent` (`L2BookUpdate`, `TradeTick`, `FundingRateUpdate`, `OnchainPoolLaunch`, `OnchainSmartMoneySwap`), `OrderIntent` (with generic `token_safety: Option<OnChainTokenSafety>`), `ApprovedOrder` (with `mev_priority_tip_bps`), `ExecutionReport`, `PodId` (`PodCarry`, `PodMomentum`, `PodOnchainAlpha`, `PodSniper`), `OrderType` (`PostOnlyMaker`, `LimitIoc`, `Market`, `MevBundleAtomic`), `Venue` (`BinanceSpot`, `BinancePerp`, `HyperliquidPerp`, `OnchainDexAggregator`, `OnchainAtomicPool`), and `PolicyEnvelope`.
2. **`crates/strategies` (`StrategyPod` Trait)**:
   ```rust
   pub trait StrategyPod: Send + Sync {
       fn id(&self) -> &'static str;
       fn on_market_event(&mut self, event: &MarketEvent, policy: &PolicyEnvelope) -> Vec<OrderIntent>;
       fn on_execution_report(&mut self, report: &ExecutionReport);
   }
   ```
3. **`crates/risk-gate` (`HardRiskGate`)**:
   - Stateful, in-memory pre-trade validator.
   - Tracks real-time equity, unrealized PnL, daily high-water mark, per-pod exposure, and order rate limits.
   - Rejects any `OrderIntent` if `daily_drawdown >= max_daily_drawdown_pct` or if `PolicyEnvelope` TTL has expired without safe-mode fallback.
4. **`crates/exec-router`**:
   - Supports four exact `ROBOTRADER_EXECUTION_MODE` values: `BACKTEST`, `PAPER` (default when unset; live market data with simulated fills/fees/slippage), `SIMULATED`, and `LIVE`. An empty or unknown value fails closed; `LIVE` still exports a `SIMULATED` vault and claims no real custody.
   - **CEX Optimization**: Uses `Post-Only` limit orders at best bid/ask with micro-repricing to capture maker rebates or low maker fees instead of paying 5–10 bps taker fees.
   - **Solana Optimization**: Quotes via Jupiter v6 and submits transactions wrapped in **Jito bundles** (`sendBundle`) so failed or front-run transactions cost zero base gas if they revert.

### 4.2. Python Warm-Path AI Layer (`backend/`)

- Uses `strands-agents` (isolated cleanly from `backend/core/` to prevent module shadowing).
- Operates asynchronously off the critical path:
  - Aggregates external signals (RSS/news feeds, exchange announcements, funding rate extremes, on-chain whale alerts).
  - Synthesizes a `PolicyEnvelope` every $N$ minutes (or immediately upon a high-priority catalyst event) and writes it to Redis key `robotrader:policy:active` with a 15-minute TTL.
  - Streams live telemetry (`robotrader:stream:telemetry` and `robotrader:stream:fills`) to the React frontend over WebSocket `/ws/telemetry` and `/ws/chat`.

---

## 5. Security & Capital Protection Invariants

1. **Simulated Vault, No Key Custody**: The `SimulatedVault` exports a `SIMULATED` manifest; addresses are explicitly non-spendable and receipts are not chain-valid. No real derivation, address encoding, chain signature, or mainnet custody is implemented.
2. **No Python Key Custody**: The Python LLM container (`backend`) holds no signing keypair, reads no seed or private key, and never broadcasts a Solana transaction. The Solana tool is a read-only RPC client over a configured public address (`custody: NONE`).
3. **No Exchange Keys in `engine-rs`**: `engine-rs` is not injected with exchange trade API keys or signing keypairs. Any CEX key policy remains an operator deployment concern; CEX API keys must be restricted to `Spot & Margin/Futures Trading` only, with IP whitelisting and withdrawals disabled.
4. **Simulated Solana Actions**: Solana Devnet actions are recorded as `SIMULATED`, unsigned, and not broadcast; they are excluded from measured live performance.
5. **Hard Kill-Switch**: A Redis + in-memory atomic kill-switch (`POST /api/v1/risk/kill` or automatic drawdown trigger) immediately cancels all open orders and flattens directional exposure.

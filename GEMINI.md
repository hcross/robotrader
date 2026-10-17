# Robotrader: AI Coding Agent Guide (GEMINI.md)

Welcome, fellow agent! This document is designed to help you quickly understand the **Robotrader v2** project and how to contribute effectively.

## Project Overview
Robotrader v2 is a **Hybrid Rust/Python Quantitative & Agentic Cryptocurrency Trading Platform** ([ADR-0001](docs/adr/0001-hybrid-quant-agentic-architecture.md)). It separates **deterministic sub-millisecond execution & risk enforcement (`engine-rs` in Rust)** from **asynchronous AI catalyst analysis & regime allocation (`backend` in Python)**.

## Tech Stack
- **Hot-Path & Replay Engine (`engine-rs`)**: Rust (Edition 2021), Cargo Workspace (`common`, `risk-gate`, `strategies`, `exec-router`, `backtest`, `node`), Serde.
- **Warm-Path AI & Control Plane (`backend`)**: Python 3.10+, FastAPI, Poetry, `strands-agents`, LiteLLM, CCXT, Solana RPC.
- **IPC & State Bus**: Redis 7 (with in-memory + TTL fallback for local dev/testing).
- **Frontend (`frontend`)**: React 19, Vite (Rolldown), Tailwind CSS v4, Lucide React.
- **Infrastructure**: Multi-stage Docker builds, Docker Compose, Helm charts (`charts/robotrader`).

## Project Structure
```bash
.
├── engine-rs/          # Rust Hot-Path, HardRiskGate, 4 Strategy Pods & Backtest Workspace
│   ├── Cargo.toml
│   └── crates/
│       ├── common/     # Canonical types: MarketEvent, OrderIntent, PolicyEnvelope, PortfolioState
│       ├── risk-gate/  # Synchronous HardRiskGate (<50µs), Kelly sizer, Drawdown kill-switch, Solana anti-rug
│       ├── strategies/ # StrategyPod trait + Pod 1 (Carry), Pod 2 (Momentum), Pod 3 (Solana), Pod 4 (Sniper)
│       ├── exec-router/# Post-Only CEX maker router & Solana Jupiter v6 + Jito bundle simulator
│       ├── backtest/   # Unified deterministic replay engine (Backtest == Paper == Live)
│       └── node/       # CLI & runtime binary (`robotrader-node`)
├── backend/            # Python Warm-Path AI Meta-Controller & FastAPI Control Plane
│   ├── core/           # IPC State Store, schemas (mirroring engine-rs/common), BaseWarmAgent
│   ├── agents/         # Orchestrator, CatalystScout, MetaAllocator, QuantAuditor, CostGuard
│   ├── tools/          # Exchange & Solana RPC tools
│   ├── tests/          # End-to-end Python <-> Rust integration tests
│   └── server.py       # FastAPI REST + WebSocket entrypoint
├── frontend/           # React 19 + Tailwind v4 Real-Time Command Center
└── docs/               # ADRs, Architecture & Agent/Pod specifications
```

## How to Run & Test
### 1. Run Rust Engine & Backtest Tests
```bash
cd engine-rs && cargo test
```

### 2. Run Python Warm-Path & Rust Bridge Integration Tests
```bash
PYTHONPATH=. python3 -m unittest discover -s backend/tests -v
```

### 3. Build Frontend
```bash
cd frontend && npm run build
```

### 4. Start Full Stack with Docker Compose
```bash
docker compose up --build
```
- **Backend Control Plane API**: `http://localhost:8000/api/v1/status`
- **Frontend Command Center**: `http://localhost:5173`

## Coding Guidelines for Agents
- **Zero LLM in the Hot Path**: Never put LLM calls or blocking network I/O inside `StrategyPod::on_market_event` or `HardRiskGate::validate`.
- **PolicyEnvelope Contract**: Keep `engine-rs/crates/common/src/lib.rs` and `backend/core/schemas.py` strictly synchronized.
- **No Module Shadowing**: Warm-Path infrastructure lives in `backend/core/` so the external `strands-agents` package (`import strands`) is never shadowed.
- **Capital Protection**: `CostGuard` (`backend/agents/monitor.py`) enforces a hard daily USD spend limit (`MAX_DAILY_LLM_BUDGET_USD`); never re-introduce unbounded automatic wallet refills.

# Robotrader v2 🤖📈⚡

**Robotrader v2** is a **Hybrid Quantitative & Autonomous Cognitive Cryptocurrency Trading Platform**.

It combines **deterministic sub-millisecond Rust execution (`engine-rs`)** with an **asynchronous AI Cognitive Loop (`backend`)** equipped with a professional Technical Analysis toolbelt, an infinite Strategy Memory Palace, self-scheduling wakeups, and budget-governed frontier model routing.

---

## 🏛️ Architecture Philosophy

Robotrader v2 solves the latency and reliability dilemma of agentic trading by enforcing a strict **Two-Tier Separation** documented in [ADR-0001](docs/adr/0001-hybrid-quant-agentic-architecture.md) and [ADR-0002](docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md):

```
┌────────────────────────────────────────────────────────────────────────┐
│               WARM-PATH: AUTONOMOUS COGNITIVE LOOP                     │
│               Python 3.11 + FastAPI + Strategy Palace                  │
│                                                                        │
│   ┌─────────────────────┐   ┌─────────────────┐   ┌────────────────┐   │
│   │ Pro TA Indicators   │   │ Social / Macro  │   │ Strategy       │   │
│   │ Ichimoku (9,26,52)  │ + │ Sentiment &     │ + │ Memory Palace  │   │
│   │ Fib 0.618 Pocket    │   │ Smart Money     │   │ strategy_ledger│   │
│   │ RSI, ATR, Bollinger │   │ Velocity        │   │ (Continuity)   │   │
│   └──────────┬──────────┘   └────────┬────────┘   └───────┬────────┘   │
│              └───────────────────────┼────────────────────┘            │
│                                      ▼                                 │
│               ┌──────────────────────────────────────────┐             │
│               │ OpenRouter Frontier Flash Routing        │             │
│               │ (DeepSeek v4.1, GLM 5.3, Qwen 3.7 Flash) │             │
│               │ Depth: DEEP_THESIS ➔ ECO_CONSERVATION    │             │
│               └──────────────────────┬───────────────────┘             │
│                                      │                                 │
│                   Compiles Strategy  │ Updates PolicyEnvelope          │
│                   into Numerical     │ (AssetOverrides, S/R, OBI, TP)  │
│                   Hard Rules         ▼                                 │
│               ┌──────────────────────────────────────────┐             │
│               │  Redis 7 IPC State Store (TTL Heartbeat) │             │
│               └──────────────────────┬───────────────────┘             │
└──────────────────────────────────────┼─────────────────────────────────┘
                                       │ Sub-millisecond reads (<50µs)
┌──────────────────────────────────────┼─────────────────────────────────┐
│               HOT-PATH: DETERMINISTIC EXECUTION ENGINE                 │
│               Rust Workspace (engine-rs)                               │
│                                      ▼                                 │
│               ┌──────────────────────────────────────────┐             │
│               │ Synchronous HardRiskGate (<50µs)         │             │
│               │ • Kelly Position Sizer                   │             │
│               │ • Drawdown Kill-Switch                   │             │
│               │ • Solana Token Anti-Rug / Freeze Check   │             │
│               └──────────────────────┬───────────────────┘             │
│                                      │                                 │
│               ┌──────────────────────┴───────────────────┐             │
│               │ 4 Autonomous Execution Strategy Pods     │             │
│               │ • Pod 1: Funding Carry / Basis Arbitrage │             │
│               │ • Pod 2: Order Book Imbalance (OBI)      │             │
│               │ • Pod 3: Solana L1 Momentum              │             │
│               │ • Pod 4: DEX Sniper (Meme / Catalyst)    │             │
│               └──────────────────────┬───────────────────┘             │
│                                      ▼                                 │
│               ┌──────────────────────────────────────────┐             │
│               │ Execution Router: Binance Post-Only &    │             │
│               │ Solana Jupiter v6 + Jito MEV Bundles     │             │
│               └──────────────────────────────────────────┘             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### 1. Zero LLM Latency in the Hot-Path
- **Sub-millisecond decisions**: Market events and Order Book Imbalance (OBI) feeds are ingested directly by Rust pods.
- **HardRiskGate (<50µs)**: Validates maximum order sizing, drawdown halts, and Solana token safety synchronously.
- **No blocking I/O**: The execution engine never waits for an external LLM call or network inference loop.

### 2. Professional Technical Analysis Toolbelt
The warm-path AI calculates high-grade mathematical indicators on live Binance 15m OHLCV candles (`SOL/USDT`, `ETH/USDT`, `BTC/USDT`):
- **Ichimoku Kinko Hyo `(9, 26, 52)`**: Tenkan-sen, Kijun-sen, Senkou Span A/B (Kumo Cloud Top/Bottom), Chikou Span, TK Crosses, and Kumo positioning (`ABOVE_KUMO_BULLISH`, `INSIDE_KUMO_NEUTRAL`, `BELOW_KUMO_BEARISH`).
- **Fibonacci Retracements & Extensions**: `0.236`, `0.382`, `0.500`, **`0.618` (Golden Pocket)**, `0.786`, `1.272`, and `1.618`, with automatic golden pocket proximity detection (`in_golden_pocket`).
- **Oscillators & Volatility**: `RSI (14)` overbought/oversold dynamics, `ATR (14)` (in USD and bps for trailing volatility), and `Bollinger Bands (20, 2)` squeeze detection.
- **Social & Macro Panorama**: Real-time sentiment metrics, Solana Smart-Money velocity, perpetual funding APR, and order book pressure.

### 3. Infinite Strategy Memory Palace (`strategy_ledger`)
- Inspired by the **MemPalace** architecture, all strategic reflections, market theses, and invalidation criteria are stored as structured `PalaceDrawer` objects in `backend/data/strategy_palace.jsonl` and mirrored in Redis (`robotrader:v2:palace`).
- Prior to every cognitive cycle, the model ingests its historical drawers to evaluate **thesis continuity**:
  - `INIT_THESIS`: Creating a fresh directional thesis.
  - `CONFIRMED`: Market price action validates the current thesis.
  - `REFINED`: Adjusting support/resistance levels or stop distances.
  - `INVALIDATED`: Price breached invalidation conditions; full defensive pivot.

### 4. Compiled Mechanical Rules in Hot-Path
The warm-path LLM translates abstract market theses into concrete numerical rules written to `PolicyEnvelope.asset_overrides`:
- `entry_obi_threshold` (e.g. `+0.14` L2 book imbalance required before entry)
- `max_rsi_long` (e.g. reject long entry if RSI > 70.0)
- `support_zone_usd` & `resistance_zone_usd`
- `invalidation_price_usd`
- `take_profit_bps` & `stop_loss_bps`

### 5. Configurable Scheduler & Self-Scheduling Wakeups
- Runs periodic strategic evaluations at a configurable base interval (`cognitive_base_interval_sec`, default `120s`).
- The LLM can autonomously schedule an **earlier wakeup** (`next_wakeup_sec` + `wakeup_reason`) when critical Fibonacci levels or Ichimoku cloud boundaries are being tested.

### 6. Budget-Driven Cognitive Routing & Ultra-Low-Cost Frontier Models
- **CostGuard** enforces a daily hard USD spend limit (`MAX_DAILY_LLM_BUDGET_USD`).
- Remaining budget governs cognitive depth:
  - `DEEP_THESIS` (> 60% budget): Exhaustive multi-asset confluence analysis.
  - `TACTICAL_FOCUS` (30% - 60% budget): Rapid zone & invalidation check.
  - `ECO_CONSERVATION` (10% - 30% budget): Minimal parameter refresh.
  - `DETERMINISTIC_LOCK` (< 10% budget): Freezes updates and locks to safe quant baselines.
- Routed via OpenRouter to cost-efficient frontier flash models with automatic fallback:
  - `deepseek/deepseek-v4.1-flash` (`$0.028/M` in, `$0.080/M` out)
  - `z-ai/glm-5.3-flash` (`$0.048/M` in, `$0.160/M` out)
  - `qwen/qwen3.7-flash` (`$0.030/M` in, `$0.130/M` out)
  - `z-ai/glm-5.3` (`$0.079/M` in, `$1.400/M` out)

### 7. Modern Command Center & Remote ZeroTier Access
- **Real-Time Dashboard**: React 19 + Tailwind v4 + Vite with live WebSocket telemetry.
- **Cognitive Panel**: Displays active AI thesis, model used, thinking depth, Ichimoku/Fibonacci confluences, and strategy drawers.
- **Execution Ledger**: Paginated transaction table with order timestamps, fills, and slippage.
- **Testnet/Devnet Telemetry**: Live Solana Devnet wallet balance and real PnL tracking.
- **ZeroTier Remote Ready**: Automatic dynamic host resolution allowing seamless access from remote LAN IPs (e.g. `http://<zerotier-ip>:5173`).

---

## 📂 Repository Structure

```bash
.
├── engine-rs/          # Rust Hot-Path, HardRiskGate & Strategy Pods
│   ├── Cargo.toml
│   └── crates/
│       ├── common/     # Canonical types: MarketEvent, OrderIntent, PolicyEnvelope, AssetOverride
│       ├── risk-gate/  # Synchronous HardRiskGate (<50µs), Kelly sizer, Drawdown kill-switch
│       ├── strategies/ # StrategyPod trait + Pod 1 (Carry), Pod 2 (Momentum), Pod 3 (Solana), Pod 4 (Sniper)
│       ├── exec-router/# Post-Only CEX maker router & Solana Jupiter v6 + Jito bundle simulator
│       ├── backtest/   # Deterministic replay engine (Replay == Paper == Live)
│       └── node/       # CLI runtime binary (robotrader-node)
├── backend/            # Python Warm-Path AI Meta-Controller & FastAPI Control Plane
│   ├── core/           # IPC State Store, StrategyMemoryPalace, Schemas, BaseWarmAgent
│   ├── agents/         # Orchestrator (cognitive loop & scheduler), CatalystScout, CostGuard
│   ├── tools/          # Pro TechnicalAnalysisTool, SocialMacroPanoramaTool, Exchange & Solana RPC
│   ├── tests/          # Architecture, RiskGate, and Warm/Hot path integration tests
│   └── server.py       # FastAPI REST & WebSocket server
├── frontend/           # React 19 + Tailwind CSS v4 Real-Time Command Center
├── docs/               # Architecture Decision Records (ADRs) & Specifications
│   ├── adr/
│   │   ├── 0001-hybrid-quant-agentic-architecture.md
│   │   └── 0002-autonomous-cognitive-warm-path-and-ta-memory.md
└── docker-compose.yml  # Multi-container orchestration (Redis, Backend, Frontend)
```

---

## 🚦 Getting Started

### Prerequisites
- [Docker & Docker Compose](https://docs.docker.com/get-docker/)
- Optional for local development:
  - Rust (stable toolchain 1.80+)
  - Python 3.10+ & Poetry
  - Node.js 20+

### 1. Configuration
Copy `.env.example` to `.env` and fill in your API credentials:
```bash
cp .env.example .env
```
Key configuration items:
```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash
MAX_DAILY_LLM_BUDGET_USD=3.00
COGNITIVE_BASE_INTERVAL_SEC=120
SOLANA_NETWORK=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_WALLET_ADDRESS=FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN
```

### 2. Run with Docker Compose
To build and start all services in the background:
```bash
docker compose up --build -d
```
Access the services:
- **Frontend Command Center**: `http://localhost:5173` (or `http://<your-ip>:5173` remotely)
- **FastAPI Control Plane**: `http://localhost:8000/api/v1/status`
- **Trigger Cognitive Reflection**: `curl -X POST http://localhost:8000/api/v1/cognitive/reflect`

### 3. Run Test Suites

#### Rust Engine & Pod Tests
```bash
cd engine-rs && cargo test
```

#### Python Architecture & Cognitive Tests
```bash
PYTHONPATH=. python3 -m unittest discover -s backend/tests -v
```

#### Build Frontend
```bash
cd frontend && npm run build
```

---

## 📖 Architecture Decision Records (ADRs)

- [**ADR-0001: Hybrid Quant & Agentic Architecture**](docs/adr/0001-hybrid-quant-agentic-architecture.md)  
  *Establishment of the hot-path Rust workspace, synchronous HardRiskGate, Kelly position sizing, and warm-path Python meta-allocation.*
- [**ADR-0002: Autonomous Cognitive Warm-Path, Pro TA & Strategy Palace**](docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md)  
  *Integration of real mathematical TA indicators (Ichimoku, Fibonacci 0.618, RSI, ATR, Bollinger), infinite strategy memory, compiled mechanical rules, self-scheduling wakeups, and budget-driven frontier flash model routing.*

---

## 🛡️ Risk & Safety Invariants

1. **Zero LLM in Hot Path**: Hot-path execution in `engine-rs` never waits for LLM calls.
2. **Capital Preservation**: `CostGuard` halts LLM spend immediately if the daily limit is exhausted.
3. **Fail-Safe Baseline**: If the Warm-Path cognitive loop becomes unreachable, the PolicyEnvelope expires via TTL and drops pods into defensive capital-preservation mode.
4. **Solana Anti-Rug Checks**: Automated freeze-authority and mint-authority verification on all SPL tokens prior to swap routing.

---

## ⚠️ Disclaimer

Robotrader is an experimental, quantitative trading research platform. Cryptocurrency trading carries substantial risk of loss. Always test thoroughly in **Paper** or **Devnet/Testnet** modes before deploying capital.

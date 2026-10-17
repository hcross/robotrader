# Warm-Path AI Agents & Hot-Path Strategy Pods

Robotrader v2 strictly separates **Warm-Path AI Agents** (asynchronous semantic analysis, regime detection, and meta-allocation in Python) from **Hot-Path Strategy Pods** (sub-millisecond deterministic signal generation and execution in Rust).

---

## Part 1: Warm-Path AI Agents (`backend/agents/` — Python & Strands)

These agents never execute raw trades on the hot path. Their output is a structured, schema-validated **`PolicyEnvelope`** published to Redis with a strict TTL (default: 15 minutes).

### 1. Orchestrator Agent (`Orchestrator`)
- **Role**: User Copilot, Command Interpreter & Swarm Supervisor.
- **Input**: Natural language commands from the Web UI (`/ws/chat`) and system alerts from `HardRiskGate` / `QuantAuditor`.
- **Output**:
  - Explains current portfolio positioning, active regime, and PnL attribution to the user.
  - Translates high-level operator directives (e.g., *"Switch to defensive carry-only mode before FOMC"*) into immediate `PolicyEnvelope` overrides.
  - Triggers on-demand backtest or walk-forward runs via the Rust replay engine.

### 2. Catalyst & Narrative Scout (`CatalystScout`)
- **Role**: Unstructured Alpha & Event Extractor.
- **Sources**: Exchange listing announcements (Binance, Upbit, Coinbase), protocol governance proposals, macro economic releases, and on-chain smart-money clustering alerts.
- **Output**: Structured `CatalystSignal` events:
  - `asset`: Target symbol or Solana mint address.
  - `catalyst_type`: `EXCHANGE_LISTING` | `MAINNET_UPGRADE` | `WHALE_ACCUMULATION` | `SECURITY_INCIDENT` | `MACRO_SHOCK`.
  - `conviction`: `0.0` to `1.0`.
  - `directional_bias`: `BULLISH` | `BEARISH` | `NEUTRAL`.
  - `half_life_minutes`: Expected duration of the edge.

### 3. Regime & Meta-Allocator (`MetaAllocator`)
- **Role**: Chief Investment Officer (CIO) / Dynamic Capital Allocator.
- **Inputs**:
  - Quantitative regime metrics computed by the engine (realized volatility, funding rate dispersion, orderbook depth, BTC dominance trend).
  - Active `CatalystSignal` items from `CatalystScout`.
  - Performance decay reports from `QuantAuditor`.
- **Output**: Computes and publishes the active **`PolicyEnvelope`** to Redis:
  - classifies global market regime (`TRENDING_BULL`, `TRENDING_BEAR`, `MEAN_REVERTING_RANGE`, `HIGH_VOL_PANIC`, `LOW_VOL_CARRY`),
  - assigns `capital_weight` (`0.0` to `1.0`, sum $\le 1.0$) across the 4 Rust Strategy Pods,
  - sets per-asset bias and risk multipliers (always clamped by the Rust `HardRiskGate` ceiling).

### 4. Post-Mortem & Drift Auditor (`QuantAuditor`)
- **Role**: Execution Quality & Alpha Decay Analyst.
- **Inputs**: Completed trades, expected fill price vs actual fill price (slippage), maker/taker ratio, and rolling Sharpe per pod.
- **Output**:
  - Detects when a strategy pod suffers from adverse selection or elevated slippage.
  - Recommends down-weighting degraded pods to `MetaAllocator` and surfaces actionable diagnostics in the UI.

### 5. LLM Cost & Model Router (`CostGuard`)
- **Role**: Inference Budget Controller & Tiered Model Router.
- **Responsibility**:
  - Routes routine extraction/classification tasks (`CatalystScout` filtering) to fast, low-cost models (e.g., Gemini Flash / Haiku / Grok Fast) and reserves deep reasoning models for `MetaAllocator` regime shifts.
  - Enforces a hard **daily USD spend cap** (`MAX_DAILY_LLM_BUDGET_USD`, default `$5.00/day`).
  - *Security Change*: Removed unbounded automatic crypto-wallet refills; alerts the operator when budget reaches 80% and degrades gracefully to deterministic baseline rules at 100%.

---

## Part 2: Hot-Path Strategy Pods (`engine-rs/crates/strategies/` — Rust)

Each pod implements the synchronous `StrategyPod` trait in Rust, runs with zero LLM latency, and emits `OrderIntent` structs verified by `HardRiskGate`.

### Pod 1: Delta-Neutral Carry & Basis (`pod-carry`)
- **Horizon**: Hours to Days.
- **Edge**: Captures positive perpetual funding rates (Long Spot / Short Perp) and cross-exchange funding spreads when annualized yield exceeds fee hurdles (e.g., APR > 15%).
- **Why First**: Highest Sharpe ratio, minimal directional market risk, immediate compounding cashflow.

### Pod 2: Intraday Orderflow & Volatility Breakout (`pod-momentum`)
- **Horizon**: 5 minutes to 12 hours.
- **Edge**:
  - Combines L2 Orderbook Imbalance (OBI), Cumulative Volume Delta (CVD) absorption, and ATR/Bollinger volatility compression breakouts on liquid pairs (`SOL`, `BTC`, `ETH`, `JUP`, `SUI`).
  - Uses the `PolicyEnvelope` directional bias and `catalyst_score` from `CatalystScout` as a regime filter to avoid false breakouts in choppy ranges.
- **Execution**: Prioritizes `Post-Only` limit orders to capture maker fees.

### Pod 3: Solana Smart-Money & Catalyst Execution (`pod-solana-alpha`)
- **Horizon**: Minutes to Days.
- **Edge**:
  - Tracks curated high-win-rate Solana wallets and executes momentum/catalyst entries on established Solana ecosystem tokens and verified mid-caps.
  - Enforces strict on-chain safety validation via `HardRiskGate` (revoked Mint/Freeze authorities, locked LP, holder distribution, transaction simulation).
- **Execution**: Routes via Jupiter v6 API and submits via **Jito Block Engine bundles** to prevent sandwich attacks.

### Pod 4: DEX Atomic Pool Sniper (`pod-sniper`)
- **Horizon**: Seconds to Minutes.
- **Edge**:
  - Listens to Raydium/Pump.fun liquidity pool initialization events via low-latency Solana Geyser gRPC / WebSocket logs.
  - Evaluates token contract safety and creator wallet history in `<5ms` in Rust.
  - Executes atomic Jito bundle entry with automated trailing stop-loss and time-based kill exit.
- **Activation**: Disabled by default (`enabled: false` in baseline `PolicyEnvelope`); requires dedicated low-latency Solana RPC/Geyser configuration.

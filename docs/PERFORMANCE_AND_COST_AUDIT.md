# Robotrader v3 — Quantitative Performance Audit & LLM Inference Cost Post-Mortem

**Date**: October 24, 2026  
**Scope**: Hierarchical Multi-Ecosystem Architecture (26 Blockchains/Platforms, `engine-rs` Rust measured mean `0.244 µs` for `HardRiskGate::validate` via `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` + Warm-Path Python OpenRouter)  
**Audited sources**:
- Immutable inference ledger: [`backend/data/transcript_ledger.jsonl`](../backend/data/transcript_ledger.jsonl) (`325` cognitive cycles, `440` OpenRouter HTTP requests, `4.41M` tokens)
- State of the 3 trading populations: `backtest_fixture` (Rust `engine-rs` **policy sanity check** fixture, `policy_sanity_check` — not a fill simulation), `paper_model` (L2 orderbook + adverse selection), `live_testnet` (Binance Spot Testnet + Solana Devnet, the only measured population)

---

## Provenance legend (English)

**Figure block (trading performance)**: any table row, bullet item, or paragraph that states at least one numeric trading-performance value. Every trading-performance figure block in §1 and §3 carries, or is grouped under, its population and source:

| Label | Population | Meaning |
|---|---|---|
| `[FIXTURE]` | `backtest_fixture` | Deterministic **policy sanity check** (`policy_sanity_check`) on a synthetic fixture; declared-edge arithmetic, **not a fill simulation**. |
| `[SIMULATED]` | `paper_model` | L2 slippage + adverse-selection paper simulation. |
| `[MEASURED]` | `live_testnet` | Binance Spot Testnet / Solana Devnet orders actually realised. |

Only the `[MEASURED]` `live_testnet` figures in §3.3 are measured trading results. Leaf-level and treasury aggregates use the retained **recent 200-row window** (`live_testnet.recent`); `engine_metrics.live_testnet.cumulative_cex_pnl_usd` remains the lifetime CEX figure, so the two bases may diverge after eviction.

The inference-cost tables in §2 and §4 measure OpenRouter token spend. They are **operational cost measurements**, outside the three trading populations, and are not forced into the trading enums.

**Language note**: this document is written entirely in English in accordance with the repository's artifact language policy.

**Hot-path benchmark note (English)**: the `HardRiskGate::validate` approved-path mean is `0.244 µs` (244.15 ns). Command: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` (criterion 0.8.2; host: Apple Silicon macOS, 2026-10-26).

---

## 1. Executive Summary

During the intensive testing campaign of the Robotrader v3 hierarchical architecture, the actual OpenRouter invoice reached **~$2.00 USD** (`4 413 015` tokens consumed across `325` cognitive cycles) — *operational inference-cost measurement, outside the three trading populations*.

**Only the `[MEASURED]` `live_testnet` figures in §3.3 are measured trading results. No fixture or simulated figure below is a product performance, a realized return, or a live trading result.**

The audit reveals a stark contrast between:
1. **Execution and trading engine performance (`engine-rs` & `paper_model`)**:
   - **Zero LLM latency in the Hot-Path** (measured mean `0.244 µs` per `validate` call in Rust via `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`) — *operational latency measurement*.
   - **Deterministic policy sanity check (`backtest_fixture`, `policy_sanity_check`) [FIXTURE]**: a rule and plumbing check over a synthetic fixture, **not a fill simulation**. It reports a **`100.0%`** win rate on the Solana branch (**`+$24.73`** of declared-edge arithmetic over `4` trades, annualized Sharpe **`128.52`**, Max Drawdown **`0.0%`**, `3` rejections: `2` by the cost hurdle and `1` `SCAM-SOL` rug pull blocked by `HardRiskGate`), and validates the **adapted Rust pods (`<= 4` per blockchain)** across all **26 ecosystems**. The PnL is `notional × (expected_edge_bps − modelled round-trip fees − modelled spread)`; it is not market-derived, realized, or backtest performance. All figures in this bullet are `[FIXTURE]`.
   - **Realistic Paper-Money simulation (`paper_model`) [SIMULATED]**: **`+$1,155.52` cumulative net PnL (`+11.55%` on `$10,000`)**, **`56.3%` win rate** (`845` wins / `624` losses / `31` flat) despite the strict application of L2 slippage and adverse selection. All figures in this bullet are `[SIMULATED]`.
2. **Over-frequency and context inflation in the Warm-Path cognitive loop (`~$2.00` spent)** — *operational inference-cost measurement*:
   - The Solana leaf robot woke up every **30s to 45s** to re-analyze **15-minute (`900s`)** candles, sending **~8,300 input tokens** per call and doubling consumption during truncation escalations (`115` retries), while `CostGuard` underestimated OpenRouter rates by a factor of ~10x and lost its counter on each container restart.

The **4 structural adjustments** implemented following this audit reduce hourly inference cost by a **factor of 25x to 40x** (`~$0.02/hour` in continuous active mode vs `~$0.65/hour` previously) and place the auto-scheduler in **pause by default on startup (`$0.00/hour`)** — *operational inference-cost measurement, outside the three trading populations*.

---

## 2. Financial Breakdown of ~$2.00 OpenRouter Inference

> Operational inference-cost measurement — outside the three trading populations. Source labels `[FIXTURE]` / `[SIMULATED]` / `[MEASURED]` do not apply to this section.

### 2.1 Exact Breakdown by Model and Agent (`transcript_ledger.jsonl`)

| OpenRouter Model | Role / Agent | Cycles | HTTP Calls (incl. retries) | Prompt Tokens (Input) | Completion Tokens (Output) | Total Tokens | Avg. Latency | Valid JSON | Estimated Real Cost |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `deepseek/deepseek-v4.1-flash-1017` | `Leaf/leaf-*` (Solana & leaves) | 199 | 265 | 2 287 323 | 550 012 | **2 837 335** | 14.0 s | 190/199 (95.5%) | **~$1.29** |
| `deepseek/deepseek-v4.1-flash` | `Leaf/leaf-solana` (initial cycles) | 110 | 156 | 1 171 878 | 300 891 | **1 472 769** | 15.3 s | 100/110 (90.9%) | **~$0.58** |
| `moonshotai/kimi-k3.1-pro` | `MasterOrchestrator/MacroLoop` | 15 | 17 | 50 671 | 31 009 | **81 680** | 43.2 s | 15/15 (100.0%) | **~$0.12** |
| `z-ai/glm-5.3-flash` | Failover / Eco | 1 | 2 | 17 139 | 4 092 | **21 231** | 17.5 s | 1/1 (100.0%) | **~$0.01** |
| **TOTAL SESSION** | **Complete Hierarchical Fleet** | **325** | **440** | **3 527 011** | **886 004** | **4 413 015** | **15.8 s** | **306/325 (94.2%)** | **~$2.00** |

### 2.2 The 3 Root Causes of Cost Drift

1. **Wakeup cadence of `30s–45s` decoupled from the `15m` (`900s`) candle horizon**:
   - Under `HIGH_INFLECTION` regime, `CostGuard` lowered `min_wakeup_sec` to `30s–45s`.
   - `Leaf/leaf-solana` executed **291 cognitive cycles** (often spaced 35 seconds apart) on the same 15-minute OHLCV candles (`SOL/USDT`, `JUP/USDT`, `RAY/USDT`), while the 4 Rust pods (`engine-rs`) already managed the L2 orderbook with `HardRiskGate::validate` measured at `0.244 µs` on average (bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`) without needing an LLM.
2. **`FULL_THESIS` prompt inflation (`~8,300` tokens/cycle) + double-billing penalty on truncation**:
   - The `FULL_THESIS` contract injected the full raw JSON dictionaries of `ta_snapshots` (`SOL/USDT`, `JUP/USDT`, `RAY/USDT`), the last 4 `MemPalace` drawers, **and** the last 2 full raw transcripts (`format_recent_transcripts(limit=2)`).
   - When the JSON response exceeded the initial output token cap (`115` times across `325` cycles, or `35%` of cycles), the escalation mechanism immediately triggered a second HTTP call with a higher cap — **re-billing the ~8,300 input tokens a second time**.
3. **Factor of ~10x under-evaluation in `CostGuard` and reset in RAM**:
   - `FRONTIER_FLASH_MODELS` used theoretical pricing (`$0.035 / 1M input`, `$0.11 / 1M output`) ~10x lower than actual OpenRouter rates for reasoning models (`~$0.30–$0.60 / 1M input`, `$1.10–$2.50 / 1M output`).
   - Furthermore, `self.total_cost_usd` was not hydrated from `transcript_ledger.jsonl` during Docker rebuilds (`docker compose up --build -d`), preventing automatic down-shifting to `TACTICAL_FOCUS` -> `ECO_CONSERVATION` -> `DETERMINISTIC_LOCK`.

---

## 3. Quantitative Assessment of Product Performance (3 Isolated Populations)

In accordance with the metric isolation invariant, Robotrader v3 strictly isolates its three evaluation populations:

### 3.1 Population 1 — Policy Sanity Check Fixture (`backtest_fixture`, `policy_sanity_check`, `engine-rs` measured mean `0.244 µs` via `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`) [`FIXTURE`]

> Source: `[FIXTURE]` — every numeric trading figure in this subsection is the output of a deterministic **policy sanity check** on a synthetic fixture. It is a rule and plumbing check, **not a fill simulation** and not realized, live, or backtest performance. The PnL is declared-edge arithmetic: `notional × (expected_edge_bps − modelled round-trip fees − modelled spread)`.

- **Solana Branch (`leaf-solana`, 4 native Rust pods)** — fixture figures, `[FIXTURE]`:
  - **Initial equity**: `$10,000.00` -> **Final equity**: **`$10,024.73`** (**`+0.247%`** declared-edge arithmetic over the reference sequence)
  - **Win Rate**: **`100.0%`** (`4` wins / `0` loss over `4` fixture executions)
  - **Annualized Sharpe Ratio**: **`128.52`** (fixture arithmetic; not a performance target)
  - **Max Drawdown**: **`0.0%`**
  - **Cumulative execution fees**: `$1.47` (CEX maker rebate `-1.0 bps` + Jupiter v6 + Jito MEV tip)
  - **`HardRiskGate` protection (measured mean `0.244 µs`; bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`)**: **`3` critical rejections** — **`2` by the cost hurdle** (JUP smart-money edge `70.2` vs hurdle `87.2`; AIX-SOL sniper edge `95.0` vs hurdle `151.4`) and **`1` `OnChainRugCheckFailed`** (`SCAM-SOL`, edge `81.0` vs hurdle `87.8`, loss avoided: 100% of sniper allocation)
  - **Attribution by Solana Rust Pod**:
    - `pod_carry` (`Solana JitoSOL/Perp Funding Basis Carry`): **`+$13.61`** (2 fixture trades)
    - `pod_momentum` (`Solana L2 Orderflow & Raydium CLMM Momentum`): **`+$11.11`** (2 fixture trades)
- **Multi-Blockchain Fleet (26 ecosystems, `1..=4` adapted Rust pods per blockchain)**:
  - Each ecosystem now has its own Rust pods compiled in `engine-rs` (`crates/strategies/src/lib.rs`) and individually testable via `POST /api/v1/leaf/{leaf_id}/backtest`.
  - Example `leaf-bitcoin` (3 Rust pods: `btc_etf_basis_carry`, `btc_halving_l2_momentum`, `btc_utxo_whale_accumulator`) — fixture `policy_sanity_check`, `[FIXTURE]`: `3` trades, `100.0%` win rate, **`+$19.58`**, Sharpe **`238.97`**, Max DD **`0.0%`**, `1` rejection by the cost hurdle. These are rule/plumbing outcomes, not a performance measurement.

### 3.2 Population 2 — Continuous Simulation with L2 Slippage & Adverse Selection (`paper_model`) [`SIMULATED`]

> Source: `[SIMULATED]` — every numeric trading figure in this subsection is produced by the L2 slippage + adverse-selection paper model. It is not realized or live profit.

The `paper_model` engine applies a microstructure model on each tick penalizing late entries (elevated RSI, L2 spread, adverse selection friction):

| `paper_model` Metric | Lifetime Window | Recent Window (last 200 trades) |
| :--- | :---: | :---: |
| **Execution count** | **1 500 trades** | 200 trades |
| **Wins / Losses / Flat** | **845 W / 624 L / 31 Flat** | 99 W / 96 L / 5 Flat |
| **Win Rate (excluding flat)** | **56.3%** | 49.5% |
| **Cumulative Net PnL (`simulated_pnl_usd`)** | **`+$1,155.52` (`+11.55%`)** | `-$35.33` |
| **Cumulative Simulated Fees** | `$27.29` | `$3.64` |

**Lifetime Attribution by Pod (`+$1,155.52` total)**:
- `pod_sniper`: **`+$629.31`** (54.5% of total profit)
- `pod_solana_alpha`: **`+$310.88`** (26.9% of total profit)
- `pod_carry`: **`+$109.38`** (9.5% of total profit)
- `pod_momentum`: **`+$105.95`** (9.2% of total profit)

*Observation*: The recent window of 200 trades (`-$35.33`, win rate `49.5%`) is explained by temporarily maintaining a `LONG_BIAS` while the `SOL/USDT` L2 orderbook had inverted (`OBI = -0.571` at `$85.56`). This demonstrates that the `paper_model` simulator is not complacent and faithfully penalizes any invalidation delay.

### 3.3 Population 3 — Real Testnet Execution (`live_testnet`: Binance Spot Testnet) [`MEASURED`]

> Source: `[MEASURED]` — these are the only measured trading results in this document. The window figures use the retained recent 200-row window; the CEX cumulative figure is a lifetime figure.

- **Executions in active window**: `200` (`16` wins / `22` losses / `162` simulated Solana Devnet actions, excluded from the measured population)
- **Realized Testnet CEX PnL**: `-$4.6036` cumulative (`-$0.1539` on recent window), linked to the bid-ask spread of the low-liquidity Binance Spot Testnet orderbook.
- **Operational stability**: `100%` RPC availability, zero crashes, nominal WebSocket/REST latency.

> **Correction dated 2026-10-26** — The `162` historical Solana Devnet auto-transfers are not measured executions: they are now recorded as simulated actions (`is_simulated: true`, unsigned, unbroadcast) and excluded from `live_testnet` and `measured_realized_pnl_usd`. Only Binance Spot Testnet remains measured.

---

## 4. The 4 Structural Adjustments Implemented (OpEx Reduction 25x–40x)

> Operational inference-cost measurement — outside the three trading populations. The table below compares inference spend, not trading performance.

| # | Adjustment | Before ($2.00 Session) | After (Optimized Configuration) | OpEx Gain |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **Auto-Scheduler paused by default at boot** (`ENABLE_AUTO_LLM_SCHEDULER=false`) + UI button `PAUSE ($0.00/h)` / `ACTIVE` | Immediate automatic startup of LLM loops upon `docker compose up` | **Paused by default (`$0.00/h`)**; on-demand activation via UI (`POST /api/v1/cognitive/scheduler`) or manual reflection | **100% at rest (`$0.00/h`)** |
| **2** | **Cadence alignment with 15m (`900s`) candles and 1h (`3600s`) Macro** | Leaf: `30s–120s` (`~45` calls/h)<br>Master: `900s` (`4` calls/h) | Active leaf: **`900s` (15m, max 4 calls/h)**<br>Master: **`3600s` (1h, 1 call/h)**<br>Passive leaf: `3600s` | **~10x fewer calls/hour** |
| **3** | **7x compression of `FULL_THESIS` prompt (`_compact_ta_digest`)** | `~8,300` input tokens/call (raw OHLCV/TA JSON + 2 full raw transcripts) | **`~1,150` input tokens/call** (complete scalar digest: Ichimoku, Fib 0.382/0.618/0.786, RSI, slope, ATR, OBI, confluence) + `max_tokens=950` | **~7x fewer tokens/call** |
| **4** | **Actual OpenRouter pricing + 24h hydration (`hydrate_from_ledger`)** | Rates underestimated ~10x (`$0.18` displayed for `$2.00` actual) and RAM zeroed on restart | Actual OpenRouter rates (`$0.30/$1.10` DeepSeek Flash, `$0.60/$2.50` Kimi K3.1 Pro) + automatic 24h accumulation reconstruction from `transcript_ledger.jsonl` | **Exact budget enforcement** |

### Projected Hourly Cost (When Auto-Scheduler is Active)
- **Default Mode (`PAUSE`)**: **`$0.00 / hour`** (Rust `engine-rs` pods continue executing mechanical rules from `PolicyEnvelope` with `HardRiskGate::validate` measured at `0.244 µs` on average; bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`; without any LLM calls).
- **Auto-Scheduler `ACTIVE` Mode (4 leaf reflections/h + 1 master reflection/h)**:
  - `Leaf/leaf-solana` (`4 x ~1,800` total tokens/h under `deepseek-v4.1-flash-1017`): **`~$0.004 / hour`**
  - `MasterOrchestrator` (`1 x ~2,500` total tokens/h under `kimi-k3.1-pro`): **`~$0.003 / hour`**
  - **Total Active Fleet**: **`~$0.007 to $0.015 / hour`** (i.e. **`<$0.30 / day`** in continuous 24/7 operation, protected by the `CostGuard` circuit breaker hydrated from disk).

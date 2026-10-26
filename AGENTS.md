# Robotrader: AI Coding Agent Guide (AGENTS.md)

Welcome, fellow agent! This document is designed to help you quickly understand the **Robotrader v2** project and how to contribute effectively.

## Project Overview
Robotrader v3 is a **Hierarchical Hybrid Rust/Python Quantitative & Agentic Cryptocurrency Trading Platform** ([ADR-0001](docs/adr/0001-hybrid-quant-agentic-architecture.md), [ADR-0002](docs/adr/0002-autonomous-cognitive-warm-path-and-ta-memory.md), [ADR-0003](docs/adr/0003-hierarchical-multi-ecosystem-architecture.md)).

It strictly separates:
1. **Master Orchestrator & Cross-Chain Treasury (`moonshotai/kimi-k3.1-pro`)**: Holds the Master Portfolio, enforces the `Dry Powder` reserve floor ($\ge 20\%$), prices cross-chain transfer viability (`hurdle_rate_bps = 2.5x round-trip cost`), executes multi-chain/multi-token operator `Checkout` requests, reads across all 26 leaf agents' MemPalace wings (`wing="master_orchestrator"` + `recall_across_wings`), and manages profit-gated/epoch-capped OpenRouter credit auto-refill on a `3600s` (1h) macro cadence.
2. **26 Specialized Blockchain & Venue Leaf Robots (`deepseek/deepseek-v4.1-flash-1017`)**: Each leaf robot is strictly isolated to **one single blockchain** (or dedicated multi-crypto/paper venue), with its own RSS feed (`EcosystemRSSAggregator`), specific TA/on-chain indicators, dedicated MemPalace wing (`wing="leaf_<slug>"`), and `1..=4` ecosystem-adapted Rust Strategy Pods in `engine-rs`. Active leaves operate on a `900s` (15m candle close) cadence.
3. **Deterministic Sub-millisecond Execution, Hard Risk & Simulated Vault (`engine-rs` in Rust)**: Hot-path event processing, order book imbalance (OBI) parsing, `HardRiskGate` validation (measured mean **0.244 µs**, including `validate_inference_refill`; bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`), `SimulatedVault` (`SIMULATED` manifest and receipts across all 26 chains: non-spendable addresses, non-chain-valid audit signatures, and a simulated prefix whitelist — see [`docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md`](docs/CRYPTO_VAULT_AND_KEY_MANAGEMENT.md)), Kelly position sizing, multi-chain on-chain anti-rug / honeypot checks (`OnChainTokenSafety`), and zero LLM latency.
4. **Cost-Controlled Warm-Path Scheduling ([`docs/PERFORMANCE_AND_COST_AUDIT.md`](docs/PERFORMANCE_AND_COST_AUDIT.md))**: Background LLM scheduling is paused by default on startup (`ENABLE_AUTO_LLM_SCHEDULER=false`, `$0.00/h`) and can be toggled in the UI (`POST /api/v1/cognitive/scheduler`). `CostGuard` uses realistic OpenRouter pricing and hydrates rolling 24h spend from `backend/data/transcript_ledger.jsonl`.

## Mandatory Delivery Workflow (SDLC)

Every change follows the right-sized workflow in [`sdlc/PROTOCOL.md`](sdlc/PROTOCOL.md).
No direct commits to `master`. No agent merges without explicit written human delegation.

| Lane | Use when | Artifacts | Cold reviews |
|---|---|---|---|
| **M** — Micro | ≤ 2 files, one module, no contract/money/risk/vault change, existing tests cover it | issue + PR | dev |
| **S** — Standard | new behavior, 3–10 files, one service, additive contract | proposal + delta specs + tasks | spec, dev |
| **L** — Large | breaking contract, money/risk/vault path, > 10 files, cross-stack, migration, ADR | proposal + specs + design + tasks | spec, plan, dev |

Hard rules:

- **One change = one issue logbook + one branch in `.worktrees/<issue>-<slug>` + one PR.**
- **Separate minds**: the author never reviews; reviewers are cold-start instances.
- **Three review rounds per stage**, then escalate to a human. A fourth round is rejected by the tooling.
- **Reviewers resume from the ledger** (`.sdlc/<change-id>/reviews/`), never from the author's chat.
- **Specs are OpenSpec-compatible** (`openspec/`), with a ≤ 400-word Review Card and ≥ 1 diagram (≤ 5 min).
- **No secrets or keys** in specs, verdicts, evidence, briefs, or dossiers.
- **Preserve the platform invariants** listed in `openspec/config.yaml` and `sdlc/checklists/dev.md`.

Start and drive a change:

```bash
scripts/sdlc/sdlc.sh start <change-id> --title "<title>" --lane <M|S|L> --reason "<why this lane>"
scripts/sdlc/sdlc.sh next <change-id>
scripts/sdlc/run-agent.sh <role> .sdlc/<change-id>/briefs/<stage>-r<N>-<role>.md
scripts/sdlc/sdlc.sh verdict <change-id> <stage> <round> <verdict-file>
scripts/sdlc/sdlc.sh merge-ready <change-id>
```

Agent profiles are canonical in `sdlc/agents/` and generated into `.claude/agents/`
(Claude Code) and `.agent/agents/` (Antigravity CLI). Run
`scripts/sdlc/install-agents.sh --check` after editing a profile.

Human guide: [`docs/sdlc/README.md`](docs/sdlc/README.md) · Decision record:
[`docs/adr/0004-agentic-sdlc.md`](docs/adr/0004-agentic-sdlc.md).

## Tech Stack
- **Hot-Path & Replay Engine (`engine-rs`)**: Rust (Edition 2021), Cargo Workspace (`common`, `risk-gate`, `strategies`, `exec-router`, `backtest`, `node`), Serde, Tokio.
- **Warm-Path AI & Control Plane (`backend`)**: Python 3.10+, FastAPI, Poetry, `strands-agents`, OpenRouter / LiteLLM, CCXT, Solana RPC.
- **IPC & State Bus**: Redis 7 (with in-memory fallback + TTL expiration for offline/local tests).
- **Frontend (`frontend`)**: React 19, Vite (Rolldown), Tailwind CSS v4, Lucide React (with ZeroTier dynamic hostname resolution).
- **Infrastructure**: Multi-stage Docker builds, Docker Compose, Helm charts (`charts/robotrader`).

## Project Structure
```bash
.
├── engine-rs/          # Rust Hot-Path, HardRiskGate, 4 Strategy Pods & Backtest Workspace
│   ├── Cargo.toml
│   └── crates/
│       ├── common/     # Canonical types: MarketEvent, OrderIntent (token_safety: OnChainTokenSafety), PolicyEnvelope
│       ├── risk-gate/  # Synchronous HardRiskGate (measured 0.244µs), SimulatedVault (26 chains, SIMULATED), Kelly sizer, OnChainTokenSafety anti-rug
│       ├── strategies/ # StrategyPod trait + Pod 1 (Carry), Pod 2 (Momentum), Pod 3 (OnChainAlphaPod), Pod 4 (DexSniperPod)
│       ├── exec-router/# Post-Only CEX maker router & On-Chain DEX Aggregator + Atomic MEV bundle simulator
│       ├── backtest/   # Unified deterministic replay engine (Backtest == Paper == Live)
│       └── node/       # CLI & runtime binary (`robotrader-node`)
├── backend/            # Python Warm-Path AI Meta-Controller & FastAPI Control Plane
│   ├── core/           # IPC State Store, schemas (mirroring engine-rs/common), BaseWarmAgent, StrategyMemoryPalace
│   ├── agents/         # Orchestrator (cognitive scheduler & reflection), CatalystScout, MetaAllocator, QuantAuditor, CostGuard
│   ├── tools/          # Pro TechnicalAnalysisTool, SocialMacroPanoramaTool, Exchange & Solana RPC tools
│   ├── tests/          # End-to-end Python <-> Rust integration & architecture tests
│   └── server.py       # FastAPI REST + WebSocket entrypoint
├── frontend/           # React 19 + Tailwind v4 Real-Time Command Center (ZeroTier & Devnet friendly)
└── docs/               # ADRs (ADR-0001, ADR-0002), Architecture & Agent/Pod specifications
```

> **Hot-path budget evidence.** `HardRiskGate::validate` measured mean: **0.244 µs** (244.15 ns). Command: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` (criterion 0.8.2; host: Apple Silicon macOS, 2026-10-26).

## How to Run & Test

### 1. Run Rust Engine & Backtest Tests
```bash
cd engine-rs && cargo test
```

### 2. Run Python Warm-Path & Architecture Tests
The suite is an integration suite: build the Rust engine binary first.
```bash
cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node
PYTHONPATH=. python3 -m unittest discover -s backend/tests -v
```

### 3. Build Frontend
```bash
cd frontend && npm run build
```

### 4. Start Full Stack with Docker Compose
```bash
docker compose up --build -d
```
- **Backend API**: `http://localhost:8000/api/v1/status`
- **Frontend Dashboard**: `http://localhost:5173` (or via ZeroTier: `http://<zerotier-ip>:5173`)

## Coding Guidelines for Agents
- **Zero LLM in the Hot Path**: Never place LLM calls, blocking HTTP calls, or unbounded sleeps inside `StrategyPod::on_market_event` or `HardRiskGate::validate`.
- **PolicyEnvelope Contract**: Keep `engine-rs/crates/common/src/lib.rs` and `backend/core/schemas.py` strictly synchronized. `AssetOverride` carries all eleven keys: required `catalyst_score`, `bias`, `max_leverage`, plus optional `support_zone_usd`, `resistance_zone_usd`, `invalidation_price_usd`, `entry_obi_threshold`, `max_rsi_long`, `min_rsi_short`, `take_profit_bps`, `stop_loss_bps`. Policy decoding is strict (`deny_unknown_fields`): an undeclared key fails the node instead of being dropped. `MarketEvent::OrderbookTick.rsi_14` is optional; with an override present and no value, the RSI guard reports `RSI=INACTIVE` until a warm-path producer exists.
- **Strategy Palace Continuity**: Always query and persist reflection drawers via `StrategyMemoryPalace` in `wing="strategy_ledger"`. Ensure every cycle explicitly qualifies continuity (`INIT_THESIS`, `CONFIRMED`, `REFINED`, `INVALIDATED`).
- **No Module Shadowing**: Warm-Path infrastructure lives in `backend/core/` so the external `strands-agents` package (`import strands`) is never shadowed.
- **Capital Protection & Token Budgeting**: `CostGuard` (`backend/agents/monitor.py`) enforces a hard daily USD spend limit (`MAX_DAILY_LLM_BUDGET_USD`) and modulates thinking depth (`DEEP_THESIS` -> `TACTICAL_FOCUS` -> `ECO_CONSERVATION` -> `DETERMINISTIC_LOCK`). Never re-introduce unbounded automatic wallet refills.
- **Mandatory Deployment Check**: When making modifications to backend or frontend services, always verify with `docker compose up --build -d` so changes are immediately observable in production.

# ADR-0002: Autonomous Warm-Path Cognitive Loop, Pro Technical Analysis Toolbelt, Infinite Strategy Memory, and Budget-Driven Frontier Routing

- **Status**: Proposed
- **Date**: 2026-10-19
- **Deciders**: Hoani Cross, Antigravity
- **Supersedes / Extends**: [ADR-0001](0001-hybrid-quant-agentic-architecture.md)

---

## 1. Context and Problem Statement

In [ADR-0001](0001-hybrid-quant-agentic-architecture.md), we separated the sub-millisecond Rust Hot-Path (`engine-rs`) from the Python Warm-Path (`backend/agents/`). However, the initial Warm-Path implementation remained passive:
1. It relied on static seed catalysts and keyword-based chat routing rather than live LLM reasoning.
2. It lacked a professional **Technical Analysis (TA) toolbelt** (Ichimoku Kinko Hyo, RSI divergences, Fibonacci retracements/extensions, ATR/Bollinger volatility squeezes) and **Social/Macro narrative aggregation** to form and verify trading intuitions.
3. It had no **persistent episodic/semantic memory** (MemPalace style) to record its observations, hypotheses, and invalidation levels across cycles—risking amnesia between evaluations.
4. It ran on a static TTL rather than a **self-scheduling cognitive loop** capable of waking up earlier when price approaches a critical confluence zone (e.g., Ichimoku Kumo edge + 0.618 Fibonacci).
5. It lacked **budget-aware reasoning depth** tied to ultra-low-cost near-frontier models (`deepseek/deepseek-v4.1-flash`, `z-ai/glm-5.3-flash`, `qwen/qwen3.7-flash`).

---

## 2. Decision Outcome

We introduce an **Autonomous Cognitive Warm-Path Loop** structured around five pillars while strictly preserving the **Zero-LLM-in-the-Hot-Path** invariant:

### Pillar 1: Pro Technical Analysis & Social/Macro Panorama Toolbelt (`backend/tools/ta_tools.py`)
Before reasoning, the Warm-Path gathers a deterministic multi-timeframe quantitative & narrative snapshot:
- **Ichimoku Kinko Hyo (9, 26, 52)**: Tenkan-sen, Kijun-sen, Senkou Span A & B (Kumo cloud boundaries), TK-cross state, and price position (`ABOVE_KUMO`, `INSIDE_KUMO`, `BELOW_KUMO`).
- **RSI (14) & Momentum Regime**: Exact RSI value, slope, overbought/oversold regime, and divergence flags.
- **Fibonacci Confluence Zones**: Swing High / Swing Low detection with `0.236`, `0.382`, `0.500`, `0.618` (Golden Pocket), `0.786` retracements and `1.272` / `1.618` extensions.
- **Macro & Social Narrative Radar**: Aggregated sentiment score, narrative tags (e.g., Solana DEX volume surge, CEX funding anomalies, whale accumulation), and L2 Orderbook Imbalance (OBI).

### Pillar 2: Infinite Strategy Memory ("Strategy Palace" — `backend/core/memory_palace.py`)
Inspired by **MemPalace**, the strategist stores and queries structured drawers organized by **Wings** and **Rooms** (persisted in Redis + JSONL disk store):
- `wing="panorama" / room="macro_social"`: Social narratives, whale flows, macro regime shifts.
- `wing="ta_confluences" / room="ichimoku_fib_rsi"`: Key technical setups and support/resistance zones.
- `wing="strategy_ledger" / room="active_theses"`: Every strategic decision, its **hypothesis**, its **invalidation price**, and the **post-mortem outcome** of the previous cycle's thesis.
- **Logical Continuity**: Every LLM prompt injects the latest drawers from `strategy_ledger` so the strategist must explicitly **CONFIRM**, **REFINE**, or **INVALIDATE** its prior thesis before emitting new rules.

### Pillar 3: Mechanical Rule Compilation into the Rust Hot-Path (`PolicyEnvelope` v2)
The LLM translates its high-level thesis into **explicit mechanical execution rules** compiled into `PolicyEnvelope` and enforced in `<50µs` by the Rust pods (`engine-rs`) and Live Execution Loop:
- Per-asset `support_zone_usd` (Fibonacci 0.618 / Kijun) and `resistance_zone_usd`,
- `entry_obi_threshold` (required L2 orderbook imbalance to trigger execution),
- `take_profit_bps`, `stop_loss_bps`, and `invalidation_price_usd`,
- Per-pod `capital_weight` and `directional_bias` (`LONG_BIAS`, `SHORT_BIAS`, `NEUTRAL`).

### Pillar 4: Configurable Periodic Reflection + Autonomous Early Wakeup (`CognitiveScheduler`)
- The Warm-Path runs on a configurable base period (`base_interval_sec`, default `180s` in Testnet / `600s` in Prod).
- At the end of each reflection, the LLM decides its own **`next_wakeup_sec`** (e.g., shortening the wakeup to `30s–60s` when price is testing a Fibonacci `0.618` + Ichimoku Kumo support, or extending it to `300s+` in a dead range) with an explicit `wakeup_reason`.

### Pillar 5: Budget-Driven Cognitive Depth & Ultra-Low-Cost Frontier Model Routing (`CostGuard`)
We select near-frontier models with ultra-low token pricing on OpenRouter:

| Model Tier | OpenRouter Slug | Input ($/1M) | Output ($/1M) | Role |
| :--- | :--- | :---: | :---: | :--- |
| **Primary Flash** | `openrouter/deepseek/deepseek-v4.1-flash` | `$0.028` | `$0.080` | Default high-IQ quant & TA synthesis |
| **Co-Primary Flash** | `openrouter/z-ai/glm-5.3-flash` | `$0.048` | `$0.160` | Structured tool/JSON strategy compilation |
| **Fallback Flash** | `openrouter/qwen/qwen3.7-flash` | `$0.030` | `$0.130` | Fast fallback |
| **Deep Inflection** | `openrouter/z-ai/glm-5.3` | `$0.079` | `$1.400` | Major regime inflection (only if budget > 60%) |

The remaining daily budget ratio ($R = \text{remaining\_usd} / \text{daily\_budget\_usd}$) dynamically governs the **Cognitive Depth (`thinking_depth`)**:
1. **`DEEP_THESIS` ($R > 50\%$)** : Full multi-indicator TA + social panorama + 5 memory drawers + allowed early wakeup (`min 30s`).
2. **`TACTICAL_FOCUS` ($20\% < R \le 50\%$)** : Compact TA summary + 2 memory drawers + `deepseek-v4.1-flash` mandatory + wakeup floor `90s`.
3. **`ECO_CONSERVATION` ($5\% < R \le 20\%$)** : Minimal token footprint (`max_tokens=350`) + wakeup floor `300s`.
4. **`DETERMINISTIC_LOCK` ($R \le 5\%$)** : LLM calls suspended; Rust Hot-Path operates autonomously on existing mechanical rules.

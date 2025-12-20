# Agent Definitions

This document defines the roles and responsibilities of each agent in the Robotrader swarm.

## 1. Orchestrator Agent (`Orchestrator`)
-   **Role**: Team Lead / Manager.
-   **Input**: User natural language commands via Web UI.
-   **Output**: Commands to other agents; Status updates to User.
-   **Tools**: `AgentManager` (spawn/kill agents), `StrategyPlanner`.
-   **Personality**: Professional, cautious, strategic.

## 2. LLM Monitor Agent (`CostGuard`)
-   **Role**: Accountant & Resource Manager.
-   **Responsibility**:
    -   Monitor token usage of all other agents.
    -   Calculate real-time costs.
    -   **CRITICAL**: Auto-refill OpenRouter credits using a dedicated crypto wallet when balance is low.
-   **Tools**: `OpenRouterAPI`, `SolanaTransferTool`.

## 3. Market Analysis Agents

### A. Trend Watcher (`TrendScout`)
-   **Role**: Sentiment Analyst.
-   **Source**: Twitter (X), Reddit, Crypto News sites.
-   **Output**: Sentiment Score (-1.0 to +1.0), Trending Topics.
-   **Tools**: `WebSearch`, `SocialMediaAPI`.

### B. Technical Analyst (`Chartist`)
-   **Role**: Quantitative Analyst.
-   **Source**: Price feeds (Binance, Pyth, Chainlink).
-   **Output**: Technical Indicators (RSI, MACD, Bollinger Bands).
-   **Tools**: `TaLib`, `PriceFeedAPI`.

## 4. Trading Agents

### A. Sniper Agent (`Sniper`)
-   **Strategy**: High risk, high speed. Looks for new pool launches or arbitrage.
-   **Tools**: `JupiterAggregator`, `RaydiumSDK`.
-   **Risk Profile**: Aggressive.

### B. Swing Trader (`Swinger`)
-   **Strategy**: Medium term. Follows trends identified by `TrendScout` and `Chartist`.
-   **Tools**: `BinanceAPI`, `JupiterAggregator`.
-   **Risk Profile**: Moderate.

### C. Portfolio Manager (`Allocator`)
-   **Role**: Risk Controller.
-   **Responsibility**:
    -   Rebalance portfolio across assets.
    -   Approve/Deny trade requests from other agents based on global risk settings.

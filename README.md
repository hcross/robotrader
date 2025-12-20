# Robotrader 🤖📈

**Robotrader** is an advanced, multi-agent cryptocurrency trading application designed to manage and grow a crypto portfolio autonomously.

## 🚀 Vision

The goal is to simulate a professional trading team working for a single client (you). The system comprises multiple specialized AI agents that communicate via the **A2A (Agent-to-Agent) Protocol** to analyze markets, execute trades, and manage risk.

## ✨ Key Features

-   **Multi-Agent Architecture**: Powered by the **Strands** framework.
-   **Orchestrated Strategy**: A central "Orchestrator" agent translates user goals into actionable trading strategies.
-   **Multi-Chain & Multi-Exchange**:
    -   **Solana** focus (initial iteration).
    -   **CEX**: Binance.
    -   **DEX**: Jupiter, Raydium, Orca.
-   **Smart Analysis**: Agents dedicated to Sentiment Analysis (Web/Socials) and Technical Analysis.
-   **Cost-Aware**: Built-in **LLM Monitor Agent** that tracks API usage and auto-refills OpenRouter credits using crypto.
-   **Modern UI**: Sleek React-based dashboard for monitoring and chatting with your agent team.
-   **Secure**: Enterprise-grade security practices for key management.

## 🛠️ Technology Stack

-   **AI/Agents**: Python, Strands Framework, LiteLLM (OpenRouter/Grok 4.1 Fast).
-   **Frontend**: React, Vite, TailwindCSS.
-   **Infrastructure**: Docker Compose, Helm Charts.

## 📂 Documentation

-   [Architecture Overview](docs/architecture.md)
-   [Agent Definitions](docs/agents.md)
-   [Implementation Plan](GEMINI.md)

## 🚦 Getting Started

### Prerequisites

-   Docker & Docker Compose
-   Python 3.10+
-   Node.js 18+

### Installation

1.  Clone the repository.
2.  Copy `.env.example` to `.env` and fill in your API keys.
3.  Run `docker-compose up -d`.

## ⚠️ Disclaimer

This software is for educational and experimental purposes. Cryptocurrency trading involves significant risk. The authors are not responsible for financial losses.

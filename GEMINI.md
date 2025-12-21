# Robotrader: AI Coding Agent Guide (GEMINI.md)

Welcome, fellow agent! This document is designed to help you quickly understand the **Robotrader** project and how to contribute effectively.

## Project Overview
Robotrader is a multi-agent cryptocurrency trading bot framework built with a Python backend and a React frontend. It uses an agent-based architecture where different agents (Orchestrator, Monitor, etc.) communicate to execute trading strategies.

## Tech Stack
- **Backend**: Python 3.10+, FastAPI, Poetry, LiteLLM (for AI agent logic), CCXT (for exchange interaction), Solana (for blockchain interaction).
- **Frontend**: React 19, Vite (Rolldown), Tailwind CSS v4, Lucide React, Axios.
- **Infrastructure**: Docker Compose, Dockerfiles for both frontend and backend.
- **Deployment**: Helm charts for Kubernetes deployment.

## Project Structure
```bash
.
├── backend/            # Python backend source code
│   ├── agents/         # AI agent implementations
│   ├── config.py       # Configuration and env var loading
│   ├── server.py       # FastAPI application entry point
│   ├── strands/        # Core agent framework (A2A messaging, base classes)
│   ├── tools/          # Tooling for agents (exchange interactions, etc.)
│   ├── pyproject.toml  # Poetry dependencies
│   └── poetry.lock
├── frontend/           # React frontend source code
│   ├── src/            # Components, hooks, and logic
│   ├── Dockerfile      # Node 22 based build
│   ├── package.json    # Dependencies and scripts
│   └── tailwind.config.js # Tailwind CSS configuration
├── docs/               # Technical documentation
│   ├── architecture.md # Detailed architectural overview
│   └── agents.md       # Agent-specific details
├── Dockerfile.backend  # Backend Docker image definition
├── docker-compose.yml  # Orchestrates development services
└── charts/             # Helm charts for K8s
```

## How to Run
### Local Docker Development
To start the entire stack:
```bash
docker compose up --build
```
- **Backend API**: `http://localhost:8000`
- **Frontend UI**: `http://localhost:5173`

## Coding Guidelines for Agents
- **Dependency Management**: Use Poetry for backend (`backend/pyproject.toml`) and npm for frontend (`frontend/package.json`).
- **Tailwind v4**: Note that this project uses Tailwind CSS v4. Use `@import "tailwindcss";` in `index.css` and the `@tailwindcss/postcss` plugin.
- **Agent Communication**: Agents inherit from `BaseAgent` and use the `send/receive` pattern defined in `backend/strands/`.
- **Environment Variables**: Always check `backend/config.py` when adding new external services or API keys. Use a `.env` file in the root.

## Verified Fixes (Dec 2025)
- Backend Docker build uses `backend/` directory as context for configuration files.
- Frontend uses `node:22-alpine` to satisfy Vite requirements.
- `.dockerignore` excludes local `node_modules` to prevent architecture mismatches.
- `Any` is correctly imported in `backend/strands/agent.py`.

Happy coding!

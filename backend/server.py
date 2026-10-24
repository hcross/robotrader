from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agents.orchestrator import OrchestratorAgent
from .core.schemas import Message
from .core.state_store import state_store
from .core.transcript_palace import transcript_palace

app = FastAPI(
    title="Robotrader v2 Hybrid Control Plane",
    version="0.2.0",
    description="Warm-Path AI Meta-Controller & Telemetry Gateway for engine-rs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = OrchestratorAgent(store=state_store)
state_store.start_live_worker(interval_sec=10.0)
orchestrator.start_cognitive_scheduler()


class ChatRequest(BaseModel):
    command: str


class RegimeRequest(BaseModel):
    preset: str


class KillSwitchRequest(BaseModel):
    active: bool
    reason: str = "Manual operator request"


class CognitiveConfigRequest(BaseModel):
    base_interval_sec: int | None = None
    preferred_model: str | None = None


@app.get("/api/v1/status")
def get_system_status() -> Dict[str, Any]:
    bt = state_store.run_rust_backtest()
    policy = state_store.get_effective_policy().to_dict()
    cost_status = orchestrator.cost_guard.get_status()
    catalysts = [c.to_dict() for c in state_store.recent_catalysts]

    return {
        "architecture": "hybrid_rust_python_v2",
        "kill_switch": {
            "active": state_store.kill_switch_active,
            "reason": state_store.kill_switch_reason,
            "max_daily_drawdown_limit_pct": 3.0,
        },
        "policy_envelope": policy,
        "engine_metrics": {
            "initial_equity_usd": bt.get("initial_equity_usd", 10000.0),
            "final_equity_usd": round(float(bt.get("final_equity_usd", 10000.0)), 2),
            "net_profit_usd": round(float(bt.get("net_profit_usd", 0.0)), 2),
            "total_return_pct": round(float(bt.get("total_return_pct", 0.0)), 3),
            "max_drawdown_pct": round(float(bt.get("max_drawdown_pct", 0.0)), 2),
            "sharpe_ratio": round(float(bt.get("sharpe_ratio", 0.0)), 2),
            "win_rate_pct": round(float(bt.get("win_rate_pct", 0.0)), 1),
            "total_trades": bt.get("total_trades", 0),
            "rejected_orders": bt.get("rejected_orders", 0),
            "total_fees_usd": round(float(bt.get("total_fees_usd", 0.0)), 2),
            "pod_pnl_attribution": bt.get("pod_pnl_attribution", {}),
            "executions": bt.get("executions", []),
        },
        "catalysts": catalysts,
        "cost_guard": cost_status,
        "testnet_telemetry": state_store.get_testnet_telemetry(),
        "cognitive_engine": orchestrator.get_cognitive_state(),
    }


@app.get("/api/v1/llm/calls")
def list_llm_calls(
    offset: int = 0,
    limit: int = 50,
    agent: str | None = None,
    model: str | None = None,
    depth: str | None = None,
) -> Dict[str, Any]:
    """
    Production LLM inspection feed (backlog ADR-0002): raw-reasoning transcripts —
    prompts, completions, per-attempt failover, tool calls, latency/cost — served
    on demand, not on the 4s-polling `/status` lane.
    """
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    page, total = transcript_palace.list_entries(
        offset=offset,
        limit=limit,
        agent=agent or None,
        model=model or None,
        thinking_depth=depth or None,
    )
    return {"calls": page, "total": total, "offset": offset, "limit": limit}


@app.post("/api/v1/cognitive/reflect")
def trigger_cognitive_reflection() -> Dict[str, Any]:
    return orchestrator.run_strategic_reflection(force=True, trigger_source="UI_MANUAL_TRIGGER")


@app.post("/api/v1/cognitive/config")
def configure_cognitive_engine(req: CognitiveConfigRequest) -> Dict[str, Any]:
    return orchestrator.update_cognitive_config(
        base_interval_sec=req.base_interval_sec,
        preferred_model=req.preferred_model,
    )


@app.post("/api/v1/backtest/run")
def run_backtest() -> Dict[str, Any]:
    bt = state_store.run_rust_backtest()
    return {
        "status": "completed",
        "policy_envelope_id": state_store.get_effective_policy().envelope_id,
        "summary": bt,
    }


@app.post("/api/v1/policy/regime")
def set_regime(req: RegimeRequest) -> Dict[str, Any]:
    env = orchestrator.meta_allocator.apply_regime_preset(req.preset)
    bt = state_store.run_rust_backtest(env)
    return {
        "status": "updated",
        "policy_envelope": env.to_dict(),
        "backtest_summary": bt,
    }


@app.post("/api/v1/risk/kill")
def toggle_kill_switch(req: KillSwitchRequest) -> Dict[str, Any]:
    state = state_store.set_kill_switch(req.active, req.reason)
    bt = state_store.run_rust_backtest()
    return {
        "status": "ok",
        "kill_switch": state,
        "backtest_summary": bt,
    }


@app.post("/api/v1/chat")
def post_chat_command(req: ChatRequest) -> Dict[str, Any]:
    return orchestrator.process_user_command(req.command)


@app.get("/api/v1/testnet/verify")
def verify_testnet_connectivity() -> Dict[str, Any]:
    from .tools.exchange_tools import BinanceTool
    from .tools.solana_tools import SolanaWalletTool

    binance = BinanceTool()
    solana = SolanaWalletTool()
    return {
        "binance_testnet": {
            "authenticated": binance.authenticated,
            "sol_usdt_price": binance.get_price("SOL/USDT"),
            "balance": binance.get_usdt_balance(),
        },
        "solana_wallet": {
            "rpc_url": solana.rpc_url,
            "public_key": str(solana.keypair.pubkey()) if solana.keypair else None,
            "balance_sol": solana.get_balance(),
        },
    }


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = orchestrator.receive(
                Message(
                    sender="User",
                    recipient="Orchestrator",
                    msg_type="USER_COMMAND",
                    content=data,
                )
            )
            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        pass

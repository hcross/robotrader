from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agents.orchestrator import OrchestratorAgent
from .core.health import health_router
from .core.hierarchy import CrossChainTreasuryRouter
from .core.schemas import Message
from .core.state_store import state_store
from .core.transcript_palace import transcript_palace
from .tools.rss_tools import EcosystemRSSAggregator

app = FastAPI(
    title="Robotrader v3 Hierarchical Multi-Ecosystem Control Plane",
    version="0.3.0",
    description="Master Orchestrator (Kimi K3.1 Pro) + 26 Ecosystem Leaf Robots (DeepSeek v4.1 Flash 1017) & engine-rs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)

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
    auto_scheduler_enabled: bool | None = None


class SchedulerToggleRequest(BaseModel):
    enabled: bool


class TreasuryDepositRequest(BaseModel):
    amount_usd: float
    token: str = "USDC"
    source_chain: str = "Solana"
    note: str = ""


class TreasuryCheckoutRequest(BaseModel):
    amount_usd: float
    target_chain: str = "Solana"
    target_token: str = "SOL"
    destination_address: str = ""
    quote_only: bool = False


class BridgeEvaluationRequest(BaseModel):
    from_chain: str = "Solana"
    to_chain: str = "Ethereum"
    amount_usd: float = 2500.0
    expected_yield_bps: float = 85.0
    horizon_days: int = 7


class LeafMandateRequest(BaseModel):
    risk_posture: str | None = None
    allocated_capital_usd: float | None = None


class LeafLiquidateRequest(BaseModel):
    reason: str = "Directive opérateur / protection d'écosystème"


class OpenRouterRefillRequest(BaseModel):
    amount_usd: float | None = None
    force: bool = True


@app.get("/api/v1/status")
def get_system_status() -> Dict[str, Any]:
    bt = state_store.run_rust_backtest()
    populations = state_store.get_population_metrics(bt)
    live_window = list(state_store.live_executions[:200])
    policy = state_store.get_effective_policy().to_dict()
    cost_status = orchestrator.cost_guard.get_status()
    catalysts = [c.to_dict() for c in state_store.recent_catalysts]

    # One ledger, one declared source: never interleave fixture rows with live ones.
    executions = live_window if live_window else list(bt.get("executions", []))
    hierarchy_snap = state_store.hierarchy.get_hierarchy_snapshot(
        cost_status=cost_status,
        solana_populations=populations,
    )

    return {
        "architecture": "hybrid_rust_python_v2",
        "hierarchy_version": "v3_hierarchical_multi_ecosystem",
        "kill_switch": {
            "active": state_store.kill_switch_active,
            "reason": state_store.kill_switch_reason,
            "max_daily_drawdown_limit_pct": 3.0,
        },
        "policy_envelope": policy,
        "engine_metrics": {
            # Three populations, each measured on its own PnL column. See
            # HybridStateStore.get_population_metrics for the contract.
            "backtest_fixture": populations["backtest_fixture"],
            "paper_model": populations["paper_model"],
            "live_testnet": populations["live_testnet"],
            "executions": executions,
            "executions_source": "live_testnet" if live_window else "backtest_fixture",
        },
        "catalysts": catalysts,
        "cost_guard": cost_status,
        "testnet_telemetry": state_store.get_testnet_telemetry(),
        "cognitive_engine": orchestrator.get_cognitive_state(),
        "solana_rss": EcosystemRSSAggregator.get_feed_for_agent("leaf-solana", max_items=5),
        "hierarchy": hierarchy_snap,
    }


@app.get("/api/v1/hierarchy")
def get_hierarchy_status() -> Dict[str, Any]:
    bt = state_store.run_rust_backtest()
    populations = state_store.get_population_metrics(bt)
    cost_status = orchestrator.cost_guard.get_status()
    return state_store.hierarchy.get_hierarchy_snapshot(
        cost_status=cost_status,
        solana_populations=populations,
    )


@app.post("/api/v1/treasury/deposit")
def deposit_to_master_treasury(req: TreasuryDepositRequest) -> Dict[str, Any]:
    return state_store.hierarchy.deposit_funds(
        amount_usd=req.amount_usd,
        token=req.token,
        source_chain=req.source_chain,
        note=req.note,
    )


@app.post("/api/v1/treasury/checkout")
def checkout_from_master_treasury(req: TreasuryCheckoutRequest) -> Dict[str, Any]:
    return state_store.hierarchy.checkout_funds(
        amount_usd=req.amount_usd,
        target_chain=req.target_chain,
        target_token=req.target_token,
        destination_address=req.destination_address,
        quote_only=req.quote_only,
    )


@app.post("/api/v1/treasury/evaluate-bridge")
def evaluate_cross_chain_bridge(req: BridgeEvaluationRequest) -> Dict[str, Any]:
    return CrossChainTreasuryRouter.evaluate_transfer_viability(
        from_chain=req.from_chain,
        to_chain=req.to_chain,
        amount_usd=req.amount_usd,
        expected_yield_bps=req.expected_yield_bps,
        horizon_days=req.horizon_days,
    )


@app.get("/api/v1/vault/manifest")
def get_vault_enclave_manifest() -> Dict[str, Any]:
    """
    Returns the public-only HD wallet manifest (`BIP-32` / `BIP-44` / `SLIP-0010`)
    exported by `RustVaultEnclave` in `engine-rs` for all 26 blockchains.
    """
    return state_store.hierarchy.vault_manifest


@app.post("/api/v1/master/reflect")
def trigger_master_reflection() -> Dict[str, Any]:
    return orchestrator.run_master_orchestrator_reflection(
        force=True, trigger_source="UI_MASTER_TRIGGER"
    )


@app.get("/api/v1/leaf/{leaf_id}")
def get_leaf_detail(leaf_id: str) -> Dict[str, Any]:
    return state_store.hierarchy.get_leaf_detail(leaf_id)


@app.post("/api/v1/leaf/{leaf_id}/reflect")
def trigger_leaf_reflection(leaf_id: str) -> Dict[str, Any]:
    return orchestrator.run_leaf_agent_reflection(
        leaf_id=leaf_id, trigger_source="UI_LEAF_TRIGGER"
    )


@app.post("/api/v1/leaf/{leaf_id}/mandate")
def update_leaf_mandate(leaf_id: str, req: LeafMandateRequest) -> Dict[str, Any]:
    return state_store.hierarchy.update_leaf_mandate(
        leaf_id=leaf_id,
        risk_posture=req.risk_posture,
        allocated_capital_usd=req.allocated_capital_usd,
    )


@app.post("/api/v1/leaf/{leaf_id}/liquidate")
def liquidate_leaf_positions(leaf_id: str, req: LeafLiquidateRequest) -> Dict[str, Any]:
    return state_store.hierarchy.emergency_liquidate_leaf(
        leaf_id=leaf_id, reason=req.reason
    )


@app.post("/api/v1/leaf/{leaf_id}/backtest")
def run_leaf_rust_backtest(leaf_id: str) -> Dict[str, Any]:
    """
    Runs the Rust `engine-rs` execution & backtest engine on the target blockchain's
    adapted Strategy Pods (max 4 pods per blockchain).
    """
    bt = state_store.run_rust_backtest_for_leaf(leaf_id)
    return {
        "status": "completed",
        "leaf_id": leaf_id,
        "summary": bt,
    }


@app.post("/api/v1/openrouter/refill")
def trigger_openrouter_refill(req: OpenRouterRefillRequest) -> Dict[str, Any]:
    total_pnl = sum(
        float(lf.get("realized_pnl_usd", 0.0))
        for lf in state_store.hierarchy.leaves.values()
    ) + float(state_store.live_pnl_usd)
    return orchestrator.cost_guard.trigger_openrouter_refill(
        realized_trading_pnl_usd=max(125.0, total_pnl),
        requested_amount_usd=req.amount_usd,
        force=req.force,
    )


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
    return {
        "calls": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "facets": transcript_palace.list_facets(),
    }


@app.post("/api/v1/cognitive/reflect")
def trigger_cognitive_reflection() -> Dict[str, Any]:
    return orchestrator.run_strategic_reflection(force=True, trigger_source="UI_MANUAL_TRIGGER")


@app.post("/api/v1/cognitive/config")
def configure_cognitive_engine(req: CognitiveConfigRequest) -> Dict[str, Any]:
    if req.auto_scheduler_enabled is not None:
        orchestrator.cost_guard.auto_scheduler_enabled = bool(req.auto_scheduler_enabled)
    return orchestrator.update_cognitive_config(
        base_interval_sec=req.base_interval_sec,
        preferred_model=req.preferred_model,
    )


@app.post("/api/v1/cognitive/scheduler")
def toggle_cognitive_scheduler(req: SchedulerToggleRequest) -> Dict[str, Any]:
    orchestrator.cost_guard.auto_scheduler_enabled = bool(req.enabled)
    return {
        "status": "updated",
        "auto_scheduler_enabled": orchestrator.cost_guard.auto_scheduler_enabled,
        "cost_guard": orchestrator.cost_guard.get_status(),
    }


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

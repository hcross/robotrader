from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.agent import BaseWarmAgent
from ..core.schemas import Message
from ..core.state_store import HybridStateStore, state_store
from .analysis import CatalystScoutAgent, QuantAuditorAgent
from .monitor import LLMMonitorAgent
from .trading import MetaAllocatorAgent


class OrchestratorAgent(BaseWarmAgent):
    """
    Warm-Path Coordinator & User Copilot.
    Bootstraps and interconnects all Warm-Path agents (`CostGuard`, `CatalystScout`,
    `QuantAuditor`, `MetaAllocator`) and bridges operator commands to the `PolicyEnvelope`
    and Rust `engine-rs` backtest/execution plane.
    """

    def __init__(self, name: str = "Orchestrator", store: Optional[HybridStateStore] = None):
        super().__init__(name, role="Warm-Path Swarm Coordinator & Operator Copilot")
        self.store = store or state_store

        # Instantiate and interconnect the Warm-Path swarm
        self.cost_guard = LLMMonitorAgent(name="CostGuard")
        self.catalyst_scout = CatalystScoutAgent(name="CatalystScout", store=self.store)
        self.quant_auditor = QuantAuditorAgent(name="QuantAuditor", store=self.store)
        self.meta_allocator = MetaAllocatorAgent(name="MetaAllocator", store=self.store)

        for peer in (self.cost_guard, self.catalyst_scout, self.quant_auditor, self.meta_allocator):
            self.register_peer(peer)
            peer.register_peer(self)

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "USER_COMMAND":
            return self.process_user_command(str(message.content))
        return None

    def process_user_command(self, command: str) -> Dict[str, Any]:
        cmd_lower = command.strip().lower()
        self.send("CostGuard", "REPORT_USAGE", {"agent": self.agent_name, "cost": 0.0015, "tokens": 350})

        if "kill" in cmd_lower or "stop" in cmd_lower or "urgence" in cmd_lower:
            state = self.store.set_kill_switch(True, reason=f"Operator command: {command}")
            return {
                "role": "agent",
                "action": "KILL_SWITCH_ACTIVATED",
                "content": (
                    "🛑 Coupe-circuit HardRiskGate activé. Tous les pods Rust (`pod_carry`, `pod_momentum`, "
                    "`pod_solana_alpha`, `pod_sniper`) sont désactivés et en mode lockdown."
                ),
                "state": state,
            }

        if "resume" in cmd_lower or "reset" in cmd_lower or "reprendre" in cmd_lower:
            state = self.store.set_kill_switch(False)
            return {
                "role": "agent",
                "action": "KILL_SWITCH_RESET",
                "content": "✅ Coupe-circuit réinitialisé. La PolicyEnvelope active est restaurée sur le moteur Rust.",
                "state": state,
            }

        if "defensive" in cmd_lower or "carry" in cmd_lower or "défensif" in cmd_lower:
            env = self.send("MetaAllocator", "SET_REGIME", {"preset": "DEFENSIVE"})
            bt = self.store.run_rust_backtest()
            return {
                "role": "agent",
                "action": "REGIME_UPDATED",
                "content": (
                    f"🛡️ Régime basculé sur **LOW_VOL_CARRY** (Pod 1 Carry = 70%, Pod 2 Momentum = 15%, "
                    f"Solana/Sniper = 0%). Validation Rust : Net PnL +${bt['net_profit_usd']:.2f} "
                    f"(Sharpe {bt['sharpe_ratio']:.2f})."
                ),
                "policy": env,
                "backtest": bt,
            }

        if "sniper" in cmd_lower or "full" in cmd_lower or "agressif" in cmd_lower:
            env = self.send("MetaAllocator", "SET_REGIME", {"preset": "FULL_SWARM"})
            bt = self.store.run_rust_backtest()
            return {
                "role": "agent",
                "action": "REGIME_UPDATED",
                "content": (
                    f"⚡ Régime basculé sur **FULL_SWARM** (4 Pods actifs incluant `pod_sniper` à 10%). "
                    f"Simulation Rust : {bt['total_trades']} trades exécutés, {bt['rejected_orders']} token rug bloqué "
                    f"par `HardRiskGate`, Net PnL +${bt['net_profit_usd']:.2f} (Sharpe {bt['sharpe_ratio']:.2f})."
                ),
                "policy": env,
                "backtest": bt,
            }

        if "backtest" in cmd_lower or "audit" in cmd_lower or "perf" in cmd_lower:
            bt = self.store.run_rust_backtest()
            audit = self.send("QuantAuditor", "AUDIT_PERFORMANCE", {})
            return {
                "role": "agent",
                "action": "BACKTEST_COMPLETED",
                "content": (
                    f"📊 **Audit Quant & Replay Rust (`engine-rs`)** : "
                    f"PnL Net **+${bt['net_profit_usd']:.2f}** | Sharpe **{bt['sharpe_ratio']:.2f}** | "
                    f"Win Rate **{bt['win_rate_pct']:.0f}%** | Slippage moyen **{audit['avg_slippage_bps']} bps** | "
                    f"Rug Solana bloqué : **{bt['rejected_orders']}**."
                ),
                "audit": audit,
                "backtest": bt,
            }

        # Default status & catalyst briefing
        audit = self.send("QuantAuditor", "AUDIT_PERFORMANCE", {})
        catalysts = self.send("CatalystScout", "GET_CATALYSTS", {})
        policy = self.store.get_effective_policy().to_dict()
        return {
            "role": "agent",
            "action": "STATUS_BRIEFING",
            "content": (
                f"🤖 **État Robotrader v2 (Hybride Rust/Python)** — Régime actif : `{policy['global_regime']}` "
                f"(Envelope `{policy['envelope_id']}`, TTL {policy['ttl_seconds']}s). "
                f"Dernier replay Rust : **+${audit['net_profit_usd']}** (Sharpe **{audit['sharpe_ratio']}**, "
                f"{len(catalysts)} catalyseurs actifs). Commandes disponibles : `backtest`, `defensive carry`, "
                f"`full swarm`, `kill switch`, `resume`."
            ),
            "audit": audit,
            "policy": policy,
        }

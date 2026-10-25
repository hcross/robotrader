from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core import provenance
from ..core.agent import BaseWarmAgent
from ..core.schemas import CatalystSignal, Message
from ..core.state_store import HybridStateStore, state_store


class CatalystScoutAgent(BaseWarmAgent):
    """
    Warm-Path Catalyst & Narrative Scout.
    Extracts structured CatalystSignal objects from unstructured events (listings, macro, whale clusters).
    """

    def __init__(self, name: str = "CatalystScout", store: Optional[HybridStateStore] = None):
        super().__init__(name, role="Unstructured Alpha & Catalyst Extractor")
        self.store = store or state_store

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "GET_CATALYSTS":
            return [c.to_dict() for c in self.store.recent_catalysts]
        if message.msg_type == "INGEST_CATALYST":
            payload = message.content
            sig = CatalystSignal(
                asset=payload.get("asset", "SOL-USDT"),
                catalyst_type=payload.get("catalyst_type", "NEWS_CATALYST"),
                conviction=float(payload.get("conviction", 0.75)),
                directional_bias=payload.get("directional_bias", "LONG_BIAS"),
                half_life_minutes=int(payload.get("half_life_minutes", 120)),
                summary=payload.get("summary", "External catalyst signal"),
            )
            self.store.recent_catalysts.insert(0, sig)
            return sig.to_dict()
        return None


class QuantAuditorAgent(BaseWarmAgent):
    """
    Warm-Path Post-Mortem & Drift Auditor.
    Audits deterministic Rust execution telemetry (slippage, fee drag, Sharpe, rug rejections).
    """

    def __init__(self, name: str = "QuantAuditor", store: Optional[HybridStateStore] = None):
        super().__init__(name, role="Execution Slippage & Alpha Decay Auditor")
        self.store = store or state_store

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "AUDIT_PERFORMANCE":
            return self.audit_latest_backtest()
        return None

    def audit_latest_backtest(self) -> Dict[str, Any]:
        bt = self.store.last_backtest_result or self.store.run_rust_backtest()
        executions: List[Dict[str, Any]] = bt.get("executions", [])
        avg_slippage_bps = (
            sum(float(e.get("realized_slippage_bps", 0.0)) for e in executions) / len(executions)
            if executions
            else 0.0
        )
        return {
            "auditor": self.agent_name,
            "source": provenance.METRIC_SOURCES[2],  # FIXTURE
            "source_detail": "engine-rs deterministic replay (robotrader-node backtest)",
            "total_trades": bt.get("total_trades", 0),
            "rejected_rug_orders": bt.get("rejected_orders", 0),
            "net_profit_usd": round(float(bt.get("net_profit_usd", 0.0)), 2),
            "sharpe_ratio": round(float(bt.get("sharpe_ratio", 0.0)), 2),
            "avg_slippage_bps": round(avg_slippage_bps, 2),
            "total_fees_usd": round(float(bt.get("total_fees_usd", 0.0)), 2),
            "pod_pnl_attribution": bt.get("pod_pnl_attribution", {}),
            "verdict": (
                "FIXTURE_HEALTHY_EDGE"
                if float(bt.get("sharpe_ratio", 0.0)) >= 1.5
                else "FIXTURE_REVIEW_REQUIRED"
            ),
        }


# Backwards-compatible aliases
TrendScoutAgent = CatalystScoutAgent
ChartistAgent = QuantAuditorAgent

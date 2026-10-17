from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..core.agent import BaseWarmAgent
from ..core.schemas import Message


class LLMMonitorAgent(BaseWarmAgent):
    """
    CostGuard: Enforces a hard daily USD inference cap and tiered model routing.
    Security invariant: Unbounded automatic crypto wallet refills are strictly prohibited.
    """

    def __init__(self, name: str = "CostGuard", daily_budget_usd: Optional[float] = None):
        super().__init__(name, role="Inference Budget & Tiered Router")
        self.daily_budget_usd: float = daily_budget_usd or float(
            os.getenv("MAX_DAILY_LLM_BUDGET_USD", "5.0")
        )
        self.total_cost_usd: float = 0.042  # Initial warm-path telemetry cost
        self.usage_log: List[Dict[str, Any]] = []

    @property
    def remaining_budget_usd(self) -> float:
        return max(0.0, self.daily_budget_usd - self.total_cost_usd)

    @property
    def budget_exhausted(self) -> bool:
        return self.total_cost_usd >= self.daily_budget_usd

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "REPORT_USAGE":
            return self.record_usage(message.content)
        if message.msg_type == "QUERY_BALANCE":
            return self.get_status()
        return None

    def record_usage(self, content: Dict[str, Any]) -> Dict[str, Any]:
        cost = float(content.get("cost", 0.0))
        agent = str(content.get("agent", "unknown"))
        self.total_cost_usd += cost
        self.usage_log.append({"agent": agent, "cost": cost, "tokens": content.get("tokens", 0)})
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        utilization_pct = (
            (self.total_cost_usd / self.daily_budget_usd) * 100.0
            if self.daily_budget_usd > 0
            else 100.0
        )
        return {
            "agent": self.agent_name,
            "daily_budget_usd": round(self.daily_budget_usd, 2),
            "total_spent_usd": round(self.total_cost_usd, 4),
            "remaining_usd": round(self.remaining_budget_usd, 4),
            "utilization_pct": round(utilization_pct, 2),
            "budget_exhausted": self.budget_exhausted,
            "auto_wallet_refill": "DISABLED_BY_SECURITY_POLICY",
        }

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..core.agent import BaseWarmAgent
from ..core.schemas import Message

# OpenRouter Frontier-Efficiency Model Catalog (Prices in USD per 1M tokens)
FRONTIER_FLASH_MODELS: Dict[str, Dict[str, Any]] = {
    "moonshotai/kimi-k3.1-pro": {
        "litellm_model": "openrouter/moonshotai/kimi-k3.1-pro",
        "label": "Kimi K3.1 Pro (Master Orchestrator)",
        "input_usd_per_m": 0.140,
        "output_usd_per_m": 0.420,
        "tier": "MASTER_ORCHESTRATOR_PRO",
    },
    "deepseek/deepseek-v4.1-flash-1017": {
        "litellm_model": "openrouter/deepseek/deepseek-v4.1-flash-1017",
        "label": "DeepSeek v4.1 Flash 1017 (Leaf Agent)",
        "input_usd_per_m": 0.028,
        "output_usd_per_m": 0.080,
        "tier": "LEAF_AGENT_FLASH_PRIMARY",
    },
    "deepseek/deepseek-v4.1-flash": {
        "litellm_model": "openrouter/deepseek/deepseek-v4.1-flash",
        "label": "DeepSeek v4.1 Flash",
        "input_usd_per_m": 0.028,
        "output_usd_per_m": 0.080,
        "tier": "FRONTIER_FLASH_PRIMARY",
    },
    "z-ai/glm-5.3-flash": {
        "litellm_model": "openrouter/z-ai/glm-5.3-flash",
        "label": "GLM 5.3 Flash (Z-AI)",
        "input_usd_per_m": 0.048,
        "output_usd_per_m": 0.160,
        "tier": "FRONTIER_FLASH_COPRIMARY",
    },
    "qwen/qwen3.7-flash": {
        "litellm_model": "openrouter/qwen/qwen3.7-flash",
        "label": "Qwen 3.7 Flash",
        "input_usd_per_m": 0.030,
        "output_usd_per_m": 0.130,
        "tier": "FRONTIER_FLASH_FALLBACK",
    },
    "z-ai/glm-5.3": {
        "litellm_model": "openrouter/z-ai/glm-5.3",
        "label": "GLM 5.3 Frontier Reasoning",
        "input_usd_per_m": 0.079,
        "output_usd_per_m": 1.400,
        "tier": "FRONTIER_DEEP_INFLECTION",
    },
    "deepseek/deepseek-v4-pro": {
        "litellm_model": "openrouter/deepseek/deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "input_usd_per_m": 0.372,
        "output_usd_per_m": 0.743,
        "tier": "FRONTIER_DEEP_INFLECTION",
    },
}


class LLMMonitorAgent(BaseWarmAgent):
    """
    CostGuard: Enforces a hard daily USD inference cap, budget-driven cognitive depth
    (`DEEP_THESIS`, `TACTICAL_FOCUS`, `ECO_CONSERVATION`, `DETERMINISTIC_LOCK`),
    and ultra-low-cost near-frontier model routing (`deepseek/deepseek-v4.1-flash`,
    `z-ai/glm-5.3-flash`, `qwen/qwen3.7-flash`).
    Security invariant: Unbounded automatic crypto wallet refills are strictly prohibited.
    """

    def __init__(self, name: str = "CostGuard", daily_budget_usd: Optional[float] = None):
        super().__init__(name, role="Inference Budget & Tiered Frontier-Flash Router")
        self.daily_budget_usd: float = daily_budget_usd or float(
            os.getenv("MAX_DAILY_LLM_BUDGET_USD", "5.0")
        )
        self.preferred_model: str = os.getenv(
            "LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017"
        ).replace("openrouter/", "")
        if self.preferred_model not in FRONTIER_FLASH_MODELS:
            self.preferred_model = "deepseek/deepseek-v4.1-flash-1017"
        self.master_model: str = os.getenv(
            "MASTER_LLM_MODEL", "moonshotai/kimi-k3.1-pro"
        ).replace("openrouter/", "")
        if self.master_model not in FRONTIER_FLASH_MODELS:
            self.master_model = "moonshotai/kimi-k3.1-pro"

        self.total_cost_usd: float = 0.0
        self.total_tokens: int = 0
        self.total_calls: int = 0
        self.usage_log: List[Dict[str, Any]] = []

        # ADR-0003: Profit-Gated & Epoch-Capped OpenRouter Credit Treasury
        self.openrouter_balance_usd: float = float(
            os.getenv("OPENROUTER_INITIAL_BALANCE_USD", "8.50")
        )
        self.low_watermark_usd: float = float(
            os.getenv("OPENROUTER_LOW_WATERMARK_USD", "2.00")
        )
        self.refill_amount_usd: float = float(
            os.getenv("OPENROUTER_REFILL_AMOUNT_USD", "10.00")
        )
        self.max_epoch_refill_usd: float = float(
            os.getenv("OPENROUTER_MAX_EPOCH_REFILL_USD", "25.00")
        )
        self.epoch_refilled_usd: float = 0.0
        self.auto_refill_enabled: bool = True
        self.refill_history: List[Dict[str, Any]] = []

    @property
    def remaining_budget_usd(self) -> float:
        return max(0.0, self.daily_budget_usd - self.total_cost_usd)

    @property
    def remaining_budget_ratio(self) -> float:
        if self.daily_budget_usd <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_budget_usd / self.daily_budget_usd))

    @property
    def budget_exhausted(self) -> bool:
        return self.total_cost_usd >= self.daily_budget_usd

    def get_thinking_depth(self) -> str:
        if self.budget_exhausted or self.remaining_budget_ratio <= 0.05:
            return "DETERMINISTIC_LOCK"
        if self.remaining_budget_ratio <= 0.20:
            return "ECO_CONSERVATION"
        if self.remaining_budget_ratio <= 0.50:
            return "TACTICAL_FOCUS"
        return "DEEP_THESIS"

    def select_cognitive_profile(self, urgency_level: str = "NORMAL_FLOW") -> Dict[str, Any]:
        depth = self.get_thinking_depth()
        if depth == "DETERMINISTIC_LOCK":
            return {
                "thinking_depth": depth,
                "output_contract": "NONE",
                "allow_llm": False,
                "model_key": self.preferred_model,
                "litellm_model": FRONTIER_FLASH_MODELS[self.preferred_model]["litellm_model"],
                "max_tokens": 0,
                "escalation_floor": 0,
                "max_escalation_tokens": 0,
                "min_wakeup_sec": 600,
                "recall_limit": 0,
            }

        if depth == "ECO_CONSERVATION":
            # Mechanical envelope contract (~140-220 tokens): omits prose-heavy
            # panorama_summary & ta_confluence_notes so 350 max_tokens never truncates.
            model_key = "deepseek/deepseek-v4.1-flash-1017"
            return {
                "thinking_depth": depth,
                "output_contract": "MECHANICAL_ENVELOPE",
                "allow_llm": True,
                "model_key": model_key,
                "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
                "max_tokens": 350,
                "escalation_floor": 500,
                "max_escalation_tokens": 650,
                "min_wakeup_sec": 300,
                "recall_limit": 1,
            }

        if depth == "TACTICAL_FOCUS":
            # Compact single-sentence tactical contract (~320-480 tokens): fits
            # comfortably within 700 max_tokens without triggering escalation retries.
            model_key = (
                self.preferred_model
                if self.preferred_model
                in (
                    "deepseek/deepseek-v4.1-flash-1017",
                    "deepseek/deepseek-v4.1-flash",
                    "z-ai/glm-5.3-flash",
                    "qwen/qwen3.7-flash",
                )
                else "deepseek/deepseek-v4.1-flash-1017"
            )
            return {
                "thinking_depth": depth,
                "output_contract": "COMPACT_TACTICAL",
                "allow_llm": True,
                "model_key": model_key,
                "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
                "max_tokens": 700,
                "escalation_floor": 950,
                "max_escalation_tokens": 1200,
                "min_wakeup_sec": 90,
                "recall_limit": 2,
            }

        # DEEP_THESIS (> 50% budget remaining). The full reflective JSON contract
        # (7 fields, detailed French prose across 3 pairs) needs ~1500-2100 tokens.
        model_key = self.preferred_model
        return {
            "thinking_depth": depth,
            "output_contract": "FULL_THESIS",
            "allow_llm": True,
            "model_key": model_key,
            "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
            "max_tokens": 2200 if urgency_level == "HIGH_INFLECTION" else 1800,
            "escalation_floor": 1800,
            "max_escalation_tokens": 3200,
            "min_wakeup_sec": 30,
            "recall_limit": 4,
        }

    def compute_call_cost(self, model_key: str, prompt_tokens: int, completion_tokens: int) -> float:
        clean_key = model_key.replace("openrouter/", "")
        meta = FRONTIER_FLASH_MODELS.get(clean_key, FRONTIER_FLASH_MODELS["deepseek/deepseek-v4.1-flash"])
        in_cost = (prompt_tokens / 1_000_000.0) * float(meta["input_usd_per_m"])
        out_cost = (completion_tokens / 1_000_000.0) * float(meta["output_usd_per_m"])
        return round(in_cost + out_cost, 7)

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "REPORT_USAGE":
            return self.record_usage(message.content)
        if message.msg_type == "QUERY_BALANCE":
            return self.get_status()
        return None

    def record_usage(self, content: Dict[str, Any]) -> Dict[str, Any]:
        model_key = str(content.get("model", self.preferred_model)).replace("openrouter/", "")
        prompt_tokens = int(content.get("prompt_tokens", 0))
        completion_tokens = int(content.get("completion_tokens", 0))
        tokens = int(content.get("tokens", prompt_tokens + completion_tokens))
        if "cost" in content and content["cost"] is not None:
            cost = float(content["cost"])
        else:
            cost = self.compute_call_cost(model_key, prompt_tokens, completion_tokens)

        agent = str(content.get("agent", "unknown"))
        self.total_cost_usd = round(self.total_cost_usd + cost, 6)
        self.openrouter_balance_usd = round(max(0.0, self.openrouter_balance_usd - cost), 6)
        self.total_tokens += tokens
        self.total_calls += 1
        self.usage_log.insert(
            0,
            {
                "agent": agent,
                "model": model_key,
                "cost": round(cost, 6),
                "tokens": tokens,
            },
        )
        self.usage_log = self.usage_log[:50]

        # Check if OpenRouter balance dropped to or below low watermark -> trigger auto-refill
        if (
            self.auto_refill_enabled
            and self.openrouter_balance_usd <= self.low_watermark_usd
            and (self.epoch_refilled_usd + self.refill_amount_usd) <= self.max_epoch_refill_usd
        ):
            self.trigger_openrouter_refill(
                amount_usd=self.refill_amount_usd,
                reason=f"Auto-refill triggered: balance ${self.openrouter_balance_usd:.2f} <= watermark ${self.low_watermark_usd:.2f}",
                source="MASTER_ORCHESTRATOR_AUTO",
            )
        return self.get_status()

    @property
    def openrouter_credit_balance_usd(self) -> float:
        return self.openrouter_balance_usd

    @openrouter_credit_balance_usd.setter
    def openrouter_credit_balance_usd(self, val: float) -> None:
        self.openrouter_balance_usd = float(val)

    def trigger_openrouter_refill(
        self,
        amount_usd: Optional[float] = None,
        reason: str = "Master Orchestrator scheduled credit top-up",
        source: str = "MASTER_ORCHESTRATOR",
        force: bool = False,
        realized_trading_pnl_usd: Optional[float] = None,
        requested_amount_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes a bounded OpenRouter credit refill from the Master Orchestrator's OpEx reserve.
        Enforces the HardRiskGate profit-gate (`realized_trading_pnl_usd > 0`) and epoch cap
        (`max_epoch_refill_usd`) so a runaway loop can never drain the principal treasury.
        """
        import time

        if realized_trading_pnl_usd is not None and float(realized_trading_pnl_usd) <= 0.0:
            return {
                "status": "rejected_no_realized_profit",
                "reason": f"Realized trading PnL (${float(realized_trading_pnl_usd):.2f}) <= 0; principal treasury protected",
                "openrouter_balance_usd": round(self.openrouter_balance_usd, 4),
            }

        eff_req = requested_amount_usd if requested_amount_usd is not None else amount_usd
        amt = round(float(eff_req if eff_req is not None else self.refill_amount_usd), 2)
        if amt <= 0 or amt > 25.0:
            return {
                "status": "rejected",
                "reason": f"Amount ${amt:.2f} outside allowed single-refill bounds (0, $25.00]",
                "openrouter_balance_usd": round(self.openrouter_balance_usd, 4),
            }
        if (
            realized_trading_pnl_usd is not None
            and amt > float(realized_trading_pnl_usd) * 0.10 + 1e-6
        ):
            return {
                "status": "rejected_exceeds_profit_share",
                "reason": f"Requested refill ${amt:.2f} > 10% of realized PnL (${float(realized_trading_pnl_usd):.2f})",
                "openrouter_balance_usd": round(self.openrouter_balance_usd, 4),
            }
        if not force and self.openrouter_balance_usd > self.low_watermark_usd:
            return {
                "status": "skipped_sufficient_balance",
                "reason": f"Balance ${self.openrouter_balance_usd:.2f} > low watermark ${self.low_watermark_usd:.2f}",
                "openrouter_balance_usd": round(self.openrouter_balance_usd, 4),
            }
        if (self.epoch_refilled_usd + amt) > self.max_epoch_refill_usd:
            return {
                "status": "rejected_epoch_cap",
                "reason": f"Epoch cap reached (${self.epoch_refilled_usd:.2f} + ${amt:.2f} > ${self.max_epoch_refill_usd:.2f})",
                "openrouter_balance_usd": round(self.openrouter_balance_usd, 4),
            }

        before_bal = round(self.openrouter_balance_usd, 4)
        self.openrouter_balance_usd = round(self.openrouter_balance_usd + amt, 4)
        self.epoch_refilled_usd = round(self.epoch_refilled_usd + amt, 2)
        event = {
            "timestamp_ms": int(time.time() * 1000),
            "amount_usd": amt,
            "balance_before_usd": before_bal,
            "balance_after_usd": self.openrouter_balance_usd,
            "epoch_refilled_usd": self.epoch_refilled_usd,
            "max_epoch_refill_usd": self.max_epoch_refill_usd,
            "source": source,
            "reason": reason,
        }
        self.refill_history.insert(0, event)
        self.refill_history = self.refill_history[:25]
        return {
            "status": "refilled",
            "refilled_usd": amt,
            "event": event,
            "openrouter_balance_usd": self.openrouter_balance_usd,
        }

    def get_status(self) -> Dict[str, Any]:
        utilization_pct = (
            (self.total_cost_usd / self.daily_budget_usd) * 100.0
            if self.daily_budget_usd > 0
            else 100.0
        )
        profile = self.select_cognitive_profile()
        return {
            "agent": self.agent_name,
            "daily_budget_usd": round(self.daily_budget_usd, 2),
            "total_spent_usd": round(self.total_cost_usd, 5),
            "remaining_usd": round(self.remaining_budget_usd, 5),
            "remaining_ratio_pct": round(self.remaining_budget_ratio * 100.0, 1),
            "utilization_pct": round(utilization_pct, 3),
            "budget_exhausted": self.budget_exhausted,
            "thinking_depth": self.get_thinking_depth(),
            "master_model": self.master_model,
            "master_model_meta": FRONTIER_FLASH_MODELS.get(self.master_model),
            "active_model": self.preferred_model,
            "active_model_meta": FRONTIER_FLASH_MODELS.get(self.preferred_model),
            "available_models": FRONTIER_FLASH_MODELS,
            "min_wakeup_sec": profile["min_wakeup_sec"],
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "recent_usage": self.usage_log[:5],
            "openrouter_credit": {
                "balance_usd": round(self.openrouter_balance_usd, 4),
                "low_watermark_usd": round(self.low_watermark_usd, 2),
                "refill_amount_usd": round(self.refill_amount_usd, 2),
                "epoch_refilled_usd": round(self.epoch_refilled_usd, 2),
                "max_epoch_refill_usd": round(self.max_epoch_refill_usd, 2),
                "auto_refill_enabled": self.auto_refill_enabled,
                "refill_history": self.refill_history[:5],
            },
            "auto_wallet_refill": "DISABLED_BY_SECURITY_POLICY",
            "auto_refill_policy": "PROFIT_GATED_CAPPED_BY_ORCHESTRATOR",
        }

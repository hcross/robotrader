from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..core.agent import BaseWarmAgent
from ..core.schemas import Message

# OpenRouter Frontier-Efficiency Model Catalog (Prices in USD per 1M tokens)
FRONTIER_FLASH_MODELS: Dict[str, Dict[str, Any]] = {
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
            "LLM_MODEL", "deepseek/deepseek-v4.1-flash"
        ).replace("openrouter/", "")
        if self.preferred_model not in FRONTIER_FLASH_MODELS:
            self.preferred_model = "deepseek/deepseek-v4.1-flash"

        self.total_cost_usd: float = 0.0
        self.total_tokens: int = 0
        self.total_calls: int = 0
        self.usage_log: List[Dict[str, Any]] = []

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
                "allow_llm": False,
                "model_key": self.preferred_model,
                "litellm_model": FRONTIER_FLASH_MODELS[self.preferred_model]["litellm_model"],
                "max_tokens": 0,
                "min_wakeup_sec": 600,
                "recall_limit": 0,
            }

        if depth == "ECO_CONSERVATION":
            model_key = "deepseek/deepseek-v4.1-flash"
            return {
                "thinking_depth": depth,
                "allow_llm": True,
                "model_key": model_key,
                "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
                "max_tokens": 350,
                "min_wakeup_sec": 300,
                "recall_limit": 1,
            }

        if depth == "TACTICAL_FOCUS":
            model_key = (
                self.preferred_model
                if self.preferred_model in ("deepseek/deepseek-v4.1-flash", "z-ai/glm-5.3-flash", "qwen/qwen3.7-flash")
                else "deepseek/deepseek-v4.1-flash"
            )
            return {
                "thinking_depth": depth,
                "allow_llm": True,
                "model_key": model_key,
                "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
                "max_tokens": 700,
                "min_wakeup_sec": 90,
                "recall_limit": 2,
            }

        # DEEP_THESIS (> 50% budget remaining). The reflective JSON contract
        # (7 fields, French prose) needs ~1500 completion tokens; 1200 truncated
        # it in production, so the cap is sized to the contract, not to the tier.
        model_key = self.preferred_model
        return {
            "thinking_depth": depth,
            "allow_llm": True,
            "model_key": model_key,
            "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
            "max_tokens": 2200 if urgency_level == "HIGH_INFLECTION" else 1800,
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
        return self.get_status()

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
            "active_model": self.preferred_model,
            "active_model_meta": FRONTIER_FLASH_MODELS.get(self.preferred_model),
            "available_models": FRONTIER_FLASH_MODELS,
            "min_wakeup_sec": profile["min_wakeup_sec"],
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "recent_usage": self.usage_log[:5],
            "auto_wallet_refill": "DISABLED_BY_SECURITY_POLICY",
        }

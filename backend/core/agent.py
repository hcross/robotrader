from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .schemas import Message


@dataclass
class CallResult:
    """Structured result of one OpenRouter invocation with per-attempt failover telemetry."""

    raw_resp: Optional[str]
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    #  attempt = {"model", "latency_ms", "ok", "prompt_tokens", "completion_tokens", "error"}
    error: str = ""  # "" | "no_api_key" | "fallback_exhausted"


class BaseWarmAgent:
    """
    Base class for Warm-Path AI Agents (Orchestrator, CatalystScout, MetaAllocator, QuantAuditor, CostGuard).
    Never sits in the sub-millisecond Hot Path; operates on semantic catalysts, Technical Analysis
    (Ichimoku, Fibonacci, RSI), Palace Memory continuity, and mechanical rule compilation.
    """

    FALLBACK_CHAIN = [
        "deepseek/deepseek-v4.1-flash",
        "z-ai/glm-5.3-flash",
        "qwen/qwen3.7-flash",
    ]

    def __init__(self, name: str, role: str, system_prompt: Optional[str] = None):
        self.agent_name = name
        self.role = role
        self.system_prompt = system_prompt or f"You are {name}. Role: {role}."
        self.mailbox: List[Message] = []
        self.lock = threading.Lock()
        self.known_agents: Dict[str, BaseWarmAgent] = {}

    def register_peer(self, peer: BaseWarmAgent) -> None:
        self.known_agents[peer.agent_name] = peer

    def send(self, recipient_name: str, msg_type: str, content: Any) -> Optional[Any]:
        peer = self.known_agents.get(recipient_name)
        if not peer:
            return None
        msg = Message(
            sender=self.agent_name,
            recipient=recipient_name,
            msg_type=msg_type,
            content=content,
        )
        return peer.receive(msg)

    def receive(self, message: Message) -> Optional[Any]:
        with self.lock:
            self.mailbox.append(message)
        return self.handle_message(message)

    def handle_message(self, message: Message) -> Optional[Any]:
        return None

    def invoke_openrouter(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        preferred_model: str = "deepseek/deepseek-v4.1-flash",
        max_tokens: int = 900,
        temperature: float = 0.2,
    ) -> CallResult:
        """
        Calls OpenRouter with the preferred near-frontier low-cost model (`deepseek/deepseek-v4.1-flash`
        or `z-ai/glm-5.3-flash`) and automatic failover across FALLBACK_CHAIN.
        Returns a `CallResult`: raw response (or None), model actually used, token usage,
        wall-clock latency, per-attempt failover telemetry and transport error.
        """
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        clean_pref = preferred_model.replace("openrouter/", "")
        if not api_key or api_key == "sk-or-your-key-here":
            return CallResult(None, clean_pref, 0, 0, 0, error="no_api_key")

        candidates = [clean_pref] + [m for m in self.FALLBACK_CHAIN if m != clean_pref]
        sys_msg = system_prompt or self.system_prompt
        attempts: List[Dict[str, Any]] = []
        total_start = time.perf_counter()

        for model_slug in candidates:
            attempt_start = time.perf_counter()
            try:
                payload = json.dumps(
                    {
                        "model": model_slug,
                        "messages": [
                            {"role": "system", "content": sys_msg},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/hoanicross/robotrader",
                        "X-Title": "Robotrader v2 Warm-Path Strategist",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=22) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if not choices:
                    attempts.append(
                        {
                            "model": model_slug,
                            "latency_ms": int((time.perf_counter() - attempt_start) * 1000),
                            "ok": False,
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "error": "empty_choices",
                        }
                    )
                    continue
                content = choices[0].get("message", {}).get("content", "")
                usage = body.get("usage", {})
                p_tok = int(usage.get("prompt_tokens", 0))
                c_tok = int(usage.get("completion_tokens", 0))
                attempts.append(
                    {
                        "model": model_slug,
                        "latency_ms": int((time.perf_counter() - attempt_start) * 1000),
                        "ok": bool(content),
                        "prompt_tokens": p_tok,
                        "completion_tokens": c_tok,
                        "error": "" if content else "empty_content",
                    }
                )
                if content:
                    return CallResult(
                        str(content).strip(),
                        model_slug,
                        p_tok,
                        c_tok,
                        int((time.perf_counter() - total_start) * 1000),
                        attempts=attempts,
                        error="",
                    )
            except Exception as exc:
                attempts.append(
                    {
                        "model": model_slug,
                        "latency_ms": int((time.perf_counter() - attempt_start) * 1000),
                        "ok": False,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "error": str(exc)[-200:],
                    }
                )
                print(f"[{self.agent_name}] OpenRouter model {model_slug} warning: {exc}")
                continue

        return CallResult(
            None, clean_pref, 0, 0, int((time.perf_counter() - total_start) * 1000), attempts=attempts, error="fallback_exhausted"
        )

from __future__ import annotations

import json
import os
import threading
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .schemas import Message


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
    ) -> Tuple[Optional[str], str, int, int]:
        """
        Calls OpenRouter with the preferred near-frontier low-cost model (`deepseek/deepseek-v4.1-flash`
        or `z-ai/glm-5.3-flash`) and automatic failover across FALLBACK_CHAIN.
        Returns: (response_text, model_used, prompt_tokens, completion_tokens)
        """
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key or api_key == "sk-or-your-key-here":
            return None, preferred_model, 0, 0

        clean_pref = preferred_model.replace("openrouter/", "")
        candidates = [clean_pref] + [m for m in self.FALLBACK_CHAIN if m != clean_pref]
        sys_msg = system_prompt or self.system_prompt

        for model_slug in candidates:
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
                    continue
                content = choices[0].get("message", {}).get("content", "")
                usage = body.get("usage", {})
                p_tok = int(usage.get("prompt_tokens", 0))
                c_tok = int(usage.get("completion_tokens", 0))
                if content:
                    return str(content).strip(), model_slug, p_tok, c_tok
            except Exception as exc:
                print(f"[{self.agent_name}] OpenRouter model {model_slug} warning: {exc}")
                continue

        return None, clean_pref, 0, 0

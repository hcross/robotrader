from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .schemas import Message


class BaseWarmAgent:
    """
    Base class for Warm-Path AI Agents (Orchestrator, CatalystScout, MetaAllocator, QuantAuditor, CostGuard).
    Never sits in the sub-millisecond Hot Path; operates on semantic catalysts, regime shifts,
    and user orchestration commands.
    """

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

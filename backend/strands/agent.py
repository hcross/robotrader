import threading
import time
from typing import List, Callable, Any, Optional
from .a2a import Message
from strands import Agent

class BaseAgent(threading.Thread):
    def __init__(self, name: str, role: str, system_prompt: Optional[str] = None):
        super().__init__(name=name, daemon=True)
        self.agent_name = name
        self.role = role
        self.mailbox: List[Message] = []
        self.running = False
        self.lock = threading.Lock()
        
        # Strands Integration
        self.smart_agent = Agent(
            name=name,
            system_prompt=system_prompt or f"You are {name}. Role: {role}."
        )

        # Registry of known agents (simplified discovery)
        self.known_agents = {}

    def register_peer(self, agent):
        self.known_agents[agent.agent_name] = agent

    def send(self, recipient_name: str, msg_type: str, content: Any):
        if recipient_name not in self.known_agents:
            print(f"[{self.agent_name}] Error: Unknown recipient {recipient_name}")
            return

        msg = Message(
            sender=self.agent_name,
            recipient=recipient_name,
            msg_type=msg_type,
            content=content
        )
        
        recipient = self.known_agents[recipient_name]
        recipient.receive(msg)
        print(f"[{self.agent_name}] -> [{recipient_name}]: {msg_type}")

    def receive(self, message: Message):
        with self.lock:
            self.mailbox.append(message)

    def process_messages(self):
        """Override this to handle incoming messages."""
        with self.lock:
            if not self.mailbox:
                return
            
            # Process all messages
            while self.mailbox:
                msg = self.mailbox.pop(0)
                self.handle_message(msg)

    def handle_message(self, message: Message):
        """Default handler."""
        print(f"[{self.agent_name}] Received {message.msg_type} from {message.sender}")

    def run(self):
        self.running = True
        print(f"[{self.agent_name}] Started.")
        while self.running:
            self.loop()
            time.sleep(0.1)

    def loop(self):
        """Main agent loop."""
        self.process_messages()
        self.perform_task()

    def perform_task(self):
        """Override for periodic tasks."""
        pass

    def stop(self):
        self.running = False

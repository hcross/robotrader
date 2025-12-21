from ..strands.agent import BaseAgent
from ..strands.a2a import Message
from ..config import get_llm_response
import json

class OrchestratorAgent(BaseAgent):
    def __init__(self, name="Orchestrator"):
        super().__init__(name, role="Manager")
        self.strategy = "neutral"
        self.active_workers = []

    def handle_message(self, message: Message):
        if message.msg_type == "USER_COMMAND":
            self.process_user_command(message.content, message.sender)
        elif message.msg_type == "MARKET_INSIGHT":
            self.process_insight(message.content, message.sender)
        else:
            super().handle_message(message)

    def process_user_command(self, command: str, sender: str):
        print(f"[{self.agent_name}] Processing user command: {command}")
        
        # Use Strands Agent to interpret command
        try:
            # The smart_agent(command) should return the LLM's response or tool output
            response = self.smart_agent(command)
            print(f"[{self.agent_name}] Strands Agent Response: {response}")
            
            # Send response back to user/sender
            self.send(sender, "RESPONSE", str(response))
            
            # Note: In a full Strands implementation, the 'tools' would be executed automatically.
            # Here we might need to parse the response if we still want manual delegation,
            # but ideally we define tools on the agent.
            
        except Exception as e:
            print(f"[{self.agent_name}] Error in Strands Agent: {e}")
            self.send(sender, "ERROR", f"Failed to process command: {e}")

    def process_insight(self, insight: dict, sender: str):
        print(f"[{self.agent_name}] Received insight from {sender}: {insight}")
        # Logic to combine insights and make a trading decision
        # ...

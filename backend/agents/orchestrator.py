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
        
        # Use LLM to interpret command
        messages = [
            {"role": "system", "content": "You are the Orchestrator of a crypto trading team. Interpret the user's command and decide which agents to deploy. Available agents: TrendScout (sentiment), Chartist (technical), Sniper (trade execution), Swinger (trade execution). Return JSON with 'plan' and 'delegation'."},
            {"role": "user", "content": command}
        ]
        
        response = get_llm_response(messages)
        if response:
            content = response.choices[0].message.content
            print(f"[{self.agent_name}] LLM Plan: {content}")
            
            # Mock parsing and delegation
            # In a real implementation, we would parse the JSON and send specific GOAL messages
            self.send(sender, "RESPONSE", f"I have received your command: '{command}'. I am activating the team.")
            
            # Example delegation
            if "buy" in command.lower() or "trade" in command.lower():
                self.send("TrendScout", "GOAL", {"task": "analyze_sentiment", "asset": "SOL"})
                self.send("Chartist", "GOAL", {"task": "analyze_technical", "asset": "SOL"})

    def process_insight(self, insight: dict, sender: str):
        print(f"[{self.agent_name}] Received insight from {sender}: {insight}")
        # Logic to combine insights and make a trading decision
        # ...

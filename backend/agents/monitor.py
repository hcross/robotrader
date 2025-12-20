from ..strands.agent import BaseAgent
from ..strands.a2a import Message
import time

class LLMMonitorAgent(BaseAgent):
    def __init__(self, name="CostGuard"):
        super().__init__(name, role="Monitor")
        self.total_cost = 0.0
        self.usage_log = []
        self.budget_limit = 10.0 # USD
        self.low_balance_threshold = 2.0

    def handle_message(self, message: Message):
        if message.msg_type == "REPORT_USAGE":
            self.record_usage(message.content)
        elif message.msg_type == "QUERY_BALANCE":
            self.report_balance(message.sender)
        else:
            super().handle_message(message)

    def record_usage(self, content):
        """
        Content expected: {'tokens': int, 'cost': float, 'agent': str}
        """
        cost = content.get('cost', 0.0)
        agent = content.get('agent', 'unknown')
        self.total_cost += cost
        self.usage_log.append(content)
        print(f"[{self.agent_name}] Recorded usage: ${cost:.4f} by {agent}. Total: ${self.total_cost:.4f}")
        
        self.check_budget()

    def report_balance(self, recipient):
        remaining = self.budget_limit - self.total_cost
        self.send(recipient, "BALANCE_REPORT", {"remaining": remaining, "total_spent": self.total_cost})

    def check_budget(self):
        remaining = self.budget_limit - self.total_cost
        if remaining < self.low_balance_threshold:
            print(f"[{self.agent_name}] WARNING: Low balance! Remaining: ${remaining:.2f}")
            self.refill_credits()

    def refill_credits(self):
        """
        Placeholder for crypto transaction to refill OpenRouter credits.
        """
        print(f"[{self.agent_name}] Initiating auto-refill via Solana...")
        # TODO: Implement Solana transaction to OpenRouter deposit address
        # For now, we just reset the budget to simulate a refill
        self.budget_limit += 10.0
        print(f"[{self.agent_name}] Refill successful. New budget: ${self.budget_limit:.2f}")

    def perform_task(self):
        # Periodic check (e.g., every minute)
        # In a real app, this would query the OpenRouter API for exact balance
        pass

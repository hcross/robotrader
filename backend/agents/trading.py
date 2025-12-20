from ..strands.agent import BaseAgent
from ..strands.a2a import Message
from ..tools.solana_tools import SolanaWalletTool
from ..tools.exchange_tools import BinanceTool, DexTool

class TradingAgent(BaseAgent):
    def __init__(self, name, role, strategy):
        super().__init__(name, role)
        self.strategy = strategy
        self.wallet = SolanaWalletTool()
        self.binance = BinanceTool()
        self.dex = DexTool()

class SniperAgent(TradingAgent):
    def __init__(self, name="Sniper"):
        super().__init__(name, role="High Frequency Trading", strategy="aggressive")

    def handle_message(self, message: Message):
        if message.msg_type == "GOAL" and message.content.get("task") == "execute_trade":
            self.execute_snipe(message.content)
        else:
            super().handle_message(message)

    def execute_snipe(self, params):
        print(f"[{self.agent_name}] Sniping {params}...")
        # Logic to use DexTool to swap immediately
        pass

class PortfolioManagerAgent(BaseAgent):
    def __init__(self, name="Allocator"):
        super().__init__(name, role="Risk Manager")
        self.holdings = {}

    def handle_message(self, message: Message):
        if message.msg_type == "REQUEST_FUNDS":
            self.approve_funds(message.content, message.sender)
        else:
            super().handle_message(message)

    def approve_funds(self, request, requestor):
        print(f"[{self.agent_name}] Reviewing fund request from {requestor}...")
        # Risk logic
        approved = True
        if approved:
            self.send(requestor, "FUNDS_APPROVED", {"amount": request.get("amount")})
        else:
            self.send(requestor, "FUNDS_DENIED", {"reason": "Risk limit exceeded"})

from ..strands.agent import BaseAgent
from ..strands.a2a import Message
import random

class TrendScoutAgent(BaseAgent):
    def __init__(self, name="TrendScout"):
        super().__init__(name, role="Sentiment Analysis")

    def handle_message(self, message: Message):
        if message.msg_type == "GOAL" and message.content.get("task") == "analyze_sentiment":
            asset = message.content.get("asset")
            self.analyze_sentiment(asset, message.sender)
        else:
            super().handle_message(message)

    def analyze_sentiment(self, asset, requestor):
        print(f"[{self.agent_name}] Analyzing sentiment for {asset}...")
        # Mock sentiment analysis
        # In reality, this would scrape Twitter/Reddit
        sentiment_score = random.uniform(-1, 1)
        insight = {
            "asset": asset,
            "sentiment": sentiment_score,
            "source": "MockSocials"
        }
        self.send(requestor, "MARKET_INSIGHT", insight)

class ChartistAgent(BaseAgent):
    def __init__(self, name="Chartist"):
        super().__init__(name, role="Technical Analysis")

    def handle_message(self, message: Message):
        if message.msg_type == "GOAL" and message.content.get("task") == "analyze_technical":
            asset = message.content.get("asset")
            self.analyze_technical(asset, message.sender)
        else:
            super().handle_message(message)

    def analyze_technical(self, asset, requestor):
        print(f"[{self.agent_name}] Computing indicators for {asset}...")
        # Mock TA
        rsi = random.uniform(30, 70)
        macd = random.uniform(-0.5, 0.5)
        insight = {
            "asset": asset,
            "rsi": rsi,
            "macd": macd
        }
        self.send(requestor, "MARKET_INSIGHT", insight)

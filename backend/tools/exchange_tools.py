from __future__ import annotations

import os
from typing import Any, Dict, Optional

import ccxt
from dotenv import load_dotenv

load_dotenv()


class BinanceTool:
    """
    Binance Spot & Futures execution adapter supporting Testnet (`BINANCE_TESTNET=true`).
    Public market data (`get_price`) works without API keys; authenticated order placement
    and balance checks require `BINANCE_API_KEY` and `BINANCE_SECRET_KEY`.
    """

    def __init__(self, testnet: Optional[bool] = None) -> None:
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY", "")
        self.is_testnet = (
            testnet
            if testnet is not None
            else os.getenv("BINANCE_TESTNET", "true").lower() in ("true", "1", "yes")
        )

        has_valid_keys = bool(
            self.api_key
            and self.secret_key
            and self.api_key != "your_api_key"
            and self.secret_key != "your_secret_key"
        )
        self.authenticated = has_valid_keys

        cfg: Dict[str, Any] = {"enableRateLimit": True}
        if has_valid_keys:
            cfg["apiKey"] = self.api_key
            cfg["secret"] = self.secret_key

        self.exchange = ccxt.binance(cfg)
        if self.is_testnet:
            self.exchange.set_sandbox_mode(True)

    def get_price(self, symbol: str = "SOL/USDT") -> Optional[float]:
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception as exc:
            print(f"[BinanceTool] Error fetching ticker {symbol}: {exc}")
            return None

    def get_usdt_balance(self) -> Dict[str, Any]:
        if not self.authenticated:
            return {"status": "unauthenticated", "free_usdt": 0.0}
        try:
            bal = self.exchange.fetch_balance()
            usdt = bal.get("USDT", {})
            return {
                "status": "ok",
                "testnet": self.is_testnet,
                "free_usdt": float(usdt.get("free", 0.0)),
                "total_usdt": float(usdt.get("total", 0.0)),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        post_only: bool = True,
    ) -> Dict[str, Any]:
        if not self.authenticated:
            return {"status": "error", "message": "Binance API keys not configured"}

        try:
            order_type = "limit" if price else "market"
            params = {"postOnly": True} if (price and post_only) else {}
            order = self.exchange.create_order(symbol, order_type, side, amount, price, params)
            return {"status": "success", "testnet": self.is_testnet, "order": order}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}


class DexTool:
    """
    Jupiter v6 Quote & Swap adapter for Solana Mainnet / Shadow-Mode simulation.
    """

    def __init__(self) -> None:
        self.api_url = "https://quote-api.jup.ag/v6"

    def get_quote(self, input_mint: str, output_mint: str, amount: int) -> Dict[str, Any]:
        return {"input_mint": input_mint, "output_mint": output_mint, "amount": amount, "impact_bps": 10}

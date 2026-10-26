from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()


class SolanaWalletTool:
    """
    Read-only Solana RPC client.

    The tool holds no signing key, derives no public key from private material,
    signs nothing, and broadcasts nothing. ``public_address`` is the only
    configured address input (``SOLANA_PUBLIC_KEY``), and it is used solely to
    read a balance. ``custody`` is ``NONE`` and every value it reports is
    simulation-only.
    """

    custody = "NONE"
    simulated = True

    def __init__(self, rpc_url: Optional[str] = None) -> None:
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
        self.public_address: Optional[str] = os.getenv("SOLANA_PUBLIC_KEY") or None

    def _rpc_call(self, method: str, params: list[Any]) -> Dict[str, Any]:
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode("utf-8")
        req = urllib.request.Request(
            self.rpc_url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Robotrader/0.2"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_balance(self, address: Optional[str] = None) -> Optional[float]:
        """Returns the balance of a configured public address, or ``None``.

        ``None`` means "not measured": either no address is configured or the
        RPC call failed. It is never reported as a zero balance.
        """
        target = address or self.public_address
        if not target:
            return None
        try:
            resp = self._rpc_call("getBalance", [target, {"commitment": "confirmed"}])
            lamports = int(resp.get("result", {}).get("value", 0))
            return lamports / 1e9
        except Exception:
            return None

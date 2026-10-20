from __future__ import annotations

import base64
import json
import os
import urllib.request
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from solders.hash import Hash  # type: ignore
from solders.keypair import Keypair  # type: ignore
from solders.message import Message  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.system_program import TransferParams, transfer  # type: ignore
from solders.transaction import Transaction  # type: ignore

load_dotenv()


class SolanaWalletTool:
    """
    Solana RPC & Ed25519 signing tool compatible with `solders` (solana >= 0.36).
    Supports Devnet, Testnet, and Mainnet-Beta RPC endpoints, including pre-flight
    `simulateTransaction` verification before broadcasting.
    """

    def __init__(self, rpc_url: Optional[str] = None, private_key: Optional[str] = None) -> None:
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
        raw_priv = private_key or os.getenv("SOLANA_PRIVATE_KEY")
        self.keypair: Optional[Keypair] = None

        if raw_priv and raw_priv != "your_private_key_array_or_base58":
            try:
                if "[" in raw_priv:
                    raw_bytes = json.loads(raw_priv)
                    self.keypair = Keypair.from_bytes(bytes(raw_bytes))
                else:
                    self.keypair = Keypair.from_base58_string(raw_priv)
            except Exception as exc:
                print(f"[SolanaWalletTool] Error loading Solana keypair: {exc}")

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

    def get_balance(self, address: Optional[str] = None) -> float:
        target = address or (str(self.keypair.pubkey()) if self.keypair else None)
        if not target:
            return 0.0
        try:
            resp = self._rpc_call("getBalance", [target, {"commitment": "confirmed"}])
            lamports = int(resp.get("result", {}).get("value", 0))
            return lamports / 1e9
        except Exception as exc:
            print(f"[SolanaWalletTool] Error getting balance: {exc}")
            return 0.0

    def get_latest_blockhash(self) -> Hash:
        resp = self._rpc_call("getLatestBlockhash", [{"commitment": "confirmed"}])
        bh_str = resp["result"]["value"]["blockhash"]
        return Hash.from_string(bh_str)

    def transfer_sol(
        self, to_address: str, amount_sol: float, simulate_only: bool = False
    ) -> Dict[str, Any]:
        if not self.keypair:
            return {"status": "error", "message": "No private key loaded"}

        try:
            to_pubkey = Pubkey.from_string(to_address)
            lamports = int(amount_sol * 1e9)
            ix = transfer(
                TransferParams(
                    from_pubkey=self.keypair.pubkey(),
                    to_pubkey=to_pubkey,
                    lamports=lamports,
                )
            )
            recent_bh = self.get_latest_blockhash()
            msg = Message.new_with_blockhash([ix], self.keypair.pubkey(), recent_bh)
            txn = Transaction([self.keypair], msg, recent_bh)
            raw_tx_b64 = base64.b64encode(bytes(txn)).decode("ascii")

            if simulate_only:
                sim = self._rpc_call(
                    "simulateTransaction",
                    [raw_tx_b64, {"encoding": "base64", "commitment": "confirmed"}],
                )
                err = sim.get("result", {}).get("value", {}).get("err")
                return {
                    "status": "simulated" if err is None else "error",
                    "err": err,
                    "units_consumed": sim.get("result", {}).get("value", {}).get("unitsConsumed"),
                }

            sent = self._rpc_call(
                "sendTransaction",
                [raw_tx_b64, {"encoding": "base64", "preflightCommitment": "confirmed"}],
            )
            if "error" in sent:
                return {"status": "error", "message": str(sent["error"])}
            return {"status": "success", "signature": sent.get("result")}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

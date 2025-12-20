from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
from solders.pubkey import Pubkey # type: ignore
from solders.keypair import Keypair # type: ignore
import os

class SolanaWalletTool:
    def __init__(self):
        self.rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        self.client = Client(self.rpc_url)
        self.private_key = os.getenv("SOLANA_PRIVATE_KEY")
        
        if self.private_key:
            # Assuming private key is stored as list of integers or base58 string
            # This is a simplified loading logic
            try:
                if "[" in self.private_key:
                    import json
                    raw_key = json.loads(self.private_key)
                    self.keypair = Keypair.from_bytes(bytes(raw_key))
                else:
                    self.keypair = Keypair.from_base58_string(self.private_key)
            except Exception as e:
                print(f"Error loading Solana key: {e}")
                self.keypair = None
        else:
            self.keypair = None

    def get_balance(self, address: str = None):
        if not address and self.keypair:
            pubkey = self.keypair.pubkey()
        elif address:
            pubkey = Pubkey.from_string(address)
        else:
            return 0.0

        try:
            resp = self.client.get_balance(pubkey)
            return resp.value / 1e9 # Lamports to SOL
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0

    def transfer_sol(self, to_address: str, amount: float):
        if not self.keypair:
            return {"status": "error", "message": "No private key loaded"}

        try:
            to_pubkey = Pubkey.from_string(to_address)
            lamports = int(amount * 1e9)
            
            txn = Transaction().add(
                transfer(
                    TransferParams(
                        from_pubkey=self.keypair.pubkey(),
                        to_pubkey=to_pubkey,
                        lamports=lamports
                    )
                )
            )
            
            resp = self.client.send_transaction(txn, self.keypair)
            return {"status": "success", "signature": str(resp.value)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

"""Contract tests for the simulated vault boundary and the read-only Solana path.

These tests use temporary fake binaries and mocked venues. They never touch the
real ``engine-rs/target`` binary and never issue a network call.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.core.hierarchy import HierarchicalFleetManager
from backend.core.memory_palace import StrategyMemoryPalace
from backend.core.state_store import HybridStateStore
from backend.tools.solana_tools import SolanaWalletTool

SIMULATED_MANIFEST = {
    "vault_version": "robotrader-simulated-vault/v1",
    "vault_mode": "SIMULATED",
    "execution_mode": "PAPER",
    "simulated": True,
    "simulation_notice": "SIMULATED VAULT: addresses are not spendable.",
    "seed_source": "DETERMINISTIC_DEVNET",
    "master_seed_fingerprint": "vault-fp-test",
    "python_private_key_access": False,
    "whitelist_enforcement": "SIMULATED",
    "simulated_whitelist_entry_count": 17,
    "canonical_bridge_contracts_count": 6,
    "wallets": [
        {
            "leaf_id": "leaf-solana",
            "chain": "Solana",
            "symbol": "SOL",
            "simulated": True,
            "address_is_spendable": False,
            "target_leaf_derivation_path": "m/44'/501'/1'/0/0",
        }
    ],
}

SIMULATED_RECEIPT = {
    "leaf_id": "leaf-solana",
    "chain": "Solana",
    "vault_mode": "SIMULATED",
    "simulated": True,
    "signature_is_chain_valid": False,
    "signature_is_cryptographic": False,
    "signature_scheme": "SIMULATED_HMAC_SHA256",
    "whitelist_enforcement": "SIMULATED",
    "signer_address": "simulated-signer",
    "destination_address": "SolanaDestination123",
    "amount_usd": 100.0,
    "token": "SOL",
    "destination_whitelisted": True,
    "signature_hex": "0xsimulatedaudittoken",
    "key_zeroized_after_sign": True,
}

CRYPTO_HD_MANIFEST = {
    "vault_version": "3.0.0",
    "vault_mode": "CRYPTO_HD_BIP32",
    "execution_mode": "PAPER",
    "simulated": False,
    "simulation_notice": "Cryptographic HD vault BIP-32/SLIP-0010 active.",
    "seed_source": "DETERMINISTIC_DEVNET",
    "master_seed_fingerprint": "vault-fp-crypto-test",
    "python_private_key_access": False,
    "whitelist_enforcement": "STRICT_FORMAT_AND_ALLOWLIST",
    "simulated_whitelist_entry_count": 44,
    "canonical_bridge_contracts_count": 6,
    "wallets": [
        {
            "leaf_id": "leaf-solana",
            "chain": "Solana",
            "symbol": "SOL",
            "simulated": False,
            "address_is_spendable": True,
            "target_leaf_derivation_path": "m/44'/501'/0'/0'",
        },
        {
            "leaf_id": "leaf-canton",
            "chain": "Canton",
            "symbol": "CC",
            "simulated": False,
            "address_is_spendable": False,
            "target_leaf_derivation_path": "m/44'/999999'/1'/0/0",
        },
    ],
}

CRYPTO_HD_RECEIPT = {
    "leaf_id": "leaf-solana",
    "chain": "Solana",
    "vault_mode": "CRYPTO_HD_BIP32",
    "simulated": False,
    "signature_is_chain_valid": False,
    "signature_is_cryptographic": True,
    "signature_scheme": "ED25519",
    "whitelist_enforcement": "STRICT_FORMAT_AND_ALLOWLIST",
    "signer_address": "941Cj1UTqcshruE19PXwK7jcctd4r9dDpKTrNzY1B62u",
    "destination_address": "SolanaDestination123",
    "amount_usd": 100.0,
    "token": "SOL",
    "destination_whitelisted": True,
    "signature_hex": "0xeadb6ba8c590438d0eb45dcb658810a126becdcedbfe200b116982c9745543cbdcbd74ead701f7ad137a9233b18cbffd3edd6b1da6e56ae788789f0a7fe6ea04",
    "key_zeroized_after_sign": True,
}


class FakeSolanaWallet:
    custody = "NONE"
    simulated = True

    def __init__(self, rpc_url=None) -> None:
        self.rpc_url = rpc_url or "fake://solana"
        self.public_address = "ReadOnlyPublicAddress"
        self.balance_calls = []

    def get_balance(self, address=None):
        self.balance_calls.append(address)
        return None

    def transfer_sol(self, *args, **kwargs):
        raise AssertionError("the simulated path must never sign or transfer")


class FakeBinance:
    authenticated = True

    def __init__(self, *args, **kwargs) -> None:
        self.exchange = self

    def fetch_order_book(self, symbol, limit=5):
        return {"bids": [[100.0, 10.0]], "asks": [[100.1, 5.0]]}

    def get_price(self, symbol="SOL/USDT"):
        return 100.0

    def place_order(self, *args, **kwargs):
        return {"status": "error", "message": "not reached by the simulated branch"}

    def get_usdt_balance(self):
        return {"status": "error"}


class SimulatedVaultTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def manager_with_candidate(self, candidate: Path) -> HierarchicalFleetManager:
        palace = StrategyMemoryPalace(storage_path=self.root / "palace.jsonl")
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            return HierarchicalFleetManager(palace=palace)

    def script(self, name: str, body: str, executable: bool = True) -> Path:
        path = self.root / name
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        if executable:
            path.chmod(0o755)
        return path

    def json_script(self, name: str, payload: dict, exit_code: int = 0) -> Path:
        body = "cat <<'EOF'\n" + json.dumps(payload) + "\nEOF\nexit " + str(exit_code)
        return self.script(name, body)


class LoaderMatrixTest(SimulatedVaultTestBase):
    def test_missing_candidate_is_unavailable(self) -> None:
        manager = self.manager_with_candidate(self.root / "absent-robotrader-node")
        self.assertEqual(manager.vault_manifest, {})
        self.assertEqual(manager.vault_manifest_error, "unavailable")

    def test_timeout_is_unavailable(self) -> None:
        candidate = self.script("timeout-node", "exit 0")
        palace = StrategyMemoryPalace(storage_path=self.root / "palace.jsonl")
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ), mock.patch(
            "backend.core.hierarchy.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="fake", timeout=5),
        ):
            manager = HierarchicalFleetManager(palace=palace)
        self.assertEqual(manager.vault_manifest, {})
        self.assertEqual(manager.vault_manifest_error, "timeout")

    def test_non_zero_exit_is_unavailable(self) -> None:
        manager = self.manager_with_candidate(self.script("nonzero-node", "exit 3"))
        self.assertEqual(manager.vault_manifest, {})
        self.assertEqual(manager.vault_manifest_error, "non_zero_exit")

    def test_unparsable_output_is_unavailable(self) -> None:
        manager = self.manager_with_candidate(
            self.script("unparsable-node", "printf 'not-json'")
        )
        self.assertEqual(manager.vault_manifest, {})
        self.assertEqual(manager.vault_manifest_error, "unparsable")

    def test_old_contract_is_unavailable(self) -> None:
        manager = self.manager_with_candidate(
            self.json_script(
                "old-node",
                {"vault_mode": "DEVNET_DETERMINISTIC_ENCLAVE", "wallets": [{}]},
            )
        )
        self.assertEqual(manager.vault_manifest, {})
        self.assertEqual(manager.vault_manifest_error, "invalid_contract")

    def test_valid_simulated_manifest_is_served_unchanged(self) -> None:
        manager = self.manager_with_candidate(
            self.json_script("valid-node", SIMULATED_MANIFEST)
        )
        self.assertEqual(manager.vault_manifest, SIMULATED_MANIFEST)
        self.assertIsNone(manager.vault_manifest_error)

    def test_valid_crypto_manifest_is_served_unchanged(self) -> None:
        manager = self.manager_with_candidate(
            self.json_script("valid-crypto-node", CRYPTO_HD_MANIFEST)
        )
        self.assertEqual(manager.vault_manifest, CRYPTO_HD_MANIFEST)
        self.assertIsNone(manager.vault_manifest_error)


class SignerMatrixTest(SimulatedVaultTestBase):
    def test_unavailable_binary_rejects_without_signature(self) -> None:
        manager = self.manager_with_candidate(self.root / "absent-robotrader-node")
        with mock.patch.object(
            HierarchicalFleetManager,
            "_rust_binary_candidates",
            return_value=[self.root / "absent-robotrader-node"],
        ):
            result = manager.sign_transfer_in_rust_enclave(
                "Solana", "SolanaDestination123", 100.0, "SOL"
            )
        self.assertEqual(result["status"], "rejected_vault_unavailable")
        for field in ("signature_hex", "destination_whitelisted", "key_zeroized_after_sign"):
            self.assertNotIn(field, result)

    def test_non_zero_exit_is_rejected_by_rust_enclave(self) -> None:
        candidate = self.json_script(
            "rejected-node",
            {"status": "rejected_by_rust_enclave", "error": "not whitelisted"},
            exit_code=1,
        )
        manager = self.manager_with_candidate(candidate)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.sign_transfer_in_rust_enclave(
                "Solana", "SolanaDestination123", 100.0, "SOL"
            )
        self.assertEqual(result["status"], "rejected_by_rust_enclave")
        self.assertNotIn("signature_hex", result)

    def test_valid_simulated_receipt_is_signed(self) -> None:
        candidate = self.json_script("signed-node", SIMULATED_RECEIPT)
        manager = self.manager_with_candidate(candidate)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.sign_transfer_in_rust_enclave(
                "Solana", "SolanaDestination123", 100.0, "SOL"
            )
        self.assertEqual(result["status"], "signed")
        self.assertEqual(result["vault_mode"], "SIMULATED")
        self.assertTrue(result["simulated"])
        self.assertFalse(result["signature_is_chain_valid"])
        self.assertFalse(result["signature_is_cryptographic"])
        self.assertEqual(result["signature_scheme"], "SIMULATED_HMAC_SHA256")
        self.assertEqual(result["whitelist_enforcement"], "SIMULATED")

    def test_valid_crypto_receipt_is_signed(self) -> None:
        candidate = self.json_script("signed-crypto-node", CRYPTO_HD_RECEIPT)
        manager = self.manager_with_candidate(candidate)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.sign_transfer_in_rust_enclave(
                "Solana", "SolanaDestination123", 100.0, "SOL"
            )
        self.assertEqual(result["status"], "signed")
        self.assertEqual(result["vault_mode"], "CRYPTO_HD_BIP32")
        self.assertFalse(result["simulated"])
        self.assertFalse(result["signature_is_chain_valid"])
        self.assertTrue(result["signature_is_cryptographic"])
        self.assertEqual(result["signature_scheme"], "ED25519")
        self.assertEqual(result["whitelist_enforcement"], "STRICT_FORMAT_AND_ALLOWLIST")

    def test_crypto_receipt_with_chain_valid_true_is_rejected(self) -> None:
        bad_receipt = dict(CRYPTO_HD_RECEIPT)
        bad_receipt["signature_is_chain_valid"] = True
        candidate = self.json_script("bad-receipt-node", bad_receipt)
        manager = self.manager_with_candidate(candidate)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.sign_transfer_in_rust_enclave(
                "Solana", "SolanaDestination123", 100.0, "SOL"
            )
        self.assertEqual(result["status"], "rejected_vault_unavailable")

    def test_old_contract_receipt_is_unavailable(self) -> None:
        candidate = self.json_script(
            "old-receipt-node", {"leaf_id": "Solana", "signature_hex": "0xabc"}
        )
        manager = self.manager_with_candidate(candidate)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.sign_transfer_in_rust_enclave(
                "Solana", "SolanaDestination123", 100.0, "SOL"
            )
        self.assertEqual(result["status"], "rejected_vault_unavailable")
        self.assertNotIn("signature_hex", result)

    def test_destination_or_amount_mismatch_is_unavailable(self) -> None:
        candidate = self.json_script("mismatch-node", SIMULATED_RECEIPT)
        manager = self.manager_with_candidate(candidate)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            wrong_amount = manager.sign_transfer_in_rust_enclave(
                "Solana", "SolanaDestination123", 101.0, "SOL"
            )
            wrong_destination = manager.sign_transfer_in_rust_enclave(
                "Solana", "OtherDestination456", 100.0, "SOL"
            )
        self.assertEqual(wrong_amount["status"], "rejected_vault_unavailable")
        self.assertEqual(wrong_destination["status"], "rejected_vault_unavailable")
        self.assertNotIn("signature_hex", wrong_amount)

    def test_kill_switch_blocks_before_consulting_a_binary(self) -> None:
        candidate = self.json_script("kill-node", SIMULATED_RECEIPT)
        manager = self.manager_with_candidate(candidate)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ), mock.patch(
            "backend.core.hierarchy.subprocess.run",
            side_effect=AssertionError("binary must not be consulted"),
        ):
            result = manager.sign_transfer_in_rust_enclave(
                "Solana",
                "SolanaDestination123",
                100.0,
                "SOL",
                kill_switch_active=True,
                kill_switch_reason="operator stop",
            )
        self.assertEqual(result["status"], "rejected_by_rust_enclave")
        self.assertEqual(result["error"], "operator stop")
        self.assertNotIn("signature_hex", result)


class CheckoutMutationTest(SimulatedVaultTestBase):
    def _snapshot(self, manager: HierarchicalFleetManager) -> tuple:
        return (
            manager.total_capital_usd,
            {lid: leaf["allocated_capital_usd"] for lid, leaf in manager.leaves.items()},
            list(manager.checkout_history),
            manager.dry_powder_usd,
        )

    def test_unavailable_vault_rejects_without_mutation(self) -> None:
        candidate = self.root / "absent-robotrader-node"
        manager = self.manager_with_candidate(candidate)
        before = self._snapshot(manager)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.checkout_funds(
                amount_usd=100.0,
                target_chain="Solana",
                target_token="SOL",
                quote_only=False,
            )
        self.assertEqual(result["status"], "rejected_vault_unavailable")
        self.assertNotIn("signature_hex", result)
        self.assertEqual(self._snapshot(manager), before)

    def test_kill_switch_rejects_without_mutation(self) -> None:
        candidate = self.json_script("valid-node", SIMULATED_RECEIPT)
        manager = self.manager_with_candidate(candidate)
        before = self._snapshot(manager)
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.checkout_funds(
                amount_usd=100.0,
                target_chain="Solana",
                target_token="SOL",
                quote_only=False,
                kill_switch_active=True,
                kill_switch_reason="operator stop",
            )
        self.assertEqual(result["status"], "rejected_by_rust_enclave")
        self.assertEqual(result["message"], "operator stop")
        self.assertEqual(self._snapshot(manager), before)

    def test_crypto_vault_checkout_mutates_capital(self) -> None:
        candidate = self.json_script("crypto-node", CRYPTO_HD_RECEIPT)
        manager = self.manager_with_candidate(candidate)
        before_total = manager.total_capital_usd
        before_sol = manager.leaves["leaf-solana"]["allocated_capital_usd"]
        with mock.patch.object(
            HierarchicalFleetManager, "_rust_binary_candidates", return_value=[candidate]
        ):
            result = manager.checkout_funds(
                amount_usd=100.0,
                target_chain="Solana",
                target_token="SOL",
                destination_address="SolanaDestination123",
                quote_only=False,
            )
        self.assertEqual(result["status"], "completed")
        receipt = result["receipt"]
        sim_receipt = receipt["simulated_vault_receipt"]
        self.assertEqual(sim_receipt["vault_mode"], "CRYPTO_HD_BIP32")
        self.assertFalse(sim_receipt["simulated"])
        self.assertTrue(sim_receipt["signature_is_cryptographic"])
        self.assertFalse(sim_receipt["signature_is_chain_valid"])
        self.assertEqual(sim_receipt["whitelist_enforcement"], "STRICT_FORMAT_AND_ALLOWLIST")
        self.assertEqual(manager.total_capital_usd, before_total - 100.0)


class SolanaCustodyTest(SimulatedVaultTestBase):
    def test_environment_key_is_ignored_and_no_send_path_exists(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"SOLANA_PRIVATE_KEY": "ignored-test-value", "SOLANA_PUBLIC_KEY": ""},
            clear=False,
        ):
            tool = SolanaWalletTool()
        self.assertFalse(hasattr(tool, "keypair"))
        self.assertFalse(hasattr(tool, "transfer_sol"))
        self.assertIsNone(tool.public_address)
        self.assertEqual(tool.custody, "NONE")
        self.assertTrue(tool.simulated)

    def test_get_balance_returns_none_without_address_or_on_rpc_error(self) -> None:
        with mock.patch.dict(os.environ, {"SOLANA_PUBLIC_KEY": ""}, clear=False):
            tool = SolanaWalletTool()
        self.assertIsNone(tool.get_balance())

        with mock.patch.dict(
            os.environ, {"SOLANA_PUBLIC_KEY": "ReadOnlyPublicAddress"}, clear=False
        ):
            configured = SolanaWalletTool()
        with mock.patch(
            "backend.tools.solana_tools.urllib.request.urlopen",
            side_effect=OSError("rpc down"),
        ):
            self.assertIsNone(configured.get_balance())

    def test_telemetry_has_no_fabricated_balance(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "REDIS_URL": "",
                "SOLANA_PUBLIC_KEY": "",
                "SOLANA_RPC_URL": "https://api.devnet.solana.com",
            },
            clear=False,
        ):
            store = HybridStateStore()
        telemetry = store.get_testnet_telemetry()
        self.assertTrue(telemetry["enabled"])
        self.assertIsNone(telemetry["solana_balance_sol"])

    def test_simulated_tick_never_broadcasts_and_is_excluded_from_measured(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "REDIS_URL": "",
                "SOLANA_PUBLIC_KEY": "",
                "SOLANA_RPC_URL": "https://api.devnet.solana.com",
            },
            clear=False,
        ):
            store = HybridStateStore()
        from backend.core.schemas import PolicyEnvelope

        policy = PolicyEnvelope.default_active()
        for pod_id, allocation in policy.pod_allocations.items():
            allocation.enabled = pod_id == "pod_onchain_alpha"
            allocation.capital_weight = 0.2 if pod_id == "pod_onchain_alpha" else 0.0
        store.set_policy(policy)

        measured_before = store.measured_realized_pnl_usd()
        live_trades_before = store.get_population_metrics()["live_testnet"]["recent"][
            "trades"
        ]
        paper_trades_before = store.get_population_metrics()["paper_model"]["recent"][
            "trades"
        ]

        with mock.patch(
            "backend.tools.exchange_tools.BinanceTool", FakeBinance
        ), mock.patch("backend.tools.solana_tools.SolanaWalletTool", FakeSolanaWallet):
            report = store.run_live_testnet_tick()

        self.assertIsNotNone(report)
        self.assertEqual(report["venue"], "SOLANA_DEVNET_ONCHAIN")
        self.assertIsNone(report["tx_signature"])
        self.assertEqual(report["source"], "SIMULATED")
        self.assertTrue(report["is_simulated"])
        self.assertEqual(report["pnl_type"], "SIMULATED_SELF_TX")
        self.assertNotIn("gas_fee_sol", report)
        self.assertEqual(store.solana_devnet_tx_count, 0)
        self.assertEqual(store.solana_devnet_gas_sol, 0.0)
        self.assertIsNone(store.testnet_wallet_snapshot["solana_balance_sol"])
        self.assertEqual(store.measured_realized_pnl_usd(), measured_before)
        population = store.get_population_metrics()
        self.assertEqual(
            population["live_testnet"]["recent"]["trades"], live_trades_before
        )
        self.assertEqual(
            population["paper_model"]["recent"]["trades"], paper_trades_before + 1
        )


TESTNET_VERIFY_CHILD = r"""
import json
from pathlib import Path
from unittest import mock

from backend.core.hierarchy import HierarchicalFleetManager

mock.patch.object(
    HierarchicalFleetManager,
    "_rust_binary_candidates",
    staticmethod(lambda: [Path("/nonexistent/robotrader-node")]),
).start()

from backend.agents.orchestrator import OrchestratorAgent
from backend.core import state_store as state_store_module

OrchestratorAgent.start_cognitive_scheduler = lambda self: None
state_store_module.HybridStateStore.start_live_worker = lambda self, interval_sec=10.0: None


class FakeBinance:
    authenticated = False

    def __init__(self, *args, **kwargs):
        pass

    def get_price(self, symbol="SOL/USDT"):
        return None

    def get_usdt_balance(self):
        return {"status": "error"}


mock.patch("backend.tools.exchange_tools.BinanceTool", FakeBinance).start()

import backend.server as server
from fastapi.testclient import TestClient

client = TestClient(server.app)
response = client.get("/api/v1/testnet/verify")
assert response.status_code == 200, (response.status_code, response.text)
payload = response.json()
wallet = payload["solana_wallet"]
assert "public_key" not in wallet, wallet
assert wallet.get("custody") == "NONE", wallet
assert wallet.get("public_address") is None, wallet
assert wallet.get("balance_sol") is None, wallet
assert "private" not in json.dumps(payload).lower(), payload
print("testnet verify contract ok")
"""


class TestnetVerifyEndpointTest(unittest.TestCase):
    def test_verify_endpoint_exposes_no_python_held_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-c", TESTNET_VERIFY_CHILD],
                capture_output=True,
                text=True,
                timeout=120,
                env={
                    **os.environ,
                    "SOLANA_PRIVATE_KEY": "ignored-test-value",
                    "SOLANA_PUBLIC_KEY": "",
                    "REDIS_URL": "",
                    "COSTGUARD_LEDGER_PATH": str(
                        Path(tmp) / "transcript_ledger.jsonl"
                    ),
                },
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("testnet verify contract ok", result.stdout)


if __name__ == "__main__":
    unittest.main()

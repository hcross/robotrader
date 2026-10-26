# Robotrader v3 — Simulated Vault & Key Boundaries

**Reference implementation**
- Rust simulated vault: [`engine-rs/crates/risk-gate/src/vault.rs`](../engine-rs/crates/risk-gate/src/vault.rs) (`SimulatedVault`, `ZeroizingBytes<N>`, `sha256`, `hmac_sha256`)
- Canonical types: [`engine-rs/crates/common/src/lib.rs`](../engine-rs/crates/common/src/lib.rs) (`CryptographicCurve`, `PublicWalletDescriptor`, `SimulatedVaultManifest`, `SignedTransferReceipt`, `ExecutionMode`, `SeedSource`)
- Rust CLI: [`engine-rs/crates/node/src/main.rs`](../engine-rs/crates/node/src/main.rs) (`robotrader-node --vault-manifest`, `robotrader-node --sign-transfer`)
- Python boundary: [`backend/core/hierarchy.py`](../backend/core/hierarchy.py) and `GET /api/v1/vault/manifest`

---

## 1. What the Vault Is, and What It Is Not

The vault is **`SIMULATED`**. It is useful as a deterministic, testable stand-in
for wallet orchestration and as a place to keep the no-key-in-Python boundary.
It is not a cryptographic enclave.

| Property | Current simulated behavior |
|---|---|
| Derivation | Deterministic HMAC-SHA256 pseudo-derivation over a target path; no real BIP-32/BIP-44/SLIP-0010/CIP-1852 hierarchy is implemented. |
| Addresses | Non-spendable character-mapped strings. `address_is_spendable` is `false` on every descriptor. |
| Signatures | 32-byte HMAC audit tokens. `signature_is_chain_valid` is `false`; no chain can broadcast them. |
| Whitelist | A prefix filter over non-spendable destinations, labelled `whitelist_enforcement: "SIMULATED"`. It is not a production allowlist. |
| Custody | None. No mainnet key custody, hardware module, or remote signer exists. |
| Python | Holds no key, reads no seed, fabricates no manifest, and broadcasts nothing. |

`simulation_notice` states addresses are not spendable and receipts are not
chain-valid. Curves, target derivation paths, and target SLIP-44 values are
target metadata, not an implemented guarantee.

The real work — vetted derivation, real address encoding, chain signatures,
exact per-chain allowlists, and mainnet custody — remains open in issue #2.

---

## 2. Manifest Contract

The Rust type is `SimulatedVaultManifest`; `GET /api/v1/vault/manifest` serves
its JSON unchanged, or HTTP 503 when the binary is unavailable or stale.

```json
{
  "vault_version": "robotrader-simulated-vault/v1",
  "vault_mode": "SIMULATED",
  "execution_mode": "PAPER",
  "simulated": true,
  "simulation_notice": "SIMULATED VAULT: addresses are not spendable on any chain and receipts are not chain-valid. Curves, target derivation paths, and target SLIP-44 values are target metadata only; no mainnet key custody exists.",
  "seed_source": "DETERMINISTIC_DEVNET",
  "master_seed_fingerprint": "vault-fp-...",
  "python_private_key_access": false,
  "whitelist_enforcement": "SIMULATED",
  "simulated_whitelist_entry_count": 17,
  "canonical_bridge_contracts_count": 6,
  "wallets": [
    {
      "leaf_id": "leaf-solana",
      "chain": "Solana",
      "symbol": "SOL",
      "curve": "ED25519_SLIP0010",
      "simulated": true,
      "address_is_spendable": false,
      "target_slip44_coin_type": 501,
      "target_master_derivation_path": "m/44'/501'/0'/0/0",
      "target_leaf_derivation_path": "m/44'/501'/1'/0/0",
      "master_treasury_address": "...",
      "leaf_hot_address": "...",
      "key_fingerprint": "fp-..."
    }
  ]
}
```

Every wallet descriptor carries `simulated: true` and
`address_is_spendable: false`. The unqualified path and coin-type field names
are not part of the contract.

### Receipt contract

```json
{
  "leaf_id": "leaf-solana",
  "chain": "Solana",
  "curve": "ED25519_SLIP0010",
  "simulated": true,
  "signature_is_chain_valid": false,
  "whitelist_enforcement": "SIMULATED",
  "signer_address": "...",
  "destination_address": "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN",
  "amount_usd": 1500.0,
  "token": "SOL",
  "destination_whitelisted": true,
  "signature_hex": "0x...",
  "key_zeroized_after_sign": true
}
```

`destination_whitelisted` is assigned from the predicate evaluated in the same
signing call. When the predicate returns `false`, signing returns an error and
no receipt is produced. `key_zeroized_after_sign` is read from the ephemeral
buffer after scrubbing.

---

## 3. Execution Mode and Seed Precedence

`ROBOTRADER_EXECUTION_MODE` accepts exactly four case-sensitive values:

| Value | Effective mode | Seed when the secret file and environment seed are empty |
|---|---|---|
| absent | `PAPER` | deterministic devnet seed (`DETERMINISTIC_DEVNET`) |
| `BACKTEST` | `BACKTEST` | deterministic devnet seed |
| `PAPER` | `PAPER` | deterministic devnet seed |
| `SIMULATED` | `SIMULATED` | deterministic devnet seed |
| `LIVE` | `LIVE` | construction fails (`MissingLiveSeed`) |
| empty, whitespace-only, `paper`, `PAPER `, ` Paper`, unknown, non-Unicode | construction fails | no manifest, no receipt, exit 2 |

There is no trimming and no case folding. The seed precedence is:

1. A readable `/run/secrets/robotrader_master_seed` with non-empty trimmed
   content selects `SECRET_FILE`; the environment seed is ignored.
2. Otherwise a non-empty trimmed `ROBOTRADER_VAULT_MASTER_SEED` selects
   `ENVIRONMENT`.
3. Otherwise `LIVE` fails; `BACKTEST`, `PAPER`, and `SIMULATED` use the
   deterministic devnet seed and report `DETERMINISTIC_DEVNET`.

An unreadable or empty secret file is treated as absent. `LIVE` is not a
custody claim: it still exports a `SIMULATED` manifest.

The CLI accepts `--vault-secret-file <path>` solely to make precedence tests
hermetic. Production uses the default secret mount path.

---

## 4. Python Boundary

- `HierarchicalFleetManager` never fabricates a manifest. Without a valid
  `SIMULATED` manifest from `robotrader-node`, `vault_manifest` is `{}` and the
  API returns HTTP 503. The backend still starts and its non-vault endpoint
  contracts are unchanged.
- `sign_transfer_in_rust_enclave` never uses a Python HMAC or local signing
  primitive. It returns `signed` only for a receipt that satisfies every
  simulation field and matches the requested leaf, destination, and amount.
  Every other outcome carries no receipt fields.
- `checkout_funds` passes the live kill-switch state to the signer and returns
  a structured rejection before mutating total capital, leaf allocations,
  checkout history, or dry powder.
- `SolanaWalletTool` is read-only: no signing keypair, no key-derived public
  key, no transfer, no broadcast. `get_balance` returns `None` when no address
  is configured or the RPC call fails; `custody` is `NONE`.
- `run_live_testnet_tick` records Solana Devnet actions as `SIMULATED`, with
  `tx_signature: None`, and excludes them from measured live performance.

---

## 5. 26 Target-Metadata Rows

The table below is target metadata. It does not describe an implemented
derivation or address encoding.

| `leaf_id` | Blockchain / venue | Target curve identifier | Target SLIP-44 | Target master path | Target leaf path |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `leaf-solana` | Solana | `ED25519_SLIP0010` | `501` | `m/44'/501'/0'/0/0` | `m/44'/501'/1'/0/0` |
| `leaf-bitcoin` | Bitcoin | `SECP256K1_SCHNORR_TAPROOT` | `0` | `m/84'/0'/0'/0/0` | `m/84'/0'/1'/0/0` |
| `leaf-ethereum` | Ethereum | `SECP256K1_ECDSA_BIP44` | `60` | `m/44'/60'/0'/0/0` | `m/44'/60'/1'/0/0` |
| `leaf-sui` | Sui | `ED25519_SLIP0010` | `784` | `m/44'/784'/0'/0/0` | `m/44'/784'/1'/0/0` |
| `leaf-hyperliquid` | Hyperliquid | `SECP256K1_ECDSA_BIP44` | `60` | `m/44'/60'/0'/0/0` | `m/44'/60'/1'/0/0` |
| `leaf-bnb` | BNB Chain | `SECP256K1_ECDSA_BIP44` | `714` | `m/44'/714'/0'/0/0` | `m/44'/714'/1'/0/0` |
| `leaf-xrp` | XRP Ledger | `SECP256K1_ECDSA_BIP44` | `144` | `m/44'/144'/0'/0/0` | `m/44'/144'/1'/0/0` |
| `leaf-ton` | TON | `ED25519_SLIP0010` | `607` | `m/44'/607'/0'/0/0` | `m/44'/607'/1'/0/0` |
| `leaf-tron` | TRON | `SECP256K1_ECDSA_BIP44` | `195` | `m/44'/195'/0'/0/0` | `m/44'/195'/1'/0/0` |
| `leaf-avalanche` | Avalanche | `SECP256K1_ECDSA_BIP44` | `9000` | `m/44'/9000'/0'/0/0` | `m/44'/9000'/1'/0/0` |
| `leaf-cosmos` | Cosmos Hub | `SECP256K1_ECDSA_BIP44` | `118` | `m/44'/118'/0'/0/0` | `m/44'/118'/1'/0/0` |
| `leaf-aptos` | Aptos | `ED25519_SLIP0010` | `637` | `m/44'/637'/0'/0/0` | `m/44'/637'/1'/0/0` |
| `leaf-chainlink` | Chainlink | `SECP256K1_ECDSA_BIP44` | `60` | `m/44'/60'/0'/0/0` | `m/44'/60'/1'/0/0` |
| `leaf-stacks` | Stacks | `SECP256K1_ECDSA_BIP44` | `5757` | `m/44'/5757'/0'/0/0` | `m/44'/5757'/1'/0/0` |
| `leaf-near` | NEAR | `ED25519_SLIP0010` | `397` | `m/44'/397'/0'/0/0` | `m/44'/397'/1'/0/0` |
| `leaf-cardano` | Cardano | `ED25519_CIP1852` | `1815` | `m/1852'/1815'/0'/0/0` | `m/1852'/1815'/1'/0/0` |
| `leaf-polkadot` | Polkadot | `SR25519_SUBSTRATE` | `354` | `m/44'/354'/0'/0/0` | `m/44'/354'/1'/0/0` |
| `leaf-dogecoin` | Dogecoin | `SECP256K1_ECDSA_BIP44` | `3` | `m/44'/3'/0'/0/0` | `m/44'/3'/1'/0/0` |
| `leaf-icp` | Internet Computer | `ED25519_SLIP0010` | `223` | `m/44'/223'/0'/0/0` | `m/44'/223'/1'/0/0` |
| `leaf-canton` | Canton Network | `MTLS_X509_PARTICIPANT` | `9991` | `m/44'/9991'/0'/0/0` | `m/44'/9991'/1'/0/0` |
| `leaf-celo` | Celo | `SECP256K1_ECDSA_BIP44` | `52752` | `m/44'/52752'/0'/0/0` | `m/44'/52752'/1'/0/0` |
| `leaf-tezos` | Tezos | `ED25519_SLIP0010` | `1729` | `m/44'/1729'/0'/0/0` | `m/44'/1729'/1'/0/0` |
| `leaf-flow` | Flow | `SECP256K1_ECDSA_BIP44` | `539` | `m/44'/539'/0'/0/0` | `m/44'/539'/1'/0/0` |
| `leaf-eos` | Vaulta (ex-EOS) | `SECP256K1_ECDSA_BIP44` | `194` | `m/44'/194'/0'/0/0` | `m/44'/194'/1'/0/0` |
| `leaf-binance-cex` | Binance CEX | `HMAC_SHA256_NO_WITHDRAW` | `714` | `m/44'/714'/0'/0/0` | `m/44'/714'/1'/0/0` |
| `leaf-paper-sandbox` | Paper Sandbox | `VIRTUAL_ZERO_KEY` | `0` | `m/44'/0'/0'/0/0` | `m/44'/0'/1'/0/0` |

---

## 6. Inspection Commands

```bash
# Public simulated manifest (26 descriptors)
./engine-rs/target/debug/robotrader-node --vault-manifest

# Accepted simulated destination -> simulated receipt
./engine-rs/target/debug/robotrader-node --sign-transfer --leaf-id Solana \
  --dest FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN --amount-usd 1500 --token SOL

# Rejected destination -> error, exit 1, no receipt
./engine-rs/target/debug/robotrader-node --sign-transfer --leaf-id Solana \
  --dest attacker_drain_wallet_999 --amount-usd 1500 --token SOL
```

Hermetic seed and mode checks pass `--vault-secret-file <path>`; production uses
`/run/secrets/robotrader_master_seed`.

---

## 7. Non-Goals

- No real BIP-32/BIP-44/SLIP-0010/CIP-1852 derivation is implemented.
- No real secp256k1, ed25519, or sr25519 address encoding or chain signature is implemented.
- No mainnet key custody, hardware security module, or remote signer exists.
- The prefix whitelist is not an exact per-chain allowlist, and it enforces no
  network or amount policy.
- Solana signing is removed from Python, not relocated into Rust.

See [ADR-0005](adr/0005-vault-is-simulated.md) for the decision record and
issue #2 for the remaining cryptography work.

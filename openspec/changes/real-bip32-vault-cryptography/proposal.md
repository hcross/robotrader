## Review Card (≤ 5 min)

| Field | Value |
|---|---|
| Outcome | Implement genuine BIP-32/SLIP-0010 HD key derivation, spendable public address generation across 23 cryptographic chains, strict destination allowlisting, and Ed25519/Secp256k1 signing to fully close Issue #2. |
| Why now | Issue #2 audit revealed that the simulated vault uses non-cryptographic HMAC pseudo-derivation and non-spendable addresses; production readiness requires real cryptographic derivation, strict destination allowlisting, and verifiable signing. |
| Blast radius | `engine-rs` (`risk-gate`, `common`, `node`), `backend/core/hierarchy.py`, `backend/server.py`. |
| Risk | Low. Mode defaults to `SIMULATED`, preserving 100% of existing behavior and test suites; invalid seeds, malformed addresses, or unlisted destinations fail closed. |
| Effort | L (Large, 3 review stages: spec, plan, dev). |
| Decision needed | None. |

```mermaid
flowchart LR
    Seed["Master Seed (32/64B)"] --> HD{"HD Derivation Engine"}
    HD -->|"SLIP-0010 / CIP-1852"| EdKeys["Ed25519 (Solana, Sui, Aptos, TON, Near, ADA, ICP, XTZ)"]
    HD -->|"BIP-32 / BIP-44"| SecpKeys["Secp256k1 (EVMx6, BTC, ATOM, TRX, XRP, DOGE, STX, FLOW, EOS)"]
    HD -->|"Substrate / Institutional"| OtherKeys["Polkadot (Sr25519), Canton (mTLS), Binance CEX, Sandbox"]
    EdKeys --> Addrs["Spendable Addresses (B58, EIP-55, Bech32, Base58Check)"]
    SecpKeys --> Addrs
    OtherKeys --> Addrs
    Addrs --> Gate{"Strict Format & Exact Allowlist"}
    Gate -->|"Valid & Whitelisted"| Signer{"Cryptographic Signer"}
    Signer -->|"Ed25519 Dalek"| EdSig["64B Ed25519 Signature"]
    Signer -->|"k256 ECDSA"| SecpSig["64B Compact ECDSA Signature"]
```

## Why

Issue #2 established that the initial vault enclave was non-cryptographic: key derivation used single-round HMAC over an ASCII path, addresses were synthetic character mappings with `address_is_spendable: false`, and signatures were 32-byte HMAC audit tokens.
Earlier change #12 truthfully marked this infrastructure as `SIMULATED` to avoid false claims; now we deliver complete closure of Issue #2 by adding `CryptographicVault` alongside `SimulatedVault`.

Real cryptographic key derivation (BIP-32 and SLIP-0010), spendable address formatting with EIP-55/Bech32/Base58Check checksums, strict address validation, exact destination allowlisting, and authentic Ed25519/Secp256k1 digital signatures provide verified on-chain readiness while preserving full testability.
Crucially, signed receipts truthfully state `signature_is_chain_valid: false` (since receipts authorize internal checkout transfers rather than raw mempool transactions) and `signature_is_cryptographic: true`.

## What Changes

- Add `CryptographicVault` in `engine-rs/crates/risk-gate/src/vault.rs` implementing BIP-32 and SLIP-0010 hierarchical deterministic key derivation.
- Support SLIP-0010 Ed25519 and CIP-1852 child key derivation for Solana, Sui, Aptos, TON, Near, Cardano, ICP, and Tezos.
- Support standard BIP-32/BIP-44 Secp256k1 child key derivation for 6 EVM ecosystems (Ethereum, BNB Chain, Avalanche, Hyperliquid, Celo, Chainlink) plus Bitcoin, Cosmos, TRON, XRP Ledger, Dogecoin, Stacks, Flow, and EOS.
- Support Sr25519 Substrate derivation for Polkadot, and preserve explicit non-BIP32 handling for Canton (`MtlsX509Participant`), Binance CEX (`HmacSha256NoWithdraw`), and Paper Sandbox (`VirtualZeroKey`).
- Implement spendable address derivation with exact checksum formats across all 23 cryptographic ecosystems (`address_is_spendable: true`), while retaining `address_is_spendable: false` for the 3 non-BIP32 institutional/simulated leaves.
- Implement strict chain-specific address validator `validate_chain_address(chain, address)` enforcing structural constraints and checksum validation before signing.
- Implement exact destination allowlist enforcement (`whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`), eliminating broad single-character prefix bypasses and rejecting unlisted destinations.
- Implement genuine digital signing: 64-byte Ed25519 signatures via `ed25519-dalek` and 64-byte compact ECDSA signatures via `k256`, with public verification function `verify_checkout_signature`.
- Update `SignedTransferReceipt` in `common` and Python schemas to include `vault_mode`, `signature_is_cryptographic`, and `signature_scheme`, setting `signature_is_chain_valid: false` to honestly reflect that checkout receipts are internal authorization tokens rather than broadcastable raw transactions.
- Provide runtime vault selection via `ROBOTRADER_VAULT_MODE`: defaults to `SIMULATED` (instantiating `SimulatedVault`), activates `CryptographicVault` when set to `CRYPTO_HD_BIP32`.
- Update `backend/core/hierarchy.py` and `backend/server.py` to validate and serve both `SIMULATED` and `CRYPTO_HD_BIP32` manifests and receipts without compromising fail-closed boundaries.

## Capabilities

### New Capabilities
- `bip32-cryptographic-vault`: Real BIP-32/SLIP-0010 HD key derivation, spendable public address generation across 23 cryptographic chains, strict chain address format and checksum validation, exact destination allowlist enforcement, and Ed25519/Secp256k1 cryptographic signing.

### Modified Capabilities
- `vault-simulation`: Scope simulated vault requirements and invariants to `ROBOTRADER_VAULT_MODE=SIMULATED` (default), support `CRYPTO_HD_BIP32` mode when configured, and update receipt/manifest schema definitions.

## Non-goals

- Python key custody or on-chain transaction broadcast: Python remains zero-custody and never holds private keys.
- Direct live transaction broadcasting to public blockchain mempools: broadcast belongs to downstream node execution tooling, not the vault signing boundary.
- Hardware Enclave / HSM physical module integration (e.g., AWS Nitro Enclaves, Ledger/Trezor USB): out of scope for software HD enclave.
- Replacing or removing `SimulatedVault`: simulated mode remains intact, default, and fully supported for CI and paper testing.

## Impact

- Affected crates: `engine-rs/crates/risk-gate`, `engine-rs/crates/common`, `engine-rs/crates/node`.
- Affected Python services: `backend/core/hierarchy.py`, `backend/server.py`, `backend/core/schemas.py`.
- Dependencies: Standard Rust cryptography crates in `engine-rs` (`ed25519-dalek`, `k256`, `sha2`, `hmac`, `ripemd`, `bs58`, `bech32`, `sha3`).
- API & Contract: Manifest and receipt schemas support `vault_mode: "CRYPTO_HD_BIP32"` with `simulated: false`, `signature_is_cryptographic: true`, and `address_is_spendable: true` alongside existing `SIMULATED` contract.

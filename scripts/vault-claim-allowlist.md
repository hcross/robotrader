# Vault claim-sweep allowlist — justifications

`scripts/vault-claim-allowlist.txt` is the executable, **patterns-only** file
consumed by `grep -vEf`. It contains exactly one ERE per line, with no comments
and no blank lines, so a malformed entry fails the gate instead of making it
vacuous. This document is the audit trail; it is not consumed by the gate.

| Pattern | Justification |
|---|---|
| `(Secp256k1EcdsaBip44\|SECP256K1_ECDSA_BIP44)` | The `CryptographicCurve` variant identifier. The enum doc comment states these are target scheme metadata, not implemented. The uppercase form appears only in the target-metadata table of the vault document. |
| `(Secp256k1SchnorrTaproot\|SECP256K1_SCHNORR_TAPROOT)` | Target scheme identifier for Bitcoin; not an implemented derivation. |
| `(Ed25519Slip0010\|ED25519_SLIP0010)` | Target scheme identifier used by Solana/Sui/Aptos/TON/NEAR/ICP/Tezos rows; not an implemented derivation. |
| `(Ed25519Cip1852\|ED25519_CIP1852)` | Target scheme identifier for Cardano; not an implemented derivation. |
| `(Sr25519Substrate\|SR25519_SUBSTRATE)` | Target scheme identifier for Polkadot; not an implemented derivation. |
| `(HmacSha256NoWithdraw\|HMAC_SHA256_NO_WITHDRAW)` | Target authentication identifier for the CEX venue; not an implemented exchange-withdrawal guard. |
| `(MtlsX509Participant\|MTLS_X509_PARTICIPANT)` | Target authentication identifier for Canton; not implemented custody. |
| `(VirtualZeroKey\|VIRTUAL_ZERO_KEY)` | Target identifier for the paper sandbox; names no real key. |
| `SimulatedVault` | The honest replacement name for the vault and its manifest. It asserts simulation, not a guarantee. |
| `sign_transfer_in_rust_enclave` | The spec-mandated Python method name, retained because the approved spec names it; it now delegates to the simulated Rust vault and holds no key. |
| `ROBOTRADER_VAULT_MASTER_SEED` | A supported seed-source variable name; it carries no value in the repository and never enters Python. |

No entry permits a claim that an address is spendable, a receipt is
broadcastable, a chain signature is produced, or a simulated Solana action is
measured. Such a claim must be removed or qualified, never allowlisted.

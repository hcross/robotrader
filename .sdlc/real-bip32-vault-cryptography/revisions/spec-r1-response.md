stage: spec
round: 1
reviewed_sha: 52859b0d1c3cf3d877160bab54f6af3e630a8ad8
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: >-
      Listed `vault-simulation` under `Modified Capabilities` in `proposal.md`.
      Created `openspec/changes/real-bip32-vault-cryptography/specs/vault-simulation/spec.md`
      with full `## MODIFIED Requirements` blocks copying all 8 requirements from
      `openspec/specs/vault-simulation/spec.md` and scoping simulation invariants to
      `ROBOTRADER_VAULT_MODE=SIMULATED` (default) while supporting `CRYPTO_HD_BIP32`.
      Documented the dual-mode architecture update to the `openspec/config.yaml` invariant.
  - id: SPEC-R1-F02
    action: fixed
    evidence: >-
      Requirement `Cryptographic checkout signing and honest receipt validity` in
      `bip32-cryptographic-vault/spec.md` and related scenarios now mandate
      `signature_is_chain_valid: false` for checkout receipts. Added `signature_is_cryptographic: true`
      and `signature_scheme: "ED25519" | "SECP256K1_ECDSA"` to distinguish authentic cryptographic
      digital signatures from FNV-1a/HMAC simulation, while truthfully documenting that receipts
      authorize internal checkout transfers rather than raw broadcastable mempool transactions.
  - id: SPEC-R1-F03
    action: fixed
    evidence: >-
      Defined the `SignedTransferReceipt` schema updates across `engine-rs/crates/common/src/lib.rs`
      and `backend/core/schemas.py`, adding `vault_mode: String`, `signature_is_cryptographic: bool`,
      and `signature_scheme: String`. Specified that `CryptographicVault` emits
      `whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`, and updated Python receipt validation
      in `backend/core/hierarchy.py` to validate both `SIMULATED` and `CRYPTO_HD_BIP32` receipts.
  - id: SPEC-R1-F04
    action: fixed
    evidence: >-
      Reconciled catalog with exact 26 leaves in `vault.rs`: removed hallucinated `stellar`,
      added `leaf-chainlink` under Secp256k1 EVM (`m/44'/60'/0'/0/1`), categorized `leaf-polkadot`
      under `SR25519_SUBSTRATE` with Substrate derivation, and explicitly specified behavior for
      non-BIP32 leaves: `leaf-canton` (`MtlsX509Participant`), `leaf-binance-cex` (`HmacSha256NoWithdraw`),
      and `leaf-paper-sandbox` (`VirtualZeroKey`), setting `address_is_spendable: false` for all three.
  - id: SPEC-R1-F05
    action: fixed
    evidence: >-
      Requirements `Spendable public address derivation across all 26 catalog leaves` and
      `Strict chain-specific address syntax and checksum validation` in `bip32-cryptographic-vault/spec.md`
      now specify exact derivation algorithms, encodings, and checksum standards for all 26 leaves
      grouped by family (EVM EIP-55, Solana B58, Bitcoin Bech32 bc1q, Cosmos Bech32 cosmos1,
      TRON Base58Check T, Dogecoin Base58Check D, XRP Base58Check r, Move 0x64 hex for Sui/Aptos,
      NEAR 64-hex, TON EQ, Cardano addr1, Polkadot SS58, ICP principal, Tezos tz1, Stacks SP,
      Flow 0x16, Canton, Binance CEX, and Paper Sandbox), complete with test scenarios.
  - id: SPEC-R1-F06
    action: fixed
    evidence: >-
      Added Requirement `Destination allowlist enforcement for CryptographicVault` and scenarios
      in `bip32-cryptographic-vault/spec.md`. `CryptographicVault` sets `whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`
      and requires BOTH syntactic address/checksum validity AND exact match against the operator
      allowlist (`ROBOTRADER_VAULT_ALLOWED_DESTINATIONS`, mounted allowlist file, or vault's own
      derived addresses and canonical bridge URIs). Broad single-character prefixes (`0x`, `r`, `T`, `D`, `bc1q`)
      are strictly rejected and prohibited from acting as wildcards.
  - id: SPEC-R1-F07
    action: fixed
    evidence: >-
      Requirement 1 in `bip32-cryptographic-vault/spec.md` now specifies seed resolution precedence:
      secret file `/run/secrets/robotrader_master_seed`, then `ROBOTRADER_VAULT_MASTER_SEED_HEX`
      (minimum 64 hex characters for 32 bytes). In `LIVE` mode, construction fails closed without
      an explicit master seed; in non-live modes, deterministic devnet seeds are rejected unless
      `ROBOTRADER_VAULT_ALLOW_TEST_SEED=1` is explicitly set.
  - id: SPEC-R1-F08
    action: fixed
    evidence: >-
      Updated Mermaid diagram in `proposal.md` to accurately summarize all curve families
      (SLIP-0010/CIP-1852 Ed25519, BIP-32/44 Secp256k1 including XRP and Dogecoin, Sr25519 Polkadot,
      and institutional leaves) and the two-stage Strict Format & Exact Allowlist gate.

# SPEC Review — Round 2

## Summary
Approved (Round 2). All eight findings from Round 1 (SPEC-R1-F01 through SPEC-R1-F08) are fully resolved at commit 14382f5a348039afaf4c644e4e8094905c3311c0. The author added the missing `vault-simulation` modified capability with full delta requirements preserving simulation invariants under `ROBOTRADER_VAULT_MODE=SIMULATED`. Signed transfer receipt contracts now truthfully set `signature_is_chain_valid: false`, certifying receipts as cryptographic authorization tokens rather than broadcastable mempool transactions, while adding `signature_is_cryptographic: true` and `signature_scheme`. All 26 catalog leaves are reconciled with exact derivation algorithms, spendable address formats, and checksum standards. Strict destination allowlisting (`whitelist_enforcement: STRICT_FORMAT_AND_ALLOWLIST`) replaces broad single-character prefixes with exact operator allowlists. With zero open blockers and zero open majors, the specification is sound and ready for plan stage.

## Findings

### SPEC-R1-F01 — [blocker] Contradiction with existing vault-simulation spec and missing Modified Capability declaration
- Location: `openspec/changes/real-bip32-vault-cryptography/proposal.md#L54` and `specs/vault-simulation/spec.md`
- Evidence: `proposal.md` now declares `vault-simulation` under `Modified Capabilities`. `specs/vault-simulation/spec.md` provides complete `## MODIFIED Requirements` blocks copying all 8 requirements, scoping simulation invariants to `ROBOTRADER_VAULT_MODE=SIMULATED` while accommodating `CRYPTO_HD_BIP32`.
- Required fix: List vault-simulation under Modified Capabilities in proposal.md, add specs/vault-simulation/spec.md with MODIFIED Requirements scoping simulation invariants to ROBOTRADER_VAULT_MODE=SIMULATED, and document the update to openspec/config.yaml.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [blocker] False `signature_is_chain_valid: true` claim for internal checkout payload signatures
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L149`
- Evidence: Requirement `Cryptographic checkout signing and honest receipt validity` and scenarios explicitly specify `signature_is_chain_valid: false`, truthfully documenting that checkout receipts authorize internal checkout transfers rather than raw broadcastable mempool transactions. Added `signature_is_cryptographic: true` and `signature_scheme` to distinguish digital signatures.
- Required fix: Set signature_is_chain_valid to false (or introduce an unambiguous flag such as signature_is_cryptographic: true), and document that checkout receipts are cryptographic authorization tokens rather than broadcastable transactions.
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [blocker] Receipt contract mismatch: `SignedTransferReceipt` lacks `vault_mode` and unaddressed `whitelist_enforcement`
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L127, L177` and `specs/vault-simulation/spec.md#L83`
- Evidence: `SignedTransferReceipt` schema update is specified across `engine-rs/crates/common/src/lib.rs` and `backend/core/schemas.py` adding `vault_mode`, `signature_is_cryptographic`, and `signature_scheme`. `CryptographicVault` emits `whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`. Python receipt validation in `backend/core/hierarchy.py` accepts both `SIMULATED` and `CRYPTO_HD_BIP32` receipts.
- Required fix: Define the schema update adding vault_mode to SignedTransferReceipt across common/src/lib.rs and schemas.py, specify the exact whitelist_enforcement string emitted by CryptographicVault, and define Python validation for CRYPTO_HD_BIP32 receipts.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [major] Catalog mismatch: hallucinated `stellar`, omitted `leaf-chainlink`, and undefined behavior for non-BIP32 leaves
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L4-L8`
- Evidence: `stellar` removed from catalog; `leaf-chainlink` added under Secp256k1 EVM (`m/44'/60'/0'/0/1`); `leaf-polkadot` curve set to `SR25519_SUBSTRATE` with Substrate derivation; and non-BIP32 leaves (`leaf-canton`, `leaf-binance-cex`, `leaf-paper-sandbox`) explicitly handled with `address_is_spendable: false`. The 26 leaves match the system catalog exactly.
- Required fix: Remove stellar, add chainlink to Secp256k1 and EVM rules, reconcile leaf-polkadot curve/derivation, and specify how CryptographicVault handles non-BIP32 leaves in its manifest and receipts.
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [major] Undefined address derivation algorithms and formats for 13 of 23 cryptographic ecosystems
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L42-L65` and `#L91-L109`
- Evidence: Requirements and scenarios now specify exact derivation algorithms, encodings, and checksum standards for all 26 catalog leaves (EVM EIP-55, Solana B58, Bitcoin Bech32, Cosmos Bech32, TRON B58Check, Dogecoin B58Check, XRP B58Check, Sui Blake2b 0x64, Aptos SHA3 0x64, NEAR 64-hex, TON EQ, Cardano addr1, Polkadot SS58, ICP principal, Tezos tz1, Stacks SP, Flow 0x16, Canton, Binance CEX, Paper Sandbox).
- Required fix: Specify the exact address derivation algorithm, encoding, and checksum standard for every supported ecosystem, or define a phased scope explicitly identifying which ecosystems are implemented, and add test scenarios.
- Status: closed
- Origin: initial

### SPEC-R1-F06 — [major] Destination whitelist enforcement remains unaddressed for `CryptographicVault` (Issue #2 finding #3 unclosed)
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L126-L143`
- Evidence: Requirement `Destination allowlist enforcement for CryptographicVault` and scenarios require both address/checksum validity AND exact match against operator allowlist (`ROBOTRADER_VAULT_ALLOWED_DESTINATIONS`, mounted allowlist file, or vault's own derived addresses and bridge URIs). Broad single-character prefixes (`0x`, `r`, `T`, `D`, `bc1q`) are prohibited from acting as wildcards.
- Required fix: Specify the destination whitelist/allowlist model for CryptographicVault (e.g. strict per-chain operator allowlist with exact matching), specify how destination_whitelisted is evaluated, and add test scenarios verifying rejection of valid non-allowlisted addresses.
- Status: closed
- Origin: initial

### SPEC-R1-F07 — [minor] Missing master seed loading and execution mode specification for `CryptographicVault`
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L9, L37` and `specs/vault-simulation/spec.md#L129`
- Evidence: Master seed resolution precedence is specified (`/run/secrets/robotrader_master_seed`, then `ROBOTRADER_VAULT_MASTER_SEED_HEX`). In `LIVE` mode, missing seed fails closed with `MissingLiveSeed`. In non-live modes, devnet deterministic seeds are rejected unless `ROBOTRADER_VAULT_ALLOW_TEST_SEED=1`.
- Required fix: Specify that CryptographicVault adheres to the seed provenance and LIVE fail-closed resolution order defined in vault-simulation.
- Status: closed
- Origin: initial

### SPEC-R1-F08 — [nit] Proposal Mermaid diagram lists Secp256k1 for EVM / Bitcoin / Cosmos / Tron, but omits XRP and Dogecoin
- Location: `openspec/changes/real-bip32-vault-cryptography/proposal.md#L16`
- Evidence: Node `SecpKeys` now reads `["Secp256k1 (EVMx6, BTC, ATOM, TRX, XRP, DOGE, STX, FLOW, EOS)"]`, including XRP, Dogecoin, and remaining Secp256k1 chains.
- Required fix: Update the SecpKeys node label in the proposal diagram to summarize or list the remaining Secp256k1 chains.
- Status: closed
- Origin: initial

## Checks run
- `openspec validate real-bip32-vault-cryptography --strict` → pass
- `python3 scripts/sdlc/spec-lint.py --change real-bip32-vault-cryptography` → pass (PASS, Review Card: 107 words, 1 diagram, ~1.0 min)
- Read time: 5.5 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "real-bip32-vault-cryptography",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "14382f5a348039afaf4c644e4e8094905c3311c0",
  "verdict": "APPROVE",
  "summary": "Approved at Round 2 with all 8 Round 1 findings resolved: dual-mode vault-simulation capability added, receipt contracts honestly reflect internal checkout authorization, 26-leaf derivation catalog and address formats specified, and strict destination allowlisting enforced.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/proposal.md#L54",
      "evidence": "vault-simulation declared under Modified Capabilities and full delta spec created in specs/vault-simulation/spec.md.",
      "required_fix": "List vault-simulation under Modified Capabilities in proposal.md, add specs/vault-simulation/spec.md with MODIFIED Requirements scoping simulation invariants to ROBOTRADER_VAULT_MODE=SIMULATED, and document the update to openspec/config.yaml."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L149",
      "evidence": "Requirement Cryptographic checkout signing and honest receipt validity sets signature_is_chain_valid: false and signature_is_cryptographic: true.",
      "required_fix": "Set signature_is_chain_valid to false (or introduce an unambiguous flag such as signature_is_cryptographic: true), and document that checkout receipts are cryptographic authorization tokens rather than broadcastable transactions."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L127",
      "evidence": "SignedTransferReceipt schema updated with vault_mode, signature_is_cryptographic, signature_scheme, and whitelist_enforcement specified as STRICT_FORMAT_AND_ALLOWLIST.",
      "required_fix": "Define the schema update adding vault_mode to SignedTransferReceipt across common/src/lib.rs and schemas.py, specify the exact whitelist_enforcement string emitted by CryptographicVault, and define Python validation for CRYPTO_HD_BIP32 receipts."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L4",
      "evidence": "Catalog aligned with 26 leaves: stellar removed, leaf-chainlink added to EVM Secp256k1, leaf-polkadot assigned Sr25519 Substrate, and non-BIP32 leaves handled with address_is_spendable: false.",
      "required_fix": "Remove stellar, add chainlink to Secp256k1 and EVM rules, reconcile leaf-polkadot curve/derivation, and specify how CryptographicVault handles non-BIP32 leaves in its manifest and receipts."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L42",
      "evidence": "Exact address derivation algorithms, encodings, and checksum standards specified for all 26 catalog leaves with test scenarios.",
      "required_fix": "Specify the exact address derivation algorithm, encoding, and checksum standard for every supported ecosystem, or define a phased scope explicitly identifying which ecosystems are implemented, and add test scenarios."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L126",
      "evidence": "Destination allowlist enforcement requirement added requiring valid address syntax and exact operator allowlist match, explicitly rejecting prefix wildcards.",
      "required_fix": "Specify the destination whitelist/allowlist model for CryptographicVault (e.g. strict per-chain operator allowlist with exact matching), specify how destination_whitelisted is evaluated, and add test scenarios verifying rejection of valid non-allowlisted addresses."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L9",
      "evidence": "Seed resolution precedence specified and LIVE mode fail-closed behavior on missing master seed defined.",
      "required_fix": "Specify that CryptographicVault adheres to the seed provenance and LIVE fail-closed resolution order defined in vault-simulation."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/real-bip32-vault-cryptography/proposal.md#L16",
      "evidence": "Mermaid diagram updated to include XRP, DOGE, and remaining Secp256k1 chains in node SecpKeys.",
      "required_fix": "Update the SecpKeys node label in the proposal diagram to summarize or list the remaining Secp256k1 chains."
    }
  ],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04",
    "SPEC-R1-F05",
    "SPEC-R1-F06",
    "SPEC-R1-F07",
    "SPEC-R1-F08"
  ]
}
```

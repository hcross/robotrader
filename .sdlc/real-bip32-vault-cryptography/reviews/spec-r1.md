# SPEC Review — Round 1

## Summary
Changes requested (Round 1). While adding real BIP-32 and SLIP-0010 cryptographic derivation is the right direction to close Issue #2, the specification contains three critical blockers: direct contradiction with the active `vault-simulation` spec without declaring it as a modified capability, a false claim of `signature_is_chain_valid: true` over internal ASCII checkout strings that cannot be broadcast to any blockchain, and an unaligned `SignedTransferReceipt` contract missing `vault_mode` and `whitelist_enforcement`. Furthermore, 13 ecosystems have undefined address formats, destination whitelist enforcement remains open, and catalog inconsistencies include a hallucinated Stellar leaf while omitting Chainlink.

## Findings

### SPEC-R1-F01 — [blocker] Contradiction with existing vault-simulation spec and missing Modified Capability declaration
- Location: `openspec/changes/real-bip32-vault-cryptography/proposal.md#L49`
- Evidence: `openspec/specs/vault-simulation/spec.md#L8` specifies: "Every manifest produced by `export_public_manifest()` MUST set `vault_mode` to the exact string `SIMULATED`", and line 38 specifies: "The manifest, transfer receipts, API responses, UI text, documentation, source docstrings and comments, test names, and process artifacts MUST NOT state that BIP-32, BIP-44, SLIP-0010, CIP-1852, secp256k1, ed25519, sr25519, real address encoding, or chain-valid signing is performed." Furthermore, `openspec/config.yaml#L21` codifies that "The vault is SimulatedVault and every vault surface is SIMULATED... No derivation, address encoding, chain signature, or mainnet custody is claimed as implemented". In `proposal.md#L49`, `Modified Capabilities` is empty, and no delta spec for `vault-simulation` is provided. Merging this change as specified leaves two active specifications in direct contradiction.
- Required fix: List `vault-simulation` under `Modified Capabilities` in `proposal.md`, add `specs/vault-simulation/spec.md` with `## MODIFIED Requirements` scoping simulation invariants to `ROBOTRADER_VAULT_MODE=SIMULATED`, and document the update to the `openspec/config.yaml` hard invariant.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [blocker] False `signature_is_chain_valid: true` claim for internal checkout payload signatures
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L64`
- Evidence: Requirement 4 specifies: "For Ed25519 chains, it MUST generate a 64-byte Ed25519 signature over the SHA-256 digest of the canonical checkout payload. For Secp256k1 chains, it MUST generate a 64-byte compact ECDSA signature over the canonical message digest... Every signed checkout receipt MUST set `simulated` to `false`, `signature_is_chain_valid` to `true`". In `vault.rs#L721`, the canonical checkout payload is an internal formatted text string `"ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}"`. An Ed25519 or compact ECDSA signature over this ASCII string is an internal checkout authorization token; it is NOT an on-chain transaction (e.g. EIP-1559 RLP envelope with gas/nonce/v/r/s for EVM, wire Message for Solana) and cannot be broadcast to any blockchain node. Setting `signature_is_chain_valid: true` reproduces the exact false claim flagged in Issue #2 ("The signature is a 32-byte HMAC, not a chain signature... Nothing here can be broadcast to any chain").
- Required fix: Specify that checkout transfer receipts set `signature_is_chain_valid: false` (or introduce an unambiguous flag such as `signature_is_cryptographic: true`), and document that the receipt signature is a cryptographic checkout authorization token rather than a broadcastable on-chain transaction.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [blocker] Receipt contract mismatch: `SignedTransferReceipt` lacks `vault_mode` and unaddressed `whitelist_enforcement`
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L64`
- Evidence: Requirement 4 mandates: "Every signed checkout receipt MUST set `simulated` to `false`, `signature_is_chain_valid` to `true`, and `vault_mode` to `CRYPTO_HD_BIP32`." However, `SignedTransferReceipt` in `engine-rs/crates/common/src/lib.rs#L249-L263` has no `vault_mode` field. In addition, `SignedTransferReceipt` requires `pub whitelist_enforcement: String`, and `backend/core/hierarchy.py#L1141` fails validation if `receipt.get("whitelist_enforcement") != "SIMULATED"`. The spec does not define what `whitelist_enforcement` value `CryptographicVault` emits, nor does it specify the schema updates for `SignedTransferReceipt` and Python checkout receipt validation.
- Required fix: Define the exact schema changes to `SignedTransferReceipt` across `engine-rs/crates/common/src/lib.rs` and `backend/core/schemas.py`, and explicitly specify the value of `whitelist_enforcement` (and how Python `hierarchy.py` validates `CRYPTO_HD_BIP32` receipts).
- Status: open
- Origin: initial

### SPEC-R1-F04 — [major] Catalog mismatch: hallucinated `stellar`, omitted `leaf-chainlink`, and undefined behavior for non-BIP32 leaves
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L4`
- Evidence: Requirement 1 lists `stellar` as an Ed25519 ecosystem, but Robotrader has no `leaf-stellar` in its 26-leaf fleet (`vault.rs#L220-L430`). Conversely, `leaf-chainlink` (leaf 13, Secp256k1, EVM) is completely omitted from both the Secp256k1 derivation list in Requirement 1 and the EVM address derivation list in Requirement 2. Furthermore, `leaf-polkadot` is assigned `CryptographicCurve::Sr25519Substrate` in the codebase but is categorized under Ed25519 SLIP-0010 in Requirement 1. Finally, the spec does not define how `CryptographicVault` handles the 3 non-BIP32/SLIP-0010 leaves: `leaf-canton` (mTLS), `leaf-binance-cex` (HMAC API keys), and `leaf-paper-sandbox` (virtual zero key).
- Required fix: Remove `stellar`, add `chainlink` to Secp256k1 and EVM requirements, reconcile `leaf-polkadot` curve/derivation, and explicitly specify how `CryptographicVault` handles non-BIP32 leaves (`canton`, `binance-cex`, `paper-sandbox`) in its manifest and receipt generation.
- Status: open
- Origin: initial

### SPEC-R1-F05 — [major] Undefined address derivation algorithms and formats for 13 of 23 cryptographic ecosystems
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L21-L43`
- Evidence: Requirement 2 states that "`CryptographicVault` MUST derive spendable public addresses from public keys matching the canonical encoding of each supported ecosystem", but only specifies encoding rules for EVM, Solana, Bitcoin, Sui, Aptos, Cosmos, and Tron. The address formatting rules, encoding schemes, and checksums for the remaining 13 ecosystems (`xrp`, `dogecoin`, `near`, `ton`, `tezos`, `stacks`, `flow`, `icp`, `cardano`, `polkadot`, `eos`) are completely omitted, and no scenarios exist to test them.
- Required fix: Specify the exact address derivation algorithm, encoding, and checksum standard for every supported ecosystem, or define a phased scope that explicitly lists which ecosystems are implemented in this change and how un-implemented ecosystems are handled. Add corresponding test scenarios.
- Status: open
- Origin: initial

### SPEC-R1-F06 — [major] Destination whitelist enforcement remains unaddressed for `CryptographicVault` (Issue #2 finding #3 unclosed)
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L44-L62`
- Evidence: Issue #2 finding #3 demonstrated that destination whitelist enforcement was broken because prefix matching (`0x`, `bc1q`, `T`, etc.) matched almost any address. Requirement 3 introduces `validate_chain_address(chain: &str, address: &str)` which only validates syntactic address formatting. Validating address syntax does not restrict destinations to an authorized operator whitelist; any validly formatted attacker address passes syntax validation. The spec does not define what whitelist mechanism `CryptographicVault` enforces, whether an exact destination allowlist exists, or how `destination_whitelisted` is evaluated for `CryptographicVault`.
- Required fix: Specify the destination whitelist / allowlist model for `CryptographicVault` (e.g. strict per-chain operator allowlist with exact address matching), specify how `destination_whitelisted` is determined, and add scenarios verifying that syntactically valid but non-whitelisted destinations are rejected.
- Status: open
- Origin: initial

### SPEC-R1-F07 — [minor] Missing master seed loading and execution mode specification for `CryptographicVault`
- Location: `openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L3-L20`
- Evidence: Requirement 1 specifies seed entropy validation (≥ 32 bytes), but does not specify how `CryptographicVault` loads the master seed (precedence between `/run/secrets/robotrader_master_seed` and `ROBOTRADER_VAULT_MASTER_SEED`), how `seed_source` is reported in the manifest, or how `ROBOTRADER_EXECUTION_MODE=LIVE` prevents use of deterministic devnet seeds for `CryptographicVault`.
- Required fix: Specify that `CryptographicVault` follows the seed provenance and `LIVE` fail-closed rules defined in `vault-simulation` or specify the exact seed resolution order.
- Status: open
- Origin: initial

### SPEC-R1-F08 — [nit] Proposal Mermaid diagram lists Secp256k1 for EVM / Bitcoin / Cosmos / Tron, but omits XRP and Dogecoin
- Location: `openspec/changes/real-bip32-vault-cryptography/proposal.md#L16`
- Evidence: Flowchart node `SecpKeys` lists `["EVM / Bitcoin / Cosmos / Tron"]` but omits XRP, Dogecoin, and other Secp256k1 chains.
- Required fix: Add or summarize the remaining Secp256k1 chains in the diagram node label.
- Status: open
- Origin: initial

## Checks run
- `openspec validate real-bip32-vault-cryptography --strict` → pass
- `python3 scripts/sdlc/spec-lint.py --change real-bip32-vault-cryptography` → pass (PASS, Review Card: 102 words, 1 diagram, ~1.0 min)
- Read time: 7.2 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "real-bip32-vault-cryptography",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "52859b0d1c3cf3d877160bab54f6af3e630a8ad8",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Changes requested due to spec contradictions with vault-simulation, false chain-validity claims, receipt contract mismatches, catalog errors, and unaddressed whitelist enforcement.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/proposal.md#L49",
      "evidence": "openspec/specs/vault-simulation/spec.md#L8 specifies that every manifest MUST set vault_mode to SIMULATED, line 38 forbids any claim of BIP-32/SLIP-0010/real derivation, and openspec/config.yaml codifies this as a hard invariant. In proposal.md, Modified Capabilities is empty and no delta spec exists for vault-simulation, creating a direct spec contradiction.",
      "required_fix": "List vault-simulation under Modified Capabilities in proposal.md, add specs/vault-simulation/spec.md with MODIFIED Requirements scoping simulation invariants to ROBOTRADER_VAULT_MODE=SIMULATED, and document the update to openspec/config.yaml."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L64",
      "evidence": "Requirement 4 mandates setting signature_is_chain_valid to true for signatures over the internal ASCII checkout payload ROBOTRADER_V3_TRANSFER|.... This is an internal authorization token, not a broadcastable on-chain transaction (e.g. EIP-1559 RLP or Solana wire Message), recreating the false validity claim audited in Issue #2.",
      "required_fix": "Set signature_is_chain_valid to false (or introduce an unambiguous flag such as signature_is_cryptographic: true), and document that checkout receipts are cryptographic authorization tokens rather than broadcastable transactions."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L64",
      "evidence": "Requirement 4 states that signed receipts set vault_mode to CRYPTO_HD_BIP32, but SignedTransferReceipt in common/src/lib.rs lacks a vault_mode field. Additionally, SignedTransferReceipt requires whitelist_enforcement (checked by Python hierarchy.py), but the spec leaves whitelist_enforcement undefined for CryptographicVault.",
      "required_fix": "Define the schema update adding vault_mode to SignedTransferReceipt across common/src/lib.rs and schemas.py, specify the exact whitelist_enforcement string emitted by CryptographicVault, and define Python validation for CRYPTO_HD_BIP32 receipts."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L4",
      "evidence": "Requirement 1 lists stellar which does not exist in the 26-leaf catalog, omits leaf-chainlink (leaf 13, EVM) from Secp256k1 and EVM rules, misclassifies leaf-polkadot (Sr25519Substrate) as Ed25519 SLIP-0010, and omits handling of non-BIP32 leaves (canton, binance-cex, paper-sandbox).",
      "required_fix": "Remove stellar, add chainlink to Secp256k1 and EVM rules, reconcile leaf-polkadot curve/derivation, and specify how CryptographicVault handles non-BIP32 leaves in its manifest and receipts."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L21-L43",
      "evidence": "Requirement 2 mandates spendable address derivation for all supported ecosystems, but only specifies encoding rules for 7 ecosystems (EVM, Solana, Bitcoin, Sui, Aptos, Cosmos, Tron). The remaining 13 ecosystems (XRP, Dogecoin, Near, TON, Tezos, Stacks, Flow, ICP, Cardano, Polkadot, EOS) have undefined address formatting rules and zero test scenarios.",
      "required_fix": "Specify the exact address derivation algorithm, encoding, and checksum standard for every supported ecosystem, or define a phased scope explicitly identifying which ecosystems are implemented, and add test scenarios."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L44-L62",
      "evidence": "Issue #2 finding #3 flagged open whitelist enforcement due to broad prefix matching. Requirement 3 only adds syntactic address validation (validate_chain_address), which permits any syntactically valid address (including an attacker's). The spec defines no whitelist mechanism, allowlist data structure, or destination_whitelisted evaluation for CryptographicVault.",
      "required_fix": "Specify the destination whitelist/allowlist model for CryptographicVault (e.g. strict per-chain operator allowlist with exact matching), specify how destination_whitelisted is evaluated, and add test scenarios verifying rejection of valid non-allowlisted addresses."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/specs/bip32-cryptographic-vault/spec.md#L3-L20",
      "evidence": "Requirement 1 specifies seed entropy checks, but does not define how CryptographicVault resolves master seed provenance (SECRET_FILE vs ENVIRONMENT) or enforces LIVE mode fail-closed behavior against devnet seeds.",
      "required_fix": "Specify that CryptographicVault adheres to the seed provenance and LIVE fail-closed resolution order defined in vault-simulation."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/real-bip32-vault-cryptography/proposal.md#L16",
      "evidence": "The Mermaid diagram node SecpKeys lists EVM / Bitcoin / Cosmos / Tron but omits XRP, Dogecoin, and other Secp256k1 ecosystems.",
      "required_fix": "Update the SecpKeys node label in the proposal diagram to summarize or list the remaining Secp256k1 chains."
    }
  ],
  "closed": []
}
```

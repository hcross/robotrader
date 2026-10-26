# ADR 0005: The Vault Is Simulated

- **Status**: Accepted
- **Date**: 2026-10-26
- **Deciders**: Hoani Cross (Architect), Claude Code (Technical Sparring Partner)
- **Related**: issue #2, [ADR-0003](0003-hierarchical-multi-ecosystem-architecture.md)

---

## 1. Context and Problem Statement

Issue #2 showed that the vault presented cryptographic guarantees it did not
implement: the derivation was an HMAC over an ASCII path, addresses were
formatted by character mappers, signatures were 32-byte HMAC audit tokens, and
the destination whitelist matched broad prefixes. Python could fabricate both
a manifest and a signature, and it read a Solana private key and broadcast a
self-transfer on every tick.

The most dangerous failure mode was trust: an operator could route capital to
an address no chain can spend, or rely on a whitelist that did not restrict a
destination. A security control that lies is worse than an absent control.

## 2. Decision

The vault is explicitly simulated until real cryptography lands.

- **Rust type and manifest**: the public type is `SimulatedVault` and the
  manifest is `SimulatedVaultManifest`. `vault_mode` is always `SIMULATED`.
  Every wallet descriptor sets `simulated: true` and
  `address_is_spendable: false`. The manifest carries a non-empty
  `simulation_notice` and `whitelist_enforcement: "SIMULATED"`.
- **Target metadata only**: curve identifiers, `target_master_derivation_path`,
  `target_leaf_derivation_path`, and `target_slip44_coin_type` are target
  metadata. They are not an implemented derivation. No real BIP-32/BIP-44/
  SLIP-0010/CIP-1852, secp256k1, ed25519, or sr25519 derivation is implemented,
  and no real address encoding or chain signature exists.
- **Receipts**: every receipt sets `simulated: true`,
  `signature_is_chain_valid: false`, and `whitelist_enforcement: "SIMULATED"`.
  `destination_whitelisted` is assigned from the predicate evaluated in the
  same call; a rejected destination yields no receipt. `key_zeroized_after_sign`
  is read from the buffer after scrubbing, not hardcoded.
- **Execution mode**: `ROBOTRADER_EXECUTION_MODE` accepts exactly `BACKTEST`,
  `PAPER`, `SIMULATED`, and `LIVE`, case-sensitively. Unset means `PAPER`.
  Empty, whitespace-only, unknown, and non-Unicode values fail closed. `LIVE`
  without a secret-mounted or environment seed fails closed. `LIVE` with a
  seed still exports a `SIMULATED` manifest; the mode gates seed selection, not
  custody.
- **Seed provenance**: the manifest reports `seed_source` as `SECRET_FILE`,
  `ENVIRONMENT`, or `DETERMINISTIC_DEVNET`. The secret mount wins; an empty or
  unreadable secret falls through; the deterministic devnet seed is never used
  in `LIVE`.
- **Python boundary**: Python never fabricates a manifest or a signature.
  Without the Rust binary, the manifest endpoint returns HTTP 503 and checkout
  returns a structured rejection before any capital, allocation, history, or
  dry-powder mutation. The kill switch is passed to the signer, not hardcoded.
- **Solana custody**: Python reads no Solana private key, holds no signing
  keypair, and never broadcasts. `SolanaWalletTool` is a read-only RPC client
  over a configured public address (`custody: "NONE"`). Solana Devnet actions
  are recorded as simulated, unsigned, and excluded from measured live
  performance.
- **UI and documentation**: the leaf view always shows a `SIMULATED` badge,
  uses the target leaf path, and renders `address_is_spendable=false`. README,
  AGENTS.md, the architecture document, ADR-0003, the DEV checklist, and the
  OpenSpec invariant tell the same story.

## 3. Alternatives Considered

| Alternative | Rejected because |
|---|---|
| Keep the names and document the behaviour | Documentation does not change a contract that an operator or consumer reads as a guarantee. |
| Implement the real cryptography now | It expands scope into vetted crypto libraries, address encodings, hardware custody, and chain-specific signing; issue #2 remains the right home for that work. |
| Refuse `LIVE` entirely | The approved contract requires `LIVE` to construct with a seed while remaining `SIMULATED`; refusing would hide the mode and break the required seed scenarios. |
| Keep the Python fallback manifest and signer | A Python HMAC signature bypasses the Rust predicate and is not a chain signature; any cached fallback keeps the false claim alive. |
| Keep the Solana key in Python and label the broadcast | Labelling does not remove key custody from the LLM process. |

## 4. Consequences

**Positive**

- Every surface states the same truth: simulation, non-spendable addresses,
  non-chain-valid receipts.
- Python holds no key and cannot fabricate a manifest or signature.
- A live-intended deployment without seed material fails closed instead of
  silently using a repo-visible seed.
- The claim sweep and its self-test keep future documentation honest.

**Negative / accepted trade-offs**

- The manifest and receipt contract is **BREAKING**: `vault_mode`,
  `seed_source`, `simulated`, `address_is_spendable`,
  `signature_is_chain_valid`, `whitelist_enforcement`, and the `target_*`
  renames require consumers to update. The frontend is updated in the same
  change.
- A misconfigured deployment that leaves `ROBOTRADER_EXECUTION_MODE` unset
  runs `PAPER` with the deterministic seed; the manifest exposes both values.
- The simulated prefix whitelist remains broad. It protects non-spendable
  addresses and no longer claims production enforcement; exact per-chain
  allowlists, network allowlists, and amount caps remain open.
- Solana telemetry may show `None` instead of a plausible balance; the UI
  renders an em dash.

## 5. Follow-Up

Issue #2 stays open for the real work, not implemented here: vetted
BIP-32/BIP-44/SLIP-0010/CIP-1852 derivation, real address encoding, chain-valid
signatures, exact per-chain destination allowlists with network and amount
policies, and mainnet key custody. This ADR records the honest-simulation slice
only.

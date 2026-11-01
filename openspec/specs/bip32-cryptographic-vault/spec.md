# bip32-cryptographic-vault Specification

## Purpose
TBD - created by archiving change real-bip32-vault-cryptography. Update Purpose after archive.
## Requirements
### Requirement: Hierarchical deterministic key derivation via BIP-32 and SLIP-0010
The `robotrader-risk-gate` vault implementation SHALL provide `CryptographicVault` implementing standards-compliant hierarchical deterministic key derivation from a 32-byte or 64-byte master seed for all 26 catalog leaves.
- For the 8 Ed25519 ecosystems (`leaf-solana`, `leaf-sui`, `leaf-aptos`, `leaf-ton`, `leaf-near`, `leaf-cardano`, `leaf-icp`, `leaf-tezos`), key derivation MUST follow SLIP-0010 (and CIP-1852 for Cardano) using HMAC-SHA512 with seed key `"ed25519 seed"` and hardened child index paths.
- For the 14 Secp256k1 ecosystems (6 EVM leaves: `leaf-ethereum`, `leaf-hyperliquid`, `leaf-bnb`, `leaf-avalanche`, `leaf-chainlink`, `leaf-celo`; plus 8 non-EVM leaves: `leaf-bitcoin`, `leaf-cosmos`, `leaf-tron`, `leaf-xrp`, `leaf-dogecoin`, `leaf-stacks`, `leaf-flow`, `leaf-eos`), key derivation MUST follow standard BIP-32/BIP-44 using HMAC-SHA512 with seed key `"Bitcoin seed"`, standard elliptic curve point multiplication, and parent key addition modulo curve order `n`.
- For `leaf-polkadot`, key derivation MUST derive a Substrate-compatible keypair using Substrate mini-secret derivation or Sr25519 Schnorrkel key generation.
- For the 3 non-BIP32 leaves (`leaf-canton`, `leaf-binance-cex`, `leaf-paper-sandbox`), the vault MUST derive deterministic participant and trading identifiers from the master seed without generating on-chain private signing keys.
- Master seed resolution MUST follow this precedence: `/run/secrets/robotrader_master_seed`, then `ROBOTRADER_VAULT_MASTER_SEED_HEX`. In `LIVE` mode, construction MUST fail closed if no seed is provided. In non-live modes (`BACKTEST`, `PAPER`, `SIMULATED`), the deterministic devnet seed MUST be rejected unless `ROBOTRADER_VAULT_ALLOW_TEST_SEED=1` is explicitly set. If the provided seed has fewer than 32 bytes of entropy (64 hex characters), initialization MUST fail closed.

#### Scenario: Ed25519 SLIP-0010 child key derivation for Solana
- **WHEN** `CryptographicVault` derives child keys for `leaf-solana` along canonical path `m/44'/501'/0'/0'`
- **THEN** it executes SLIP-0010 hardened derivation using HMAC-SHA512
- **THEN** it yields a valid 32-byte Ed25519 private key and corresponding 32-byte Ed25519 public key

#### Scenario: Secp256k1 BIP-32 child key derivation for Ethereum and Chainlink
- **WHEN** `CryptographicVault` derives child keys for `leaf-ethereum` (path `m/44'/60'/0'/0/0`) and `leaf-chainlink` (path `m/44'/60'/0'/0/1`)
- **THEN** it executes BIP-32 derivation using HMAC-SHA512 and secp256k1 scalar addition
- **THEN** it yields valid 32-byte secp256k1 private keys and corresponding 33-byte compressed and 65-byte uncompressed public keys

#### Scenario: Polkadot Sr25519 key derivation
- **WHEN** `CryptographicVault` derives keys for `leaf-polkadot`
- **THEN** it generates a valid Substrate public key and sets curve metadata to `SR25519_SUBSTRATE`

#### Scenario: Non-BIP32 leaves derive deterministic audit identifiers
- **WHEN** `CryptographicVault` exports wallet descriptors for `leaf-canton`, `leaf-binance-cex`, and `leaf-paper-sandbox`
- **THEN** descriptors report `address_is_spendable: false`
- **THEN** `leaf-canton` reports curve `MTLS_X509_PARTICIPANT`
- **THEN** `leaf-binance-cex` reports curve `HMAC_SHA256_NO_WITHDRAW`
- **THEN** `leaf-paper-sandbox` reports curve `VIRTUAL_ZERO_KEY`

#### Scenario: Master seed validation fails closed on insufficient entropy
- **WHEN** `CryptographicVault` is initialized with a seed having fewer than 32 bytes (64 hex characters)
- **THEN** initialization returns an error
- **THEN** no vault instance is constructed and no keys are derived

#### Scenario: Live mode fails closed without explicit master seed
- **WHEN** `ROBOTRADER_EXECUTION_MODE=LIVE`, no secret file exists, and `ROBOTRADER_VAULT_MASTER_SEED_HEX` is unset
- **THEN** `CryptographicVault` initialization fails closed with `MissingLiveSeed`
- **THEN** devnet deterministic seeds are not loaded

### Requirement: Spendable public address derivation across all 26 catalog leaves
`CryptographicVault` MUST derive public addresses from derived public keys matching the canonical encoding of each ecosystem in the 26-leaf fleet:
- EVM family (`leaf-ethereum`, `leaf-hyperliquid`, `leaf-bnb`, `leaf-avalanche`, `leaf-chainlink`, `leaf-celo`, `leaf-eos`): Keccak-256 of uncompressed public key (last 20 bytes), formatted with EIP-55 mixed-case checksum (`0x` + 40 hex characters).
- Solana (`leaf-solana`): Base58 encoding of 32-byte Ed25519 public key (43-44 characters).
- Bitcoin (`leaf-bitcoin`): Native SegWit Bech32 (`bc1q...`, 42 characters) encoding of RIPEMD160(SHA256(compressed_secp256k1_pubkey)) with witness version 0 and HRP `bc`.
- Cosmos (`leaf-cosmos`): Bech32 with HRP `cosmos` (`cosmos1...`, 45 characters) over RIPEMD160(SHA256(compressed_pubkey)).
- TRON (`leaf-tron`): Base58Check with prefix byte `0x41` + last 20 bytes of Keccak-256 + 4-byte double-SHA256 checksum, starting with `T` (34 characters).
- Dogecoin (`leaf-dogecoin`): Base58Check with version byte `0x1e` + HASH160(compressed_pubkey) + 4-byte checksum, starting with `D` (34 characters).
- XRP Ledger (`leaf-xrp`): Base58Check with version byte `0x00` + HASH160(compressed_pubkey) + 4-byte checksum, starting with `r` (33-34 characters).
- Sui (`leaf-sui`): `0x` + 64 lowercase hex characters of Blake2b-256 over `0x00 || ed25519_pubkey` (66 characters total).
- Aptos (`leaf-aptos`): `0x` + 64 lowercase hex characters of SHA3-256 over `ed25519_pubkey || 0x00` (66 characters total).
- NEAR (`leaf-near`): 64 lowercase hex characters of 32-byte Ed25519 public key.
- TON (`leaf-ton`): Base64url/Base58 bounceable user-friendly address starting with `EQ` (48 characters).
- Cardano (`leaf-cardano`): Bech32 with HRP `addr1` over Shelley payment credential hash.
- Polkadot (`leaf-polkadot`): SS58 address starting with `1` (Substrate SS58 prefix 0).
- Internet Computer (`leaf-icp`): Text representation principal string formatted with dashes (`aaaaa-bbbbb-...-cai`).
- Tezos (`leaf-tezos`): Base58Check with prefix `0x06, 0xa1, 0x9f` (`tz1`) over 20-byte Blake2b hash of Ed25519 public key (36 characters).
- Stacks (`leaf-stacks`): c32check address starting with `SP` (version 22 over 20-byte HASH160).
- Flow (`leaf-flow`): `0x` + 16 hex characters (last 8 bytes of SHA3-256 public key hash).
- Canton (`leaf-canton`): `canton::<role>::<16-hex-fingerprint>`.
- Binance CEX (`leaf-binance-cex`): `binance:leaf-binance-cex:<hex>:trade-only-no-withdraw`.
- Paper Sandbox (`leaf-paper-sandbox`): `sandbox:leaf-paper-sandbox:<role>:virtual-zero-key`.
In the exported manifest, all 23 cryptographic leaves MUST set `address_is_spendable: true` and `simulated: false`. The 3 non-BIP32 leaves (`canton`, `binance-cex`, `paper-sandbox`) MUST set `address_is_spendable: false`.

#### Scenario: EVM address derivation with EIP-55 checksum
- **WHEN** `CryptographicVault` generates the address for `leaf-ethereum` or `leaf-chainlink`
- **THEN** the address starts with `0x`, contains 40 hexadecimal characters, and matches the EIP-55 mixed-case checksum
- **THEN** the wallet descriptor sets `address_is_spendable` to `true` and `simulated` to `false`

#### Scenario: Solana Base58 address derivation
- **WHEN** `CryptographicVault` generates the address for `leaf-solana`
- **THEN** the address is a valid Base58 string decoding to exactly 32 bytes
- **THEN** the wallet descriptor sets `address_is_spendable` to `true` and `simulated` to `false`

#### Scenario: Bitcoin Bech32 native SegWit address derivation
- **WHEN** `CryptographicVault` generates the address for `leaf-bitcoin`
- **THEN** the address starts with `bc1q`, is 42 characters long, and verifies against Bech32 witness v0 checksum
- **THEN** the wallet descriptor sets `address_is_spendable` to `true` and `simulated` to `false`

#### Scenario: Tron and Dogecoin Base58Check derivation
- **WHEN** `CryptographicVault` generates addresses for `leaf-tron` and `leaf-dogecoin`
- **THEN** `leaf-tron` address starts with `T`, is 34 characters long, and verifies against Base58Check version 0x41
- **THEN** `leaf-dogecoin` address starts with `D`, is 34 characters long, and verifies against Base58Check version 0x1e
- **THEN** both wallet descriptors set `address_is_spendable` to `true` and `simulated` to `false`

#### Scenario: Non-spendable leaves set address_is_spendable false
- **WHEN** `CryptographicVault` exports descriptors for `leaf-canton`, `leaf-binance-cex`, or `leaf-paper-sandbox`
- **THEN** `address_is_spendable` is `false`

### Requirement: Strict chain-specific address syntax and checksum validation
The vault module MUST provide a public function `validate_chain_address(chain: &str, address: &str) -> Result<(), AddressValidationError>` that enforces structural, length, alphabet, and checksum rules specific to each blockchain. Any transfer destination address that fails validation MUST cause signing to be rejected before any key is loaded or signature is generated.
- EVM family (`ethereum`, `bnb`, `avalanche`, `hyperliquid`, `celo`, `chainlink`, `eos`): starts with `0x`, exactly 42 characters, valid hex; if mixed-case, capitalization MUST match the EIP-55 checksum.
- Solana (`solana`): valid Base58 string decoding to exactly 32 bytes.
- Bitcoin (`bitcoin`): native SegWit Bech32 starting with `bc1q`, 42 characters, valid Bech32 checksum.
- Cosmos (`cosmos`): Bech32 starting with `cosmos1`, valid Bech32 checksum.
- TRON (`tron`): Base58Check starting with `T`, 34 characters, valid version 0x41 and 4-byte double-SHA256 checksum.
- Dogecoin (`dogecoin`): Base58Check starting with `D`, 34 characters, valid version 0x1e and checksum.
- XRP (`xrp`): Base58Check starting with `r`, 33-34 characters, valid checksum.
- Move family (`sui`, `aptos`): `0x` + 64 lowercase hex characters (66 characters total).
- NEAR (`near`): 64 lowercase hex characters or valid `.near` named account.
- TON (`ton`): 48 characters Base64url/Base58 starting with `EQ` or `UQ`.
- Cardano (`cardano`): Bech32 starting with `addr1`.
- Polkadot (`polkadot`): SS58 format starting with `1`.
- Tezos (`tezos`): Base58Check starting with `tz1` (36 characters).
- Stacks (`stacks`): c32check format starting with `SP`.
- Flow (`flow`): `0x` + 16 hex characters (18 characters total).
- Institutional/simulated: exact format matching `canton::`, `binance:`, `sandbox:`, or `bridge:`.

#### Scenario: EVM invalid address rejected
- **WHEN** `validate_chain_address` is called with chain `ethereum` and an address missing `0x` prefix or having an invalid length
- **THEN** validation returns an error indicating invalid address format

#### Scenario: EVM invalid EIP-55 checksum rejected
- **WHEN** `validate_chain_address` is called with chain `ethereum` and a mixed-case address whose capitalization contradicts the EIP-55 checksum
- **THEN** validation returns an error indicating invalid checksum

#### Scenario: Solana invalid Base58 address rejected
- **WHEN** `validate_chain_address` is called with chain `solana` and an address containing invalid Base58 characters or decoding to a byte count other than 32
- **THEN** validation returns an error indicating invalid address format

#### Scenario: Valid destination passes validation
- **WHEN** `validate_chain_address` is called with a well-formed address for any supported ecosystem
- **THEN** validation returns `Ok(())`

### Requirement: Destination allowlist enforcement for CryptographicVault
`CryptographicVault` MUST enforce strict destination allowlisting (`whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`), completely replacing the broad prefix matching used in simulated mode. A transfer destination MUST be accepted if and only if BOTH conditions hold: (1) `validate_chain_address` returns `Ok(())`, AND (2) the destination exactly matches an entry in the operator allowlist configured via `ROBOTRADER_VAULT_ALLOWED_DESTINATIONS`, a mounted allowlist file `/run/secrets/robotrader_vault_allowlist`, or the vault's own derived master and leaf addresses and canonical bridge URIs (`bridge:cctp:`, `bridge:wormhole:`, `bridge:layerzero:`, `bridge:thorchain:`, `bridge:ibc:`, `bridge:ccip:`). Broad single-character prefixes such as `"0x"`, `"r"`, `"T"`, `"D"`, and `"bc1q"` MUST NOT be recognized as allowlist entries by `CryptographicVault`. When a destination is rejected, signing MUST return a typed `RiskRejection::VaultSigningRejected` error and no receipt MUST be produced.

#### Scenario: Syntactically valid but unlisted destination is rejected
- **WHEN** a transfer destination is syntactically valid for `solana` or `ethereum` but is not present in the operator allowlist
- **THEN** `CryptographicVault` rejects the transfer
- **THEN** no receipt is produced and no key is derived

#### Scenario: Broad prefix is not treated as a wildcard allowlist entry
- **WHEN** destination is an arbitrary EVM address beginning with `0x` or TRON address beginning with `T` not in the operator allowlist
- **THEN** `CryptographicVault` evaluates `destination_whitelisted` as `false`
- **THEN** signing is rejected

#### Scenario: Allowed operator destination is accepted
- **WHEN** destination exactly matches an address configured in `ROBOTRADER_VAULT_ALLOWED_DESTINATIONS` or a canonical bridge URI
- **THEN** `CryptographicVault` accepts the destination with `destination_whitelisted: true`
- **THEN** receipt carries `whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST"`

### Requirement: Cryptographic checkout signing and honest receipt validity
`CryptographicVault` SHALL sign canonical checkout payloads (`ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}`) using standard digital signature algorithms matching the chain curve.
- For Ed25519 chains, it MUST generate a 64-byte Ed25519 signature (128 hex characters prefixed with `0x`) over the SHA-256 digest of the payload.
- For Secp256k1 chains, it MUST generate a 64-byte compact ECDSA signature (128 hex characters prefixed with `0x`) over the canonical message digest.
- The module MUST provide `verify_checkout_signature` to verify the signature against the leaf public key and payload digest.
- Transfer receipts produced by `CryptographicVault` MUST honestly declare `signature_is_chain_valid: false`, certifying that the receipt is an internal cryptographic checkout authorization token rather than a broadcastable raw on-chain transaction.
- Receipts MUST set `vault_mode` to `CRYPTO_HD_BIP32`, `simulated` to `false`, `signature_is_cryptographic` to `true`, and `signature_scheme` to `"ED25519"` or `"SECP256K1_ECDSA"`.
- Derived child private keys MUST be securely zeroized in memory immediately following signature generation, and `key_zeroized_after_sign` MUST reflect an actual check of the key buffer.

#### Scenario: Ed25519 checkout signing and verification
- **WHEN** `CryptographicVault` signs a valid checkout transfer for `leaf-solana`
- **THEN** it generates a 64-byte (128 hex characters) Ed25519 signature
- **THEN** `verify_checkout_signature` evaluates to true when checked against the leaf public key and payload digest
- **THEN** the returned receipt has `vault_mode: "CRYPTO_HD_BIP32"`, `simulated: false`, `signature_is_chain_valid: false`, `signature_is_cryptographic: true`, and `signature_scheme: "ED25519"`
- **THEN** `key_zeroized_after_sign` is `true`

#### Scenario: Secp256k1 ECDSA checkout signing and verification
- **WHEN** `CryptographicVault` signs a valid checkout transfer for `leaf-ethereum`
- **THEN** it generates a 64-byte (128 hex characters) compact ECDSA signature
- **THEN** `verify_checkout_signature` evaluates to true when checked against the leaf public key and payload digest
- **THEN** the returned receipt has `vault_mode: "CRYPTO_HD_BIP32"`, `simulated: false`, `signature_is_chain_valid: false`, `signature_is_cryptographic: true`, and `signature_scheme: "SECP256K1_ECDSA"`
- **THEN** `key_zeroized_after_sign` is `true`

#### Scenario: Tampered signature fails verification
- **WHEN** any byte of an Ed25519 or Secp256k1 signature is modified in a receipt
- **THEN** `verify_checkout_signature` returns false

#### Scenario: Kill switch blocks cryptographic signing
- **WHEN** the kill switch is active and signing is requested
- **THEN** `CryptographicVault` rejects the request with a kill-switch rejection error
- **THEN** no signature is produced and no key is derived

### Requirement: Vault backend selection and fail-closed runtime boundary
The system MUST select between `SimulatedVault` and `CryptographicVault` based on the environment variable `ROBOTRADER_VAULT_MODE`. When `ROBOTRADER_VAULT_MODE` is unset or set to `SIMULATED`, the system MUST instantiate `SimulatedVault`, preserving 100% of existing `vault-simulation` invariants, manifest formats, and test behaviors. When `ROBOTRADER_VAULT_MODE` is set to `CRYPTO_HD_BIP32`, the system MUST instantiate `CryptographicVault`. Any other non-empty value MUST fail closed during initialization. `SignedTransferReceipt` in `common/src/lib.rs` and `backend/core/schemas.py` MUST include `vault_mode`, `signature_is_cryptographic`, and `signature_scheme`. Python services querying the vault manifest and checkout endpoints MUST validate and accept both `SIMULATED` and `CRYPTO_HD_BIP32` valid responses without holding private keys or weakening fail-closed error handling.

#### Scenario: Default mode selects SimulatedVault
- **WHEN** `ROBOTRADER_VAULT_MODE` is unset
- **THEN** the vault backend is `SimulatedVault`
- **THEN** manifest `vault_mode` is `SIMULATED`
- **THEN** `simulated` is `true` and `address_is_spendable` is `false`

#### Scenario: Explicit SIMULATED selects SimulatedVault
- **WHEN** `ROBOTRADER_VAULT_MODE=SIMULATED`
- **THEN** the vault backend is `SimulatedVault`
- **THEN** all existing simulation tests pass without modification

#### Scenario: Explicit CRYPTO_HD_BIP32 selects CryptographicVault
- **WHEN** `ROBOTRADER_VAULT_MODE=CRYPTO_HD_BIP32`
- **THEN** the vault backend is `CryptographicVault`
- **THEN** manifest `vault_mode` is `CRYPTO_HD_BIP32`
- **THEN** `simulated` is `false`, `signature_is_cryptographic` is `true`, and `address_is_spendable` is `true` for cryptographic leaves

#### Scenario: Unknown vault mode fails closed
- **WHEN** `ROBOTRADER_VAULT_MODE` contains an unrecognized string such as `UNSUPPORTED_ENCLAVE`
- **THEN** vault initialization fails closed with a typed error
- **THEN** no manifest and no receipt are generated


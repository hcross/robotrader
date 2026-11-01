## ADDED Requirements

### Requirement: Hierarchical deterministic key derivation via BIP-32 and SLIP-0010
The `robotrader-risk-gate` vault implementation SHALL provide `CryptographicVault` implementing standards-compliant hierarchical deterministic key derivation from a 32-byte or 64-byte master seed. For Ed25519 ecosystems (`solana`, `sui`, `aptos`, `near`, `cardano`, `polkadot`, `ton`, `tezos`, `stellar`, `icp`), key derivation MUST follow SLIP-0010 using HMAC-SHA512 with key `"ed25519 seed"` and hardened child index paths. For Secp256k1 ecosystems (`ethereum`, `bnb`, `avalanche`, `hyperliquid`, `celo`, `bitcoin`, `cosmos`, `tron`, `xrp`, `dogecoin`, `stacks`, `flow`, `eos`), key derivation MUST follow standard BIP-32/BIP-44 using HMAC-SHA512 with key `"Bitcoin seed"`, standard elliptic curve point multiplication, and parent key addition modulo curve order `n`. If the seed contains fewer than 32 bytes of entropy or invalid hex encoding, initialization MUST fail closed.

#### Scenario: Ed25519 SLIP-0010 child key derivation for Solana
- **WHEN** `CryptographicVault` derives child keys for `leaf-solana` along canonical path `m/44'/501'/0'/0'`
- **THEN** it executes SLIP-0010 hardened derivation using HMAC-SHA512
- **THEN** it yields a valid 32-byte Ed25519 private key and corresponding 32-byte Ed25519 public key

#### Scenario: Secp256k1 BIP-32 child key derivation for Ethereum
- **WHEN** `CryptographicVault` derives child keys for `leaf-ethereum` along canonical path `m/44'/60'/0'/0/0`
- **THEN** it executes BIP-32 derivation using HMAC-SHA512 and secp256k1 scalar addition
- **THEN** it yields a valid 32-byte secp256k1 private key and corresponding 33-byte compressed and 65-byte uncompressed public keys

#### Scenario: Master seed validation fails closed on insufficient entropy
- **WHEN** `CryptographicVault` is initialized with a seed having fewer than 32 bytes (64 hex characters)
- **THEN** initialization returns an error
- **THEN** no vault instance is constructed and no keys are derived

### Requirement: Spendable public address derivation with chain-specific formatting
`CryptographicVault` MUST derive spendable public addresses from public keys matching the canonical encoding of each supported ecosystem. For EVM chains (`ethereum`, `bnb`, `avalanche`, `hyperliquid`, `celo`), the public address MUST be the last 20 bytes of Keccak-256 over the uncompressed public key coordinates formatted with EIP-55 mixed-case checksum (`0x` + 40 hex characters). For Solana (`solana`), the address MUST be the Base58 string of the 32-byte Ed25519 public key. For Bitcoin (`bitcoin`), the address MUST be Native SegWit Bech32 (`bc1q...`, 42 characters) encoding of RIPEMD160(SHA256(compressed_pubkey)). For Sui (`sui`) and Aptos (`aptos`), the address MUST be `0x` followed by 64 lowercase hex characters derived from the public key scheme digest. For Cosmos (`cosmos`), the address MUST be Bech32 with human-readable part `cosmos`. For Tron (`tron`), the address MUST be Base58Check with prefix byte `0x41` and a 4-byte double-SHA256 checksum, starting with `T` (34 characters). In the exported manifest, every cryptographically derived wallet MUST set `address_is_spendable` to `true` and `simulated` to `false`.

#### Scenario: EVM address derivation with EIP-55 checksum
- **WHEN** `CryptographicVault` generates the address for `leaf-ethereum`
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

#### Scenario: Tron Base58Check address derivation
- **WHEN** `CryptographicVault` generates the address for `leaf-tron`
- **THEN** the address starts with `T`, contains 34 Base58 characters, and has a valid double-SHA256 checksum
- **THEN** the wallet descriptor sets `address_is_spendable` to `true` and `simulated` to `false`

### Requirement: Strict chain-specific address validation before checkout
The vault module MUST provide a public function `validate_chain_address(chain: &str, address: &str) -> Result<(), AddressValidationError>` that enforces structural, length, alphabet, and checksum rules specific to each blockchain. Destination addresses that fail validation MUST cause signing to be rejected before any key is loaded or signature is generated.

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
- **WHEN** `validate_chain_address` is called with a well-formed address for `solana`, `ethereum`, `bitcoin`, `tron`, `sui`, or `cosmos`
- **THEN** validation returns `Ok(())`

### Requirement: Cryptographic checkout signing and signature verification
`CryptographicVault` SHALL sign checkout transfer payloads using standard digital signature algorithms matching the chain curve. For Ed25519 chains, it MUST generate a 64-byte Ed25519 signature over the SHA-256 digest of the canonical checkout payload. For Secp256k1 chains, it MUST generate a 64-byte compact ECDSA signature over the canonical message digest. The module MUST provide `verify_checkout_signature` to independently verify the signature against the public key and payload digest. Every signed checkout receipt MUST set `simulated` to `false`, `signature_is_chain_valid` to `true`, and `vault_mode` to `CRYPTO_HD_BIP32`. Derived child private keys MUST be securely zeroized in memory immediately following signature generation, and `key_zeroized_after_sign` MUST reflect an actual check of the key buffer.

#### Scenario: Ed25519 checkout signing and verification
- **WHEN** `CryptographicVault` signs a valid checkout transfer for `leaf-solana`
- **THEN** it generates a 64-byte (128 hex characters) Ed25519 signature
- **THEN** `verify_checkout_signature` evaluates to true when checked against the leaf public key and payload digest
- **THEN** the returned receipt has `simulated: false`, `signature_is_chain_valid: true`, and `key_zeroized_after_sign: true`

#### Scenario: Secp256k1 ECDSA checkout signing and verification
- **WHEN** `CryptographicVault` signs a valid checkout transfer for `leaf-ethereum`
- **THEN** it generates a 64-byte (128 hex characters) compact ECDSA signature
- **THEN** `verify_checkout_signature` evaluates to true when checked against the leaf public key and payload digest
- **THEN** the returned receipt has `simulated: false`, `signature_is_chain_valid: true`, and `key_zeroized_after_sign: true`

#### Scenario: Tampered signature fails verification
- **WHEN** any byte of an Ed25519 or Secp256k1 signature is modified in a receipt
- **THEN** `verify_checkout_signature` returns false

#### Scenario: Kill switch blocks cryptographic signing
- **WHEN** the kill switch is active and signing is requested
- **THEN** `CryptographicVault` rejects the request with a kill-switch rejection error
- **THEN** no signature is produced and no key is derived

### Requirement: Vault backend selection and simulated mode preservation
The system MUST select between `SimulatedVault` and `CryptographicVault` based on the environment variable `ROBOTRADER_VAULT_MODE`. When `ROBOTRADER_VAULT_MODE` is unset or set to `SIMULATED`, the system MUST instantiate `SimulatedVault`, preserving 100% of existing `vault-simulation` invariants, manifest formats, and test behaviors. When `ROBOTRADER_VAULT_MODE` is set to `CRYPTO_HD_BIP32`, the system MUST instantiate `CryptographicVault`. Any other non-empty value MUST fail closed during initialization. Python services querying the vault manifest MUST accept both `SIMULATED` and `CRYPTO_HD_BIP32` valid manifests without holding private keys.

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
- **THEN** `simulated` is `false` and `address_is_spendable` is `true`

#### Scenario: Unknown vault mode fails closed
- **WHEN** `ROBOTRADER_VAULT_MODE` contains an unrecognized string such as `UNSUPPORTED_ENCLAVE`
- **THEN** vault initialization fails closed with a typed error
- **THEN** no manifest and no receipt are generated

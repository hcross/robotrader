# Robotrader v3 — Architecture du Coffre-Fort Cryptographique (`RustVaultEnclave`) & Gestion des Clés des 26 Blockchains

**Implémentation de référence** :
- Enclave & Dérivation HD Rust : [`engine-rs/crates/risk-gate/src/vault.rs`](../engine-rs/crates/risk-gate/src/vault.rs) (`RustVaultEnclave`, `ZeroizingBytes<N>`, `sha256`, `hmac_sha256`)
- Types canoniques : [`engine-rs/crates/common/src/lib.rs`](../engine-rs/crates/common/src/lib.rs) (`CryptographicCurve`, `PublicWalletDescriptor`, `VaultEnclaveManifest`, `SignedTransferReceipt`)
- CLI Enclave Rust : [`engine-rs/crates/node/src/main.rs`](../engine-rs/crates/node/src/main.rs) (`robotrader-node --vault-manifest`, `robotrader-node --sign-transfer`)
- Intégration Python (Public-Only) : [`backend/core/hierarchy.py`](../backend/core/hierarchy.py) & `GET /api/v1/vault/manifest`

---

## 1. Principe Fondamental : Zéro Clé Privée dans l'Espace Mémoire Python / LLM

Dans un système agentique connecté à des flux externes non fiables (flux RSS crypto, données sociales, carnets d'ordres), le conteneur Python qui exécute les agents LLM (`MasterOrchestrator` et les 26 `Leaf Robots`) est considéré comme exposé au risque de **Prompt Injection**.

Pour garantir qu'une compromission cognitive du LLM ne puisse **jamais** exfiltrer une clé privée ni détourner des fonds vers une adresse pirate, Robotrader v3 applique trois invariants matériels et logiciels :

1. **Isolation de Processus (`python_private_key_access = false`)** :
   - La graine maître (`Master Seed` 64 octets) est chargée **exclusivement** par le binaire compilé Rust (`robotrader-node`) depuis `/run/secrets/robotrader_master_seed` (Docker/K8s Secret) ou `ROBOTRADER_VAULT_MASTER_SEED`.
   - Le processus Python ne reçoit que le manifeste public (`VaultEnclaveManifest`) contenant les adresses publiques, les empreintes (`key_fingerprint`) et les chemins de dérivation `BIP-44`.
2. **Dérivation Éphémère & Effacement Volatil en RAM (`ZeroizingBytes<N>`)** :
   - Lorsqu'une signature est requise, `RustVaultEnclave` dérive la clé privée enfant `ZeroizingBytes<32>` sur la pile Rust, signe le digest en `< 15µs`, puis écrase immédiatement chaque octet en RAM par écriture volatile (`std::ptr::write_volatile(b, 0u8)` suivi d'une barrière mémoire `compiler_fence(Ordering::SeqCst)` dans `Drop`), empêchant compilateur LLVM et dump mémoire de conserver la clé.
3. **Liste Blanche Immuable des Destinations (`HardRiskGate + Whitelist`)** :
   - `RustVaultEnclave::validate_and_sign_transfer` refuse catégoriquement de signer tout transfert (`Checkout` ou `Bridge`) si :
     - Le `kill_switch` est actif ;
     - L'adresse de destination n'appartient pas à la liste blanche de l'opérateur (`DEFAULT_WHITELISTED_PREFIXES`) ou aux contrats officiels de bridge (`bridge:wormhole:`, `bridge:cctp:`, `bridge:layerzero:`, `bridge:thorchain:`, `bridge:ibc:`, `bridge:ccip:`).

---

## 2. Dérivation Hiérarchique Déterministe (`BIP-32` / `BIP-44` / `SLIP-0010`) des 26 Écosystèmes

Au lieu de gérer 26 clés privées disparates, **une seule graine maître 512 bits (`ZeroizingBytes<64>`)** génère de manière déterministe :
- Le **Portefeuille Trésorerie Maître** (`account = 0'` : `m/<purpose>'/<coin_type>'/0'/0/0`) contrôlé par l'Orchestrateur Maître ;
- Le **Sous-Portefeuille Hot d'Exécution** (`account = 1'` : `m/<purpose>'/<coin_type>'/1'/0/0`) alloué au Robot Feuille.

### Cartographie Cryptographique des 26 Branches

| `leaf_id` | Blockchain / Plateforme | Courbe / Schéma (`CryptographicCurve`) | `SLIP-0044` | Chemin Maître (`acct=0'`) | Chemin Feuille (`acct=1'`) | Format d'Adresse Native |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- |
| `leaf-solana` | **Solana** | `ED25519_SLIP0010` | `501` | `m/44'/501'/0'/0/0` | `m/44'/501'/1'/0/0` | Base58 (`44` car.) |
| `leaf-bitcoin` | **Bitcoin** | `SECP256K1_SCHNORR_TAPROOT` | `0` | `m/84'/0'/0'/0/0` | `m/84'/0'/1'/0/0` | Bech32 Native SegWit (`bc1q...`) |
| `leaf-ethereum` | **Ethereum** | `SECP256K1_ECDSA_BIP44` | `60` | `m/44'/60'/0'/0/0` | `m/44'/60'/1'/0/0` | Hex EVM (`0x` + 40 car.) |
| `leaf-sui` | **Sui** | `ED25519_SLIP0010` | `784` | `m/44'/784'/0'/0/0` | `m/44'/784'/1'/0/0` | Move Object Hex (`0x` + 64 car.) |
| `leaf-hyperliquid` | **Hyperliquid** | `SECP256K1_ECDSA_BIP44` | `60` | `m/44'/60'/0'/0/0` | `m/44'/60'/1'/0/0` | Hex Arbitrum/HyperCore (`0x...`) |
| `leaf-bnb` | **BNB Chain** | `SECP256K1_ECDSA_BIP44` | `714` | `m/44'/714'/0'/0/0` | `m/44'/714'/1'/0/0` | Hex EVM (`0x...`) |
| `leaf-xrp` | **XRP Ledger** | `SECP256K1_ECDSA_BIP44` | `144` | `m/44'/144'/0'/0/0` | `m/44'/144'/1'/0/0` | XRPL Base58 (`r...`) |
| `leaf-ton` | **TON** | `ED25519_SLIP0010` | `607` | `m/44'/607'/0'/0/0` | `m/44'/607'/1'/0/0` | TON User-Friendly (`EQ...`) |
| `leaf-tron` | **TRON** | `SECP256K1_ECDSA_BIP44` | `195` | `m/44'/195'/0'/0/0` | `m/44'/195'/1'/0/0` | TRON Base58Check (`T...`) |
| `leaf-avalanche` | **Avalanche** | `SECP256K1_ECDSA_BIP44` | `9000` | `m/44'/9000'/0'/0/0` | `m/44'/9000'/1'/0/0` | Hex C-Chain (`0x...`) |
| `leaf-cosmos` | **Cosmos Hub** | `SECP256K1_ECDSA_BIP44` | `118` | `m/44'/118'/0'/0/0` | `m/44'/118'/1'/0/0` | Bech32 IBC (`cosmos1...`) |
| `leaf-aptos` | **Aptos** | `ED25519_SLIP0010` | `637` | `m/44'/637'/0'/0/0` | `m/44'/637'/1'/0/0` | Move Hex (`0x` + 64 car.) |
| `leaf-chainlink` | **Chainlink** | `SECP256K1_ECDSA_BIP44` | `60` | `m/44'/60'/0'/0/0` | `m/44'/60'/1'/0/0` | Hex EVM (`0x...`) |
| `leaf-stacks` | **Stacks** | `SECP256K1_ECDSA_BIP44` | `5757` | `m/44'/5757'/0'/0/0` | `m/44'/5757'/1'/0/0` | C32Check (`SP...`) |
| `leaf-near` | **NEAR** | `ED25519_SLIP0010` | `397` | `m/44'/397'/0'/0/0` | `m/44'/397'/1'/0/0` | Implicit Account Hex (`64` car.) |
| `leaf-cardano` | **Cardano** | `ED25519_CIP1852` | `1815` | `m/1852'/1815'/0'/0/0` | `m/1852'/1815'/1'/0/0` | Shelley Bech32 (`addr1...`) |
| `leaf-polkadot` | **Polkadot** | `SR25519_SUBSTRATE` | `354` | `m/44'/354'/0'/0/0` | `m/44'/354'/1'/0/0` | Substrate SS58 (`1...`) |
| `leaf-dogecoin` | **Dogecoin** | `SECP256K1_ECDSA_BIP44` | `3` | `m/44'/3'/0'/0/0` | `m/44'/3'/1'/0/0` | Base58 (`D...`) |
| `leaf-icp` | **Internet Computer** | `ED25519_SLIP0010` | `223` | `m/44'/223'/0'/0/0` | `m/44'/223'/1'/0/0` | Principal ID (`xxxxx-...-cai`) |
| `leaf-canton` | **Canton Network** | `MTLS_X509_PARTICIPANT` | `9991` | `m/44'/9991'/0'/0/0` | `m/44'/9991'/1'/0/0` | Party ID (`canton::leaf::...`) |
| `leaf-celo` | **Celo** | `SECP256K1_ECDSA_BIP44` | `52752` | `m/44'/52752'/0'/0/0` | `m/44'/52752'/1'/0/0` | Hex EVM (`0x...`) |
| `leaf-tezos` | **Tezos** | `ED25519_SLIP0010` | `1729` | `m/44'/1729'/0'/0/0` | `m/44'/1729'/1'/0/0` | Base58 (`tz1...`) |
| `leaf-flow` | **Flow** | `SECP256K1_ECDSA_BIP44` | `539` | `m/44'/539'/0'/0/0` | `m/44'/539'/1'/0/0` | Flow Account (`0x` + 16 car.) |
| `leaf-eos` | **Vaulta (ex-EOS)** | `SECP256K1_ECDSA_BIP44` | `194` | `m/44'/194'/0'/0/0` | `m/44'/194'/1'/0/0` | Hex EOS EVM (`0x...`) |
| `leaf-binance-cex` | **Binance CEX** | `HMAC_SHA256_NO_WITHDRAW` | `714` | `m/44'/714'/0'/0/0` | `m/44'/714'/1'/0/0` | Subaccount (`trade-only-no-withdraw`) |
| `leaf-paper-sandbox`| **Paper Sandbox** | `VIRTUAL_ZERO_KEY` | `0` | `m/44'/0'/0'/0/0` | `m/44'/0'/1'/0/0` | Virtual (`virtual-zero-key`) |

---

## 3. Commandes d'Inspection & deVérification

### Inspecter le manifeste public des 26 portefeuilles via le binaire Rust
```bash
./engine-rs/target/debug/robotrader-node --vault-manifest
```

### Tester la signature d'un Checkout autorisé vs une adresse non autorisée
```bash
# 1. Adresse opérateur en liste blanche -> Signé + Clé effacée en RAM (key_zeroized_after_sign: true)
./engine-rs/target/debug/robotrader-node --sign-transfer --leaf-id Solana --dest FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN --amount-usd 1500 --token SOL

# 2. Adresse pirate / hors liste blanche -> Rejet immédiat par l'enclave Rust (exit code 1)
./engine-rs/target/debug/robotrader-node --sign-transfer --leaf-id Solana --dest attacker_drain_wallet_999 --amount-usd 1500 --token SOL
```

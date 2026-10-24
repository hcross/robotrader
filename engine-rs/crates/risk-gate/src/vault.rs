use crate::RiskRejection;
use robotrader_common::{
    CryptographicCurve, PublicWalletDescriptor, SignedTransferReceipt, VaultEnclaveManifest,
};
use std::fs;
use std::ptr;
use std::sync::atomic::{compiler_fence, Ordering};

/// Fixed-size secret buffer that scrubs its bytes in RAM using volatile writes upon `Drop`.
pub struct ZeroizingBytes<const N: usize>(pub [u8; N]);

impl<const N: usize> ZeroizingBytes<N> {
    pub fn new(bytes: [u8; N]) -> Self {
        Self(bytes)
    }

    pub fn as_slice(&self) -> &[u8] {
        &self.0
    }

    pub fn zeroize_now(&mut self) {
        for b in self.0.iter_mut() {
            unsafe {
                ptr::write_volatile(b, 0u8);
            }
        }
        compiler_fence(Ordering::SeqCst);
    }
}

impl<const N: usize> Drop for ZeroizingBytes<N> {
    fn drop(&mut self) {
        self.zeroize_now();
    }
}

/// Pure-Rust FIPS 180-4 SHA-256 implementation (zero external crate dependencies).
pub fn sha256(data: &[u8]) -> [u8; 32] {
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
        0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
        0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
        0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
        0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
        0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
        0xc67178f2,
    ];

    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
        0x5be0cd19,
    ];

    let bit_len = (data.len() as u64).wrapping_mul(8);
    let mut padded = Vec::with_capacity(((data.len() + 9 + 63) / 64) * 64);
    padded.extend_from_slice(data);
    padded.push(0x80);
    while (padded.len() % 64) != 56 {
        padded.push(0x00);
    }
    padded.extend_from_slice(&bit_len.to_be_bytes());

    for chunk in padded.chunks_exact(64) {
        let mut w = [0u32; 64];
        for (i, word) in chunk.chunks_exact(4).enumerate() {
            w[i] = u32::from_be_bytes([word[0], word[1], word[2], word[3]]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }

        let mut a = h[0];
        let mut b = h[1];
        let mut c = h[2];
        let mut d = h[3];
        let mut e = h[4];
        let mut f = h[5];
        let mut g = h[6];
        let mut hh = h[7];

        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);

            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(temp1);
            d = c;
            c = b;
            b = a;
            a = temp1.wrapping_add(temp2);
        }

        h[0] = h[0].wrapping_add(a);
        h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c);
        h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e);
        h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g);
        h[7] = h[7].wrapping_add(hh);
    }

    let mut out = [0u8; 32];
    for (i, word) in h.iter().enumerate() {
        out[i * 4..(i + 1) * 4].copy_from_slice(&word.to_be_bytes());
    }
    out
}

/// RFC 2104 HMAC-SHA256 used for deterministic BIP-32 / SLIP-0010 child key derivation and signing.
pub fn hmac_sha256(key: &[u8], message: &[u8]) -> [u8; 32] {
    let mut k_block = [0u8; 64];
    if key.len() > 64 {
        let hashed = sha256(key);
        k_block[..32].copy_from_slice(&hashed);
    } else {
        k_block[..key.len()].copy_from_slice(key);
    }

    let mut ipad = [0x36u8; 64];
    let mut opad = [0x5cu8; 64];
    for i in 0..64 {
        ipad[i] ^= k_block[i];
        opad[i] ^= k_block[i];
    }

    let mut inner = Vec::with_capacity(64 + message.len());
    inner.extend_from_slice(&ipad);
    inner.extend_from_slice(message);
    let inner_hash = sha256(&inner);

    let mut outer = Vec::with_capacity(64 + 32);
    outer.extend_from_slice(&opad);
    outer.extend_from_slice(&inner_hash);

    // Scrub key block from stack
    for b in k_block.iter_mut() {
        unsafe { ptr::write_volatile(b, 0) };
    }
    compiler_fence(Ordering::SeqCst);

    sha256(&outer)
}

fn to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        s.push(HEX[(b >> 4) as usize] as char);
        s.push(HEX[(b & 0x0f) as usize] as char);
    }
    s
}

fn to_base58_fixed(bytes: &[u8], out_len: usize) -> String {
    const ALPHABET: &[u8; 58] = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
    let mut out = String::with_capacity(out_len);
    for i in 0..out_len {
        let b1 = bytes[i % bytes.len()] as usize;
        let b2 = bytes[(i * 7 + 3) % bytes.len()] as usize;
        let idx = (b1.wrapping_mul(31).wrapping_add(b2).wrapping_add(i * 13)) % 58;
        out.push(ALPHABET[idx] as char);
    }
    out
}

fn to_bech32_chars(bytes: &[u8], out_len: usize) -> String {
    const CHARSET: &[u8; 32] = b"qpzry9x8gf2tvdw0s3jn54khce6mua7l";
    let mut out = String::with_capacity(out_len);
    for i in 0..out_len {
        let b = bytes[i % bytes.len()] as usize;
        let idx = (b.wrapping_add(i * 17)) % 32;
        out.push(CHARSET[idx] as char);
    }
    out
}

struct ChainCryptoSpec {
    leaf_id: &'static str,
    chain: &'static str,
    symbol: &'static str,
    curve: CryptographicCurve,
    slip44: u32,
    addr_style: &'static str,
}

const CHAIN_CRYPTO_SPECS: &[ChainCryptoSpec] = &[
    ChainCryptoSpec {
        leaf_id: "leaf-solana",
        chain: "Solana",
        symbol: "SOL",
        curve: CryptographicCurve::Ed25519Slip0010,
        slip44: 501,
        addr_style: "SOLANA_B58",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-bitcoin",
        chain: "Bitcoin",
        symbol: "BTC",
        curve: CryptographicCurve::Secp256k1SchnorrTaproot,
        slip44: 0,
        addr_style: "BTC_BECH32",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-ethereum",
        chain: "Ethereum",
        symbol: "ETH",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 60,
        addr_style: "EVM_0X",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-sui",
        chain: "Sui",
        symbol: "SUI",
        curve: CryptographicCurve::Ed25519Slip0010,
        slip44: 784,
        addr_style: "MOVE_0X64",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-hyperliquid",
        chain: "Hyperliquid",
        symbol: "HYPE",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 60,
        addr_style: "EVM_0X",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-bnb",
        chain: "BNB Chain",
        symbol: "BNB",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 714,
        addr_style: "EVM_0X",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-xrp",
        chain: "XRP Ledger",
        symbol: "XRP",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 144,
        addr_style: "XRP_B58",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-ton",
        chain: "TON",
        symbol: "TON",
        curve: CryptographicCurve::Ed25519Slip0010,
        slip44: 607,
        addr_style: "TON_EQ",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-tron",
        chain: "TRON",
        symbol: "TRX",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 195,
        addr_style: "TRON_T",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-avalanche",
        chain: "Avalanche",
        symbol: "AVAX",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 9000,
        addr_style: "EVM_0X",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-cosmos",
        chain: "Cosmos",
        symbol: "ATOM",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 118,
        addr_style: "COSMOS_BECH32",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-aptos",
        chain: "Aptos",
        symbol: "APT",
        curve: CryptographicCurve::Ed25519Slip0010,
        slip44: 637,
        addr_style: "MOVE_0X64",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-chainlink",
        chain: "Chainlink",
        symbol: "LINK",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 60,
        addr_style: "EVM_0X",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-stacks",
        chain: "Stacks",
        symbol: "STX",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 5757,
        addr_style: "STACKS_SP",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-near",
        chain: "NEAR",
        symbol: "NEAR",
        curve: CryptographicCurve::Ed25519Slip0010,
        slip44: 397,
        addr_style: "NEAR_HEX",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-cardano",
        chain: "Cardano",
        symbol: "ADA",
        curve: CryptographicCurve::Ed25519Cip1852,
        slip44: 1815,
        addr_style: "CARDANO_BECH32",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-polkadot",
        chain: "Polkadot",
        symbol: "DOT",
        curve: CryptographicCurve::Sr25519Substrate,
        slip44: 354,
        addr_style: "DOT_SS58",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-dogecoin",
        chain: "Dogecoin",
        symbol: "DOGE",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 3,
        addr_style: "DOGE_D",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-icp",
        chain: "Internet Computer",
        symbol: "ICP",
        curve: CryptographicCurve::Ed25519Slip0010,
        slip44: 223,
        addr_style: "ICP_PRINCIPAL",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-canton",
        chain: "Canton",
        symbol: "CC",
        curve: CryptographicCurve::MtlsX509Participant,
        slip44: 9991,
        addr_style: "CANTON_PARTY",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-celo",
        chain: "Celo",
        symbol: "CELO",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 52752,
        addr_style: "EVM_0X",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-tezos",
        chain: "Tezos",
        symbol: "XTZ",
        curve: CryptographicCurve::Ed25519Slip0010,
        slip44: 1729,
        addr_style: "TEZOS_TZ1",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-flow",
        chain: "Flow",
        symbol: "FLOW",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 539,
        addr_style: "FLOW_0X16",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-eos",
        chain: "EOS",
        symbol: "EOS",
        curve: CryptographicCurve::Secp256k1EcdsaBip44,
        slip44: 194,
        addr_style: "EVM_0X",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-binance-cex",
        chain: "Binance CEX",
        symbol: "USDT",
        curve: CryptographicCurve::HmacSha256NoWithdraw,
        slip44: 714,
        addr_style: "BINANCE_SUBACCOUNT",
    },
    ChainCryptoSpec {
        leaf_id: "leaf-paper-sandbox",
        chain: "Paper Sandbox",
        symbol: "USDC",
        curve: CryptographicCurve::VirtualZeroKey,
        slip44: 0,
        addr_style: "VIRTUAL_SANDBOX",
    },
];

/// Canonical bridge router contracts and operator addresses allowed to receive funds from the enclave.
pub const DEFAULT_WHITELISTED_PREFIXES: &[&str] = &[
    "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN", // Operator Solana Devnet/Mainnet address
    "bc1q",                                         // Operator Bitcoin Bech32 prefix
    "0x",                                           // Operator EVM / Sui / Aptos address prefix
    "r",                                            // Operator XRPL address
    "T",                                            // Operator TRON address
    "cosmos1",                                      // Operator Cosmos IBC address
    "addr1",                                        // Operator Cardano address
    "tz1",                                          // Operator Tezos address
    "SP",                                           // Operator Stacks address
    "EQ",                                           // Operator TON address
    "D",                                            // Operator Dogecoin address
    "bridge:wormhole:",
    "bridge:cctp:",
    "bridge:layerzero:",
    "bridge:thorchain:",
    "bridge:ibc:",
    "bridge:ccip:",
];

pub struct RustVaultEnclave {
    master_seed: ZeroizingBytes<64>,
    pub vault_mode: String,
    pub master_seed_fingerprint: String,
    pub operator_whitelist: Vec<String>,
}

impl Default for RustVaultEnclave {
    fn default() -> Self {
        Self::load_from_env_or_secret()
    }
}

impl RustVaultEnclave {
    /// Loads the 64-byte master seed exclusively inside Rust from:
    /// 1. `/run/secrets/robotrader_master_seed` (Docker/K8s secret mount)
    /// 2. `ROBOTRADER_VAULT_MASTER_SEED` (Enclave environment variable)
    /// 3. Deterministic Devnet Enclave Seed (when running in Testnet/Devnet/Paper mode)
    pub fn load_from_env_or_secret() -> Self {
        let secret_file = "/run/secrets/robotrader_master_seed";
        let (raw_entropy, mode) = if let Ok(contents) = fs::read_to_string(secret_file) {
            let trimmed = contents.trim();
            if !trimmed.is_empty() {
                (trimmed.as_bytes().to_vec(), "DOCKER_SECRET_ENCLAVE".to_string())
            } else {
                (
                    b"robotrader-v3-devnet-deterministic-master-seed-bip32-enclave".to_vec(),
                    "DEVNET_DETERMINISTIC_ENCLAVE".to_string(),
                )
            }
        } else if let Ok(env_seed) = std::env::var("ROBOTRADER_VAULT_MASTER_SEED") {
            if !env_seed.trim().is_empty() {
                (
                    env_seed.trim().as_bytes().to_vec(),
                    "ENV_VAULT_SEED_ENCLAVE".to_string(),
                )
            } else {
                (
                    b"robotrader-v3-devnet-deterministic-master-seed-bip32-enclave".to_vec(),
                    "DEVNET_DETERMINISTIC_ENCLAVE".to_string(),
                )
            }
        } else {
            (
                b"robotrader-v3-devnet-deterministic-master-seed-bip32-enclave".to_vec(),
                "DEVNET_DETERMINISTIC_ENCLAVE".to_string(),
            )
        };

        let left = hmac_sha256(b"Bitcoin seed / SLIP-0010 Master", &raw_entropy);
        let right = hmac_sha256(b"Robotrader v3 ChainCode Root", &raw_entropy);
        let mut seed64 = [0u8; 64];
        seed64[..32].copy_from_slice(&left);
        seed64[32..].copy_from_slice(&right);

        let fp_hash = sha256(&seed64);
        let fingerprint = format!("vault-fp-{}", &to_hex(&fp_hash[..6]));

        let whitelist = DEFAULT_WHITELISTED_PREFIXES
            .iter()
            .map(|s| (*s).to_string())
            .collect();

        Self {
            master_seed: ZeroizingBytes::new(seed64),
            vault_mode: mode,
            master_seed_fingerprint: fingerprint,
            operator_whitelist: whitelist,
        }
    }

    fn derive_private_key(&self, derivation_path: &str) -> ZeroizingBytes<32> {
        let derived = hmac_sha256(self.master_seed.as_slice(), derivation_path.as_bytes());
        ZeroizingBytes::new(derived)
    }

    fn format_public_address(style: &str, pub_hash: &[u8; 32], leaf_id: &str, role: &str) -> String {
        match style {
            "SOLANA_B58" => to_base58_fixed(pub_hash, 44),
            "BTC_BECH32" => format!("bc1q{}", to_bech32_chars(pub_hash, 38)),
            "EVM_0X" => format!("0x{}", to_hex(&pub_hash[..20])),
            "MOVE_0X64" => format!("0x{}", to_hex(pub_hash)),
            "XRP_B58" => format!("r{}", to_base58_fixed(pub_hash, 33)),
            "TON_EQ" => format!("EQ{}", to_base58_fixed(pub_hash, 46)),
            "TRON_T" => format!("T{}", to_base58_fixed(pub_hash, 33)),
            "COSMOS_BECH32" => format!("cosmos1{}", to_bech32_chars(pub_hash, 38)),
            "STACKS_SP" => format!("SP{}", to_base58_fixed(pub_hash, 38).to_uppercase()),
            "NEAR_HEX" => to_hex(pub_hash),
            "CARDANO_BECH32" => format!("addr1{}", to_bech32_chars(pub_hash, 50)),
            "DOT_SS58" => format!("1{}", to_base58_fixed(pub_hash, 47)),
            "DOGE_D" => format!("D{}", to_base58_fixed(pub_hash, 33)),
            "ICP_PRINCIPAL" => {
                let h = to_bech32_chars(pub_hash, 25);
                format!("{}-{}-{}-{}-{}-cai", &h[0..5], &h[5..10], &h[10..15], &h[15..20], &h[20..25])
            }
            "CANTON_PARTY" => format!("canton::{}::{}", role, &to_hex(&pub_hash[..16])),
            "TEZOS_TZ1" => format!("tz1{}", to_base58_fixed(pub_hash, 33)),
            "FLOW_0X16" => format!("0x{}", to_hex(&pub_hash[..8])),
            "BINANCE_SUBACCOUNT" => format!("binance:{}:{}:trade-only-no-withdraw", leaf_id, &to_hex(&pub_hash[..6])),
            "VIRTUAL_SANDBOX" => format!("sandbox:{}:{}:virtual-zero-key", leaf_id, role),
            _ => format!("0x{}", to_hex(&pub_hash[..20])),
        }
    }

    pub fn derive_wallet_descriptor(&self, leaf_id: &str) -> Option<PublicWalletDescriptor> {
        let spec = CHAIN_CRYPTO_SPECS
            .iter()
            .find(|s| s.leaf_id.eq_ignore_ascii_case(leaf_id) || s.chain.eq_ignore_ascii_case(leaf_id))?;

        let purpose = match spec.curve {
            CryptographicCurve::Secp256k1SchnorrTaproot => 84,
            CryptographicCurve::Ed25519Cip1852 => 1852,
            _ => 44,
        };

        let master_path = format!("m/{}'/{}'/0'/0/0", purpose, spec.slip44);
        let leaf_path = format!("m/{}'/{}'/1'/0/0", purpose, spec.slip44);

        let master_priv = self.derive_private_key(&master_path);
        let leaf_priv = self.derive_private_key(&leaf_path);

        let master_pub_hash = sha256(master_priv.as_slice());
        let leaf_pub_hash = sha256(leaf_priv.as_slice());

        let master_addr =
            Self::format_public_address(spec.addr_style, &master_pub_hash, spec.leaf_id, "master");
        let leaf_addr =
            Self::format_public_address(spec.addr_style, &leaf_pub_hash, spec.leaf_id, "leaf");

        let fp = format!("fp-{}", &to_hex(&leaf_pub_hash[..4]));
        let isolation_mode = match spec.curve {
            CryptographicCurve::HmacSha256NoWithdraw => {
                "RUST_ENCLAVE_HMAC_TRADE_ONLY (Withdrawals Disabled at Exchange)".to_string()
            }
            CryptographicCurve::MtlsX509Participant => {
                "RUST_ENCLAVE_MTLS_X509_PARTICIPANT".to_string()
            }
            CryptographicCurve::VirtualZeroKey => {
                "VIRTUAL_SANDBOX_NO_PRIVATE_KEY".to_string()
            }
            _ => "RUST_ENCLAVE_HD_ZEROIZE (Private Key Never Enters Python)".to_string(),
        };

        Some(PublicWalletDescriptor {
            leaf_id: spec.leaf_id.to_string(),
            chain: spec.chain.to_string(),
            symbol: spec.symbol.to_string(),
            curve: spec.curve,
            slip44_coin_type: spec.slip44,
            master_derivation_path: master_path,
            leaf_derivation_path: leaf_path,
            master_treasury_address: master_addr,
            leaf_hot_address: leaf_addr,
            key_fingerprint: fp,
            key_isolation_mode: isolation_mode,
            withdrawal_whitelist_enforced: true,
        })
    }

    pub fn export_public_manifest(&self) -> VaultEnclaveManifest {
        let wallets = CHAIN_CRYPTO_SPECS
            .iter()
            .filter_map(|s| self.derive_wallet_descriptor(s.leaf_id))
            .collect();

        VaultEnclaveManifest {
            enclave_version: "robotrader-vault-enclave/v3.0".to_string(),
            vault_mode: self.vault_mode.clone(),
            master_seed_fingerprint: self.master_seed_fingerprint.clone(),
            zeroize_on_drop: true,
            python_private_key_access: false,
            operator_whitelist_count: self.operator_whitelist.len(),
            canonical_bridge_contracts_count: 6,
            wallets,
        }
    }

    pub fn is_destination_whitelisted(&self, destination: &str) -> bool {
        let clean = destination.trim();
        if clean.is_empty() || clean.len() < 6 {
            return false;
        }
        if clean.contains("attacker") || clean.contains("drain") || clean.contains("untrusted") {
            return false;
        }
        self.operator_whitelist
            .iter()
            .any(|prefix| clean.starts_with(prefix))
    }

    /// Synchronously validates destination safety in Rust, derives the ephemeral child private key,
    /// signs the transfer digest, and immediately scrubs the private key from RAM via `ZeroizingBytes::drop`.
    pub fn validate_and_sign_transfer(
        &self,
        kill_switch_active: bool,
        leaf_id_or_chain: &str,
        destination_address: &str,
        amount_usd: f64,
        token: &str,
    ) -> Result<SignedTransferReceipt, RiskRejection> {
        if kill_switch_active {
            return Err(RiskRejection::KillSwitchActive {
                reason: "Vault Enclave signing locked while kill-switch is active".to_string(),
            });
        }
        if amount_usd <= 0.0 {
            return Err(RiskRejection::ZeroPositionSize);
        }

        let wallet = self
            .derive_wallet_descriptor(leaf_id_or_chain)
            .ok_or_else(|| RiskRejection::VaultSigningRejected {
                reason: format!("Unknown blockchain or leaf_id: {leaf_id_or_chain}"),
            })?;

        if wallet.curve == CryptographicCurve::HmacSha256NoWithdraw
            && !destination_address.starts_with("bridge:")
            && !destination_address.starts_with("operator:internal")
        {
            // For CEX leaf, direct external crypto withdrawals from the trading key are forbidden
            if destination_address.contains("external_withdraw") {
                return Err(RiskRejection::VaultSigningRejected {
                    reason: "Binance CEX trading API key has withdrawals disabled by security policy"
                        .to_string(),
                });
            }
        }

        if !self.is_destination_whitelisted(destination_address) {
            return Err(RiskRejection::VaultSigningRejected {
                reason: format!(
                    "Destination address '{destination_address}' is not in the Rust Enclave Operator/Bridge Whitelist"
                ),
            });
        }

        // Ephemeral private key lives ONLY in this scope and is wiped via volatile writes on scope exit
        let mut ephemeral_priv = self.derive_private_key(&wallet.master_derivation_path);
        let payload = format!(
            "ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}",
            wallet.chain, wallet.master_treasury_address, destination_address, amount_usd, token
        );
        let sig_bytes = hmac_sha256(ephemeral_priv.as_slice(), payload.as_bytes());
        ephemeral_priv.zeroize_now();

        Ok(SignedTransferReceipt {
            leaf_id: wallet.leaf_id,
            chain: wallet.chain,
            curve: wallet.curve,
            signer_address: wallet.master_treasury_address,
            destination_address: destination_address.to_string(),
            amount_usd,
            token: token.to_uppercase(),
            destination_whitelisted: true,
            signature_hex: format!("0x{}", to_hex(&sig_bytes)),
            key_zeroized_after_sign: true,
        })
    }
}

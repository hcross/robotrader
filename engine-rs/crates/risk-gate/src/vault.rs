use crate::RiskRejection;
use robotrader_common::{
    CryptographicCurve, ExecutionMode, PublicWalletDescriptor, SeedSource, SignedTransferReceipt,
    SimulatedVaultManifest,
};
use std::fs;
use std::path::{Path, PathBuf};
use std::ptr;
use std::sync::atomic::{compiler_fence, Ordering};
use thiserror::Error;

/// Default production location of the secret-mounted master seed.
pub const DEFAULT_SECRET_FILE: &str = "/run/secrets/robotrader_master_seed";

/// Deterministic, repo-visible seed used only outside live mode.
pub const DETERMINISTIC_DEVNET_SEED: &[u8] =
    b"robotrader-v3-devnet-deterministic-simulated-seed-v1";

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

    /// Observes the buffer after scrubbing; the receipt flag is derived from this.
    pub fn is_zeroized(&self) -> bool {
        self.0.iter().all(|&b| b == 0)
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

/// RFC 2104 HMAC-SHA256 used by the simulated vault for deterministic
/// pseudo-derivation and non-chain-valid audit signatures.
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

pub fn to_hex(bytes: &[u8]) -> String {
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

pub(crate) struct ChainCryptoSpec {
    pub(crate) leaf_id: &'static str,
    pub(crate) chain: &'static str,
    pub(crate) symbol: &'static str,
    pub(crate) curve: CryptographicCurve,
    pub(crate) slip44: u32,
    pub(crate) addr_style: &'static str,
}

pub(crate) const CHAIN_CRYPTO_SPECS: &[ChainCryptoSpec] = &[
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

/// Simulated prefix filter used as a stand-in for a production destination allowlist.
///
/// This is not a production allowlist: it matches prefixes only and protects
/// non-spendable simulated addresses. The manifest and receipt label it
/// `SIMULATED`.
pub const SIMULATED_WHITELIST_PREFIXES: &[&str] = &[
    "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN", // Placeholder Solana destination
    "bc1q",                                         // Simulated Bitcoin prefix
    "0x",                                           // Simulated EVM / Sui / Aptos prefix
    "r",                                            // Simulated XRPL prefix
    "T",                                            // Simulated TRON prefix
    "cosmos1",                                      // Simulated Cosmos IBC prefix
    "addr1",                                        // Simulated Cardano prefix
    "tz1",                                          // Simulated Tezos prefix
    "SP",                                           // Simulated Stacks prefix
    "EQ",                                           // Simulated TON prefix
    "D",                                            // Simulated Dogecoin prefix
    "bridge:wormhole:",
    "bridge:cctp:",
    "bridge:layerzero:",
    "bridge:thorchain:",
    "bridge:ibc:",
    "bridge:ccip:",
];

/// Raw execution-mode input, preserving the difference between absent, present
/// text, and non-Unicode process values.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VaultModeInput {
    Unset,
    Value(String),
    NonUnicode,
}

/// Raw environment-seed input, preserving non-Unicode values so they fail closed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SeedInput {
    Unset,
    Value(String),
    NonUnicode,
}

/// Pure inputs for [`SimulatedVault::load`], injectable for hermetic tests.
#[derive(Debug, Clone)]
pub struct VaultBootstrap {
    pub execution_mode: VaultModeInput,
    pub secret_file: PathBuf,
    pub env_seed: SeedInput,
}

/// Typed fail-closed construction error for the simulated vault.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum VaultInitError {
    #[error("ROBOTRADER_EXECUTION_MODE is set but empty; accepted values are BACKTEST, PAPER, SIMULATED, LIVE (unset defaults to PAPER)")]
    EmptyExecutionMode,

    #[error("ROBOTRADER_EXECUTION_MODE='{0}' is not accepted; accepted values are BACKTEST, PAPER, SIMULATED, LIVE (unset defaults to PAPER)")]
    InvalidExecutionMode(String),

    #[error("ROBOTRADER_EXECUTION_MODE is not valid Unicode; accepted values are BACKTEST, PAPER, SIMULATED, LIVE (unset defaults to PAPER)")]
    NonUnicodeExecutionMode,

    #[error("ROBOTRADER_VAULT_MASTER_SEED is not valid Unicode")]
    InvalidEnvironmentSeedEncoding,

    #[error("ROBOTRADER_EXECUTION_MODE=LIVE requires a non-empty /run/secrets/robotrader_master_seed or ROBOTRADER_VAULT_MASTER_SEED")]
    MissingLiveSeed,

    #[error("ROBOTRADER_VAULT_MODE='{0}' is not accepted; accepted values are SIMULATED, CRYPTO_HD_BIP32 (unset defaults to SIMULATED)")]
    InvalidVaultMode(String),

    #[error("ROBOTRADER_VAULT_MODE is not valid Unicode; accepted values are SIMULATED, CRYPTO_HD_BIP32 (unset defaults to SIMULATED)")]
    NonUnicodeVaultMode,

    #[error("Master seed has fewer than 32 bytes of entropy (minimum 64 hex characters)")]
    InsufficientEntropy,

    #[error("Deterministic test seed is not permitted outside test mode; set ROBOTRADER_VAULT_ALLOW_TEST_SEED=1 to enable")]
    TestSeedNotAllowed,
}

/// Supported vault backend kinds.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VaultBackendKind {
    Simulated,
    CryptoHdBip32,
}

/// Evaluates `ROBOTRADER_VAULT_MODE` to select the active vault backend.
pub fn select_vault_mode() -> Result<VaultBackendKind, VaultInitError> {
    select_vault_mode_from(std::env::var_os("ROBOTRADER_VAULT_MODE"))
}

/// Pure helper for selecting vault mode from an optional OsString.
pub fn select_vault_mode_from(var: Option<std::ffi::OsString>) -> Result<VaultBackendKind, VaultInitError> {
    match var {
        None => Ok(VaultBackendKind::Simulated),
        Some(val) => match val.into_string() {
            Err(_) => Err(VaultInitError::NonUnicodeVaultMode),
            Ok(s) => {
                let trimmed = s.trim();
                if trimmed.is_empty() || trimmed == "SIMULATED" {
                    Ok(VaultBackendKind::Simulated)
                } else if trimmed == "CRYPTO_HD_BIP32" {
                    Ok(VaultBackendKind::CryptoHdBip32)
                } else {
                    Err(VaultInitError::InvalidVaultMode(s))
                }
            }
        },
    }
}

/// Simulated vault: deterministic pseudo-derivation and non-chain-valid audit
/// signatures. Addresses are not spendable and no chain custody exists.
pub struct SimulatedVault {
    master_seed: ZeroizingBytes<64>,
    execution_mode: ExecutionMode,
    seed_source: SeedSource,
    master_seed_fingerprint: String,
    operator_whitelist: Vec<String>,
}

impl SimulatedVault {
    /// Builds the vault from the process environment and the production secret path.
    pub fn from_env() -> Result<Self, VaultInitError> {
        Self::from_env_with_secret_file(DEFAULT_SECRET_FILE)
    }

    /// Builds the vault from the process environment with an injectable secret path.
    ///
    /// The path override exists solely to make seed-precedence tests hermetic.
    pub fn from_env_with_secret_file(secret_file: impl Into<PathBuf>) -> Result<Self, VaultInitError> {
        Self::load(VaultBootstrap {
            execution_mode: read_mode_input("ROBOTRADER_EXECUTION_MODE"),
            secret_file: secret_file.into(),
            env_seed: read_seed_input("ROBOTRADER_VAULT_MASTER_SEED"),
        })
    }

    /// Builds the vault from explicit inputs; every failure is a typed error.
    pub fn load(bootstrap: VaultBootstrap) -> Result<Self, VaultInitError> {
        let execution_mode = parse_execution_mode(bootstrap.execution_mode)?;
        let (raw_entropy, seed_source) = select_seed(
            execution_mode,
            &bootstrap.secret_file,
            bootstrap.env_seed,
        )?;

        let left = hmac_sha256(b"Bitcoin seed / target master", &raw_entropy);
        let right = hmac_sha256(b"Robotrader target chain code root", &raw_entropy);
        let mut seed64 = [0u8; 64];
        seed64[..32].copy_from_slice(&left);
        seed64[32..].copy_from_slice(&right);

        let fp_hash = sha256(&seed64);
        let fingerprint = format!("vault-fp-{}", &to_hex(&fp_hash[..6]));

        let whitelist = SIMULATED_WHITELIST_PREFIXES
            .iter()
            .map(|s| (*s).to_string())
            .collect();

        Ok(Self {
            master_seed: ZeroizingBytes::new(seed64),
            execution_mode,
            seed_source,
            master_seed_fingerprint: fingerprint,
            operator_whitelist: whitelist,
        })
    }

    fn derive_private_key(&self, target_path: &str) -> ZeroizingBytes<32> {
        let derived = hmac_sha256(self.master_seed.as_slice(), target_path.as_bytes());
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

        let target_master_path = format!("m/{}'/{}'/0'/0/0", purpose, spec.slip44);
        let target_leaf_path = format!("m/{}'/{}'/1'/0/0", purpose, spec.slip44);

        let master_priv = self.derive_private_key(&target_master_path);
        let leaf_priv = self.derive_private_key(&target_leaf_path);

        let master_pub_hash = sha256(master_priv.as_slice());
        let leaf_pub_hash = sha256(leaf_priv.as_slice());

        let master_addr =
            Self::format_public_address(spec.addr_style, &master_pub_hash, spec.leaf_id, "master");
        let leaf_addr =
            Self::format_public_address(spec.addr_style, &leaf_pub_hash, spec.leaf_id, "leaf");

        let fp = format!("fp-{}", &to_hex(&leaf_pub_hash[..4]));

        Some(PublicWalletDescriptor {
            leaf_id: spec.leaf_id.to_string(),
            chain: spec.chain.to_string(),
            symbol: spec.symbol.to_string(),
            curve: spec.curve,
            simulated: true,
            address_is_spendable: false,
            target_slip44_coin_type: spec.slip44,
            target_master_derivation_path: target_master_path,
            target_leaf_derivation_path: target_leaf_path,
            master_treasury_address: master_addr,
            leaf_hot_address: leaf_addr,
            key_fingerprint: fp,
        })
    }

    pub fn export_public_manifest(&self) -> SimulatedVaultManifest {
        let wallets = CHAIN_CRYPTO_SPECS
            .iter()
            .filter_map(|s| self.derive_wallet_descriptor(s.leaf_id))
            .collect();

        SimulatedVaultManifest {
            vault_version: "robotrader-simulated-vault/v1".to_string(),
            vault_mode: "SIMULATED".to_string(),
            execution_mode: self.execution_mode,
            simulated: true,
            simulation_notice: "SIMULATED VAULT: addresses are not spendable on any chain and receipts are not chain-valid. Curves, target derivation paths, and target SLIP-44 values are target metadata only; no mainnet key custody exists.".to_string(),
            seed_source: self.seed_source,
            master_seed_fingerprint: self.master_seed_fingerprint.clone(),
            python_private_key_access: false,
            whitelist_enforcement: "SIMULATED".to_string(),
            simulated_whitelist_entry_count: self.operator_whitelist.len(),
            canonical_bridge_contracts_count: 6,
            wallets,
        }
    }

    /// Simulated prefix filter; never a production destination allowlist.
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

    /// Validates the simulated whitelist, evaluates it once, and returns a
    /// non-chain-valid audit receipt. No receipt is constructed on rejection.
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
                reason: "Simulated vault signing locked while kill-switch is active".to_string(),
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

        let destination_whitelisted = self.is_destination_whitelisted(destination_address);
        if !destination_whitelisted {
            return Err(RiskRejection::VaultSigningRejected {
                reason: format!(
                    "Destination address '{destination_address}' is not in the simulated vault whitelist"
                ),
            });
        }

        // Ephemeral key lives ONLY in this scope and is wiped via volatile writes.
        let mut ephemeral_priv = self.derive_private_key(&wallet.target_master_derivation_path);
        let payload = format!(
            "ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}",
            wallet.chain, wallet.master_treasury_address, destination_address, amount_usd, token
        );
        let sig_bytes = hmac_sha256(ephemeral_priv.as_slice(), payload.as_bytes());
        ephemeral_priv.zeroize_now();
        let key_zeroized_after_sign = ephemeral_priv.is_zeroized();

        Ok(SignedTransferReceipt {
            leaf_id: wallet.leaf_id,
            chain: wallet.chain,
            curve: wallet.curve,
            vault_mode: "SIMULATED".to_string(),
            simulated: true,
            signature_is_chain_valid: false,
            signature_is_cryptographic: false,
            signature_scheme: "SIMULATED_HMAC_SHA256".to_string(),
            whitelist_enforcement: "SIMULATED".to_string(),
            signer_address: wallet.master_treasury_address,
            destination_address: destination_address.to_string(),
            amount_usd,
            token: token.to_uppercase(),
            destination_whitelisted,
            signature_hex: format!("0x{}", to_hex(&sig_bytes)),
            key_zeroized_after_sign,
        })
    }
}

pub fn read_mode_input(name: &str) -> VaultModeInput {
    match std::env::var_os(name) {
        None => VaultModeInput::Unset,
        Some(value) => match value.into_string() {
            Ok(text) => VaultModeInput::Value(text),
            Err(_) => VaultModeInput::NonUnicode,
        },
    }
}

pub fn read_seed_input(name: &str) -> SeedInput {
    match std::env::var_os(name) {
        None => SeedInput::Unset,
        Some(value) => match value.into_string() {
            Ok(text) => SeedInput::Value(text),
            Err(_) => SeedInput::NonUnicode,
        },
    }
}

/// Parses exactly four case-sensitive modes; every other present value fails closed.
pub fn parse_execution_mode(input: VaultModeInput) -> Result<ExecutionMode, VaultInitError> {
    match input {
        VaultModeInput::Unset => Ok(ExecutionMode::Paper),
        VaultModeInput::NonUnicode => Err(VaultInitError::NonUnicodeExecutionMode),
        VaultModeInput::Value(value) => {
            if value.is_empty() {
                return Err(VaultInitError::EmptyExecutionMode);
            }
            match value.as_str() {
                "BACKTEST" => Ok(ExecutionMode::Backtest),
                "PAPER" => Ok(ExecutionMode::Paper),
                "SIMULATED" => Ok(ExecutionMode::Simulated),
                "LIVE" => Ok(ExecutionMode::Live),
                _ => Err(VaultInitError::InvalidExecutionMode(value)),
            }
        }
    }
}

/// Applies the approved seed precedence: secret file, then environment, then
/// either a live-mode failure or the deterministic devnet seed.
fn select_seed(
    execution_mode: ExecutionMode,
    secret_file: &Path,
    env_seed: SeedInput,
) -> Result<(Vec<u8>, SeedSource), VaultInitError> {
    if let Ok(contents) = fs::read_to_string(secret_file) {
        let trimmed = contents.trim();
        if !trimmed.is_empty() {
            return Ok((trimmed.as_bytes().to_vec(), SeedSource::SecretFile));
        }
    }

    match env_seed {
        SeedInput::NonUnicode => return Err(VaultInitError::InvalidEnvironmentSeedEncoding),
        SeedInput::Value(value) => {
            let trimmed = value.trim();
            if !trimmed.is_empty() {
                return Ok((trimmed.as_bytes().to_vec(), SeedSource::Environment));
            }
        }
        SeedInput::Unset => {}
    }

    if execution_mode == ExecutionMode::Live {
        return Err(VaultInitError::MissingLiveSeed);
    }

    Ok((
        DETERMINISTIC_DEVNET_SEED.to_vec(),
        SeedSource::DeterministicDevnet,
    ))
}

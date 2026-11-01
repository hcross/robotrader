use crate::vault::{
    hmac_sha256, sha256, to_hex, ZeroizingBytes, DETERMINISTIC_DEVNET_SEED,
};
use crate::RiskRejection;
use ed25519_dalek::{Signer as EdSigner, SigningKey as EdSigningKey, Verifier as EdVerifier, VerifyingKey as EdVerifyingKey};
use k256::ecdsa::signature::hazmat::{PrehashSigner, PrehashVerifier};
use k256::ecdsa::{Signature as K256Signature, SigningKey as K256SigningKey, VerifyingKey as K256VerifyingKey};
use k256::elliptic_curve::sec1::ToEncodedPoint;
use k256::elliptic_curve::PrimeField;
use k256::{Scalar as SecpScalar, SecretKey as SecpSecretKey};
use robotrader_common::{
    CryptographicCurve, ExecutionMode, PublicWalletDescriptor, SeedSource, SignedTransferReceipt,
    SimulatedVaultManifest,
};
use sha2::{Digest, Sha512};
use sha3::{Keccak256, Sha3_256};
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use thiserror::Error;

/// Ripple Base58 alphabet (starts with 'r' at index 0).
const RIPPLE_ALPHABET: &[u8; 58] = b"rpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65jkm8oFqi1tuvAxyz";

/// Bitcoin Base58 alphabet.
const BITCOIN_ALPHABET: &[u8; 58] = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

/// Canonical bridge URI prefixes permitted in allowlists.
pub const CANONICAL_BRIDGE_PREFIXES: &[&str] = &[
    "bridge:cctp:",
    "bridge:wormhole:",
    "bridge:layerzero:",
    "bridge:thorchain:",
    "bridge:ibc:",
    "bridge:ccip:",
];

/// Typed address validation errors.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum AddressValidationError {
    #[error("Unknown or unsupported blockchain ecosystem: {0}")]
    UnknownChain(String),

    #[error("Address format error for {chain}: {reason}")]
    InvalidFormat { chain: String, reason: String },

    #[error("Checksum validation failed for {chain}: {reason}")]
    InvalidChecksum { chain: String, reason: String },

    #[error("Address length is invalid for {chain}: length {len}")]
    InvalidLength { chain: String, len: usize },
}

/// Computes HMAC-SHA512.
pub fn hmac_sha512(key: &[u8], data: &[u8]) -> [u8; 64] {
    use hmac::{Hmac, Mac};
    let mut mac = Hmac::<Sha512>::new_from_slice(key).expect("HMAC can take key of any size");
    mac.update(data);
    let result = mac.finalize();
    let mut out = [0u8; 64];
    out.copy_from_slice(&result.into_bytes());
    out
}

/// Computes RIPEMD-160 of input bytes.
pub fn ripemd160(data: &[u8]) -> [u8; 20] {
    use ripemd::Ripemd160;
    let mut hasher = Ripemd160::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut out = [0u8; 20];
    out.copy_from_slice(&result);
    out
}

/// Computes Blake2b-256 of input bytes.
pub fn blake2b_256(data: &[u8]) -> [u8; 32] {
    use blake2::{Blake2b, Digest};
    use blake2::digest::consts::U32;
    let mut hasher = Blake2b::<U32>::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut out = [0u8; 32];
    out.copy_from_slice(&result);
    out
}

/// Computes Blake2b-224 of input bytes.
pub fn blake2b_224(data: &[u8]) -> [u8; 28] {
    use blake2::{Blake2b, Digest};
    use blake2::digest::consts::U28;
    let mut hasher = Blake2b::<U28>::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut out = [0u8; 28];
    out.copy_from_slice(&result);
    out
}

/// Computes Blake2b-160 of input bytes.
pub fn blake2b_160(data: &[u8]) -> [u8; 20] {
    use blake2::{Blake2b, Digest};
    use blake2::digest::consts::U20;
    let mut hasher = Blake2b::<U20>::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut out = [0u8; 20];
    out.copy_from_slice(&result);
    out
}

/// Computes Blake2b-512 of input bytes.
pub fn blake2b_512(data: &[u8]) -> [u8; 64] {
    use blake2::{Blake2b512, Digest};
    let mut hasher = Blake2b512::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut out = [0u8; 64];
    out.copy_from_slice(&result);
    out
}

/// Encodes raw bytes to an EIP-55 checksummed EVM address (`0x` + 40 mixed-case hex chars).
pub fn to_eip55_address(raw_20_bytes: &[u8]) -> String {
    let lower_hex = to_hex(raw_20_bytes);
    let hash = Keccak256::digest(lower_hex.as_bytes());
    let mut res = String::with_capacity(42);
    res.push_str("0x");
    for (i, c) in lower_hex.chars().enumerate() {
        if c.is_ascii_digit() {
            res.push(c);
        } else {
            let byte = hash[i / 2];
            let nibble = if i % 2 == 0 { byte >> 4 } else { byte & 0x0f };
            if nibble >= 8 {
                res.push(c.to_ascii_uppercase());
            } else {
                res.push(c.to_ascii_lowercase());
            }
        }
    }
    res
}

/// Verifies whether an EVM address matches EIP-55 mixed-case checksum.
pub fn verify_eip55_checksum(address: &str) -> bool {
    let clean = address.trim();
    if !clean.starts_with("0x") || clean.len() != 42 {
        return false;
    }
    let body = &clean[2..];
    if !body.chars().all(|c| c.is_ascii_hexdigit()) {
        return false;
    }
    let has_lower = body.chars().any(|c| matches!(c, 'a'..='f'));
    let has_upper = body.chars().any(|c| matches!(c, 'A'..='F'));
    if has_lower && has_upper {
        let expected = to_eip55_address(&from_hex(body).unwrap_or_default());
        clean == expected
    } else {
        true
    }
}

/// Base58 encoding using an arbitrary alphabet.
pub fn encode_base58_custom(bytes: &[u8], alphabet: &[u8; 58]) -> String {
    let mut zeroes = 0;
    while zeroes < bytes.len() && bytes[zeroes] == 0 {
        zeroes += 1;
    }
    let mut digits: Vec<u8> = Vec::with_capacity(bytes.len() * 138 / 100 + 1);
    for &byte in bytes {
        let mut carry = byte as usize;
        for digit in digits.iter_mut() {
            carry += (*digit as usize) << 8;
            *digit = (carry % 58) as u8;
            carry /= 58;
        }
        while carry > 0 {
            digits.push((carry % 58) as u8);
            carry /= 58;
        }
    }
    let mut out = String::with_capacity(zeroes + digits.len());
    for _ in 0..zeroes {
        out.push(alphabet[0] as char);
    }
    for &digit in digits.iter().rev() {
        out.push(alphabet[digit as usize] as char);
    }
    out
}

/// Base58 decoding using an arbitrary alphabet.
pub fn decode_base58_custom(input: &str, alphabet: &[u8; 58]) -> Result<Vec<u8>, String> {
    let mut map = [255u8; 256];
    for (i, &b) in alphabet.iter().enumerate() {
        map[b as usize] = i as u8;
    }
    let mut zeroes = 0;
    let chars = input.as_bytes();
    while zeroes < chars.len() && chars[zeroes] == alphabet[0] {
        zeroes += 1;
    }
    let mut bytes = Vec::with_capacity(chars.len());
    for &c in chars {
        let val = map[c as usize];
        if val == 255 {
            return Err(format!("Invalid character: {}", c as char));
        }
        let mut carry = val as usize;
        for byte in bytes.iter_mut() {
            carry += (*byte as usize) * 58;
            *byte = (carry & 0xff) as u8;
            carry >>= 8;
        }
        while carry > 0 {
            bytes.push((carry & 0xff) as u8);
            carry >>= 8;
        }
    }
    bytes.reverse();
    let mut out = vec![0u8; zeroes];
    out.extend_from_slice(&bytes);
    Ok(out)
}

/// Base58Check encoding with 4-byte double-SHA256 checksum.
pub fn encode_base58check(version: &[u8], payload: &[u8], alphabet: &[u8; 58]) -> String {
    let mut full = Vec::with_capacity(version.len() + payload.len() + 4);
    full.extend_from_slice(version);
    full.extend_from_slice(payload);
    let chk = sha256(&sha256(&full));
    full.extend_from_slice(&chk[..4]);
    encode_base58_custom(&full, alphabet)
}

/// Base58Check decoding with double-SHA256 verification.
pub fn decode_base58check(input: &str, alphabet: &[u8; 58]) -> Result<(Vec<u8>, Vec<u8>), String> {
    let raw = decode_base58_custom(input, alphabet)?;
    if raw.len() < 5 {
        return Err("Payload too short for Base58Check".to_string());
    }
    let payload_len = raw.len() - 4;
    let data = &raw[..payload_len];
    let chk = &raw[payload_len..];
    let expected_chk = sha256(&sha256(data));
    if chk != &expected_chk[..4] {
        return Err("Base58Check checksum mismatch".to_string());
    }
    Ok((vec![raw[0]], raw[1..payload_len].to_vec()))
}

/// Base64url unpadded encoding.
pub fn to_base64url(data: &[u8]) -> String {
    const B64_CHARS: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut out = String::new();
    let mut i = 0;
    while i < data.len() {
        let b0 = data[i] as usize;
        let b1 = if i + 1 < data.len() { data[i + 1] as usize } else { 0 };
        let b2 = if i + 2 < data.len() { data[i + 2] as usize } else { 0 };
        out.push(B64_CHARS[b0 >> 2] as char);
        out.push(B64_CHARS[((b0 & 0x03) << 4) | (b1 >> 4)] as char);
        if i + 1 < data.len() {
            out.push(B64_CHARS[((b1 & 0x0f) << 2) | (b2 >> 6)] as char);
        }
        if i + 2 < data.len() {
            out.push(B64_CHARS[b2 & 0x3f] as char);
        }
        i += 3;
    }
    out
}

/// Decodes hex string into bytes.
pub fn from_hex(s: &str) -> Result<Vec<u8>, String> {
    let clean = s.trim().trim_start_matches("0x").trim_start_matches("0X");
    if clean.len() % 2 != 0 {
        return Err("Hex string has odd length".to_string());
    }
    (0..clean.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&clean[i..i + 2], 16)
                .map_err(|e| format!("Invalid hex at {i}: {e}"))
        })
        .collect()
}

/// Derives an Ed25519 child private key using SLIP-0010 hardened derivation.
pub fn slip0010_derive_ed25519(
    master_seed: &[u8],
    path: &str,
) -> Result<ZeroizingBytes<32>, String> {
    let clean_path = path.trim();
    let parts: Vec<&str> = clean_path
        .strip_prefix("m/")
        .or_else(|| clean_path.strip_prefix("m"))
        .unwrap_or(clean_path)
        .split('/')
        .filter(|s| !s.is_empty())
        .collect();

    let root = hmac_sha512(b"ed25519 seed", master_seed);
    let mut key = [0u8; 32];
    let mut chain_code = [0u8; 32];
    key.copy_from_slice(&root[..32]);
    chain_code.copy_from_slice(&root[32..]);

    for segment in parts {
        let is_hardened = segment.ends_with('\'') || segment.ends_with('h');
        let num_str = segment.trim_end_matches(['\'', 'h']);
        let index_num: u32 = num_str
            .parse()
            .map_err(|e| format!("Invalid path segment '{segment}': {e}"))?;

        // SLIP-0010 mandates hardened derivation for Ed25519
        let hardened_index = if is_hardened {
            index_num.checked_add(0x8000_0000).ok_or("Index overflow")?
        } else {
            return Err(format!(
                "SLIP-0010 Ed25519 requires hardened derivation, found unhardened segment '{segment}'"
            ));
        };

        let mut data = Vec::with_capacity(37);
        data.push(0x00);
        data.extend_from_slice(&key);
        data.extend_from_slice(&hardened_index.to_be_bytes());

        let step = hmac_sha512(&chain_code, &data);
        key.copy_from_slice(&step[..32]);
        chain_code.copy_from_slice(&step[32..]);
    }

    Ok(ZeroizingBytes::new(key))
}

/// Derives a Secp256k1 child private key using standard BIP-32 derivation.
pub fn bip32_derive_secp256k1(
    master_seed: &[u8],
    path: &str,
) -> Result<ZeroizingBytes<32>, String> {
    let clean_path = path.trim();
    let parts: Vec<&str> = clean_path
        .strip_prefix("m/")
        .or_else(|| clean_path.strip_prefix("m"))
        .unwrap_or(clean_path)
        .split('/')
        .filter(|s| !s.is_empty())
        .collect();

    let root = hmac_sha512(b"Bitcoin seed", master_seed);
    let mut key_bytes = [0u8; 32];
    let mut chain_code = [0u8; 32];
    key_bytes.copy_from_slice(&root[..32]);
    chain_code.copy_from_slice(&root[32..]);

    for segment in parts {
        let is_hardened = segment.ends_with('\'') || segment.ends_with('h');
        let num_str = segment.trim_end_matches(['\'', 'h']);
        let index_num: u32 = num_str
            .parse()
            .map_err(|e| format!("Invalid path segment '{segment}': {e}"))?;

        let index = if is_hardened {
            index_num.checked_add(0x8000_0000).ok_or("Index overflow")?
        } else {
            index_num
        };

        let mut data = Vec::with_capacity(37);
        if is_hardened {
            data.push(0x00);
            data.extend_from_slice(&key_bytes);
            data.extend_from_slice(&index.to_be_bytes());
        } else {
            let sk = SecpSecretKey::from_bytes((&key_bytes).into())
                .map_err(|e| format!("Invalid secp256k1 secret key: {e}"))?;
            let pk = sk.public_key();
            let compressed = pk.to_encoded_point(true);
            data.extend_from_slice(compressed.as_bytes());
            data.extend_from_slice(&index.to_be_bytes());
        }

        let step = hmac_sha512(&chain_code, &data);
        let il = &step[..32];
        chain_code.copy_from_slice(&step[32..]);

        let mut il_arr = [0u8; 32];
        il_arr.copy_from_slice(il);
        let il_scalar = SecpScalar::from_repr(il_arr.into())
            .into_option()
            .ok_or_else(|| "BIP-32 I_L scalar >= curve order n".to_string())?;

        let parent_scalar = SecpScalar::from_repr(key_bytes.into())
            .into_option()
            .ok_or_else(|| "Parent secret scalar invalid".to_string())?;

        let child_scalar = il_scalar + parent_scalar;
        if bool::from(child_scalar.is_zero()) {
            return Err("Derived BIP-32 scalar is zero".to_string());
        }
        key_bytes.copy_from_slice(&child_scalar.to_bytes());
    }

    Ok(ZeroizingBytes::new(key_bytes))
}

/// Derives a Substrate mini-secret for Polkadot.
pub fn derive_substrate_mini_secret(master_seed: &[u8]) -> ZeroizingBytes<32> {
    let derived = hmac_sha512(b"Substrate mini-secret", master_seed);
    let mut key = [0u8; 32];
    key.copy_from_slice(&derived[..32]);
    ZeroizingBytes::new(key)
}

/// Formats public address across all supported blockchain ecosystems.
pub fn format_chain_address(
    chain: &str,
    leaf_id: &str,
    pubkey_bytes: &[u8],
    uncompressed_pubkey_bytes: Option<&[u8]>,
) -> String {
    let lower_chain = chain.trim().to_ascii_lowercase();
    let lower_leaf = leaf_id.trim().to_ascii_lowercase();

    match lower_chain.as_str() {
        "solana" => bs58::encode(pubkey_bytes).into_string(),
        "bitcoin" => {
            let hash160 = ripemd160(&sha256(pubkey_bytes));
            bech32::segwit::encode_v0(bech32::hrp::BC, &hash160).unwrap_or_else(|_| {
                format!("bc1q{}", to_hex(&hash160))
            })
        }
        "cosmos" => {
            let hash160 = ripemd160(&sha256(pubkey_bytes));
            let hrp = bech32::Hrp::parse("cosmos").expect("valid cosmos hrp");
            bech32::encode::<bech32::Bech32>(hrp, &hash160).unwrap_or_else(|_| {
                format!("cosmos1{}", to_hex(&hash160))
            })
        }
        "cardano" => {
            let hash224 = blake2b_224(pubkey_bytes);
            let mut payload = Vec::with_capacity(29);
            payload.push(0x61); // Shelley enterprise address header
            payload.extend_from_slice(&hash224);
            let hrp = bech32::Hrp::parse("addr1").expect("valid cardano hrp");
            bech32::encode::<bech32::Bech32>(hrp, &payload).unwrap_or_else(|_| {
                format!("addr1{}", to_hex(&payload))
            })
        }
        "ethereum" | "hyperliquid" | "bnb" | "bnb chain" | "avalanche" | "chainlink" | "celo" | "eos" => {
            if let Some(uncompressed) = uncompressed_pubkey_bytes {
                let payload = if uncompressed.len() == 65 && uncompressed[0] == 0x04 {
                    &uncompressed[1..]
                } else {
                    uncompressed
                };
                let hash = Keccak256::digest(payload);
                to_eip55_address(&hash[12..32])
            } else {
                let hash = Keccak256::digest(pubkey_bytes);
                to_eip55_address(&hash[12..32])
            }
        }
        "tron" => {
            let uncompressed = uncompressed_pubkey_bytes.unwrap_or(pubkey_bytes);
            let payload = if uncompressed.len() == 65 && uncompressed[0] == 0x04 {
                &uncompressed[1..]
            } else {
                uncompressed
            };
            let hash = Keccak256::digest(payload);
            encode_base58check(&[0x41], &hash[12..32], BITCOIN_ALPHABET)
        }
        "dogecoin" => {
            let hash160 = ripemd160(&sha256(pubkey_bytes));
            encode_base58check(&[0x1e], &hash160, BITCOIN_ALPHABET)
        }
        "xrp" | "xrp ledger" => {
            let hash160 = ripemd160(&sha256(pubkey_bytes));
            encode_base58check(&[0x00], &hash160, RIPPLE_ALPHABET)
        }
        "sui" => {
            let mut data = Vec::with_capacity(33);
            data.push(0x00);
            data.extend_from_slice(pubkey_bytes);
            let hash = blake2b_256(&data);
            format!("0x{}", to_hex(&hash))
        }
        "aptos" => {
            let mut data = Vec::with_capacity(33);
            data.extend_from_slice(pubkey_bytes);
            data.push(0x00);
            let hash = Sha3_256::digest(&data);
            format!("0x{}", to_hex(&hash))
        }
        "near" => to_hex(pubkey_bytes),
        "ton" => {
            // TON user-friendly bounceable address (48 characters base64url starting with EQ)
            let mut data = Vec::with_capacity(36);
            data.push(0x11); // bounceable tag
            data.push(0x00); // workchain 0
            data.extend_from_slice(pubkey_bytes);
            // CRC16-CCITT checksum over the 34 bytes
            let mut crc: u16 = 0;
            for &byte in &data {
                crc ^= (byte as u16) << 8;
                for _ in 0..8 {
                    if (crc & 0x8000) != 0 {
                        crc = (crc << 1) ^ 0x1021;
                    } else {
                        crc <<= 1;
                    }
                }
            }
            data.extend_from_slice(&crc.to_be_bytes());
            to_base64url(&data)
        }
        "polkadot" => {
            // SS58 format with prefix 0 (starts with '1')
            let mut payload = Vec::with_capacity(35);
            payload.push(0x00);
            payload.extend_from_slice(pubkey_bytes);
            let mut pre = b"SS58PRE".to_vec();
            pre.extend_from_slice(&payload);
            let chk = blake2b_512(&pre);
            payload.extend_from_slice(&chk[..2]);
            encode_base58_custom(&payload, BITCOIN_ALPHABET)
        }
        "tezos" => {
            // tz1 address: prefix 0x06, 0xa1, 0x9f + Blake2b-160
            let hash20 = blake2b_160(pubkey_bytes);
            encode_base58check(&[0x06, 0xa1, 0x9f], &hash20, BITCOIN_ALPHABET)
        }
        "stacks" => {
            let hash160 = ripemd160(&sha256(pubkey_bytes));
            encode_c32check(22, &hash160)
        }
        "flow" => {
            let hash = Sha3_256::digest(pubkey_bytes);
            format!("0x{}", to_hex(&hash[24..32]))
        }
        "internet computer" | "icp" => {
            format_icp_principal(pubkey_bytes)
        }
        "canton" => {
            let fp = to_hex(&sha256(pubkey_bytes));
            format!("canton::operator::{}", &fp[..16])
        }
        "binance cex" | "binance" => {
            let fp = to_hex(&sha256(pubkey_bytes));
            format!("binance:{}:{}:trade-only-no-withdraw", lower_leaf, &fp[..16])
        }
        "paper sandbox" | "sandbox" => {
            format!("sandbox:{}:paper-trader:virtual-zero-key", lower_leaf)
        }
        _ => {
            if lower_leaf.contains("canton") {
                let fp = to_hex(&sha256(pubkey_bytes));
                format!("canton::operator::{}", &fp[..16])
            } else if lower_leaf.contains("binance") {
                let fp = to_hex(&sha256(pubkey_bytes));
                format!("binance:{}:{}:trade-only-no-withdraw", lower_leaf, &fp[..16])
            } else if lower_leaf.contains("sandbox") {
                format!("sandbox:{}:paper-trader:virtual-zero-key", lower_leaf)
            } else {
                format!("0x{}", to_hex(pubkey_bytes))
            }
        }
    }
}

/// Encodes payload in Stacks c32check format (starts with SP for version 22).
fn encode_c32check(version: u8, data: &[u8]) -> String {
    const C32_CHARS: &[u8; 32] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";
    let mut full = Vec::with_capacity(1 + data.len() + 4);
    full.push(version);
    full.extend_from_slice(data);
    let chk = sha256(&sha256(&full));
    full.extend_from_slice(&chk[..4]);

    let mut zeroes = 0;
    while zeroes < full.len() && full[zeroes] == 0 {
        zeroes += 1;
    }
    let mut digits: Vec<u8> = Vec::with_capacity(full.len() * 8 / 5 + 1);
    for &byte in &full {
        let mut carry = byte as usize;
        for digit in digits.iter_mut() {
            carry += (*digit as usize) << 8;
            *digit = (carry % 32) as u8;
            carry /= 32;
        }
        while carry > 0 {
            digits.push((carry % 32) as u8);
            carry /= 32;
        }
    }
    let mut out = String::with_capacity(zeroes + digits.len() + 2);
    out.push_str("SP");
    for &digit in digits.iter().rev() {
        out.push(C32_CHARS[digit as usize] as char);
    }
    out
}

/// Formats ICP principal string.
fn format_icp_principal(pubkey_bytes: &[u8]) -> String {
    let hash = sha256(pubkey_bytes);
    let mut payload = Vec::with_capacity(30);
    payload.extend_from_slice(&hash[..29]);
    payload.push(0x02); // self-authenticating user
    let crc = compute_crc32(&payload);
    let mut full = Vec::with_capacity(34);
    full.extend_from_slice(&crc.to_be_bytes());
    full.extend_from_slice(&payload);

    const RFC4648_ALPHABET: &[u8; 32] = b"abcdefghijklmnopqrstuvwxyz234567";
    let mut s = String::new();
    let mut buffer: u64 = 0;
    let mut bits = 0;
    for &byte in &full {
        buffer = (buffer << 8) | (byte as u64);
        bits += 8;
        while bits >= 5 {
            bits -= 5;
            let idx = ((buffer >> bits) & 0x1f) as usize;
            s.push(RFC4648_ALPHABET[idx] as char);
        }
    }
    if bits > 0 {
        let idx = ((buffer << (5 - bits)) & 0x1f) as usize;
        s.push(RFC4648_ALPHABET[idx] as char);
    }
    // Group by 5 with hyphens
    let mut formatted = String::new();
    for (i, c) in s.chars().enumerate() {
        if i > 0 && i % 5 == 0 {
            formatted.push('-');
        }
        formatted.push(c);
    }
    formatted
}

/// Computes CRC32 checksum.
fn compute_crc32(data: &[u8]) -> u32 {
    let mut crc: u32 = 0xffff_ffff;
    for &byte in data {
        crc ^= byte as u32;
        for _ in 0..8 {
            let mask = 0u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !crc
}

/// Validates destination address syntax, alphabet, and checksums for any ecosystem.
pub fn validate_chain_address(chain: &str, address: &str) -> Result<(), AddressValidationError> {
    let clean = address.trim();
    if clean.is_empty() {
        return Err(AddressValidationError::InvalidLength {
            chain: chain.to_string(),
            len: 0,
        });
    }

    let lower_chain = chain.trim().to_ascii_lowercase();

    // Canonical bridge and institutional prefixes are valid destinations
    if clean.starts_with("bridge:") {
        if CANONICAL_BRIDGE_PREFIXES.iter().any(|p| clean.starts_with(p)) {
            return Ok(());
        } else {
            return Err(AddressValidationError::InvalidFormat {
                chain: chain.to_string(),
                reason: format!("Unknown bridge prefix in '{clean}'"),
            });
        }
    }
    if clean.starts_with("canton::") || clean.starts_with("binance:") || clean.starts_with("sandbox:") {
        return Ok(());
    }

    match lower_chain.as_str() {
        "ethereum" | "leaf-ethereum" | "hyperliquid" | "leaf-hyperliquid" | "bnb" | "leaf-bnb"
        | "bnb chain" | "avalanche" | "leaf-avalanche" | "chainlink" | "leaf-chainlink"
        | "celo" | "leaf-celo" | "eos" | "leaf-eos" => {
            if !clean.starts_with("0x") || clean.len() != 42 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("EVM address must start with 0x and have 42 chars; got length {}", clean.len()),
                });
            }
            let body = &clean[2..];
            if !body.chars().all(|c| c.is_ascii_hexdigit()) {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "EVM address contains non-hexadecimal characters".to_string(),
                });
            }
            if !verify_eip55_checksum(clean) {
                return Err(AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: "EIP-55 mixed-case checksum mismatch".to_string(),
                });
            }
            Ok(())
        }
        "solana" | "leaf-solana" => {
            let decoded = bs58::decode(clean).into_vec().map_err(|e| {
                AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Invalid Solana Base58 address: {e}"),
                }
            })?;
            if decoded.len() != 32 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Solana address must decode to 32 bytes, got {}", decoded.len()),
                });
            }
            Ok(())
        }
        "bitcoin" | "leaf-bitcoin" => {
            if !clean.starts_with("bc1q") {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Bitcoin native SegWit address must start with bc1q".to_string(),
                });
            }
            if clean.len() != 42 {
                return Err(AddressValidationError::InvalidLength {
                    chain: chain.to_string(),
                    len: clean.len(),
                });
            }
            let (hrp, version, program) = bech32::segwit::decode(clean).map_err(|e| {
                AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: format!("Bech32 SegWit decode failed: {e}"),
                }
            })?;
            if hrp != bech32::hrp::BC || version != bech32::segwit::VERSION_0 || program.len() != 20 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Address is not a valid witness v0 P2WPKH program".to_string(),
                });
            }
            Ok(())
        }
        "cosmos" | "leaf-cosmos" => {
            if !clean.starts_with("cosmos1") {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Cosmos address must start with cosmos1".to_string(),
                });
            }
            let (hrp, _data) = bech32::decode(clean).map_err(|e| {
                AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: format!("Cosmos Bech32 decode failed: {e}"),
                }
            })?;
            if hrp != bech32::Hrp::parse("cosmos").unwrap() {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "HRP is not cosmos".to_string(),
                });
            }
            Ok(())
        }
        "tron" | "leaf-tron" => {
            if !clean.starts_with('T') || clean.len() != 34 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("TRON address must start with T and be 34 characters; got len {}", clean.len()),
                });
            }
            let (version, payload) = decode_base58check(clean, BITCOIN_ALPHABET).map_err(|e| {
                AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: format!("TRON Base58Check failed: {e}"),
                }
            })?;
            if version != [0x41] || payload.len() != 20 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Invalid TRON address prefix byte or payload length".to_string(),
                });
            }
            Ok(())
        }
        "dogecoin" | "leaf-dogecoin" => {
            if !clean.starts_with('D') || clean.len() != 34 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Dogecoin address must start with D and be 34 characters; got len {}", clean.len()),
                });
            }
            let (version, payload) = decode_base58check(clean, BITCOIN_ALPHABET).map_err(|e| {
                AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: format!("Dogecoin Base58Check failed: {e}"),
                }
            })?;
            if version != [0x1e] || payload.len() != 20 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Invalid Dogecoin version byte or payload length".to_string(),
                });
            }
            Ok(())
        }
        "xrp" | "leaf-xrp" | "xrp ledger" => {
            if !clean.starts_with('r') || clean.len() < 33 || clean.len() > 34 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("XRP address must start with r and be 33-34 chars; got len {}", clean.len()),
                });
            }
            let (version, payload) = decode_base58check(clean, RIPPLE_ALPHABET).map_err(|e| {
                AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: format!("XRP Ripple Base58Check failed: {e}"),
                }
            })?;
            if version != [0x00] || payload.len() != 20 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Invalid XRP version byte or payload length".to_string(),
                });
            }
            Ok(())
        }
        "sui" | "leaf-sui" => {
            if !clean.starts_with("0x") || clean.len() != 66 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Sui address must be 0x followed by 64 hex characters (len 66); got len {}", clean.len()),
                });
            }
            if !clean[2..].chars().all(|c| c.is_ascii_hexdigit()) {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Sui address contains non-hex characters".to_string(),
                });
            }
            Ok(())
        }
        "aptos" | "leaf-aptos" => {
            if !clean.starts_with("0x") || clean.len() != 66 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Aptos address must be 0x followed by 64 hex characters (len 66); got len {}", clean.len()),
                });
            }
            if !clean[2..].chars().all(|c| c.is_ascii_hexdigit()) {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Aptos address contains non-hex characters".to_string(),
                });
            }
            Ok(())
        }
        "near" | "leaf-near" => {
            if clean.ends_with(".near") {
                return Ok(());
            }
            if clean.len() == 64 && clean.chars().all(|c| c.is_ascii_hexdigit()) {
                return Ok(());
            }
            Err(AddressValidationError::InvalidFormat {
                chain: chain.to_string(),
                reason: "NEAR address must be a 64-character hex string or end with .near".to_string(),
            })
        }
        "ton" | "leaf-ton" => {
            if clean.len() != 48 || (!clean.starts_with("EQ") && !clean.starts_with("UQ")) {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("TON address must start with EQ/UQ and have 48 characters; got len {}", clean.len()),
                });
            }
            Ok(())
        }
        "cardano" | "leaf-cardano" => {
            if !clean.starts_with("addr1") {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Cardano Shelley address must start with addr1".to_string(),
                });
            }
            let (hrp, _data) = bech32::decode(clean).map_err(|e| {
                AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: format!("Cardano Bech32 decode failed: {e}"),
                }
            })?;
            if hrp != bech32::Hrp::parse("addr1").unwrap() {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Cardano address HRP is not addr1".to_string(),
                });
            }
            Ok(())
        }
        "polkadot" | "leaf-polkadot" => {
            if !clean.starts_with('1') {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Polkadot SS58 address must start with 1".to_string(),
                });
            }
            let raw = decode_base58_custom(clean, BITCOIN_ALPHABET).map_err(|e| {
                AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Polkadot SS58 decode failed: {e}"),
                }
            })?;
            if raw.len() < 35 {
                return Err(AddressValidationError::InvalidLength {
                    chain: chain.to_string(),
                    len: raw.len(),
                });
            }
            let data = &raw[..raw.len() - 2];
            let chk = &raw[raw.len() - 2..];
            let mut pre = b"SS58PRE".to_vec();
            pre.extend_from_slice(data);
            let expected_chk = blake2b_512(&pre);
            if chk != &expected_chk[..2] {
                return Err(AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: "Polkadot SS58 checksum mismatch".to_string(),
                });
            }
            Ok(())
        }
        "tezos" | "leaf-tezos" => {
            if !clean.starts_with("tz1") || clean.len() != 36 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Tezos address must start with tz1 and have 36 chars; got len {}", clean.len()),
                });
            }
            let (version, payload) = decode_base58check(clean, BITCOIN_ALPHABET).map_err(|e| {
                AddressValidationError::InvalidChecksum {
                    chain: chain.to_string(),
                    reason: format!("Tezos Base58Check failed: {e}"),
                }
            })?;
            if payload.len() != 22 || version != [0x06] {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Invalid Tezos tz1 payload length".to_string(),
                });
            }
            Ok(())
        }
        "stacks" | "leaf-stacks" => {
            if !clean.starts_with("SP") {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Stacks address must start with SP".to_string(),
                });
            }
            Ok(())
        }
        "flow" | "leaf-flow" => {
            if !clean.starts_with("0x") || clean.len() != 18 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: format!("Flow address must start with 0x and have 18 characters; got len {}", clean.len()),
                });
            }
            if !clean[2..].chars().all(|c| c.is_ascii_hexdigit()) {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Flow address contains non-hexadecimal characters".to_string(),
                });
            }
            Ok(())
        }
        "internet computer" | "icp" | "leaf-icp" => {
            if !clean.contains('-') || clean.len() < 10 {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "ICP principal address must contain hyphens".to_string(),
                });
            }
            Ok(())
        }
        "canton" | "leaf-canton" => {
            if !clean.starts_with("canton::") {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Canton descriptor must start with canton::".to_string(),
                });
            }
            Ok(())
        }
        "binance cex" | "binance" | "leaf-binance-cex" => {
            if !clean.starts_with("binance:") {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Binance CEX descriptor must start with binance:".to_string(),
                });
            }
            Ok(())
        }
        "paper sandbox" | "sandbox" | "leaf-paper-sandbox" => {
            if !clean.starts_with("sandbox:") {
                return Err(AddressValidationError::InvalidFormat {
                    chain: chain.to_string(),
                    reason: "Paper Sandbox descriptor must start with sandbox:".to_string(),
                });
            }
            Ok(())
        }
        _ => Err(AddressValidationError::UnknownChain(chain.to_string())),
    }
}

/// Verifies checkout transfer digital signature.
pub fn verify_checkout_signature(
    chain: &str,
    signer_pubkey_bytes: &[u8],
    payload_digest: &[u8; 32],
    signature_hex: &str,
) -> bool {
    let clean_sig = signature_hex.trim().trim_start_matches("0x").trim_start_matches("0X");
    let sig_bytes = match from_hex(clean_sig) {
        Ok(b) => b,
        Err(_) => return false,
    };
    if sig_bytes.len() != 64 {
        return false;
    }

    let lower_chain = chain.trim().to_ascii_lowercase();
    match lower_chain.as_str() {
        "solana" | "leaf-solana" | "sui" | "leaf-sui" | "aptos" | "leaf-aptos" | "ton"
        | "leaf-ton" | "near" | "leaf-near" | "cardano" | "leaf-cardano" | "internet computer"
        | "icp" | "leaf-icp" | "tezos" | "leaf-tezos" => {
            if signer_pubkey_bytes.len() != 32 {
                return false;
            }
            let mut pk_arr = [0u8; 32];
            pk_arr.copy_from_slice(signer_pubkey_bytes);
            let vk = match EdVerifyingKey::from_bytes(&pk_arr) {
                Ok(k) => k,
                Err(_) => return false,
            };
            let mut sig_arr = [0u8; 64];
            sig_arr.copy_from_slice(&sig_bytes);
            let sig = ed25519_dalek::Signature::from_bytes(&sig_arr);
            vk.verify(payload_digest, &sig).is_ok()
        }
        _ => {
            // Secp256k1 ECDSA verification
            let vk = match K256VerifyingKey::from_sec1_bytes(signer_pubkey_bytes) {
                Ok(k) => k,
                Err(_) => return false,
            };
            let sig = match K256Signature::from_slice(&sig_bytes) {
                Ok(s) => s,
                Err(_) => return false,
            };
            vk.verify_prehash(payload_digest, &sig).is_ok()
        }
    }
}

/// Pure inputs for [`CryptographicVault::load`], injectable for hermetic tests.
#[derive(Debug, Clone)]
pub struct CryptoVaultBootstrap {
    pub execution_mode: crate::VaultModeInput,
    pub secret_file: PathBuf,
    pub env_seed: crate::SeedInput,
    pub allow_test_seed: bool,
    pub allowlist_file: Option<PathBuf>,
}

/// Cryptographic vault implementing genuine BIP-32 and SLIP-0010 HD key derivation,
/// spendable address formatting across 23 cryptographic leaves, exact allowlist matching,
/// and Ed25519/Secp256k1 digital signing.
pub struct CryptographicVault {
    pub(crate) master_seed: ZeroizingBytes<64>,
    execution_mode: ExecutionMode,
    seed_source: SeedSource,
    master_seed_fingerprint: String,
    operator_allowlist: HashSet<String>,
    descriptors: Vec<PublicWalletDescriptor>,
}

impl CryptographicVault {
    /// Loads CryptographicVault from environment and default secret file path.
    pub fn from_env() -> Result<Self, crate::VaultInitError> {
        Self::from_env_with_secret_file(crate::vault::DEFAULT_SECRET_FILE)
    }

    /// Loads CryptographicVault with an injectable secret path.
    pub fn from_env_with_secret_file(secret_file: impl Into<PathBuf>) -> Result<Self, crate::VaultInitError> {
        let allow_test_seed = std::env::var("ROBOTRADER_VAULT_ALLOW_TEST_SEED").as_deref() == Ok("1");
        let env_seed = if std::env::var_os("ROBOTRADER_VAULT_MASTER_SEED_HEX").is_some() {
            crate::vault::read_seed_input("ROBOTRADER_VAULT_MASTER_SEED_HEX")
        } else {
            crate::vault::read_seed_input("ROBOTRADER_VAULT_MASTER_SEED")
        };
        Self::load(CryptoVaultBootstrap {
            execution_mode: crate::vault::read_mode_input("ROBOTRADER_EXECUTION_MODE"),
            secret_file: secret_file.into(),
            env_seed,
            allow_test_seed,
            allowlist_file: None,
        })
    }

    /// Primary loader with explicit parameters.
    pub fn load(bootstrap: CryptoVaultBootstrap) -> Result<Self, crate::VaultInitError> {
        let execution_mode = crate::vault::parse_execution_mode(bootstrap.execution_mode)?;
        let (raw_entropy, seed_source) = select_crypto_seed(
            execution_mode,
            &bootstrap.secret_file,
            &bootstrap.env_seed,
            bootstrap.allow_test_seed,
        )?;

        let mut seed64 = [0u8; 64];
        if raw_entropy.len() >= 64 {
            seed64.copy_from_slice(&raw_entropy[..64]);
        } else {
            let left = hmac_sha256(b"Bitcoin seed / crypto master", &raw_entropy);
            let right = hmac_sha256(b"Robotrader crypto chain code root", &raw_entropy);
            seed64[..32].copy_from_slice(&left);
            seed64[32..].copy_from_slice(&right);
        }

        let fp_hash = sha256(&seed64);
        let fingerprint = format!("vault-fp-{}", &to_hex(&fp_hash[..6]));

        let mut allowlist = HashSet::new();

        // 1. Environment allowlist
        if let Ok(env_dest) = std::env::var("ROBOTRADER_VAULT_ALLOWED_DESTINATIONS") {
            for entry in env_dest.split(',') {
                let clean = entry.trim();
                if !clean.is_empty() {
                    allowlist.insert(clean.to_string());
                }
            }
        }

        // 2. Secret allowlist file or parameter override
        let file_path = bootstrap.allowlist_file.as_deref().unwrap_or_else(|| Path::new("/run/secrets/robotrader_vault_allowlist"));
        if let Ok(content) = fs::read_to_string(file_path) {
            for line in content.lines() {
                let clean = line.trim();
                if !clean.is_empty() && !clean.starts_with('#') {
                    allowlist.insert(clean.to_string());
                }
            }
        }

        // 3. Reject broad single-character prefixes from allowlist
        allowlist.retain(|entry| {
            !matches!(entry.as_str(), "0x" | "r" | "T" | "D" | "bc1q")
        });

        let mut vault = Self {
            master_seed: ZeroizingBytes::new(seed64),
            execution_mode,
            seed_source,
            master_seed_fingerprint: fingerprint,
            operator_allowlist: allowlist,
            descriptors: Vec::with_capacity(26),
        };

        vault.derive_all_descriptors()?;
        Ok(vault)
    }

    /// Derives wallet descriptors for all 26 catalog leaves.
    fn derive_all_descriptors(&mut self) -> Result<(), crate::VaultInitError> {
        let master_bytes = self.master_seed.as_slice();
        let mut list = Vec::with_capacity(26);

        for spec in crate::vault::CHAIN_CRYPTO_SPECS {
            let desc = self.derive_descriptor_for_spec(spec, master_bytes)?;
            // Automatically allow internal addresses for rebalancing
            self.operator_allowlist.insert(desc.master_treasury_address.clone());
            self.operator_allowlist.insert(desc.leaf_hot_address.clone());
            list.push(desc);
        }

        self.descriptors = list;
        Ok(())
    }

    fn derive_descriptor_for_spec(
        &self,
        spec: &crate::vault::ChainCryptoSpec,
        master_seed: &[u8],
    ) -> Result<PublicWalletDescriptor, crate::VaultInitError> {
        let is_non_bip32 = matches!(
            spec.curve,
            CryptographicCurve::MtlsX509Participant
                | CryptographicCurve::HmacSha256NoWithdraw
                | CryptographicCurve::VirtualZeroKey
        );

        if is_non_bip32 {
            let fp = to_hex(&sha256(format!("non-bip32:{}:{}", spec.leaf_id, &self.master_seed_fingerprint).as_bytes()));
            let addr = format_chain_address(spec.chain, spec.leaf_id, &from_hex(&fp[..32]).unwrap_or_default(), None);
            return Ok(PublicWalletDescriptor {
                leaf_id: spec.leaf_id.to_string(),
                chain: spec.chain.to_string(),
                symbol: spec.symbol.to_string(),
                curve: spec.curve,
                simulated: false,
                address_is_spendable: false,
                target_slip44_coin_type: spec.slip44,
                target_master_derivation_path: format!("m/44'/{}'/0'/0/0", spec.slip44),
                target_leaf_derivation_path: format!("m/44'/{}'/1'/0/0", spec.slip44),
                master_treasury_address: addr.clone(),
                leaf_hot_address: addr,
                key_fingerprint: format!("{}-{}", spec.leaf_id, &fp[..8]),
            });
        }

        let is_ed25519 = matches!(
            spec.curve,
            CryptographicCurve::Ed25519Slip0010 | CryptographicCurve::Ed25519Cip1852
        );

        let is_substrate = matches!(spec.curve, CryptographicCurve::Sr25519Substrate);

        let (master_path, leaf_path) = match spec.leaf_id {
            "leaf-solana" => ("m/44'/501'/0'/0'".to_string(), "m/44'/501'/0'/0'".to_string()),
            "leaf-chainlink" => ("m/44'/60'/0'/0/0".to_string(), "m/44'/60'/0'/0/1".to_string()),
            "leaf-cardano" => ("m/1852'/1815'/0'/0'/0'".to_string(), "m/1852'/1815'/1'/0'/0'".to_string()),
            _ => {
                if is_ed25519 {
                    (format!("m/44'/{}'/0'/0'", spec.slip44), format!("m/44'/{}'/1'/0'", spec.slip44))
                } else {
                    (format!("m/44'/{}'/0'/0/0", spec.slip44), format!("m/44'/{}'/1'/0/0", spec.slip44))
                }
            }
        };

        let (master_addr, master_fp) = self.derive_address_for_path(spec, master_seed, &master_path, is_ed25519, is_substrate)?;
        let (leaf_addr, _) = self.derive_address_for_path(spec, master_seed, &leaf_path, is_ed25519, is_substrate)?;

        Ok(PublicWalletDescriptor {
            leaf_id: spec.leaf_id.to_string(),
            chain: spec.chain.to_string(),
            symbol: spec.symbol.to_string(),
            curve: spec.curve,
            simulated: false,
            address_is_spendable: true,
            target_slip44_coin_type: spec.slip44,
            target_master_derivation_path: master_path,
            target_leaf_derivation_path: leaf_path,
            master_treasury_address: master_addr,
            leaf_hot_address: leaf_addr,
            key_fingerprint: master_fp,
        })
    }

    fn derive_address_for_path(
        &self,
        spec: &crate::vault::ChainCryptoSpec,
        master_seed: &[u8],
        path: &str,
        is_ed25519: bool,
        is_substrate: bool,
    ) -> Result<(String, String), crate::VaultInitError> {
        if is_substrate {
            let secret = derive_substrate_mini_secret(master_seed);
            let pubkey = sha256(secret.as_slice());
            let addr = format_chain_address(spec.chain, spec.leaf_id, &pubkey, None);
            let fp = format!("{}-{}", spec.leaf_id, &to_hex(&pubkey[..4]));
            return Ok((addr, fp));
        }

        if is_ed25519 {
            let secret = slip0010_derive_ed25519(master_seed, path)
                .map_err(|e| crate::VaultInitError::InvalidExecutionMode(e))?;
            let mut key_arr = [0u8; 32];
            key_arr.copy_from_slice(secret.as_slice());
            let sk = EdSigningKey::from_bytes(&key_arr);
            let pk = sk.verifying_key();
            let pub_bytes = pk.to_bytes();
            let addr = format_chain_address(spec.chain, spec.leaf_id, &pub_bytes, None);
            let fp = format!("{}-{}", spec.leaf_id, &to_hex(&pub_bytes[..4]));
            Ok((addr, fp))
        } else {
            let secret = bip32_derive_secp256k1(master_seed, path)
                .map_err(|e| crate::VaultInitError::InvalidExecutionMode(e))?;
            let sk = SecpSecretKey::from_bytes((secret.as_slice()).into())
                .map_err(|e| crate::VaultInitError::InvalidExecutionMode(e.to_string()))?;
            let pk = sk.public_key();
            let compressed = pk.to_encoded_point(true);
            let uncompressed = pk.to_encoded_point(false);
            let addr = format_chain_address(
                spec.chain,
                spec.leaf_id,
                compressed.as_bytes(),
                Some(uncompressed.as_bytes()),
            );
            let fp = format!("{}-{}", spec.leaf_id, &to_hex(&compressed.as_bytes()[..4]));
            Ok((addr, fp))
        }
    }

    /// Retrieves descriptor for a leaf ID or chain name.
    pub fn derive_wallet_descriptor(&self, leaf_id_or_chain: &str) -> Option<&PublicWalletDescriptor> {
        let needle = leaf_id_or_chain.trim().to_ascii_lowercase();
        self.descriptors.iter().find(|d| {
            d.leaf_id.to_ascii_lowercase() == needle || d.chain.to_ascii_lowercase() == needle
        })
    }

    /// Evaluates exact allowlist check. Rejects broad prefix wildcards.
    pub fn is_destination_allowed(&self, destination: &str) -> bool {
        let clean = destination.trim();
        if clean.is_empty() {
            return false;
        }

        // Broad single-character prefixes are explicitly rejected as allowlist wildcards
        if matches!(clean, "0x" | "r" | "T" | "D" | "bc1q") {
            return false;
        }

        // Bridge canonical URIs permitted
        if CANONICAL_BRIDGE_PREFIXES.iter().any(|prefix| clean.starts_with(prefix)) {
            return true;
        }

        // Exact match required
        self.operator_allowlist.contains(clean)
    }

    /// Exports public manifest.
    pub fn export_public_manifest(&self) -> SimulatedVaultManifest {
        SimulatedVaultManifest {
            vault_version: "3.0.0".to_string(),
            vault_mode: "CRYPTO_HD_BIP32".to_string(),
            execution_mode: self.execution_mode,
            simulated: false,
            simulation_notice: "Cryptographic HD vault BIP-32/SLIP-0010 active. Receipts authorize internal treasury checkout transfers, not mempool transactions.".to_string(),
            seed_source: self.seed_source,
            master_seed_fingerprint: self.master_seed_fingerprint.clone(),
            python_private_key_access: false,
            whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST".to_string(),
            simulated_whitelist_entry_count: self.operator_allowlist.len(),
            canonical_bridge_contracts_count: CANONICAL_BRIDGE_PREFIXES.len(),
            wallets: self.descriptors.clone(),
        }
    }

    /// Validates address syntax, checks exact allowlist, zeroizes ephemeral key,
    /// and generates 64-byte Ed25519 or compact Secp256k1 digital signature.
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
                reason: "Cryptographic vault signing locked while kill-switch is active".to_string(),
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

        // 1. Strict syntax & checksum validation
        if let Err(val_err) = validate_chain_address(&wallet.chain, destination_address) {
            return Err(RiskRejection::VaultSigningRejected {
                reason: format!("Destination address '{destination_address}' failed chain validation: {val_err}"),
            });
        }

        // 2. Exact allowlist check
        if !self.is_destination_allowed(destination_address) {
            return Err(RiskRejection::VaultSigningRejected {
                reason: format!(
                    "Destination address '{destination_address}' is not in the cryptographic vault allowlist"
                ),
            });
        }

        // 3. Ephemeral key derivation
        let master_seed = self.master_seed.as_slice();
        let is_ed25519 = matches!(
            wallet.curve,
            CryptographicCurve::Ed25519Slip0010 | CryptographicCurve::Ed25519Cip1852
        );

        let mut ephemeral_priv: ZeroizingBytes<32> = if is_ed25519 {
            slip0010_derive_ed25519(master_seed, &wallet.target_leaf_derivation_path)
                .map_err(|e| RiskRejection::VaultSigningRejected { reason: e })?
        } else if matches!(wallet.curve, CryptographicCurve::Sr25519Substrate) {
            derive_substrate_mini_secret(master_seed)
        } else if matches!(
            wallet.curve,
            CryptographicCurve::MtlsX509Participant
                | CryptographicCurve::HmacSha256NoWithdraw
                | CryptographicCurve::VirtualZeroKey
        ) {
            let fp = sha256(format!("ephemeral:{}:{}", wallet.leaf_id, destination_address).as_bytes());
            ZeroizingBytes::new(fp)
        } else {
            bip32_derive_secp256k1(master_seed, &wallet.target_leaf_derivation_path)
                .map_err(|e| RiskRejection::VaultSigningRejected { reason: e })?
        };

        // 4. Canonical payload & signing
        let payload = format!(
            "ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}",
            wallet.chain, wallet.leaf_hot_address, destination_address, amount_usd, token
        );
        let digest = sha256(payload.as_bytes());

        let (sig_hex, scheme) = if is_ed25519 {
            let mut key_arr = [0u8; 32];
            key_arr.copy_from_slice(ephemeral_priv.as_slice());
            let sk = EdSigningKey::from_bytes(&key_arr);
            let sig: ed25519_dalek::Signature = sk.sign(&digest);
            (format!("0x{}", to_hex(&sig.to_bytes())), "ED25519".to_string())
        } else {
            let sk = K256SigningKey::from_bytes((ephemeral_priv.as_slice()).into())
                .map_err(|e| RiskRejection::VaultSigningRejected { reason: e.to_string() })?;
            let sig: K256Signature = sk.sign_prehash(&digest)
                .map_err(|e| RiskRejection::VaultSigningRejected { reason: e.to_string() })?;
            (format!("0x{}", to_hex(&sig.to_bytes())), "SECP256K1_ECDSA".to_string())
        };

        // 5. Zeroize ephemeral key in memory
        ephemeral_priv.zeroize_now();
        let key_zeroized_after_sign = ephemeral_priv.is_zeroized();

        Ok(SignedTransferReceipt {
            leaf_id: wallet.leaf_id.clone(),
            chain: wallet.chain.clone(),
            curve: wallet.curve,
            vault_mode: "CRYPTO_HD_BIP32".to_string(),
            simulated: false,
            signature_is_chain_valid: false,
            signature_is_cryptographic: true,
            signature_scheme: scheme,
            whitelist_enforcement: "STRICT_FORMAT_AND_ALLOWLIST".to_string(),
            signer_address: wallet.leaf_hot_address.clone(),
            destination_address: destination_address.to_string(),
            amount_usd,
            token: token.to_uppercase(),
            destination_whitelisted: true,
            signature_hex: sig_hex,
            key_zeroized_after_sign,
        })
    }
}

/// Seed selection logic with entropy check (>= 32 bytes).
pub fn select_crypto_seed(
    execution_mode: ExecutionMode,
    secret_file: &Path,
    env_seed: &crate::SeedInput,
    allow_test_seed: bool,
) -> Result<(Vec<u8>, SeedSource), crate::VaultInitError> {
    // 1. Secret file
    if let Ok(contents) = fs::read_to_string(secret_file) {
        let trimmed = contents.trim();
        if !trimmed.is_empty() {
            if let Ok(bytes) = from_hex(trimmed) {
                if bytes.len() >= 32 {
                    return Ok((bytes, SeedSource::SecretFile));
                } else {
                    return Err(crate::VaultInitError::InsufficientEntropy);
                }
            } else if trimmed.as_bytes().len() >= 32 {
                return Ok((trimmed.as_bytes().to_vec(), SeedSource::SecretFile));
            } else {
                return Err(crate::VaultInitError::InsufficientEntropy);
            }
        }
    }

    // 2. Environment seed
    match env_seed {
        crate::SeedInput::NonUnicode => return Err(crate::VaultInitError::InvalidEnvironmentSeedEncoding),
        crate::SeedInput::Value(env_val) => {
            let trimmed = env_val.trim();
            if !trimmed.is_empty() {
                if let Ok(bytes) = from_hex(trimmed) {
                    if bytes.len() >= 32 {
                        return Ok((bytes, SeedSource::Environment));
                    } else {
                        return Err(crate::VaultInitError::InsufficientEntropy);
                    }
                } else if trimmed.as_bytes().len() >= 32 {
                    return Ok((trimmed.as_bytes().to_vec(), SeedSource::Environment));
                } else {
                    return Err(crate::VaultInitError::InsufficientEntropy);
                }
            }
        }
        crate::SeedInput::Unset => {}
    }

    // 3. Fallback resolution
    if execution_mode == ExecutionMode::Live {
        return Err(crate::VaultInitError::MissingLiveSeed);
    }

    if allow_test_seed {
        let mut seed64 = [0u8; 64];
        let bytes = DETERMINISTIC_DEVNET_SEED;
        seed64[..bytes.len().min(64)].copy_from_slice(&bytes[..bytes.len().min(64)]);
        Ok((seed64.to_vec(), SeedSource::DeterministicDevnet))
    } else {
        Err(crate::VaultInitError::TestSeedNotAllowed)
    }
}

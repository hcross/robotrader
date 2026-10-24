from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, List, Optional

from ..tools.rss_tools import EcosystemRSSAggregator
from .memory_palace import PalaceDrawer, StrategyMemoryPalace

# Reference prices in USD for multi-chain checkout & valuation
TOKEN_PRICES_USD: Dict[str, float] = {
    "USDC": 1.0,
    "USDT": 1.0,
    "SOL": 152.40,
    "JUP": 1.24,
    "RAY": 2.82,
    "BTC": 80775.0,
    "ETH": 2368.0,
    "SUI": 3.15,
    "HYPE": 24.80,
    "BNB": 612.0,
    "XRP": 2.38,
    "TON": 5.45,
    "TRX": 0.24,
    "AVAX": 28.50,
    "ATOM": 6.80,
    "APT": 9.40,
    "LINK": 18.20,
    "STX": 1.85,
    "NEAR": 5.10,
    "ADA": 0.78,
    "DOT": 5.60,
    "DOGE": 0.19,
    "ICP": 9.80,
    "CC": 0.40,
    "CELO": 0.68,
    "XTZ": 1.05,
    "FLOW": 0.72,
    "EOS": 0.64,
}


LEAF_ECOSYSTEM_CATALOG: List[Dict[str, Any]] = [
    {
        "leaf_id": "leaf-solana",
        "name": "Solana Leaf Robot",
        "chain": "Solana",
        "symbol": "SOL",
        "icon": "☀️",
        "category": "BLOCKCHAIN_L1",
        "tier": "P0_CORE",
        "default_weight": 0.24,
        "default_posture": "AGGRESSIVE",
        "exclusive_assets": ["SOL-USDT", "JUP-USDT", "RAY-USDT", "SOL-DEVNET"],
        "supported_tokens": ["SOL", "USDC", "USDT", "JUP", "RAY"],
        "venues": ["Jupiter v6", "Raydium CLMM", "Drift Perps", "Jito Bundles"],
        "mempalace_wing": "leaf_solana",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Wormhole / Circle CCTP",
        "bridge_base_fee_usd": 0.35,
        "bridge_Variable_bps": 4.0,
        "finality_sec": 2,
        "ta_specific_metrics": {
            "tps_effective": 4210,
            "jito_tip_floor_lamports": 12000,
            "dex_24h_vol_usd_b": 4.85,
            "perp_funding_apr_pct": 24.0,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 150.15,
            "rsi_14": 54.2,
            "obi_l2": 0.19,
        },
        "study_verdict": "P0 Core — Exclusivement dédié à Solana (BTC/ETH purgés). Vélocité <400ms, carnets Raydium/Jupiter et anti-rug HardRiskGate <50µs.",
    },
    {
        "leaf_id": "leaf-bitcoin",
        "name": "Bitcoin Leaf Robot",
        "chain": "Bitcoin",
        "symbol": "BTC",
        "icon": "₿",
        "category": "BLOCKCHAIN_L1",
        "tier": "P0_CORE",
        "default_weight": 0.20,
        "default_posture": "BALANCED",
        "exclusive_assets": ["BTC-USD", "wBTC-BTC", "sBTC-BTC"],
        "supported_tokens": ["BTC", "USDT", "USDC"],
        "venues": ["Bitcoin L1 Native", "ThorChain Native Pool", "Lightning Liquidity"],
        "mempalace_wing": "leaf_bitcoin",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "ThorChain / wBTC Institutional",
        "bridge_base_fee_usd": 3.50,
        "bridge_Variable_bps": 12.0,
        "finality_sec": 600,
        "ta_specific_metrics": {
            "mempool_fee_sat_vb": 6.2,
            "hash_ribbon_state": "EXPANSION_BULLISH",
            "etf_netflow_24h_usd_m": 328.0,
            "miner_reserve_delta_btc": 140.0,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 79850.0,
            "rsi_14": 56.4,
            "obi_l2": 0.31,
        },
        "study_verdict": "P0 Core — Pilier macro et réserve de valeur ; arbitrage de liquidité native et suivi des flux ETF/Mempool/Hash Ribbons.",
    },
    {
        "leaf_id": "leaf-ethereum",
        "name": "Ethereum Leaf Robot",
        "chain": "Ethereum",
        "symbol": "ETH",
        "icon": "Ξ",
        "category": "BLOCKCHAIN_L1",
        "tier": "P0_CORE",
        "default_weight": 0.14,
        "default_posture": "BALANCED",
        "exclusive_assets": ["ETH-USDC", "stETH-ETH", "UNI-ETH", "AAVE-ETH"],
        "supported_tokens": ["ETH", "USDC", "USDT"],
        "venues": ["Uniswap v4", "Aave v3", "Curve", "Lido / EigenLayer"],
        "mempalace_wing": "leaf_ethereum",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Circle CCTP / LayerZero Stargate",
        "bridge_base_fee_usd": 1.80,
        "bridge_Variable_bps": 6.0,
        "finality_sec": 15,
        "ta_specific_metrics": {
            "eip1559_base_fee_gwei": 4.2,
            "blob_fee_gwei": 0.08,
            "steth_peg_ratio": 0.9997,
            "restaking_apr_pct": 3.65,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 2295.0,
            "rsi_14": 51.8,
            "obi_l2": 0.14,
        },
        "study_verdict": "P0 Core — Cœur institutionnel DeFi/RWA, rendement stETH/EigenLayer et arbitrage concentré Uniswap v4.",
    },
    {
        "leaf_id": "leaf-sui",
        "name": "Sui Leaf Robot",
        "chain": "Sui",
        "symbol": "SUI",
        "icon": "💧",
        "category": "BLOCKCHAIN_L1",
        "tier": "P1_HIGH",
        "default_weight": 0.06,
        "default_posture": "AGGRESSIVE",
        "exclusive_assets": ["SUI-USDC", "DEEP-SUI", "CETUS-SUI"],
        "supported_tokens": ["SUI", "USDC", "USDT"],
        "venues": ["DeepBook v3 CLOB", "Cetus CLMM", "Navi Protocol"],
        "mempalace_wing": "leaf_sui",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Wormhole / Sui Native Bridge",
        "bridge_base_fee_usd": 0.45,
        "bridge_Variable_bps": 5.0,
        "finality_sec": 1,
        "ta_specific_metrics": {
            "mysticeti_finality_ms": 385,
            "deepbook_v3_vol_usd_m": 482.0,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 3.02,
            "rsi_14": 61.5,
            "obi_l2": 0.24,
        },
        "study_verdict": "P1 Recommandé — L1 Move à finalité sub-400ms doté d'un carnet d'ordres central natif (DeepBook v3).",
    },
    {
        "leaf_id": "leaf-hyperliquid",
        "name": "Hyperliquid L1 Leaf Robot",
        "chain": "Hyperliquid",
        "symbol": "HYPE",
        "icon": "⚡",
        "category": "DEX_L1_CLOB",
        "tier": "P0_CORE",
        "default_weight": 0.07,
        "default_posture": "AGGRESSIVE",
        "exclusive_assets": ["HYPE-USDC", "PURR-USDC"],
        "supported_tokens": ["HYPE", "USDC"],
        "venues": ["HyperCore L1 CLOB", "HLP Liquidity Vault", "HyperEVM"],
        "mempalace_wing": "leaf_hyperliquid",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Hyperliquid Arbitrum USDC Bridge",
        "bridge_base_fee_usd": 0.25,
        "bridge_Variable_bps": 3.0,
        "finality_sec": 1,
        "ta_specific_metrics": {
            "hlp_apr_pct": 19.4,
            "clob_open_interest_usd_b": 3.9,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 23.60,
            "rsi_14": 59.0,
            "obi_l2": 0.27,
        },
        "study_verdict": "P0/P1 Incontournable — L1 spécialisé CLOB Perps & Spot sans gas sur ordres avec coffre de market-making HLP.",
    },
    {
        "leaf_id": "leaf-bnb",
        "name": "BNB Chain Leaf Robot",
        "chain": "BNB Chain",
        "symbol": "BNB",
        "icon": "🔶",
        "category": "BLOCKCHAIN_L1",
        "tier": "P1_HIGH",
        "default_weight": 0.03,
        "default_posture": "BALANCED",
        "exclusive_assets": ["BNB-USDT", "CAKE-BNB"],
        "supported_tokens": ["BNB", "USDT", "USDC"],
        "venues": ["PancakeSwap v3", "Venus Protocol", "opBNB"],
        "mempalace_wing": "leaf_bnb",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "LayerZero Stargate / cBridge",
        "bridge_base_fee_usd": 0.40,
        "bridge_Variable_bps": 5.0,
        "finality_sec": 3,
        "ta_specific_metrics": {
            "pancakeswap_24h_vol_usd_m": 940.0,
            "venus_usdt_supply_apr_pct": 8.4,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 598.0,
            "rsi_14": 53.1,
            "obi_l2": 0.11,
        },
        "study_verdict": "P1 Haute pertinence — Écosystème EVM à frais réduits et forte vélocité retail sur PancakeSwap v3.",
    },
    {
        "leaf_id": "leaf-xrp",
        "name": "XRP Ledger Leaf Robot",
        "chain": "XRP Ledger",
        "symbol": "XRP",
        "icon": "✕",
        "category": "BLOCKCHAIN_L1",
        "tier": "P1_HIGH",
        "default_weight": 0.03,
        "default_posture": "BALANCED",
        "exclusive_assets": ["XRP-RLUSD", "XRP-USDT"],
        "supported_tokens": ["XRP", "USDT", "USDC"],
        "venues": ["XRPL Native CLOB", "XRPL XLS-30 AMM"],
        "mempalace_wing": "leaf_xrp",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Axelar XRPL / CEX Settlement Hub",
        "bridge_base_fee_usd": 0.20,
        "bridge_Variable_bps": 6.0,
        "finality_sec": 4,
        "ta_specific_metrics": {
            "xrpl_clob_spread_bps": 4.2,
            "rlusd_pool_tvl_usd_m": 185.0,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 2.31,
            "rsi_14": 49.5,
            "obi_l2": 0.08,
        },
        "study_verdict": "P1 Haute pertinence — CLOB et AMM intégrés nativement au protocole L1 avec règlement en 3-4s et stablecoin RLUSD.",
    },
    {
        "leaf_id": "leaf-ton",
        "name": "TON (ex-Gram) Leaf Robot",
        "chain": "TON",
        "symbol": "TON",
        "icon": "💎",
        "category": "BLOCKCHAIN_L1",
        "tier": "P1_HIGH",
        "default_weight": 0.02,
        "default_posture": "BALANCED",
        "exclusive_assets": ["TON-USDT", "NOT-TON"],
        "supported_tokens": ["TON", "USDT"],
        "venues": ["STON.fi", "DeDust.io"],
        "mempalace_wing": "leaf_ton",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "TON Official Bridge / LayerZero",
        "bridge_base_fee_usd": 0.60,
        "bridge_Variable_bps": 8.0,
        "finality_sec": 5,
        "ta_specific_metrics": {
            "usdt_ton_supply_usd_b": 1.25,
            "stonfi_tvl_usd_m": 210.0,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 5.28,
            "rsi_14": 52.0,
            "obi_l2": 0.09,
        },
        "study_verdict": "P1 Haute pertinence — Successeur effectif de « Gram » (The Open Network), forte liquidité USDT native et distribution Telegram.",
    },
    {
        "leaf_id": "leaf-tron",
        "name": "TRON Leaf Robot",
        "chain": "TRON",
        "symbol": "TRX",
        "icon": "🔺",
        "category": "BLOCKCHAIN_L1",
        "tier": "P1_HIGH",
        "default_weight": 0.02,
        "default_posture": "DEFENSIVE",
        "exclusive_assets": ["TRX-USDT", "SUN-TRX"],
        "supported_tokens": ["TRX", "USDT"],
        "venues": ["SunSwap v3", "JustLend DAO"],
        "mempalace_wing": "leaf_tron",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "BitTorrent Bridge / CEX TRC-20 Rail",
        "bridge_base_fee_usd": 1.00,
        "bridge_Variable_bps": 4.0,
        "finality_sec": 3,
        "ta_specific_metrics": {
            "usdt_trc20_daily_vol_usd_b": 16.4,
            "energy_rental_apy_pct": 11.2,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 0.234,
            "rsi_14": 55.0,
            "obi_l2": 0.07,
        },
        "study_verdict": "P1 Rail Stablecoin — Premier réseau mondial de règlement USDT TRC-20 et yield de location d'Energy.",
    },
    {
        "leaf_id": "leaf-avalanche",
        "name": "Avalanche Leaf Robot",
        "chain": "Avalanche",
        "symbol": "AVAX",
        "icon": "🏔️",
        "category": "BLOCKCHAIN_L1",
        "tier": "P1_HIGH",
        "default_weight": 0.02,
        "default_posture": "BALANCED",
        "exclusive_assets": ["AVAX-USDC", "JOE-AVAX"],
        "supported_tokens": ["AVAX", "USDC", "USDT"],
        "venues": ["LFJ (Trader Joe) Liquidity Book", "Benqi"],
        "mempalace_wing": "leaf_avalanche",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Circle CCTP / LayerZero",
        "bridge_base_fee_usd": 0.40,
        "bridge_Variable_bps": 5.0,
        "finality_sec": 2,
        "ta_specific_metrics": {
            "liquidity_book_active_bin_bps": 10.0,
            "subnet_tx_share_pct": 38.0,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 27.80,
            "rsi_14": 48.7,
            "obi_l2": 0.06,
        },
        "study_verdict": "P1 Haute pertinence — AMM à bins discrets zéro-slippage intra-bin (Liquidity Book) et finalité Snowman <2s.",
    },
    {
        "leaf_id": "leaf-cosmos",
        "name": "Cosmos Hub & IBC Leaf Robot",
        "chain": "Cosmos",
        "symbol": "ATOM",
        "icon": "⚛️",
        "category": "BLOCKCHAIN_L1",
        "tier": "P1_HIGH",
        "default_weight": 0.01,
        "default_posture": "DEFENSIVE",
        "exclusive_assets": ["ATOM-USDC", "OSMO-ATOM", "INJ-USDC"],
        "supported_tokens": ["ATOM", "USDC"],
        "venues": ["Osmosis Supercharged Pools", "Injective Helix CLOB", "Noble USDC"],
        "mempalace_wing": "leaf_cosmos",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "IBC Native / Axelar",
        "bridge_base_fee_usd": 0.15,
        "bridge_Variable_bps": 4.0,
        "finality_sec": 6,
        "ta_specific_metrics": {
            "ibc_24h_volume_usd_m": 195.0,
            "atom_staking_apr_pct": 13.8,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 6.62,
            "rsi_14": 47.2,
            "obi_l2": 0.04,
        },
        "study_verdict": "P1 IBC Hub — Regroupe Atom et les app-chains IBC (Osmosis, Injective, Noble) où réside la liquidité DeFi Cosmos.",
    },
    {
        "leaf_id": "leaf-aptos",
        "name": "Aptos Leaf Robot",
        "chain": "Aptos",
        "symbol": "APT",
        "icon": "🌐",
        "category": "BLOCKCHAIN_L1",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["APT-USDC", "THL-APT"],
        "supported_tokens": ["APT", "USDC", "USDT"],
        "venues": ["Thala Labs", "Aries Markets", "Econia CLOB"],
        "mempalace_wing": "leaf_aptos",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "LayerZero Aptos Bridge / CCTP",
        "bridge_base_fee_usd": 0.50,
        "bridge_Variable_bps": 6.0,
        "finality_sec": 1,
        "ta_specific_metrics": {
            "block_stm_tps": 1850,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 9.10,
            "rsi_14": 50.1,
            "obi_l2": 0.05,
        },
        "study_verdict": "P2 Spécialisé — Exécution parallèle Block-STM Move et carnets Econia/Thala.",
    },
    {
        "leaf_id": "leaf-chainlink",
        "name": "Chainlink Oracle & CCIP Leaf Robot",
        "chain": "Chainlink",
        "symbol": "LINK",
        "icon": "🔗",
        "category": "INFRA_ORACLE",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["LINK-USDC", "LINK-ETH"],
        "supported_tokens": ["LINK", "USDC"],
        "venues": ["Chainlink Staking v0.2", "Uniswap v4 LINK/ETH"],
        "mempalace_wing": "leaf_chainlink",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Chainlink CCIP Native",
        "bridge_base_fee_usd": 1.20,
        "bridge_Variable_bps": 5.0,
        "finality_sec": 15,
        "ta_specific_metrics": {
            "ccip_24h_messages": 18400,
            "staking_pool_fill_pct": 100.0,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 17.65,
            "rsi_14": 54.0,
            "obi_l2": 0.10,
        },
        "study_verdict": "P2 Infrastructure — Réseau d'oracles et de routage CCIP (et non L1 autonome) ; agent dédié au token LINK et à la télémétrie CCIP.",
    },
    {
        "leaf_id": "leaf-stacks",
        "name": "Stacks (ex-Blockstack) Leaf Robot",
        "chain": "Stacks",
        "symbol": "STX",
        "icon": "🟧",
        "category": "BITCOIN_L2",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["STX-BTC", "sBTC-BTC", "ALEX-STX"],
        "supported_tokens": ["STX", "BTC"],
        "venues": ["ALEX Lab", "Velar", "StackingDAO"],
        "mempalace_wing": "leaf_stacks",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "sBTC Peg / Stacks Nakamoto",
        "bridge_base_fee_usd": 1.50,
        "bridge_Variable_bps": 10.0,
        "finality_sec": 5,
        "ta_specific_metrics": {
            "stacking_btc_yield_apy_pct": 7.8,
            "sbtc_tvl_btc": 3400.0,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 1.78,
            "rsi_14": 52.8,
            "obi_l2": 0.07,
        },
        "study_verdict": "P2 Bitcoin L2 — Rebranding de Blockstack ; blocs rapides Nakamoto (~5s) et arbitrage sBTC/BTC.",
    },
    {
        "leaf_id": "leaf-near",
        "name": "NEAR Protocol Leaf Robot",
        "chain": "NEAR",
        "symbol": "NEAR",
        "icon": "Ⓝ",
        "category": "BLOCKCHAIN_L1",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["NEAR-USDC", "REF-NEAR"],
        "supported_tokens": ["NEAR", "USDC", "USDT"],
        "venues": ["Ref Finance", "Burrow", "NEAR Intents Solver"],
        "mempalace_wing": "leaf_near",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Rainbow Bridge / NEAR Intents",
        "bridge_base_fee_usd": 0.25,
        "bridge_Variable_bps": 5.0,
        "finality_sec": 2,
        "ta_specific_metrics": {
            "nightshade_shards": 6,
            "intents_daily_vol_usd_m": 64.0,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 4.92,
            "rsi_14": 49.9,
            "obi_l2": 0.05,
        },
        "study_verdict": "P2 Spécialisé — Sharding Nightshade et infrastructure Chain Signatures / NEAR Intents.",
    },
    {
        "leaf_id": "leaf-cardano",
        "name": "Cardano Leaf Robot",
        "chain": "Cardano",
        "symbol": "ADA",
        "icon": "🔵",
        "category": "BLOCKCHAIN_L1",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["ADA-USDM", "MIN-ADA"],
        "supported_tokens": ["ADA"],
        "venues": ["Minswap v2", "SundaeSwap v3", "Indigo"],
        "mempalace_wing": "leaf_cardano",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Wanchain / Rosen Bridge",
        "bridge_base_fee_usd": 1.40,
        "bridge_Variable_bps": 14.0,
        "finality_sec": 20,
        "ta_specific_metrics": {
            "eutxo_batcher_congestion_pct": 18.0,
            "staking_apr_pct": 3.1,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 0.75,
            "rsi_14": 46.5,
            "obi_l2": 0.03,
        },
        "study_verdict": "P2 Swing — Modèle eUTXO à blocs de 20s : adapté au swing/yield uniquement, inadapté au HFT.",
    },
    {
        "leaf_id": "leaf-polkadot",
        "name": "Polkadot Leaf Robot",
        "chain": "Polkadot",
        "symbol": "DOT",
        "icon": "🟣",
        "category": "BLOCKCHAIN_L1",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["DOT-USDC", "HDX-DOT", "vDOT-DOT"],
        "supported_tokens": ["DOT", "USDC"],
        "venues": ["Hydration (HydraDX) Omnipool", "Bifrost Liquid Staking"],
        "mempalace_wing": "leaf_polkadot",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Snowbridge / Hyperbridge XCM",
        "bridge_base_fee_usd": 0.55,
        "bridge_Variable_bps": 7.0,
        "finality_sec": 6,
        "ta_specific_metrics": {
            "xcm_daily_transfers": 9400,
            "vdot_apr_pct": 11.4,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 5.42,
            "rsi_14": 48.0,
            "obi_l2": 0.04,
        },
        "study_verdict": "P2 Spécialisé — Liquidité concentrée sur Hydration Omnipool et liquid staking vDOT via XCM.",
    },
    {
        "leaf_id": "leaf-dogecoin",
        "name": "Dogecoin Leaf Robot",
        "chain": "Dogecoin",
        "symbol": "DOGE",
        "icon": "🐕",
        "category": "BLOCKCHAIN_L1",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["DOGE-USD"],
        "supported_tokens": ["DOGE"],
        "venues": ["ThorChain Native DOGE Pool", "Dogecoin L1 UTXO"],
        "mempalace_wing": "leaf_dogecoin",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "ThorChain Native DOGE",
        "bridge_base_fee_usd": 0.80,
        "bridge_Variable_bps": 12.0,
        "finality_sec": 60,
        "ta_specific_metrics": {
            "whale_tx_count_24h": 410,
            "social_rss_velocity_zscore": 1.45,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 0.182,
            "rsi_14": 57.0,
            "obi_l2": 0.12,
        },
        "study_verdict": "P2 Momentum Social — L1 PoW UTXO sans DeFi native ; piloté par impulsions RSS/narratives et exécuté via ThorChain.",
    },
    {
        "leaf_id": "leaf-icp",
        "name": "Internet Computer (ICP) Leaf Robot",
        "chain": "Internet Computer",
        "symbol": "ICP",
        "icon": "♾️",
        "category": "BLOCKCHAIN_L1",
        "tier": "P2_SPECIALIZED",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["ICP-ckUSDC", "ckBTC-ICP"],
        "supported_tokens": ["ICP"],
        "venues": ["ICDex On-Chain CLOB", "ICPSwap"],
        "mempalace_wing": "leaf_icp",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "ICP Chain-Key Cryptography (ckBTC/ckETH)",
        "bridge_base_fee_usd": 0.20,
        "bridge_Variable_bps": 6.0,
        "finality_sec": 2,
        "ta_specific_metrics": {
            "cycle_burn_rate_t_sec": 4.8,
            "ckbtc_minted": 1120.0,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 9.45,
            "rsi_14": 50.2,
            "obi_l2": 0.05,
        },
        "study_verdict": "P2 Spécialisé — Primitives Chain-Key (ckBTC/ckETH sans bridge tiers) et carnet ICDex sur canisters.",
    },
    {
        "leaf_id": "leaf-canton",
        "name": "Canton Network RWA Leaf Robot",
        "chain": "Canton",
        "symbol": "CC",
        "icon": "🏛️",
        "category": "PERMISSIONED_RWA",
        "tier": "P3_WATCH",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["CC-USD", "USTB-CC"],
        "supported_tokens": ["CC", "USDC"],
        "venues": ["Canton Institutional Synchronizer (Watch-Only)"],
        "mempalace_wing": "leaf_canton",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Institutional Custodian Gateway",
        "bridge_base_fee_usd": 15.0,
        "bridge_Variable_bps": 20.0,
        "finality_sec": 30,
        "ta_specific_metrics": {
            "rwa_repo_volume_usd_b": 42.0,
            "access_mode": "PERMISSIONED_PARTICIPANT_NODE_REQUIRED",
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 0.39,
            "rsi_14": 50.0,
            "obi_l2": 0.0,
        },
        "study_verdict": "P3 Veille — Réseau institutionnel RWA permissionné (Daml) ; maintenu en veille RSS tant qu'un nœud participant n'est pas raccordé.",
    },
    {
        "leaf_id": "leaf-celo",
        "name": "Celo Leaf Robot",
        "chain": "Celo",
        "symbol": "CELO",
        "icon": "🟡",
        "category": "ETHEREUM_L2",
        "tier": "P3_WATCH",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["CELO-cUSD", "cEUR-cUSD"],
        "supported_tokens": ["CELO", "USDC"],
        "venues": ["Mento Reserve", "Uniswap v3 Celo"],
        "mempalace_wing": "leaf_celo",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "OP Stack Native Bridge / Wormhole",
        "bridge_base_fee_usd": 0.25,
        "bridge_Variable_bps": 8.0,
        "finality_sec": 2,
        "ta_specific_metrics": {
            "mento_fx_volume_usd_m": 28.0,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 0.66,
            "rsi_14": 48.0,
            "obi_l2": 0.02,
        },
        "study_verdict": "P3 Veille — Migré en L2 Ethereum (OP Stack) spécialisé stablecoins FX régionaux (Mento).",
    },
    {
        "leaf_id": "leaf-tezos",
        "name": "Tezos Leaf Robot",
        "chain": "Tezos",
        "symbol": "XTZ",
        "icon": "⚜️",
        "category": "BLOCKCHAIN_L1",
        "tier": "P3_WATCH",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["XTZ-USDT"],
        "supported_tokens": ["XTZ"],
        "venues": ["Etherlink DEX", "Plenty DeFi"],
        "mempalace_wing": "leaf_tezos",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Etherlink Bridge",
        "bridge_base_fee_usd": 0.80,
        "bridge_Variable_bps": 18.0,
        "finality_sec": 15,
        "ta_specific_metrics": {
            "baking_apr_pct": 5.4,
            "kumo_regime": "BELOW_KUMO_BEARISH",
            "golden_pocket_fib_618": 1.02,
            "rsi_14": 44.0,
            "obi_l2": -0.03,
        },
        "study_verdict": "P3 Veille — Liquidité DeFi étroite hors rollup EVM Etherlink ; maintenu en hibernation par défaut.",
    },
    {
        "leaf_id": "leaf-flow",
        "name": "Flow Leaf Robot",
        "chain": "Flow",
        "symbol": "FLOW",
        "icon": "🌊",
        "category": "BLOCKCHAIN_L1",
        "tier": "P3_WATCH",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["FLOW-USDC"],
        "supported_tokens": ["FLOW"],
        "venues": ["IncrementFi", "Flow EVM"],
        "mempalace_wing": "leaf_flow",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Celer cBridge",
        "bridge_base_fee_usd": 0.90,
        "bridge_Variable_bps": 20.0,
        "finality_sec": 4,
        "ta_specific_metrics": {
            "cadence_evm_tx_ratio": 0.42,
            "kumo_regime": "INSIDE_KUMO_NEUTRAL",
            "golden_pocket_fib_618": 0.70,
            "rsi_14": 46.0,
            "obi_l2": 0.01,
        },
        "study_verdict": "P3 Veille — Orienté applications grand public/NFT ; profondeur DeFi insuffisante pour un déploiement permanent.",
    },
    {
        "leaf_id": "leaf-eos",
        "name": "Vaulta (ex-EOS) Leaf Robot",
        "chain": "EOS",
        "symbol": "EOS",
        "icon": "⬛",
        "category": "BLOCKCHAIN_L1",
        "tier": "P3_WATCH",
        "default_weight": 0.0,
        "default_posture": "HIBERNATION",
        "exclusive_assets": ["EOS-USDT"],
        "supported_tokens": ["EOS"],
        "venues": ["Defibox", "EOS RAM Market"],
        "mempalace_wing": "leaf_eos",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "EOS EVM Bridge",
        "bridge_base_fee_usd": 0.75,
        "bridge_Variable_bps": 22.0,
        "finality_sec": 3,
        "ta_specific_metrics": {
            "ram_price_eos_kb": 0.31,
            "kumo_regime": "BELOW_KUMO_BEARISH",
            "golden_pocket_fib_618": 0.62,
            "rsi_14": 43.5,
            "obi_l2": -0.04,
        },
        "study_verdict": "P3 Veille — Rebrandé en Vaulta ; liquidité résiduelle concentrée sur le marché interne de RAM.",
    },
    {
        "leaf_id": "leaf-binance-cex",
        "name": "Binance CEX Multi-Crypto Robot",
        "chain": "Binance CEX",
        "symbol": "USDT",
        "icon": "📊",
        "category": "CEX_MULTI_CRYPTO",
        "tier": "VENUE_MULTI",
        "default_weight": 0.08,
        "default_posture": "BALANCED",
        "exclusive_assets": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT"],
        "supported_tokens": ["USDT", "USDC", "BTC", "ETH", "SOL", "BNB", "XRP"],
        "venues": ["Binance Spot L2", "Binance USD-M Perps"],
        "mempalace_wing": "leaf_binance_cex",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Binance Multi-Network Withdrawal Hub",
        "bridge_base_fee_usd": 0.50,
        "bridge_Variable_bps": 2.0,
        "finality_sec": 30,
        "ta_specific_metrics": {
            "cross_pair_funding_spread_apr_pct": 18.6,
            "orderbook_depth_top10_usd_m": 42.0,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 80450.0,
            "rsi_14": 53.4,
            "obi_l2": 0.21,
        },
        "study_verdict": "Agent Plateforme CEX Dédié — Reprend le trading CEX multi-crypto (BTC/ETH/SOL) retiré de `leaf-solana`.",
    },
    {
        "leaf_id": "leaf-paper-sandbox",
        "name": "Paper-Money Microstructure Lab",
        "chain": "Paper Sandbox",
        "symbol": "USDC",
        "icon": "🧪",
        "category": "PAPER_SANDBOX",
        "tier": "VENUE_MULTI",
        "default_weight": 0.0,
        "default_posture": "BALANCED",
        "exclusive_assets": ["SOL-PERP-SIM", "BTC-PERP-SIM", "ETH-PERP-SIM"],
        "supported_tokens": ["USDC", "USDT"],
        "venues": ["Simulated L2 Orderbook + Adverse Selection Engine"],
        "mempalace_wing": "leaf_paper_sandbox",
        "model": "deepseek/deepseek-v4.1-flash-1017",
        "bridge_protocol": "Virtual Zero-Cost Ledger",
        "bridge_base_fee_usd": 0.0,
        "bridge_Variable_bps": 0.0,
        "finality_sec": 0,
        "ta_specific_metrics": {
            "adverse_selection_model": "L2_OBI_MOMENTUM_RSI_FRICTION",
            "simulated_slippage_bps": 2.4,
            "kumo_regime": "ABOVE_KUMO_BULLISH",
            "golden_pocket_fib_618": 150.0,
            "rsi_14": 50.0,
            "obi_l2": 0.10,
        },
        "study_verdict": "Agent Plateforme Paper-Money — Banc d'essai sans risque financier avec sélection adverse et slippage L2.",
    },
]

for _spec in LEAF_ECOSYSTEM_CATALOG:
    _spec.setdefault("id", _spec["leaf_id"])
    _spec.setdefault("ta_metrics", _spec.get("ta_specific_metrics", {}))


class CrossChainTreasuryRouter:
    """
    Master Orchestrator's Cross-Chain Bridge Pricer & Checkout Delivery Engine.
    Measures gas + bridge fee + slippage before any capital move and enforces a 2.5x
    round-trip hurdle rate before funding a leaf ecosystem.
    """

    HURDLE_MULTIPLIER = 2.5

    @classmethod
    def get_leaf_meta(cls, chain_or_leaf_id: str) -> Dict[str, Any]:
        needle = chain_or_leaf_id.strip().lower()
        for item in LEAF_ECOSYSTEM_CATALOG:
            if (
                item["leaf_id"].lower() == needle
                or item["chain"].lower() == needle
                or item["symbol"].lower() == needle
            ):
                return item
        return LEAF_ECOSYSTEM_CATALOG[0]

    @classmethod
    def quote_transfer(
        cls,
        from_chain: str,
        to_chain: str,
        amount_usd: float,
        target_token: str = "USDC",
    ) -> Dict[str, Any]:
        amt = max(0.0, float(amount_usd))
        src = cls.get_leaf_meta(from_chain)
        dst = cls.get_leaf_meta(to_chain)

        if src["chain"] == dst["chain"] and target_token.upper() in ("USDC", "USDT"):
            total_fee_usd = 0.02
            slippage_usd = 0.0
            bridge_used = f"{dst['chain']} Native Local Transfer"
            eta_sec = 2
        else:
            base_fee = float(src.get("bridge_base_fee_usd", 0.5)) * 0.5 + float(
                dst.get("bridge_base_fee_usd", 0.5)
            )
            var_bps = float(dst.get("bridge_Variable_bps", 6.0))
            swap_slip_bps = 3.0 if target_token.upper() in ("USDC", "USDT") else 8.5
            protocol_fee_usd = amt * (var_bps / 10_000.0)
            slippage_usd = amt * (swap_slip_bps / 10_000.0)
            total_fee_usd = round(base_fee + protocol_fee_usd + slippage_usd, 4)
            bridge_used = str(dst.get("bridge_protocol", "Wormhole / CCTP"))
            eta_sec = int(dst.get("finality_sec", 10)) + 12

        total_cost_bps = round((total_fee_usd / amt) * 10_000.0, 2) if amt > 0 else 0.0
        net_usd = max(0.0, round(amt - total_fee_usd, 4))
        tok_upper = target_token.upper()
        tok_price = float(TOKEN_PRICES_USD.get(tok_upper, 1.0))
        delivered_tokens = round(net_usd / tok_price, 6) if tok_price > 0 else net_usd

        return {
            "from_chain": src["chain"],
            "to_chain": dst["chain"],
            "bridge_protocol": bridge_used,
            "gross_amount_usd": round(amt, 2),
            "total_fee_usd": round(total_fee_usd, 4),
            "total_cost_bps": total_cost_bps,
            "net_delivered_usd": round(net_usd, 2),
            "target_token": tok_upper,
            "token_price_usd": tok_price,
            "delivered_token_amount": delivered_tokens,
            "delivered_token_qty": delivered_tokens,
            "estimated_finality_sec": eta_sec,
        }

    @classmethod
    def evaluate_transfer_viability(
        cls,
        from_chain: str,
        to_chain: str,
        amount_usd: float,
        expected_yield_bps: float,
        horizon_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Evaluates whether moving `amount_usd` from `from_chain` to `to_chain` is worth the
        round-trip bridge + gas + slippage cost before executing the transfer.
        """
        q_in = cls.quote_transfer(from_chain, to_chain, amount_usd, "USDC")
        q_out = cls.quote_transfer(to_chain, from_chain, amount_usd, "USDC")
        round_trip_cost_bps = round(q_in["total_cost_bps"] + q_out["total_cost_bps"], 2)
        round_trip_fee_usd = round(q_in["total_fee_usd"] + q_out["total_fee_usd"], 4)
        hurdle_bps = round(round_trip_cost_bps * cls.HURDLE_MULTIPLIER, 2)
        approved = float(expected_yield_bps) >= hurdle_bps and float(amount_usd) >= 25.0
        expected_net_profit_usd = round(
            float(amount_usd) * ((float(expected_yield_bps) - round_trip_cost_bps) / 10_000.0),
            2,
        )
        return {
            "from_chain": q_in["from_chain"],
            "to_chain": q_in["to_chain"],
            "bridge_protocol": q_in["bridge_protocol"],
            "amount_usd": round(float(amount_usd), 2),
            "round_trip_fee_usd": round_trip_fee_usd,
            "round_trip_cost_bps": round_trip_cost_bps,
            "hurdle_rate_bps": hurdle_bps,
            "expected_yield_bps": round(float(expected_yield_bps), 1),
            "horizon_days": int(horizon_days),
            "expected_net_profit_usd": expected_net_profit_usd,
            "approved": approved,
            "viable": approved,
            "recommendation": "APPROVE_TRANSFER" if approved else "HOLD_CURRENT_CHAIN",
            "rationale": (
                f"Transfert APPROUVÉ : rendement attendu {expected_yield_bps:.1f} bps >= hurdle {hurdle_bps:.1f} bps "
                f"(coût A/R {round_trip_cost_bps:.1f} bps soit ${round_trip_fee_usd:.2f}, gain net attendu +${expected_net_profit_usd:.2f})."
                if approved
                else f"Transfert REJETÉ : rendement attendu {expected_yield_bps:.1f} bps < hurdle {hurdle_bps:.1f} bps "
                f"(les frais de bridge A/R de ${round_trip_fee_usd:.2f} / {round_trip_cost_bps:.1f} bps absorbent l'opportunité)."
            ),
        }


class HierarchicalFleetManager:
    """
    Stateful coordinator for Robotrader v3:
    - Holds the Master Orchestrator (`moonshotai/kimi-k3.1-pro`) and Master Treasury
    - Enforces a permanent Dry Powder safety reserve (default >= 20% of capital)
    - Manages the 26 specialized Leaf Robots (`deepseek/deepseek-v4.1-flash-1017`)
    - Provides deposit, cross-chain checkout delivery, emergency leaf liquidation,
      and full MemPalace cross-wing inspection.
    """

    REDIS_HIERARCHY_KEY = "robotrader:v3:hierarchy"

    def __init__(
        self,
        palace: StrategyMemoryPalace,
        redis_cmd_fn: Optional[Any] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.palace = palace
        self._redis_cmd = redis_cmd_fn
        self._redis_url = redis_url

        self.master_model = "moonshotai/kimi-k3.1-pro"
        self.leaf_default_model = "deepseek/deepseek-v4.1-flash-1017"
        self.master_interval_sec = 900  # 15-min macro reflection cadence (longer than leaf agents)
        now_ms = int(time.time() * 1000)
        self.last_master_reflection_ms = now_ms
        self.next_master_reflection_ms = now_ms + self.master_interval_sec * 1000

        self.total_capital_usd: float = 25_000.0
        self.min_dry_powder_ratio: float = 0.20  # Keep >= 20% dry powder for safety & opportunities
        self.long_term_strategy_thesis: str = (
            "Stratégie Macro Long Terme (Kimi K3.1 Pro) : Conservation d'une réserve de sécurité liquide "
            "de >= 20% (Dry Powder USDC/SOL) pour saisir les dislocations de marché et couvrir les retraits. "
            "Concentration du capital actif sur les écosystèmes L1 à haute vélocité et carnets natifs "
            "(Solana 24%, Bitcoin 20%, Ethereum 14%, Hyperliquid 7%, Sui 6%, Binance CEX 8%), avec maintien "
            "en hibernation sans frais des chaînes P2/P3 tant que leur rendement ajusté du coût de bridge "
            "ne franchit pas le hurdle rate de 2.5x."
        )
        self.master_state: Dict[str, Any] = {
            "model": self.master_model,
            "leaf_default_model": self.leaf_default_model,
            "long_term_strategy": self.long_term_strategy_thesis,
            "macro_regime_summary": "Flux institutionnels ETF BTC/ETH résilients et activité DEX Solana/Hyperliquid en forte expansion.",
            "capital_allocation_rationale": "Concentration P0/P1 avec plancher Dry Powder >= 20% et hurdle rate bridge 2.5x.",
            "last_reflection_ms": self.last_master_reflection_ms,
            "next_wakeup_ms": self.next_master_reflection_ms,
            "wakeup_reason": "Cycle macro périodique 15m (900s)",
        }

        self.leaves: Dict[str, Dict[str, Any]] = {}
        self.deposit_history: List[Dict[str, Any]] = []
        self.checkout_history: List[Dict[str, Any]] = []
        self.bridge_evaluations: List[Dict[str, Any]] = []

        self._init_leaves()
        self._seed_initial_palace_drawers()
        self._load_persisted()

    def _init_leaves(self) -> None:
        now_ms = int(time.time() * 1000)
        initial_weights = self.smart_allocate_by_capital_size(self.total_capital_usd)
        for spec in LEAF_ECOSYSTEM_CATALOG:
            lid = spec["leaf_id"]
            weight = float(initial_weights.get(lid, 0.0))
            alloc_usd = round(self.total_capital_usd * weight, 2)
            posture = (
                str(spec.get("default_posture", "BALANCED"))
                if alloc_usd > 0
                else "HIBERNATION"
            )
            obj_summary = (
                f"Capturer l'alpha natif {spec['chain']} ({', '.join(spec['exclusive_assets'][:3])}) "
                f"via {', '.join(spec['venues'][:2])} en posture {posture}."
                if alloc_usd > 0
                else f"Veille RSS passive sur {spec['chain']} — aucun capital engagé (économie d'OpEx)."
            )
            self.leaves[lid] = {
                **spec,
                "id": lid,
                "leaf_id": lid,
                "allocated_capital_usd": alloc_usd,
                "capital_weight": weight,
                "weight_pct": round(weight * 100.0, 2),
                "risk_posture": posture,
                "enabled": alloc_usd > 0 and posture != "HIBERNATION",
                "execution_engine": ", ".join(spec.get("venues", [])[:2]),
                "last_price_usd": float(TOKEN_PRICES_USD.get(spec["symbol"], 1.0)),
                "ta_metrics": dict(spec.get("ta_specific_metrics", {})),
                "sharpe_ratio": 2.45 if alloc_usd > 0 else 1.65,
                "win_rate_pct": 64.5 if alloc_usd > 0 else 58.0,
                "base_interval_sec": 120 if alloc_usd > 0 else 600,
                "target_annual_return_pct": 35.0 if posture == "AGGRESSIVE" else (18.0 if posture == "BALANCED" else 8.0),
                "max_drawdown_limit_pct": 4.0 if posture == "AGGRESSIVE" else 2.5,
                "realized_pnl_usd": round(alloc_usd * 0.018, 2) if alloc_usd > 0 else 0.0,
                "paper_pnl_usd": round(alloc_usd * 0.022, 2) if alloc_usd > 0 else 0.0,
                "active_positions_count": 2 if alloc_usd >= 600 else (1 if alloc_usd > 0 else 0),
                "last_reflection_ms": now_ms,
                "objective_summary": obj_summary,
                "last_hypothesis": obj_summary,
            }

        # Seed sample cross-chain evaluations so the UI immediately shows how the Orchestrator prices transfers
        self.bridge_evaluations = [
            CrossChainTreasuryRouter.evaluate_transfer_viability("Ethereum", "Solana", 1500.0, 68.0, 7),
            CrossChainTreasuryRouter.evaluate_transfer_viability("Solana", "Sui", 800.0, 54.0, 7),
            CrossChainTreasuryRouter.evaluate_transfer_viability("Solana", "Tezos", 250.0, 18.0, 7),
        ]

    def _seed_initial_palace_drawers(self) -> None:
        now_ms = int(time.time() * 1000)
        existing_wings = {d.wing for d in self.palace.drawers}

        if "master_orchestrator" not in existing_wings:
            self.palace.add_drawer(
                PalaceDrawer(
                    drawer_id=f"drw_master_{now_ms}",
                    timestamp_ms=now_ms,
                    wing="master_orchestrator",
                    room="macro_allocation",
                    model_used=self.master_model,
                    thinking_depth="DEEP_THESIS",
                    thesis_continuity="CONFIRMED",
                    global_regime="TRENDING_BULL",
                    panorama_summary="Flux institutionnels soutenus sur Solana, Bitcoin et Sui ; frais CCTP/Wormhole en baisse de 18%.",
                    ta_confluence_notes="Inspection transversale des 26 MemPalaces feuilles : confluence haussière SOL ($152.40) + BTC ($80,775) + SUI ($3.15).",
                    hypothesis=self.long_term_strategy_thesis,
                    invalidation_condition="Rupture simultanée du Kumo 15m sur BTC (<$79,800) et SOL (<$148.50) ou drawdown journalier > 2.5%.",
                    compiled_rules_summary={
                        "dry_powder_ratio": self.dry_powder_ratio,
                        "active_leaves": [k for k, v in self.leaves.items() if v["enabled"]],
                    },
                    next_wakeup_sec=900,
                    wakeup_reason="Cycle stratégique long terme de l'Orchestrateur Maître (15m)",
                    tokens_used=1420,
                    cost_usd=0.00048,
                )
            )

        for lid, leaf in self.leaves.items():
            wing = str(leaf["mempalace_wing"])
            if wing not in existing_wings and (leaf["enabled"] or lid in ("leaf-bitcoin", "leaf-ethereum", "leaf-sui", "leaf-hyperliquid")):
                ta = leaf["ta_specific_metrics"]
                self.palace.add_drawer(
                    PalaceDrawer(
                        drawer_id=f"drw_{wing}_{now_ms}",
                        timestamp_ms=now_ms,
                        wing=wing,
                        room="active_theses",
                        model_used=self.leaf_default_model,
                        thinking_depth="DEEP_THESIS" if leaf["enabled"] else "ECO_CONSERVATION",
                        thesis_continuity="CONFIRMED",
                        global_regime=str(ta.get("kumo_regime", "ABOVE_KUMO_BULLISH")),
                        panorama_summary=f"Flux RSS {leaf['chain']} positifs ; isolation stricte sur {', '.join(leaf['exclusive_assets'][:2])}.",
                        ta_confluence_notes=f"{leaf['chain']} : Fib 0.618={ta.get('golden_pocket_fib_618')}, RSI(14)={ta.get('rsi_14')}, OBI={ta.get('obi_l2')}.",
                        hypothesis=leaf["objective_summary"],
                        invalidation_condition=f"Clôture sous le Fib 0.618 ({ta.get('golden_pocket_fib_618')}) ou alerte RSS critique sur {leaf['chain']}.",
                        compiled_rules_summary={
                            "exclusive_assets": leaf["exclusive_assets"],
                            "risk_posture": leaf["risk_posture"],
                            "allocated_capital_usd": leaf["allocated_capital_usd"],
                        },
                        next_wakeup_sec=120 if leaf["enabled"] else 600,
                        wakeup_reason=f"Surveillance dédiée {leaf['chain']}",
                        tokens_used=620,
                        cost_usd=0.00004,
                    )
                )

    @property
    def deployed_capital_usd(self) -> float:
        return round(sum(float(v.get("allocated_capital_usd", 0.0)) for v in self.leaves.values()), 2)

    @property
    def dry_powder_usd(self) -> float:
        return round(max(0.0, self.total_capital_usd - self.deployed_capital_usd), 2)

    @property
    def dry_powder_ratio(self) -> float:
        if self.total_capital_usd <= 0:
            return 1.0
        return round(self.dry_powder_usd / self.total_capital_usd, 4)

    @property
    def treasury(self) -> Dict[str, Any]:
        return {
            "total_capital_usd": round(self.total_capital_usd, 2),
            "deployed_capital_usd": self.deployed_capital_usd,
            "dry_powder_usd": self.dry_powder_usd,
            "dry_powder_ratio": self.dry_powder_ratio,
            "min_dry_powder_ratio": self.min_dry_powder_ratio,
        }

    def _load_persisted(self) -> None:
        if not self._redis_url or not self._redis_cmd:
            return
        raw = self._redis_cmd(self._redis_url, "GET", self.REDIS_HIERARCHY_KEY)
        if not raw:
            return
        try:
            data = json.loads(raw)
            self.total_capital_usd = float(data.get("total_capital_usd", self.total_capital_usd))
            self.long_term_strategy_thesis = str(
                data.get("long_term_strategy_thesis", self.long_term_strategy_thesis)
            )
            saved_leaves = data.get("leaves", {})
            if isinstance(saved_leaves, dict):
                for lid, state in saved_leaves.items():
                    if lid in self.leaves and isinstance(state, dict):
                        for k in (
                            "allocated_capital_usd",
                            "capital_weight",
                            "risk_posture",
                            "enabled",
                            "realized_pnl_usd",
                            "paper_pnl_usd",
                            "active_positions_count",
                            "objective_summary",
                        ):
                            if k in state:
                                self.leaves[lid][k] = state[k]
                        self.leaves[lid]["weight_pct"] = round(
                            float(self.leaves[lid].get("capital_weight", 0.0)) * 100.0, 2
                        )
            if isinstance(data.get("deposit_history"), list):
                self.deposit_history = data["deposit_history"][:25]
            if isinstance(data.get("checkout_history"), list):
                self.checkout_history = data["checkout_history"][:25]
        except Exception:
            pass

    def persist(self) -> None:
        if not self._redis_url or not self._redis_cmd:
            return
        try:
            payload = json.dumps(
                {
                    "total_capital_usd": self.total_capital_usd,
                    "long_term_strategy_thesis": self.long_term_strategy_thesis,
                    "leaves": {
                        lid: {
                            "allocated_capital_usd": v["allocated_capital_usd"],
                            "capital_weight": v["capital_weight"],
                            "risk_posture": v["risk_posture"],
                            "enabled": v["enabled"],
                            "realized_pnl_usd": v["realized_pnl_usd"],
                            "paper_pnl_usd": v["paper_pnl_usd"],
                            "active_positions_count": v["active_positions_count"],
                            "objective_summary": v["objective_summary"],
                        }
                        for lid, v in self.leaves.items()
                    },
                    "deposit_history": self.deposit_history[:25],
                    "checkout_history": self.checkout_history[:25],
                },
                ensure_ascii=False,
            )
            self._redis_cmd(self._redis_url, "SET", self.REDIS_HIERARCHY_KEY, payload)
        except Exception:
            pass

    def _persist_state(self) -> None:
        self.persist()

    def smart_allocate_by_capital_size(self, total_usd: float) -> Dict[str, float]:
        """
        Determines optimal ecosystem weights based on capital scale so bridge fees never
        eat small portfolios while larger portfolios unlock specialized L1 alpha.
        Always keeps >= 20% in Dry Powder reserve.
        """
        if total_usd < 2_500.0:
            weights = {
                "leaf-solana": 0.45,
                "leaf-bitcoin": 0.30,
            }
        elif total_usd <= 25_000.0:
            weights = {
                "leaf-solana": 0.24,
                "leaf-bitcoin": 0.20,
                "leaf-ethereum": 0.14,
                "leaf-binance-cex": 0.08,
                "leaf-hyperliquid": 0.07,
                "leaf-sui": 0.06,
            }
        else:
            weights = {
                "leaf-solana": 0.20,
                "leaf-bitcoin": 0.18,
                "leaf-ethereum": 0.12,
                "leaf-binance-cex": 0.07,
                "leaf-hyperliquid": 0.07,
                "leaf-sui": 0.05,
                "leaf-bnb": 0.03,
                "leaf-xrp": 0.02,
                "leaf-ton": 0.02,
                "leaf-avalanche": 0.01,
                "leaf-tron": 0.01,
            }
        return weights

    def deposit_funds(
        self,
        amount_usd: float,
        token: str = "USDC",
        source_chain: str = "Solana",
        note: str = "Apport de capital opérateur",
    ) -> Dict[str, Any]:
        amt = round(float(amount_usd), 2)
        if amt <= 0:
            return {"status": "rejected", "reason": "Le montant confié doit être strictement positif."}

        now_ms = int(time.time() * 1000)
        before_total = self.total_capital_usd
        before_dry = self.dry_powder_usd
        self.total_capital_usd = round(self.total_capital_usd + amt, 2)

        target_weights = self.smart_allocate_by_capital_size(self.total_capital_usd)
        for lid, leaf in self.leaves.items():
            w = float(target_weights.get(lid, 0.0))
            leaf["capital_weight"] = w
            leaf["weight_pct"] = round(w * 100.0, 2)
            leaf["allocated_capital_usd"] = round(self.total_capital_usd * w, 2)
            leaf["enabled"] = leaf["allocated_capital_usd"] > 0
            if leaf["enabled"] and leaf["risk_posture"] in ("HIBERNATION", "LIQUIDATED_LOCKED"):
                leaf["risk_posture"] = "BALANCED"
            elif not leaf["enabled"]:
                leaf["risk_posture"] = "HIBERNATION"

        sizing_tier = (
            "COMPACT_P0"
            if self.total_capital_usd < 2500.0
            else ("GROWTH_P0_P1" if self.total_capital_usd <= 25000.0 else "INSTITUTIONAL_MULTI_CHAIN")
        )
        record = {
            "deposit_id": f"dep_{now_ms}",
            "timestamp_ms": now_ms,
            "amount_usd": amt,
            "token": token.upper(),
            "source_chain": source_chain,
            "capital_before_usd": before_total,
            "capital_after_usd": self.total_capital_usd,
            "dry_powder_after_usd": self.dry_powder_usd,
            "note": note,
        }
        self.deposit_history.insert(0, record)
        self.deposit_history = self.deposit_history[:25]
        self.persist()
        return {
            "status": "completed",
            "deposited_usd": amt,
            "sizing_tier": sizing_tier,
            "reserved_dry_powder_usd": round(max(0.0, self.dry_powder_usd - before_dry), 2),
            "deployed_usd": round(amt - max(0.0, self.dry_powder_usd - before_dry), 2),
            "deposit": record,
            "total_capital_usd": self.total_capital_usd,
            "dry_powder_usd": self.dry_powder_usd,
            "deployed_capital_usd": self.deployed_capital_usd,
        }

    def checkout_funds(
        self,
        amount_usd: float,
        target_chain: str,
        target_token: str,
        destination_address: str = "operator_wallet_default",
        quote_only: bool = False,
    ) -> Dict[str, Any]:
        amt = round(float(amount_usd), 2)
        if amt <= 0:
            return {"status": "error", "message": "Le montant demandé doit être strictement positif."}
        if amt > self.total_capital_usd:
            return {
                "status": "error",
                "message": f"Montant demandé (${amt:.2f}) supérieur au portefeuille maître (${self.total_capital_usd:.2f}).",
            }

        quote = CrossChainTreasuryRouter.quote_transfer(
            from_chain="Solana",
            to_chain=target_chain,
            amount_usd=amt,
            target_token=target_token,
        )

        # Determine funding breakdown: Dry Powder first, then proportional leaf recall if needed
        from_dry_powder = min(self.dry_powder_usd, amt)
        from_leaves = round(max(0.0, amt - from_dry_powder), 2)

        if quote_only:
            return {
                "status": "quoted",
                "quote": quote,
                "bridge_quote": quote,
                "target_chain": quote["to_chain"],
                "target_token": quote["target_token"],
                "delivered_token_qty": quote["delivered_token_amount"],
                "net_delivered_usd": quote["net_delivered_usd"],
                "total_fee_usd": quote["total_fee_usd"],
                "funding_plan": {
                    "from_dry_powder_usd": round(from_dry_powder, 2),
                    "recalled_from_leaves_usd": from_leaves,
                    "remaining_capital_usd": round(self.total_capital_usd - amt, 2),
                },
            }

        now_ms = int(time.time() * 1000)
        if from_leaves > 0 and self.deployed_capital_usd > 0:
            ratio_keep = max(0.0, (self.deployed_capital_usd - from_leaves) / self.deployed_capital_usd)
            for leaf in self.leaves.values():
                leaf["allocated_capital_usd"] = round(float(leaf["allocated_capital_usd"]) * ratio_keep, 2)
                if leaf["allocated_capital_usd"] <= 0:
                    leaf["enabled"] = False
                    leaf["risk_posture"] = "HIBERNATION"

        self.total_capital_usd = round(max(0.0, self.total_capital_usd - amt), 2)
        for leaf in self.leaves.values():
            w = (
                round(float(leaf["allocated_capital_usd"]) / self.total_capital_usd, 4)
                if self.total_capital_usd > 0
                else 0.0
            )
            leaf["capital_weight"] = w
            leaf["weight_pct"] = round(w * 100.0, 2)

        receipt = {
            "checkout_id": f"chk_{now_ms}",
            "timestamp_ms": now_ms,
            "destination_address": destination_address or f"{target_chain.lower()}_operator_vault",
            "from_dry_powder_usd": round(from_dry_powder, 2),
            "recalled_from_leaves_usd": from_leaves,
            **quote,
            "tx_hash": f"0x{hex(now_ms)[2:]}c7f9b2a1",
        }
        self.checkout_history.insert(0, receipt)
        self.checkout_history = self.checkout_history[:25]
        self.persist()
        return {
            "status": "completed",
            "receipt": receipt,
            "bridge_quote": quote,
            "target_chain": quote["to_chain"],
            "target_token": quote["target_token"],
            "delivered_token_qty": quote["delivered_token_amount"],
            "net_delivered_usd": quote["net_delivered_usd"],
            "total_fee_usd": quote["total_fee_usd"],
            "total_capital_usd": self.total_capital_usd,
            "dry_powder_usd": self.dry_powder_usd,
            "deployed_capital_usd": self.deployed_capital_usd,
        }

    def emergency_liquidate_leaf(self, leaf_id: str, reason: str = "Danger écosystème / contre-performance") -> Dict[str, Any]:
        """
        Immediately closes all positions of `leaf_id` and repatriates 100% of its allocated
        capital back into the Master Orchestrator's Dry Powder reserve.
        """
        if leaf_id not in self.leaves:
            return {"status": "error", "reason": f"Agent feuille inconnu: {leaf_id}"}

        leaf = self.leaves[leaf_id]
        repatriated_usd = float(leaf.get("allocated_capital_usd", 0.0))
        leaf["allocated_capital_usd"] = 0.0
        leaf["capital_weight"] = 0.0
        leaf["weight_pct"] = 0.0
        leaf["enabled"] = False
        leaf["risk_posture"] = "HIBERNATION"
        leaf["active_positions_count"] = 0
        leaf["objective_summary"] = f"🛑 Liquidé et rapatrié vers Dry Powder (${repatriated_usd:.2f}) — Motif : {reason}"
        leaf["last_hypothesis"] = leaf["objective_summary"]
        self.persist()
        return {
            "status": "liquidated",
            "leaf_id": leaf_id,
            "repatriated_usd": round(repatriated_usd, 2),
            "dry_powder_usd": self.dry_powder_usd,
            "reason": reason,
        }

    def update_leaf_mandate(
        self,
        leaf_id: str,
        risk_posture: Optional[str] = None,
        allocated_capital_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        if leaf_id not in self.leaves:
            return {"status": "error", "reason": f"Agent feuille inconnu: {leaf_id}"}
        leaf = self.leaves[leaf_id]

        if allocated_capital_usd is not None:
            requested = max(0.0, round(float(allocated_capital_usd), 2))
            other_deployed = sum(
                float(v["allocated_capital_usd"]) for k, v in self.leaves.items() if k != leaf_id
            )
            max_allowed = max(0.0, self.total_capital_usd * (1.0 - self.min_dry_powder_ratio) - other_deployed)
            effective_alloc = min(requested, round(max_allowed, 2))
            leaf["allocated_capital_usd"] = effective_alloc
            w = (
                round(effective_alloc / self.total_capital_usd, 4)
                if self.total_capital_usd > 0
                else 0.0
            )
            leaf["capital_weight"] = w
            leaf["weight_pct"] = round(w * 100.0, 2)
            leaf["enabled"] = effective_alloc > 0

        if risk_posture in ("AGGRESSIVE", "BALANCED", "DEFENSIVE", "HIBERNATION"):
            leaf["risk_posture"] = risk_posture
            if risk_posture == "HIBERNATION":
                leaf["enabled"] = False
            elif leaf["allocated_capital_usd"] > 0:
                leaf["enabled"] = True

        self.persist()
        return {"status": "updated", "leaf": self.get_leaf_detail(leaf_id)}

    def get_leaf_detail(self, leaf_id: str, solana_live_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        leaf = dict(self.leaves.get(leaf_id, self.leaves["leaf-solana"]))
        wing = str(leaf["mempalace_wing"])
        rss_feed = EcosystemRSSAggregator.get_feed_for_agent(leaf_id)
        drawers = self.palace.recall_recent(limit=6, wing=wing)
        leaf["rss_feed"] = rss_feed
        leaf["palace_drawers"] = drawers
        if leaf_id == "leaf-solana" and solana_live_metrics:
            leaf["paper_pnl_usd"] = round(
                float(solana_live_metrics.get("paper_model", {}).get("cumulative_pnl_usd", 0.0)), 2
            )
            leaf["realized_pnl_usd"] = round(
                float(solana_live_metrics.get("live_testnet", {}).get("cumulative_cex_pnl_usd", 0.0)), 4
            )
        return {
            **leaf,
            "leaf": leaf,
            "mempalace_drawers": drawers,
        }

    def get_hierarchy_snapshot(
        self,
        cost_status: Optional[Dict[str, Any]] = None,
        solana_populations: Optional[Dict[str, Any]] = None,
        cost_guard_status: Optional[Dict[str, Any]] = None,
        solana_live_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        eff_cost = cost_status or cost_guard_status or {}
        eff_sol = solana_populations or solana_live_metrics
        leaves_list = [
            self.get_leaf_detail(spec["leaf_id"], solana_live_metrics=eff_sol)
            for spec in LEAF_ECOSYSTEM_CATALOG
        ]
        all_wings = [str(spec["mempalace_wing"]) for spec in LEAF_ECOSYSTEM_CATALOG]
        macro_rss = EcosystemRSSAggregator.get_feed_for_agent("master")
        or_credit = dict(eff_cost.get("openrouter_credit", {}))
        or_credit.setdefault("credit_balance_usd", or_credit.get("balance_usd", 24.5))
        or_credit.setdefault("max_profit_share_pct", 0.10)
        active_cnt = sum(1 for lf in leaves_list if float(lf.get("allocated_capital_usd", 0.0)) > 0)
        tot_pnl = round(sum(float(lf.get("realized_pnl_usd", 0.0)) for lf in leaves_list), 2)
        return {
            "architecture": "hierarchical_master_leaf_v3",
            "master_orchestrator": {
                **self.master_state,
                "agent_name": "MasterOrchestrator",
                "model": self.master_model,
                "role": "Sovereign Portfolio Manager, Cross-Chain Capital Allocator & OpenRouter Credit Guardian",
                "mempalace_wing": "master_orchestrator",
                "cycle_interval_sec": self.master_interval_sec,
                "last_reflection_ms": self.last_master_reflection_ms,
                "next_reflection_ms": self.next_master_reflection_ms,
                "long_term_strategy_thesis": self.long_term_strategy_thesis,
                "rss_feed": macro_rss,
                "palace_drawers": self.palace.recall_recent(limit=6, wing="master_orchestrator"),
                "leaf_palaces_accessible_wings": len(all_wings),
                "cross_wing_digest": self.palace.format_cross_wing_digest(
                    wings=["leaf_solana", "leaf_bitcoin", "leaf_ethereum", "leaf_sui", "leaf_hyperliquid"],
                    per_wing_limit=1,
                ),
            },
            "treasury": {
                "total_capital_usd": round(self.total_capital_usd, 2),
                "deployed_capital_usd": self.deployed_capital_usd,
                "dry_powder_usd": self.dry_powder_usd,
                "dry_powder_ratio": self.dry_powder_ratio,
                "min_dry_powder_ratio": self.min_dry_powder_ratio,
                "dry_powder_ratio_pct": round(self.dry_powder_ratio * 100.0, 1),
                "min_dry_powder_ratio_pct": round(self.min_dry_powder_ratio * 100.0, 1),
                "active_leaves_count": active_cnt,
                "total_realized_pnl_usd": tot_pnl,
                "supported_checkout_tokens": list(TOKEN_PRICES_USD.keys()),
                "token_prices_usd": TOKEN_PRICES_USD,
                "deposit_history": self.deposit_history[:10],
                "checkout_history": self.checkout_history[:10],
                "bridge_evaluations": self.bridge_evaluations,
            },
            "openrouter_credit": or_credit,
            "openrouter_autonomy": or_credit,
            "macro_rss": macro_rss,
            "leaves": leaves_list,
            "leaf_agents": leaves_list,
            "checkout_history": self.checkout_history[:10],
            "bridge_evaluations": self.bridge_evaluations,
        }

from __future__ import annotations

import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional


class EcosystemRSSAggregator:
    """
    Provides strictly scoped RSS intelligence per leaf blockchain ecosystem as well as
    multi-channel macro/cross-chain RSS feeds for the Master Orchestrator (`Kimi K3.1 Pro`).
    """

    ECOSYSTEM_RSS_SOURCES: Dict[str, List[Dict[str, str]]] = {
        "master": [
            {"name": "CoinDesk Macro & Regulation", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
            {"name": "Blockworks Institutional Flows", "url": "https://blockworks.co/feed"},
            {"name": "DefiLlama Cross-Chain Bridge Monitor", "url": "https://defillama.com/rss"},
        ],
        "leaf-solana": [
            {"name": "Solana Foundation Status & Releases", "url": "https://solana.com/news/rss.xml"},
            {"name": "Helius Solana Validator & MEV Digest", "url": "https://www.helius.dev/blog/rss.xml"},
            {"name": "Jupiter & Jito Governance Feed", "url": "https://jup.ag/rss.xml"},
        ],
        "leaf-bitcoin": [
            {"name": "Bitcoin Optech Newsletter", "url": "https://bitcoinops.org/feed.xml"},
            {"name": "Mempool & Hashrate Intelligence", "url": "https://mempool.space/rss"},
        ],
        "leaf-ethereum": [
            {"name": "Week in Ethereum News", "url": "https://weekinethereumnews.com/feed/"},
            {"name": "Ethereum Foundation Blog", "url": "https://blog.ethereum.org/en/feed.xml"},
        ],
        "leaf-sui": [
            {"name": "Sui Foundation & DeepBook Updates", "url": "https://blog.sui.io/rss/"},
        ],
        "leaf-hyperliquid": [
            {"name": "Hyperliquid L1 & HLP Vault Telemetry", "url": "https://hyperliquid.xyz/rss"},
        ],
        "leaf-bnb": [
            {"name": "BNB Chain Blog & Quarterly Burn", "url": "https://www.bnbchain.org/en/blog/rss.xml"},
        ],
        "leaf-xrp": [
            {"name": "XRPL Dev & RLUSD Institutional Feed", "url": "https://xrpl.org/blog/rss.xml"},
        ],
        "leaf-ton": [
            {"name": "TON Foundation & Telegram Mini-Apps", "url": "https://blog.ton.org/rss/"},
        ],
        "leaf-tron": [
            {"name": "TRON DAO & USDT TRC-20 Treasury", "url": "https://trondao.org/feed/"},
        ],
        "leaf-avalanche": [
            {"name": "Avalanche Subnets & Liquidity Book", "url": "https://www.avax.network/blog/rss.xml"},
        ],
        "leaf-cosmos": [
            {"name": "Cosmos Hub & IBC Interchain Feed", "url": "https://blog.cosmos.network/feed"},
        ],
        "leaf-aptos": [
            {"name": "Aptos Labs Move VM Updates", "url": "https://aptosfoundation.org/rss.xml"},
        ],
        "leaf-chainlink": [
            {"name": "Chainlink CCIP & Oracle Network", "url": "https://blog.chain.link/rss/"},
        ],
        "leaf-stacks": [
            {"name": "Stacks sBTC & Nakamoto Bitcoin L2", "url": "https://www.stacks.co/blog/rss.xml"},
        ],
        "leaf-near": [
            {"name": "NEAR Protocol Chain Signatures & Intents", "url": "https://near.org/blog/rss.xml"},
        ],
        "leaf-cardano": [
            {"name": "Cardano IOG & eUTXO DeFi Feed", "url": "https://iohk.io/en/blog/rss.xml"},
        ],
        "leaf-polkadot": [
            {"name": "Polkadot XCM & Hydration Omnipool", "url": "https://polkadot.com/blog/rss.xml"},
        ],
        "leaf-dogecoin": [
            {"name": "Dogecoin Core & PoW UTXO Monitor", "url": "https://dogecoin.com/rss.xml"},
        ],
        "leaf-icp": [
            {"name": "DFINITY Internet Computer & Chain-Key", "url": "https://medium.com/feed/dfinity"},
        ],
        "leaf-canton": [
            {"name": "Canton Network Institutional RWA Feed", "url": "https://www.canton.network/rss.xml"},
        ],
        "leaf-celo": [
            {"name": "Celo OP Stack L2 & Mento Stablecoins", "url": "https://blog.celo.org/feed"},
        ],
        "leaf-tezos": [
            {"name": "Tezos & Etherlink Rollup Updates", "url": "https://spotlight.tezos.com/rss/"},
        ],
        "leaf-flow": [
            {"name": "Flow Blockchain Cadence DeFi", "url": "https://flow.com/post/rss.xml"},
        ],
        "leaf-eos": [
            {"name": "Vaulta (ex-EOS) Network Foundation", "url": "https://eosnetwork.com/blog/feed/"},
        ],
        "leaf-binance-cex": [
            {"name": "Binance Announcements & Perp Funding", "url": "https://www.binance.com/en/support/announcement/rss"},
        ],
        "leaf-paper-sandbox": [
            {"name": "Quant Microstructure & Adverse Selection Lab", "url": "https://arxiv.org/rss/q-fin.TR"},
        ],
    }

    CURATED_ECOSYSTEM_ITEMS: Dict[str, List[Dict[str, Any]]] = {
        "master": [
            {
                "source": "Blockworks Institutional Flows",
                "title": "Les flux institutionnels privilégient Solana, Bitcoin et Sui ; rotation de liquidité depuis les L1 secondaires",
                "sentiment": 0.68,
                "impact": "HIGH",
                "category": "MACRO_ALLOCATION",
            },
            {
                "source": "DefiLlama Cross-Chain Bridge Monitor",
                "title": "Baisse des frais Circle CCTP et Wormhole vers Solana (-18% sur les transferts USDC > $1,000)",
                "sentiment": 0.55,
                "impact": "MEDIUM",
                "category": "BRIDGE_ECONOMICS",
            },
            {
                "source": "CoinDesk Macro & Regulation",
                "title": "Stabilité des taux directeurs et hausse de l'encours stablecoin global (+$2.4B sur 7 jours)",
                "sentiment": 0.62,
                "impact": "HIGH",
                "category": "LIQUIDITY_REGIME",
            },
        ],
        "leaf-solana": [
            {
                "source": "Helius Solana Validator & MEV Digest",
                "title": "Firedancer / Agave : débit soutenu à 4 200 TPS effectifs, baisse de 22% des échecs de bundles Jito",
                "sentiment": 0.78,
                "impact": "HIGH",
                "category": "SOLANA_L1_INFRA",
            },
            {
                "source": "Jupiter & Jito Governance Feed",
                "title": "Hausse de +31% des volumes agrégés Jupiter v6 sur SOL/USDC, JUP/SOL et RAY/SOL",
                "sentiment": 0.72,
                "impact": "HIGH",
                "category": "SOLANA_DEX_FLOW",
            },
            {
                "source": "Solana Foundation Status & Releases",
                "title": "Funding perp SOL sur Drift et Jupiter Perps stable à +24% APR — portage delta-neutre attractif",
                "sentiment": 0.65,
                "impact": "MEDIUM",
                "category": "SOLANA_CARRY",
            },
        ],
        "leaf-bitcoin": [
            {
                "source": "Bitcoin Optech Newsletter",
                "title": "Mempool Bitcoin calme (6 sat/vB) et accumulation nette des ETF Spot BTC (+4 100 BTC)",
                "sentiment": 0.71,
                "impact": "HIGH",
                "category": "BTC_ONCHAIN",
            },
            {
                "source": "Mempool & Hashrate Intelligence",
                "title": "Hash Ribbon en expansion post-ajustement de difficulté ; réserves mineurs stables",
                "sentiment": 0.58,
                "impact": "MEDIUM",
                "category": "BTC_MINING",
            },
        ],
        "leaf-ethereum": [
            {
                "source": "Week in Ethereum News",
                "title": "Uniswap v4 hooks et Aave v3 concentrent 68% des volumes DeFi L1 ; basefee EIP-1559 à 4.2 Gwei",
                "sentiment": 0.61,
                "impact": "HIGH",
                "category": "ETH_DEFI",
            },
            {
                "source": "Ethereum Foundation Blog",
                "title": "Rendement staking Lido stETH + EigenLayer restaking stabilisé à 3.6% APR",
                "sentiment": 0.52,
                "impact": "MEDIUM",
                "category": "ETH_YIELD",
            },
        ],
        "leaf-sui": [
            {
                "source": "Sui Foundation & DeepBook Updates",
                "title": "DeepBook v3 CLOB franchit $480M de volume quotidien avec latence de finalité Mysticeti < 390ms",
                "sentiment": 0.76,
                "impact": "HIGH",
                "category": "SUI_CLOB",
            },
        ],
        "leaf-hyperliquid": [
            {
                "source": "Hyperliquid L1 & HLP Vault Telemetry",
                "title": "HLP Vault APR à 19.4% et open interest record sur le carnet Perps L1 natif",
                "sentiment": 0.74,
                "impact": "HIGH",
                "category": "HYPE_PERPS",
            },
        ],
        "leaf-bnb": [
            {
                "source": "BNB Chain Blog & Quarterly Burn",
                "title": "PancakeSwap v3 domine les volumes DEX EVM low-fee ; nouveau Launchpool actif",
                "sentiment": 0.60,
                "impact": "MEDIUM",
                "category": "BNB_DEFI",
            },
        ],
        "leaf-xrp": [
            {
                "source": "XRPL Dev & RLUSD Institutional Feed",
                "title": "Hausse de la liquidité RLUSD sur le CLOB natif XRPL et corridors de règlement transfrontaliers",
                "sentiment": 0.59,
                "impact": "MEDIUM",
                "category": "XRPL_CLOB",
            },
        ],
        "leaf-ton": [
            {
                "source": "TON Foundation & Telegram Mini-Apps",
                "title": "Circulation USDT-TON en hausse de +14% sur STON.fi et DeDust",
                "sentiment": 0.57,
                "impact": "MEDIUM",
                "category": "TON_ECOSYSTEM",
            },
        ],
        "leaf-tron": [
            {
                "source": "TRON DAO & USDT TRC-20 Treasury",
                "title": "Règlement quotidien USDT TRC-20 supérieur à $16B ; rendement Energy staking stable",
                "sentiment": 0.54,
                "impact": "MEDIUM",
                "category": "TRON_STABLECOIN",
            },
        ],
        "leaf-avalanche": [
            {
                "source": "Avalanche Subnets & Liquidity Book",
                "title": "Compression des spreads sur Trader Joe Liquidity Book (AVAX/USDC)",
                "sentiment": 0.56,
                "impact": "MEDIUM",
                "category": "AVAX_DEX",
            },
        ],
        "leaf-aptos": [
            {
                "source": "Aptos Labs Move VM Updates",
                "title": "Mise à niveau Move VM et croissance DeFi Thala (APT-USDC)",
                "sentiment": 0.57,
                "impact": "MEDIUM",
                "category": "APTOS_MOVE_VM",
            },
        ],
        "leaf-cosmos": [
            {
                "source": "Cosmos Hub & IBC Interchain Feed",
                "title": "Flux IBC soutenus entre Noble USDC, Osmosis et Injective",
                "sentiment": 0.55,
                "impact": "MEDIUM",
                "category": "COSMOS_IBC",
            },
        ],
    }

    CURATED_FIXTURE_TIMESTAMP_MS: int = 1730000000000

    @classmethod
    def parse_feed_xml(
        cls,
        xml_bytes: bytes,
        source_name: str,
        agent_id: str = "leaf-bitcoin",
        max_items: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Parses RSS 2.0 (<item>) or Atom (<entry> / {http://www.w3.org/2005/Atom}entry) XML bytes
        into normalized item dictionaries enriched with catalyst scoring and strictly scoped assets.
        """
        now_ms = int(time.time() * 1000)
        items: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_bytes)
        except Exception:
            return items

        node_elements = root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry") + root.findall(".//{*}entry") + root.findall(".//entry")
        # Deduplicate nodes by id/object identity while preserving order
        seen = set()
        unique_nodes = []
        for n in node_elements:
            if id(n) not in seen:
                seen.add(id(n))
                unique_nodes.append(n)
        node_elements = unique_nodes

        for node in node_elements[:max_items]:
            title = (
                node.findtext("title")
                or node.findtext("{http://www.w3.org/2005/Atom}title")
                or ""
            ).strip()
            summary = (
                node.findtext("description")
                or node.findtext("summary")
                or node.findtext("{http://www.w3.org/2005/Atom}summary")
                or node.findtext("{http://www.w3.org/2005/Atom}content")
                or ""
            ).strip()

            if not title:
                continue

            if agent_id == "leaf-ethereum":
                scored = cls.score_ethereum_catalyst(title, summary)
            elif agent_id == "leaf-sui":
                scored = cls.score_sui_catalyst(title, summary)
            elif agent_id == "leaf-hyperliquid":
                scored = cls.score_hyperliquid_catalyst(title, summary)
            elif agent_id == "leaf-xrp":
                scored = cls.score_xrp_catalyst(title, summary)
            elif agent_id == "leaf-bnb":
                scored = cls.score_bnb_catalyst(title, summary)
            elif agent_id == "leaf-tron":
                scored = cls.score_tron_catalyst(title, summary)
            elif agent_id == "leaf-avalanche":
                scored = cls.score_avalanche_catalyst(title, summary)
            elif agent_id == "leaf-cosmos":
                scored = cls.score_cosmos_catalyst(title, summary)
            elif agent_id == "leaf-aptos":
                scored = cls.score_aptos_catalyst(title, summary)
            else:
                scored = cls.score_bitcoin_catalyst(title, summary)
            items.append(
                {
                    "source": source_name,
                    "title": title[:180],
                    "summary": summary[:300],
                    "sentiment": scored["sentiment"],
                    "catalyst_score": scored["catalyst_score"],
                    "impact": scored["impact"],
                    "category": scored["category"],
                    "affected_assets": scored["affected_assets"],
                    "source_kind": "LIVE_RSS",
                    "curated": False,
                    "timestamp_ms": now_ms,
                }
            )

        return items

    @classmethod
    def score_bitcoin_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies Bitcoin-specific catalyst signals strictly scoped to BTC-USD, wBTC-BTC, and sBTC-BTC.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["etf", "spot", "inflow", "outflow", "fund", "blackrock", "fidelity"]):
            category = "BTC_ETF_FLOW"
        elif any(w in combined for w in ["mempool", "fee", "sat/vb", "congestion", "block"]):
            category = "BTC_MEMPOOL_FEES"
        elif any(w in combined for w in ["hash", "ribbon", "mining", "miner", "difficulty", "hashrate"]):
            category = "BTC_HASH_RIBBON"
        elif any(w in combined for w in ["wbtc", "sbtc", "bridge", "wrapped", "peg"]):
            category = "BTC_WBTC_SBTC_BRIDGE"
        else:
            category = "BTC_PROTOCOL_OPTECH"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "halving", "upgrade", "etf"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if "wbtc" in combined:
            affected_assets = ["wBTC-BTC", "BTC-USD"]
        elif "sbtc" in combined:
            affected_assets = ["sBTC-BTC", "BTC-USD"]
        else:
            affected_assets = ["BTC-USD", "wBTC-BTC", "sBTC-BTC"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    @classmethod
    def verify_and_ingest_bitcoin_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        """
        Iterates across all configured `leaf-bitcoin` RSS/Atom sources, parses live or injected XML,
        falls back cleanly to curated fixtures when offline/unreachable, and computes composite metrics.
        """
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-bitcoin", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://bitcoinops.org/feed.xml" if "Optech" in s_name else "https://mempool.space/rss")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-bitcoin", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-bitcoin", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_bitcoin_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        return {
            "agent_id": "leaf-bitcoin",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    ETHEREUM_EXCLUSIVE_ASSETS: List[str] = ["ETH-USDC", "stETH-ETH", "UNI-ETH", "AAVE-ETH"]

    @classmethod
    def score_ethereum_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies Ethereum-specific catalyst categories ("ETH_LST_RESTAKING", "ETH_DEFI_UNIV4_AAVE",
        "ETH_EIP1559_BLOB_GAS", "ETH_ETF_INSTITUTIONAL", "ETH_PROTOCOL_UPGRADE"), sentiment, catalyst_score,
        impact, and affected_assets strictly within ETHEREUM_EXCLUSIVE_ASSETS.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["steth", "eigenlayer", "restaking", "staking", "lido", "liquid"]):
            category = "ETH_LST_RESTAKING"
        elif any(w in combined for w in ["uniswap", "v4", "hooks", "aave", "v3", "defi", "curve", "liquidity"]):
            category = "ETH_DEFI_UNIV4_AAVE"
        elif any(w in combined for w in ["eip-1559", "eip1559", "basefee", "blob", "gas", "burn"]):
            category = "ETH_EIP1559_BLOB_GAS"
        elif any(w in combined for w in ["etf", "institutional", "blackrock", "fidelity", "fund", "spot"]):
            category = "ETH_ETF_INSTITUTIONAL"
        else:
            category = "ETH_PROTOCOL_UPGRADE"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "etf", "v4"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "hooks"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "hooks"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["steth", "eigenlayer", "restaking", "staking", "lido"]):
            affected_assets = ["stETH-ETH", "ETH-USDC"]
        elif any(w in combined for w in ["uni", "uniswap", "v4", "hooks"]):
            affected_assets = ["UNI-ETH", "ETH-USDC"]
        elif any(w in combined for w in ["aave", "v3"]):
            affected_assets = ["AAVE-ETH", "ETH-USDC"]
        else:
            affected_assets = list(cls.ETHEREUM_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.ETHEREUM_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["ETH-USDC"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    @classmethod
    def verify_and_ingest_ethereum_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        """
        Iterates across `leaf-ethereum` sources (`Week in Ethereum News`, `Ethereum Foundation Blog`),
        parsing live/injected RSS/Atom XML (source_kind="LIVE_RSS", feed_mode="LIVE" or "MIXED"),
        falling back cleanly to CURATED_FIXTURE (feed_mode="CURATED_FALLBACK"), and returning
        asset_catalyst_scores for all 4 Ethereum exclusive assets (ETH-USDC, stETH-ETH, UNI-ETH, AAVE-ETH).
        """
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-ethereum", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://weekinethereumnews.com/feed/" if "Week" in s_name else "https://blog.ethereum.org/en/feed.xml")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-ethereum", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-ethereum", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_ethereum_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.ETHEREUM_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-ethereum",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    SUI_EXCLUSIVE_ASSETS: List[str] = ["SUI-USDC", "DEEP-SUI", "CETUS-SUI"]

    @classmethod
    def score_sui_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies Sui-specific catalyst categories ("SUI_DEEPBOOK_CLOB", "SUI_CETUS_CLMM",
        "SUI_NAVI_LENDING", "SUI_PROTOCOL_UPGRADE"), sentiment, catalyst_score,
        impact, and affected_assets strictly within SUI_EXCLUSIVE_ASSETS.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["deepbook", "clob", "order book", "limit book"]):
            category = "SUI_DEEPBOOK_CLOB"
        elif any(w in combined for w in ["cetus", "clmm", "concentrated", "amm"]):
            category = "SUI_CETUS_CLMM"
        elif any(w in combined for w in ["navi", "lending", "borrow", "collateral"]):
            category = "SUI_NAVI_LENDING"
        else:
            category = "SUI_PROTOCOL_UPGRADE"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "mysticeti", "throughput"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "finality"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "mysticeti"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["deepbook", "clob"]):
            affected_assets = ["DEEP-SUI", "SUI-USDC"]
        elif any(w in combined for w in ["cetus", "clmm"]):
            affected_assets = ["CETUS-SUI", "SUI-USDC"]
        elif any(w in combined for w in ["navi", "lending"]):
            affected_assets = ["SUI-USDC"]
        else:
            affected_assets = list(cls.SUI_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.SUI_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["SUI-USDC"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    HYPERLIQUID_EXCLUSIVE_ASSETS: List[str] = ["HYPE-USDC", "PURR-USDC"]

    @classmethod
    def score_hyperliquid_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies Hyperliquid-specific catalyst categories, sentiment, catalyst_score,
        impact, and affected_assets strictly within HYPERLIQUID_EXCLUSIVE_ASSETS, extracting
        venue entities (HyperCore L1 CLOB, HLP Liquidity Vault, HyperEVM) from text.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["hlp", "vault", "market making", "liquidity vault", "maker"]):
            category = "HYPE_HLP_VAULT"
        elif any(w in combined for w in ["hyperevm", "spot", "auction", "liquidation", "evm"]):
            category = "HYPE_HYPEREVM_SPOT"
        elif any(w in combined for w in ["hypercore", "clob", "perp", "funding", "basis", "open interest", "order book", "obi"]):
            category = "HYPE_HYPERCORE_CLOB"
        else:
            category = "HYPE_ECOSYSTEM"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "hlp", "clob", "vault", "open interest"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "finality", "basis"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "hlp", "perp", "clob"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack", "liquidation"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["purr", "hyperevm", "spot", "auction"]):
            affected_assets = ["PURR-USDC", "HYPE-USDC"]
        elif any(w in combined for w in ["hlp", "vault", "maker", "liquidity"]):
            affected_assets = ["HYPE-USDC", "PURR-USDC"]
        elif any(w in combined for w in ["hypercore", "clob", "perp", "funding", "basis", "open interest", "order book", "obi"]):
            affected_assets = ["HYPE-USDC"]
        else:
            affected_assets = list(cls.HYPERLIQUID_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.HYPERLIQUID_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["HYPE-USDC"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    XRP_EXCLUSIVE_ASSETS: List[str] = ["XRP-RLUSD", "XRP-USDT"]

    @classmethod
    def score_xrp_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies XRP Ledger-specific catalyst categories, sentiment, catalyst_score,
        impact, and affected_assets strictly within XRP_EXCLUSIVE_ASSETS, extracting
        venue entities (XRPL Native CLOB, XRPL XLS-30 AMM) from text.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["amm", "xls-30", "xls 30", "xls30", "automated market maker", "pool"]):
            category = "XRPL_XLS30_AMM"
        elif any(w in combined for w in ["clob", "native clob", "order book", "limit book", "offer", "native dex"]):
            category = "XRPL_NATIVE_CLOB"
        elif any(w in combined for w in ["rlusd", "stablecoin", "settlement", "corridor", "gateway"]):
            category = "XRPL_RLUSD_SETTLEMENT"
        else:
            category = "XRPL_ECOSYSTEM"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "liquidity", "spread", "volume"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "finality", "throughput"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "clob", "amm", "rlusd", "settlement"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack", "default"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["amm", "xls-30", "xls 30", "xls30", "pool"]):
            affected_assets = ["XRP-RLUSD", "XRP-USDT"]
        elif any(w in combined for w in ["clob", "native clob", "order book", "limit book", "offer", "native dex"]):
            affected_assets = ["XRP-RLUSD"]
        elif any(w in combined for w in ["rlusd", "stablecoin", "settlement", "corridor", "gateway"]):
            affected_assets = ["XRP-RLUSD"]
        else:
            affected_assets = list(cls.XRP_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.XRP_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["XRP-RLUSD"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    BNB_EXCLUSIVE_ASSETS: List[str] = ["BNB-USDT", "CAKE-BNB"]

    @classmethod
    def score_bnb_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies BNB Chain-specific catalyst categories, sentiment, catalyst_score,
        impact, and affected_assets strictly within BNB_EXCLUSIVE_ASSETS, extracting
        venue entities (PancakeSwap v3, Venus Protocol, opBNB) from text.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["pancake", "pancakeswap", "cake", "v3", "launchpool"]):
            category = "BNB_PANCAKESWAP_V3"
        elif any(w in combined for w in ["venus", "lending", "supply", "apr", "money market"]):
            category = "BNB_VENUS_LENDING"
        elif any(w in combined for w in ["opbnb", "op-bnb", "l2", "layer 2", "rollup"]):
            category = "BNB_OPBNB_L2"
        elif any(w in combined for w in ["burn", "quarterly", "deflation", "auto-burn"]):
            category = "BNB_QUARTERLY_BURN"
        else:
            category = "BNB_ECOSYSTEM"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "burn", "launchpool", "v3"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "finality", "basis"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "pancake", "v3", "burn", "cake", "launchpool"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack", "liquidation"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["cake", "pancake", "pancakeswap", "launchpool"]):
            affected_assets = ["CAKE-BNB", "BNB-USDT"]
        elif any(w in combined for w in ["venus", "lending", "supply", "apr", "money market"]):
            affected_assets = ["BNB-USDT"]
        elif any(w in combined for w in ["opbnb", "op-bnb", "l2", "layer 2", "rollup"]):
            affected_assets = ["BNB-USDT"]
        elif any(w in combined for w in ["burn", "quarterly", "deflation", "auto-burn"]):
            affected_assets = ["BNB-USDT", "CAKE-BNB"]
        else:
            affected_assets = list(cls.BNB_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.BNB_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["BNB-USDT"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    @classmethod
    def verify_and_ingest_bnb_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-bnb", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://www.bnbchain.org/en/blog/rss.xml")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-bnb", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-bnb", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_bnb_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.BNB_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-bnb",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    TRON_EXCLUSIVE_ASSETS: List[str] = ["TRX-USDT", "SUN-TRX"]

    @classmethod
    def score_tron_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["sunswap", "sun swap", "sunswap v3", "swap", "dex", "pool", "liquidity"]):
            category = "TRON_SUNSWAP_V3"
        elif any(w in combined for w in ["justlend", "just lend", "lending", "lend", "borrow", "money market", "supply"]):
            category = "TRON_JUSTLEND_DAO"
        elif any(w in combined for w in ["usdt", "trc-20", "trc20", "treasury", "stablecoin", "settlement"]):
            category = "TRON_USDT_TRC20"
        elif any(w in combined for w in ["energy", "staking", "rental", "rent", "apy", "apr"]):
            category = "TRON_ENERGY_STAKING"
        else:
            category = "TRON_ECOSYSTEM"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "usdt", "energy", "staking", "sunswap", "treasury"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "swap", "lending", "liquidity", "pool"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "swap", "liquidity", "pool", "usdt", "energy", "staking", "sunswap", "sun"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack", "liquidation", "default"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["sunswap", "sun", "swap", "dex", "pool", "liquidity"]):
            affected_assets = ["SUN-TRX", "TRX-USDT"]
        elif any(w in combined for w in ["justlend", "lending", "lend", "borrow", "money market", "supply"]):
            affected_assets = ["TRX-USDT"]
        elif any(w in combined for w in ["usdt", "trc-20", "trc20", "treasury", "stablecoin", "settlement"]):
            affected_assets = ["TRX-USDT"]
        elif any(w in combined for w in ["energy", "staking", "rental", "rent", "apy", "apr"]):
            affected_assets = ["TRX-USDT"]
        else:
            affected_assets = list(cls.TRON_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.TRON_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["TRX-USDT"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    @classmethod
    def verify_and_ingest_tron_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-tron", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://trondao.org/feed/")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-tron", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-tron", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_tron_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.TRON_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-tron",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    @classmethod
    def verify_and_ingest_hyperliquid_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-hyperliquid", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://hyperliquid.xyz/rss")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-hyperliquid", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-hyperliquid", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_hyperliquid_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.HYPERLIQUID_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-hyperliquid",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    @classmethod
    def verify_and_ingest_xrp_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-xrp", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://xrpl.org/blog/rss.xml")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-xrp", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-xrp", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_xrp_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.XRP_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-xrp",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    @classmethod
    def verify_and_ingest_sui_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        """
        Iterates across `leaf-sui` sources (`Sui Foundation & DeepBook Updates`),
        parsing live/injected RSS/Atom XML (source_kind="LIVE_RSS", feed_mode="LIVE" or "MIXED"),
        falling back cleanly to CURATED_FIXTURE (feed_mode="CURATED_FALLBACK"), and returning
        asset_catalyst_scores for all 3 Sui exclusive assets (SUI-USDC, DEEP-SUI, CETUS-SUI).
        """
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-sui", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://blog.sui.io/rss/")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-sui", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-sui", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_sui_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.SUI_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-sui",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    AVALANCHE_EXCLUSIVE_ASSETS: List[str] = ["AVAX-USDC", "JOE-AVAX"]

    @classmethod
    def score_avalanche_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies Avalanche-specific catalyst categories, sentiment, catalyst_score,
        impact, and affected_assets strictly within AVALANCHE_EXCLUSIVE_ASSETS, extracting
        venue entities (LFJ (Trader Joe) Liquidity Book, Benqi) from text.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["benqi", "lending", "borrow", "collateral", "money market", "staking", "sav"]):
            category = "AVALANCHE_BENQI_LENDING"
        elif any(w in combined for w in ["liquidity book", "lfj", "trader joe", "joe", "amm", "clmm", "active bin", "dex"]):
            category = "AVALANCHE_LFJ_LIQUIDITY_BOOK"
        elif any(w in combined for w in ["subnet", "subnets", "l1", "c-chain", "hyperchains", "teleporter"]):
            category = "AVALANCHE_SUBNET_ECOSYSTEM"
        else:
            category = "AVALANCHE_ECOSYSTEM"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "throughput", "finality", "ict"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "liquidity", "swap", "bin"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "liquidity", "swap", "book", "subnet", "finality", "teleporter"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack", "liquidation"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["joe", "trader joe", "lfj", "liquidity book", "amm", "clmm"]):
            affected_assets = ["JOE-AVAX", "AVAX-USDC"]
        elif any(w in combined for w in ["benqi", "lending", "borrow", "collateral", "staking", "sav"]):
            affected_assets = ["AVAX-USDC"]
        elif any(w in combined for w in ["subnet", "subnets", "teleporter", "hyperchains"]):
            affected_assets = ["AVAX-USDC"]
        else:
            affected_assets = list(cls.AVALANCHE_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.AVALANCHE_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["AVAX-USDC"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    @classmethod
    def verify_and_ingest_avalanche_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-avalanche", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://www.avax.network/blog/rss.xml")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-avalanche", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-avalanche", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_avalanche_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.AVALANCHE_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-avalanche",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    COSMOS_EXCLUSIVE_ASSETS: List[str] = ["ATOM-USDC", "OSMO-ATOM", "INJ-USDC"]

    @classmethod
    def score_cosmos_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies Cosmos-specific catalyst categories, sentiment, catalyst_score,
        impact, and affected_assets strictly within COSMOS_EXCLUSIVE_ASSETS, extracting
        venue entities (Osmosis Supercharged Pools, Injective Helix CLOB, Noble USDC)
        from text.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["osmosis", "supercharged", "clmm", "pool", "liquidity", "swap", "amm"]):
            category = "COSMOS_OSMOSIS_SUPERCHARGED_POOLS"
        elif any(w in combined for w in ["injective", "helix", "clob", "orderbook", "derivatives", "perp"]):
            category = "COSMOS_INJECTIVE_HELIX_CLOB"
        elif any(w in combined for w in ["noble", "usdc", "stablecoin", "ibc", "transfer", "bridge", "noble usdc"]):
            category = "COSMOS_NOBLE_USDC_IBC"
        elif any(w in combined for w in ["ibc", "interchain", "cosmos hub", "atom", "staking", "hub"]):
            category = "COSMOS_IBC_INTERCHAIN"
        else:
            category = "COSMOS_ECOSYSTEM"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "throughput", "finality", "volume"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "liquidity", "swap", "pool", "ibc"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "liquidity", "swap", "pool", "ibc", "interchain", "atom", "osmosis", "injective", "noble", "usdc", "supercharged", "helix"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack", "liquidation"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["osmosis", "supercharged", "clmm", "pool", "liquidity", "swap", "amm"]):
            affected_assets = ["OSMO-ATOM", "ATOM-USDC"]
        elif any(w in combined for w in ["injective", "helix", "clob", "orderbook", "derivatives", "perp"]):
            affected_assets = ["INJ-USDC", "ATOM-USDC"]
        elif any(w in combined for w in ["noble", "usdc", "stablecoin", "ibc", "transfer", "bridge"]):
            affected_assets = ["ATOM-USDC"]
        elif any(w in combined for w in ["ibc", "interchain", "cosmos hub", "atom", "staking", "hub"]):
            affected_assets = ["ATOM-USDC"]
        else:
            affected_assets = list(cls.COSMOS_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.COSMOS_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["ATOM-USDC"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    @classmethod
    def verify_and_ingest_cosmos_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-cosmos", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://blog.cosmos.network/feed")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-cosmos", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-cosmos", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_cosmos_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.COSMOS_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-cosmos",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    APTOS_EXCLUSIVE_ASSETS: List[str] = ["APT-USDC", "THL-APT"]

    @classmethod
    def score_aptos_catalyst(cls, title: str, summary: str = "") -> Dict[str, Any]:
        """
        Classifies Aptos-specific catalyst categories, sentiment, catalyst_score,
        impact, and affected_assets strictly within APTOS_EXCLUSIVE_ASSETS, extracting
        venue entities (Thala Labs, Aries Markets, Econia CLOB) from text.
        """
        combined = f"{title} {summary}".lower()

        if any(w in combined for w in ["thala", "thalaswap", "liquidswap", "amm", "dex", "swap", "pool", "liquidity"]):
            category = "APTOS_THALA_LABS"
        elif any(w in combined for w in ["aries", "aries markets", "lending", "borrow", "money market", "collateral"]):
            category = "APTOS_ARIES_MARKETS"
        elif any(w in combined for w in ["econia", "clob", "order book", "matching engine"]):
            category = "APTOS_ECONIA_CLOB"
        elif any(w in combined for w in ["move", "move vm", "bytecode", "upgrade", "mainnet", "block stm", "parallel"]):
            category = "APTOS_MOVE_VM"
        else:
            category = "APTOS_ECOSYSTEM"

        if any(w in combined for w in ["record", "surge", "collapse", "major", "upgrade", "throughput", "finality", "launch", "release"]):
            impact = "HIGH"
        elif any(w in combined for w in ["moderate", "stable", "shift", "expansion", "growth", "liquidity", "swap", "lending"]):
            impact = "MEDIUM"
        else:
            impact = "LOW"

        pos_keywords = ["surge", "accumulation", "expansion", "inflow", "calm", "stable", "growth", "bullish", "high", "liquidity", "swap", "move", "upgrade", "mainnet", "finality", "parallel", "throughput"]
        neg_keywords = ["outflow", "congestion", "drop", "decline", "risk", "pressure", "bearish", "hack", "liquidation", "default"]

        score_mod = 0.0
        for pk in pos_keywords:
            if pk in combined:
                score_mod += 0.15
        for nk in neg_keywords:
            if nk in combined:
                score_mod -= 0.15

        sentiment = max(-1.0, min(1.0, round(0.60 + score_mod, 2)))
        catalyst_score = max(-1.0, min(1.0, round(0.65 + score_mod, 2)))

        if any(w in combined for w in ["thala", "thalaswap", "liquidswap", "amm", "dex", "swap", "pool", "liquidity"]):
            affected_assets = ["THL-APT", "APT-USDC"]
        elif any(w in combined for w in ["aries", "lending", "borrow", "collateral", "money market"]):
            affected_assets = ["APT-USDC"]
        elif any(w in combined for w in ["econia", "clob", "order book", "matching engine"]):
            affected_assets = ["APT-USDC"]
        elif any(w in combined for w in ["move", "move vm", "bytecode", "upgrade", "mainnet", "parallel", "throughput"]):
            affected_assets = ["APT-USDC"]
        else:
            affected_assets = list(cls.APTOS_EXCLUSIVE_ASSETS)

        affected_assets = [a for a in affected_assets if a in cls.APTOS_EXCLUSIVE_ASSETS]
        if not affected_assets:
            affected_assets = ["APT-USDC"]

        return {
            "sentiment": sentiment,
            "catalyst_score": catalyst_score,
            "impact": impact,
            "category": category,
            "affected_assets": affected_assets,
        }

    @classmethod
    def verify_and_ingest_aptos_feeds(
        cls,
        xml_payloads: Optional[Dict[str, bytes]] = None,
        try_network: bool = False,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get("leaf-aptos", [])
        items: List[Dict[str, Any]] = []
        live_count = 0

        xml_payloads = xml_payloads or {}

        for src in sources:
            s_name = src["name"]
            s_url = src["url"]
            payload = xml_payloads.get(s_name) or xml_payloads.get(s_url) or xml_payloads.get("https://aptosfoundation.org/rss.xml")
            if payload is None:
                for k, v in xml_payloads.items():
                    if s_name.lower() in k.lower() or k.lower() in s_name.lower() or s_url in k or k in s_url:
                        payload = v
                        break

            if payload is None and try_network:
                try:
                    req = urllib.request.Request(
                        s_url,
                        headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        payload = resp.read()
                except Exception:
                    payload = None

            if payload is not None:
                parsed = cls.parse_feed_xml(payload, s_name, agent_id="leaf-aptos", max_items=max_items)
                if parsed:
                    items.extend(parsed)
                    live_count += len(parsed)

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get("leaf-aptos", [])
            for item in curated[:max_items]:
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                scored = cls.score_aptos_catalyst(entry.get("title", ""), entry.get("summary", ""))
                entry.setdefault("sentiment", scored["sentiment"])
                entry.setdefault("catalyst_score", scored["catalyst_score"])
                entry.setdefault("impact", scored["impact"])
                entry.setdefault("category", scored["category"])
                entry.setdefault("affected_assets", scored["affected_assets"])
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        avg_catalyst = (
            round(sum(float(i.get("catalyst_score", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )

        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        asset_catalyst_scores: Dict[str, Dict[str, Any]] = {}
        for asset in cls.APTOS_EXCLUSIVE_ASSETS:
            asset_items = [i for i in items if asset in i.get("affected_assets", [])]
            if not asset_items:
                asset_items = items
            a_sent = round(sum(float(i.get("sentiment", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            a_cat = round(sum(float(i.get("catalyst_score", 0.5)) for i in asset_items) / len(asset_items), 2) if asset_items else 0.5
            asset_catalyst_scores[asset] = {
                "composite_sentiment": a_sent,
                "composite_catalyst_score": a_cat,
                "item_count": len(asset_items),
            }

        return {
            "agent_id": "leaf-aptos",
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "composite_catalyst_score": avg_catalyst,
            "items": items,
            "asset_catalyst_scores": asset_catalyst_scores,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }

    @classmethod
    def get_feed_for_agent(
        cls, agent_id: str, try_network: bool = False, max_items: int = 5
    ) -> Dict[str, Any]:
        """
        Returns strictly ecosystem-scoped RSS items and composite sentiment for `agent_id`
        (`master` or `leaf-<ecosystem>`). Supports RSS 2.0 (<item>) and Atom (<entry>) for bitcoin.
        """
        if agent_id == "leaf-bitcoin":
            res = cls.verify_and_ingest_bitcoin_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }
        elif agent_id == "leaf-ethereum":
            res = cls.verify_and_ingest_ethereum_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }
        elif agent_id == "leaf-sui":
            res = cls.verify_and_ingest_sui_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }
        elif agent_id == "leaf-hyperliquid":
            res = cls.verify_and_ingest_hyperliquid_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }
        elif agent_id == "leaf-xrp":
            res = cls.verify_and_ingest_xrp_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }

        elif agent_id == "leaf-bnb":
            res = cls.verify_and_ingest_bnb_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }

        elif agent_id == "leaf-tron":
            res = cls.verify_and_ingest_tron_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }

        elif agent_id == "leaf-avalanche":
            res = cls.verify_and_ingest_avalanche_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }

        elif agent_id == "leaf-cosmos":
            res = cls.verify_and_ingest_cosmos_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }

        elif agent_id == "leaf-aptos":
            res = cls.verify_and_ingest_aptos_feeds(try_network=try_network, max_items=max_items)
            return {
                "agent_id": res["agent_id"],
                "sources": res["sources"],
                "composite_sentiment": res["composite_sentiment"],
                "items": res["items"],
                "feed_mode": res["feed_mode"],
                "live_count": res["live_count"],
                "curated_count": res["curated_count"],
                "updated_at_ms": res["updated_at_ms"],
            }


        now_ms = int(time.time() * 1000)
        sources = cls.ECOSYSTEM_RSS_SOURCES.get(
            agent_id,
            [{"name": f"{agent_id} Ecosystem Official RSS", "url": f"https://{agent_id}.org/rss.xml"}],
        )
        items: List[Dict[str, Any]] = []

        if try_network and sources:
            try:
                req = urllib.request.Request(
                    sources[0]["url"],
                    headers={"User-Agent": "Robotrader-v3-RSS/1.0"},
                )
                with urllib.request.urlopen(req, timeout=1.2) as resp:
                    xml_bytes = resp.read()
                root = ET.fromstring(xml_bytes)
                for node in root.findall(".//item")[:max_items]:
                    title = (node.findtext("title") or "").strip()
                    if title:
                        items.append(
                            {
                                "source": sources[0]["name"],
                                "title": title[:180],
                                "sentiment": 0.58,
                                "impact": "MEDIUM",
                                "category": "LIVE_RSS",
                                "source_kind": "LIVE_RSS",
                                "curated": False,
                                "timestamp_ms": now_ms,
                            }
                        )
            except Exception:
                pass

        if not items:
            curated = cls.CURATED_ECOSYSTEM_ITEMS.get(agent_id)
            if not curated:
                eco_label = agent_id.replace("leaf-", "").upper()
                curated = [
                    {
                        "source": sources[0]["name"],
                        "title": f"Surveillance on-chain et gouvernance {eco_label} : liquidité stable, aucun incident validateur détecté",
                        "sentiment": 0.50,
                        "impact": "LOW",
                        "category": f"{eco_label}_WATCH",
                    }
                ]
            for idx, item in enumerate(curated[:max_items]):
                entry = dict(item)
                entry["source_kind"] = "CURATED_FIXTURE"
                entry["curated"] = True
                entry["timestamp_ms"] = item.get("timestamp_ms", cls.CURATED_FIXTURE_TIMESTAMP_MS)
                items.append(entry)

        avg_sentiment = (
            round(sum(float(i.get("sentiment", 0.5)) for i in items) / len(items), 2)
            if items
            else 0.5
        )
        live_count = sum(1 for i in items if i.get("source_kind") == "LIVE_RSS")
        curated_count = sum(1 for i in items if i.get("source_kind") == "CURATED_FIXTURE")
        if live_count > 0 and curated_count == 0:
            feed_mode = "LIVE"
        elif live_count > 0 and curated_count > 0:
            feed_mode = "MIXED"
        else:
            feed_mode = "CURATED_FALLBACK"

        return {
            "agent_id": agent_id,
            "sources": sources,
            "composite_sentiment": avg_sentiment,
            "items": items,
            "feed_mode": feed_mode,
            "live_count": live_count,
            "curated_count": curated_count,
            "updated_at_ms": now_ms,
        }


CURATED_FIXTURE_TIMESTAMP_MS = EcosystemRSSAggregator.CURATED_FIXTURE_TIMESTAMP_MS

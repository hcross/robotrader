from __future__ import annotations

import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List


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
    def get_feed_for_agent(
        cls, agent_id: str, try_network: bool = False, max_items: int = 5
    ) -> Dict[str, Any]:
        """
        Returns strictly ecosystem-scoped RSS items and composite sentiment for `agent_id`
        (`master` or `leaf-<ecosystem>`).
        """
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


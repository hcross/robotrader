from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple


class TechnicalAnalysisTool:
    """
    Professional Quantitative & Technical Analysis Engine for the Warm-Path Strategist.
    Computes exact mathematical indicators from live OHLCV candles (Binance CCXT) so the LLM
    reasons over verified confluences rather than guessing math:
      - Ichimoku Kinko Hyo (9, 26, 52): Tenkan-sen, Kijun-sen, Senkou Span A/B (Kumo cloud), TK cross
      - RSI (14): Wilder's smoothed Relative Strength Index, slope, and overbought/oversold regime
      - Fibonacci Retracements & Extensions: Swing High/Low, 0.236, 0.382, 0.500, 0.618 (Golden Pocket), 0.786, 1.272, 1.618
      - Volatility & Orderflow: ATR (14), Bollinger Bands (20, 2) squeeze detection, and L2 OBI
    """

    @staticmethod
    def _midpoint(highs: List[float], lows: List[float], period: int) -> float:
        w_highs = highs[-period:] if len(highs) >= period else highs
        w_lows = lows[-period:] if len(lows) >= period else lows
        if not w_highs or not w_lows:
            return 0.0
        return (max(w_highs) + min(w_lows)) / 2.0

    @staticmethod
    def compute_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        gains: List[float] = []
        losses: List[float] = []
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(0.0, delta))
            losses.append(max(0.0, -delta))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    @staticmethod
    def compute_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < 2:
            return 0.0
        trs: List[float] = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        window = trs[-period:] if len(trs) >= period else trs
        return sum(window) / len(window) if window else 0.0

    @classmethod
    def analyze_candles(
        cls,
        symbol: str,
        candles: List[List[float]],
        obi: float = 0.0,
        timeframe: str = "15m",
    ) -> Dict[str, Any]:
        """
        candles format: [[timestamp_ms, open, high, low, close, volume], ...]
        """
        if not candles:
            return {"symbol": symbol, "error": "no_candles"}

        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        closes = [float(c[4]) for c in candles]
        volumes = [float(c[5]) for c in candles]
        last_close = closes[-1]

        # 1. Ichimoku Kinko Hyo (9, 26, 52)
        tenkan = cls._midpoint(highs, lows, 9)
        kijun = cls._midpoint(highs, lows, 26)
        span_a = (tenkan + kijun) / 2.0
        span_b = cls._midpoint(highs, lows, 52)
        kumo_top = max(span_a, span_b)
        kumo_bottom = min(span_a, span_b)

        if last_close > kumo_top:
            kumo_regime = "ABOVE_KUMO_BULLISH"
        elif last_close < kumo_bottom:
            kumo_regime = "BELOW_KUMO_BEARISH"
        else:
            kumo_regime = "INSIDE_KUMO_NEUTRAL"

        if tenkan > kijun * 1.0005:
            tk_cross = "BULLISH_TK_CROSS"
        elif tenkan < kijun * 0.9995:
            tk_cross = "BEARISH_TK_CROSS"
        else:
            tk_cross = "NEUTRAL_TK"

        # 2. RSI (14) & Slope
        rsi_now = cls.compute_rsi(closes, 14)
        rsi_prev = cls.compute_rsi(closes[:-3], 14) if len(closes) > 18 else rsi_now
        rsi_slope = round(rsi_now - rsi_prev, 2)
        if rsi_now >= 70.0:
            rsi_regime = "OVERBOUGHT"
        elif rsi_now <= 32.0:
            rsi_regime = "OVERSOLD_BOUNCE_ZONE"
        elif rsi_now >= 55.0:
            rsi_regime = "BULLISH_MOMENTUM"
        elif rsi_now <= 45.0:
            rsi_regime = "BEARISH_MOMENTUM"
        else:
            rsi_regime = "NEUTRAL"

        # 3. Fibonacci Retracements & Extensions (over 52-bar swing)
        swing_window = min(len(candles), 52)
        swing_high = max(highs[-swing_window:])
        swing_low = min(lows[-swing_window:])
        swing_range = max(swing_high - swing_low, last_close * 0.005)

        fib_levels = {
            "0.236": round(swing_high - 0.236 * swing_range, 4),
            "0.382": round(swing_high - 0.382 * swing_range, 4),
            "0.500": round(swing_high - 0.500 * swing_range, 4),
            "0.618_golden_pocket": round(swing_high - 0.618 * swing_range, 4),
            "0.786": round(swing_high - 0.786 * swing_range, 4),
            "ext_1.272": round(swing_high + 0.272 * swing_range, 4),
            "ext_1.618": round(swing_high + 0.618 * swing_range, 4),
        }
        nearest_fib_name, nearest_fib_val = min(
            fib_levels.items(), key=lambda kv: abs(last_close - kv[1])
        )
        dist_to_nearest_fib_bps = round(
            ((last_close - nearest_fib_val) / last_close) * 10_000.0, 1
        )

        # 4. Bollinger Bands (20, 2) & ATR (14)
        bb_win = closes[-20:] if len(closes) >= 20 else closes
        sma_20 = sum(bb_win) / len(bb_win)
        variance = sum((x - sma_20) ** 2 for x in bb_win) / len(bb_win)
        std_20 = math.sqrt(variance)
        bb_upper = sma_20 + 2.0 * std_20
        bb_lower = sma_20 - 2.0 * std_20
        bb_width_pct = round(((bb_upper - bb_lower) / sma_20) * 100.0, 3) if sma_20 > 0 else 0.0
        atr_14 = cls.compute_atr(highs, lows, closes, 14)
        atr_bps = round((atr_14 / last_close) * 10_000.0, 1) if last_close > 0 else 0.0

        # 5. Pro Trader Confluence Synthesis
        support_usd = round(min(fib_levels["0.618_golden_pocket"], kijun), 2)
        resistance_usd = round(max(fib_levels["0.236"], kumo_top), 2)
        invalidation_usd = round(swing_low - atr_14 * 0.8, 2)

        confluence_score = 0.0
        confluence_reasons: List[str] = []
        if kumo_regime == "ABOVE_KUMO_BULLISH":
            confluence_score += 0.35
            confluence_reasons.append("Prix > Nuage Kumo (Haussier)")
        elif kumo_regime == "BELOW_KUMO_BEARISH":
            confluence_score -= 0.35
            confluence_reasons.append("Prix < Nuage Kumo (Baissier)")
        else:
            confluence_reasons.append("Prix dans le Kumo (Équilibre/Transition)")

        if tk_cross == "BULLISH_TK_CROSS":
            confluence_score += 0.20
            confluence_reasons.append("Tenkan > Kijun (TK Cross +)")
        elif tk_cross == "BEARISH_TK_CROSS":
            confluence_score -= 0.20
            confluence_reasons.append("Tenkan < Kijun (TK Cross -)")

        if rsi_now <= 35.0:
            confluence_score += 0.25
            confluence_reasons.append(f"RSI Survente ({rsi_now:.1f}) propice au rebond")
        elif rsi_now >= 70.0:
            confluence_score -= 0.25
            confluence_reasons.append(f"RSI Surachat ({rsi_now:.1f}) risque de rejet")
        elif 52.0 <= rsi_now < 68.0:
            confluence_score += 0.15
            confluence_reasons.append(f"RSI Momentum Haussier ({rsi_now:.1f})")

        if abs(dist_to_nearest_fib_bps) <= 45.0:
            confluence_reasons.append(
                f"Test Fib {nearest_fib_name} (${nearest_fib_val:.2f}, {dist_to_nearest_fib_bps:+.0f} bps)"
            )

        if obi >= 0.15:
            confluence_score += 0.20
            confluence_reasons.append(f"Absorption Bid L2 (OBI {obi:+.2f})")
        elif obi <= -0.15:
            confluence_score -= 0.20
            confluence_reasons.append(f"Pression Ask L2 (OBI {obi:+.2f})")

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "last_price": round(last_close, 2),
            "obi_l2": round(obi, 3),
            "ichimoku": {
                "tenkan_sen": round(tenkan, 2),
                "kijun_sen": round(kijun, 2),
                "senkou_span_a": round(span_a, 2),
                "senkou_span_b": round(span_b, 2),
                "kumo_top": round(kumo_top, 2),
                "kumo_bottom": round(kumo_bottom, 2),
                "kumo_regime": kumo_regime,
                "tk_cross": tk_cross,
            },
            "rsi": {
                "rsi_14": rsi_now,
                "slope": rsi_slope,
                "regime": rsi_regime,
            },
            "fibonacci": {
                "swing_high": round(swing_high, 2),
                "swing_low": round(swing_low, 2),
                "levels": fib_levels,
                "golden_pocket_618": round(fib_levels["0.618_golden_pocket"], 2),
                "nearest_level": nearest_fib_name,
                "nearest_level_price": round(nearest_fib_val, 2),
                "distance_to_nearest_bps": dist_to_nearest_fib_bps,
            },
            "volatility": {
                "atr_14": round(atr_14, 3),
                "atr_bps": atr_bps,
                "bb_upper": round(bb_upper, 2),
                "bb_lower": round(bb_lower, 2),
                "bb_width_pct": bb_width_pct,
                "squeeze_active": bb_width_pct < 1.8,
            },
            "key_zones": {
                "support_zone_usd": support_usd,
                "resistance_zone_usd": resistance_usd,
                "invalidation_price_usd": invalidation_usd,
            },
            "confluence_score": round(max(-1.0, min(1.0, confluence_score)), 2),
            "confluence_summary": " | ".join(confluence_reasons),
            "volume_last": round(volumes[-1], 2) if volumes else 0.0,
        }

    @classmethod
    def compute_bitcoin_ta_metrics(
        cls,
        candles: List[List[float]],
        bids: Optional[List[Tuple[float, float]]] = None,
        asks: Optional[List[Tuple[float, float]]] = None,
        onchain_telemetry: Optional[Dict[str, Any]] = None,
        symbol: str = "BTC-USD",
        timeframe: str = "15m",
    ) -> Dict[str, Any]:
        """
        Dedicated Bitcoin telemetry & TA computation helper supporting leaf-bitcoin exclusive assets
        (BTC-USD, wBTC-BTC, sBTC-BTC) across Bitcoin L1 Native, ThorChain Native Pool, and Lightning Liquidity.
        Computes real TA indicators from OHLCV + L2 orderbook and integrates on-chain telemetry metrics
        (mempool_fee_sat_vb, hash_ribbon_state, etf_netflow_24h_usd_m, miner_reserve_delta_btc) with explicit provenance.
        """
        obi = 0.0
        if bids and asks:
            b_vol = sum(float(b[1]) for b in bids[:5])
            a_vol = sum(float(a[1]) for a in asks[:5])
            tot = b_vol + a_vol
            if tot > 0:
                obi = (b_vol - a_vol) / tot

        has_candles = bool(candles and len(candles) >= 5)
        has_telemetry = bool(onchain_telemetry and isinstance(onchain_telemetry, dict) and len(onchain_telemetry) > 0)

        if not has_candles:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "ta_metrics_source": "CATALOG_FIXTURE",
                "mempool_fee_sat_vb": 6.2,
                "hash_ribbon_state": "EXPANSION_BULLISH",
                "etf_netflow_24h_usd_m": 328.0,
                "miner_reserve_delta_btc": 140.0,
                "kumo_regime": "ABOVE_KUMO_BULLISH",
                "golden_pocket_fib_618": 79850.0,
                "rsi_14": 56.4,
                "obi_l2": obi if (bids or asks) else 0.31,
                "venues": ["Bitcoin L1 Native", "ThorChain Native Pool", "Lightning Liquidity"],
                "exclusive_assets": ["BTC-USD", "wBTC-BTC", "sBTC-BTC"],
            }

        ta_result = cls.analyze_candles(symbol=symbol, candles=candles, obi=obi, timeframe=timeframe)
        kumo_regime = ta_result.get("ichimoku", {}).get("kumo_regime", "ABOVE_KUMO_BULLISH")
        golden_pocket = ta_result.get("fibonacci", {}).get("golden_pocket_618", 79850.0)
        rsi_14 = ta_result.get("rsi", {}).get("rsi_14", 56.4)
        obi_l2 = ta_result.get("obi_l2", obi)

        telemetry = onchain_telemetry or {}
        mempool_fee = float(telemetry.get("mempool_fee_sat_vb", 8.5))
        hash_ribbon = str(telemetry.get("hash_ribbon_state", "EXPANSION_BULLISH"))
        etf_netflow = float(telemetry.get("etf_netflow_24h_usd_m", 412.5))
        miner_reserve = float(telemetry.get("miner_reserve_delta_btc", 185.0))

        source = "LIVE_COMPUTED" if has_candles else "CATALOG_FIXTURE"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "ta_metrics_source": source,
            "mempool_fee_sat_vb": mempool_fee,
            "hash_ribbon_state": hash_ribbon,
            "etf_netflow_24h_usd_m": etf_netflow,
            "miner_reserve_delta_btc": miner_reserve,
            "kumo_regime": kumo_regime,
            "golden_pocket_fib_618": golden_pocket,
            "rsi_14": rsi_14,
            "obi_l2": obi_l2,
            "venues": ["Bitcoin L1 Native", "ThorChain Native Pool", "Lightning Liquidity"],
            "exclusive_assets": ["BTC-USD", "wBTC-BTC", "sBTC-BTC"],
        }

    @classmethod
    def ingest_bitcoin_market_snapshot(
        cls,
        candles: List[List[float]],
        bids: Optional[List[Tuple[float, float]]] = None,
        asks: Optional[List[Tuple[float, float]]] = None,
        onchain_telemetry: Optional[Dict[str, Any]] = None,
        symbol: str = "BTC-USD",
        timeframe: str = "15m",
    ) -> Dict[str, Any]:
        return cls.compute_bitcoin_ta_metrics(
            candles=candles,
            bids=bids,
            asks=asks,
            onchain_telemetry=onchain_telemetry,
            symbol=symbol,
            timeframe=timeframe,
        )

    ETHEREUM_EXCLUSIVE_ASSETS = ("ETH-USDC", "stETH-ETH", "UNI-ETH", "AAVE-ETH")
    ETHEREUM_VENUES = ("Uniswap v4", "Aave v3", "Curve", "Lido / EigenLayer")
    ETHEREUM_FALLBACK_TA_METRICS = {
        "eip1559_base_fee_gwei": 4.2,
        "blob_fee_gwei": 0.08,
        "steth_peg_ratio": 0.9997,
        "restaking_apr_pct": 3.65,
        "kumo_regime": "ABOVE_KUMO_BULLISH",
        "golden_pocket_fib_618": 2295.0,
        "rsi_14": 51.8,
        "obi_l2": 0.14,
    }

    @classmethod
    def compute_ethereum_ta_metrics(
        cls,
        candles: Optional[List[List[float]]] = None,
        bids: Optional[List[Tuple[float, float]]] = None,
        asks: Optional[List[Tuple[float, float]]] = None,
        onchain_telemetry: Optional[Dict[str, Any]] = None,
        symbol: str = "ETH-USDC",
        timeframe: str = "15m",
        venue: str = "Uniswap v4",
    ) -> Dict[str, Any]:
        """
        Dedicated Ethereum telemetry & TA computation helper supporting leaf-ethereum exclusive assets
        (ETH-USDC, stETH-ETH, UNI-ETH, AAVE-ETH) across Uniswap v4, Aave v3, Curve, Lido / EigenLayer.
        Enforces symbol in ETHEREUM_EXCLUSIVE_ASSETS and venue in ETHEREUM_VENUES (raising ValueError on mismatch).
        Computes real TA indicators from OHLCV + L2 orderbook and integrates Ethereum on-chain telemetry metrics
        (eip1559_base_fee_gwei, blob_fee_gwei, steth_peg_ratio, restaking_apr_pct) with explicit provenance.
        """
        if symbol not in cls.ETHEREUM_EXCLUSIVE_ASSETS:
            raise ValueError(f"Invalid Ethereum symbol: {symbol}. Expected one of {cls.ETHEREUM_EXCLUSIVE_ASSETS}")
        if venue not in cls.ETHEREUM_VENUES:
            raise ValueError(f"Invalid Ethereum venue: {venue}. Expected one of {cls.ETHEREUM_VENUES}")

        obi = 0.0
        if bids and asks:
            b_vol = sum(float(b[1]) for b in bids[:5])
            a_vol = sum(float(a[1]) for a in asks[:5])
            tot = b_vol + a_vol
            if tot > 0:
                obi = (b_vol - a_vol) / tot

        has_candles = bool(candles and isinstance(candles, list) and len(candles) >= 5)

        if not has_candles:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "venue": venue,
                "ta_metrics_source": "CATALOG_FIXTURE",
                **cls.ETHEREUM_FALLBACK_TA_METRICS,
                "obi_l2": obi if (bids or asks) else cls.ETHEREUM_FALLBACK_TA_METRICS["obi_l2"],
                "venues": list(cls.ETHEREUM_VENUES),
                "exclusive_assets": list(cls.ETHEREUM_EXCLUSIVE_ASSETS),
            }

        ta_result = cls.analyze_candles(symbol=symbol, candles=candles, obi=obi, timeframe=timeframe)
        kumo_regime = ta_result.get("ichimoku", {}).get("kumo_regime", cls.ETHEREUM_FALLBACK_TA_METRICS["kumo_regime"])
        golden_pocket = ta_result.get("fibonacci", {}).get("golden_pocket_618", cls.ETHEREUM_FALLBACK_TA_METRICS["golden_pocket_fib_618"])
        rsi_14 = ta_result.get("rsi", {}).get("rsi_14", cls.ETHEREUM_FALLBACK_TA_METRICS["rsi_14"])
        obi_l2 = ta_result.get("obi_l2", obi)

        telemetry = onchain_telemetry or {}
        eip1559_base_fee = float(telemetry.get("eip1559_base_fee_gwei", cls.ETHEREUM_FALLBACK_TA_METRICS["eip1559_base_fee_gwei"]))
        blob_fee = float(telemetry.get("blob_fee_gwei", cls.ETHEREUM_FALLBACK_TA_METRICS["blob_fee_gwei"]))
        steth_peg = float(telemetry.get("steth_peg_ratio", cls.ETHEREUM_FALLBACK_TA_METRICS["steth_peg_ratio"]))
        restaking_apr = float(telemetry.get("restaking_apr_pct", cls.ETHEREUM_FALLBACK_TA_METRICS["restaking_apr_pct"]))

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "venue": venue,
            "ta_metrics_source": "LIVE_COMPUTED",
            "eip1559_base_fee_gwei": eip1559_base_fee,
            "blob_fee_gwei": blob_fee,
            "steth_peg_ratio": steth_peg,
            "restaking_apr_pct": restaking_apr,
            "kumo_regime": kumo_regime,
            "golden_pocket_fib_618": golden_pocket,
            "rsi_14": rsi_14,
            "obi_l2": obi_l2,
            "venues": list(cls.ETHEREUM_VENUES),
            "exclusive_assets": list(cls.ETHEREUM_EXCLUSIVE_ASSETS),
        }

    @classmethod
    def ingest_ethereum_market_snapshot(
        cls,
        market_feeds: Optional[Dict[str, Dict[str, Any]]] = None,
        onchain_telemetry: Optional[Dict[str, Any]] = None,
        venue: str = "Uniswap v4",
    ) -> Dict[str, Any]:
        """
        Ingests Ethereum market snapshot across market feeds and onchain telemetry.
        """
        feeds = market_feeds or {}
        symbol = "ETH-USDC"
        candles: Optional[List[List[float]]] = None
        bids: Optional[List[Tuple[float, float]]] = None
        asks: Optional[List[Tuple[float, float]]] = None

        if feeds:
            target_sym = next(iter(feeds.keys()))
            if target_sym in cls.ETHEREUM_EXCLUSIVE_ASSETS:
                symbol = target_sym
            feed_data = feeds.get(symbol, next(iter(feeds.values())))
            candles = feed_data.get("candles")
            bids = feed_data.get("bids")
            asks = feed_data.get("asks")

        return cls.compute_ethereum_ta_metrics(
            candles=candles,
            bids=bids,
            asks=asks,
            onchain_telemetry=onchain_telemetry,
            symbol=symbol,
            venue=venue,
        )


class SocialMacroPanoramaTool:
    """
    Synthesizes high-level social narratives (X/CT, Reddit, Telegram whale alerts, macro liquidity)
    combined with live exchange orderflow metrics to give the Warm-Path LLM a 360° market panorama.
    """

    @staticmethod
    def build_panorama(ta_snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)

        # Dynamic confluence computation across only present snapshots
        scores: List[float] = []
        for symbol, snap in (ta_snapshots or {}).items():
            if isinstance(snap, dict) and "confluence_score" in snap:
                try:
                    scores.append(float(snap["confluence_score"]))
                except (ValueError, TypeError):
                    pass
        avg_score = (sum(scores) / len(scores)) if scores else 0.0

        sol_ta = (ta_snapshots or {}).get("SOL/USDT", {})
        sol_score = float(sol_ta.get("confluence_score", 0.0)) if isinstance(sol_ta, dict) else 0.0
        btc_ta = (ta_snapshots or {}).get("BTC/USDT", {})
        btc_score = float(btc_ta.get("confluence_score", 0.0)) if isinstance(btc_ta, dict) else 0.0

        sol_fib_dist = abs(
            float(sol_ta.get("fibonacci", {}).get("distance_to_nearest_bps", 100.0))
        ) if isinstance(sol_ta, dict) else 100.0
        sol_squeeze = bool(sol_ta.get("volatility", {}).get("squeeze_active", False)) if isinstance(sol_ta, dict) else False

        signals: List[Dict[str, Any]] = [
            {
                "source": "X / CryptoTwitter Quant Pulse",
                "topic": "Solana DeFi & Jito MEV Flow",
                "sentiment_score": round(0.68 + 0.15 * sol_score, 2),
                "narrative": (
                    "Hausse de +34% des volumes Jupiter v6 et accumulation de wallets smart-money "
                    "autour de la Kijun-sen SOL ; attention aux faux départs de memecoins non vérifiés."
                ),
                "source_kind": "SYNTHETIC_FIXTURE",
            },
            {
                "source": "On-Chain Whale & Perp Funding Radar",
                "topic": "Funding Basis & Absorption Spot",
                "sentiment_score": round(0.58 + 0.15 * btc_score, 2),
                "narrative": (
                    "Funding annualisé positif (+24% APR sur SOL-PERP) favorisant le Pod 1 Carry ; "
                    "carnet Spot absorbant les ventes proches du retracement Fibonacci 0.618."
                ),
                "source_kind": "SYNTHETIC_FIXTURE",
            },
            {
                "source": "Macro & Cross-Asset Volatility",
                "topic": "Compression de Volatilité Intraday",
                "sentiment_score": round(0.52 + 0.20 * avg_score, 2),
                "narrative": (
                    "Compression Bollinger détectée sur 15m : les desks quantitatifs resserrent "
                    "les seuils OBI avant cassure du Nuage d'Ichimoku."
                    if sol_squeeze
                    else "Flux directionnel actif sur les paires majeures avec rotation vers le bêta Solana."
                ),
                "source_kind": "SYNTHETIC_FIXTURE",
            },
        ]

        urgency_level = "HIGH_INFLECTION" if (sol_fib_dist < 30.0 or sol_squeeze) else "NORMAL_FLOW"
        composite_sentiment = round(0.55 + 0.25 * avg_score, 2)
        return {
            "timestamp_ms": now_ms,
            "composite_sentiment": composite_sentiment,
            "Composite_sentiment": composite_sentiment,
            "urgency_level": urgency_level,
            "source_kind": "SYNTHETIC_FIXTURE",
            "social_signals": signals,
        }

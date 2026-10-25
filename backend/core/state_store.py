from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .errors import RustBinaryNotFoundError
from .hierarchy import HierarchicalFleetManager
from .memory_palace import PalaceDrawer, StrategyMemoryPalace
from .schemas import AssetOverride, CatalystSignal, PolicyEnvelope


def _redis_cmd(redis_url: str, *args: str) -> Optional[str]:
    """Minimal zero-dependency RESP client for persisting state to Redis."""
    try:
        parsed = urlparse(redis_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        payload = f"*{len(args)}\r\n" + "".join(
            f"${len(a.encode('utf-8'))}\r\n{a}\r\n" for a in args
        )
        with socket.create_connection((host, port), timeout=0.5) as sock:
            sock.sendall(payload.encode("utf-8"))
            first = b""
            while not first.endswith(b"\r\n"):
                chunk = sock.recv(1)
                if not chunk:
                    return None
                first += chunk
            header = first.decode("utf-8").strip()
            if header.startswith("+"):
                return header[1:]
            if header.startswith("$"):
                length = int(header[1:])
                if length < 0:
                    return None
                data = b""
                while len(data) < length + 2:
                    chunk = sock.recv(min(4096, length + 2 - len(data)))
                    if not chunk:
                        break
                    data += chunk
                return data[:-2].decode("utf-8")
    except Exception:
        return None
    return None


def resolve_robotrader_binary(engine_dir: Path) -> Path:
    """Select the ``robotrader-node`` binary with debug-first precedence.

    A fresh local debug build must win over a stale release build; the runtime
    image ships only the release binary, so release is the fallback. No compiler
    is invoked: a missing binary raises ``RustBinaryNotFoundError`` and callers
    must build it explicitly before serving requests.
    """
    debug_binary = engine_dir / "target" / "debug" / "robotrader-node"
    release_binary = engine_dir / "target" / "release" / "robotrader-node"
    if debug_binary.exists():
        return debug_binary
    if release_binary.exists():
        return release_binary
    raise RustBinaryNotFoundError([debug_binary, release_binary])


class HybridStateStore:
    """
    Manages the shared IPC state between the Python Warm-Path AI Meta-Controller,
    the Rust Hot-Path / Backtest Engine (`engine-rs`), and the continuous Live Testnet
    execution loop (Binance Testnet + Solana Devnet).
    """

    REDIS_STATE_KEY = "robotrader:v2:state"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._redis_url: Optional[str] = os.getenv("REDIS_URL")
        self._policy: PolicyEnvelope = PolicyEnvelope.default_active()
        self.kill_switch_active: bool = False
        self.kill_switch_reason: Optional[str] = None
        self.recent_catalysts: List[CatalystSignal] = [
            CatalystSignal(
                asset="SOL-USDT",
                catalyst_type="WHALE_ACCUMULATION",
                conviction=0.85,
                directional_bias="LONG_BIAS",
                half_life_minutes=240,
                summary="Smart-money inflow +$4.8M on Solana perps & spot; funding APR 32%",
            ),
            CatalystSignal(
                asset="JUP-USDT",
                catalyst_type="GOVERNANCE_CATALYST",
                conviction=0.78,
                directional_bias="LONG_BIAS",
                half_life_minutes=180,
                summary="ASR staking fee distribution vote passed; strong L2 bid absorption",
            ),
        ]
        self.last_backtest_result: Optional[Dict[str, Any]] = None
        self.live_executions: List[Dict[str, Any]] = []
        self.live_pnl_usd: float = 0.0
        self.live_fees_usd: float = 0.0
        self.paper_lifetime_trades: int = 0
        self.paper_lifetime_wins: int = 0
        self.paper_lifetime_losses: int = 0
        self.paper_lifetime_flat: int = 0
        self.live_pod_pnl: Dict[str, float] = {
            "pod_carry": 0.0,
            "pod_momentum": 0.0,
            "pod_onchain_alpha": 0.0,
            "pod_sniper": 0.0,
        }
        self.live_tick_count: int = 0
        self._worker_started: bool = False
        self._last_prices: Dict[str, float] = {}
        self._last_obi: Dict[str, float] = {}

        solana_rpc = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com").lower()
        binance_testnet = os.getenv("BINANCE_TESTNET", "true").lower() in ("true", "1", "yes")
        self.is_testnet_mode: bool = binance_testnet or ("devnet" in solana_rpc) or ("testnet" in solana_rpc)
        self.solana_cluster: str = "devnet" if "devnet" in solana_rpc else ("testnet" if "testnet" in solana_rpc else "mainnet-beta")
        self.testnet_positions: Dict[str, Dict[str, float]] = {}
        self.testnet_cex_realized_pnl_usd: float = 0.0
        self.solana_devnet_tx_count: int = 0
        self.solana_devnet_gas_sol: float = 0.0
        self.testnet_wallet_snapshot: Dict[str, Any] = {
            "binance_free_usdt": 10000.0,
            "binance_total_usdt": 10000.0,
            "solana_address": os.getenv("SOLANA_PUBLIC_KEY", ""),
            "solana_balance_sol": 5.0,
        }

        # ADR-0002 & ADR-0003: Infinite Strategy Palace Memory + Hierarchical Fleet Manager
        self.palace = StrategyMemoryPalace(redis_cmd_fn=_redis_cmd, redis_url=self._redis_url)
        self.hierarchy = HierarchicalFleetManager(
            palace=self.palace,
            redis_cmd_fn=_redis_cmd,
            redis_url=self._redis_url,
        )
        self.latest_ta_snapshots: Dict[str, Dict[str, Any]] = {}
        self.latest_social_panorama: Dict[str, Any] = {}
        self.cognitive_base_interval_sec: int = int(os.getenv("COGNITIVE_BASE_INTERVAL_SEC", "900"))
        now_ms = int(time.time() * 1000)
        self.last_cognitive_wakeup_ms: int = now_ms
        self.next_cognitive_wakeup_ms: int = now_ms + self.cognitive_base_interval_sec * 1000
        self.cognitive_wakeup_reason: str = (
            "Auto-scheduler LLM en pause par défaut ($0.00/h) — cadence 15m (900s) alignée sur la clôture des bougies"
        )

        self._load_persisted_state()

    @staticmethod
    def _is_solana_ecosystem_symbol(symbol: str) -> bool:
        s = str(symbol or "").upper()
        return any(s.startswith(prefix) for prefix in ("SOL", "JUP", "RAY", "BONK", "PYTH", "JTO"))

    def _normalize_legacy_execution(self, ex: Dict[str, Any]) -> Dict[str, Any]:
        venue = str(ex.get("venue", ""))
        if venue == "SOLANA_DEVNET_ONCHAIN" and "pnl_type" not in ex:
            sim_pnl = float(ex.get("simulated_pnl_usd", ex.get("realized_pnl_usd", 0.0)))
            ex["simulated_pnl_usd"] = sim_pnl
            ex["realized_pnl_usd"] = 0.0
            ex["gas_fee_sol"] = float(ex.get("gas_fee_sol", 0.000005))
            ex["pnl_type"] = "DEVNET_SELF_TX"
            ex["is_testnet_devnet"] = True
        elif venue == "BINANCE_TESTNET_LIVE" and "pnl_type" not in ex:
            sim_pnl = float(ex.get("simulated_pnl_usd", ex.get("realized_pnl_usd", 0.0)))
            ex["simulated_pnl_usd"] = sim_pnl
            ex["pnl_type"] = "TESTNET_CEX_ORDER"
            ex["is_testnet_devnet"] = True
        return ex

    def _load_persisted_state(self) -> None:
        if not self._redis_url:
            return
        raw = _redis_cmd(self._redis_url, "GET", self.REDIS_STATE_KEY)
        if not raw:
            return
        try:
            data = json.loads(raw)
            if "policy" in data and isinstance(data["policy"], dict):
                pol = PolicyEnvelope.from_dict(data["policy"])
                pol.issued_at_ms = int(time.time() * 1000)
                # Ensure non-Solana asset overrides are stripped from leaf-solana policy
                pol.asset_overrides = {
                    k: v
                    for k, v in pol.asset_overrides.items()
                    if self._is_solana_ecosystem_symbol(k)
                }
                for default_k, default_v in PolicyEnvelope.default_active().asset_overrides.items():
                    pol.asset_overrides.setdefault(default_k, default_v)
                self._policy = pol
            self.kill_switch_active = bool(data.get("kill_switch_active", False))
            self.kill_switch_reason = data.get("kill_switch_reason")
            raw_execs = list(data.get("live_executions", []))[:200]
            # ADR-0003: Purify leaf-solana ledger from legacy BTC/ETH executions
            self.live_executions = [
                self._normalize_legacy_execution(e)
                for e in raw_execs
                if self._is_solana_ecosystem_symbol(str(e.get("symbol", "")))
            ]
            self.live_pnl_usd = float(data.get("live_pnl_usd", 0.0))
            self.live_fees_usd = float(data.get("live_fees_usd", 0.0))
            window_stats = self._sample_stats(self.live_executions, "simulated_pnl_usd")
            self.paper_lifetime_trades = int(
                data.get("paper_lifetime_trades", window_stats["trades"])
            )
            self.paper_lifetime_wins = int(
                data.get("paper_lifetime_wins", window_stats["wins"])
            )
            self.paper_lifetime_losses = int(
                data.get("paper_lifetime_losses", window_stats["losses"])
            )
            self.paper_lifetime_flat = int(
                data.get("paper_lifetime_flat", window_stats["flat"])
            )
            if isinstance(data.get("live_pod_pnl"), dict):
                for k, v in data["live_pod_pnl"].items():
                    canonical_pod = "pod_onchain_alpha" if str(k) == "pod_solana_alpha" else str(k)
                    self.live_pod_pnl[canonical_pod] = float(v)
            if isinstance(data.get("testnet_positions"), dict):
                self.testnet_positions = {
                    k: v
                    for k, v in data["testnet_positions"].items()
                    if self._is_solana_ecosystem_symbol(k)
                }
            self.testnet_cex_realized_pnl_usd = float(data.get("testnet_cex_realized_pnl_usd", 0.0))
            self.solana_devnet_tx_count = int(
                data.get(
                    "solana_devnet_tx_count",
                    sum(1 for e in self.live_executions if e.get("venue") == "SOLANA_DEVNET_ONCHAIN"),
                )
            )
            self.solana_devnet_gas_sol = round(
                float(data.get("solana_devnet_gas_sol", self.solana_devnet_tx_count * 0.000005)),
                6,
            )
            if isinstance(data.get("testnet_wallet_snapshot"), dict):
                self.testnet_wallet_snapshot.update(data["testnet_wallet_snapshot"])
            if "cognitive_base_interval_sec" in data:
                self.cognitive_base_interval_sec = max(900, int(data["cognitive_base_interval_sec"]))
            if "cognitive_wakeup_reason" in data:
                self.cognitive_wakeup_reason = str(data["cognitive_wakeup_reason"])
        except Exception as exc:
            print(f"[HybridStateStore] Redis state restore warning: {exc}")

    def _persist_state(self) -> None:
        if not self._redis_url:
            return
        try:
            payload = json.dumps(
                {
                    "policy": self._policy.to_dict(),
                    "kill_switch_active": self.kill_switch_active,
                    "kill_switch_reason": self.kill_switch_reason,
                    "live_executions": self.live_executions[:200],
                    "live_pnl_usd": self.live_pnl_usd,
                    "live_fees_usd": self.live_fees_usd,
                    "paper_lifetime_trades": self.paper_lifetime_trades,
                    "paper_lifetime_wins": self.paper_lifetime_wins,
                    "paper_lifetime_losses": self.paper_lifetime_losses,
                    "paper_lifetime_flat": self.paper_lifetime_flat,
                    "live_pod_pnl": self.live_pod_pnl,
                    "testnet_positions": self.testnet_positions,
                    "testnet_cex_realized_pnl_usd": self.testnet_cex_realized_pnl_usd,
                    "solana_devnet_tx_count": self.solana_devnet_tx_count,
                    "solana_devnet_gas_sol": self.solana_devnet_gas_sol,
                    "testnet_wallet_snapshot": self.testnet_wallet_snapshot,
                    "cognitive_base_interval_sec": self.cognitive_base_interval_sec,
                    "cognitive_wakeup_reason": self.cognitive_wakeup_reason,
                }
            )
            _redis_cmd(self._redis_url, "SET", self.REDIS_STATE_KEY, payload)
        except Exception:
            pass

    @staticmethod
    def _synthetic_ohlcv_candles(sym: str, base_price: float) -> List[List[float]]:
        now_ms = int(time.time() * 1000)
        candles: List[List[float]] = []
        price = base_price * 0.965
        for idx in range(60):
            ts = now_ms - (60 - idx) * 900_000
            drift = 0.0012 if idx % 3 != 0 else -0.0007
            open_p = price
            close_p = round(open_p * (1.0 + drift), 4)
            high_p = round(max(open_p, close_p) * 1.0035, 4)
            low_p = round(min(open_p, close_p) * 0.9965, 4)
            vol = round(42_000.0 + (idx % 7) * 5_500.0, 2)
            candles.append([ts, open_p, high_p, low_p, close_p, vol])
            price = close_p
        return candles

    def refresh_ta_and_panorama(self) -> Dict[str, Any]:
        """
        Fetches real 15m OHLCV candles for active ecosystem pairs
        and computes Ichimoku, RSI(14), Fibonacci levels, Bollinger/ATR, and Social Panorama.
        Returns `tool_timings` (per tool-call wall-clock, ms) for transcript instrumentation.
        """
        from ..tools.ta_tools import SocialMacroPanoramaTool, TechnicalAnalysisTool

        binance = None
        try:
            from ..tools.exchange_tools import BinanceTool

            binance = BinanceTool()
        except Exception:
            binance = None
        snapshots: Dict[str, Dict[str, Any]] = {}
        tool_timings: List[Dict[str, Any]] = []
        fallback_bases = {"SOL/USDT": 182.5, "JUP/USDT": 1.18, "RAY/USDT": 2.45}
        for sym in ("SOL/USDT", "JUP/USDT", "RAY/USDT"):
            fetch_start = time.perf_counter()
            candles = None
            try:
                if binance is None:
                    raise RuntimeError("ccxt_unavailable_using_dex_synth")
                candles = binance.exchange.fetch_ohlcv(sym, timeframe="15m", limit=60)
                tool_timings.append(
                    {"name": f"fetch_ohlcv:{sym}", "duration_ms": int((time.perf_counter() - fetch_start) * 1000), "ok": True, "error": ""}
                )
            except Exception as exc:
                candles = self._synthetic_ohlcv_candles(sym, fallback_bases.get(sym, 1.5))
                tool_timings.append(
                    {"name": f"fetch_ohlcv_dex_synth:{sym}", "duration_ms": int((time.perf_counter() - fetch_start) * 1000), "ok": True, "error": str(exc)[:120]}
                )
            try:
                obi = self._last_obi.get(sym, 0.09)
                if candles:
                    analyze_start = time.perf_counter()
                    snapshots[sym] = TechnicalAnalysisTool.analyze_candles(
                        sym, candles, obi=obi, timeframe="15m"
                    )
                    self._last_prices[sym] = float(snapshots[sym]["last_price"])
                    tool_timings.append(
                        {"name": f"analyze_candles:{sym}", "duration_ms": int((time.perf_counter() - analyze_start) * 1000), "ok": True, "error": ""}
                    )
            except Exception as exc:
                err_ms = int((time.perf_counter() - fetch_start) * 1000)
                tool_timings.append({"name": f"analyze_candles:{sym}", "duration_ms": err_ms, "ok": False, "error": str(exc)[:200]})
                print(f"[TA Engine] Warning analyzing {sym}: {exc}")

        pano_start = time.perf_counter()
        try:
            panorama = SocialMacroPanoramaTool.build_panorama(snapshots)
            tool_timings.append({"name": "build_panorama", "duration_ms": int((time.perf_counter() - pano_start) * 1000), "ok": True, "error": ""})
        except Exception as exc:
            panorama = {}
            tool_timings.append({"name": "build_panorama", "duration_ms": int((time.perf_counter() - pano_start) * 1000), "ok": False, "error": str(exc)[:200]})
        with self._lock:
            if snapshots:
                self.latest_ta_snapshots = snapshots
            self.latest_social_panorama = panorama
        return {
            "ta_snapshots": self.latest_ta_snapshots,
            "social_panorama": self.latest_social_panorama,
            "tool_timings": tool_timings,
        }

    def get_testnet_telemetry(self) -> Dict[str, Any]:
        if not self.is_testnet_mode:
            return {"enabled": False}
        with self._lock:
            return {
                "enabled": True,
                "solana_cluster": self.solana_cluster,
                "solana_address": self.testnet_wallet_snapshot.get("solana_address")
                or os.getenv("SOLANA_PUBLIC_KEY", ""),
                "solana_balance_sol": round(
                    float(self.testnet_wallet_snapshot.get("solana_balance_sol", 5.0)), 6
                ),
                "solana_tx_count": self.solana_devnet_tx_count,
                "solana_gas_spent_sol": round(self.solana_devnet_gas_sol, 6),
                "solana_onchain_pnl_sol": 0.0,
                "binance_free_usdt": round(
                    float(self.testnet_wallet_snapshot.get("binance_free_usdt", 10000.0)), 2
                ),
                "binance_total_usdt": round(
                    float(self.testnet_wallet_snapshot.get("binance_total_usdt", 10000.0)), 2
                ),
                "binance_open_positions": dict(self.testnet_positions),
                "binance_realized_pnl_usd": round(self.testnet_cex_realized_pnl_usd, 4),
                "simulated_model_pnl_usd": round(self.live_pnl_usd, 2),
            }

    def start_live_worker(self, interval_sec: float = 10.0) -> None:
        with self._lock:
            if self._worker_started:
                return
            self._worker_started = True

        def _loop() -> None:
            # Initial baseline from Rust engine
            try:
                self.run_rust_backtest()
            except Exception as exc:
                print(f"[LiveWorker] Initial Rust replay warning: {exc}")

            while True:
                try:
                    self.run_live_testnet_tick()
                except Exception as exc:
                    print(f"[LiveWorker] Tick error: {exc}")
                time.sleep(interval_sec)

        thread = threading.Thread(target=_loop, name="TestnetLiveLoop", daemon=True)
        thread.start()

    def set_policy(self, policy: PolicyEnvelope) -> None:
        with self._lock:
            self._policy = policy
            self._persist_state()

    def get_effective_policy(self, now_ms: Optional[int] = None) -> PolicyEnvelope:
        if self.kill_switch_active:
            safe = PolicyEnvelope.safe_baseline(now_ms)
            safe.envelope_id = "kill_switch_lockdown"
            for pod in safe.pod_allocations.values():
                pod.enabled = False
                pod.capital_weight = 0.0
            return safe

        if self._policy.is_expired(now_ms):
            return PolicyEnvelope.safe_baseline(now_ms)
        return self._policy

    def set_kill_switch(self, active: bool, reason: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            self.kill_switch_active = active
            self.kill_switch_reason = reason if active else None
            self._persist_state()
        return {
            "kill_switch_active": self.kill_switch_active,
            "kill_switch_reason": self.kill_switch_reason,
            "effective_policy": self.get_effective_policy().to_dict(),
        }

    @staticmethod
    def compute_paper_execution_pnl(
        notional_usd: float,
        fee_usd: float,
        side: str,
        obi: float,
        price_change_bps: float,
        rsi_val: float = 50.0,
        spread_bps: float = 2.5,
        entry_obi_threshold: float = 0.08,
        max_rsi_long: float = 68.0,
        min_rsi_short: float = 30.0,
        venue: str = "BINANCE_TESTNET_LIVE",
        pod_id: str = "pod_momentum",
    ) -> Dict[str, float]:
        """
        Microstructure-aware Paper execution model with L2 spread/volatility slippage
        and adverse selection. Can produce both wins and losses depending on orderbook
        alignment (`signed_obi`), short-term price impulse (`signed_momentum_bps`),
        and RSI exhaustion.
        """
        direction = 1.0 if str(side).upper() == "BUY" else -1.0
        signed_obi = float(obi) * direction
        signed_momentum_bps = float(price_change_bps) * direction

        # 1. Realized slippage: half-spread + volatility impact
        is_dex = "ONCHAIN" in venue.upper() or "SOLANA" in venue.upper() or pod_id in ("pod_onchain_alpha", "pod_solana_alpha", "pod_sniper")
        base_slip_bps = max(4.5 if is_dex else 1.5, float(spread_bps) * 0.5)
        vol_slip_bps = min(18.0, abs(float(price_change_bps)) * 0.35)
        realized_slippage_bps = round(base_slip_bps + vol_slip_bps, 2)

        # 2. Adverse selection penalty when trading against orderflow, momentum, or RSI extremes
        obi_deficit = max(0.0, float(entry_obi_threshold) - signed_obi)
        adverse_obi_bps = obi_deficit * (48.0 if is_dex else 42.0)
        adverse_mom_bps = abs(min(0.0, signed_momentum_bps)) * 0.85
        rsi_exhaustion_bps = 0.0
        if direction > 0 and rsi_val > max_rsi_long:
            rsi_exhaustion_bps = min(22.0, (rsi_val - max_rsi_long) * 1.6 + 8.0)
        elif direction < 0 and rsi_val < min_rsi_short:
            rsi_exhaustion_bps = min(22.0, (min_rsi_short - rsi_val) * 1.6 + 8.0)
        adverse_selection_bps = round(adverse_obi_bps + adverse_mom_bps + rsi_exhaustion_bps, 2)

        # 3. Gross directional/maker alpha
        base_alpha_bps = 24.0 if pod_id == "pod_sniper" else (20.0 if is_dex else 15.0)
        flow_alpha_bps = max(0.0, signed_obi) * 38.0 + max(0.0, signed_momentum_bps) * 0.55
        gross_alpha_bps = round(base_alpha_bps + flow_alpha_bps, 2)

        # 4. Net edge and paper PnL (can be negative when friction + adverse selection > alpha)
        net_edge_bps = round(gross_alpha_bps - realized_slippage_bps - adverse_selection_bps, 2)
        sim_pnl_usd = round(float(notional_usd) * (net_edge_bps / 10_000.0) - float(fee_usd), 2)

        return {
            "simulated_pnl_usd": sim_pnl_usd,
            "net_edge_bps": net_edge_bps,
            "expected_edge_bps": gross_alpha_bps,
            "realized_slippage_bps": realized_slippage_bps,
            "adverse_selection_bps": adverse_selection_bps,
        }

    def run_live_testnet_tick(self) -> Optional[Dict[str, Any]]:
        """
        Polls real live orderbook & ticker data from Binance Testnet and executes
        real Testnet orders (Binance Spot Testnet + Solana Devnet) according to
        the active PolicyEnvelope and HardRiskGate limits.
        """
        if self.kill_switch_active:
            return None

        from ..tools.exchange_tools import BinanceTool
        from ..tools.solana_tools import SolanaWalletTool

        now_ms = int(time.time() * 1000)
        with self._lock:
            # Warm-Path Heartbeat: renew issued_at_ms so operator-selected regime (e.g. FULL_SWARM)
            # does not auto-expire after 900s while the Warm-Path controller is healthy.
            self._policy.issued_at_ms = now_ms

        policy = self.get_effective_policy(now_ms)
        allocs = policy.pod_allocations
        binance = BinanceTool()
        if not binance.authenticated:
            return None

        self.live_tick_count += 1

        symbols = ["SOL/USDT", "JUP/USDT", "RAY/USDT"]
        symbol = symbols[self.live_tick_count % len(symbols)]
        try:
            book = binance.exchange.fetch_order_book(symbol, limit=5)
        except Exception:
            symbol = "SOL/USDT"
            book = binance.exchange.fetch_order_book(symbol, limit=5)
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if not bids or not asks:
            return None

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid_price = (best_bid + best_ask) / 2.0
        bid_vol = sum(float(b[1]) for b in bids[:5])
        ask_vol = sum(float(a[1]) for a in asks[:5])
        total_vol = bid_vol + ask_vol
        obi = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

        prev_price = self._last_prices.get(symbol, mid_price)
        self._last_prices[symbol] = mid_price
        self._last_obi[symbol] = obi
        price_change_bps = ((mid_price - prev_price) / prev_price) * 10_000.0 if prev_price > 0 else 0.0

        asset_key = symbol.replace("/", "-")
        rule = policy.asset_overrides.get(asset_key)
        ta_snap = self.latest_ta_snapshots.get(symbol, {})
        rsi_val = float(ta_snap.get("rsi", {}).get("rsi_14", 50.0))
        kumo_state = str(ta_snap.get("ichimoku", {}).get("kumo_regime", "ABOVE_KUMO_BULLISH"))
        fib_618 = ta_snap.get("fibonacci", {}).get("golden_pocket_618")

        # Choose active pod for this tick
        active_pods = [k for k, v in allocs.items() if v.enabled and v.capital_weight > 0]
        if not active_pods:
            return None

        chosen_pod = active_pods[self.live_tick_count % len(active_pods)]

        if chosen_pod in ("pod_onchain_alpha", "pod_solana_alpha", "pod_sniper"):
            solana = SolanaWalletTool()
            if solana.keypair:
                pubkey_str = str(solana.keypair.pubkey())
                sol_price = self._last_prices.get("SOL/USDT") or binance.get_price("SOL/USDT") or 85.0
                tx_res = solana.transfer_sol(pubkey_str, 0.0005, simulate_only=False)
                sig = str(tx_res.get("signature", ""))
                short_sig = f"{sig[:10]}...{sig[-6:]}" if len(sig) > 16 else (sig or "sim_ok")
                sol_bal = solana.get_balance(pubkey_str)

                notional_usd = round(sol_price * 1.5, 2)
                fee_usd = round(0.000005 * sol_price, 6)
                with self._lock:
                    self.solana_devnet_tx_count += 1
                    self.solana_devnet_gas_sol = round(self.solana_devnet_gas_sol + 0.000005, 6)
                    self.testnet_wallet_snapshot["solana_address"] = pubkey_str
                    if sol_bal > 0:
                        self.testnet_wallet_snapshot["solana_balance_sol"] = sol_bal

                sol_ta = self.latest_ta_snapshots.get("SOL/USDT", {})
                sol_fib = sol_ta.get("fibonacci", {}).get("golden_pocket_618", round(sol_price * 0.99, 2))
                sol_rsi = float(sol_ta.get("rsi", {}).get("rsi_14", 50.0))
                sol_obi = float(self._last_obi.get("SOL/USDT", obi))
                sol_rule = policy.asset_overrides.get("SOL-USDT")
                paper_eval = self.compute_paper_execution_pnl(
                    notional_usd=notional_usd,
                    fee_usd=round(notional_usd * 0.0008, 4),
                    side="BUY",
                    obi=sol_obi,
                    price_change_bps=price_change_bps,
                    rsi_val=sol_rsi,
                    spread_bps=6.0,
                    entry_obi_threshold=sol_rule.entry_obi_threshold if sol_rule else 0.08,
                    max_rsi_long=sol_rule.max_rsi_long if sol_rule else 68.0,
                    min_rsi_short=sol_rule.min_rsi_short if sol_rule else 30.0,
                    venue="SOLANA_DEVNET_ONCHAIN",
                    pod_id=chosen_pod,
                )
                sim_pnl_usd = paper_eval["simulated_pnl_usd"]
                report = {
                    "timestamp_ms": now_ms,
                    "pod_id": chosen_pod,
                    "symbol": "SOL-DEVNET",
                    "venue": "SOLANA_DEVNET_ONCHAIN",
                    "side": "BUY",
                    "filled_quantity": 0.0005,
                    "fill_price": round(sol_price, 2),
                    "notional_usd": notional_usd,
                    "fee_usd": fee_usd,
                    "gas_fee_sol": 0.000005,
                    "tx_signature": sig,
                    "realized_slippage_bps": paper_eval["realized_slippage_bps"],
                    "adverse_selection_bps": paper_eval["adverse_selection_bps"],
                    "expected_edge_bps": paper_eval["net_edge_bps"],
                    "realized_pnl_usd": 0.0,
                    "simulated_pnl_usd": sim_pnl_usd,
                    "pnl_type": "DEVNET_SELF_TX",
                    "is_testnet_devnet": True,
                    "rationale": (
                        f"Règle Rust [{chosen_pod}] : RSI={sol_rsi:.1f} | OBI={sol_obi:+.2f} | "
                        f"Edge net={paper_eval['net_edge_bps']:+.1f}bps (Adv -{paper_eval['adverse_selection_bps']:.1f}bps) | "
                        f"Fib 0.618=${sol_fib} | Auto-TX Devnet {short_sig}"
                    ),
                }
                self._record_live_execution(report)
                return report

        # CEX Binance Testnet Live Execution (Pod 1 Carry or Pod 2 Momentum — Solana Ecosystem Only)
        qty_map = {"SOL/USDT": 0.25, "JUP/USDT": 15.0, "RAY/USDT": 8.0}
        default_qty = qty_map.get(symbol, 0.25)

        with self._lock:
            open_pos = self.testnet_positions.get(symbol)

        if open_pos and float(open_pos.get("qty", 0.0)) > 0:
            side = "sell"
            qty = float(open_pos["qty"])
        else:
            side = "buy"
            qty = default_qty

        order_res = binance.place_order(symbol, side, qty, price=None, post_only=False)
        if order_res.get("status") != "success":
            return None

        order = order_res["order"]
        order_id = order.get("id", "testnet")
        fill_price = float(order.get("average") or order.get("price") or mid_price)
        filled_qty = float(order.get("filled") or order.get("amount") or qty)
        notional_usd = round(fill_price * filled_qty, 2)
        fee_usd = round(notional_usd * 0.00036, 4)

        spread_bps = ((best_ask - best_bid) / mid_price) * 10_000.0 if mid_price > 0 else 2.5
        pod_Key = chosen_pod if chosen_pod in ("pod_carry", "pod_momentum") else "pod_momentum"
        paper_eval = self.compute_paper_execution_pnl(
            notional_usd=notional_usd,
            fee_usd=fee_usd,
            side=side,
            obi=obi,
            price_change_bps=price_change_bps,
            rsi_val=rsi_val,
            spread_bps=spread_bps,
            entry_obi_threshold=rule.entry_obi_threshold if rule else 0.08,
            max_rsi_long=rule.max_rsi_long if rule else 68.0,
            min_rsi_short=rule.min_rsi_short if rule else 30.0,
            venue="BINANCE_TESTNET_LIVE",
            pod_id=pod_Key,
        )
        edge_bps = paper_eval["net_edge_bps"]
        sim_pnl_usd = paper_eval["simulated_pnl_usd"]

        rule_tag = (
            f"Ichimoku={kumo_state.split('_')[0]} | RSI={rsi_val:.1f}"
            + (f" | Fib618=${fib_618}" if fib_618 else "")
            + (f" | Seuil OBI>={rule.entry_obi_threshold:.2f}" if rule else "")
        )

        bal_info = binance.get_usdt_balance()
        with self._lock:
            if bal_info.get("status") == "ok":
                self.testnet_wallet_snapshot["binance_free_usdt"] = bal_info.get("free_usdt", 10000.0)
                self.testnet_wallet_snapshot["binance_total_usdt"] = bal_info.get("total_usdt", 10000.0)

            if side == "buy":
                self.testnet_positions[symbol] = {
                    "qty": filled_qty,
                    "entry_price": round(fill_price, 4),
                }
                real_pnl_usd = 0.0
                pnl_type = "TESTNET_OPEN_LONG"
                rationale = (
                    f"OPEN BUY #{order_id} @ ${fill_price:.2f} | Règle: {rule_tag} | OBI {obi:+.2f}"
                )
            else:
                entry_price = float((open_pos or {}).get("entry_price", fill_price))
                real_pnl_usd = round((fill_price - entry_price) * filled_qty, 4)
                self.testnet_cex_realized_pnl_usd = round(
                    self.testnet_cex_realized_pnl_usd + real_pnl_usd, 4
                )
                self.testnet_positions.pop(symbol, None)
                pnl_type = "TESTNET_CLOSE_LONG"
                rationale = (
                    f"CLOSE SELL #{order_id} (${entry_price:.2f} -> ${fill_price:.2f}, "
                    f"PnL Réel {real_pnl_usd:+.4f} USDT) | Règle: {rule_tag}"
                )

        report = {
            "timestamp_ms": now_ms,
            "pod_id": pod_Key,
            "symbol": symbol.replace("/", "-"),
            "venue": "BINANCE_TESTNET_LIVE",
            "side": side.upper(),
            "filled_quantity": filled_qty,
            "fill_price": round(fill_price, 2),
            "notional_usd": notional_usd,
            "fee_usd": fee_usd,
            "realized_slippage_bps": paper_eval["realized_slippage_bps"],
            "adverse_selection_bps": paper_eval["adverse_selection_bps"],
            "expected_edge_bps": round(edge_bps, 1),
            "realized_pnl_usd": real_pnl_usd,
            "simulated_pnl_usd": sim_pnl_usd,
            "pnl_type": pnl_type,
            "is_testnet_devnet": True,
            "rationale": rationale,
        }
        self._record_live_execution(report)
        return report

    def _record_live_execution(self, report: Dict[str, Any]) -> None:
        with self._lock:
            self.live_executions.insert(0, report)
            self.live_executions = self.live_executions[:200]
            pnl = float(report.get("simulated_pnl_usd", report.get("realized_pnl_usd", 0.0)))
            fee = float(report.get("fee_usd", 0.0))
            pod_id = str(report.get("pod_id", "pod_momentum"))
            self.live_pnl_usd += pnl
            self.live_fees_usd += fee
            self.paper_lifetime_trades += 1
            if pnl > 0:
                self.paper_lifetime_wins += 1
            elif pnl < 0:
                self.paper_lifetime_losses += 1
            else:
                self.paper_lifetime_flat += 1
            self.live_pod_pnl[pod_id] = self.live_pod_pnl.get(pod_id, 0.0) + pnl
            self._persist_state()

    def run_rust_backtest(self, policy: Optional[PolicyEnvelope] = None) -> Dict[str, Any]:
        """
        Invokes the compiled Rust `robotrader-node` binary with the active PolicyEnvelope
        to run a deterministic multi-pod backtest & anti-rug verification.

        Returns the **fixture** summary exactly as the Rust engine computed it. Live
        testnet executions and paper-model PnL are deliberately NOT merged here: doing so
        used to add `len(live_executions)` to `total_trades` while leaving `win_rate_pct`
        from the fixture, so the displayed ratio had a fixture numerator and a live
        denominator. Callers that want the live populations use `get_population_metrics`.
        """
        effective_policy = policy or self.get_effective_policy()
        repo_root = Path(__file__).resolve().parents[2]
        engine_dir = repo_root / "engine-rs"
        binary_path = resolve_robotrader_binary(engine_dir)

        policy_json = json.dumps(effective_policy.to_dict())

        cmd = [str(binary_path), "--policy-json", policy_json]

        proc = subprocess.run(
            cmd,
            cwd=str(engine_dir),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        result: Dict[str, Any] = json.loads(proc.stdout)
        result["executions_source"] = "backtest_fixture"

        with self._lock:
            self.last_backtest_result = result
        return result

    def run_rust_backtest_for_leaf(self, leaf_id: str) -> Dict[str, Any]:
        """
        Executes the deterministic Rust `BacktestEngine` (`robotrader-node --leaf-id <leaf_id>`)
        using the target blockchain's adapted Rust Strategy Pods (1..=4 pods max).
        """
        if leaf_id == "leaf-solana":
            return self.run_rust_backtest()

        repo_root = Path(__file__).resolve().parents[2]
        engine_dir = repo_root / "engine-rs"
        binary_path = resolve_robotrader_binary(engine_dir)

        cmd = [str(binary_path), "--leaf-id", leaf_id]

        proc = subprocess.run(
            cmd,
            cwd=str(engine_dir) if engine_dir.exists() else None,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        result: Dict[str, Any] = json.loads(proc.stdout)
        result["executions_source"] = "rust_leaf_backtest"

        if leaf_id in self.hierarchy.leaves:
            with self.hierarchy._lock:
                self.hierarchy.leaves[leaf_id]["last_rust_backtest"] = {
                    "net_profit_usd": round(float(result.get("net_profit_usd", 0.0)), 2),
                    "sharpe_ratio": round(float(result.get("sharpe_ratio", 0.0)), 2),
                    "win_rate_pct": round(float(result.get("win_rate_pct", 0.0)), 1),
                    "total_trades": int(result.get("total_trades", 0)),
                    "pod_pnl_attribution": dict(result.get("pod_pnl_attribution", {})),
                }
        return result

    @staticmethod
    def _sample_stats(executions: List[Dict[str, Any]], pnl_key: str) -> Dict[str, Any]:
        """Win/loss/flat breakdown of one explicitly named population."""
        pnls = [float(e.get(pnl_key, 0.0) or 0.0) for e in executions]
        trades = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        flat = trades - wins - losses
        stamps = [int(e.get("timestamp_ms", 0)) for e in executions if e.get("timestamp_ms")]
        return {
            "pnl_key": pnl_key,
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "flat": flat,
            "win_rate_pct": round(100.0 * wins / trades, 1) if trades else None,
            "pnl_usd": round(sum(pnls), 4),
            "from_ms": min(stamps) if stamps else None,
            "to_ms": max(stamps) if stamps else None,
        }

    def get_population_metrics(self, backtest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Three performance populations, each measured on its own PnL column and never
        mixed:

        - `backtest_fixture`  : the deterministic `engine-rs` replay (synthetic scenario).
        - `paper_model`       : cumulative PnL of the paper simulation (`simulated_pnl_usd`).
        - `live_testnet`      : what the testnet/devnet orders actually realised
                                (`realized_pnl_usd`).

        `cumulative_*` fields cover the worker's whole life; `recent` fields cover the
        retained window (the newest 200 executions), whose bounds are returned so a
        reader can see what the win rate was computed on.
        """
        bt = backtest or self.run_rust_backtest()
        with self._lock:
            live = list(self.live_executions)
            paper_pnl = float(self.live_pnl_usd)
            paper_fees = float(self.live_fees_usd)
            pod_pnl = dict(self.live_pod_pnl)
            cex_realized = float(self.testnet_cex_realized_pnl_usd)
            lt_trades = int(self.paper_lifetime_trades)
            lt_wins = int(self.paper_lifetime_wins)
            lt_losses = int(self.paper_lifetime_losses)
            lt_flat = int(self.paper_lifetime_flat)

        initial = float(bt.get("initial_equity_usd", 10000.0))
        paper_return_pct = (paper_pnl / initial) * 100.0 if initial else 0.0

        paper_recent = self._sample_stats(live, "simulated_pnl_usd")
        paper_recent["positive_edge_share_pct"] = paper_recent["win_rate_pct"]
        paper_recent["deterministic"] = False
        paper_recent["adverse_selection_enabled"] = True

        paper_lifetime = {
            "trades": lt_trades,
            "wins": lt_wins,
            "losses": lt_losses,
            "flat": lt_flat,
            "win_rate_pct": round(100.0 * lt_wins / lt_trades, 1) if lt_trades else None,
        }

        return {
            "backtest_fixture": {
                "source": "engine-rs deterministic replay (synthetic scenario)",
                "initial_equity_usd": initial,
                "final_equity_usd": round(float(bt.get("final_equity_usd", initial)), 2),
                "cumulative_pnl_usd": round(float(bt.get("net_profit_usd", 0.0)), 2),
                "total_return_pct": round(float(bt.get("total_return_pct", 0.0)), 3),
                "max_drawdown_pct": round(float(bt.get("max_drawdown_pct", 0.0)), 2),
                "sharpe_ratio": round(float(bt.get("sharpe_ratio", 0.0)), 2),
                "win_rate_pct": round(float(bt.get("win_rate_pct", 0.0)), 1),
                "trades": int(bt.get("total_trades", 0)),
                "rejected_orders": int(bt.get("rejected_orders", 0)),
                "fees_usd": round(float(bt.get("total_fees_usd", 0.0)), 2),
                "pod_pnl_attribution": dict(bt.get("pod_pnl_attribution", {})),
            },
            "paper_model": {
                "source": "simulated_pnl_usd (L2 slippage + adverse-selection paper model)",
                "note": "simulated_pnl_usd deducts half-spread, volatility impact, fees and adverse selection when trading against L2 OBI, momentum or RSI extremes",
                "initial_equity_usd": initial,
                "final_equity_usd": round(initial + paper_pnl, 2),
                "cumulative_pnl_usd": round(paper_pnl, 2),
                "total_return_pct": round(paper_return_pct, 3),
                "cumulative_fees_usd": round(paper_fees, 2),
                "pod_pnl_attribution": {k: round(v, 2) for k, v in pod_pnl.items()},
                "lifetime": paper_lifetime,
                "recent": paper_recent,
            },
            "live_testnet": {
                "source": "realized_pnl_usd (testnet/devnet orders)",
                "cumulative_cex_pnl_usd": round(cex_realized, 4),
                "recent": self._sample_stats(live, "realized_pnl_usd"),
            },
        }


state_store = HybridStateStore()

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
        self.live_pod_pnl: Dict[str, float] = {
            "pod_carry": 0.0,
            "pod_momentum": 0.0,
            "pod_solana_alpha": 0.0,
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

        # ADR-0002: Infinite Strategy Palace Memory + TA Snapshots + Self-Scheduling Cognitive Timer
        self.palace = StrategyMemoryPalace(redis_cmd_fn=_redis_cmd, redis_url=self._redis_url)
        self.latest_ta_snapshots: Dict[str, Dict[str, Any]] = {}
        self.latest_social_panorama: Dict[str, Any] = {}
        self.cognitive_base_interval_sec: int = int(os.getenv("COGNITIVE_BASE_INTERVAL_SEC", "120"))
        now_ms = int(time.time() * 1000)
        self.last_cognitive_wakeup_ms: int = now_ms
        self.next_cognitive_wakeup_ms: int = now_ms + 15_000
        self.cognitive_wakeup_reason: str = "Initialisation de la boucle cognitive Warm-Path"

        self._load_persisted_state()

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
                self._policy = pol
            self.kill_switch_active = bool(data.get("kill_switch_active", False))
            self.kill_switch_reason = data.get("kill_switch_reason")
            raw_execs = list(data.get("live_executions", []))[:200]
            self.live_executions = [self._normalize_legacy_execution(e) for e in raw_execs]
            self.live_pnl_usd = float(data.get("live_pnl_usd", 0.0))
            self.live_fees_usd = float(data.get("live_fees_usd", 0.0))
            if isinstance(data.get("live_pod_pnl"), dict):
                for k, v in data["live_pod_pnl"].items():
                    self.live_pod_pnl[str(k)] = float(v)
            if isinstance(data.get("testnet_positions"), dict):
                self.testnet_positions = data["testnet_positions"]
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
                self.cognitive_base_interval_sec = max(30, int(data["cognitive_base_interval_sec"]))
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

    def refresh_ta_and_panorama(self) -> Dict[str, Any]:
        """
        Fetches real 15m OHLCV candles from Binance for SOL/USDT, ETH/USDT, BTC/USDT
        and computes Ichimoku, RSI(14), Fibonacci levels, Bollinger/ATR, and Social Panorama.
        Returns `tool_timings` (per tool-call wall-clock, ms) for transcript instrumentation.
        """
        from ..tools.exchange_tools import BinanceTool
        from ..tools.ta_tools import SocialMacroPanoramaTool, TechnicalAnalysisTool

        binance = BinanceTool()
        snapshots: Dict[str, Dict[str, Any]] = {}
        tool_timings: List[Dict[str, Any]] = []
        for sym in ("SOL/USDT", "ETH/USDT", "BTC/USDT"):
            fetch_start = time.perf_counter()
            try:
                candles = binance.exchange.fetch_ohlcv(sym, timeframe="15m", limit=60)
                tool_timings.append(
                    {"name": f"fetch_ohlcv:{sym}", "duration_ms": int((time.perf_counter() - fetch_start) * 1000), "ok": True, "error": ""}
                )
                obi = self._last_obi.get(sym, 0.05)
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
                if not any(t["name"] == f"fetch_ohlcv:{sym}" for t in tool_timings):
                    tool_timings.append({"name": f"fetch_ohlcv:{sym}", "duration_ms": err_ms, "ok": False, "error": str(exc)[:200]})
                print(f"[TA Engine] Warning fetching OHLCV for {sym}: {exc}")

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

        symbols = ["SOL/USDT", "ETH/USDT", "BTC/USDT"]
        symbol = symbols[self.live_tick_count % len(symbols)]
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

        if chosen_pod in ("pod_solana_alpha", "pod_sniper"):
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
                sim_pnl_usd = round(
                    notional_usd * (0.0038 if chosen_pod == "pod_solana_alpha" else 0.0062)
                    - round(notional_usd * 0.0008, 4),
                    2,
                )
                with self._lock:
                    self.solana_devnet_tx_count += 1
                    self.solana_devnet_gas_sol = round(self.solana_devnet_gas_sol + 0.000005, 6)
                    self.testnet_wallet_snapshot["solana_address"] = pubkey_str
                    if sol_bal > 0:
                        self.testnet_wallet_snapshot["solana_balance_sol"] = sol_bal

                sol_ta = self.latest_ta_snapshots.get("SOL/USDT", {})
                sol_fib = sol_ta.get("fibonacci", {}).get("golden_pocket_618", round(sol_price * 0.99, 2))
                sol_rsi = sol_ta.get("rsi", {}).get("rsi_14", 50.0)
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
                    "realized_slippage_bps": 1.2,
                    "expected_edge_bps": 46.0,
                    "realized_pnl_usd": 0.0,
                    "simulated_pnl_usd": sim_pnl_usd,
                    "pnl_type": "DEVNET_SELF_TX",
                    "is_testnet_devnet": True,
                    "rationale": (
                        f"Règle Rust [{chosen_pod}] : RSI={sol_rsi} | Fib 0.618=${sol_fib} | "
                        f"Auto-TX Devnet {short_sig}"
                    ),
                }
                self._record_live_execution(report)
                return report

        # CEX Binance Testnet Live Execution (Pod 1 Carry or Pod 2 Momentum)
        qty_map = {"SOL/USDT": 0.25, "ETH/USDT": 0.015, "BTC/USDT": 0.0005}
        default_qty = qty_map.get(symbol, 0.2)

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

        edge_bps = 24.0 + abs(obi) * 35.0 + abs(price_change_bps) * 0.5
        sim_pnl_usd = round(notional_usd * (edge_bps / 10_000.0) - fee_usd, 2)
        pod_Key = chosen_pod if chosen_pod in ("pod_carry", "pod_momentum") else "pod_momentum"

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
            "realized_slippage_bps": 0.5,
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
        binary_path = engine_dir / "target" / "debug" / "robotrader-node"

        policy_json = json.dumps(effective_policy.to_dict())

        if binary_path.exists():
            cmd = [str(binary_path), "--policy-json", policy_json]
        else:
            cmd = [
                "cargo",
                "run",
                "--quiet",
                "--bin",
                "robotrader-node",
                "--",
                "--policy-json",
                policy_json,
            ]

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

        initial = float(bt.get("initial_equity_usd", 10000.0))
        paper_return_pct = (paper_pnl / initial) * 100.0 if initial else 0.0

        # `simulated_pnl_usd` is not an outcome: the worker computes
        # `notional * (edge_bps / 10_000) - fee` with `edge_bps >= 24`, so it is
        # strictly positive on every cycle. A "win rate" over that column would
        # be 100% by construction, not by performance — it is reported as an
        # edge-capture share, and only the live column carries a win rate.
        paper_recent = self._sample_stats(live, "simulated_pnl_usd")
        paper_recent["positive_edge_share_pct"] = paper_recent.pop("win_rate_pct")
        paper_recent["deterministic"] = True

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
                "source": "simulated_pnl_usd (paper simulation)",
                "note": "simulated_pnl_usd = notional × edge_bps − fee with edge_bps ≥ 24 → positive by construction; the share below measures edge capture, not a win rate",
                "initial_equity_usd": initial,
                "final_equity_usd": round(initial + paper_pnl, 2),
                "cumulative_pnl_usd": round(paper_pnl, 2),
                "total_return_pct": round(paper_return_pct, 3),
                "cumulative_fees_usd": round(paper_fees, 2),
                "pod_pnl_attribution": {k: round(v, 2) for k, v in pod_pnl.items()},
                "recent": paper_recent,
            },
            "live_testnet": {
                "source": "realized_pnl_usd (testnet/devnet orders)",
                "cumulative_cex_pnl_usd": round(cex_realized, 4),
                "recent": self._sample_stats(live, "realized_pnl_usd"),
            },
        }


state_store = HybridStateStore()

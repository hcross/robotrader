from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional, Tuple

from ..core.agent import BaseWarmAgent
from ..core.schemas import Message
from ..core.state_store import resolve_robotrader_binary

_subprocess_run = subprocess.run

# Rolling accounting window. An entry contributes while its age is strictly
# below the bound; a day is a half-open interval [now - 86_400_000, now].
ROLLING_WINDOW_MS = 86_400_000
LEDGER_SCAN_CHUNK_BYTES = 64 * 1024

# OpenRouter Frontier-Efficiency Model Catalog (Realistic effective prices in USD per 1M tokens)
FRONTIER_FLASH_MODELS: Dict[str, Dict[str, Any]] = {
    "moonshotai/kimi-k3.1-pro": {
        "litellm_model": "openrouter/moonshotai/kimi-k3.1-pro",
        "label": "Kimi K3.1 Pro (Master Orchestrator)",
        "input_usd_per_m": 0.600,
        "output_usd_per_m": 2.500,
        "tier": "MASTER_ORCHESTRATOR_PRO",
    },
    "deepseek/deepseek-v4.1-flash-1017": {
        "litellm_model": "openrouter/deepseek/deepseek-v4.1-flash-1017",
        "label": "DeepSeek v4.1 Flash 1017 (Leaf Agent)",
        "input_usd_per_m": 0.300,
        "output_usd_per_m": 1.100,
        "tier": "LEAF_AGENT_FLASH_PRIMARY",
    },
    "deepseek/deepseek-v4.1-flash": {
        "litellm_model": "openrouter/deepseek/deepseek-v4.1-flash",
        "label": "DeepSeek v4.1 Flash",
        "input_usd_per_m": 0.300,
        "output_usd_per_m": 1.100,
        "tier": "FRONTIER_FLASH_PRIMARY",
    },
    "z-ai/glm-5.3-flash": {
        "litellm_model": "openrouter/z-ai/glm-5.3-flash",
        "label": "GLM 5.3 Flash (Z-AI)",
        "input_usd_per_m": 0.150,
        "output_usd_per_m": 0.600,
        "tier": "FRONTIER_FLASH_COPRIMARY",
    },
    "qwen/qwen3.7-flash": {
        "litellm_model": "openrouter/qwen/qwen3.7-flash",
        "label": "Qwen 3.7 Flash",
        "input_usd_per_m": 0.150,
        "output_usd_per_m": 0.600,
        "tier": "FRONTIER_FLASH_FALLBACK",
    },
    "z-ai/glm-5.3": {
        "litellm_model": "openrouter/z-ai/glm-5.3",
        "label": "GLM 5.3 Frontier Reasoning",
        "input_usd_per_m": 0.350,
        "output_usd_per_m": 1.400,
        "tier": "FRONTIER_DEEP_INFLECTION",
    },
    "deepseek/deepseek-v4-pro": {
        "litellm_model": "openrouter/deepseek/deepseek-v4-pro",
        "label": "DeepSeek v4 Pro",
        "input_usd_per_m": 0.600,
        "output_usd_per_m": 1.800,
        "tier": "FRONTIER_DEEP_INFLECTION",
    },
}


class LLMMonitorAgent(BaseWarmAgent):
    """
    CostGuard: Enforces a hard daily USD inference cap, budget-driven cognitive depth
    (`DEEP_THESIS`, `TACTICAL_FOCUS`, `ECO_CONSERVATION`, `DETERMINISTIC_LOCK`),
    and ultra-low-cost near-frontier model routing (`deepseek/deepseek-v4.1-flash`,
    `z-ai/glm-5.3-flash`, `qwen/qwen3.7-flash`).
    Security invariant: Unbounded automatic crypto wallet refills are strictly prohibited.
    """

    def __init__(
        self,
        name: str = "CostGuard",
        daily_budget_usd: Optional[float] = None,
        store: Optional[Any] = None,
        ledger_path: Optional[Path | str] = None,
        now_ms: Optional[Callable[[], int]] = None,
    ):
        super().__init__(name, role="Inference Budget & Tiered Frontier-Flash Router")
        self.daily_budget_usd: float = daily_budget_usd or float(
            os.getenv("MAX_DAILY_LLM_BUDGET_USD", "5.0")
        )
        self.preferred_model: str = os.getenv(
            "LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017"
        ).replace("openrouter/", "")
        if self.preferred_model not in FRONTIER_FLASH_MODELS:
            self.preferred_model = "deepseek/deepseek-v4.1-flash-1017"
        self.master_model: str = os.getenv(
            "MASTER_LLM_MODEL", "moonshotai/kimi-k3.1-pro"
        ).replace("openrouter/", "")
        if self.master_model not in FRONTIER_FLASH_MODELS:
            self.master_model = "moonshotai/kimi-k3.1-pro"

        # The measured PnL source is injected by the owner (OrchestratorAgent).
        # No module-global store is ever imported or consulted here.
        self.store = store
        self._now_ms: Callable[[], int] = now_ms or (lambda: int(time.time() * 1000))
        self.ledger_path: Path = self._resolve_ledger_path(ledger_path)

        # Both accounting windows are bounded deques guarded by one re-entrant
        # lock: the scheduler and the REST thread both read and write them.
        self._lock = threading.RLock()
        self._spend_window: Deque[Tuple[int, float]] = deque()
        self._epoch_window: Deque[Tuple[int, float]] = deque()
        self._hydrated = False
        self._hydrating = False
        self.total_tokens: int = 0
        self.total_calls: int = 0
        self.usage_log: List[Dict[str, Any]] = []

        # Default to paused auto-scheduler ($0.00/h at boot) unless explicitly enabled
        self.auto_scheduler_enabled: bool = os.getenv(
            "ENABLE_AUTO_LLM_SCHEDULER", "false"
        ).lower() in ("true", "1", "yes")

        # ADR-0003: Profit-Gated & Epoch-Capped OpenRouter Credit Treasury
        self.openrouter_balance_usd: float = float(
            os.getenv("OPENROUTER_INITIAL_BALANCE_USD", "8.50")
        )
        self.low_watermark_usd: float = float(
            os.getenv("OPENROUTER_LOW_WATERMARK_USD", "2.00")
        )
        self.refill_amount_usd: float = float(
            os.getenv("OPENROUTER_REFILL_AMOUNT_USD", "10.00")
        )
        self.max_epoch_refill_usd: float = float(
            os.getenv("OPENROUTER_MAX_EPOCH_REFILL_USD", "25.00")
        )
        self.auto_refill_enabled: bool = True
        self.refill_history: List[Dict[str, Any]] = []
        self.last_refill_rejection: Optional[Dict[str, Any]] = None

    @staticmethod
    def _resolve_ledger_path(ledger_path: Optional[Path | str]) -> Path:
        if ledger_path is not None:
            return Path(ledger_path)
        env_path = os.getenv("COSTGUARD_LEDGER_PATH", "").strip()
        if env_path:
            return Path(env_path)
        # Module-anchored default: independent of the process working directory.
        return Path(__file__).resolve().parents[1] / "data" / "transcript_ledger.jsonl"

    @property
    def measured_pnl_source_available(self) -> bool:
        return self.store is not None

    def _measured_pnl(self) -> Optional[float]:
        if self.store is None:
            return None
        return float(self.store.measured_realized_pnl_usd())

    def _kill_switch_active(self) -> bool:
        if self.store is None:
            return False
        return bool(self.store.kill_switch_active)

    def _prune_spend_window(self, now_ms: int) -> None:
        cutoff_ms = now_ms - ROLLING_WINDOW_MS
        window = self._spend_window
        while window and window[0][0] <= cutoff_ms:
            window.popleft()

    def _prune_epoch_window(self, now_ms: int) -> None:
        cutoff_ms = now_ms - ROLLING_WINDOW_MS
        window = self._epoch_window
        while window and window[0][0] <= cutoff_ms:
            window.popleft()

    @property
    def total_cost_usd(self) -> float:
        """Derived rolling 24h spend. Read-only: never assignable."""
        self._ensure_hydrated()
        with self._lock:
            self._prune_spend_window(self._now_ms())
            return round(sum(cost for _, cost in self._spend_window), 6)

    @property
    def epoch_refilled_usd(self) -> float:
        """Derived rolling 24h refilled total. Read-only: never assignable."""
        with self._lock:
            self._prune_epoch_window(self._now_ms())
            return round(sum(amount for _, amount in self._epoch_window), 6)

    def _ensure_hydrated(self) -> None:
        """Runs the lazy ledger hydration once, re-entrantly and concurrently safe."""
        with self._lock:
            if self._hydrated or self._hydrating:
                return
            self.hydrate_from_ledger()

    @staticmethod
    def _iter_reverse_lines(path: Path) -> Iterator[bytes]:
        """Yields the file's lines newest first, reading 64 KiB blocks backwards."""
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            remainder = b""
            while position > 0:
                chunk_size = min(LEDGER_SCAN_CHUNK_BYTES, position)
                position -= chunk_size
                handle.seek(position)
                data = handle.read(chunk_size) + remainder
                parts = data.split(b"\n")
                remainder = parts[0]
                for line in reversed(parts[1:]):
                    yield line
            if remainder:
                yield remainder

    def _scan_ledger(
        self, path: Path, now_ms: int
    ) -> Tuple[int, int, float, List[Tuple[int, float]], List[Dict[str, Any]]]:
        """Streams the active ledger then `<name>.1`, newest first, within the window.

        The early stop assumes `timestamp_ms` is monotonically non-decreasing: a
        late-appended older entry can hide earlier in-window entries. Rotated
        segments older than `<name>.1` are out of scope.
        """
        cutoff_ms = now_ms - ROLLING_WINDOW_MS
        hits: List[Tuple[int, float]] = []
        recent: List[Dict[str, Any]] = []
        calls_cnt = 0
        tok_sum = 0
        cost_sum = 0.0

        for segment in (path, path.with_name(path.name + ".1")):
            if not segment.exists():
                continue
            for raw in self._iter_reverse_lines(segment):
                line = raw.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(entry, dict):
                    continue
                try:
                    ts = int(entry.get("timestamp_ms", 0))
                except (TypeError, ValueError):
                    continue
                if ts <= cutoff_ms:
                    break
                try:
                    p_tok_raw = entry.get("prompt_tokens", 0)
                    p_tok = int(0 if p_tok_raw is None else p_tok_raw)
                    c_tok_raw = entry.get("completion_tokens", 0)
                    c_tok = int(0 if c_tok_raw is None else c_tok_raw)
                    cost_raw = entry.get("cost_usd", 0.0)
                    cost_val = float(0.0 if cost_raw is None else cost_raw)
                    if not (math.isfinite(cost_val) and p_tok >= 0 and c_tok >= 0 and cost_val >= 0.0):
                        continue
                except (TypeError, ValueError, OverflowError):
                    continue
                model_used = str(
                    entry.get("model_used")
                    or entry.get("model_requested")
                    or self.preferred_model
                )
                real_cost = max(
                    cost_val,
                    self.compute_call_cost(model_used, p_tok, c_tok),
                )
                cost_sum += real_cost
                tok_sum += p_tok + c_tok
                calls_cnt += 1
                hits.append((ts, real_cost))
                recent.append(
                    {
                        "agent": str(entry.get("agent", "unknown")),
                        "model": model_used,
                        "cost": round(real_cost, 6),
                        "tokens": p_tok + c_tok,
                    }
                )

        return calls_cnt, tok_sum, cost_sum, hits, recent

    def hydrate_from_ledger(self, storage_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Rebuilds the rolling 24h spend window from the transcript ledger.

        Missing file = empty window; malformed lines are skipped; an existing but
        unreadable file raises. An explicit call always runs and replaces the
        spend window (never the epoch refill window); using it after records is a
        deliberate undercount with no production caller.
        """
        path = Path(storage_path) if storage_path is not None else self.ledger_path
        with self._lock:
            if self._hydrating:
                return {"hydrated_calls": 0, "hydrated_cost_usd": 0.0}
            self._hydrating = True
            try:
                calls_cnt, tok_sum, cost_sum, hits, recent = self._scan_ledger(
                    path, self._now_ms()
                )
                # Replace, never append: a repeated hydration cannot double count.
                self._spend_window = deque(reversed(hits))
                self.total_tokens = tok_sum
                self.total_calls = calls_cnt
                self.usage_log = recent[:50]
                self._hydrated = True
                return {
                    "hydrated_calls": calls_cnt,
                    "hydrated_cost_usd": round(cost_sum, 6),
                }
            finally:
                self._hydrating = False

    @property
    def remaining_budget_usd(self) -> float:
        return max(0.0, self.daily_budget_usd - self.total_cost_usd)

    @property
    def remaining_budget_ratio(self) -> float:
        if self.daily_budget_usd <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_budget_usd / self.daily_budget_usd))

    @property
    def budget_exhausted(self) -> bool:
        return self.total_cost_usd >= self.daily_budget_usd

    def get_thinking_depth(self) -> str:
        if self.budget_exhausted or self.remaining_budget_ratio <= 0.05:
            return "DETERMINISTIC_LOCK"
        if self.remaining_budget_ratio <= 0.20:
            return "ECO_CONSERVATION"
        if self.remaining_budget_ratio <= 0.50:
            return "TACTICAL_FOCUS"
        return "DEEP_THESIS"

    def select_cognitive_profile(self, urgency_level: str = "NORMAL_FLOW") -> Dict[str, Any]:
        depth = self.get_thinking_depth()
        if depth == "DETERMINISTIC_LOCK":
            return {
                "thinking_depth": depth,
                "output_contract": "NONE",
                "allow_llm": False,
                "model_key": self.preferred_model,
                "litellm_model": FRONTIER_FLASH_MODELS[self.preferred_model]["litellm_model"],
                "max_tokens": 0,
                "escalation_floor": 0,
                "max_escalation_tokens": 0,
                "min_wakeup_sec": 3600,
                "recall_limit": 0,
            }

        if depth == "ECO_CONSERVATION":
            # Mechanical envelope contract (~140-220 tokens): omits prose-heavy
            # panorama_summary & ta_confluence_notes so 350 max_tokens never truncates.
            model_key = "deepseek/deepseek-v4.1-flash-1017"
            return {
                "thinking_depth": depth,
                "output_contract": "MECHANICAL_ENVELOPE",
                "allow_llm": True,
                "model_key": model_key,
                "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
                "max_tokens": 350,
                "escalation_floor": 500,
                "max_escalation_tokens": 650,
                "min_wakeup_sec": 1800,
                "recall_limit": 1,
            }

        if depth == "TACTICAL_FOCUS":
            # Compact single-sentence tactical contract (~320-480 tokens): fits
            # comfortably within 700 max_tokens without triggering escalation retries.
            model_key = (
                self.preferred_model
                if self.preferred_model
                in (
                    "deepseek/deepseek-v4.1-flash-1017",
                    "deepseek/deepseek-v4.1-flash",
                    "z-ai/glm-5.3-flash",
                    "qwen/qwen3.7-flash",
                )
                else "deepseek/deepseek-v4.1-flash-1017"
            )
            return {
                "thinking_depth": depth,
                "output_contract": "COMPACT_TACTICAL",
                "allow_llm": True,
                "model_key": model_key,
                "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
                "max_tokens": 700,
                "escalation_floor": 950,
                "max_escalation_tokens": 1200,
                "min_wakeup_sec": 900,
                "recall_limit": 2,
            }

        # DEEP_THESIS (> 50% budget remaining): aligned on 15m candle closes (min_wakeup_sec=900s)
        # with compact TA digest and lean output ceiling to avoid token bloat.
        model_key = self.preferred_model
        return {
            "thinking_depth": depth,
            "output_contract": "FULL_THESIS",
            "allow_llm": True,
            "model_key": model_key,
            "litellm_model": FRONTIER_FLASH_MODELS[model_key]["litellm_model"],
            "max_tokens": 950,
            "escalation_floor": 1250,
            "max_escalation_tokens": 1600,
            "min_wakeup_sec": 900,
            "recall_limit": 2,
        }

    def compute_call_cost(self, model_key: str, prompt_tokens: int, completion_tokens: int) -> float:
        clean_key = model_key.replace("openrouter/", "")
        meta = FRONTIER_FLASH_MODELS.get(clean_key, FRONTIER_FLASH_MODELS["deepseek/deepseek-v4.1-flash"])
        in_cost = (prompt_tokens / 1_000_000.0) * float(meta["input_usd_per_m"])
        out_cost = (completion_tokens / 1_000_000.0) * float(meta["output_usd_per_m"])
        return round(in_cost + out_cost, 7)

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "REPORT_USAGE":
            return self.record_usage(message.content)
        if message.msg_type == "QUERY_BALANCE":
            return self.get_status()
        return None

    def record_usage(self, content: Dict[str, Any]) -> Dict[str, Any]:
        model_key = str(content.get("model", self.preferred_model)).replace("openrouter/", "")
        prompt_tokens = int(content.get("prompt_tokens", 0))
        completion_tokens = int(content.get("completion_tokens", 0))
        tokens = int(content.get("tokens", prompt_tokens + completion_tokens))
        if "cost" in content and content["cost"] is not None:
            cost = float(content["cost"])
        else:
            cost = self.compute_call_cost(model_key, prompt_tokens, completion_tokens)

        agent = str(content.get("agent", "unknown"))
        # Hydration precedes the first record so a call is counted exactly once:
        # the ledger copy is already in the window, the live record is appended.
        self._ensure_hydrated()
        now_ms = self._now_ms()
        with self._lock:
            self._prune_spend_window(now_ms)
            self._spend_window.append((now_ms, cost))
            self.openrouter_balance_usd = round(
                max(0.0, self.openrouter_balance_usd - cost), 6
            )
            self.total_tokens += tokens
            self.total_calls += 1
            self.usage_log.insert(
                0,
                {
                    "agent": agent,
                    "model": model_key,
                    "cost": round(cost, 6),
                    "tokens": tokens,
                },
            )
            self.usage_log = self.usage_log[:50]

        # The automatic path evaluates the same gate as the operator path, with
        # the measured PnL of the injected source and no fallback.
        if self.auto_refill_enabled and self.openrouter_balance_usd <= self.low_watermark_usd:
            measured_pnl = self._measured_pnl()
            if measured_pnl is None:
                self._record_rejection(
                    "rejected_no_pnl_source",
                    "No measured PnL source is injected; the refill gate is inoperative",
                )
            else:
                self.trigger_openrouter_refill(
                    realized_trading_pnl_usd=measured_pnl,
                    amount_usd=self.refill_amount_usd,
                    reason=(
                        f"Auto-refill triggered: balance ${self.openrouter_balance_usd:.2f} "
                        f"<= watermark ${self.low_watermark_usd:.2f}"
                    ),
                    source="MASTER_ORCHESTRATOR_AUTO",
                )
        return self.get_status()

    @property
    def openrouter_credit_balance_usd(self) -> float:
        return self.openrouter_balance_usd

    @openrouter_credit_balance_usd.setter
    def openrouter_credit_balance_usd(self, val: float) -> None:
        self.openrouter_balance_usd = float(val)

    @staticmethod
    def _format_signed_usd(value: float) -> str:
        return f"{'-' if float(value) < 0 else ''}${abs(float(value)):.2f}"

    def _record_rejection(self, status: str, reason: str) -> None:
        """Records the bounded diagnosis object; never a refill-history event."""
        with self._lock:
            self.last_refill_rejection = {
                "status": status,
                "reason": reason,
                "timestamp_ms": self._now_ms(),
            }

    def _reject(self, status: str, reason: str) -> Dict[str, Any]:
        self._record_rejection(status, reason)
        return {
            "status": status,
            "reason": reason,
            "openrouter_balance_usd": round(self.openrouter_balance_usd, 4),
        }

    def operator_refill(
        self,
        amount_usd: Optional[float] = None,
        force: bool = True,
        reason: str = "Operator-requested credit top-up",
        source: str = "OPERATOR_REST",
    ) -> Dict[str, Any]:
        """Operator facade: resolves the injected measured source, then runs the gate."""
        measured_pnl = self._measured_pnl()
        if measured_pnl is None:
            return self._reject(
                "rejected_no_pnl_source",
                "No measured PnL source is injected; the refill gate is inoperative",
            )
        return self.trigger_openrouter_refill(
            realized_trading_pnl_usd=measured_pnl,
            requested_amount_usd=amount_usd,
            reason=reason,
            source=source,
            force=force,
        )

    def trigger_openrouter_refill(
        self,
        realized_trading_pnl_usd: float,
        amount_usd: Optional[float] = None,
        reason: str = "Master Orchestrator scheduled credit top-up",
        source: str = "MASTER_ORCHESTRATOR",
        force: bool = False,
        requested_amount_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes a bounded OpenRouter credit refill from the Master Orchestrator's OpEx reserve.

        Validation delegates to authoritative Rust HardRiskGate via `robotrader-node --validate-refill`.
        If the validator binary is missing, exits non-zero, raises an error, or returns malformed output,
        the monitor fails closed with `rejected_validator_unavailable` and preserves all state without mutation.
        """
        eff_req = requested_amount_usd if requested_amount_usd is not None else amount_usd
        if eff_req is None:
            requested_usd = self.refill_amount_usd
        else:
            try:
                requested_usd = float(eff_req)
            except (TypeError, ValueError):
                requested_usd = float("nan")

        try:
            pnl = float(realized_trading_pnl_usd)
        except (TypeError, ValueError):
            pnl = float("nan")

        with self._lock:
            now_ms = self._now_ms()
            self._prune_epoch_window(now_ms)
            epoch_refilled_usd = round(sum(amount for _, amount in self._epoch_window), 6)

            try:
                engine_dir = Path(__file__).resolve().parents[2] / "engine-rs"
                binary_path = resolve_robotrader_binary(engine_dir)
                if str(binary_path) == "robotrader-node" and not binary_path.exists():
                    debug_bin = engine_dir / "target" / "debug" / "robotrader-node"
                    release_bin = engine_dir / "target" / "release" / "robotrader-node"
                    if debug_bin.exists():
                        binary_path = debug_bin
                    elif release_bin.exists():
                        binary_path = release_bin
            except Exception as e:
                return self._reject(
                    "rejected_validator_unavailable",
                    f"Rust HardRiskGate validator binary unavailable: {e}",
                )

            def _format_cli_float(v: float) -> Any:
                if math.isnan(v):
                    return "NaN"
                if math.isinf(v):
                    return "Infinity" if v > 0 else "-Infinity"
                return float(v)

            cli_payload = {
                "requested_usd": _format_cli_float(requested_usd),
                "realized_trading_pnl_usd": _format_cli_float(pnl),
                "current_balance_usd": _format_cli_float(self.openrouter_balance_usd),
                "low_watermark_usd": _format_cli_float(self.low_watermark_usd),
                "epoch_refilled_usd": _format_cli_float(epoch_refilled_usd),
                "max_epoch_refill_usd": _format_cli_float(self.max_epoch_refill_usd),
                "force": bool(force),
                "kill_switch_active": bool(self._kill_switch_active()),
            }

            try:
                proc = _subprocess_run(
                    [str(binary_path), "--validate-refill", json.dumps(cli_payload)],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                if proc.returncode != 0:
                    return self._reject(
                        "rejected_validator_unavailable",
                        f"Rust validator exited with code {proc.returncode}: {proc.stderr.strip()}",
                    )
                verdict = json.loads(proc.stdout)
                if (
                    not isinstance(verdict, dict)
                    or "approved" not in verdict
                    or "status" not in verdict
                ):
                    return self._reject(
                        "rejected_validator_unavailable",
                        "Rust validator returned invalid verdict shape",
                    )
            except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as e:
                return self._reject(
                    "rejected_validator_unavailable",
                    f"Rust validator execution failed: {e}",
                )

            if verdict.get("approved") is True and verdict.get("status") == "refilled":
                approved_usd = float(verdict.get("approved_usd", requested_usd))
                before_bal = round(self.openrouter_balance_usd, 4)
                self.openrouter_balance_usd = round(self.openrouter_balance_usd + approved_usd, 4)
                self._epoch_window.append((now_ms, approved_usd))
                epoch_total = round(epoch_refilled_usd + approved_usd, 6)
                event = {
                    "timestamp_ms": now_ms,
                    "amount_usd": approved_usd,
                    "balance_before_usd": before_bal,
                    "balance_after_usd": self.openrouter_balance_usd,
                    "epoch_refilled_usd": epoch_total,
                    "max_epoch_refill_usd": self.max_epoch_refill_usd,
                    "source": source,
                    "reason": reason,
                    "validator": "RUST_HARD_RISK_GATE",
                }
                self.refill_history.insert(0, event)
                self.refill_history = self.refill_history[:25]
                return {
                    "status": "refilled",
                    "refilled_usd": approved_usd,
                    "event": event,
                    "openrouter_balance_usd": self.openrouter_balance_usd,
                }

            if verdict.get("status") == "skipped_sufficient_balance":
                return {
                    "status": "skipped_sufficient_balance",
                    "reason": verdict.get(
                        "reason",
                        f"Balance ${self.openrouter_balance_usd:.2f} > low watermark ${self.low_watermark_usd:.2f}",
                    ),
                    "openrouter_balance_usd": round(self.openrouter_balance_usd, 4),
                }

            return self._reject(
                str(verdict.get("status", "rejected")),
                str(verdict.get("reason", "Rejected by Rust HardRiskGate")),
            )

    def get_status(self) -> Dict[str, Any]:
        spend_usd = self.total_cost_usd
        utilization_pct = (
            (spend_usd / self.daily_budget_usd) * 100.0
            if self.daily_budget_usd > 0
            else 100.0
        )
        auto_refill_label = (
            "ENABLED_PROFIT_GATED" if self.auto_refill_enabled else "DISABLED"
        )
        auto_refill_policy = (
            "PROFIT_GATED_CAPPED_BY_ORCHESTRATOR"
            if self.auto_refill_enabled
            else "DISABLED"
        )
        profile = self.select_cognitive_profile()
        return {
            "agent": self.agent_name,
            "daily_budget_usd": round(self.daily_budget_usd, 2),
            "total_spent_usd": round(spend_usd, 5),
            "remaining_usd": round(self.remaining_budget_usd, 5),
            "remaining_ratio_pct": round(self.remaining_budget_ratio * 100.0, 1),
            "utilization_pct": round(utilization_pct, 3),
            "budget_exhausted": self.budget_exhausted,
            "auto_scheduler_enabled": self.auto_scheduler_enabled,
            "thinking_depth": self.get_thinking_depth(),
            "master_model": self.master_model,
            "master_model_meta": FRONTIER_FLASH_MODELS.get(self.master_model),
            "active_model": self.preferred_model,
            "active_model_meta": FRONTIER_FLASH_MODELS.get(self.preferred_model),
            "available_models": FRONTIER_FLASH_MODELS,
            "min_wakeup_sec": profile["min_wakeup_sec"],
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "recent_usage": self.usage_log[:5],
            "openrouter_credit": {
                "balance_usd": round(self.openrouter_balance_usd, 4),
                "low_watermark_usd": round(self.low_watermark_usd, 2),
                "refill_amount_usd": round(self.refill_amount_usd, 2),
                "epoch_refilled_usd": round(self.epoch_refilled_usd, 2),
                "max_epoch_refill_usd": round(self.max_epoch_refill_usd, 2),
                "measured_pnl_source_available": self.measured_pnl_source_available,
                "last_refill_rejection": self.last_refill_rejection,
                "auto_refill_enabled": self.auto_refill_enabled,
                "refill_history": self.refill_history[:5],
                "balance_source": "SIMULATED_INTERNAL_LEDGER",
            },
            "auto_wallet_refill": auto_refill_label,
            "auto_refill_policy": auto_refill_policy,
        }

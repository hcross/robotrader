from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .agent import CallResult
from .state_store import _redis_cmd


@dataclass
class TranscriptEntry:
    """
    A persistent raw-reasoning transcript entry ("model can inspect its own
    past thought transcripts" — backlog item of ADR-0002). Unlike `PalaceDrawer`
    (whose summaries feed logical continuity), a transcript keeps the verbatim
    prompts and completions, per-attempt failover timings, per-cycle tool calls,
    and the full latency/cost profile of one production LLM call.
    """

    entry_id: str
    timestamp_ms: int
    kind: str  # "reflection" | "chat"
    agent: str
    thinking_depth: str
    model_requested: str
    model_used: str
    status: str  # "ok" | "no_api_key" | "fallback_failed" | "llm_skipped_budget"
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    #  attempt = {"model", "latency_ms", "ok", "prompt_tokens", "completion_tokens", "error"}
    system_prompt: str = ""
    user_prompt: str = ""
    raw_completion: str = ""
    parsed_ok: bool = False
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    #  tool = {"name", "duration_ms", "ok", "error"}
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TranscriptEntry:
        now_ms = int(time.time() * 1000)
        return cls(
            entry_id=str(data.get("entry_id", f"tsc_{now_ms}_{uuid.uuid4().hex[:6]}")),
            timestamp_ms=int(data.get("timestamp_ms", now_ms)),
            kind=str(data.get("kind", "reflection")),
            agent=str(data.get("agent", "unknown")),
            thinking_depth=str(data.get("thinking_depth", "UNSPECIFIED")),
            model_requested=str(data.get("model_requested", "")),
            model_used=str(data.get("model_used", "")),
            status=str(data.get("status", "ok")),
            attempts=list(data.get("attempts", [])),
            system_prompt=str(data.get("system_prompt", "")),
            user_prompt=str(data.get("user_prompt", "")),
            raw_completion=str(data.get("raw_completion", "")),
            parsed_ok=bool(data.get("parsed_ok", False)),
            tool_calls=list(data.get("tool_calls", [])),
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
            latency_ms=int(data.get("latency_ms", 0)),
            error=str(data.get("error", "")),
            meta=dict(data.get("meta", {})),
        )


class TranscriptPalace:
    """
    Infinite raw-reasoning transcript store for the Warm-Path AI agents, cloned
    from `StrategyMemoryPalace`: append-only JSONL on disk (`backend/data/
    transcript_ledger.jsonl` — the durable source of truth) mirrored to Redis
    (`robotrader:v2:transcript`, volatile container cache) with an in-memory
    200-entry head for fast recall. Never touches the strategy-ledger lane:
    this is the transcript extension, not a replacement.
    """

    REDIS_TRANSCRIPT_KEY = "robotrader:v2:transcript"
    MAX_MEMORY_ENTRIES = 200
    MAX_JSONL_BYTES = 100_000_000

    def __init__(
        self,
        redis_cmd_fn: Optional[Any] = None,
        redis_url: Optional[str] = None,
        storage_path: Optional[Path] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._redis_cmd = redis_cmd_fn
        self._redis_url = redis_url
        default_dir = Path(__file__).resolve().parents[1] / "data"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path = storage_path or (default_dir / "transcript_ledger.jsonl")
        self.entries: List[TranscriptEntry] = []
        self._rotate_if_needed()
        self._load()

    def _rotate_if_needed(self) -> None:
        try:
            if self.storage_path.exists() and self.storage_path.stat().st_size > self.MAX_JSONL_BYTES:
                renamed = self.storage_path.with_name(self.storage_path.name + ".1")
                self.storage_path.rename(renamed)
        except Exception:
            pass

    def _load(self) -> None:
        loaded: List[TranscriptEntry] = []
        if self._redis_url and self._redis_cmd:
            raw = self._redis_cmd(self._redis_url, "GET", self.REDIS_TRANSCRIPT_KEY)
            if raw:
                try:
                    items = json.loads(raw)
                    if isinstance(items, list):
                        loaded = [TranscriptEntry.from_dict(x) for x in items]
                except Exception:
                    pass

        if not loaded and self.storage_path.exists():
            try:
                lines = self.storage_path.read_text(encoding="utf-8").splitlines()
                for line in reversed(lines[-self.MAX_MEMORY_ENTRIES:]):
                    if line.strip():
                        loaded.append(TranscriptEntry.from_dict(json.loads(line)))
            except Exception:
                pass

        self.entries = loaded[: self.MAX_MEMORY_ENTRIES]

    def add_entry(self, entry: TranscriptEntry) -> TranscriptEntry:
        with self._lock:
            self.entries.insert(0, entry)
            self.entries = self.entries[: self.MAX_MEMORY_ENTRIES]

            try:
                with self.storage_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            except Exception:
                pass

            if self._redis_url and self._redis_cmd:
                try:
                    payload = json.dumps([e.to_dict() for e in self.entries[:100]], ensure_ascii=False)
                    self._redis_cmd(self._redis_url, "SET", self.REDIS_TRANSCRIPT_KEY, payload)
                except Exception:
                    pass

        return entry

    def recall_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries[:limit]]

    def list_entries(
        self,
        offset: int = 0,
        limit: int = 50,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        thinking_depth: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Full-JSONL scan (most recent first) with optional filters.
        Returns `(page, total_before_filter)`.
        """
        all_items: List[Dict[str, Any]] = []
        if self.storage_path.exists():
            try:
                for line in reversed(self.storage_path.read_text(encoding="utf-8").splitlines()):
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    if agent and str(data.get("agent", "")) != agent:
                        continue
                    if model and str(data.get("model_used", "") or data.get("model_requested", "")) != model:
                        continue
                    if thinking_depth and str(data.get("thinking_depth", "")) != thinking_depth:
                        continue
                    all_items.append(data)
            except Exception:
                pass

        total = len(all_items)
        page = all_items[offset : offset + limit]
        return page, total

    def format_recent_transcripts(
        self,
        limit: int = 2,
        max_completion_chars: int = 1200,
        max_total_chars: int = 4000,
    ) -> str:
        """
        Self-inspection lane: returns the model's own most recent raw
        completions (never the prompts — system is constant and user contains
        data already refreshed for the current cycle).
        """
        if not self.entries:
            return "Aucun transcript antérieur (premier cycle d'initialisation)."

        lines: List[str] = []
        total_chars = 0
        for idx, e in enumerate(self.entries[:limit], 1):
            stamp = time.strftime("%H:%M:%S", time.localtime(e.timestamp_ms / 1000.0))
            excerpt = e.raw_completion[:max_completion_chars]
            suffix = " …(tronqué)" if len(e.raw_completion) > max_completion_chars else ""
            line = (
                f"[Entrée T-{idx} | {stamp} | depth={e.thinking_depth} | model={e.model_used} | parsed={'OK' if e.parsed_ok else 'NOK'}]\n"
                f"  Extrait brut de votre décision : « {excerpt}{suffix} »"
            )
            if total_chars + len(line) > max_total_chars:
                break
            total_chars += len(line)
            lines.append(line)
        return "\n".join(lines) if lines else "Aucun transcript antérieur (premier cycle d'initialisation)."


def record_llm_call(
    *,
    agent: str,
    kind: str,
    thinking_depth: str,
    model_requested: str,
    result: CallResult,
    system_prompt: str,
    user_prompt: str,
    parsed_ok: bool,
    cost_usd: float = 0.0,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    meta: Optional[Dict[str, Any]] = None,
    status: Optional[str] = None,
) -> TranscriptEntry:
    """
    Pure constructor from a `CallResult` — no side effects, testable in
    isolation. The caller decides whether to persist via `transcript_palace`.
    `status` overrides the transport mapping (e.g. "llm_skipped_budget" for a
    cycle locked by CostGuard, where prompts are still recorded).
    """
    if status:
        resolved_status = status
    else:
        resolved_status = "ok"
        if result.error:
            resolved_status = "no_api_key" if result.error == "no_api_key" else "fallback_failed"
    return TranscriptEntry(
        entry_id=f"tsc_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        timestamp_ms=int(time.time() * 1000),
        kind=kind,
        agent=agent,
        thinking_depth=thinking_depth,
        model_requested=model_requested.replace("openrouter/", ""),
        model_used=result.model_used.replace("openrouter/", ""),
        status=resolved_status,
        attempts=list(result.attempts),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_completion=result.raw_resp or "",
        parsed_ok=parsed_ok,
        tool_calls=list(tool_calls or []),
        prompt_tokens=int(result.prompt_tokens),
        completion_tokens=int(result.completion_tokens),
        cost_usd=float(cost_usd),
        latency_ms=int(result.latency_ms),
        error=(result.error or "")[-200:],
        meta=dict(meta or {}),
    )


transcript_palace = TranscriptPalace(
    redis_cmd_fn=_redis_cmd, redis_url=os.getenv("REDIS_URL")
)
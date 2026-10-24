from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PalaceDrawer:
    """
    A persistent cognitive memory drawer inspired by MemPalace.
    Stores the strategist's observations, technical confluences, thesis continuity
    (CONFIRMED / REFINED / INVALIDATED), compiled mechanical rules, and wakeup schedule.
    """

    drawer_id: str
    timestamp_ms: int
    wing: str
    room: str
    model_used: str
    thinking_depth: str
    thesis_continuity: str  # "INITIAL" | "CONFIRMED" | "REFINED" | "INVALIDATED"
    global_regime: str
    panorama_summary: str
    ta_confluence_notes: str
    hypothesis: str
    invalidation_condition: str
    compiled_rules_summary: Dict[str, Any] = field(default_factory=dict)
    next_wakeup_sec: int = 120
    wakeup_reason: str = "Cycle périodique standard"
    tokens_used: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PalaceDrawer:
        return cls(
            drawer_id=str(data.get("drawer_id", f"drw_{int(time.time() * 1000)}")),
            timestamp_ms=int(data.get("timestamp_ms", int(time.time() * 1000))),
            wing=str(data.get("wing", "strategy_ledger")),
            room=str(data.get("room", "active_theses")),
            model_used=str(data.get("model_used", "deepseek/deepseek-v4.1-flash")),
            thinking_depth=str(data.get("thinking_depth", "DEEP_THESIS")),
            thesis_continuity=str(data.get("thesis_continuity", "CONFIRMED")),
            global_regime=str(data.get("global_regime", "TRENDING_BULL")),
            panorama_summary=str(data.get("panorama_summary", "")),
            ta_confluence_notes=str(data.get("ta_confluence_notes", "")),
            hypothesis=str(data.get("hypothesis", "")),
            invalidation_condition=str(data.get("invalidation_condition", "")),
            compiled_rules_summary=dict(data.get("compiled_rules_summary", {})),
            next_wakeup_sec=int(data.get("next_wakeup_sec", 120)),
            wakeup_reason=str(data.get("wakeup_reason", "")),
            tokens_used=int(data.get("tokens_used", 0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
        )


class StrategyMemoryPalace:
    """
    Infinite structured memory store ("Strategy Palace") for the Warm-Path AI Strategist.
    Maintains long-term strategic continuity across reflections by persisting drawers to both
    disk (`backend/data/strategy_palace.jsonl`) and Redis (`robotrader:v2:palace`).
    """

    REDIS_PALACE_KEY = "robotrader:v2:palace"

    def __init__(
        self,
        redis_cmd_fn: Optional[Callable[..., Optional[str]]] = None,
        redis_url: Optional[str] = None,
        storage_path: Optional[Path] = None,
    ) -> None:
        self._redis_cmd = redis_cmd_fn
        self._redis_url = redis_url
        default_dir = Path(__file__).resolve().parents[1] / "data"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path = storage_path or (default_dir / "strategy_palace.jsonl")
        self.drawers: List[PalaceDrawer] = []
        self._load()

    def _load(self) -> None:
        loaded: List[PalaceDrawer] = []
        if self._redis_url and self._redis_cmd:
            raw = self._redis_cmd(self._redis_url, "GET", self.REDIS_PALACE_KEY)
            if raw:
                try:
                    items = json.loads(raw)
                    if isinstance(items, list):
                        loaded = [PalaceDrawer.from_dict(x) for x in items]
                except Exception:
                    pass

        if not loaded and self.storage_path.exists():
            try:
                lines = self.storage_path.read_text(encoding="utf-8").splitlines()
                for line in reversed(lines[-200:]):
                    if line.strip():
                        loaded.append(PalaceDrawer.from_dict(json.loads(line)))
            except Exception:
                pass

        self.drawers = loaded[:200]

    def add_drawer(self, drawer: PalaceDrawer) -> PalaceDrawer:
        self.drawers.insert(0, drawer)
        self.drawers = self.drawers[:200]

        # Append to append-only JSONL palace log on disk
        try:
            with self.storage_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(drawer.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

        # Mirror recent 100 drawers to Redis for fast container restart recovery
        if self._redis_url and self._redis_cmd:
            try:
                payload = json.dumps([d.to_dict() for d in self.drawers[:100]], ensure_ascii=False)
                self._redis_cmd(self._redis_url, "SET", self.REDIS_PALACE_KEY, payload)
            except Exception:
                pass

        return drawer

    def recall_recent(self, limit: int = 4, wing: Optional[str] = None) -> List[Dict[str, Any]]:
        if wing in ("leaf_solana", "strategy_ledger"):
            filtered = [d for d in self.drawers if d.wing in ("leaf_solana", "strategy_ledger")]
        else:
            filtered = [d for d in self.drawers if (wing is None or d.wing == wing)]
        return [d.to_dict() for d in filtered[:limit]]

    def recall_across_wings(
        self, wings: Optional[List[str]] = None, per_wing_limit: int = 2
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Allows the Master Orchestrator to inspect the recent memory drawers of all leaf agents."""
        target_wings = wings or sorted(
            {d.wing for d in self.drawers if d.wing != "master_orchestrator"}
        )
        return {w: self.recall_recent(limit=per_wing_limit, wing=w) for w in target_wings}

    def format_continuity_prompt(self, limit: int = 3, wing: Optional[str] = None) -> str:
        recent = self.recall_recent(limit=limit, wing=wing)
        if not recent:
            return "Aucune thèse antérieure enregistrée dans le Strategy Palace (Premier cycle d'initialisation)."
        lines: List[str] = []
        for idx, d in enumerate(recent, 1):
            lines.append(
                f"[Thèse T-{idx} | Wing={d.get('wing')} | {d['thesis_continuity']} | Régime={d['global_regime']} | Modèle={d['model_used']}]\n"
                f"  - Panorama & TA : {d['ta_confluence_notes']}\n"
                f"  - Hypothèse : {d['hypothesis']}\n"
                f"  - Invalidation : {d['invalidation_condition']}\n"
                f"  - Règles compilées : {json.dumps(d.get('compiled_rules_summary', {}), ensure_ascii=False)}"
            )
        return "\n".join(lines)

    def format_cross_wing_digest(
        self,
        wings: Optional[List[str]] = None,
        per_wing_limit: int = 1,
        limit_per_wing: Optional[int] = None,
    ) -> str:
        """Compact summary of all leaf agents' MemPalace wings for the Master Orchestrator."""
        eff_limit = limit_per_wing if limit_per_wing is not None else per_wing_limit
        across = self.recall_across_wings(wings=wings, per_wing_limit=eff_limit)
        blocks: List[str] = []
        for w, items in across.items():
            if not items:
                continue
            top = items[0]
            blocks.append(
                f"- [{w}] ({top.get('thesis_continuity')} | {top.get('model_used')}): "
                f"{top.get('hypothesis', '')[:180]} | Invalidation: {top.get('invalidation_condition', '')[:120]}"
            )
        return "\n".join(blocks) if blocks else "Aucun rapport MemPalace feuille disponible."

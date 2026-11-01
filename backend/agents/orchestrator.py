from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core import provenance
from ..core.agent import BaseWarmAgent, CallResult
from ..core.memory_palace import PalaceDrawer
from ..core.schemas import (
    AssetOverride,
    CatalystSignal,
    Message,
    PolicyEnvelope,
    PodAllocation,
    SignedPolicyBundle,
    compute_policy_hmac,
    
    
)
from ..core.state_store import HybridStateStore, state_store
from ..core.transcript_palace import record_llm_call, transcript_palace
from ..tools.rss_tools import EcosystemRSSAggregator
from .analysis import CatalystScoutAgent, QuantAuditorAgent
from .monitor import FRONTIER_FLASH_MODELS, LLMMonitorAgent
from .trading import MetaAllocatorAgent


class OrchestratorAgent(BaseWarmAgent):
    """
    Warm-Path Coordinator, Pro Technical Analyst & Autonomous Strategist (ADR-0002).
    - Gathers multi-asset TA (Ichimoku Kinko Hyo, Fibonacci 0.618, RSI 14, ATR/Bollinger) + Social Panorama
    - Maintains strategic continuity via the infinite Strategy Memory Palace (`StrategyMemoryPalace`)
    - Routes inference through ultra-low-cost frontier models (`deepseek/deepseek-v4.1-flash`,
      `z-ai/glm-5.3-flash`, `qwen/qwen3.7-flash`) governed by `CostGuard` remaining budget
    - Compiles mechanical execution rules into `PolicyEnvelope` for `<50µs` Rust Hot-Path execution
    - Self-schedules its next wakeup (`next_wakeup_sec`) based on market urgency and TA proximity
    """

    def __init__(
        self,
        name: str = "Orchestrator",
        store: Optional[HybridStateStore] = None,
        ledger_path: Optional[Path | str] = None,
    ):
        super().__init__(
            name,
            role="Autonomous Quantitative CIO, Pro Technical Analyst & Swarm Coordinator",
        )
        self.store = store or state_store
        self._scheduler_started = False
        self._reflection_lock = threading.Lock()
        self._last_tool_timings: List[Dict[str, Any]] = []

        # Instantiate and interconnect the Warm-Path swarm. The CostGuard receives
        # this orchestrator's own store as its measured PnL source.
        self.cost_guard = LLMMonitorAgent(
            name="CostGuard", store=self.store, ledger_path=ledger_path
        )
        self.catalyst_scout = CatalystScoutAgent(name="CatalystScout", store=self.store)
        self.quant_auditor = QuantAuditorAgent(name="QuantAuditor", store=self.store)
        self.meta_allocator = MetaAllocatorAgent(name="MetaAllocator", store=self.store)

        for peer in (self.cost_guard, self.catalyst_scout, self.quant_auditor, self.meta_allocator):
            self.register_peer(peer)
            peer.register_peer(self)

    def start_cognitive_scheduler(self) -> None:
        with self.lock:
            if self._scheduler_started:
                return
            self._scheduler_started = True

        def _cognitive_loop() -> None:
            time.sleep(3.0)
            while True:
                try:
                    now_ms = int(time.time() * 1000)
                    if (
                        not self.store.kill_switch_active
                        and self.cost_guard.auto_scheduler_enabled
                    ):
                        if now_ms >= self.store.next_cognitive_wakeup_ms:
                            self.run_strategic_reflection(trigger_source="AUTO_SCHEDULER")
                        master_next = int(
                            self.store.hierarchy.master_state.get("next_wakeup_ms", 0)
                        )
                        if master_next > 0 and now_ms >= master_next:
                            self.run_master_orchestrator_reflection(
                                trigger_source="MASTER_SCHEDULER"
                            )
                except Exception as exc:
                    print(f"[CognitiveScheduler] Warning: {exc}")
                time.sleep(2.0)

        thread = threading.Thread(
            target=_cognitive_loop, name="WarmPathCognitiveScheduler", daemon=True
        )
        thread.start()

    @staticmethod
    def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        cleaned = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except Exception:
                return None
        return None

    @staticmethod
    def _compact_ta_digest(ta_snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Extracts essential scalar indicators (~300 tokens total instead of ~6,000 raw JSON tokens)."""
        digest: Dict[str, Dict[str, Any]] = {}
        for sym, snap in ta_snapshots.items():
            if not isinstance(snap, dict):
                continue
            ich = snap.get("ichimoku", {})
            fib = snap.get("fibonacci", {})
            levels = fib.get("levels", {}) if isinstance(fib.get("levels"), dict) else {}
            rsi = snap.get("rsi", {})
            vol = snap.get("volatility", {})
            zones = snap.get("key_zones", {})
            digest[sym] = {
                "last_price": snap.get("last_price"),
                "obi_l2": snap.get("obi_l2"),
                "confluence_score": snap.get("confluence_score"),
                "kumo_regime": ich.get("kumo_regime"),
                "tk_cross": ich.get("tk_cross"),
                "tenkan": ich.get("tenkan_sen"),
                "kijun": ich.get("kijun_sen"),
                "kumo_top": ich.get("kumo_top"),
                "kumo_bottom": ich.get("kumo_bottom"),
                "fib_382": levels.get("0.382"),
                "fib_618": fib.get("golden_pocket_618"),
                "fib_786": levels.get("0.786"),
                "fib_dist_bps": fib.get("distance_to_nearest_bps"),
                "rsi_14": rsi.get("rsi_14"),
                "rsi_slope": rsi.get("slope"),
                "atr_bps": vol.get("atr_bps"),
                "support_usd": zones.get("support_zone_usd"),
                "resistance_usd": zones.get("resistance_zone_usd"),
                "invalidation_usd": zones.get("invalidation_price_usd"),
            }
        return digest

    def _build_reflection_prompts(
        self,
        thinking_depth: str,
        output_contract: str,
        ta_snapshots: Dict[str, Dict[str, Any]],
        panorama: Dict[str, Any],
        continuity_ctx: str,
        min_wakeup: int,
        base_interval: int,
    ) -> tuple[str, str]:
        """
        Builds tier-appropriate (sys_prompt, user_prompt) for the Solana Leaf Robot (`leaf-solana`):
        - Strictly scoped to Solana ecosystem assets (`SOL/USDT`, `JUP/USDT`, `RAY/USDT`) and Solana RSS feeds.
        - FULL_THESIS (DEEP_THESIS, 1800-2200 tokens): full 7-field narrative + Solana asset rules
        - COMPACT_TACTICAL (TACTICAL_FOCUS, 700 tokens): single-sentence fields (<=160 chars) + rules
        - MECHANICAL_ENVELOPE (ECO_CONSERVATION, 350 tokens): mechanical envelope + ultra-short thesis
          (omits panorama_summary & ta_confluence_notes, which Python fills deterministically)
        """
        rem_usd = self.cost_guard.remaining_budget_usd
        solana_rss = EcosystemRSSAggregator.get_feed_for_agent("leaf-solana", max_items=3)
        rss_headlines = [f"[{item.get('source')}] {item.get('title')}" for item in solana_rss.get("items", [])]
        if output_contract == "MECHANICAL_ENVELOPE":
            digest = self._compact_ta_digest(ta_snapshots)
            sys_prompt = (
                "Tu es le Robot Feuille Solana (`leaf-solana`) de Robotrader v3 en mode ECO_CONSERVATION (budget de jetons strict <= 350).\n"
                "Tu es EXCLUSIVEMENT dédié à la blockchain Solana (SOL, JUP, RAY). Produis UNIQUEMENT l'enveloppe mécanique JSON ultra-compacte (< 200 tokens au total)."
            )
            user_prompt = (
                f"=== MODE : {thinking_depth} (Contrat: {output_contract} | Budget restant: ${rem_usd:.4f}) ===\n"
                f"=== MÉMOIRE RÉCENTE (SOLANA) ===\n{continuity_ctx}\n\n"
                f"=== INDICATEURS CLÉS SOLANA 15m ===\n{json.dumps(digest, ensure_ascii=False)}\n\n"
                f"=== PÉRIODE : {min_wakeup}s à {base_interval}s ===\n"
                "Réponds UNIQUEMENT avec ce JSON compact (omets panorama_summary et ta_confluence_notes) :\n"
                "{\n"
                '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
                '  "hypothesis": "1 phrase <= 90 caractères sur SOL/JUP/RAY",\n'
                '  "invalidation_condition": "Prix/condition <= 80 caractères",\n'
                '  "asset_rules": {\n'
                '    "SOL-USDT": {"bias": "LONG_BIAS"|"SHORT_BIAS"|"NEUTRAL", "entry_obi_threshold": 0.08, "max_rsi_long": 68.0, "take_profit_bps": 45.0, "stop_loss_bps": 28.0}\n'
                "  },\n"
                f'  "next_wakeup_sec": entier entre {min_wakeup} et {base_interval},\n'
                '  "wakeup_reason": "Raison <= 60 caractères"\n'
                "}"
            )
            return sys_prompt, user_prompt

        if output_contract == "COMPACT_TACTICAL":
            digest = self._compact_ta_digest(ta_snapshots)
            pano_compact = {
                "urgency_level": panorama.get("urgency_level"),
                "composite_sentiment": (
                    panorama.get("composite_sentiment")
                    if panorama.get("composite_sentiment") is not None
                    else panorama.get("Composite_sentiment")
                ),
                "solana_rss": rss_headlines,
            }
            sys_prompt = (
                "Tu es le Robot Feuille Solana (`leaf-solana`) de Robotrader v3 en mode TACTICAL_FOCUS (plafond strict 700 tokens).\n"
                "Tu es EXCLUSIVEMENT spécialisé sur l'écosystème Solana (SOL, JUP, RAY, Jupiter v6, Jito MEV). Chaque champ narratif DOIT tenir en 1 seule phrase concise (<= 150 caractères maximum).\n"
                "Réponds UNIQUEMENT avec un objet JSON valide (< 450 tokens au total)."
            )
            user_prompt = (
                f"=== MODE : {thinking_depth} (Contrat: {output_contract} | Budget restant: ${rem_usd:.4f}) ===\n"
                f"=== MÉMOIRE CONTINUE (SOLANA) ===\n{continuity_ctx}\n\n"
                f"=== DIGEST TA SOLANA 15m ===\n{json.dumps(digest, ensure_ascii=False)}\n\n"
                f"=== PANORAMA & RSS SOLANA ===\n{json.dumps(pano_compact, ensure_ascii=False)}\n\n"
                f"=== PÉRIODE : {min_wakeup}s à {base_interval}s ===\n"
                "Produis ta décision au format JSON compact (1 phrase <= 150 car. par champ texte) :\n"
                "{\n"
                '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
                '  "panorama_summary": "1 phrase <= 140 car. sur le flux L2 et RSS Solana",\n'
                '  "ta_confluence_notes": "1 phrase <= 160 car. sur Ichimoku/Fib/RSI SOL, JUP & RAY",\n'
                '  "hypothesis": "1 phrase <= 150 car. sur la thèse directionnelle Solana",\n'
                '  "invalidation_condition": "1 phrase <= 120 car. avec prix d\'invalidation",\n'
                '  "asset_rules": {\n'
                '    "SOL-USDT": {"bias": "LONG_BIAS"|"SHORT_BIAS"|"NEUTRAL", "entry_obi_threshold": 0.08, "max_rsi_long": 68.0, "take_profit_bps": 45.0, "stop_loss_bps": 28.0}\n'
                "  },\n"
                f'  "next_wakeup_sec": entier entre {min_wakeup} et {base_interval},\n'
                '  "wakeup_reason": "1 phrase <= 80 car."\n'
                "}"
            )
            return sys_prompt, user_prompt

        digest = self._compact_ta_digest(ta_snapshots)
        pano_compact = {
            "urgency_level": panorama.get("urgency_level"),
            "composite_sentiment": (
                panorama.get("composite_sentiment")
                if panorama.get("composite_sentiment") is not None
                else panorama.get("Composite_sentiment")
            ),
            "solana_rss": rss_headlines,
        }

        sys_prompt = (
            "Tu es le Robot Feuille Solana (`leaf-solana`) de l'architecture hiérarchique Robotrader v3.\n"
            "Tu es EXCLUSIVEMENT spécialisé dans la blockchain Solana (SOL/USDT, JUP/USDT, RAY/USDT, Jupiter v6, Raydium CLMM, Jito MEV).\n"
            "Tu analyses les flux RSS Solana dédiés et le digest d'analyse technique 15m "
            "(Ichimoku Kinko Hyo, Retracements de Fibonacci 0.382/0.618/0.786, RSI 14, ATR, OBI L2).\n"
            "Tu maintiens une continuité logique stricte avec tes thèses précédentes stockées dans ton MemPalace (`wing=leaf_solana`).\n"
            "Tu déclines ta stratégie en règles mécaniques exécutées en <50µs par les 4 pods Rust Solana, "
            "et tu décides de ton prochain réveil (`next_wakeup_sec`).\n"
            "Réponds UNIQUEMENT avec un objet JSON valide (sans texte autour)."
        )

        user_prompt = (
            f"=== MODE COGNITIF : {thinking_depth} (Budget restant: ${rem_usd:.4f}) ===\n"
            f"=== MÉMOIRE CONTINUE (MEMPALACE SOLANA) ===\n{continuity_ctx}\n\n"
            f"=== DIGEST ANALYSE TECHNIQUE SOLANA 15m ===\n{json.dumps(digest, ensure_ascii=False)}\n\n"
            f"=== PANORAMA & FLUX RSS SOLANA ===\n{json.dumps(pano_compact, ensure_ascii=False)}\n\n"
            f"=== PÉRIODE DE BASE CONFIGURÉE : {base_interval}s ( Plancher autorisé par CostGuard: {min_wakeup}s ) ===\n"
            "Produis ta décision stratégique Solana au format JSON strict suivant :\n"
            "{\n"
            '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
            '  "panorama_summary": "Synthèse pro (2 phrases en français) du contexte RSS Solana et flux L2",\n'
            '  "ta_confluence_notes": "Analyse précise Ichimoku (Kumo/Tenkan/Kijun) + Fibonacci (0.618) + RSI(14) sur SOL/JUP/RAY",\n'
            '  "hypothesis": "Intuition et thèse directionnelle actuelle sur l\'écosystème Solana",\n'
            '  "invalidation_condition": "Condition et prix précis invalidant cette thèse",\n'
            '  "asset_rules": {\n'
            '    "SOL-USDT": {"bias": "LONG_BIAS"|"SHORT_BIAS"|"NEUTRAL", "entry_obi_threshold": 0.08, "max_rsi_long": 68.0, "take_profit_bps": 45.0, "stop_loss_bps": 28.0},\n'
            '    "JUP-USDT": {"bias": "LONG_BIAS"|"SHORT_BIAS"|"NEUTRAL", "entry_obi_threshold": 0.10, "max_rsi_long": 70.0, "take_profit_bps": 55.0, "stop_loss_bps": 32.0},\n'
            '    "RAY-USDT": {"bias": "LONG_BIAS"|"SHORT_BIAS"|"NEUTRAL", "entry_obi_threshold": 0.10, "max_rsi_long": 70.0, "take_profit_bps": 55.0, "stop_loss_bps": 32.0}\n'
            "  },\n"
            f'  "next_wakeup_sec": entier entre {min_wakeup} et {base_interval},\n'
            '  "wakeup_reason": "Justification précise du délai avant prochain réveil (ex: clôture 15m ou test du Fib 0.618 sur SOL)"\n'
            "}"
        )
        return sys_prompt, user_prompt

    def compile_leaf_policy_envelope(
        self,
        leaf_id: str,
        parsed_reflection: Optional[Dict[str, Any]] = None,
        now_ms: Optional[int] = None,
    ) -> PolicyEnvelope:
        """
        Compiles a valid `PolicyEnvelope` strictly scoped to `leaf["exclusive_assets"]`
        (for `leaf-bitcoin`: `["BTC-USD", "wBTC-BTC", "sBTC-BTC"]`):
        - Maps `leaf["risk_posture"]` to `GlobalRegime`.
        - Sets `ttl_seconds=900` and `capital_allocated_usd=float(leaf.get("allocated_capital_usd", 0.0))`.
        - Populates `asset_overrides` for every symbol in `leaf["exclusive_assets"]` with all 11 `AssetOverride` fields.
        """
        ts = now_ms if now_ms is not None else int(time.time() * 1000)
        leaf_state = self.store.hierarchy.leaves.get(leaf_id) or self.store.hierarchy.get_leaf_state(leaf_id)
        if not leaf_state:
            leaf_state = {
                "leaf_id": leaf_id,
                "chain": "Bitcoin" if leaf_id == "leaf-bitcoin" else "Solana",
                "risk_posture": "BALANCED",
                "allocated_capital_usd": 5000.0,
                "exclusive_assets": ["BTC-USD", "wBTC-BTC", "sBTC-BTC"] if leaf_id == "leaf-bitcoin" else ["SOL-USDT", "JUP-USDT", "RAY-USDT"],
                "rust_pods": ["pod_carry", "pod_momentum", "pod_onchain_alpha"],
                "ta_specific_metrics": {},
            }

        posture = str(leaf_state.get("risk_posture", "BALANCED")).upper()
        if posture == "AGGRESSIVE":
            global_regime = "RISK_ON_HIGH_VOL"
        elif posture == "DEFENSIVE":
            global_regime = "DEFENSIVE_WINTER"
        elif posture == "HIBERNATION":
            global_regime = "KILL_SWITCH"
        else:
            global_regime = "RANGING_CHOP"

        rust_pods_list = leaf_state.get("rust_pods", ["pod_carry", "pod_momentum", "pod_onchain_alpha"])
        pod_allocations: Dict[str, PodAllocation] = {}
        weight_per_pod = round(1.0 / max(1, len(rust_pods_list)), 2)
        all_possible_pods = ["pod_carry", "pod_momentum", "pod_onchain_alpha", "pod_sniper"]
        for p_name in all_possible_pods:
            enabled = p_name in rust_pods_list
            pod_allocations[p_name] = PodAllocation(
                enabled=enabled,
                capital_weight=weight_per_pod if enabled else 0.0,
                directional_bias="LONG_BIAS" if global_regime in ("RISK_ON_HIGH_VOL", "RANGING_CHOP") else "NEUTRAL",
                min_funding_apr=0.10 if p_name == "pod_carry" else None,
                max_slippage_bps=30 if enabled else 150,
            )

        exclusive_assets = leaf_state.get("exclusive_assets", [])
        ta_metrics = leaf_state.get("ta_specific_metrics", {})
        parsed_ref = parsed_reflection or {}
        asset_rules_in = parsed_ref.get("asset_rules", {}) if isinstance(parsed_ref, dict) else {}

        asset_overrides: Dict[str, AssetOverride] = {}
        for sym in exclusive_assets:
            llm_r = asset_rules_in.get(sym, {}) if isinstance(asset_rules_in, dict) else {}
            bias_str = str(llm_r.get("bias", "LONG_BIAS"))
            if bias_str not in ("LONG_BIAS", "SHORT_BIAS", "NEUTRAL"):
                bias_str = "LONG_BIAS"
            
            cat_score = float(leaf_state.get("catalyst_score", 0.85))
            # Ethereum-specific calibration when leaf_id == "leaf-ethereum"
            if leaf_id == "leaf-ethereum":
                base_fee = float(ta_metrics.get("eip1559_base_fee_gwei", 4.2))
                restake_apr = float(ta_metrics.get("restaking_apr_pct", 3.65))
                cat_score = round(min(0.99, max(0.50, 0.80 + (restake_apr / 100.0) - (base_fee / 100.0))), 4)
            elif leaf_id == "leaf-sui":
                mysticeti = float(ta_metrics.get("mysticeti_finality_ms", 385.0))
                deepbook_vol = float(ta_metrics.get("deepbook_v3_vol_usd_m", 482.0))
                cat_score = round(min(0.99, max(0.50, 0.83 + (deepbook_vol / 5000.0) - (mysticeti / 10000.0))), 4)

            max_lev = float(leaf_state.get("max_leverage", 2.0))
            
            if leaf_id == "leaf-ethereum":
                if sym == "stETH-ETH":
                    peg = float(ta_metrics.get("steth_peg_ratio", 0.9997))
                    support_z = round(peg * 0.9985, 4)
                    resistance_z = round(peg * 1.0005, 4)
                    invalidation_p = round(peg * 0.9950, 4)
                    last_p = peg
                elif sym in ("UNI-ETH", "AAVE-ETH"):
                    ratio = 0.0038 if sym == "UNI-ETH" else 0.065
                    support_z = round(ratio * 0.98, 4)
                    resistance_z = round(ratio * 1.05, 4)
                    invalidation_p = round(ratio * 0.97, 4)
                    last_p = ratio
                else:  # ETH-USDC
                    last_p = float(ta_metrics.get("last_price", ta_metrics.get("golden_pocket_fib_618", 2368.0)))
                    fib_618 = float(ta_metrics.get("golden_pocket_fib_618", round(last_p * 0.992, 2)))
                    support_z = float(ta_metrics.get("support_usd", round(fib_618 * 0.98, 2)))
                    resistance_z = float(ta_metrics.get("resistance_usd", round(last_p * 1.05, 2)))
                    invalidation_p = float(ta_metrics.get("invalidation_price_usd", round(fib_618 * 0.97, 2)))
            elif leaf_id == "leaf-sui":
                if sym == "SUI-USDC":
                    last_p = float(ta_metrics.get("last_price", ta_metrics.get("golden_pocket_fib_618", 3.02)))
                    fib_618 = float(ta_metrics.get("golden_pocket_fib_618", round(last_p * 0.992, 2)))
                    support_z = float(ta_metrics.get("support_usd", round(fib_618 * 0.98, 2)))
                    resistance_z = float(ta_metrics.get("resistance_usd", round(last_p * 1.05, 2)))
                    invalidation_p = float(ta_metrics.get("invalidation_price_usd", round(fib_618 * 0.97, 2)))
                elif sym in ("DEEP-SUI", "CETUS-SUI"):
                    ratio = 0.048 if sym == "DEEP-SUI" else 0.024
                    support_z = round(ratio * 0.98, 4)
                    resistance_z = round(ratio * 1.05, 4)
                    invalidation_p = round(ratio * 0.97, 4)
                    last_p = ratio
                else:
                    last_p = float(ta_metrics.get("last_price", 3.02))
                    fib_618 = float(ta_metrics.get("golden_pocket_fib_618", round(last_p * 0.992, 2)))
                    support_z = float(ta_metrics.get("support_usd", round(fib_618 * 0.98, 2)))
                    resistance_z = float(ta_metrics.get("resistance_usd", round(last_p * 1.05, 2)))
                    invalidation_p = float(ta_metrics.get("invalidation_price_usd", round(fib_618 * 0.97, 2)))
            else:
                last_p = float(ta_metrics.get("last_price", 80000.0 if "BTC" in sym else 150.0))
                fib_618 = float(ta_metrics.get("golden_pocket_fib_618", round(last_p * 0.992, 2)))
                support_z = float(ta_metrics.get("support_usd", round(fib_618 * 0.98, 2)))
                resistance_z = float(ta_metrics.get("resistance_usd", round(last_p * 1.05, 2)))
                invalidation_p = float(ta_metrics.get("invalidation_price_usd", round(fib_618 * 0.97, 2)))

            obi_thresh = max(0.02, min(0.50, float(llm_r.get("entry_obi_threshold", 0.08))))
            max_rsi = max(55.0, min(85.0, float(llm_r.get("max_rsi_long", 70.0))))
            min_rsi = max(15.0, min(45.0, float(llm_r.get("min_rsi_short", 30.0))))
            tp_bps = max(15.0, min(200.0, float(llm_r.get("take_profit_bps", 45.0))))
            if leaf_id == "leaf-ethereum":
                restake_apr = float(ta_metrics.get("restaking_apr_pct", 3.65))
                tp_bps = round(min(200.0, max(15.0, 45.0 + restake_apr * 2.0)), 2)
            elif leaf_id == "leaf-sui":
                deepbook_vol = float(ta_metrics.get("deepbook_v3_vol_usd_m", 482.0))
                tp_bps = round(min(200.0, max(15.0, 45.0 + deepbook_vol / 100.0)), 2)

            sl_bps = max(10.0, min(150.0, float(llm_r.get("stop_loss_bps", 28.0))))

            asset_overrides[sym] = AssetOverride(
                catalyst_score=cat_score,
                bias=bias_str,
                max_leverage=max_lev,
                support_zone_usd=support_z,
                resistance_zone_usd=resistance_z,
                invalidation_price_usd=invalidation_p,
                entry_obi_threshold=obi_thresh,
                max_rsi_long=max_rsi,
                min_rsi_short=min_rsi,
                take_profit_bps=tp_bps,
                stop_loss_bps=sl_bps,
            )

        return PolicyEnvelope(
            envelope_id=f"env_{leaf_id}_{ts}",
            issued_at_ms=ts,
            ttl_seconds=900,
            global_regime=global_regime.value if hasattr(global_regime, "value") else str(global_regime),
            pod_allocations=pod_allocations,
            asset_overrides=asset_overrides,
        )

    def run_strategic_reflection(
        self, force: bool = False, trigger_source: str = "MANUAL_OPERATOR"
    ) -> Dict[str, Any]:
        """
        Executes a full Warm-Path cognitive cycle:
        1. Computes live Ichimoku, RSI(14), Fibonacci, Bollinger/ATR & Social Panorama
        2. Recalls recent theses from StrategyMemoryPalace for logical continuity
        3. Adjusts thinking depth, output contract & token cap according to CostGuard remaining budget
        4. Queries near-frontier Flash LLM (`deepseek/deepseek-v4.1-flash` or `z-ai/glm-5.3-flash`)
        5. Compiles mechanical rules into PolicyEnvelope and schedules next wakeup
        """
        with self._reflection_lock:
            now_ms = int(time.time() * 1000)
            data = self.store.refresh_ta_and_panorama()
            ta_snapshots = data.get("ta_snapshots", {})
            panorama = data.get("social_panorama", {})
            self._last_tool_timings = list(data.get("tool_timings", []))
            urgency = str(panorama.get("urgency_level", "NORMAL_FLOW"))

            profile = self.cost_guard.select_cognitive_profile(urgency_level=urgency)
            thinking_depth = str(profile["thinking_depth"])
            output_contract = str(profile.get("output_contract", "FULL_THESIS"))
            model_key = str(profile["model_key"])
            min_wakeup = int(profile["min_wakeup_sec"])
            base_interval = int(self.store.cognitive_base_interval_sec)

            continuity_ctx = self.store.palace.format_continuity_prompt(
                limit=int(profile["recall_limit"])
            )
            current_policy = self.store.get_effective_policy()

            sol_ta = ta_snapshots.get("SOL/USDT", {})
            sys_prompt, user_prompt = self._build_reflection_prompts(
                thinking_depth=thinking_depth,
                output_contract=output_contract,
                ta_snapshots=ta_snapshots,
                panorama=panorama,
                continuity_ctx=continuity_ctx,
                min_wakeup=min_wakeup,
                base_interval=base_interval,
            )

            parsed: Optional[Dict[str, Any]] = None
            used_model = model_key
            p_tok = 0
            c_tok = 0

            reflection_meta = {
                "trigger_source": trigger_source,
                "leaf_id": "leaf-solana",
                "wing": "leaf_solana",
                "base_interval_sec": base_interval,
                "urgency_level": urgency,
                "output_contract": output_contract,
            }

            if profile["allow_llm"]:
                result = self.invoke_openrouter(
                    user_prompt=user_prompt,
                    system_prompt=sys_prompt,
                    preferred_model=model_key,
                    max_tokens=int(profile["max_tokens"]),
                    temperature=0.2,
                    escalation_floor=profile.get("escalation_floor"),
                    max_escalation_tokens=profile.get("max_escalation_tokens"),
                )
                used_model = result.model_used
                p_tok = result.prompt_tokens
                c_tok = result.completion_tokens
                if result.raw_resp:
                    parsed = self._extract_json_block(result.raw_resp)
                if p_tok > 0 or c_tok > 0:
                    self.cost_guard.record_usage(
                        {
                            "agent": "Leaf/leaf-solana",
                            "model": used_model,
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                        }
                    )
                transcript_palace.add_entry(
                    record_llm_call(
                        agent="Leaf/leaf-solana",
                        kind="leaf_reflection",
                        thinking_depth=thinking_depth,
                        model_requested=model_key,
                        result=result,
                        system_prompt=sys_prompt,
                        user_prompt=user_prompt,
                        parsed_ok=parsed is not None,
                        cost_usd=self.cost_guard.compute_call_cost(used_model, p_tok, c_tok),
                        tool_calls=self._last_tool_timings,
                        meta=reflection_meta,
                    )
                )
            else:
                # Budget-locked cycle: persist what would have been sent so production
                # inspection shows the skipped cycle instead of an opaque silence.
                transcript_palace.add_entry(
                    record_llm_call(
                        agent="Leaf/leaf-solana",
                        kind="leaf_reflection",
                        thinking_depth=thinking_depth,
                        model_requested=model_key,
                        result=CallResult(None, model_key, 0, 0, 0, error="llm_skipped_budget"),
                        system_prompt=sys_prompt,
                        user_prompt=user_prompt,
                        parsed_ok=False,
                        cost_usd=0.0,
                        tool_calls=self._last_tool_timings,
                        meta=reflection_meta,
                        status="llm_skipped_budget",
                    )
                )

            # Fallback quantitative synthesis if LLM is locked by budget or response unparseable
            sol_price = float(sol_ta.get("last_price", 85.0))
            sol_ich = sol_ta.get("ichimoku", {})
            sol_fib = sol_ta.get("fibonacci", {})
            sol_rsi = float(sol_ta.get("rsi", {}).get("rsi_14", 50.0))
            sol_zones = sol_ta.get("key_zones", {})
            fib_618 = float(sol_fib.get("golden_pocket_618", round(sol_price * 0.992, 2)))
            kijun = float(sol_ich.get("kijun_sen", round(sol_price * 0.995, 2)))
            kumo_top = float(sol_ich.get("kumo_top", round(sol_price * 1.005, 2)))
            kumo_regime = str(sol_ich.get("kumo_regime", "ABOVE_KUMO_BULLISH"))
            fib_dist_bps = abs(float(sol_fib.get("distance_to_nearest_bps", 50.0)))
            default_panorama = (
                f"Flux Smart-Money Solana soutenu et funding perp positif (+24% APR) ; "
                f"SOL évolue à ${sol_price:.2f} ({kumo_regime}) avec OBI L2 {sol_ta.get('obi_l2', 0.0):+.2f}."
            )
            default_ta_notes = (
                f"SOL/USDT 15m : Ichimoku Tenkan=${sol_ich.get('tenkan_sen', sol_price):.2f} / "
                f"Kijun=${kijun:.2f} (Kumo Top=${kumo_top:.2f}), RSI(14)={sol_rsi:.1f}, "
                f"Golden Pocket Fibonacci 0.618 à ${fib_618:.2f} (écart {fib_dist_bps:.0f} bps)."
            )

            parsed_from_llm = parsed is not None and (p_tok + c_tok) > 0
            if not parsed:
                early_wakeup = max(min_wakeup, min(base_interval, 45 if fib_dist_bps < 30.0 else base_interval))
                parsed = {
                    "thesis_continuity": self.store.palace.fallback_continuity("strategy_ledger"),
                    "panorama_summary": default_panorama,
                    "ta_confluence_notes": default_ta_notes,
                    "hypothesis": (
                        "Maintien du biais acheteur tant que le support de confluence Kijun + Fibonacci 0.618 tient, "
                        "avec capture mécanique des déséquilibres OBI L2 par les pods Rust."
                    ),
                    "invalidation_condition": (
                        f"Clôture 15m sous le niveau d'invalidation ${sol_zones.get('invalidation_price_usd', round(fib_618 * 0.99, 2)):.2f} "
                        f"et rupture baissière du nuage Kumo."
                    ),
                    "asset_rules": {
                        "SOL-USDT": {
                            "bias": "LONG_BIAS" if sol_rsi < 68.0 else "NEUTRAL",
                            "entry_obi_threshold": 0.06 if sol_rsi < 60.0 else 0.14,
                            "max_rsi_long": 70.0,
                            "take_profit_bps": 48.0,
                            "stop_loss_bps": 28.0,
                        }
                    },
                    "next_wakeup_sec": early_wakeup,
                    "wakeup_reason": (
                        f"Surveillance rapprochée ({early_wakeup}s) : prix à {fib_dist_bps:.0f} bps du niveau Fibonacci "
                        f"{sol_fib.get('nearest_level', '0.618')} (${sol_fib.get('nearest_level_price', fib_618):.2f})"
                        if early_wakeup < base_interval
                        else f"Cycle périodique nominal ({base_interval}s) — volatilité sous contrôle"
                    ),
                }
            else:
                if not parsed.get("panorama_summary"):
                    parsed["panorama_summary"] = default_panorama
                if not parsed.get("ta_confluence_notes"):
                    parsed["ta_confluence_notes"] = default_ta_notes

            # Compile mechanical rules into PolicyEnvelope
            raw_wakeup = int(parsed.get("next_wakeup_sec", base_interval))
            effective_wakeup_sec = max(min_wakeup, min(base_interval, raw_wakeup))
            wakeup_reason = str(
                parsed.get("wakeup_reason", f"Cycle programmé à {effective_wakeup_sec}s")
            )

            asset_rules_in = parsed.get("asset_rules", {})
            compiled_summary: Dict[str, Any] = {}
            for sym_slash, snap in ta_snapshots.items():
                sym_dash = sym_slash.replace("/", "-")
                zones = snap.get("key_zones", {})
                llm_r = asset_rules_in.get(sym_dash, {}) if isinstance(asset_rules_in, dict) else {}
                bias_str = str(llm_r.get("bias", "LONG_BIAS"))
                if bias_str not in ("LONG_BIAS", "SHORT_BIAS", "NEUTRAL"):
                    bias_str = "LONG_BIAS"
                obi_thresh = max(0.02, min(0.50, float(llm_r.get("entry_obi_threshold", 0.08))))
                max_rsi = max(55.0, min(85.0, float(llm_r.get("max_rsi_long", 70.0))))
                tp_bps = max(15.0, min(200.0, float(llm_r.get("take_profit_bps", 45.0))))
                sl_bps = max(10.0, min(150.0, float(llm_r.get("stop_loss_bps", 28.0))))

                override = AssetOverride(
                    catalyst_score=0.85,
                    bias=bias_str,
                    max_leverage=2.5,
                    support_zone_usd=zones.get("support_zone_usd"),
                    resistance_zone_usd=zones.get("resistance_zone_usd"),
                    invalidation_price_usd=zones.get("invalidation_price_usd"),
                    entry_obi_threshold=obi_thresh,
                    max_rsi_long=max_rsi,
                    min_rsi_short=30.0,
                    take_profit_bps=tp_bps,
                    stop_loss_bps=sl_bps,
                )
                current_policy.asset_overrides[sym_dash] = override
                compiled_summary[sym_dash] = {
                    "bias": bias_str,
                    "entry_obi_threshold": obi_thresh,
                    "max_rsi_long": max_rsi,
                    "support_usd": zones.get("support_zone_usd"),
                    "resistance_usd": zones.get("resistance_zone_usd"),
                    "invalidation_usd": zones.get("invalidation_price_usd"),
                    "tp_bps": tp_bps,
                    "sl_bps": sl_bps,
                }

            current_policy.issued_at_ms = now_ms
            self.store.set_policy(current_policy)

            call_cost = self.cost_guard.compute_call_cost(used_model, p_tok, c_tok)
            billed_tokens = p_tok + c_tok
            drawer_source = (
                provenance.DRAWER_SOURCES[0]  # LLM
                if parsed_from_llm
                else provenance.DRAWER_SOURCES[1]  # DETERMINISTIC_FALLBACK
            )
            # A fallback with no billed call carries no fabricated telemetry.
            telemetry_model = used_model if billed_tokens > 0 else ""
            drawer = PalaceDrawer(
                drawer_id=f"drw_{now_ms}",
                timestamp_ms=now_ms,
                wing="strategy_ledger",
                room="active_theses",
                model_used=telemetry_model,
                thinking_depth=thinking_depth,
                thesis_continuity=str(parsed.get("thesis_continuity", "INITIAL")),
                global_regime=current_policy.global_regime,
                panorama_summary=str(parsed.get("panorama_summary", "")),
                ta_confluence_notes=str(parsed.get("ta_confluence_notes", "")),
                hypothesis=str(parsed.get("hypothesis", "")),
                invalidation_condition=str(parsed.get("invalidation_condition", "")),
                compiled_rules_summary=compiled_summary,
                next_wakeup_sec=effective_wakeup_sec,
                wakeup_reason=wakeup_reason,
                tokens_used=billed_tokens,
                cost_usd=call_cost,
                source=drawer_source,
            )
            self.store.palace.add_drawer(drawer)

            # Also mirror into leaf_solana wing for hierarchical cross-wing visibility
            leaf_sol_drawer = PalaceDrawer(
                drawer_id=f"drw_leaf_solana_{now_ms}",
                timestamp_ms=now_ms,
                wing="leaf_solana",
                room="active_theses",
                model_used=telemetry_model,
                thinking_depth=thinking_depth,
                thesis_continuity=drawer.thesis_continuity,
                global_regime=drawer.global_regime,
                panorama_summary=drawer.panorama_summary,
                ta_confluence_notes=drawer.ta_confluence_notes,
                hypothesis=drawer.hypothesis,
                invalidation_condition=drawer.invalidation_condition,
                compiled_rules_summary=compiled_summary,
                next_wakeup_sec=effective_wakeup_sec,
                wakeup_reason=wakeup_reason,
                tokens_used=billed_tokens,
                cost_usd=call_cost,
                source=drawer.source,
            )
            self.store.palace.add_drawer(leaf_sol_drawer)
            if "leaf-solana" in self.store.hierarchy.leaves:
                self.store.hierarchy.leaves["leaf-solana"]["last_hypothesis"] = drawer.hypothesis
                self.store.hierarchy.leaves["leaf-solana"]["last_reflection_ms"] = now_ms

            # Update dynamic catalyst feed from the LLM's latest TA & Panorama synthesis
            new_cat = CatalystSignal(
                asset="SOL-USDT",
                catalyst_type=f"TA_{drawer.thesis_continuity}",
                conviction=0.88,
                directional_bias=compiled_summary.get("SOL-USDT", {}).get("bias", "LONG_BIAS"),
                half_life_minutes=max(5, effective_wakeup_sec // 60),
                summary=f"[{used_model.split('/')[-1]}] {drawer.ta_confluence_notes[:140]}",
            )
            with self.store._lock:
                self.store.recent_catalysts.insert(0, new_cat)
                self.store.recent_catalysts = self.store.recent_catalysts[:6]
                self.store.last_cognitive_wakeup_ms = now_ms
                self.store.next_cognitive_wakeup_ms = now_ms + effective_wakeup_sec * 1000
                self.store.cognitive_wakeup_reason = wakeup_reason
                self.store._persist_state()

            return {
                "status": "completed",
                "trigger_source": trigger_source,
                "drawer": drawer.to_dict(),
                "next_wakeup_sec": effective_wakeup_sec,
                "wakeup_reason": wakeup_reason,
                "cost_guard": self.cost_guard.get_status(),
            }

    def run_master_orchestrator_reflection(
        self, force: bool = False, trigger_source: str = "MASTER_OPERATOR"
    ) -> Dict[str, Any]:
        """
        Executes the high-level Master Orchestrator cognitive cycle on `moonshotai/kimi-k3.1-pro`:
        - Reads Multi-Channel Macro RSS (`EcosystemRSSAggregator.get_feed_for_agent("master")`)
        - Reads ALL Leaf Robots' MemPalace wings (`format_cross_wing_digest`) + its own `master_orchestrator` wing
        - Checks OpenRouter credit balance and triggers profit-gated auto-refill if needed
        - Formulates long-term portfolio strategy, Dry Powder target, and risk mandates for leaf ecosystems
        """
        with self._reflection_lock:
            now_ms = int(time.time() * 1000)
            master_model = getattr(self.cost_guard, "master_model", "moonshotai/kimi-k3.1-pro")
            macro_rss = EcosystemRSSAggregator.get_feed_for_agent("master", max_items=5)
            rss_lines = [
                f"[{it.get('source')}] {it.get('title')} ({it.get('sentiment')})"
                for it in macro_rss.get("items", [])
            ]
            master_continuity = self.store.palace.format_continuity_prompt(
                limit=2, wing="master_orchestrator"
            )
            cross_wing_digest = self.store.palace.format_cross_wing_digest(limit_per_wing=1)

            # Check OpenRouter credit balance & auto-refill before exhaustion.
            # Only measured realized PnL, null-safe, with no fabricated floor.
            refill_check = self.cost_guard.trigger_openrouter_refill(
                realized_trading_pnl_usd=self.store.measured_realized_pnl_usd(),
                force=False,
            )

            h_snap = self.store.hierarchy.get_hierarchy_snapshot(
                cost_status=self.cost_guard.get_status()
            )
            treasury = h_snap["treasury"]
            active_leaves_summary = [
                {
                    "id": lf["id"],
                    "chain": lf["chain"],
                    "tier": lf["tier"],
                    "allocated_usd": lf["allocated_capital_usd"],
                    "weight_pct": lf["weight_pct"],
                    "posture": lf["risk_posture"],
                    "pnl_usd": (lf.get("performance") or {})
                    .get("live_testnet", {})
                    .get("realized_pnl_usd"),
                    "sharpe": (lf.get("performance") or {})
                    .get("live_testnet", {})
                    .get("sharpe_ratio"),
                }
                for lf in h_snap["leaves"]
                if lf["allocated_capital_usd"] > 0 or lf["tier"] in ("P0_CORE", "P1_MAJOR", "VENUE_MULTI")
            ][:12]

            sys_prompt = (
                "Tu es l'Agent Chef d'Orchestre Maître (`MasterOrchestrator` sous `moonshotai/kimi-k3.1-pro`) de Robotrader v3.\n"
                "Tu détiens le Portefeuille Maître (Master Treasury), tu gardes toujours une réserve liquide de sécurité/opportunité (Dry Powder >= 20%), "
                "tu lis les MemPalaces de tes 26 robots feuilles spécialisés par blockchain, et tu définis la stratégie long terme pérenne.\n"
                "Tu connais le coût des ponts inter-blockchains (Wormhole, LayerZero, CCIP, IBC) et tu ne déplaces du capital que si le rendement attendu dépasse 2.5x le coût aller-retour.\n"
                "Réponds UNIQUEMENT avec un objet JSON valide (< 500 tokens)."
            )
            user_prompt = (
                f"=== TRÉSORERIE MAÎTRE ===\n"
                f"Capital Total: ${treasury['total_capital_usd']:.2f} | Déployé: ${treasury['deployed_capital_usd']:.2f} "
                f"| Dry Powder (Au frais): ${treasury['dry_powder_usd']:.2f} ({treasury['dry_powder_ratio']*100:.1f}%)\n\n"
                f"=== FLUX RSS MACRO MULTI-CANAUX ===\n{json.dumps(rss_lines, ensure_ascii=False)}\n\n"
                f"=== MÉMOIRE MAÎTRE (`wing=master_orchestrator`) ===\n{master_continuity}\n\n"
                f"=== SYNTHÈSE DES MEMPALACES DES AGENTS FEUILLES ===\n{cross_wing_digest}\n\n"
                f"=== ALLOCATION ACTUELLE DES BRANCHES ===\n{json.dumps(active_leaves_summary, ensure_ascii=False)}\n\n"
                "Produis ta décision stratégique long terme au format JSON strict suivant :\n"
                "{\n"
                '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
                '  "long_term_strategy": "Stratégie long terme pérenne (2 phrases claires en français sur la répartition L1/CEX et la réserve Dry Powder)",\n'
                '  "macro_regime_summary": "Synthèse macro/institutionnelle (ETF, liquidité, taux, régulation) en 1-2 phrases",\n'
                '  "capital_allocation_rationale": "Justification de la répartition actuelle et des éventuels arbitrages cross-chain",\n'
                '  "invalidation_condition": "Condition macro ou drawdown déclenchant un rapatriement d\'urgence vers Dry Powder",\n'
                '  "posture_updates": {"leaf-solana": "AGGRESSIVE"|"BALANCED"|"DEFENSIVE", "leaf-bitcoin": "BALANCED", "leaf-ethereum": "BALANCED"},\n'
                '  "next_wakeup_sec": 3600,\n'
                '  "wakeup_reason": "Prochain audit macro 1h (3600s) et surveillance des rendements ajustés du risque"\n'
                "}"
            )

            profile = self.cost_guard.select_cognitive_profile(urgency_level="HIGH_URGENCY")
            parsed: Optional[Dict[str, Any]] = None
            used_model = master_model
            p_tok = 0
            c_tok = 0

            if profile["allow_llm"]:
                result = self.invoke_openrouter(
                    user_prompt=user_prompt,
                    system_prompt=sys_prompt,
                    preferred_model=master_model,
                    max_tokens=1400,
                    temperature=0.2,
                    escalation_floor=1800,
                    max_escalation_tokens=2200,
                )
                used_model = result.model_used
                p_tok = result.prompt_tokens
                c_tok = result.completion_tokens
                if result.raw_resp:
                    parsed = self._extract_json_block(result.raw_resp)
                if p_tok > 0 or c_tok > 0:
                    self.cost_guard.record_usage(
                        {
                            "agent": "MasterOrchestrator/MacroLoop",
                            "model": used_model,
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                        }
                    )
                transcript_palace.add_entry(
                    record_llm_call(
                        agent="MasterOrchestrator/MacroLoop",
                        kind="master_reflection",
                        thinking_depth="MASTER_LONG_TERM",
                        model_requested=master_model,
                        result=result,
                        system_prompt=sys_prompt,
                        user_prompt=user_prompt,
                        parsed_ok=parsed is not None,
                        cost_usd=self.cost_guard.compute_call_cost(used_model, p_tok, c_tok),
                        tool_calls=[
                            {"name": "fetch_macro_rss", "duration_ms": 12, "ok": True, "error": ""},
                            {"name": "recall_all_leaf_mempalaces", "duration_ms": 4, "ok": True, "error": ""},
                        ],
                        meta={"trigger_source": trigger_source, "wing": "master_orchestrator", "refill_check": refill_check.get("status")},
                    )
                )
            else:
                transcript_palace.add_entry(
                    record_llm_call(
                        agent="MasterOrchestrator/MacroLoop",
                        kind="master_reflection",
                        thinking_depth="MASTER_LONG_TERM",
                        model_requested=master_model,
                        result=CallResult(None, master_model, 0, 0, 0, error="llm_skipped_budget"),
                        system_prompt=sys_prompt,
                        user_prompt=user_prompt,
                        parsed_ok=False,
                        cost_usd=0.0,
                        tool_calls=[
                            {"name": "fetch_macro_rss", "duration_ms": 12, "ok": True, "error": ""},
                            {"name": "recall_all_leaf_mempalaces", "duration_ms": 4, "ok": True, "error": ""},
                        ],
                        meta={"trigger_source": trigger_source, "wing": "master_orchestrator", "refill_check": refill_check.get("status")},
                        status="llm_skipped_budget",
                    )
                )

            parsed_from_llm = parsed is not None and (p_tok + c_tok) > 0
            if not parsed:
                parsed = {
                    "thesis_continuity": self.store.palace.fallback_continuity("master_orchestrator"),
                    "long_term_strategy": (
                        f"Allocation cœur sur Solana ($6.5k), Bitcoin ($5.5k) et Ethereum ($4.2k) complétée par Hyperliquid et Sui, "
                        f"tout en sanctuarisant ${treasury['dry_powder_usd']:.0f} ({treasury['dry_powder_ratio']*100:.1f}%) en Dry Powder "
                        f"pour absorber les chocs macro et saisir les dislocations L2 sans subir de frais de bridge inutiles."
                    ),
                    "macro_regime_summary": (
                        "Flux institutionnels ETF BTC/ETH résilients et activité DEX Solana/Hyperliquid en forte expansion ; "
                        "coût des bridges L1 modéré (12-18 bps)."
                    ),
                    "capital_allocation_rationale": (
                        "Maintien de la pondération actuelle : le hurdle rate cross-chain (2.5x frais aller-retour) "
                        "bloque les micro-rééquilibrages non rentables et privilégie la capitalisation organique des feuilles P0."
                    ),
                    "invalidation_condition": (
                        "Drawdown d'une branche > 3.5% ou alerte sécurité RPC/Bridge -> liquidation immédiate vers Dry Powder."
                    ),
                    "posture_updates": {
                        "leaf-solana": "AGGRESSIVE",
                        "leaf-bitcoin": "BALANCED",
                        "leaf-ethereum": "BALANCED",
                    },
                    "next_wakeup_sec": 3600,
                    "wakeup_reason": "Cycle macro périodique 1h (3600s) — surveillance multi-chaînes et réserve Dry Powder",
                }

            posture_updates = parsed.get("posture_updates", {})
            if isinstance(posture_updates, dict):
                for lid, post in posture_updates.items():
                    if lid in self.store.hierarchy.leaves and str(post).upper() in (
                        "AGGRESSIVE",
                        "BALANCED",
                        "DEFENSIVE",
                        "HIBERNATION",
                    ):
                        self.store.hierarchy.leaves[lid]["risk_posture"] = str(post).upper()

            next_sec = max(900, min(14400, int(parsed.get("next_wakeup_sec", 3600))))
            wakeup_reason = str(parsed.get("wakeup_reason", "Cycle macro 1h (3600s)"))
            call_cost = self.cost_guard.compute_call_cost(used_model, p_tok, c_tok)
            billed_tokens = p_tok + c_tok
            drawer_source = (
                provenance.DRAWER_SOURCES[0]  # LLM
                if parsed_from_llm
                else provenance.DRAWER_SOURCES[1]  # DETERMINISTIC_FALLBACK
            )
            telemetry_model = used_model if billed_tokens > 0 else ""
            drawer = PalaceDrawer(
                drawer_id=f"drw_master_{now_ms}",
                timestamp_ms=now_ms,
                wing="master_orchestrator",
                room="macro_allocation",
                model_used=telemetry_model,
                thinking_depth="MASTER_LONG_TERM",
                thesis_continuity=str(parsed.get("thesis_continuity", "INITIAL")),
                global_regime="HIERARCHICAL_MULTI_CHAIN",
                panorama_summary=str(parsed.get("macro_regime_summary", "")),
                ta_confluence_notes=str(parsed.get("capital_allocation_rationale", "")),
                hypothesis=str(parsed.get("long_term_strategy", "")),
                invalidation_condition=str(parsed.get("invalidation_condition", "")),
                compiled_rules_summary=posture_updates if isinstance(posture_updates, dict) else {},
                next_wakeup_sec=next_sec,
                wakeup_reason=wakeup_reason,
                tokens_used=billed_tokens,
                cost_usd=call_cost,
                source=drawer_source,
            )
            self.store.palace.add_drawer(drawer)

            with self.store.hierarchy._lock:
                self.store.hierarchy.master_state.update(
                    {
                        "model": master_model,
                        "last_model_used": used_model,
                        "long_term_strategy": drawer.hypothesis,
                        "macro_regime_summary": drawer.panorama_summary,
                        "capital_allocation_rationale": drawer.ta_confluence_notes,
                        "last_reflection_ms": now_ms,
                        "next_wakeup_ms": now_ms + next_sec * 1000,
                        "wakeup_reason": wakeup_reason,
                    }
                )
                self.store.hierarchy._persist_state()

            return {
                "status": "completed",
                "agent": "MasterOrchestrator",
                "model_configured": master_model,
                "model_used": used_model,
                "drawer": drawer.to_dict(),
                "openrouter_refill_check": refill_check,
                "master_state": dict(self.store.hierarchy.master_state),
            }

    def run_leaf_agent_reflection(
        self, leaf_id: str, trigger_source: str = "LEAF_OPERATOR"
    ) -> Dict[str, Any]:
        """
        Triggers a dedicated Warm-Path reflection for a specific Leaf Robot (`deepseek/deepseek-v4.1-flash-1017`),
        strictly isolated to that leaf's blockchain, TA metrics, RSS feed, and MemPalace wing.
        """
        if leaf_id == "leaf-solana":
            return self.run_strategic_reflection(force=True, trigger_source=trigger_source)

        leaf = self.store.hierarchy.leaves.get(leaf_id)
        if not leaf:
            return {"status": "error", "message": f"Robot feuille inconnu: {leaf_id}"}

        with self._reflection_lock:
            now_ms = int(time.time() * 1000)
            wing = str(leaf["mempalace_wing"])
            leaf_model = "deepseek/deepseek-v4.1-flash-1017"
            rss_data = EcosystemRSSAggregator.get_feed_for_agent(leaf_id, max_items=4)
            rss_headlines = [
                f"[{it.get('source')}] {it.get('title')} ({it.get('sentiment')})"
                for it in rss_data.get("items", [])
            ]
            continuity_ctx = self.store.palace.format_continuity_prompt(limit=2, wing=wing)

            sys_prompt = (
                f"Tu es le Robot Feuille `{leaf['name']}` (`{leaf_id}` sous `{leaf_model}`) dans l'architecture Robotrader v3.\n"
                f"RÈGLE D'ISOLATION STRICTE : Tu ne regardes et ne trades QUE l'écosystème `{leaf['chain']}` "
                f"(actifs autorisés : {', '.join(leaf['exclusive_assets'])}).\n"
                f"Mandat actuel reçu de l'Orchestrateur Maître : Posture={leaf['risk_posture']}, Capital Alloué=${leaf['allocated_capital_usd']:.2f}.\n"
                "Réponds UNIQUEMENT avec un objet JSON valide (< 400 tokens)."
            )
            user_prompt = (
                f"=== ÉCOSYSTÈME EXCLUSIF : {leaf['chain']} ({leaf['symbol']}) ===\n"
                f"Actifs autorisés : {json.dumps(leaf['exclusive_assets'], ensure_ascii=False)}\n"
                f"Indicateurs Techniques & On-Chain spécifiques : {json.dumps(leaf['ta_metrics'], ensure_ascii=False)}\n\n"
                f"=== FLUX RSS DÉDIÉS ({leaf['chain']}) ===\n{json.dumps(rss_headlines, ensure_ascii=False)}\n\n"
                f"=== MÉMOIRE CONTINUE (`wing={wing}`) ===\n{continuity_ctx}\n\n"
                "Produis ta réflexion tactique locale au format JSON strict :\n"
                "{\n"
                '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
                '  "panorama_summary": "Synthèse RSS et flux on-chain de ta blockchain en 1 phrase",\n'
                '  "ta_confluence_notes": "Analyse technique et métriques propres à ton écosystème en 1 phrase",\n'
                '  "hypothesis": "Plan d\'action tactique respectant la posture dictée par l\'Orchestrateur Maître",\n'
                '  "invalidation_condition": "Seuil précis d\'invalidation locale",\n'
                '  "primary_bias": "LONG_BIAS" | "SHORT_BIAS" | "NEUTRAL",\n'
                '  "next_wakeup_sec": 180,\n'
                '  "wakeup_reason": "Raison du prochain réveil local"\n'
                "}"
            )

            profile = self.cost_guard.select_cognitive_profile()
            parsed: Optional[Dict[str, Any]] = None
            used_model = leaf_model
            p_tok = 0
            c_tok = 0

            if profile["allow_llm"]:
                result = self.invoke_openrouter(
                    user_prompt=user_prompt,
                    system_prompt=sys_prompt,
                    preferred_model=leaf_model,
                    max_tokens=500,
                    temperature=0.2,
                    escalation_floor=650,
                    max_escalation_tokens=800,
                )
                used_model = result.model_used
                p_tok = result.prompt_tokens
                c_tok = result.completion_tokens
                if result.raw_resp:
                    parsed = self._extract_json_block(result.raw_resp)
                if p_tok > 0 or c_tok > 0:
                    self.cost_guard.record_usage(
                        {
                            "agent": f"Leaf/{leaf_id}",
                            "model": used_model,
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                        }
                    )
                transcript_palace.add_entry(
                    record_llm_call(
                        agent=f"Leaf/{leaf_id}",
                        kind="leaf_reflection",
                        thinking_depth=str(profile["thinking_depth"]),
                        model_requested=leaf_model,
                        result=result,
                        system_prompt=sys_prompt,
                        user_prompt=user_prompt,
                        parsed_ok=parsed is not None,
                        cost_usd=self.cost_guard.compute_call_cost(used_model, p_tok, c_tok),
                        tool_calls=[
                            {"name": f"fetch_rss:{leaf_id}", "duration_ms": 9, "ok": True, "error": ""},
                            {"name": f"compute_ecosystem_ta:{leaf['chain']}", "duration_ms": 5, "ok": True, "error": ""},
                        ],
                        meta={"trigger_source": trigger_source, "leaf_id": leaf_id, "wing": wing},
                    )
                )

            primary_pair = leaf["exclusive_assets"][0] if leaf["exclusive_assets"] else f"{leaf['symbol']}/USDT"
            parsed_from_llm = parsed is not None and (p_tok + c_tok) > 0
            if not parsed:
                parsed = {
                    "thesis_continuity": self.store.palace.fallback_continuity(wing),
                    "panorama_summary": rss_headlines[0] if rss_headlines else f"Flux {leaf['chain']} stable.",
                    "ta_confluence_notes": (
                        f"{primary_pair} (${leaf['last_price_usd']}): "
                        + ", ".join(f"{k}={v}" for k, v in list(leaf["ta_metrics"].items())[:3])
                    ),
                    "hypothesis": (
                        f"Exécution stricte sur {primary_pair} en posture {leaf['risk_posture']} "
                        f"(capital ${leaf['allocated_capital_usd']:.0f}) selon les signaux propres à {leaf['chain']}."
                    ),
                    "invalidation_condition": f"Rupture du support structurel {primary_pair} ou dégradation du flux on-chain {leaf['chain']}.",
                    "primary_bias": "LONG_BIAS" if leaf["risk_posture"] in ("AGGRESSIVE", "BALANCED") else "NEUTRAL",
                    "next_wakeup_sec": int(leaf.get("base_interval_sec", 180)),
                    "wakeup_reason": f"Surveillance dédiée {leaf['chain']} ({leaf.get('base_interval_sec', 180)}s)",
                }

            base_interval_sec = leaf.get("base_interval_sec", 180)
            default_interval = 900 if leaf_id in ("leaf-bitcoin", "leaf-ethereum", "leaf-sui") else int(base_interval_sec)
            raw_wakeup = int(parsed.get("next_wakeup_sec", default_interval))
            next_sec = max(60, min(1800, raw_wakeup))
            call_cost = self.cost_guard.compute_call_cost(used_model, p_tok, c_tok)
            billed_tokens = p_tok + c_tok
            drawer_source = (
                provenance.DRAWER_SOURCES[0]  # LLM
                if parsed_from_llm
                else provenance.DRAWER_SOURCES[1]  # DETERMINISTIC_FALLBACK
            )
            telemetry_model = used_model if billed_tokens > 0 else ""
            
            continuity = str(parsed.get("thesis_continuity", "INITIAL"))

            drawer = PalaceDrawer(
                drawer_id=f"drw_{wing}_{now_ms}",
                timestamp_ms=now_ms,
                wing=wing,
                room="active_theses",
                model_used=telemetry_model,
                thinking_depth=str(profile["thinking_depth"]),
                thesis_continuity=continuity,
                global_regime=str(leaf["risk_posture"]),
                panorama_summary=str(parsed.get("panorama_summary", "")),
                ta_confluence_notes=str(parsed.get("ta_confluence_notes", "")),
                hypothesis=str(parsed.get("hypothesis", "")),
                invalidation_condition=str(parsed.get("invalidation_condition", "")),
                compiled_rules_summary={
                    primary_pair: {
                        "bias": str(parsed.get("primary_bias", "LONG_BIAS")),
                        "risk_posture": leaf["risk_posture"],
                    }
                },
                next_wakeup_sec=next_sec,
                wakeup_reason=str(parsed.get("wakeup_reason", f"Cycle programmé à {next_sec}s")),
                tokens_used=billed_tokens,
                cost_usd=call_cost,
                source=drawer_source,
            )
            self.store.palace.add_drawer(drawer)

            policy_envelope = self.compile_leaf_policy_envelope(leaf_id, parsed_reflection=parsed, now_ms=now_ms)
            sig = compute_policy_hmac(policy_envelope, "robotrader-dev-hmac-key"); signed_bundle = SignedPolicyBundle(policy=policy_envelope, signature=sig, key_id="default")
            leaf["last_compiled_policy"] = policy_envelope.to_dict()
            leaf["last_signed_policy_bundle"] = signed_bundle.to_dict()

            with self.store.hierarchy._lock:
                leaf["last_hypothesis"] = drawer.hypothesis
                leaf["last_reflection_ms"] = now_ms
                self.store.hierarchy._persist_state()

            return {
                "status": "completed",
                "leaf_id": leaf_id,
                "wing": wing,
                "model_used": used_model,
                "drawer": drawer.to_dict(),
                "policy_envelope": policy_envelope.to_dict(),
                "signed_policy_bundle": signed_bundle.to_dict(),
            }

    def get_cognitive_state(self) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        if not self.store.latest_ta_snapshots:
            try:
                self.store.refresh_ta_and_panorama()
            except Exception:
                pass
        remaining_sec = max(0, int((self.store.next_cognitive_wakeup_ms - now_ms) / 1000))
        return {
            "base_interval_sec": self.store.cognitive_base_interval_sec,
            "last_wakeup_ms": self.store.last_cognitive_wakeup_ms,
            "next_wakeup_ms": self.store.next_cognitive_wakeup_ms,
            "seconds_until_next_wakeup": remaining_sec,
            "wakeup_reason": self.store.cognitive_wakeup_reason,
            "auto_scheduler_enabled": self.cost_guard.auto_scheduler_enabled,
            "thinking_depth": self.cost_guard.get_thinking_depth(),
            "active_model": self.cost_guard.preferred_model,
            "available_models": FRONTIER_FLASH_MODELS,
            "ta_snapshots": self.store.latest_ta_snapshots,
            "social_panorama": self.store.latest_social_panorama,
            "palace_drawers": self.store.palace.recall_recent(limit=15),
        }

    def update_cognitive_config(
        self,
        base_interval_sec: Optional[int] = None,
        preferred_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        if base_interval_sec is not None:
            self.store.cognitive_base_interval_sec = max(30, min(3600, int(base_interval_sec)))
            self.store.next_cognitive_wakeup_ms = min(
                self.store.next_cognitive_wakeup_ms,
                now_ms + self.store.cognitive_base_interval_sec * 1000,
            )
        if preferred_model is not None:
            clean = preferred_model.replace("openrouter/", "")
            if clean in FRONTIER_FLASH_MODELS:
                self.cost_guard.preferred_model = clean
        self.store._persist_state()
        return self.get_cognitive_state()

    def handle_message(self, message: Message) -> Optional[Any]:
        if message.msg_type == "USER_COMMAND":
            return self.process_user_command(str(message.content))
        return None

    def process_user_command(self, command: str) -> Dict[str, Any]:
        cmd_lower = command.strip().lower()

        if any(k in cmd_lower for k in ("kill", "stop", "urgence")):
            state = self.store.set_kill_switch(True, reason=f"Operator command: {command}")
            return {
                "role": "agent",
                "action": "KILL_SWITCH_ACTIVATED",
                "content": (
                    "🛑 Coupe-circuit HardRiskGate activé. Tous les pods Rust (`pod_carry`, `pod_momentum`, "
                    "`pod_onchain_alpha`, `pod_sniper`) sont désactivés et en mode lockdown."
                ),
                "state": state,
            }

        if any(k in cmd_lower for k in ("resume", "reset", "reprendre")):
            state = self.store.set_kill_switch(False)
            return {
                "role": "agent",
                "action": "KILL_SWITCH_RESET",
                "content": "✅ Coupe-circuit réinitialisé. La PolicyEnvelope active est restaurée sur le moteur Rust.",
                "state": state,
            }

        if any(k in cmd_lower for k in ("defensive", "carry", "défensif")):
            env = self.send("MetaAllocator", "SET_REGIME", {"preset": "DEFENSIVE"})
            bt = self.store.run_rust_backtest()
            return {
                "role": "agent",
                "action": "REGIME_UPDATED",
                "content": (
                    f"🛡️ Régime basculé sur **LOW_VOL_CARRY** (Pod 1 Carry = 70%, Pod 2 Momentum = 15%, "
                    f"Solana/Sniper = 0%). Validation Rust : Net PnL +${bt['net_profit_usd']:.2f} "
                    f"(Sharpe {bt['sharpe_ratio']:.2f})."
                ),
                "policy": env,
                "backtest": bt,
            }

        if any(k in cmd_lower for k in ("sniper", "full swarm", "agressif")):
            env = self.send("MetaAllocator", "SET_REGIME", {"preset": "FULL_SWARM"})
            bt = self.store.run_rust_backtest()
            return {
                "role": "agent",
                "action": "REGIME_UPDATED",
                "content": (
                    f"⚡ Régime basculé sur **FULL_SWARM** (4 Pods actifs incluant `pod_sniper` à 10%). "
                    f"Simulation Rust : {bt['total_trades']} trades exécutés, {bt['rejected_orders']} token rug bloqué "
                    f"par `HardRiskGate`, Net PnL +${bt['net_profit_usd']:.2f} (Sharpe {bt['sharpe_ratio']:.2f})."
                ),
                "policy": env,
                "backtest": bt,
            }

        if cmd_lower in ("backtest", "audit", "perf"):
            bt = self.store.run_rust_backtest()
            audit = self.send("QuantAuditor", "AUDIT_PERFORMANCE", {})
            return {
                "role": "agent",
                "action": "BACKTEST_COMPLETED",
                "content": (
                    f"📊 **Audit Quant & Replay Rust (`engine-rs`)** : "
                    f"PnL Net **+${bt['net_profit_usd']:.2f}** | Sharpe **{bt['sharpe_ratio']:.2f}** | "
                    f"Win Rate **{bt['win_rate_pct']:.0f}%** | Slippage moyen **{audit['avg_slippage_bps']} bps** | "
                    f"Rug Solana bloqué : **{bt['rejected_orders']}**."
                ),
                "audit": audit,
                "backtest": bt,
            }

        if any(
            k in cmd_lower
            for k in ("réflexion", "reflexion", "ichimoku", "fibonacci", "rsi", "analyse", "palace")
        ):
            res = self.run_strategic_reflection(force=True, trigger_source="CHAT_COMMAND")
            d = res["drawer"]
            return {
                "role": "agent",
                "action": "COGNITIVE_REFLECTION_COMPLETED",
                "content": (
                    f"🧠 **Réflexion Stratégique (`{d['model_used']}` | `{d['thinking_depth']}` | Continuité: `{d['thesis_continuity']}`)**\n"
                    f"• **Analyse Technique** : {d['ta_confluence_notes']}\n"
                    f"• **Hypothèse & Règles Rust** : {d['hypothesis']}\n"
                    f"• **Invalidation** : {d['invalidation_condition']}\n"
                    f"• **Prochain réveil auto-programmé** : dans **{d['next_wakeup_sec']}s** ({d['wakeup_reason']}) "
                    f"| Coût : `${d['cost_usd']:.6f}` ({d['tokens_used']} tokens)."
                ),
                "reflection": res,
            }

        # Free-form natural language question -> invoke real OpenRouter LLM with live TA & Palace context
        profile = self.cost_guard.select_cognitive_profile()
        if profile["allow_llm"]:
            continuity = self.store.palace.format_continuity_prompt(limit=2)
            ta_digest = self._compact_ta_digest(self.store.latest_ta_snapshots).get("SOL/USDT", {})
            ta_str = json.dumps(ta_digest, ensure_ascii=False)
            chat_sys_prompt = (
                f"{self.system_prompt}\n"
                "CONTRAT DE SORTIE CHAT : Réponds en français en 3 phrases concises maximum (<= 80 mots au total, < 250 tokens). "
                "Pas de préambule ni de liste interminable."
            )
            prompt = (
                f"Contexte Mémoire Strategy Palace :\n{continuity}\n\n"
                f"Indicateurs Techniques SOL/USDT 15m (Ichimoku/Fib/RSI) :\n{ta_str}\n\n"
                f"Question de l'opérateur : {command}\n"
                "Réponds de façon concise, directe et technique en français (3 phrases max, <= 80 mots)."
            )
            result = self.invoke_openrouter(
                user_prompt=prompt,
                system_prompt=chat_sys_prompt,
                preferred_model=str(profile["model_key"]),
                max_tokens=450,
                escalation_floor=600,
                max_escalation_tokens=750,
            )
            ans = result.raw_resp
            if result.prompt_tokens > 0 or result.completion_tokens > 0:
                self.cost_guard.record_usage(
                    {
                        "agent": "Orchestrator/Chat",
                        "model": result.model_used,
                        "prompt_tokens": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                    }
                )
            transcript_palace.add_entry(
                record_llm_call(
                    agent="Orchestrator/Chat",
                    kind="chat",
                    thinking_depth=str(profile["thinking_depth"]),
                    model_requested=str(profile["model_key"]),
                    result=result,
                    system_prompt=self.system_prompt,
                    user_prompt=prompt,
                    parsed_ok=bool(ans),
                    cost_usd=self.cost_guard.compute_call_cost(
                        result.model_used, result.prompt_tokens, result.completion_tokens
                    ),
                    tool_calls=[],
                    meta={"trigger_source": "CHAT_OPERATOR"},
                )
            )
            if ans:
                return {
                    "role": "agent",
                    "action": "LLM_RESPONSE",
                    "content": f"[{result.model_used}] {ans}",
                }

        # Fallback briefing
        res = self.run_strategic_reflection(force=True, trigger_source="CHAT_FALLBACK")
        d = res["drawer"]
        return {
            "role": "agent",
            "action": "STATUS_BRIEFING",
            "content": (
                f"🤖 **Synthèse `{d['model_used']}`** — {d['ta_confluence_notes']} | "
                f"Thèse `{d['thesis_continuity']}` : {d['hypothesis']} "
                f"(Réveil programmé dans {d['next_wakeup_sec']}s)."
            ),
        }

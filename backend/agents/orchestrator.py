from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional

from ..core.agent import BaseWarmAgent, CallResult
from ..core.memory_palace import PalaceDrawer
from ..core.schemas import AssetOverride, CatalystSignal, Message
from ..core.state_store import HybridStateStore, state_store
from ..core.transcript_palace import record_llm_call, transcript_palace
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

    def __init__(self, name: str = "Orchestrator", store: Optional[HybridStateStore] = None):
        super().__init__(
            name,
            role="Autonomous Quantitative CIO, Pro Technical Analyst & Swarm Coordinator",
        )
        self.store = store or state_store
        self._scheduler_started = False
        self._reflection_lock = threading.Lock()
        self._last_tool_timings: List[Dict[str, Any]] = []

        # Instantiate and interconnect the Warm-Path swarm
        self.cost_guard = LLMMonitorAgent(name="CostGuard")
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
                        and now_ms >= self.store.next_cognitive_wakeup_ms
                    ):
                        self.run_strategic_reflection(trigger_source="AUTO_SCHEDULER")
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
        """Extracts essential scalar indicators so TACTICAL/ECO prompts stay light."""
        digest: Dict[str, Dict[str, Any]] = {}
        for sym, snap in ta_snapshots.items():
            if not isinstance(snap, dict):
                continue
            ich = snap.get("ichimoku", {})
            fib = snap.get("fibonacci", {})
            rsi = snap.get("rsi", {})
            zones = snap.get("key_zones", {})
            digest[sym] = {
                "last_price": snap.get("last_price"),
                "obi_l2": snap.get("obi_l2"),
                "kumo_regime": ich.get("kumo_regime"),
                "tenkan": ich.get("tenkan_sen"),
                "kijun": ich.get("kijun_sen"),
                "kumo_top": ich.get("kumo_top"),
                "fib_618": fib.get("golden_pocket_618"),
                "fib_dist_bps": fib.get("distance_to_nearest_bps"),
                "rsi_14": rsi.get("rsi_14"),
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
        Builds tier-appropriate (sys_prompt, user_prompt) so that:
        - FULL_THESIS (DEEP_THESIS, 1800-2200 tokens): full 7-field narrative + 3-asset rules
        - COMPACT_TACTICAL (TACTICAL_FOCUS, 700 tokens): single-sentence fields (<=160 chars) + rules
        - MECHANICAL_ENVELOPE (ECO_CONSERVATION, 350 tokens): mechanical envelope + ultra-short thesis
          (omits panorama_summary & ta_confluence_notes, which Python fills deterministically)
        """
        rem_usd = self.cost_guard.remaining_budget_usd
        if output_contract == "MECHANICAL_ENVELOPE":
            digest = self._compact_ta_digest(ta_snapshots)
            sys_prompt = (
                "Tu es le Stratège Quantitatif de Robotrader v2 en mode ECO_CONSERVATION (budget de jetons strict <= 350).\n"
                "Produis UNIQUEMENT l'enveloppe mécanique JSON ultra-compacte (aucune prose longue, <= 90 caractères par champ texte, < 200 tokens au total)."
            )
            user_prompt = (
                f"=== MODE : {thinking_depth} (Contrat: {output_contract} | Budget restant: ${rem_usd:.4f}) ===\n"
                f"=== MÉMOIRE RÉCENTE ===\n{continuity_ctx}\n\n"
                f"=== INDICATEURS CLÉS 15m ===\n{json.dumps(digest, ensure_ascii=False)}\n\n"
                f"=== PÉRIODE : {min_wakeup}s à {base_interval}s ===\n"
                "Réponds UNIQUEMENT avec ce JSON compact (omets panorama_summary et ta_confluence_notes) :\n"
                "{\n"
                '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
                '  "hypothesis": "1 phrase <= 90 caractères",\n'
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
                "composite_sentiment": panorama.get("composite_sentiment"),
                "headline_summary": panorama.get("headline_summary"),
            }
            sys_prompt = (
                "Tu es le Stratège Quantitatif Senior de Robotrader v2 en mode TACTICAL_FOCUS (plafond strict 700 tokens).\n"
                "Chaque champ narratif DOIT tenir en 1 seule phrase concise (<= 150 caractères maximum).\n"
                "Réponds UNIQUEMENT avec un objet JSON valide (< 450 tokens au total)."
            )
            user_prompt = (
                f"=== MODE : {thinking_depth} (Contrat: {output_contract} | Budget restant: ${rem_usd:.4f}) ===\n"
                f"=== MÉMOIRE CONTINUE ===\n{continuity_ctx}\n\n"
                f"=== DIGEST TA 15m ===\n{json.dumps(digest, ensure_ascii=False)}\n\n"
                f"=== PANORAMA ===\n{json.dumps(pano_compact, ensure_ascii=False)}\n\n"
                f"=== PÉRIODE : {min_wakeup}s à {base_interval}s ===\n"
                "Produis ta décision au format JSON compact (1 phrase <= 150 car. par champ texte) :\n"
                "{\n"
                '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
                '  "panorama_summary": "1 phrase <= 140 car. sur le flux L2 et macro",\n'
                '  "ta_confluence_notes": "1 phrase <= 160 car. sur Ichimoku/Fib/RSI SOL & BTC",\n'
                '  "hypothesis": "1 phrase <= 150 car. sur la thèse directionnelle",\n'
                '  "invalidation_condition": "1 phrase <= 120 car. avec prix d\'invalidation",\n'
                '  "asset_rules": {\n'
                '    "SOL-USDT": {"bias": "LONG_BIAS"|"SHORT_BIAS"|"NEUTRAL", "entry_obi_threshold": 0.08, "max_rsi_long": 68.0, "take_profit_bps": 45.0, "stop_loss_bps": 28.0}\n'
                "  },\n"
                f'  "next_wakeup_sec": entier entre {min_wakeup} et {base_interval},\n'
                '  "wakeup_reason": "1 phrase <= 80 car."\n'
                "}"
            )
            return sys_prompt, user_prompt

        sol_ta = ta_snapshots.get("SOL/USDT", {})
        eth_ta = ta_snapshots.get("ETH/USDT", {})
        btc_ta = ta_snapshots.get("BTC/USDT", {})

        sys_prompt = (
            "Tu es le Stratège Quantitatif Senior (CIO & Chartiste Pro) de Robotrader v2.\n"
            "Tu analyses le Panorama Macro/Social et les indicateurs techniques précis "
            "(Ichimoku Kinko Hyo, Retracements de Fibonacci 0.618 Golden Pocket, RSI 14, ATR/Bollinger, OBI L2).\n"
            "Tu maintiens une continuité logique stricte avec tes thèses précédentes stockées dans le Strategy Palace.\n"
            "Tu déclines ta stratégie en règles mécaniques exécutées en <50µs par les robots Rust, "
            "et tu décides de ton prochain réveil (`next_wakeup_sec`).\n"
            "Réponds UNIQUEMENT avec un objet JSON valide (sans texte autour)."
        )

        user_prompt = (
            f"=== MODE COGNITIF : {thinking_depth} (Budget restant: ${rem_usd:.4f}) ===\n"
            f"=== MÉMOIRE CONTINUE (STRATEGY PALACE) ===\n{continuity_ctx}\n\n"
            f"=== AUTO-OBSERVATION : VOS DERNIERS TRANSCRIPTS BRUTS ===\n{transcript_palace.format_recent_transcripts(limit=2)}\n\n"
            f"=== ANALYSE TECHNIQUE 15m EN DIRECT ===\n"
            f"- SOL/USDT : {json.dumps(sol_ta, ensure_ascii=False)}\n"
            f"- ETH/USDT : {json.dumps(eth_ta, ensure_ascii=False)}\n"
            f"- BTC/USDT : {json.dumps(btc_ta, ensure_ascii=False)}\n\n"
            f"=== PANORAMA SOCIAL & ON-CHAIN ===\n{json.dumps(panorama, ensure_ascii=False)}\n\n"
            f"=== PÉRIODE DE BASE CONFIGURÉE : {base_interval}s ( Plancher autorisé par CostGuard: {min_wakeup}s ) ===\n"
            "Produis ta décision stratégique au format JSON strict suivant :\n"
            "{\n"
            '  "thesis_continuity": "CONFIRMED" | "REFINED" | "INVALIDATED",\n'
            '  "panorama_summary": "Synthèse pro (2 phrases en français) du contexte macro/social et flux L2",\n'
            '  "ta_confluence_notes": "Analyse précise Ichimoku (Kumo/Tenkan/Kijun) + Fibonacci (0.618) + RSI(14) sur SOL/BTC",\n'
            '  "hypothesis": "Intuition et thèse directionnelle actuelle",\n'
            '  "invalidation_condition": "Condition et prix précis invalidant cette thèse",\n'
            '  "asset_rules": {\n'
            '    "SOL-USDT": {"bias": "LONG_BIAS"|"SHORT_BIAS"|"NEUTRAL", "entry_obi_threshold": 0.08, "max_rsi_long": 68.0, "take_profit_bps": 45.0, "stop_loss_bps": 28.0}\n'
            "  },\n"
            f'  "next_wakeup_sec": entier entre {min_wakeup} et {base_interval},\n'
            '  "wakeup_reason": "Justification précise du délai avant prochain réveil (ex: test imminent du Fib 0.618 ou de la Kijun-sen)"\n'
            "}"
        )
        return sys_prompt, user_prompt

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
                            "agent": "Orchestrator/CognitiveLoop",
                            "model": used_model,
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                        }
                    )
                transcript_palace.add_entry(
                    record_llm_call(
                        agent="Orchestrator/CognitiveLoop",
                        kind="reflection",
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
                        agent="Orchestrator/CognitiveLoop",
                        kind="reflection",
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

            if not parsed:
                early_wakeup = max(min_wakeup, min(base_interval, 45 if fib_dist_bps < 30.0 else base_interval))
                parsed = {
                    "thesis_continuity": "CONFIRMED" if self.store.palace.drawers else "INITIAL",
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
            drawer = PalaceDrawer(
                drawer_id=f"drw_{now_ms}",
                timestamp_ms=now_ms,
                wing="strategy_ledger",
                room="active_theses",
                model_used=used_model,
                thinking_depth=thinking_depth,
                thesis_continuity=str(parsed.get("thesis_continuity", "CONFIRMED")),
                global_regime=current_policy.global_regime,
                panorama_summary=str(parsed.get("panorama_summary", "")),
                ta_confluence_notes=str(parsed.get("ta_confluence_notes", "")),
                hypothesis=str(parsed.get("hypothesis", "")),
                invalidation_condition=str(parsed.get("invalidation_condition", "")),
                compiled_rules_summary=compiled_summary,
                next_wakeup_sec=effective_wakeup_sec,
                wakeup_reason=wakeup_reason,
                tokens_used=p_tok + c_tok,
                cost_usd=call_cost,
            )
            self.store.palace.add_drawer(drawer)

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
                    "`pod_solana_alpha`, `pod_sniper`) sont désactivés et en mode lockdown."
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

pub mod vault;

use robotrader_common::{
    fee_bps_for, spread_bps_for, ApprovedOrder, OnChainTokenSafety, OrderIntent, PolicyEnvelope,
    PortfolioState,
};
use serde::{Deserialize, Serialize};
use thiserror::Error;
pub use vault::{
    SeedInput, SimulatedVault, VaultBootstrap, VaultInitError, VaultModeInput, ZeroizingBytes,
};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Error)]
pub enum RiskRejection {
    #[error("Kill-switch is active: {reason}")]
    KillSwitchActive { reason: String },

    #[error("Daily drawdown {current_pct:.2}% exceeded hard limit {limit_pct:.2}%")]
    DailyDrawdownExceeded { current_pct: f64, limit_pct: f64 },

    #[error("Pod {pod_id} is disabled in active PolicyEnvelope ({envelope_id})")]
    PodDisabled { pod_id: String, envelope_id: String },

    #[error("Expected edge {edge_bps:.1} bps is below minimum threshold {min_bps:.1} bps")]
    InsufficientEdge { edge_bps: f64, min_bps: f64 },

    #[error("Requested slippage {requested_bps} bps exceeds hard ceiling {max_bps} bps")]
    ExcessiveSlippage { requested_bps: u32, max_bps: u32 },

    #[error("On-chain token anti-rug security check failed: {reason}")]
    OnChainRugCheckFailed { reason: String },

    #[error("Computed Kelly/volatility size is non-positive")]
    ZeroPositionSize,

    #[error("OpenRouter auto-refill rejected: {reason}")]
    InferenceRefillRejected { reason: String },

    #[error("Simulated vault signing rejected: {reason}")]
    VaultSigningRejected { reason: String },
}

/// Hard risk limits enforced by [`HardRiskGate::validate`].
///
/// `min_edge_buffer_bps` is the only execution-cost knob: the gate derives the
/// rest of the hurdle from the intent's venue, order type, and declared
/// `max_slippage_bps`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskLimits {
    pub max_daily_drawdown_pct: f64,
    pub max_single_position_pct: f64,
    pub max_leverage_ceiling: f64,
    pub kelly_fraction: f64,
    pub target_annual_volatility_pct: f64,
    /// Minimum margin, in basis points, by which `expected_edge_bps` must
    /// exceed estimated execution cost. The effective value is sanitized to
    /// `0.0` when the configured value is negative or non-finite.
    pub min_edge_buffer_bps: f64,
    pub max_slippage_ceiling_bps: u32,
    #[serde(alias = "min_solana_lp_locked_pct")]
    pub min_onchain_lp_locked_pct: f64,
    #[serde(alias = "max_solana_top10_holder_pct")]
    pub max_onchain_top10_holder_pct: f64,
}

impl Default for RiskLimits {
    fn default() -> Self {
        Self {
            max_daily_drawdown_pct: 3.0,
            max_single_position_pct: 0.15, // Max 15% of equity per single trade
            max_leverage_ceiling: 3.0,
            kelly_fraction: 0.25,          // Quarter-Kelly for safety
            target_annual_volatility_pct: 25.0,
            min_edge_buffer_bps: 2.0,
            max_slippage_ceiling_bps: 150,
            min_onchain_lp_locked_pct: 80.0,
            max_onchain_top10_holder_pct: 35.0,
        }
    }
}

pub struct HardRiskGate {
    pub limits: RiskLimits,
    pub kill_switch_active: bool,
    pub kill_switch_reason: Option<String>,
}

impl HardRiskGate {
    pub fn new(limits: RiskLimits) -> Self {
        Self {
            limits,
            kill_switch_active: false,
            kill_switch_reason: None,
        }
    }

    pub fn trigger_kill_switch(&mut self, reason: impl Into<String>) {
        self.kill_switch_active = true;
        self.kill_switch_reason = Some(reason.into());
    }

    pub fn reset_kill_switch(&mut self) {
        self.kill_switch_active = false;
        self.kill_switch_reason = None;
    }

    /// Validates a bounded OpenRouter credit auto-refill initiated by the Master Orchestrator.
    pub fn validate_inference_refill(
        &self,
        requested_usd: f64,
        current_balance_usd: f64,
        low_watermark_usd: f64,
        epoch_refilled_usd: f64,
        max_epoch_refill_usd: f64,
    ) -> Result<f64, RiskRejection> {
        if self.kill_switch_active {
            return Err(RiskRejection::KillSwitchActive {
                reason: self
                    .kill_switch_reason
                    .clone()
                    .unwrap_or_else(|| "Kill-switch active".to_string()),
            });
        }
        if requested_usd <= 0.0 || requested_usd > 25.0 {
            return Err(RiskRejection::InferenceRefillRejected {
                reason: format!("Single refill ${requested_usd:.2} outside (0, $25.00] bounds"),
            });
        }
        if current_balance_usd > low_watermark_usd {
            return Err(RiskRejection::InferenceRefillRejected {
                reason: format!(
                    "Current balance ${current_balance_usd:.2} is above low watermark ${low_watermark_usd:.2}"
                ),
            });
        }
        if epoch_refilled_usd + requested_usd > max_epoch_refill_usd {
            return Err(RiskRejection::InferenceRefillRejected {
                reason: format!(
                    "Epoch refill cap exceeded: ${:.2} + ${:.2} > ${:.2}",
                    epoch_refilled_usd, requested_usd, max_epoch_refill_usd
                ),
            });
        }
        Ok(requested_usd)
    }

    pub fn validate_token_safety(&self, safety: &OnChainTokenSafety) -> Result<(), RiskRejection> {
        if !safety.supply_mint_immutable {
            return Err(RiskRejection::OnChainRugCheckFailed {
                reason: "Token supply / mint authority is still mutable".to_string(),
            });
        }
        if !safety.transfer_freeze_disabled {
            return Err(RiskRejection::OnChainRugCheckFailed {
                reason: "Transfer freeze / blacklist authority is still active".to_string(),
            });
        }
        if !safety.no_honeypot_or_transfer_tax {
            return Err(RiskRejection::OnChainRugCheckFailed {
                reason: "Honeypot or transfer tax detected on token contract".to_string(),
            });
        }
        if safety.lp_locked_pct < self.limits.min_onchain_lp_locked_pct {
            return Err(RiskRejection::OnChainRugCheckFailed {
                reason: format!(
                    "LP locked {:.1}% < {:.1}% minimum",
                    safety.lp_locked_pct, self.limits.min_onchain_lp_locked_pct
                ),
            });
        }
        if safety.top10_holder_pct > self.limits.max_onchain_top10_holder_pct {
            return Err(RiskRejection::OnChainRugCheckFailed {
                reason: format!(
                    "Top-10 holders own {:.1}% > {:.1}% maximum",
                    safety.top10_holder_pct, self.limits.max_onchain_top10_holder_pct
                ),
            });
        }
        if !safety.tx_simulation_success {
            return Err(RiskRejection::OnChainRugCheckFailed {
                reason: "RPC pre-flight transaction simulation reverted".to_string(),
            });
        }
        Ok(())
    }

    /// Computes Volatility-Targeted Fractional Kelly notional in USD.
    pub fn compute_kelly_notional(
        &self,
        intent: &OrderIntent,
        equity_usd: f64,
        pod_weight: f64,
        clamped_leverage: f64,
    ) -> f64 {
        let p = intent.win_probability.clamp(0.01, 0.99);
        let q = 1.0 - p;
        let b = intent.reward_risk_ratio.max(0.1);

        // Classic Kelly f* = p - q / b
        let raw_kelly = p - (q / b);
        if raw_kelly <= 0.0 {
            return 0.0;
        }

        let fractional_kelly = raw_kelly * self.limits.kelly_fraction;

        // Volatility scalar: inverse scaling against asset daily volatility
        let asset_vol = intent.asset_volatility_pct.max(0.5);
        let vol_scalar = (2.0 / asset_vol).clamp(0.25, 1.5);

        let pod_capital = equity_usd * pod_weight.clamp(0.0, 1.0);
        let desired_notional = pod_capital * fractional_kelly * vol_scalar * clamped_leverage;

        let hard_cap_notional =
            equity_usd * self.limits.max_single_position_pct * clamped_leverage;

        desired_notional.min(hard_cap_notional)
    }

    /// Synchronous pre-trade firewall.
    ///
    /// Gates run in this order: kill switch, daily drawdown circuit breaker,
    /// effective-envelope resolution and pod enablement, slippage ceiling,
    /// on-chain token safety when present, per-intent execution-cost hurdle,
    /// leverage clamp, then fractional-Kelly sizing and zero-position
    /// rejection. The hurdle is
    /// `2 x fee + spread + max_slippage_bps + effective_buffer_bps` and is
    /// computed from the intent alone; no portfolio, chain, or sibling-leaf
    /// state is read. See `README.md` for the measured hot-path budget.
    pub fn validate(
        &mut self,
        intent: &OrderIntent,
        portfolio: &PortfolioState,
        raw_envelope: &PolicyEnvelope,
        now_ms: u64,
    ) -> Result<ApprovedOrder, RiskRejection> {
        if self.kill_switch_active {
            return Err(RiskRejection::KillSwitchActive {
                reason: self
                    .kill_switch_reason
                    .clone()
                    .unwrap_or_else(|| "Manual operator trigger".to_string()),
            });
        }

        // 1. Check 24h Drawdown Circuit Breaker
        let dd_pct = portfolio.daily_drawdown_pct();
        if dd_pct >= self.limits.max_daily_drawdown_pct {
            self.trigger_kill_switch(format!(
                "Auto circuit-breaker: daily drawdown {:.2}% >= {:.2}%",
                dd_pct, self.limits.max_daily_drawdown_pct
            ));
            return Err(RiskRejection::DailyDrawdownExceeded {
                current_pct: dd_pct,
                limit_pct: self.limits.max_daily_drawdown_pct,
            });
        }

        // 2. Resolve effective PolicyEnvelope (enforces TTL fallback automatically)
        let envelope = raw_envelope.effective(now_ms);
        let pod_key = intent.pod_id.as_str();
        let pod_alloc = envelope
            .pod_allocations
            .get(pod_key)
            .filter(|a| a.enabled && a.capital_weight > 0.0)
            .ok_or_else(|| RiskRejection::PodDisabled {
                pod_id: pod_key.to_string(),
                envelope_id: envelope.envelope_id.clone(),
            })?;

        // 3. Validate slippage bounds before economic gates: a safety rejection
        //    must keep its own variant instead of becoming `InsufficientEdge`.
        let effective_slippage_cap = pod_alloc
            .max_slippage_bps
            .unwrap_or(self.limits.max_slippage_ceiling_bps)
            .min(self.limits.max_slippage_ceiling_bps);

        if intent.max_slippage_bps > effective_slippage_cap {
            return Err(RiskRejection::ExcessiveSlippage {
                requested_bps: intent.max_slippage_bps,
                max_bps: effective_slippage_cap,
            });
        }

        // 4. On-chain token anti-rug gate (mandatory if safety payload is present)
        if let Some(ref safety) = intent.token_safety {
            self.validate_token_safety(safety)?;
        }

        // 5. Validate expected alpha edge against the per-intent execution-cost
        //    hurdle: round-trip fee + spread + declared impact + buffer.
        //
        //    The priority tip is computed once here and reused unchanged in the
        //    `ApprovedOrder`. `!(edge > hurdle)` is the strict boundary: it also
        //    rejects a `NaN` edge. A `+inf` edge is strictly above every finite
        //    hurdle and is therefore approved, matching the spec's `>` rule.
        let mev_priority_tip_bps = ((intent.expected_edge_bps * 0.10) as u32).clamp(2, 25);
        let round_trip_fee_bps = fee_bps_for(intent.venue, intent.order_type) * 2.0;
        let spread_bps = spread_bps_for(intent.order_type, mev_priority_tip_bps);
        let impact_bps = intent.max_slippage_bps as f64;
        let effective_buffer_bps = if self.limits.min_edge_buffer_bps.is_finite() {
            self.limits.min_edge_buffer_bps.max(0.0)
        } else {
            0.0
        };
        let hurdle_bps = round_trip_fee_bps + spread_bps + impact_bps + effective_buffer_bps;

        if !(intent.expected_edge_bps > hurdle_bps) {
            return Err(RiskRejection::InsufficientEdge {
                edge_bps: intent.expected_edge_bps,
                min_bps: hurdle_bps,
            });
        }

        // 6. Clamp leverage against both AI AssetOverride and Hard Ceiling
        let ai_leverage_cap = envelope
            .asset_overrides
            .get(&intent.symbol)
            .map(|o| o.max_leverage)
            .unwrap_or(self.limits.max_leverage_ceiling);

        let clamped_leverage = intent
            .requested_leverage
            .min(ai_leverage_cap)
            .min(self.limits.max_leverage_ceiling)
            .max(1.0);

        // 7. Compute position size via Fractional Kelly & Volatility Targeting
        let approved_notional_usd = self.compute_kelly_notional(
            intent,
            portfolio.current_equity_usd,
            pod_alloc.capital_weight,
            clamped_leverage,
        );

        if approved_notional_usd <= 10.0 || intent.reference_price <= 0.0 {
            return Err(RiskRejection::ZeroPositionSize);
        }

        let approved_quantity = approved_notional_usd / intent.reference_price;

        Ok(ApprovedOrder {
            intent: intent.clone(),
            approved_notional_usd,
            approved_quantity,
            clamped_leverage,
            mev_priority_tip_bps,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use robotrader_common::{OrderType, PodId, Side, Venue};
    use robotrader_exec_router::{ExecutionMode, SmartExecutionRouter};

    const ALL_VENUES: [Venue; 5] = [
        Venue::BinanceSpot,
        Venue::BinancePerp,
        Venue::HyperliquidPerp,
        Venue::OnchainDexAggregator,
        Venue::OnchainAtomicPool,
    ];
    const ALL_ORDER_TYPES: [OrderType; 4] = [
        OrderType::PostOnlyMaker,
        OrderType::Limit,
        OrderType::Market,
        OrderType::MevBundleAtomic,
    ];

    fn sample_intent() -> OrderIntent {
        OrderIntent {
            pod_id: PodId::PodCarry,
            symbol: "SOL-USDT".to_string(),
            venue: Venue::BinancePerp,
            side: Side::Sell,
            order_type: OrderType::PostOnlyMaker,
            reference_price: 150.0,
            win_probability: 0.68,
            reward_risk_ratio: 2.2,
            asset_volatility_pct: 2.0,
            expected_edge_bps: 35.0,
            max_slippage_bps: 15,
            requested_leverage: 10.0, // Intentionally high to test clamping
            stop_loss_pct: 1.2,
            take_profit_pct: 2.6,
            token_safety: None,
            rationale: "Funding APR 28% carry capture".to_string(),
        }
    }

    #[test]
    fn test_leverage_clamping_and_approval() {
        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);
        let env = PolicyEnvelope::safe_baseline(1_000_000);

        let approved = gate
            .validate(&sample_intent(), &portfolio, &env, 1_000_500)
            .expect("Order should be approved");

        // Requested 10x must be clamped to hard ceiling 3.0x
        assert_eq!(approved.clamped_leverage, 3.0);
        // Max single position cap = 15% * 10,000 * 3.0 = $4,500
        assert!(approved.approved_notional_usd <= 4_500.0);
        assert!(approved.approved_notional_usd > 100.0);
    }

    #[test]
    fn test_drawdown_circuit_breaker_trips_automatically() {
        let mut gate = HardRiskGate::new(RiskLimits::default());
        let mut portfolio = PortfolioState::new(10_000.0);
        portfolio.apply_pnl(-350.0); // -3.5% daily drawdown (> 3.0% limit)
        let env = PolicyEnvelope::safe_baseline(1_000_000);

        let res = gate.validate(&sample_intent(), &portfolio, &env, 1_000_500);
        assert!(matches!(
            res,
            Err(RiskRejection::DailyDrawdownExceeded { .. })
        ));
        assert!(gate.kill_switch_active);
    }

    #[test]
    fn test_onchain_anti_rug_rejects_mutable_supply_authority() {
        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);
        let mut env = PolicyEnvelope::safe_baseline(1_000_000);
        env.pod_allocations
            .get_mut("pod_onchain_alpha")
            .unwrap()
            .enabled = true;
        env.pod_allocations
            .get_mut("pod_onchain_alpha")
            .unwrap()
            .capital_weight = 0.20;

        let mut intent = sample_intent();
        intent.pod_id = PodId::PodOnchainAlpha;
        intent.token_safety = Some(OnChainTokenSafety {
            supply_mint_immutable: false, // RUG RISK!
            transfer_freeze_disabled: true,
            no_honeypot_or_transfer_tax: true,
            lp_locked_pct: 95.0,
            top10_holder_pct: 18.0,
            tx_simulation_success: true,
        });

        let res = gate.validate(&intent, &portfolio, &env, 1_000_500);
        assert!(matches!(
            res,
            Err(RiskRejection::OnChainRugCheckFailed { .. })
        ));
    }

    #[test]
    fn test_profit_gated_inference_refill_validation() {
        let gate = HardRiskGate::new(RiskLimits::default());
        // Valid refill below low watermark and within epoch cap
        let ok = gate.validate_inference_refill(10.0, 1.20, 2.00, 5.0, 25.0);
        assert_eq!(ok, Ok(10.0));

        // Rejected when balance is still above low watermark
        let above = gate.validate_inference_refill(10.0, 4.50, 2.00, 5.0, 25.0);
        assert!(matches!(
            above,
            Err(RiskRejection::InferenceRefillRejected { .. })
        ));

        // Rejected when epoch cap would be exceeded
        let cap_hit = gate.validate_inference_refill(10.0, 1.20, 2.00, 20.0, 25.0);
        assert!(matches!(
            cap_hit,
            Err(RiskRejection::InferenceRefillRejected { .. })
        ));
    }

    fn enable_pod(envelope: &mut PolicyEnvelope, pod: PodId, weight: f64, cap_bps: u32) {
        let alloc = envelope
            .pod_allocations
            .get_mut(pod.as_str())
            .expect("safe baseline declares every pod");
        alloc.enabled = true;
        alloc.capital_weight = weight;
        alloc.max_slippage_bps = Some(cap_bps);
    }

    fn intent_for(
        pod_id: PodId,
        venue: Venue,
        order_type: OrderType,
        expected_edge_bps: f64,
        max_slippage_bps: u32,
    ) -> OrderIntent {
        OrderIntent {
            pod_id,
            symbol: "SOL-USDT".to_string(),
            venue,
            side: Side::Buy,
            order_type,
            reference_price: 150.0,
            win_probability: 0.68,
            reward_risk_ratio: 2.2,
            asset_volatility_pct: 2.0,
            expected_edge_bps,
            max_slippage_bps,
            requested_leverage: 1.0,
            stop_loss_pct: 1.2,
            take_profit_pct: 2.6,
            token_safety: None,
            rationale: "hurdle fixture".to_string(),
        }
    }

    fn rejection_min_bps(result: Result<ApprovedOrder, RiskRejection>) -> f64 {
        match result {
            Err(RiskRejection::InsufficientEdge { min_bps, .. }) => min_bps,
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }
    }

    #[test]
    fn test_cost_terms_match_the_execution_router_for_every_pair() {
        let router = SmartExecutionRouter::new(ExecutionMode::Backtest);
        for venue in ALL_VENUES {
            for order_type in ALL_ORDER_TYPES {
                assert_eq!(
                    fee_bps_for(venue, order_type),
                    router.fee_bps_for(venue, order_type),
                    "fee divergence for {venue:?}/{order_type:?}"
                );

                let approved = ApprovedOrder {
                    intent: intent_for(PodId::PodCarry, venue, order_type, 12.0, 2),
                    approved_notional_usd: 1_000.0,
                    approved_quantity: 1_000.0 / 150.0,
                    clamped_leverage: 1.0,
                    mev_priority_tip_bps: 10,
                };
                assert_eq!(
                    spread_bps_for(order_type, 10),
                    router.slippage_bps_for(&approved),
                    "spread divergence for {venue:?}/{order_type:?}"
                );
            }
        }
    }

    #[test]
    fn test_hurdle_differentiates_venue_and_order_type() {
        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);
        let envelope = PolicyEnvelope::safe_baseline(1_000_000);
        let now_ms = 1_000_500;

        let mut sniper_envelope = PolicyEnvelope::safe_baseline(1_000_000);
        enable_pod(&mut sniper_envelope, PodId::PodSniper, 0.10, 150);
        let onchain = intent_for(
            PodId::PodSniper,
            Venue::OnchainAtomicPool,
            OrderType::MevBundleAtomic,
            12.0,
            150,
        );
        match gate.validate(&onchain, &portfolio, &sniper_envelope, now_ms) {
            Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                assert_eq!(edge_bps, 12.0);
                assert_eq!(min_bps, 177.2);
            }
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }

        let maker = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::PostOnlyMaker,
            12.0,
            2,
        );
        assert!(gate
            .validate(&maker, &portfolio, &envelope, now_ms)
            .is_ok());

        let taker = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::Market,
            12.0,
            2,
        );
        match gate.validate(&taker, &portfolio, &envelope, now_ms) {
            Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                assert_eq!(edge_bps, 12.0);
                assert_eq!(min_bps, 22.0);
            }
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }

        let hyperliquid_maker = intent_for(
            PodId::PodCarry,
            Venue::HyperliquidPerp,
            OrderType::PostOnlyMaker,
            7.0,
            2,
        );
        assert!(gate
            .validate(&hyperliquid_maker, &portfolio, &envelope, now_ms)
            .is_ok());

        let binance_maker = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::PostOnlyMaker,
            7.0,
            2,
        );
        match gate.validate(&binance_maker, &portfolio, &envelope, now_ms) {
            Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                assert_eq!(edge_bps, 7.0);
                assert_eq!(min_bps, 8.1);
            }
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }
    }

    #[test]
    fn test_buffer_default_shift_and_sanitization() {
        assert_eq!(RiskLimits::default().min_edge_buffer_bps, 2.0);

        let portfolio = PortfolioState::new(10_000.0);
        let envelope = PolicyEnvelope::safe_baseline(1_000_000);
        let now_ms = 1_000_500;
        let failing = intent_for(
            PodId::PodCarry,
            Venue::HyperliquidPerp,
            OrderType::PostOnlyMaker,
            1.0,
            2,
        );

        let mut default_gate = HardRiskGate::new(RiskLimits::default());
        let default_min = rejection_min_bps(default_gate.validate(
            &failing,
            &portfolio,
            &envelope,
            now_ms,
        ));
        assert_eq!(default_min, 6.5);

        let mut shifted_limits = RiskLimits::default();
        shifted_limits.min_edge_buffer_bps = 5.0;
        let mut shifted_gate = HardRiskGate::new(shifted_limits);
        let shifted_min = rejection_min_bps(shifted_gate.validate(
            &failing,
            &portfolio,
            &envelope,
            now_ms,
        ));
        assert_eq!(shifted_min, 9.5);
        assert_eq!(shifted_min - default_min, 3.0);

        let at_cost = intent_for(
            PodId::PodCarry,
            Venue::HyperliquidPerp,
            OrderType::PostOnlyMaker,
            4.5,
            2,
        );
        let mut zero_limits = RiskLimits::default();
        zero_limits.min_edge_buffer_bps = 0.0;
        let mut zero_gate = HardRiskGate::new(zero_limits);
        let zero_min =
            rejection_min_bps(zero_gate.validate(&at_cost, &portfolio, &envelope, now_ms));
        assert_eq!(zero_min, 4.5);

        for buffer in [-5.0, f64::NAN] {
            let mut limits = RiskLimits::default();
            limits.min_edge_buffer_bps = buffer;
            let mut gate = HardRiskGate::new(limits);
            let sanitized_min =
                rejection_min_bps(gate.validate(&at_cost, &portfolio, &envelope, now_ms));
            assert_eq!(sanitized_min, 4.5, "buffer {buffer} must sanitize to 0.0");
        }
    }

    #[test]
    fn test_hurdle_boundary_is_strict() {
        let portfolio = PortfolioState::new(10_000.0);
        let envelope = PolicyEnvelope::safe_baseline(1_000_000);
        let now_ms = 1_000_500;

        for edge_bps in [4.4, 4.5, 6.5] {
            let mut gate = HardRiskGate::new(RiskLimits::default());
            let intent = intent_for(
                PodId::PodCarry,
                Venue::HyperliquidPerp,
                OrderType::PostOnlyMaker,
                edge_bps,
                2,
            );
            assert!(
                matches!(
                    gate.validate(&intent, &portfolio, &envelope, now_ms),
                    Err(RiskRejection::InsufficientEdge { .. })
                ),
                "edge {edge_bps} must be rejected at or below the hurdle"
            );
        }

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let above = intent_for(
            PodId::PodCarry,
            Venue::HyperliquidPerp,
            OrderType::PostOnlyMaker,
            6.6,
            2,
        );
        assert!(gate.validate(&above, &portfolio, &envelope, now_ms).is_ok());

        let taker = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::Market,
            12.0,
            2,
        );
        match gate.validate(&taker, &portfolio, &envelope, now_ms) {
            Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                assert_eq!(edge_bps, 12.0);
                assert_eq!(min_bps, 22.0);
            }
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }
    }

    #[test]
    fn test_safety_gates_precede_the_hurdle() {
        let portfolio = PortfolioState::new(10_000.0);
        let now_ms = 1_000_500;
        let mut envelope = PolicyEnvelope::safe_baseline(1_000_000);
        enable_pod(&mut envelope, PodId::PodOnchainAlpha, 0.15, 80);

        let mut scam = intent_for(
            PodId::PodOnchainAlpha,
            Venue::OnchainDexAggregator,
            OrderType::MevBundleAtomic,
            81.0,
            65,
        );
        scam.symbol = "SCAM-SOL".to_string();
        scam.token_safety = Some(OnChainTokenSafety {
            supply_mint_immutable: false,
            transfer_freeze_disabled: false,
            no_honeypot_or_transfer_tax: false,
            lp_locked_pct: 10.0,
            top10_holder_pct: 82.0,
            tx_simulation_success: true,
        });

        let mut gate = HardRiskGate::new(RiskLimits::default());
        match gate.validate(&scam, &portfolio, &envelope, now_ms) {
            Err(RiskRejection::OnChainRugCheckFailed { .. }) => {}
            other => panic!("expected OnChainRugCheckFailed, got {other:?}"),
        }

        let mut without_safety = scam.clone();
        without_safety.token_safety = None;
        match gate.validate(&without_safety, &portfolio, &envelope, now_ms) {
            Err(RiskRejection::InsufficientEdge { edge_bps, min_bps }) => {
                assert_eq!(edge_bps, 81.0);
                assert_eq!(min_bps, 87.8);
            }
            other => panic!("expected InsufficientEdge, got {other:?}"),
        }

        let carry_envelope = PolicyEnvelope::safe_baseline(1_000_000);
        let slippage = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::PostOnlyMaker,
            1.0,
            30,
        );
        match gate.validate(&slippage, &portfolio, &carry_envelope, now_ms) {
            Err(RiskRejection::ExcessiveSlippage {
                requested_bps,
                max_bps,
            }) => {
                assert_eq!(requested_bps, 30);
                assert_eq!(max_bps, 25);
            }
            other => panic!("expected ExcessiveSlippage, got {other:?}"),
        }
    }

    #[test]
    fn test_non_regression_gates_keep_their_variants() {
        let portfolio = PortfolioState::new(10_000.0);
        let envelope = PolicyEnvelope::safe_baseline(1_000_000);
        let now_ms = 1_000_500;
        let hurdle_failing = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::Market,
            1.0,
            2,
        );

        let mut gate = HardRiskGate::new(RiskLimits::default());
        gate.trigger_kill_switch("operator halt");
        assert!(matches!(
            gate.validate(&hurdle_failing, &portfolio, &envelope, now_ms),
            Err(RiskRejection::KillSwitchActive { .. })
        ));

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let mut drawdown = PortfolioState::new(10_000.0);
        drawdown.apply_pnl(-350.0);
        assert!(matches!(
            gate.validate(&hurdle_failing, &drawdown, &envelope, now_ms),
            Err(RiskRejection::DailyDrawdownExceeded { .. })
        ));
        assert!(gate.kill_switch_active);

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let sniper = intent_for(
            PodId::PodSniper,
            Venue::OnchainAtomicPool,
            OrderType::MevBundleAtomic,
            200.0,
            100,
        );
        assert!(matches!(
            gate.validate(&sniper, &portfolio, &envelope, now_ms),
            Err(RiskRejection::PodDisabled { .. })
        ));

        let mut expired = PolicyEnvelope::safe_baseline(1_000_000);
        expired.ttl_seconds = 900;
        let mut gate = HardRiskGate::new(RiskLimits::default());
        match gate.validate(&sniper, &portfolio, &expired, 1_900_001) {
            Err(RiskRejection::PodDisabled { envelope_id, .. }) => {
                assert_eq!(envelope_id, "safe_baseline_fallback");
            }
            other => panic!("expected PodDisabled, got {other:?}"),
        }

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let mut passing = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::PostOnlyMaker,
            12.0,
            2,
        );
        passing.requested_leverage = 10.0;
        let approved = gate
            .validate(&passing, &portfolio, &envelope, now_ms)
            .expect("a hurdle-passing intent must be approved");
        assert_eq!(approved.clamped_leverage, 3.0);

        let mut gate = HardRiskGate::new(RiskLimits::default());
        let mut zero_kelly = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::PostOnlyMaker,
            12.0,
            2,
        );
        zero_kelly.win_probability = 0.01;
        zero_kelly.reward_risk_ratio = 0.1;
        assert!(matches!(
            gate.validate(&zero_kelly, &portfolio, &envelope, now_ms),
            Err(RiskRejection::ZeroPositionSize)
        ));

        let gate = HardRiskGate::new(RiskLimits::default());
        assert_eq!(
            gate.validate_inference_refill(10.0, 1.20, 2.00, 5.0, 25.0),
            Ok(10.0)
        );
        assert!(matches!(
            gate.validate_inference_refill(10.0, 4.50, 2.00, 5.0, 25.0),
            Err(RiskRejection::InferenceRefillRejected { .. })
        ));
    }

    #[test]
    fn test_nan_edge_fails_closed() {
        let mut gate = HardRiskGate::new(RiskLimits::default());
        let portfolio = PortfolioState::new(10_000.0);
        let envelope = PolicyEnvelope::safe_baseline(1_000_000);
        let intent = intent_for(
            PodId::PodCarry,
            Venue::BinancePerp,
            OrderType::PostOnlyMaker,
            f64::NAN,
            2,
        );
        assert!(matches!(
            gate.validate(&intent, &portfolio, &envelope, 1_000_500),
            Err(RiskRejection::InsufficientEdge { .. })
        ));
    }

    mod simulated_vault_tests {
        use super::*;
        use robotrader_common::{ExecutionMode, SeedSource};
        use std::fs;
        use std::path::PathBuf;
        use std::sync::atomic::{AtomicU64, Ordering};

        static NEXT_TEMP: AtomicU64 = AtomicU64::new(0);

        const OPERATOR_DESTINATION: &str = "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN";

        fn temporary_seed_path(tag: &str) -> PathBuf {
            std::env::temp_dir().join(format!(
                "robotrader-simulated-vault-{}-{}-{tag}.seed",
                std::process::id(),
                NEXT_TEMP.fetch_add(1, Ordering::SeqCst)
            ))
        }

        fn load(
            execution_mode: VaultModeInput,
            secret_file: impl Into<PathBuf>,
            env_seed: SeedInput,
        ) -> Result<SimulatedVault, VaultInitError> {
            SimulatedVault::load(VaultBootstrap {
                execution_mode,
                secret_file: secret_file.into(),
                env_seed,
            })
        }

        fn paper_vault() -> SimulatedVault {
            load(VaultModeInput::Unset, temporary_seed_path("absent"), SeedInput::Unset)
                .expect("default PAPER configuration must construct")
        }

        fn write_seed_file(tag: &str, contents: &str) -> PathBuf {
            let path = temporary_seed_path(tag);
            fs::write(&path, contents).expect("temporary seed file");
            path
        }

        #[test]
        fn test_simulated_vault_manifest_contract() {
            let vault = paper_vault();
            let manifest = vault.export_public_manifest();

            assert_eq!(manifest.vault_mode, "SIMULATED");
            assert!(manifest.simulated);
            assert!(!manifest.python_private_key_access);
            assert_eq!(manifest.whitelist_enforcement, "SIMULATED");
            assert_eq!(manifest.seed_source, SeedSource::DeterministicDevnet);
            assert_eq!(manifest.execution_mode, ExecutionMode::Paper);
            assert!(!manifest.simulation_notice.is_empty());
            assert!(manifest.simulation_notice.contains("not spendable"));
            assert_eq!(manifest.wallets.len(), 26);

            for wallet in &manifest.wallets {
                assert!(wallet.simulated);
                assert!(!wallet.address_is_spendable);
                assert!(!wallet.target_master_derivation_path.is_empty());
                assert!(!wallet.target_leaf_derivation_path.is_empty());
            }

            let sol = vault.derive_wallet_descriptor("leaf-solana").unwrap();
            assert_ne!(sol.master_treasury_address, sol.leaf_hot_address);
            assert_eq!(sol.target_master_derivation_path, "m/44'/501'/0'/0/0");
            assert_eq!(sol.target_leaf_derivation_path, "m/44'/501'/1'/0/0");
            assert_eq!(sol.target_slip44_coin_type, 501);

            let btc = vault.derive_wallet_descriptor("leaf-bitcoin").unwrap();
            assert!(btc.master_treasury_address.starts_with("bc1q"));
            assert_eq!(btc.target_master_derivation_path, "m/84'/0'/0'/0/0");

            let eth = vault.derive_wallet_descriptor("leaf-ethereum").unwrap();
            assert!(eth.master_treasury_address.starts_with("0x"));
            assert_eq!(eth.master_treasury_address.len(), 42);
        }

        #[test]
        fn test_execution_mode_parsing() {
            let absent = temporary_seed_path("mode-absent");
            let env = SeedInput::Value("test-only-not-a-secret".to_string());

            let unset = load(VaultModeInput::Unset, &absent, SeedInput::Unset).unwrap();
            assert_eq!(
                unset.export_public_manifest().execution_mode,
                ExecutionMode::Paper
            );
            assert_eq!(
                unset.export_public_manifest().seed_source,
                SeedSource::DeterministicDevnet
            );

            for (value, expected) in [
                ("BACKTEST", ExecutionMode::Backtest),
                ("PAPER", ExecutionMode::Paper),
                ("SIMULATED", ExecutionMode::Simulated),
                ("LIVE", ExecutionMode::Live),
            ] {
                let vault = load(
                    VaultModeInput::Value(value.to_string()),
                    &absent,
                    env.clone(),
                )
                .unwrap_or_else(|err| panic!("{value} must be accepted: {err}"));
                assert_eq!(vault.export_public_manifest().execution_mode, expected);
            }

            let empty = load(
                VaultModeInput::Value(String::new()),
                &absent,
                SeedInput::Unset,
            )
            .err().expect("expected a vault init error");
            assert_eq!(empty, VaultInitError::EmptyExecutionMode);
            assert!(empty.to_string().contains("ROBOTRADER_EXECUTION_MODE"));
            assert!(empty.to_string().contains("BACKTEST"));

            for value in [" ", "paper", "PAPER ", " Paper", "BOGUS"] {
                let err = load(
                    VaultModeInput::Value(value.to_string()),
                    &absent,
                    SeedInput::Unset,
                )
                .err().expect("expected a vault init error");
                assert_eq!(
                    err,
                    VaultInitError::InvalidExecutionMode(value.to_string()),
                    "{value:?} must fail closed"
                );
                assert!(err.to_string().contains("ROBOTRADER_EXECUTION_MODE"));
                assert!(err.to_string().contains("accepted values are"));
            }

            let non_unicode =
                load(VaultModeInput::NonUnicode, &absent, SeedInput::Unset).err().expect("expected a vault init error");
            assert_eq!(non_unicode, VaultInitError::NonUnicodeExecutionMode);
            assert!(non_unicode.to_string().contains("ROBOTRADER_EXECUTION_MODE"));
        }

        #[test]
        fn test_seed_precedence() {
            let live = VaultModeInput::Value("LIVE".to_string());
            let secret = write_seed_file("precedence-secret", "test-only-not-a-secret\n");
            let empty_secret = write_seed_file("precedence-empty", "   \n");

            let from_secret = load(
                live.clone(),
                &secret,
                SeedInput::Value("environment-seed".to_string()),
            )
            .expect("a readable non-empty secret must win");
            assert_eq!(
                from_secret.export_public_manifest().seed_source,
                SeedSource::SecretFile
            );

            let from_environment = load(
                live.clone(),
                &empty_secret,
                SeedInput::Value("environment-seed".to_string()),
            )
            .expect("an empty secret must fall through to the environment");
            assert_eq!(
                from_environment.export_public_manifest().seed_source,
                SeedSource::Environment
            );

            let missing = load(live.clone(), temporary_seed_path("live-absent"), SeedInput::Unset)
                .err().expect("expected a vault init error");
            assert_eq!(missing, VaultInitError::MissingLiveSeed);

            let live_environment = load(
                live,
                temporary_seed_path("live-absent"),
                SeedInput::Value("environment-seed".to_string()),
            )
            .expect("live mode accepts an environment seed");
            assert_eq!(
                live_environment.export_public_manifest().seed_source,
                SeedSource::Environment
            );

            let deterministic = load(
                VaultModeInput::Unset,
                temporary_seed_path("non-live-absent"),
                SeedInput::Unset,
            )
            .expect("non-live mode uses the deterministic seed");
            assert_eq!(
                deterministic.export_public_manifest().seed_source,
                SeedSource::DeterministicDevnet
            );

            let non_unicode = load(
                VaultModeInput::Unset,
                temporary_seed_path("non-unicode"),
                SeedInput::NonUnicode,
            )
            .err().expect("expected a vault init error");
            assert_eq!(non_unicode, VaultInitError::InvalidEnvironmentSeedEncoding);

            fs::remove_file(secret).ok();
            fs::remove_file(empty_secret).ok();
        }

        #[test]
        fn test_simulated_receipt_contract() {
            let vault = paper_vault();
            let receipt = vault
                .validate_and_sign_transfer(false, "Solana", OPERATOR_DESTINATION, 1500.0, "SOL")
                .expect("the simulated whitelist accepts the placeholder destination");

            assert!(receipt.simulated);
            assert!(!receipt.signature_is_chain_valid);
            assert_eq!(receipt.whitelist_enforcement, "SIMULATED");
            assert!(receipt.destination_whitelisted);
            assert!(receipt.key_zeroized_after_sign);
            assert!(receipt.signature_hex.starts_with("0x"));
            assert!(!receipt.signature_hex.is_empty());
            assert_eq!(receipt.destination_address, OPERATOR_DESTINATION);
            assert_eq!(receipt.amount_usd, 1500.0);
        }

        #[test]
        fn test_rejected_destination_no_receipt() {
            let vault = paper_vault();
            let rejected = vault.validate_and_sign_transfer(
                false,
                "Solana",
                "attacker_drain_wallet_999999999",
                1500.0,
                "SOL",
            );
            assert!(matches!(
                rejected,
                Err(RiskRejection::VaultSigningRejected { .. })
            ));

            let killed = vault.validate_and_sign_transfer(
                true,
                "Solana",
                OPERATOR_DESTINATION,
                1500.0,
                "SOL",
            );
            assert!(matches!(killed, Err(RiskRejection::KillSwitchActive { .. })));
        }

        #[test]
        fn test_key_zeroization_observation() {
            let mut secret = ZeroizingBytes::new([0xAAu8; 32]);
            assert!(!secret.is_zeroized());
            secret.zeroize_now();
            assert!(secret.is_zeroized());
            assert!(secret.as_slice().iter().all(|&b| b == 0));

            let already_zero = ZeroizingBytes::new([0u8; 32]);
            assert!(already_zero.is_zeroized());
        }

    }
}

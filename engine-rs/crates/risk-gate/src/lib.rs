pub mod crypto_vault;
pub mod vault;

use robotrader_common::{
    fee_bps_for, spread_bps_for, ApprovedOrder, OnChainTokenSafety, OrderIntent, PolicyEnvelope,
    PortfolioState,
};
use serde::{Deserialize, Serialize};
use thiserror::Error;
pub use bs58;
pub use crypto_vault::{
    validate_chain_address, verify_checkout_signature, AddressValidationError,
    CryptoVaultBootstrap, CryptographicVault,
};
pub use vault::{
    parse_execution_mode, read_mode_input, read_seed_input, select_vault_mode,
    select_vault_mode_from, sha256, SeedInput, SimulatedVault, VaultBackendKind, VaultBootstrap,
    VaultInitError, VaultModeInput, ZeroizingBytes,
};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct InferenceRefillVerdict {
    pub approved: bool,
    pub status: String,
    pub reason: String,
    pub approved_usd: f64,
}

fn format_signed_usd(value: f64) -> String {
    if value.is_nan() {
        "NaN".to_string()
    } else if value < 0.0 {
        format!("-${:.2}", value.abs())
    } else {
        format!("${:.2}", value)
    }
}

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

    /// Validates an OpenRouter inference credit refill against the 6-step canonical risk gate.
    pub fn validate_inference_refill(
        &self,
        requested_usd: f64,
        realized_trading_pnl_usd: f64,
        current_balance_usd: f64,
        low_watermark_usd: f64,
        epoch_refilled_usd: f64,
        max_epoch_refill_usd: f64,
        force: bool,
    ) -> InferenceRefillVerdict {
        // Step 1: Kill switch
        if self.kill_switch_active {
            return InferenceRefillVerdict {
                approved: false,
                status: "rejected_kill_switch".to_string(),
                reason: self
                    .kill_switch_reason
                    .clone()
                    .unwrap_or_else(|| "Kill switch active; inference credit refills are suspended".to_string()),
                approved_usd: 0.0,
            };
        }

        // Step 2: Realized trading PnL > 0 and finite
        if !realized_trading_pnl_usd.is_finite() || realized_trading_pnl_usd <= 0.0 {
            return InferenceRefillVerdict {
                approved: false,
                status: "rejected_no_realized_profit".to_string(),
                reason: format!(
                    "Realized trading PnL ({}) <= 0; principal treasury protected",
                    format_signed_usd(realized_trading_pnl_usd)
                ),
                approved_usd: 0.0,
            };
        }

        // Step 3: Single refill bounds (0, $25.00] and finite
        if !requested_usd.is_finite() || requested_usd <= 0.0 || requested_usd > 25.0 {
            return InferenceRefillVerdict {
                approved: false,
                status: "rejected".to_string(),
                reason: format!(
                    "Amount ${requested_usd:.2} outside allowed single-refill bounds (0, $25.00]"
                ),
                approved_usd: 0.0,
            };
        }

        // Step 4: 10% profit-share cap
        if requested_usd > (realized_trading_pnl_usd * 0.10) + 1e-6 {
            return InferenceRefillVerdict {
                approved: false,
                status: "rejected_exceeds_profit_share".to_string(),
                reason: format!(
                    "Requested refill ${requested_usd:.2} > 10% of realized PnL ({})",
                    format_signed_usd(realized_trading_pnl_usd)
                ),
                approved_usd: 0.0,
            };
        }

        // Step 5: Low-watermark threshold (honoring force)
        if !force && current_balance_usd > low_watermark_usd {
            return InferenceRefillVerdict {
                approved: false,
                status: "skipped_sufficient_balance".to_string(),
                reason: format!(
                    "Balance ${current_balance_usd:.2} > low watermark ${low_watermark_usd:.2}"
                ),
                approved_usd: 0.0,
            };
        }

        // Step 6: Rolling 24-hour epoch cap
        if epoch_refilled_usd + requested_usd > max_epoch_refill_usd {
            return InferenceRefillVerdict {
                approved: false,
                status: "rejected_epoch_cap".to_string(),
                reason: format!(
                    "Epoch cap reached (${epoch_refilled_usd:.2} + ${requested_usd:.2} > ${max_epoch_refill_usd:.2})"
                ),
                approved_usd: 0.0,
            };
        }

        // Approved
        InferenceRefillVerdict {
            approved: true,
            status: "refilled".to_string(),
            reason: format!("Approved refill of ${requested_usd:.2}"),
            approved_usd: requested_usd,
        }
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
        // Valid refill: requested $4.00, realized PnL $100.00, balance $1.20 <= watermark $2.00, epoch spent $5.00
        let ok = gate.validate_inference_refill(4.0, 100.0, 1.20, 2.00, 5.0, 25.0, false);
        assert_eq!(
            ok,
            InferenceRefillVerdict {
                approved: true,
                status: "refilled".to_string(),
                reason: "Approved refill of $4.00".to_string(),
                approved_usd: 4.0,
            }
        );
    }

    #[test]
    fn test_refill_kill_switch_active_rejects() {
        let mut gate = HardRiskGate::new(RiskLimits::default());
        gate.trigger_kill_switch("emergency halt");
        let verdict = gate.validate_inference_refill(4.0, 100.0, 1.00, 2.00, 0.0, 25.0, false);
        assert!(!verdict.approved);
        assert_eq!(verdict.status, "rejected_kill_switch");
        assert_eq!(verdict.approved_usd, 0.0);
        assert_eq!(verdict.reason, "emergency halt");
    }

    #[test]
    fn test_refill_non_positive_and_non_finite_pnl_rejects() {
        let gate = HardRiskGate::new(RiskLimits::default());
        for pnl in [-5.0, 0.0, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            let verdict = gate.validate_inference_refill(4.0, pnl, 1.00, 2.00, 0.0, 25.0, false);
            assert!(!verdict.approved, "pnl={pnl} must not be approved");
            assert_eq!(
                verdict.status, "rejected_no_realized_profit",
                "pnl={pnl} must reject with rejected_no_realized_profit"
            );
            assert_eq!(verdict.approved_usd, 0.0);
        }
    }

    #[test]
    fn test_refill_out_of_bounds_amount_rejects() {
        let gate = HardRiskGate::new(RiskLimits::default());
        for req in [0.0, -1.0, 25.01, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            let verdict = gate.validate_inference_refill(req, 1000.0, 1.00, 2.00, 0.0, 25.0, false);
            assert!(!verdict.approved, "req={req} must not be approved");
            assert_eq!(
                verdict.status, "rejected",
                "req={req} must reject with status 'rejected'"
            );
            assert_eq!(verdict.approved_usd, 0.0);
        }
    }

    #[test]
    fn test_refill_exceeds_profit_share_rejects() {
        let gate = HardRiskGate::new(RiskLimits::default());
        // requested $10.00 > 10% of $50.00 ($5.00)
        let verdict = gate.validate_inference_refill(10.0, 50.0, 1.00, 2.00, 0.0, 25.0, false);
        assert!(!verdict.approved);
        assert_eq!(verdict.status, "rejected_exceeds_profit_share");
        assert_eq!(verdict.approved_usd, 0.0);
        assert!(verdict.reason.contains("$50.00"));
    }

    #[test]
    fn test_refill_watermark_and_force_override() {
        let gate = HardRiskGate::new(RiskLimits::default());
        // balance $3.00 > watermark $2.00 with force = false -> skip
        let skipped = gate.validate_inference_refill(4.0, 100.0, 3.00, 2.00, 0.0, 25.0, false);
        assert!(!skipped.approved);
        assert_eq!(skipped.status, "skipped_sufficient_balance");
        assert_eq!(skipped.approved_usd, 0.0);

        // balance $3.00 > watermark $2.00 with force = true -> approved
        let forced = gate.validate_inference_refill(4.0, 100.0, 3.00, 2.00, 0.0, 25.0, true);
        assert!(forced.approved);
        assert_eq!(forced.status, "refilled");
        assert_eq!(forced.approved_usd, 4.0);
    }

    #[test]
    fn test_refill_epoch_cap_violation_rejects() {
        let gate = HardRiskGate::new(RiskLimits::default());
        // epoch $23.00 + requested $4.00 > max $25.00
        let verdict = gate.validate_inference_refill(4.0, 100.0, 1.00, 2.00, 23.0, 25.0, false);
        assert!(!verdict.approved);
        assert_eq!(verdict.status, "rejected_epoch_cap");
        assert_eq!(verdict.approved_usd, 0.0);
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
            gate.validate_inference_refill(4.0, 100.0, 1.20, 2.00, 5.0, 25.0, false),
            InferenceRefillVerdict {
                approved: true,
                status: "refilled".to_string(),
                reason: "Approved refill of $4.00".to_string(),
                approved_usd: 4.0,
            }
        );
        let above = gate.validate_inference_refill(4.0, 100.0, 4.50, 2.00, 5.0, 25.0, false);
        assert_eq!(above.status, "skipped_sufficient_balance");
        assert!(!above.approved);
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

            assert_eq!(receipt.vault_mode, "SIMULATED");
            assert!(receipt.simulated);
            assert!(!receipt.signature_is_chain_valid);
            assert!(!receipt.signature_is_cryptographic);
            assert_eq!(receipt.signature_scheme, "SIMULATED_HMAC_SHA256");
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

    mod cryptographic_vault_tests {
        use super::*;
        use crate::vault::sha256;
        use k256::elliptic_curve::sec1::ToEncodedPoint;
        use robotrader_common::{CryptographicCurve, SeedSource};
        use std::ffi::OsString;
        use std::fs;
        use std::path::PathBuf;
        use std::sync::atomic::{AtomicU64, Ordering};

        static NEXT_TEMP_CRYPTO: AtomicU64 = AtomicU64::new(0);

        fn temporary_seed_path(tag: &str) -> PathBuf {
            std::env::temp_dir().join(format!(
                "robotrader-crypto-vault-{}-{}-{tag}.seed",
                std::process::id(),
                NEXT_TEMP_CRYPTO.fetch_add(1, Ordering::SeqCst)
            ))
        }

        fn write_seed_file(tag: &str, contents: &str) -> PathBuf {
            let path = temporary_seed_path(tag);
            fs::write(&path, contents).expect("temporary seed file");
            path
        }

        fn valid_hex_seed() -> String {
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef".to_string()
        }

        fn load_crypto(
            execution_mode: VaultModeInput,
            secret_file: impl Into<PathBuf>,
            env_seed: SeedInput,
            allow_test_seed: bool,
            allowlist_file: Option<PathBuf>,
        ) -> Result<CryptographicVault, VaultInitError> {
            CryptographicVault::load(CryptoVaultBootstrap {
                execution_mode,
                secret_file: secret_file.into(),
                env_seed,
                allow_test_seed,
                allowlist_file,
            })
        }

        fn test_vault() -> CryptographicVault {
            load_crypto(
                VaultModeInput::Unset,
                temporary_seed_path("absent"),
                SeedInput::Unset,
                true,
                None,
            )
            .expect("default test configuration with allow_test_seed=true must construct")
        }

        #[test]
        fn test_crypto_seed_precedence_and_entropy() {
            let live = VaultModeInput::Value("LIVE".to_string());
            let valid_hex = valid_hex_seed();
            let short_hex = "0123456789abcdef".to_string(); // 8 bytes < 32 bytes

            // 1. Secret file with valid seed
            let secret_valid = write_seed_file("crypto-secret-valid", &format!("{valid_hex}\n"));
            let from_secret = load_crypto(
                live.clone(),
                &secret_valid,
                SeedInput::Value("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff".to_string()),
                false,
                None,
            )
            .expect("valid secret file must succeed");
            assert_eq!(
                from_secret.export_public_manifest().seed_source,
                SeedSource::SecretFile
            );

            // 2. Secret file with insufficient entropy (<32 bytes)
            let secret_short = write_seed_file("crypto-secret-short", &format!("{short_hex}\n"));
            let short_err = load_crypto(
                live.clone(),
                &secret_short,
                SeedInput::Unset,
                false,
                None,
            )
            .err()
            .expect("short secret file must fail closed");
            assert_eq!(short_err, VaultInitError::InsufficientEntropy);

            // 3. Empty secret file falls through to environment seed
            let secret_empty = write_seed_file("crypto-secret-empty", "   \n");
            let from_env = load_crypto(
                live.clone(),
                &secret_empty,
                SeedInput::Value(valid_hex.clone()),
                false,
                None,
            )
            .expect("empty secret must fall through to environment seed");
            assert_eq!(
                from_env.export_public_manifest().seed_source,
                SeedSource::Environment
            );

            // 4. Environment seed with insufficient entropy (<32 bytes)
            let env_short_err = load_crypto(
                live.clone(),
                temporary_seed_path("absent"),
                SeedInput::Value(short_hex),
                false,
                None,
            )
            .err()
            .expect("short environment seed must fail closed");
            assert_eq!(env_short_err, VaultInitError::InsufficientEntropy);

            // 5. LIVE mode without any seed fails closed
            let missing_live = load_crypto(
                live,
                temporary_seed_path("absent"),
                SeedInput::Unset,
                false,
                None,
            )
            .err()
            .expect("live mode without seed must fail");
            assert_eq!(missing_live, VaultInitError::MissingLiveSeed);

            // 6. Non-live mode without seed rejects test seed if allow_test_seed is false
            let test_rejected = load_crypto(
                VaultModeInput::Unset,
                temporary_seed_path("absent"),
                SeedInput::Unset,
                false,
                None,
            )
            .err()
            .expect("test seed must be rejected when allow_test_seed is false");
            assert_eq!(test_rejected, VaultInitError::TestSeedNotAllowed);

            // 7. Non-live mode with allow_test_seed succeeds with DeterministicDevnet
            let test_allowed = load_crypto(
                VaultModeInput::Unset,
                temporary_seed_path("absent"),
                SeedInput::Unset,
                true,
                None,
            )
            .expect("test seed must be allowed when allow_test_seed is true");
            assert_eq!(
                test_allowed.export_public_manifest().seed_source,
                SeedSource::DeterministicDevnet
            );

            // 8. Non-unicode env seed fails closed
            let non_unicode = load_crypto(
                VaultModeInput::Unset,
                temporary_seed_path("absent"),
                SeedInput::NonUnicode,
                true,
                None,
            )
            .err()
            .expect("non-unicode env seed must fail closed");
            assert_eq!(non_unicode, VaultInitError::InvalidEnvironmentSeedEncoding);

            // Clean up files
            fs::remove_file(secret_valid).ok();
            fs::remove_file(secret_short).ok();
            fs::remove_file(secret_empty).ok();
        }

        #[test]
        fn test_crypto_vault_manifest_contract() {
            let vault = test_vault();
            let manifest = vault.export_public_manifest();

            assert_eq!(manifest.vault_mode, "CRYPTO_HD_BIP32");
            assert!(!manifest.simulated);
            assert_eq!(manifest.whitelist_enforcement, "STRICT_FORMAT_AND_ALLOWLIST");
            assert_eq!(manifest.wallets.len(), 26);
            assert!(manifest.simulation_notice.contains("Cryptographic HD vault BIP-32/SLIP-0010 active"));

            let mut spendable_count = 0;
            let mut non_spendable_count = 0;

            for wallet in &manifest.wallets {
                assert!(!wallet.simulated);
                if wallet.address_is_spendable {
                    spendable_count += 1;
                } else {
                    non_spendable_count += 1;
                }
            }

            assert_eq!(spendable_count, 23);
            assert_eq!(non_spendable_count, 3);
        }

        #[test]
        fn test_hd_derivation_ed25519_solana() {
            let vault = test_vault();
            let sol = vault.derive_wallet_descriptor("leaf-solana").unwrap();

            assert_eq!(sol.curve, CryptographicCurve::Ed25519Slip0010);
            assert_eq!(sol.target_leaf_derivation_path, "m/44'/501'/0'/0'");
            assert!(sol.address_is_spendable);
            assert!(!sol.simulated);
            assert_eq!(sol.target_slip44_coin_type, 501);

            // Solana address must be a valid 32-byte Base58 string
            let decoded = bs58::decode(&sol.leaf_hot_address).into_vec().unwrap();
            assert_eq!(decoded.len(), 32);
            assert!(validate_chain_address("solana", &sol.leaf_hot_address).is_ok());
        }

        #[test]
        fn test_hd_derivation_secp256k1_ethereum_and_chainlink() {
            let vault = test_vault();

            let eth = vault.derive_wallet_descriptor("leaf-ethereum").unwrap();
            assert_eq!(eth.curve, CryptographicCurve::Secp256k1EcdsaBip44);
            assert_eq!(eth.target_master_derivation_path, "m/44'/60'/0'/0/0");
            assert_eq!(eth.target_leaf_derivation_path, "m/44'/60'/1'/0/0");
            assert!(eth.address_is_spendable);
            assert!(!eth.simulated);
            assert!(eth.leaf_hot_address.starts_with("0x"));
            assert_eq!(eth.leaf_hot_address.len(), 42);
            assert!(validate_chain_address("ethereum", &eth.leaf_hot_address).is_ok());

            let link = vault.derive_wallet_descriptor("leaf-chainlink").unwrap();
            assert_eq!(link.curve, CryptographicCurve::Secp256k1EcdsaBip44);
            assert_eq!(link.target_master_derivation_path, "m/44'/60'/0'/0/0");
            assert_eq!(link.target_leaf_derivation_path, "m/44'/60'/0'/0/1");
            assert!(link.address_is_spendable);
            assert!(!link.simulated);
            assert!(link.leaf_hot_address.starts_with("0x"));
            assert_eq!(link.leaf_hot_address.len(), 42);
            assert!(validate_chain_address("chainlink", &link.leaf_hot_address).is_ok());
        }

        #[test]
        fn test_hd_derivation_polkadot_and_non_bip32() {
            let vault = test_vault();

            let dot = vault.derive_wallet_descriptor("leaf-polkadot").unwrap();
            assert_eq!(dot.curve, CryptographicCurve::Sr25519Substrate);
            assert!(dot.address_is_spendable);
            assert!(dot.leaf_hot_address.starts_with('1'));
            assert!(validate_chain_address("polkadot", &dot.leaf_hot_address).is_ok());

            let canton = vault.derive_wallet_descriptor("leaf-canton").unwrap();
            assert_eq!(canton.curve, CryptographicCurve::MtlsX509Participant);
            assert!(!canton.address_is_spendable);
            assert!(canton.leaf_hot_address.starts_with("canton::"));
            assert!(validate_chain_address("canton", &canton.leaf_hot_address).is_ok());

            let binance = vault.derive_wallet_descriptor("leaf-binance-cex").unwrap();
            assert_eq!(binance.curve, CryptographicCurve::HmacSha256NoWithdraw);
            assert!(!binance.address_is_spendable);
            assert!(binance.leaf_hot_address.starts_with("binance:"));
            assert!(validate_chain_address("binance", &binance.leaf_hot_address).is_ok());

            let sandbox = vault.derive_wallet_descriptor("leaf-paper-sandbox").unwrap();
            assert_eq!(sandbox.curve, CryptographicCurve::VirtualZeroKey);
            assert!(!sandbox.address_is_spendable);
            assert!(sandbox.leaf_hot_address.starts_with("sandbox:"));
            assert!(validate_chain_address("sandbox", &sandbox.leaf_hot_address).is_ok());
        }

        #[test]
        fn test_spendable_addresses_across_all_26_leaves() {
            let vault = test_vault();
            let manifest = vault.export_public_manifest();

            for wallet in &manifest.wallets {
                let val_res = validate_chain_address(&wallet.chain, &wallet.leaf_hot_address);
                assert!(
                    val_res.is_ok(),
                    "Leaf {} address {} failed validation: {:?}",
                    wallet.leaf_id,
                    wallet.leaf_hot_address,
                    val_res
                );
            }

            // Specific ecosystem assertions
            let btc = vault.derive_wallet_descriptor("leaf-bitcoin").unwrap();
            assert!(btc.leaf_hot_address.starts_with("bc1q"));
            assert_eq!(btc.leaf_hot_address.len(), 42);

            let tron = vault.derive_wallet_descriptor("leaf-tron").unwrap();
            assert!(tron.leaf_hot_address.starts_with('T'));
            assert_eq!(tron.leaf_hot_address.len(), 34);

            let doge = vault.derive_wallet_descriptor("leaf-dogecoin").unwrap();
            assert!(doge.leaf_hot_address.starts_with('D'));
            assert_eq!(doge.leaf_hot_address.len(), 34);

            let xrp = vault.derive_wallet_descriptor("leaf-xrp").unwrap();
            assert!(xrp.leaf_hot_address.starts_with('r'));
            assert!(xrp.leaf_hot_address.len() == 33 || xrp.leaf_hot_address.len() == 34);

            let cosmos = vault.derive_wallet_descriptor("leaf-cosmos").unwrap();
            assert!(cosmos.leaf_hot_address.starts_with("cosmos1"));

            let sui = vault.derive_wallet_descriptor("leaf-sui").unwrap();
            assert!(sui.leaf_hot_address.starts_with("0x"));
            assert_eq!(sui.leaf_hot_address.len(), 66);

            let aptos = vault.derive_wallet_descriptor("leaf-aptos").unwrap();
            assert!(aptos.leaf_hot_address.starts_with("0x"));
            assert_eq!(aptos.leaf_hot_address.len(), 66);

            let ton = vault.derive_wallet_descriptor("leaf-ton").unwrap();
            assert!(ton.leaf_hot_address.starts_with("EQ") || ton.leaf_hot_address.starts_with("UQ"));
            assert_eq!(ton.leaf_hot_address.len(), 48);

            let cardano = vault.derive_wallet_descriptor("leaf-cardano").unwrap();
            assert!(cardano.leaf_hot_address.starts_with("addr1"));

            let tezos = vault.derive_wallet_descriptor("leaf-tezos").unwrap();
            assert!(tezos.leaf_hot_address.starts_with("tz1"));
            assert_eq!(tezos.leaf_hot_address.len(), 36);

            let stacks = vault.derive_wallet_descriptor("leaf-stacks").unwrap();
            assert!(stacks.leaf_hot_address.starts_with("SP"));

            let flow = vault.derive_wallet_descriptor("leaf-flow").unwrap();
            assert!(flow.leaf_hot_address.starts_with("0x"));
            assert_eq!(flow.leaf_hot_address.len(), 18);
        }

        #[test]
        fn test_validate_chain_address_rules() {
            // EVM checks
            assert!(validate_chain_address("ethereum", "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed").is_ok());
            assert!(validate_chain_address("ethereum", "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed").is_ok());
            assert!(validate_chain_address("ethereum", "0x5AAEB6053F3E94C9B9A09F33669435E7EF1BEAED").is_ok());
            // EVM invalid: missing 0x
            assert!(matches!(
                validate_chain_address("ethereum", "5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"),
                Err(AddressValidationError::InvalidFormat { .. })
            ));
            // EVM invalid: wrong length
            assert!(matches!(
                validate_chain_address("ethereum", "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAe"),
                Err(AddressValidationError::InvalidFormat { .. })
            ));
            // EVM invalid: corrupted EIP-55 checksum (flip 'F' to 'f' where hash requires uppercase)
            assert!(matches!(
                validate_chain_address("ethereum", "0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed"),
                Err(AddressValidationError::InvalidChecksum { .. })
            ));

            // Solana checks
            assert!(validate_chain_address("solana", "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN").is_ok());
            // Solana invalid: non-base58 char '0' or 'O'
            assert!(matches!(
                validate_chain_address("solana", "0K286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN"),
                Err(AddressValidationError::InvalidFormat { .. })
            ));
            // Solana invalid: wrong decoded length
            assert!(matches!(
                validate_chain_address("solana", "1111111111111111111111111111111"),
                Err(AddressValidationError::InvalidFormat { .. })
            ));

            // Bridges
            assert!(validate_chain_address("solana", "bridge:cctp:0x1234567890abcdef").is_ok());
            assert!(validate_chain_address("ethereum", "bridge:wormhole:0x1234567890abcdef").is_ok());
            assert!(matches!(
                validate_chain_address("ethereum", "bridge:unknown_bridge:0x1234"),
                Err(AddressValidationError::InvalidFormat { .. })
            ));
        }

        #[test]
        fn test_allowlist_evaluator_exact_and_wildcard_rejection() {
            let vault = test_vault();

            // Broad prefixes must be rejected as wildcards
            for prefix in ["0x", "r", "T", "D", "bc1q"] {
                assert!(!vault.is_destination_allowed(prefix));
            }

            // Arbitrary unlisted EVM address must be rejected
            let unlisted_evm = "0x0000000000000000000000000000000000000001";
            assert!(!vault.is_destination_allowed(unlisted_evm));

            // Internal addresses are automatically allowed
            let sol = vault.derive_wallet_descriptor("leaf-solana").unwrap();
            assert!(vault.is_destination_allowed(&sol.leaf_hot_address));
            assert!(vault.is_destination_allowed(&sol.master_treasury_address));

            // Canonical bridge URI is allowed
            assert!(vault.is_destination_allowed("bridge:cctp:treasury"));

            // Signing rejected destination fails closed with VaultSigningRejected
            let rejected = vault.validate_and_sign_transfer(
                false,
                "leaf-solana",
                "11111111111111111111111111111111", // valid 32-byte zero solana addr, but unlisted
                100.0,
                "SOL",
            );
            assert!(matches!(
                rejected,
                Err(RiskRejection::VaultSigningRejected { .. })
            ));
        }

        #[test]
        fn test_crypto_signing_ed25519_and_secp256k1() {
            let vault = test_vault();

            // 1. Ed25519 checkout signing for Solana
            let sol = vault.derive_wallet_descriptor("leaf-solana").unwrap();
            let sol_dest = sol.master_treasury_address.clone();
            let receipt_sol = vault
                .validate_and_sign_transfer(false, "leaf-solana", &sol_dest, 500.0, "SOL")
                .expect("Solana signing must succeed");

            assert_eq!(receipt_sol.vault_mode, "CRYPTO_HD_BIP32");
            assert!(!receipt_sol.simulated);
            assert!(!receipt_sol.signature_is_chain_valid);
            assert!(receipt_sol.signature_is_cryptographic);
            assert_eq!(receipt_sol.signature_scheme, "ED25519");
            assert_eq!(receipt_sol.whitelist_enforcement, "STRICT_FORMAT_AND_ALLOWLIST");
            assert!(receipt_sol.destination_whitelisted);
            assert!(receipt_sol.key_zeroized_after_sign);
            assert!(receipt_sol.signature_hex.starts_with("0x"));
            assert_eq!(receipt_sol.signature_hex.len(), 2 + 128); // "0x" + 64 bytes hex

            // Verify signature using verify_checkout_signature
            let payload_sol = format!(
                "ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}",
                receipt_sol.chain, receipt_sol.signer_address, receipt_sol.destination_address, 500.0, "SOL"
            );
            let digest_sol = sha256(payload_sol.as_bytes());
            let sol_pub_bytes = bs58::decode(&receipt_sol.signer_address).into_vec().unwrap();
            assert!(verify_checkout_signature(
                &receipt_sol.chain,
                &sol_pub_bytes,
                &digest_sol,
                &receipt_sol.signature_hex
            ));

            // Tampered signature fails
            let mut tampered_hex = receipt_sol.signature_hex.clone();
            let last_char = if tampered_hex.ends_with('0') { '1' } else { '0' };
            tampered_hex.pop();
            tampered_hex.push(last_char);
            assert!(!verify_checkout_signature(
                &receipt_sol.chain,
                &sol_pub_bytes,
                &digest_sol,
                &tampered_hex
            ));

            // 2. Secp256k1 checkout signing for Ethereum
            let eth = vault.derive_wallet_descriptor("leaf-ethereum").unwrap();
            let eth_dest = eth.master_treasury_address.clone();
            let receipt_eth = vault
                .validate_and_sign_transfer(false, "leaf-ethereum", &eth_dest, 1000.0, "ETH")
                .expect("Ethereum signing must succeed");

            assert_eq!(receipt_eth.vault_mode, "CRYPTO_HD_BIP32");
            assert!(!receipt_eth.simulated);
            assert!(!receipt_eth.signature_is_chain_valid);
            assert!(receipt_eth.signature_is_cryptographic);
            assert_eq!(receipt_eth.signature_scheme, "SECP256K1_ECDSA");
            assert_eq!(receipt_eth.whitelist_enforcement, "STRICT_FORMAT_AND_ALLOWLIST");
            assert!(receipt_eth.destination_whitelisted);
            assert!(receipt_eth.key_zeroized_after_sign);
            assert!(receipt_eth.signature_hex.starts_with("0x"));
            assert_eq!(receipt_eth.signature_hex.len(), 2 + 128);

            // Verify Secp256k1 signature
            let payload_eth = format!(
                "ROBOTRADER_V3_TRANSFER|chain={}|signer={}|dest={}|amount_usd={:.4}|token={}",
                receipt_eth.chain, receipt_eth.signer_address, receipt_eth.destination_address, 1000.0, "ETH"
            );
            let digest_eth = sha256(payload_eth.as_bytes());
            // Derive leaf hot pubkey bytes for verification
            let eth_seed = vault.master_seed.as_slice();
            let eth_child = crate::crypto_vault::bip32_derive_secp256k1(eth_seed, &eth.target_leaf_derivation_path).unwrap();
            let sk = k256::SecretKey::from_bytes((eth_child.as_slice()).into()).unwrap();
            let compressed_pub = sk.public_key().to_encoded_point(true);
            assert!(verify_checkout_signature(
                &receipt_eth.chain,
                compressed_pub.as_bytes(),
                &digest_eth,
                &receipt_eth.signature_hex
            ));

            // Tampered Secp256k1 signature fails
            let mut tampered_eth_hex = receipt_eth.signature_hex.clone();
            let last_char = if tampered_eth_hex.ends_with('0') { '1' } else { '0' };
            tampered_eth_hex.pop();
            tampered_eth_hex.push(last_char);
            assert!(!verify_checkout_signature(
                &receipt_eth.chain,
                compressed_pub.as_bytes(),
                &digest_eth,
                &tampered_eth_hex
            ));
        }

        #[test]
        fn test_kill_switch_and_zero_amount_rejection() {
            let vault = test_vault();
            let sol = vault.derive_wallet_descriptor("leaf-solana").unwrap();
            let sol_dest = sol.master_treasury_address.clone();

            let killed = vault.validate_and_sign_transfer(true, "leaf-solana", &sol_dest, 100.0, "SOL");
            assert!(matches!(killed, Err(RiskRejection::KillSwitchActive { .. })));

            let zero_amount = vault.validate_and_sign_transfer(false, "leaf-solana", &sol_dest, 0.0, "SOL");
            assert!(matches!(zero_amount, Err(RiskRejection::ZeroPositionSize)));

            let neg_amount = vault.validate_and_sign_transfer(false, "leaf-solana", &sol_dest, -50.0, "SOL");
            assert!(matches!(neg_amount, Err(RiskRejection::ZeroPositionSize)));
        }

        #[test]
        fn test_select_vault_mode_pure() {
            assert_eq!(select_vault_mode_from(None).unwrap(), VaultBackendKind::Simulated);
            assert_eq!(select_vault_mode_from(Some(OsString::from(""))).unwrap(), VaultBackendKind::Simulated);
            assert_eq!(select_vault_mode_from(Some(OsString::from("SIMULATED"))).unwrap(), VaultBackendKind::Simulated);
            assert_eq!(select_vault_mode_from(Some(OsString::from("CRYPTO_HD_BIP32"))).unwrap(), VaultBackendKind::CryptoHdBip32);
            assert_eq!(
                select_vault_mode_from(Some(OsString::from("UNSUPPORTED_ENCLAVE"))).unwrap_err(),
                VaultInitError::InvalidVaultMode("UNSUPPORTED_ENCLAVE".to_string())
            );
        }

    }
}

pub mod vault;

use robotrader_common::{
    ApprovedOrder, OnChainTokenSafety, OrderIntent, PolicyEnvelope, PortfolioState,
};
use serde::{Deserialize, Serialize};
use thiserror::Error;
pub use vault::{RustVaultEnclave, ZeroizingBytes};

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

    #[error("Vault Enclave signing rejected: {reason}")]
    VaultSigningRejected { reason: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskLimits {
    pub max_daily_drawdown_pct: f64,
    pub max_single_position_pct: f64,
    pub max_leverage_ceiling: f64,
    pub kelly_fraction: f64,
    pub target_annual_volatility_pct: f64,
    pub min_edge_over_cost_bps: f64,
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
            min_edge_over_cost_bps: 12.0,
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

    /// Synchronous pre-trade firewall (<50µs execution).
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

        // 3. Validate expected alpha edge vs execution cost hurdle
        if intent.expected_edge_bps < self.limits.min_edge_over_cost_bps {
            return Err(RiskRejection::InsufficientEdge {
                edge_bps: intent.expected_edge_bps,
                min_bps: self.limits.min_edge_over_cost_bps,
            });
        }

        // 4. Validate slippage bounds
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

        // 5. On-chain token anti-rug gate (mandatory if safety payload is present)
        if let Some(ref safety) = intent.token_safety {
            self.validate_token_safety(safety)?;
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
        let mev_priority_tip_bps = ((intent.expected_edge_bps * 0.10) as u32).clamp(2, 25);

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

    #[test]
    fn test_vault_enclave_26_chains_hd_derivation_and_whitelist_signing() {
        let enclave = RustVaultEnclave::default();
        let manifest = enclave.export_public_manifest();

        assert_eq!(manifest.wallets.len(), 26);
        assert!(manifest.zeroize_on_drop);
        assert!(!manifest.python_private_key_access);

        // Verify distinct master vs leaf addresses and native formatting
        let sol = enclave.derive_wallet_descriptor("leaf-solana").unwrap();
        assert_ne!(sol.master_treasury_address, sol.leaf_hot_address);
        assert_eq!(sol.master_derivation_path, "m/44'/501'/0'/0/0");
        assert_eq!(sol.leaf_derivation_path, "m/44'/501'/1'/0/0");

        let btc = enclave.derive_wallet_descriptor("leaf-bitcoin").unwrap();
        assert!(btc.master_treasury_address.starts_with("bc1q"));
        assert_eq!(btc.master_derivation_path, "m/84'/0'/0'/0/0");

        let eth = enclave.derive_wallet_descriptor("leaf-ethereum").unwrap();
        assert!(eth.master_treasury_address.starts_with("0x"));
        assert_eq!(eth.master_treasury_address.len(), 42);

        // Whitelisted operator address succeeds and zeroizes ephemeral key
        let receipt = enclave
            .validate_and_sign_transfer(
                false,
                "Solana",
                "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN",
                1500.0,
                "SOL",
            )
            .expect("Whitelisted operator address should be signed");
        assert!(receipt.destination_whitelisted);
        assert!(receipt.key_zeroized_after_sign);
        assert!(receipt.signature_hex.starts_with("0x"));
        assert_eq!(receipt.signature_hex.len(), 66);

        // Untrusted / attacker address is rejected by Rust enclave
        let bad = enclave.validate_and_sign_transfer(
            false,
            "Solana",
            "attacker_drain_wallet_999999999",
            1500.0,
            "SOL",
        );
        assert!(matches!(bad, Err(RiskRejection::VaultSigningRejected { .. })));

        // Kill-switch active blocks all signing
        let killed = enclave.validate_and_sign_transfer(
            true,
            "Solana",
            "FK286wA4ggcyhMrxWnBUW92JVmJPQN6xkmQ9eXgjpgN",
            1500.0,
            "SOL",
        );
        assert!(matches!(killed, Err(RiskRejection::KillSwitchActive { .. })));

        // Verify volatile zeroization
        let mut secret = ZeroizingBytes::new([0xAAu8; 32]);
        assert_eq!(secret.as_slice()[0], 0xAA);
        secret.zeroize_now();
        assert!(secret.as_slice().iter().all(|&b| b == 0));
    }
}

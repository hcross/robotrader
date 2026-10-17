use robotrader_common::{
    DirectionalBias, ExecutionReport, MarketEvent, OrderIntent, OrderType, PodId, PolicyEnvelope,
    Side, Venue,
};

pub trait StrategyPod: Send + Sync {
    fn id(&self) -> PodId;
    fn on_market_event(
        &mut self,
        event: &MarketEvent,
        envelope: &PolicyEnvelope,
    ) -> Vec<OrderIntent>;
    fn on_execution_report(&mut self, report: &ExecutionReport);
}

/// Pod 1: Delta-Neutral Carry & Spot-Perp Basis Arbitrage (`pod_carry`).
/// Captures high perpetual funding APR and basis spreads with near-zero directional exposure.
pub struct CarryPod {
    pub default_min_funding_apr: f64,
}

impl Default for CarryPod {
    fn default() -> Self {
        Self {
            default_min_funding_apr: 0.15, // 15% annualized funding threshold
        }
    }
}

impl StrategyPod for CarryPod {
    fn id(&self) -> PodId {
        PodId::PodCarry
    }

    fn on_market_event(
        &mut self,
        event: &MarketEvent,
        envelope: &PolicyEnvelope,
    ) -> Vec<OrderIntent> {
        let MarketEvent::FundingSnapshot {
            symbol,
            spot_price,
            perp_price,
            annualized_funding_apr,
            ..
        } = event
        else {
            return Vec::new();
        };

        let min_apr = envelope
            .pod_allocations
            .get(PodId::PodCarry.as_str())
            .and_then(|a| a.min_funding_apr)
            .unwrap_or(self.default_min_funding_apr);

        if *annualized_funding_apr < min_apr || *spot_price <= 0.0 {
            return Vec::new();
        }

        let basis_bps = ((*perp_price - *spot_price) / *spot_price) * 10_000.0;
        // Expected 3-day carry + basis convergence in bps
        let expected_edge_bps = (*annualized_funding_apr * 10_000.0 / 120.0) + basis_bps.max(0.0);

        if expected_edge_bps < 15.0 {
            return Vec::new();
        }

        vec![OrderIntent {
            pod_id: PodId::PodCarry,
            symbol: symbol.clone(),
            venue: Venue::BinancePerp,
            side: Side::Sell, // Delta-neutral hedge leg (Long Spot + Short Perp)
            order_type: OrderType::PostOnlyMaker,
            reference_price: *perp_price,
            win_probability: 0.78,
            reward_risk_ratio: 2.8,
            asset_volatility_pct: 1.2,
            expected_edge_bps,
            max_slippage_bps: 15,
            requested_leverage: 1.5,
            stop_loss_pct: 0.8,
            take_profit_pct: 2.2,
            solana_safety: None,
            rationale: format!(
                "Delta-Neutral Carry: APR {:.1}%, Basis +{:.1} bps",
                annualized_funding_apr * 100.0,
                basis_bps
            ),
        }]
    }

    fn on_execution_report(&mut self, _report: &ExecutionReport) {}
}

/// Pod 2: Intraday Orderflow (OBI + CVD) & Volatility Breakout (`pod_momentum`).
pub struct MomentumPod {
    pub obi_threshold: f64,
    pub min_breakout_zscore: f64,
}

impl Default for MomentumPod {
    fn default() -> Self {
        Self {
            obi_threshold: 0.22,
            min_breakout_zscore: 1.8,
        }
    }
}

impl StrategyPod for MomentumPod {
    fn id(&self) -> PodId {
        PodId::PodMomentum
    }

    fn on_market_event(
        &mut self,
        event: &MarketEvent,
        envelope: &PolicyEnvelope,
    ) -> Vec<OrderIntent> {
        let MarketEvent::OrderbookTick {
            symbol,
            mid_price,
            bid_volume_top5,
            ask_volume_top5,
            cvd_delta,
            atr_pct,
            breakout_zscore,
            ..
        } = event
        else {
            return Vec::new();
        };

        let total_book = bid_volume_top5 + ask_volume_top5;
        if total_book <= 0.0 || *mid_price <= 0.0 {
            return Vec::new();
        }

        // Orderbook Imbalance in [-1.0, +1.0]
        let obi = (bid_volume_top5 - ask_volume_top5) / total_book;
        let catalyst_boost = envelope
            .asset_overrides
            .get(symbol)
            .map(|o| o.catalyst_score)
            .unwrap_or(0.5);

        let pod_bias = envelope
            .pod_allocations
            .get(PodId::PodMomentum.as_str())
            .and_then(|a| a.directional_bias)
            .unwrap_or(DirectionalBias::Neutral);

        // Long Breakout condition
        if obi >= self.obi_threshold
            && *cvd_delta > 0.0
            && *breakout_zscore >= self.min_breakout_zscore
            && pod_bias != DirectionalBias::ShortBias
        {
            let expected_edge_bps =
                22.0 + (obi * 40.0) + (*breakout_zscore * 6.0) + (catalyst_boost * 18.0);
            return vec![OrderIntent {
                pod_id: PodId::PodMomentum,
                symbol: symbol.clone(),
                venue: Venue::HyperliquidPerp,
                side: Side::Buy,
                order_type: OrderType::PostOnlyMaker,
                reference_price: *mid_price,
                win_probability: (0.58 + catalyst_boost * 0.12).clamp(0.52, 0.75),
                reward_risk_ratio: 2.4,
                asset_volatility_pct: (*atr_pct).max(1.5),
                expected_edge_bps,
                max_slippage_bps: 20,
                requested_leverage: 2.0,
                stop_loss_pct: (*atr_pct * 0.9).clamp(0.8, 3.0),
                take_profit_pct: (*atr_pct * 2.2).clamp(1.8, 7.5),
                solana_safety: None,
                rationale: format!(
                    "Momentum Long: OBI +{:.2}, z={:.2}, catalyst={:.2}",
                    obi, breakout_zscore, catalyst_boost
                ),
            }];
        }

        // Short Breakdown condition
        if obi <= -self.obi_threshold
            && *cvd_delta < 0.0
            && *breakout_zscore <= -self.min_breakout_zscore
            && pod_bias != DirectionalBias::LongBias
        {
            let expected_edge_bps =
                22.0 + (obi.abs() * 40.0) + (breakout_zscore.abs() * 6.0);
            return vec![OrderIntent {
                pod_id: PodId::PodMomentum,
                symbol: symbol.clone(),
                venue: Venue::HyperliquidPerp,
                side: Side::Sell,
                order_type: OrderType::PostOnlyMaker,
                reference_price: *mid_price,
                win_probability: 0.60,
                reward_risk_ratio: 2.2,
                asset_volatility_pct: (*atr_pct).max(1.5),
                expected_edge_bps,
                max_slippage_bps: 20,
                requested_leverage: 2.0,
                stop_loss_pct: (*atr_pct * 0.9).clamp(0.8, 3.0),
                take_profit_pct: (*atr_pct * 2.1).clamp(1.8, 7.0),
                solana_safety: None,
                rationale: format!(
                    "Momentum Short: OBI {:.2}, z={:.2}",
                    obi, breakout_zscore
                ),
            }];
        }

        Vec::new()
    }

    fn on_execution_report(&mut self, _report: &ExecutionReport) {}
}

/// Pod 3: Solana Smart-Money & Catalyst Execution (`pod_solana_alpha`).
pub struct SolanaAlphaPod {
    pub min_whale_winrate: f64,
    pub min_buy_volume_usd: f64,
}

impl Default for SolanaAlphaPod {
    fn default() -> Self {
        Self {
            min_whale_winrate: 0.65,
            min_buy_volume_usd: 15_000.0,
        }
    }
}

impl StrategyPod for SolanaAlphaPod {
    fn id(&self) -> PodId {
        PodId::PodSolanaAlpha
    }

    fn on_market_event(
        &mut self,
        event: &MarketEvent,
        _envelope: &PolicyEnvelope,
    ) -> Vec<OrderIntent> {
        let MarketEvent::SolanaSmartMoneySwap {
            symbol,
            price_usd,
            whale_wallet_winrate,
            buy_volume_usd,
            safety,
            ..
        } = event
        else {
            return Vec::new();
        };

        if *whale_wallet_winrate < self.min_whale_winrate
            || *buy_volume_usd < self.min_buy_volume_usd
        {
            return Vec::new();
        }

        let expected_edge_bps = 45.0 + (*whale_wallet_winrate - 0.60) * 180.0;

        vec![OrderIntent {
            pod_id: PodId::PodSolanaAlpha,
            symbol: symbol.clone(),
            venue: Venue::SolanaJupiterJito,
            side: Side::Buy,
            order_type: OrderType::JitoBundleAtomic,
            reference_price: *price_usd,
            win_probability: (*whale_wallet_winrate).clamp(0.55, 0.78),
            reward_risk_ratio: 2.8,
            asset_volatility_pct: 3.5,
            expected_edge_bps,
            max_slippage_bps: 65,
            requested_leverage: 1.0,
            stop_loss_pct: 4.0,
            take_profit_pct: 12.0,
            solana_safety: Some(safety.clone()),
            rationale: format!(
                "Solana Smart-Money inflow ${:.0}k (wallet winrate {:.0}%)",
                buy_volume_usd / 1000.0,
                whale_wallet_winrate * 100.0
            ),
        }]
    }

    fn on_execution_report(&mut self, _report: &ExecutionReport) {}
}

/// Pod 4: DEX Atomic Pool Sniper (`pod_sniper`).
pub struct DexSniperPod {
    pub min_initial_liquidity_usd: f64,
}

impl Default for DexSniperPod {
    fn default() -> Self {
        Self {
            min_initial_liquidity_usd: 25_000.0,
        }
    }
}

impl StrategyPod for DexSniperPod {
    fn id(&self) -> PodId {
        PodId::PodSniper
    }

    fn on_market_event(
        &mut self,
        event: &MarketEvent,
        _envelope: &PolicyEnvelope,
    ) -> Vec<OrderIntent> {
        let MarketEvent::SolanaPoolLaunch {
            symbol,
            initial_liquidity_usd,
            creator_rug_count,
            price_usd,
            safety,
            ..
        } = event
        else {
            return Vec::new();
        };

        if *creator_rug_count > 0 || *initial_liquidity_usd < self.min_initial_liquidity_usd {
            return Vec::new();
        }

        vec![OrderIntent {
            pod_id: PodId::PodSniper,
            symbol: symbol.clone(),
            venue: Venue::SolanaRaydiumAtomic,
            side: Side::Buy,
            order_type: OrderType::JitoBundleAtomic,
            reference_price: *price_usd,
            win_probability: 0.56,
            reward_risk_ratio: 3.5,
            asset_volatility_pct: 6.0,
            expected_edge_bps: 95.0,
            max_slippage_bps: 120,
            requested_leverage: 1.0,
            stop_loss_pct: 6.0,
            take_profit_pct: 22.0,
            solana_safety: Some(safety.clone()),
            rationale: format!(
                "Atomic Raydium pool launch: LP ${:.0}k, clean deployer",
                initial_liquidity_usd / 1000.0
            ),
        }]
    }

    fn on_execution_report(&mut self, _report: &ExecutionReport) {}
}

pub fn default_strategy_pods() -> Vec<Box<dyn StrategyPod>> {
    vec![
        Box::new(CarryPod::default()),
        Box::new(MomentumPod::default()),
        Box::new(SolanaAlphaPod::default()),
        Box::new(DexSniperPod::default()),
    ]
}

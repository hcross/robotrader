use robotrader_common::{
    DirectionalBias, EcosystemPodSpec, ExecutionReport, MarketEvent, OrderIntent, OrderType, PodId,
    PolicyEnvelope, Side, Venue,
};

pub const MAX_PODS_PER_BLOCKCHAIN: usize = 4;

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
            token_safety: None,
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
                token_safety: None,
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
                token_safety: None,
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

/// Pod 3: On-Chain Smart-Money & Catalyst Execution (`pod_onchain_alpha`).
pub struct OnChainAlphaPod {
    pub min_whale_winrate: f64,
    pub min_buy_volume_usd: f64,
}

impl Default for OnChainAlphaPod {
    fn default() -> Self {
        Self {
            min_whale_winrate: 0.65,
            min_buy_volume_usd: 15_000.0,
        }
    }
}

impl StrategyPod for OnChainAlphaPod {
    fn id(&self) -> PodId {
        PodId::PodOnchainAlpha
    }

    fn on_market_event(
        &mut self,
        event: &MarketEvent,
        _envelope: &PolicyEnvelope,
    ) -> Vec<OrderIntent> {
        let MarketEvent::OnchainSmartMoneySwap {
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
            pod_id: PodId::PodOnchainAlpha,
            symbol: symbol.clone(),
            venue: Venue::OnchainDexAggregator,
            side: Side::Buy,
            order_type: OrderType::MevBundleAtomic,
            reference_price: *price_usd,
            win_probability: (*whale_wallet_winrate).clamp(0.55, 0.78),
            reward_risk_ratio: 2.8,
            asset_volatility_pct: 3.5,
            expected_edge_bps,
            max_slippage_bps: 65,
            requested_leverage: 1.0,
            stop_loss_pct: 4.0,
            take_profit_pct: 12.0,
            token_safety: Some(safety.clone()),
            rationale: format!(
                "On-Chain Smart-Money inflow ${:.0}k (wallet winrate {:.0}%)",
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
        let MarketEvent::OnchainPoolLaunch {
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
            venue: Venue::OnchainAtomicPool,
            side: Side::Buy,
            order_type: OrderType::MevBundleAtomic,
            reference_price: *price_usd,
            win_probability: 0.56,
            reward_risk_ratio: 3.5,
            asset_volatility_pct: 6.0,
            expected_edge_bps: 95.0,
            max_slippage_bps: 120,
            requested_leverage: 1.0,
            stop_loss_pct: 6.0,
            take_profit_pct: 22.0,
            token_safety: Some(safety.clone()),
            rationale: format!(
                "Atomic DEX pool launch: LP ${:.0}k, clean deployer",
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
        Box::new(OnChainAlphaPod::default()),
        Box::new(DexSniperPod::default()),
    ]
}

/// Wrapper that adapts a canonical Rust `StrategyPod` to a specific blockchain ecosystem's
/// venue and labels its execution rationale with `[pod_code @ native_venue]`.
pub struct EcosystemAdaptedPod {
    pub spec: EcosystemPodSpec,
    pub target_venue: Venue,
    pub inner: Box<dyn StrategyPod>,
}

impl StrategyPod for EcosystemAdaptedPod {
    fn id(&self) -> PodId {
        self.spec.slot_id
    }

    fn on_market_event(
        &mut self,
        event: &MarketEvent,
        envelope: &PolicyEnvelope,
    ) -> Vec<OrderIntent> {
        let mut intents = self.inner.on_market_event(event, envelope);
        for intent in intents.iter_mut() {
            intent.venue = self.target_venue;
            intent.rationale = format!(
                "[{} @ {}] {}",
                self.spec.pod_code, self.spec.native_venue, intent.rationale
            );
        }
        intents
    }

    fn on_execution_report(&mut self, report: &ExecutionReport) {
        self.inner.on_execution_report(report);
    }
}

fn spec(
    slot_id: PodId,
    pod_code: &str,
    name: &str,
    archetype: &str,
    native_venue: &str,
    default_weight: f64,
    description: &str,
) -> EcosystemPodSpec {
    EcosystemPodSpec {
        slot_id,
        pod_code: pod_code.to_string(),
        name: name.to_string(),
        archetype: archetype.to_string(),
        native_venue: native_venue.to_string(),
        default_weight,
        description: description.to_string(),
    }
}

/// Returns the catalog of ecosystem-specific Rust Strategy Pods for a given blockchain leaf
/// (guaranteed `1 <= len <= MAX_PODS_PER_BLOCKCHAIN (4)`).
pub fn ecosystem_pod_specs(leaf_id: &str) -> Vec<EcosystemPodSpec> {
    let mut specs = match leaf_id {
        "leaf-solana" => vec![
            spec(
                PodId::PodCarry,
                "sol_drift_carry",
                "Solana Drift/JUP Perp Carry",
                "DELTA_NEUTRAL_CARRY",
                "Drift Protocol / Jupiter Perps",
                0.35,
                "Arbitrage delta-neutre Spot SOL/JUP/RAY vs Funding Perp Solana (>15% APR).",
            ),
            spec(
                PodId::PodMomentum,
                "sol_clob_momentum",
                "Phoenix & Raydium CLMM OBI Breakout",
                "CLOB_ORDERFLOW_MOMENTUM",
                "Jupiter v6 / Raydium CLMM",
                0.35,
                "Capture des déséquilibres L2 (OBI + CVD) et cassures de volatilité en <400ms.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "sol_jito_smart_money",
                "Jito Bundle Smart-Money Tracker",
                "ONCHAIN_WHALE_FLOW",
                "Jito Bundles / Jupiter v6",
                0.20,
                "Suivi atomique des portefeuilles Solana à fort winrate avec filtre anti-rug HardRiskGate.",
            ),
            spec(
                PodId::PodSniper,
                "sol_raydium_sniper",
                "Raydium Atomic Pool Launch Sniper",
                "ATOMIC_DEX_SNIPER",
                "Raydium Atomic / Jito",
                0.10,
                "Exécution atomique sur nouveaux pools Raydium vérifiés (Mint/Freeze révoqués, LP verrouillée).",
            ),
        ],
        "leaf-bitcoin" => vec![
            spec(
                PodId::PodCarry,
                "btc_basis_carry",
                "Bitcoin Spot-Perp & ETF Basis Carry",
                "BASIS_CASH_AND_CARRY",
                "Bitcoin Native / Perp Basis",
                0.45,
                "Capture du basis institutionnel BTC Spot vs Perp et prime de liquidité.",
            ),
            spec(
                PodId::PodMomentum,
                "btc_hash_ribbon_breakout",
                "BTC Mempool & Orderflow Breakout",
                "MACRO_VOL_BREAKOUT",
                "Bitcoin L1 / Native Liquidity",
                0.35,
                "Breakout directionnel filtré par l'expansion Hash Ribbon, les flux ETF et l'OBI L2.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "btc_thorchain_peg_arb",
                "ThorChain Native BTC / wBTC / sBTC Arb",
                "CROSS_WRAPPER_ARB",
                "ThorChain Native Pool",
                0.20,
                "Arbitrage de parité entre BTC natif, wBTC et sBTC et suivi des baleines UTXO.",
            ),
        ],
        "leaf-ethereum" => vec![
            spec(
                PodId::PodCarry,
                "eth_lst_restaking_carry",
                "Lido stETH & EigenLayer Restaking Carry",
                "LST_RESTAKING_CARRY",
                "Lido / EigenLayer / Aave v3",
                0.40,
                "Portage de rendement stETH + EigenLayer combiné à une jambe de couverture delta-neutre.",
            ),
            spec(
                PodId::PodMomentum,
                "eth_univ4_clmm_momentum",
                "Uniswap v4 Hooks & L2 OBI Momentum",
                "CLMM_RANGE_MOMENTUM",
                "Uniswap v4",
                0.30,
                "Momentum sur paires ETH-USDC, UNI-ETH et AAVE-ETH calibré sur le base-fee EIP-1559.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "eth_curve_peg_arb",
                "Curve stETH/ETH Peg & Smart-Money Pod",
                "LST_PEG_ARBITRAGE",
                "Curve Finance / Aave v3",
                0.20,
                "Arbitrage de convergence sur le peg stETH/ETH et suivi des flux institutionnels.",
            ),
            spec(
                PodId::PodSniper,
                "eth_mev_liquidation_sniper",
                "Flashbots Protect DeFi Liquidation Pod",
                "MEV_LIQUIDATION_SNIPER",
                "Flashbots / Uniswap v4",
                0.10,
                "Capture atomique des liquidations DeFi Aave/Morpho lorsque le gas L1 est bas.",
            ),
        ],
        "leaf-hyperliquid" => vec![
            spec(
                PodId::PodCarry,
                "hype_hlp_funding_carry",
                "HyperCore Perp Funding & HLP Basis",
                "CLOB_FUNDING_CARRY",
                "HyperCore L1 CLOB",
                0.35,
                "Arbitrage de funding perpétuel sans frais de gas sur le carnet natif Hyperliquid.",
            ),
            spec(
                PodId::PodMomentum,
                "hype_clob_obi_scalper",
                "HyperCore L1 Post-Only OBI Scalper",
                "SUBSECOND_CLOB_MOMENTUM",
                "HyperCore L1 CLOB",
                0.35,
                "Exécution Post-Only Maker sur HYPE-USDC et PURR-USDC pilotée par le déséquilibre L2.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "hype_vault_whale_tracker",
                "HLP Vault Skew & Top-Trader Flow",
                "VAULT_POSITION_FLOW",
                "HLP Liquidity Vault",
                0.20,
                "Suivi temps réel du skew du coffre HLP et des portefeuilles perps à haut Sharpe.",
            ),
            spec(
                PodId::PodSniper,
                "hype_hyperevm_sniper",
                "HyperEVM Spot Auction & Liquidation Pod",
                "SPOT_PERP_SNIPER",
                "HyperEVM / HyperCore",
                0.10,
                "Capture des dislocations entre les enchères Spot HyperEVM et le carnet Perp.",
            ),
        ],
        "leaf-sui" => vec![
            spec(
                PodId::PodCarry,
                "sui_navi_scallop_carry",
                "Navi & Scallop Move Lending Carry",
                "MOVE_YIELD_CARRY",
                "Navi Protocol",
                0.30,
                "Portage de taux USDC/SUI sur les marchés monétaires Move et basis SUI.",
            ),
            spec(
                PodId::PodMomentum,
                "sui_deepbook_clob_momentum",
                "DeepBook v3 Sub-400ms CLOB Momentum",
                "MOVE_CLOB_MOMENTUM",
                "DeepBook v3 CLOB",
                0.35,
                "Breakout sur le carnet d'ordres central natif DeepBook v3 (finalité Mysticeti <400ms).",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "sui_cetus_clmm_alpha",
                "Cetus CLMM Whale & Range Rebalancer",
                "CLMM_WHALE_FLOW",
                "Cetus CLMM",
                0.25,
                "Suivi des flux de baleines sur SUI-USDC, DEEP-SUI et CETUS-SUI.",
            ),
            spec(
                PodId::PodSniper,
                "sui_object_pool_sniper",
                "Sui Move Atomic Pool Sniper",
                "MOVE_POOL_SNIPER",
                "Cetus / DeepBook v3",
                0.10,
                "Entrée atomique sur nouvelles poches de liquidité Move vérifiées.",
            ),
        ],
        "leaf-bnb" => vec![
            spec(
                PodId::PodCarry,
                "bnb_venus_carry",
                "Venus Protocol & BNB Basis Carry",
                "LENDING_BASIS_CARRY",
                "Venus Protocol",
                0.40,
                "Capture des écarts de taux USDT/BNB sur Venus et du funding BNB.",
            ),
            spec(
                PodId::PodMomentum,
                "bnb_pancake_v3_momentum",
                "PancakeSwap v3 CLMM OBI Breakout",
                "DEX_CLMM_MOMENTUM",
                "PancakeSwap v3",
                0.40,
                "Momentum intraday sur BNB-USDT et CAKE-BNB dans les ticks concentrés PancakeSwap v3.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "bnb_launchpool_whale_flow",
                "BNB Launchpool & Smart-Money Catalyst",
                "CATALYST_WHALE_FLOW",
                "PancakeSwap v3 / opBNB",
                0.20,
                "Détection des accumulations on-chain liées aux Launchpools et rotations BSC.",
            ),
        ],
        "leaf-xrp" => vec![
            spec(
                PodId::PodCarry,
                "xrp_rlusd_mm_carry",
                "XRPL Native CLOB & RLUSD Spread Carry",
                "CLOB_SPREAD_CARRY",
                "XRPL Native CLOB",
                0.45,
                "Market-making passif et capture de spread sur XRP-RLUSD et XRP-USDT.",
            ),
            spec(
                PodId::PodMomentum,
                "xrp_clob_obi_momentum",
                "XRPL Built-In DEX Orderflow Breakout",
                "NATIVE_DEX_MOMENTUM",
                "XRPL Native CLOB",
                0.35,
                "Suivi des déséquilibres d'ordres sur le carnet natif XRPL (finalité 4s).",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "xrp_xls30_amm_arb",
                "XRPL XLS-30 AMM vs CLOB Arbitrage",
                "AMM_CLOB_ARBITRAGE",
                "XRPL XLS-30 AMM",
                0.20,
                "Arbitrage mécanique d'enchère continue entre les pools XLS-30 et le CLOB XRPL.",
            ),
        ],
        "leaf-ton" => vec![
            spec(
                PodId::PodCarry,
                "ton_usdt_vault_carry",
                "TON Native USDT & STON.fi Yield Carry",
                "STABLE_LP_CARRY",
                "STON.fi / DeDust",
                0.40,
                "Portage de liquidité sur l'USDT natif TON et capture de frais de swap.",
            ),
            spec(
                PodId::PodMomentum,
                "ton_jetton_momentum",
                "TON & Jetton Volatility Breakout",
                "JETTON_MOMENTUM",
                "STON.fi",
                0.40,
                "Momentum sur TON-USDT et NOT-TON lors des vagues de volume Telegram Mini-Apps.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "ton_whale_accumulator",
                "TON Workchain Whale & TVL Flow",
                "ONCHAIN_WHALE_FLOW",
                "DeDust",
                0.20,
                "Suivi des flux de baleines TON sur les pools DeDust et STON.fi.",
            ),
        ],
        "leaf-tron" => vec![
            spec(
                PodId::PodCarry,
                "trx_justlend_usdt_carry",
                "JustLend TRC-20 USDT & Energy Carry",
                "STABLECOIN_ENERGY_CARRY",
                "JustLend DAO",
                0.55,
                "Capture du rendement d'alimentation TRC-20 USDT et location d'Energy TRON.",
            ),
            spec(
                PodId::PodMomentum,
                "trx_sunswap_momentum",
                "SunSwap v3 TRX/USDT Orderflow Pod",
                "DEX_ORDERFLOW_MOMENTUM",
                "SunSwap v3",
                0.30,
                "Exécution directionnelle sur TRX-USDT lors des pics de règlement stablecoin.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "trx_usdt_mint_tracker",
                "Tether Treasury Mint & Peg Arbitrage",
                "TREASURY_FLOW_ARB",
                "SunSwap v3",
                0.15,
                "Réaction mécanique aux émissions/destructions de TRC-20 USDT par Tether Treasury.",
            ),
        ],
        "leaf-avalanche" => vec![
            spec(
                PodId::PodCarry,
                "avax_benqi_savax_carry",
                "Benqi sAVAX Liquid Staking Carry",
                "LST_BASIS_CARRY",
                "Benqi / GMX v2",
                0.40,
                "Portage sAVAX/AVAX combiné au funding perpétuel GMX v2 sur C-Chain.",
            ),
            spec(
                PodId::PodMomentum,
                "avax_lfj_bin_momentum",
                "LFJ (TraderJoe) Discrete Bin Breakout",
                "LIQUIDITY_BOOK_MOMENTUM",
                "LFJ Liquidity Book",
                0.40,
                "Momentum directionnel à travers les bins de liquidité discrète LFJ v2.2.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "avax_subnet_icm_flow",
                "Avalanche9000 Teleporter & Whale Flow",
                "SUBNET_FLOW_ALPHA",
                "GMX v2 Avalanche",
                0.20,
                "Suivi des flux inter-subnets (ICM/Teleporter) et des positions GMX v2.",
            ),
        ],
        "leaf-cosmos" => vec![
            spec(
                PodId::PodCarry,
                "atom_stride_ibc_carry",
                "Stride stATOM & Osmosis Yield Carry",
                "IBC_LST_CARRY",
                "Stride / Osmosis",
                0.45,
                "Portage du rendement de staking liquide stATOM et des bassins stables IBC.",
            ),
            spec(
                PodId::PodMomentum,
                "atom_osmosis_clmm_momentum",
                "Osmosis Supercharged Liquidity Breakout",
                "IBC_DEX_MOMENTUM",
                "Osmosis DEX",
                0.35,
                "Capture des mouvements d'expansion sur ATOM-USDC et TIA-USDC.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "atom_ibc_relayer_arb",
                "Cross-Zone IBC Packet Dislocation Arb",
                "IBC_CROSS_ZONE_ARB",
                "Osmosis / Astroport",
                0.20,
                "Arbitrage des écarts de prix entre zones Cosmos lors des vagues de trafic IBC.",
            ),
        ],
        "leaf-binance-cex" => vec![
            spec(
                PodId::PodCarry,
                "cex_perp_funding_harvester",
                "Binance Multi-Asset Spot-Perp Funding Carry",
                "CEX_DELTA_NEUTRAL_CARRY",
                "Binance Perp / Spot",
                0.40,
                "Moissonnage delta-neutre des taux de funding perpétuels CEX en Post-Only Maker.",
            ),
            spec(
                PodId::PodMomentum,
                "cex_l2_obi_breakout",
                "Binance L2 Orderbook Imbalance & CVD Pod",
                "CEX_ORDERFLOW_MOMENTUM",
                "Binance Spot / Perp",
                0.35,
                "Exécution Post-Only Maker (1.8 bps) sur déséquilibre du carnet L2 et cassure ATR.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "cex_cross_pair_stat_arb",
                "CEX Cross-Margin Basis & Liquidation Reversion",
                "STAT_ARB_REVERSION",
                "Binance Cross-Margin",
                0.25,
                "Capture des mèches de liquidation et retour à la moyenne sur le carnet central.",
            ),
        ],
        "leaf-paper-sandbox" => vec![
            spec(
                PodId::PodCarry,
                "paper_sim_carry",
                "Sandbox Simulated Funding Carry Pod",
                "PAPER_CARRY",
                "Paper Engine Simulator",
                0.35,
                "Validation sans risque réel des stratégies de portage delta-neutre.",
            ),
            spec(
                PodId::PodMomentum,
                "paper_sim_momentum",
                "Sandbox Adverse-Selection & OBI Pod",
                "PAPER_MOMENTUM",
                "Paper Engine Simulator",
                0.35,
                "Test de robustesse des signaux Ichimoku/Fibonacci/OBI avec modèle de sélection adverse.",
            ),
            spec(
                PodId::PodOnchainAlpha,
                "paper_sim_whale_alpha",
                "Sandbox Smart-Money Replay Pod",
                "PAPER_ONCHAIN_ALPHA",
                "Paper Engine Simulator",
                0.20,
                "Simulation de copie de flux on-chain sur données réelles.",
            ),
            spec(
                PodId::PodSniper,
                "paper_sim_sniper",
                "Sandbox Anti-Rug & Pool Sniper Pod",
                "PAPER_SNIPER",
                "Paper Engine Simulator",
                0.10,
                "Banc d'essai des filtres de sécurité HardRiskGate sur nouveaux pools.",
            ),
        ],
        _ => {
            // Specialized P2/P3 ecosystems (Aptos, Chainlink, Stacks, NEAR, Cardano, Polkadot,
            // Dogecoin, ICP, Canton, Celo, Tezos, Flow, EOS): 3 tailored Rust pods (<= 4 max).
            let slug = leaf_id.trim_start_matches("leaf-");
            vec![
                spec(
                    PodId::PodCarry,
                    &format!("{slug}_staking_yield_carry"),
                    &format!("{} Native Staking & Basis Carry", slug.to_uppercase()),
                    "ECOSYSTEM_YIELD_CARRY",
                    &format!("{} Native DeFi", slug.to_uppercase()),
                    0.45,
                    &format!("Capture du rendement natif et du basis sur l'écosystème {}.", slug.to_uppercase()),
                ),
                spec(
                    PodId::PodMomentum,
                    &format!("{slug}_dex_obi_momentum"),
                    &format!("{} Native DEX Orderflow Momentum", slug.to_uppercase()),
                    "ECOSYSTEM_ORDERFLOW_MOMENTUM",
                    &format!("{} Primary DEX", slug.to_uppercase()),
                    0.35,
                    &format!("Breakout de volatilité et déséquilibre de carnet sur {}.", slug.to_uppercase()),
                ),
                spec(
                    PodId::PodOnchainAlpha,
                    &format!("{slug}_onchain_catalyst_alpha"),
                    &format!("{} On-Chain Whale & Catalyst Pod", slug.to_uppercase()),
                    "ECOSYSTEM_ONCHAIN_ALPHA",
                    &format!("{} L1 RPC / Pools", slug.to_uppercase()),
                    0.20,
                    &format!("Détection de flux on-chain et catalyseurs propres à la blockchain {}.", slug.to_uppercase()),
                ),
            ]
        }
    };
    specs.truncate(MAX_PODS_PER_BLOCKCHAIN);
    specs
}

/// Instantiates the executable Rust `StrategyPod` objects (max 4) adapted to `leaf_id`.
pub fn strategy_pods_for_leaf(leaf_id: &str) -> Vec<Box<dyn StrategyPod>> {
    if leaf_id == "leaf-solana" {
        return default_strategy_pods();
    }

    let specs = ecosystem_pod_specs(leaf_id);
    let mut pods: Vec<Box<dyn StrategyPod>> = Vec::with_capacity(specs.len());

    for s in specs.into_iter().take(MAX_PODS_PER_BLOCKCHAIN) {
        let (inner, target_venue): (Box<dyn StrategyPod>, Venue) = match s.slot_id {
            PodId::PodCarry => (
                Box::new(CarryPod {
                    default_min_funding_apr: 0.10,
                }),
                if leaf_id == "leaf-hyperliquid" {
                    Venue::HyperliquidPerp
                } else {
                    Venue::BinancePerp
                },
            ),
            PodId::PodMomentum => (
                Box::new(MomentumPod {
                    obi_threshold: 0.18,
                    min_breakout_zscore: 1.65,
                }),
                if leaf_id == "leaf-binance-cex" {
                    Venue::BinanceSpot
                } else {
                    Venue::HyperliquidPerp
                },
            ),
            PodId::PodOnchainAlpha => (
                Box::new(OnChainAlphaPod {
                    min_whale_winrate: 0.62,
                    min_buy_volume_usd: 12_000.0,
                }),
                Venue::OnchainDexAggregator,
            ),
            PodId::PodSniper => (
                Box::new(DexSniperPod {
                    min_initial_liquidity_usd: 20_000.0,
                }),
                Venue::OnchainAtomicPool,
            ),
        };

        pods.push(Box::new(EcosystemAdaptedPod {
            spec: s,
            target_venue,
            inner,
        }));
    }

    pods
}

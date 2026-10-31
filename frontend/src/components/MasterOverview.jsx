import React, { useState } from 'react';
import {
  Wallet,
  ArrowDownCircle,
  ArrowUpRight,
  ShieldCheck,
  Cpu,
  Globe,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  ScrollText,
  Layers,
  Rss,
} from 'lucide-react';
import LLMInspectionModal from './LLMInspectionModal';
import SourceBadge from './SourceBadge';
import { formatMetric, formatOperational } from '../lib/provenance';

const CHAIN_TOKENS = {
  Solana: ['SOL', 'USDC', 'USDT', 'JUP', 'RAY'],
  Bitcoin: ['BTC', 'USDT'],
  Ethereum: ['ETH', 'USDC', 'USDT', 'LINK'],
  Sui: ['SUI', 'USDC'],
  Hyperliquid: ['HYPE', 'USDC'],
  'BNB Chain': ['BNB', 'USDT'],
  'XRP Ledger': ['XRP', 'USDC'],
  TON: ['TON', 'USDT'],
  TRON: ['TRX', 'USDT'],
  Avalanche: ['AVAX', 'USDC'],
  'Cosmos IBC': ['ATOM', 'USDC'],
  Aptos: ['APT', 'USDC'],
  Chainlink: ['LINK', 'USDC'],
  Stacks: ['STX', 'BTC'],
  NEAR: ['NEAR', 'USDC'],
  Cardano: ['ADA', 'USDC'],
  Polkadot: ['DOT', 'USDC'],
  Dogecoin: ['DOGE', 'USDT'],
  'Internet Computer': ['ICP', 'USDC'],
  'Canton Network': ['CC', 'USDC'],
  Celo: ['CELO', 'USDC'],
  Tezos: ['XTZ', 'USDC'],
  Flow: ['FLOW', 'USDC'],
  'EOS (Vaulta)': ['EOS', 'USDT'],
  'Binance CEX Multi-Pair': ['USDT', 'BTC', 'ETH', 'SOL', 'BNB'],
  'Paper Sandbox': ['USDC', 'USDT'],
};

const POSTURE_BADGES = {
  AGGRESSIVE: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  BALANCED: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  DEFENSIVE: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  HIBERNATION: 'bg-gray-700/40 text-gray-400 border-gray-600/40',
};

const MasterOverview = ({ statusData, apiBase, onRefresh, onSelectLeaf }) => {
  const hierarchy = statusData?.hierarchy || {};
  const master = hierarchy.master_orchestrator || {};
  // No local fallback portfolio: an absent treasury renders as an em dash.
  const treasury = hierarchy.treasury || {};
  const leaves = hierarchy.leaves || [];
  const openrouterCredit =
    hierarchy.openrouter_credit || statusData?.cost_guard?.openrouter_credit || {};
  const macroRss = hierarchy.macro_rss?.items || [];
  const checkoutHistory = hierarchy.checkout_history || [];
  const bridgeHistory = hierarchy.bridge_evaluations || [];

  // 1. Deposit state
  const [depositAmount, setDepositAmount] = useState('5000');
  const [depositToken, setDepositToken] = useState('USDC');
  const [depositChain, setDepositChain] = useState('Solana');
  const [depositFeedback, setDepositFeedback] = useState(null);
  const [depositing, setDepositing] = useState(false);

  // 2. Checkout state
  const [checkoutAmount, setCheckoutAmount] = useState('1500');
  const [checkoutChain, setCheckoutChain] = useState('Solana');
  const [checkoutToken, setCheckoutToken] = useState('SOL');
  const [checkoutAddress, setCheckoutAddress] = useState('');
  const [checkoutQuote, setCheckoutQuote] = useState(null);
  const [checkingOut, setCheckingOut] = useState(false);

  // 3. Bridge calculator & Master LLM state
  const [bridgeFrom, setBridgeFrom] = useState('Solana');
  const [bridgeTo, setBridgeTo] = useState('Ethereum');
  const [bridgeAmt, setBridgeAmt] = useState('4000');
  const [bridgeExpectedBps, setBridgeExpectedBps] = useState('95');
  const [bridgeEvalResult, setBridgeEvalResult] = useState(null);
  const [masterReflecting, setMasterReflecting] = useState(false);
  const [togglingScheduler, setTogglingScheduler] = useState(false);
  const [refillingOr, setRefillingOr] = useState(false);
  const [showLLMModal, setShowLLMModal] = useState(false);
  const [llmModalAgentFilter, setLlmModalAgentFilter] = useState('MasterOrchestrator/MacroLoop');
  const [tierFilter, setTierFilter] = useState('ALL');
  const masterDrawers = master.palace_drawers || [];
  const autoSchedulerEnabled = Boolean(
    statusData?.cost_guard?.auto_scheduler_enabled ??
      statusData?.cognitive_engine?.auto_scheduler_enabled ??
      false
  );

  const handleDeposit = async (e) => {
    e.preventDefault();
    const val = parseFloat(depositAmount);
    if (!val || val <= 0) return;
    setDepositing(true);
    setDepositFeedback(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/treasury/deposit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount_usd: val,
          token: depositToken,
          source_chain: depositChain,
          note: 'Dépôt opérateur via accueil Orchestrateur',
        }),
      });
      const data = await res.json();
      setDepositFeedback(data);
      if (onRefresh) await onRefresh();
    } catch (err) {
      setDepositFeedback({ status: 'error', message: String(err) });
    } finally {
      setDepositing(false);
    }
  };

  const handleCheckout = async (quoteOnly = false) => {
    const val = parseFloat(checkoutAmount);
    if (!val || val <= 0) return;
    setCheckingOut(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/treasury/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount_usd: val,
          target_chain: checkoutChain,
          target_token: checkoutToken,
          destination_address: checkoutAddress,
          quote_only: quoteOnly,
        }),
      });
      const data = await res.json();
      setCheckoutQuote(data);
      if (!quoteOnly && onRefresh) await onRefresh();
    } catch (err) {
      setCheckoutQuote({ status: 'error', message: String(err) });
    } finally {
      setCheckingOut(false);
    }
  };

  const handleEvaluateBridge = async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/treasury/evaluate-bridge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from_chain: bridgeFrom,
          to_chain: bridgeTo,
          amount_usd: parseFloat(bridgeAmt) || 2500,
          expected_yield_bps: parseFloat(bridgeExpectedBps) || 80,
          horizon_days: 7,
        }),
      });
      const data = await res.json();
      setBridgeEvalResult(data);
    } catch {
      // ignore
    }
  };

  const handleMasterReflect = async () => {
    setMasterReflecting(true);
    try {
      await fetch(`${apiBase}/api/v1/master/reflect`, { method: 'POST' });
      if (onRefresh) await onRefresh();
    } finally {
      setMasterReflecting(false);
    }
  };

  const handleToggleAutoScheduler = async () => {
    setTogglingScheduler(true);
    try {
      await fetch(`${apiBase}/api/v1/cognitive/scheduler`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !autoSchedulerEnabled }),
      });
      if (onRefresh) await onRefresh();
    } finally {
      setTogglingScheduler(false);
    }
  };

  const handleOpenRouterRefill = async () => {
    setRefillingOr(true);
    try {
      await fetch(`${apiBase}/api/v1/openrouter/refill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_usd: 15.0, force: true }),
      });
      if (onRefresh) await onRefresh();
    } finally {
      setRefillingOr(false);
    }
  };

  const handleLiquidateLeaf = async (leafId, leafName) => {
    try {
      await fetch(`${apiBase}/api/v1/leaf/${leafId}/liquidate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason: `Liquidation d'urgence vers Dry Powder déclenchée depuis l'Orchestrateur (${leafName})`,
        }),
      });
      if (onRefresh) await onRefresh();
    } catch {
      // ignore
    }
  };

  const handlePostureChange = async (leafId, riskPosture) => {
    try {
      await fetch(`${apiBase}/api/v1/leaf/${leafId}/mandate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ risk_posture: riskPosture }),
      });
      if (onRefresh) await onRefresh();
    } catch {
      // ignore
    }
  };

  const availableTokensForCheckout = CHAIN_TOKENS[checkoutChain] || ['USDC', 'USDT'];
  const filteredLeaves = leaves.filter((lf) =>
    tierFilter === 'ALL'
      ? true
      : tierFilter === 'DEPLOYED'
        ? Number(lf.allocated_capital_usd || 0) > 0
        : lf.tier === tierFilter
  );

  return (
    <div className="space-y-6">
      {/* Top Executive Summary Banner */}
      <div className="bg-gradient-to-r from-gray-900 via-indigo-950/40 to-gray-900 p-5 rounded-xl border border-indigo-500/30 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                Chef d&apos;Orchestre Maître
              </span>
              <span className="px-2.5 py-0.5 text-[11px] font-mono rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                LLM : {master.model || 'moonshotai/kimi-k3.1-pro'}
              </span>
              <span className="px-2.5 py-0.5 text-[11px] font-mono rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Sous-Agents : deepseek/deepseek-v4.1-flash-1017
              </span>
            </div>
            <h2 className="text-xl font-bold text-white mt-2">
              Portefeuille Maître Multi-Écosystèmes &amp; Allocation Stratégique Long Terme
            </h2>
            <p className="text-xs text-gray-300 mt-1 max-w-3xl">
              {master.long_term_strategy ||
                "Concentration du capital sur les écosystèmes à haute vélocité (Solana, Bitcoin, Ethereum, Hyperliquid, Sui) tout en préservant au moins 20% de réserve liquide (Dry Powder) pour absorber les chocs macro et financer les opportunités à fort levier."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleToggleAutoScheduler}
              disabled={togglingScheduler}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold border transition ${
                autoSchedulerEnabled
                  ? 'bg-emerald-950/70 hover:bg-emerald-900/70 text-emerald-300 border-emerald-500/40'
                  : 'bg-amber-950/70 hover:bg-amber-900/70 text-amber-300 border-amber-500/40'
              }`}
              title="Active ou met en pause les réveils périodiques automatiques LLM en arrière-plan (15m feuilles / 1h maître)"
            >
              <Cpu className="w-3.5 h-3.5" />
              {autoSchedulerEnabled
                ? 'Auto-Scheduler LLM : ACTIF (15m / 1h)'
                : 'Auto-Scheduler LLM : PAUSE ($0.00/h)'}
            </button>
            <button
              type="button"
              onClick={handleMasterReflect}
              disabled={masterReflecting}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow transition disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {masterReflecting
                ? 'Réflexion Kimi K3.1 Pro...'
                : 'Réflexion Stratégique Maître (Kimi K3.1 Pro)'}
            </button>
            <button
              type="button"
              onClick={() => {
                setLlmModalAgentFilter('MasterOrchestrator/MacroLoop');
                setShowLLMModal(true);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-purple-950/60 hover:bg-purple-900/70 text-purple-200 border border-purple-500/40 text-xs font-semibold transition"
            >
              <ScrollText className="w-3.5 h-3.5 text-purple-300" />
              Transcripts Orchestrateur
            </button>
            <button
              type="button"
              onClick={() => {
                setLlmModalAgentFilter('');
                setShowLLMModal(true);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs transition"
            >
              <ScrollText className="w-3.5 h-3.5 text-gray-400" />
              Tous les Transcripts
            </button>
          </div>
        </div>

        {/* 4 Key Treasury & OpenRouter Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4 pt-4 border-t border-gray-800/80">
          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-gray-800">
            <div className="text-[11px] uppercase tracking-wider text-gray-400">
              Capital Total Maître
            </div>
            <div className="text-2xl font-bold text-white mt-0.5">
              {formatOperational(treasury.total_capital_usd, 'money')}
            </div>
            <div className="text-[11px] text-emerald-400 mt-0.5 flex items-center gap-1.5">
              PnL Global Flotte :{' '}
              {formatMetric(
                treasury.total_realized_pnl_usd,
                treasury.source,
                'signedMoney'
              )}
              <SourceBadge source={treasury.source} />
            </div>
          </div>

          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-gray-800">
            <div className="text-[11px] uppercase tracking-wider text-gray-400">
              Capital Déployé ({formatOperational(treasury.active_leaves_count, 'integer')} Robots
              actifs)
            </div>
            <div className="text-2xl font-bold text-blue-300 mt-0.5">
              {formatOperational(treasury.deployed_capital_usd, 'money')}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">
              {treasury.dry_powder_ratio === null || treasury.dry_powder_ratio === undefined
                ? '— du portefeuille en travail'
                : `${((1 - Number(treasury.dry_powder_ratio)) * 100).toFixed(1)}% du portefeuille en travail`}
            </div>
          </div>

          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-emerald-500/30">
            <div className="text-[11px] uppercase tracking-wider text-emerald-300 flex items-center justify-between">
              <span>Réserve « Dry Powder » (Au Frais)</span>
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 mt-0.5">
              {formatOperational(treasury.dry_powder_usd, 'money')}
            </div>
            <div className="text-[11px] text-gray-300 mt-0.5">
              {formatOperational(
                treasury.dry_powder_ratio === null || treasury.dry_powder_ratio === undefined
                  ? null
                  : Number(treasury.dry_powder_ratio) * 100,
                'rate'
              )}{' '}
              disponible (Plancher sécurité :{' '}
              {formatOperational(Number(treasury.min_dry_powder_ratio ?? 0.2) * 100, 'rate')})
            </div>
          </div>

          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-purple-500/30">
            <div className="flex items-center justify-between text-[11px] uppercase tracking-wider text-purple-300">
              <span>Crédits Cognitifs OpenRouter</span>
              <button
                type="button"
                onClick={handleOpenRouterRefill}
                disabled={refillingOr}
                className="px-2 py-0.5 rounded bg-purple-600/30 hover:bg-purple-600/50 text-purple-200 border border-purple-500/40 text-[10px] font-semibold transition"
              >
                {refillingOr ? 'Recharge...' : '+ Recharger ($15)'}
              </button>
            </div>
            <div className="text-2xl font-bold text-purple-300 mt-0.5">
              {formatOperational(openrouterCredit.credit_balance_usd, 'money')}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">
              Auto-Refill avant épuisement (&lt;
              {formatOperational(openrouterCredit.low_watermark_usd, 'money')}) • Cap{' '}
              {((openrouterCredit.max_profit_share_pct ?? 0.1) * 100).toFixed(0)}% PnL
            </div>
          </div>
        </div>
      </div>

      {/* PILLARS 1 & 2: Confier des fonds (Deposit) & Récupérer des fonds (Multi-Chain Checkout) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 1. Confier des fonds à l'Orchestrateur */}
        <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <ArrowDownCircle className="w-4 h-4 text-emerald-400" />
                1. Confier des Capitaux à l&apos;Orchestrateur
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Répartition intelligente automatique selon la taille du capital et le plancher Dry Powder (22%)
              </p>
            </div>
          </div>

          <form onSubmit={handleDeposit} className="space-y-3 text-xs">
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-gray-400 mb-1">Montant (USD equiv.)</label>
                <input
                  type="number"
                  min="10"
                  step="any"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-700 rounded px-2.5 py-1.5 text-white font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Token déposé</label>
                <select
                  value={depositToken}
                  onChange={(e) => setDepositToken(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-700 rounded px-2.5 py-1.5 text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="USDC">USDC</option>
                  <option value="USDT">USDT</option>
                  <option value="SOL">SOL</option>
                  <option value="BTC">BTC</option>
                  <option value="ETH">ETH</option>
                </select>
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Réseau source</label>
                <select
                  value={depositChain}
                  onChange={(e) => setDepositChain(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-700 rounded px-2.5 py-1.5 text-white focus:outline-none focus:border-emerald-500"
                >
                  {Object.keys(CHAIN_TOKENS).map((ch) => (
                    <option key={ch} value={ch}>
                      {ch}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={depositing}
              className="w-full py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition disabled:opacity-50"
            >
              {depositing
                ? 'Allocation intelligente en cours...'
                : `Confier $${Number(depositAmount || 0).toLocaleString()} (${depositToken}) à l'Orchestrateur`}
            </button>
          </form>

          {depositFeedback && depositFeedback.status === 'completed' && (
            <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/40 text-xs space-y-1">
              <div className="font-semibold text-emerald-300">
                ✅ Dépôt de ${depositFeedback.deposited_usd?.toLocaleString()} réparti avec succès (Palier :{' '}
                {depositFeedback.sizing_tier})
              </div>
              <div className="text-gray-300">
                • Conservé au frais (Dry Powder) :{' '}
                <strong className="text-white">${depositFeedback.reserved_dry_powder_usd}</strong> | Déployé :{' '}
                <strong className="text-emerald-300">${depositFeedback.deployed_usd}</strong>
              </div>
            </div>
          )}
        </div>

        {/* 2. Demander un Checkout multi-chaîne / multi-token */}
        <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <ArrowUpRight className="w-4 h-4 text-blue-400" />
                2. Récupérer des Fonds (« Checkout » Multi-Chaîne &amp; Token)
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                L&apos;Orchestrateur puise dans le Dry Powder (ou désalloue), route et livre dans le token demandé
              </p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-gray-400 mb-1">Montant (USD)</label>
                <input
                  type="number"
                  min="10"
                  step="any"
                  value={checkoutAmount}
                  onChange={(e) => setCheckoutAmount(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-700 rounded px-2.5 py-1.5 text-white font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Blockchain cible</label>
                <select
                  value={checkoutChain}
                  onChange={(e) => {
                    const nextChain = e.target.value;
                    setCheckoutChain(nextChain);
                    const toks = CHAIN_TOKENS[nextChain] || ['USDC'];
                    setCheckoutToken(toks[0]);
                  }}
                  className="w-full bg-gray-950 border border-gray-700 rounded px-2.5 py-1.5 text-white focus:outline-none focus:border-blue-500"
                >
                  {Object.keys(CHAIN_TOKENS).map((ch) => (
                    <option key={ch} value={ch}>
                      {ch}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Token souhaité</label>
                <select
                  value={checkoutToken}
                  onChange={(e) => setCheckoutToken(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-700 rounded px-2.5 py-1.5 text-white font-mono focus:outline-none focus:border-blue-500"
                >
                  {availableTokensForCheckout.map((tk) => (
                    <option key={tk} value={tk}>
                      {tk}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleCheckout(true)}
                disabled={checkingOut}
                className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 font-medium transition"
              >
                Simuler Frais &amp; Route
              </button>
              <button
                type="button"
                onClick={() => handleCheckout(false)}
                disabled={checkingOut}
                className="flex-1 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition disabled:opacity-50"
              >
                {checkingOut
                  ? 'Routage cross-chain en cours...'
                  : `Exécuter Checkout ($${Number(checkoutAmount || 0).toLocaleString()} → ${checkoutToken} sur ${checkoutChain})`}
              </button>
            </div>
          </div>

          {checkoutQuote && (
            <div
              className={`p-3 rounded-lg border text-xs space-y-1 ${
                checkoutQuote.status === 'error'
                  ? 'bg-red-950/30 border-red-500/40 text-red-200'
                  : 'bg-blue-950/30 border-blue-500/40 text-blue-100'
              }`}
            >
              {checkoutQuote.status === 'error' ? (
                <div>❌ {checkoutQuote.message}</div>
              ) : (
                <>
                  <div className="font-semibold flex items-center justify-between">
                    <span>
                      {checkoutQuote.status === 'quoted' ? '📋 Devis Checkout' : '✅ Checkout Livré'} :{' '}
                      <strong className="text-emerald-300">
                        {checkoutQuote.delivered_token_qty} {checkoutQuote.target_token}
                      </strong>{' '}
                      (${checkoutQuote.net_delivered_usd} net)
                    </span>
                    <span className="font-mono text-[11px] text-gray-300">
                      Pont : {checkoutQuote.bridge_quote?.bridge_protocol}
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-300">
                    Frais totaux (Gas + Bridge + Swap DEX) : ${checkoutQuote.total_fee_usd} (
                    {checkoutQuote.bridge_quote?.total_cost_bps} bps) • Finalité estimée :{' '}
                    {checkoutQuote.bridge_quote?.estimated_finality_sec}s
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* PILLAR 3: Répartition actuelle du Portefeuille & Gouvernance des 26 Agents Feuilles */}
      <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-800 pb-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-400" />
              3. Répartition du Portefeuille Maître par Branche Blockchain &amp; Contrôle du Risque
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Chaque robot feuille ne regarde et ne trade QUE son écosystème. L&apos;Orchestrateur peut modifier sa
              posture ou liquider ses positions vers le Dry Powder en 1 clic.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            {[
              { id: 'ALL', label: `Tous (${leaves.length})` },
              { id: 'DEPLOYED', label: 'Capital Déployé' },
              { id: 'P0_CORE', label: 'P0 Core' },
              { id: 'P1_MAJOR', label: 'P1 Majeurs' },
              { id: 'P2_SPECIALIZED', label: 'P2 Spécialisés' },
              { id: 'P3_WATCH', label: 'P3 Veille' },
              { id: 'VENUE_MULTI', label: 'CEX / Paper' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setTierFilter(tab.id)}
                className={`px-2.5 py-1 rounded border transition ${
                  tierFilter === tab.id
                    ? 'bg-purple-600/30 border-purple-400 text-purple-200 font-semibold'
                    : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 uppercase text-[10px]">
                <th className="py-2 pr-3">Branche / Écosystème</th>
                <th className="py-2 px-3">Actifs Exclusifs</th>
                <th className="py-2 px-3 text-right">Capital Alloué</th>
                <th className="py-2 px-3 text-right">Poids</th>
                <th className="py-2 px-3">Posture (Mandat)</th>
                <th className="py-2 px-3 text-right">PnL / Sharpe</th>
                <th className="py-2 pl-3 text-right">Actions Orchestrateur</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/70">
              {filteredLeaves.map((lf) => {
                const livePerf = lf.performance?.live_testnet || {};
                const pnl = livePerf.realized_pnl_usd;
                return (
                <tr key={lf.id} className="hover:bg-gray-800/40 transition">
                  <td className="py-2.5 pr-3">
                    <button
                      type="button"
                      onClick={() => onSelectLeaf && onSelectLeaf(lf.id)}
                      className="text-left group"
                    >
                      <div className="font-bold text-white group-hover:text-blue-400 transition flex items-center gap-1.5">
                        <span>{lf.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 font-mono">
                          {lf.symbol}
                        </span>
                        {lf.execution_mode === 'ACTIVE_SOLANA' || lf.id === 'leaf-solana' ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-mono font-semibold">
                            ACTIVE_SOLANA
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono font-semibold">
                            PASSIVE_CATALOG
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-gray-400">
                        {lf.tier} • MemPalace: <code>{lf.mempalace_wing}</code>
                      </div>
                    </button>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-gray-300">
                    {(lf.exclusive_assets || []).join(', ')}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono font-semibold text-white">
                    ${Number(lf.allocated_capital_usd || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-gray-300">
                    {Number(lf.weight_pct || 0).toFixed(1)}%
                  </td>
                  <td className="py-2.5 px-3">
                    <select
                      value={lf.risk_posture || 'BALANCED'}
                      onChange={(e) => handlePostureChange(lf.id, e.target.value)}
                      className={`px-2 py-1 rounded border text-[11px] font-semibold focus:outline-none ${
                        POSTURE_BADGES[lf.risk_posture] || POSTURE_BADGES.BALANCED
                      }`}
                    >
                      <option value="AGGRESSIVE">AGGRESSIVE</option>
                      <option value="BALANCED">BALANCED</option>
                      <option value="DEFENSIVE">DEFENSIVE</option>
                      <option value="HIBERNATION">HIBERNATION</option>
                    </select>
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono">
                    <span
                      className={
                        typeof pnl === 'number'
                          ? pnl >= 0
                            ? 'text-emerald-400'
                            : 'text-red-400'
                          : 'text-gray-500'
                      }
                    >
                      {formatMetric(pnl, livePerf.source, 'signedMoney')}
                    </span>{' '}
                    <span className="text-gray-400 text-[11px]">
                      (SR {formatMetric(livePerf.sharpe_ratio, livePerf.source, 'number')})
                    </span>{' '}
                    <SourceBadge source={livePerf.source} />
                  </td>
                  <td className="py-2.5 pl-3 text-right space-x-1.5">
                    <button
                      type="button"
                      onClick={() => onSelectLeaf && onSelectLeaf(lf.id)}
                      className="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-blue-300 border border-gray-700 text-[11px] font-medium transition"
                    >
                      Ouvrir Onglet →
                    </button>
                    {Number(lf.allocated_capital_usd || 0) > 0 && (
                      <button
                        type="button"
                        onClick={() => handleLiquidateLeaf(lf.id, lf.name)}
                        className="px-2.5 py-1 rounded bg-red-600/20 hover:bg-red-600/40 text-red-300 border border-red-500/40 text-[11px] font-semibold transition"
                        title="Fermer immédiatement les positions et rapatrier le capital en Dry Powder"
                      >
                        Liquider → Dry Powder
                      </button>
                    )}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cross-Chain Bridge Hurdle Pricer & Macro Multi-Channel RSS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cross-Chain Transfer Viability Pricer */}
        <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Globe className="w-4 h-4 text-emerald-400" />
            Évaluateur de Coût &amp; Rentabilité des Transferts Inter-Blockchains (Hurdle 2.5x)
          </h3>
          <p className="text-xs text-gray-400">
            Avant tout déplacement de fonds d&apos;une blockchain à l&apos;autre, l&apos;Orchestrateur mesure les frais
            (Gas + Bridge + Slippage) et exige un alpha attendu &gt;= 2.5× le coût aller-retour.
          </p>

          <div className="grid grid-cols-4 gap-2 text-xs">
            <div>
              <label className="block text-gray-400 mb-1">De</label>
              <select
                value={bridgeFrom}
                onChange={(e) => setBridgeFrom(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-white"
              >
                {Object.keys(CHAIN_TOKENS).map((ch) => (
                  <option key={ch} value={ch}>
                    {ch}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-gray-400 mb-1">Vers</label>
              <select
                value={bridgeTo}
                onChange={(e) => setBridgeTo(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-white"
              >
                {Object.keys(CHAIN_TOKENS).map((ch) => (
                  <option key={ch} value={ch}>
                    {ch}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-gray-400 mb-1">Capital ($)</label>
              <input
                type="number"
                value={bridgeAmt}
                onChange={(e) => setBridgeAmt(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-white font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-400 mb-1">Alpha attendu (bps)</label>
              <input
                type="number"
                value={bridgeExpectedBps}
                onChange={(e) => setBridgeExpectedBps(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-white font-mono"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={handleEvaluateBridge}
            className="w-full py-1.5 rounded bg-gray-800 hover:bg-gray-700 border border-gray-700 text-xs font-semibold text-emerald-300 transition"
          >
            Calculer Frais de Pont &amp; Viabilité du Transfert
          </button>

          {bridgeEvalResult && (
            <div className="p-3 rounded bg-gray-950 border border-gray-800 text-xs space-y-1">
              <div className="flex items-center justify-between font-semibold">
                <span className={bridgeEvalResult.viable ? 'text-emerald-400' : 'text-amber-400'}>
                  {bridgeEvalResult.recommendation === 'APPROVE_TRANSFER'
                    ? '✅ Transfert Approuvé'
                    : '🛑 Transfert Rejeté (Coût > Hurdle)'}
                </span>
                <span className="font-mono text-gray-300">
                  Hurdle requis : {bridgeEvalResult.hurdle_rate_bps} bps (Aller-retour :{' '}
                  {bridgeEvalResult.round_trip_cost_bps} bps)
                </span>
              </div>
              <div className="text-gray-300">{bridgeEvalResult.rationale}</div>
            </div>
          )}
        </div>

        {/* Multi-Channel Macro RSS Feed */}
        <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Rss className="w-4 h-4 text-amber-400" />
            Canaux RSS Macro Multi-Sources (Signaux Haut-Niveau de l&apos;Orchestrateur)
          </h3>
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {macroRss.map((item, idx) => (
              <div
                key={idx}
                className="p-2.5 rounded bg-gray-950/70 border border-gray-800 text-xs flex items-start justify-between gap-2"
              >
                <div>
                  <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-semibold text-[10px] mr-2">
                    {item.source}
                  </span>
                  <span className="text-gray-200">{item.title}</span>
                </div>
                <span className="text-emerald-400 font-mono text-[10px] whitespace-nowrap">
                  {(Number(item.sentiment || 0.5) * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Master Orchestrator MemPalace Drawers (wing=master_orchestrator) & Cross-Wing Recall */}
      <div className="bg-gray-900 p-5 rounded-xl border border-indigo-500/30 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-400" />
              Journal de Réflexion MemPalace de l&apos;Orchestrateur Maître (<code>wing=master_orchestrator</code>)
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Historique des thèses macro long terme de l&apos;Orchestrateur et lecture transversale de tous les
              MemPalaces feuilles.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setLlmModalAgentFilter('MasterOrchestrator/MacroLoop');
              setShowLLMModal(true);
            }}
            className="px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-200 text-xs font-semibold flex items-center gap-1.5 transition"
          >
            <ScrollText className="w-3.5 h-3.5" />
            Voir les Prompts &amp; Completions Bruts de l&apos;Orchestrateur
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-indigo-300">
              Dernières Thèses de l&apos;Orchestrateur Maître ({masterDrawers.length})
            </div>
            {masterDrawers.slice(0, 3).map((drw) => (
              <div
                key={drw.drawer_id}
                className="p-3 rounded-lg bg-gray-950/80 border border-indigo-500/20 text-xs space-y-1"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-mono text-indigo-300 font-semibold flex items-center gap-1.5">
                    👑 {drw.model_used || 'no model call'} • {drw.thesis_continuity}
                    <SourceBadge source={drw.source} />
                  </span>
                  <span className="text-gray-400 font-mono">
                    {drw.timestamp_ms ? new Date(drw.timestamp_ms).toLocaleTimeString('fr-FR') : ''}
                  </span>
                </div>
                <div className="text-gray-200 font-medium">{drw.hypothesis}</div>
                {drw.panorama_summary && (
                  <div className="text-[11px] text-gray-400">Macro : {drw.panorama_summary}</div>
                )}
                {drw.invalidation_condition && (
                  <div className="text-[11px] text-amber-300/90">
                    Invalidation : {drw.invalidation_condition}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-purple-300">
              Synthèse Transversale des MemPalaces des Agents Feuilles (Cross-Wing Recall)
            </div>
            <pre className="text-[11px] font-mono whitespace-pre-wrap break-words bg-gray-950/90 text-gray-300 p-3 rounded-lg border border-gray-800 max-h-56 overflow-y-auto">
              {master.cross_wing_digest || 'Aucune synthèse inter-ailes disponible.'}
            </pre>
          </div>
        </div>
      </div>

      <LLMInspectionModal
        apiBase={apiBase}
        open={showLLMModal}
        onClose={() => setShowLLMModal(false)}
        initialAgentFilter={llmModalAgentFilter}
      />
    </div>
  );
};

export default MasterOverview;

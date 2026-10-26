import React, { useState } from 'react';
import {
  Activity,
  TrendingUp,
  DollarSign,
  Shield,
  Cpu,
  Zap,
  ScrollText,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import LLMInspectionModal from './LLMInspectionModal';
import SourceBadge from './SourceBadge';
import {
  POLICY_SANITY_CHECK_LABEL,
  formatMetric,
  formatOperational,
} from '../lib/provenance';

const POD_META = {
  pod_carry: {
    label: 'Pod 1 — Delta-Neutral Carry',
    desc: 'Funding Rate & Spot-Perp Basis Arbitrage',
  },
  pod_momentum: {
    label: 'Pod 2 — Intraday Orderflow & Vol',
    desc: 'L2 OBI + CVD + Volatility Breakout (Post-Only Maker)',
  },
  pod_onchain_alpha: {
    label: 'Pod 3 — On-Chain Smart-Money & Whale Alpha',
    desc: 'Whale Flow & Catalyst Swaps (DEX Aggregator + MEV Bundle)',
  },
  pod_sniper: {
    label: 'Pod 4 — DEX Atomic Sniper',
    desc: 'Raydium / Pump.fun Pool Launch (<5ms Rust + Jito)',
  },
};

const StatCard = ({ title, value, subtitle, icon: Icon, color, source }) => (
  <div className="bg-gray-900 p-4 rounded-lg shadow border border-gray-800">
    <div className="flex items-center justify-between mb-1 gap-2">
      <h3 className="text-gray-400 text-xs font-medium uppercase tracking-wider">{title}</h3>
      <div className="flex items-center gap-1.5">
        {source !== undefined && <SourceBadge source={source} />}
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
    </div>
    <p className="text-2xl font-bold text-white">{value}</p>
    {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
  </div>
);

const Dashboard = ({ statusData, apiBase = 'http://localhost:8000', onRefresh }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(8);
  const [reflecting, setReflecting] = useState(false);
  const [showLLMModal, setShowLLMModal] = useState(false);

  const metrics = statusData?.engine_metrics || {};
  const allocations = statusData?.policy_envelope?.pod_allocations || {};
  const assetOverrides = statusData?.policy_envelope?.asset_overrides || {};
  // Three declared populations — never blend them (see /api/v1/status contract).
  const bt = metrics.backtest_fixture || {};
  const paper = metrics.paper_model || {};
  const livePop = metrics.live_testnet || {};
  const paperRecent = paper.recent || {};
  const paperLifetime = paper.lifetime || {};
  const liveRecent = livePop.recent || {};
  const attribution = paper.pod_pnl_attribution || {};
  const executions = metrics.executions || [];
  const executionsSource = metrics.executions_source;
  // A missing executions_source is unattributed, never backtest_fixture.
  const executionRowSource =
    executionsSource === 'live_testnet'
      ? 'MEASURED'
      : executionsSource === 'paper_model'
        ? 'SIMULATED'
        : executionsSource === 'backtest_fixture'
          ? 'FIXTURE'
          : null;
  const catalysts = statusData?.catalysts || [];
  const costGuard = statusData?.cost_guard || {};
  const testnetTelemetry = statusData?.testnet_telemetry;
  const isTestnetMode = Boolean(testnetTelemetry?.enabled);
  const cognitive = statusData?.cognitive_engine || {};
  const taSnapshots = cognitive.ta_snapshots || {};
  const palaceDrawers = cognitive.palace_drawers || [];

  const totalExecutions = executions.length;
  const totalPages = Math.max(1, Math.ceil(totalExecutions / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalExecutions);
  const paginatedExecutions = executions.slice(startIndex, endIndex);

  const handlePageSizeChange = (e) => {
    const newSize = Number(e.target.value);
    setPageSize(newSize);
    setCurrentPage(1);
  };

  const handleTriggerReflection = async () => {
    setReflecting(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/cognitive/reflect`, { method: 'POST' });
      if (res.ok && onRefresh) {
        await onRefresh();
      }
    } catch {
      // Ignore error
    } finally {
      setReflecting(false);
    }
  };

  const handleCognitiveConfigChange = async (updates) => {
    try {
      const res = await fetch(`${apiBase}/api/v1/cognitive/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (res.ok && onRefresh) {
        await onRefresh();
      }
    } catch {
      // Ignore error
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
        <StatCard
          title="Equity Modèle Paper (cumul)"
          value={formatMetric(paper.final_equity_usd, paper.source, 'money')}
          subtitle={`PnL paper: ${formatMetric(paper.cumulative_pnl_usd, paper.source, 'signedMoney')} (${formatMetric(paper.total_return_pct, paper.source, 'percent')}) · Win rate ${formatMetric(paperRecent.win_rate_pct ?? paperRecent.positive_edge_share_pct, paper.source, 'rate')} (${formatMetric(paperRecent.wins, paper.source, 'integer')}G/${formatMetric(paperRecent.losses, paper.source, 'integer')}P sur ${formatMetric(paperRecent.trades, paper.source, 'integer')} · Vie: ${formatMetric(paperLifetime.trades ?? paperRecent.trades, paper.source, 'integer')} trades)`}
          icon={DollarSign}
          color="text-emerald-400"
          source={paper.source}
        />
        <StatCard
          title="Live Testnet (réel)"
          value={formatMetric(liveRecent.pnl_usd, livePop.source, 'signedMoney')}
          subtitle={`Win rate ${formatMetric(liveRecent.win_rate_pct, livePop.source, 'rate')} (${formatMetric(liveRecent.wins, livePop.source, 'integer')} gains / ${formatMetric(liveRecent.losses, livePop.source, 'integer')} pertes / ${formatMetric(liveRecent.flat, livePop.source, 'integer')} nuls) · PnL réalisé`}
          icon={Activity}
          color="text-cyan-400"
          source={livePop.source}
        />
        <StatCard
          title={POLICY_SANITY_CHECK_LABEL}
          value={formatMetric(bt.sharpe_ratio, bt.source, 'number')}
          subtitle={`FIXTURE · rule & plumbing check, not a fill simulation · declared-edge arithmetic · Win rate ${formatMetric(bt.win_rate_pct, bt.source, 'rate')} (${formatMetric(bt.trades, bt.source, 'integer')} trades) · Net ${formatMetric(bt.cumulative_pnl_usd, bt.source, 'signedMoney')}`}
          icon={TrendingUp}
          color="text-blue-400"
          source={bt.source}
        />
        <StatCard
          title="HardRiskGate (&lt;50µs)"
          value={`${formatMetric(bt.rejected_orders, bt.source, 'integer')} Rug Bloqué`}
          subtitle={`Policy sanity check · Max DD fixture: ${formatMetric(bt.max_drawdown_pct, bt.source, 'number')}% / Limite 3.0%`}
          icon={Shield}
          color="text-amber-400"
          source={bt.source}
        />
        <StatCard
          title="CostGuard &amp; Profondeur LLM"
          value={formatOperational(costGuard.total_spent_usd, 'cost')}
          subtitle={`Mode: ${costGuard.thinking_depth || 'DEEP_THESIS'} | Reste: ${formatOperational(costGuard.remaining_usd, 'cost')}/j`}
          icon={Cpu}
          color="text-purple-400"
        />
      </div>

      {/* Testnet / Devnet Real Wallet & Accounting Banner (ONLY displayed in Testnet/Devnet mode) */}
      {isTestnetMode && (
        <div className="bg-amber-950/20 p-4 rounded-lg border border-amber-500/30">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <h3 className="text-sm font-semibold text-amber-300 flex items-center gap-2">
              🧪 Mode Testnet / Devnet — Télémétrie Solana en lecture seule (SIMULATED) vs PnL Modèle (Paper)
            </h3>
            {testnetTelemetry.solana_address && (
              <a
                href={`https://solscan.io/account/${testnetTelemetry.solana_address}?cluster=${testnetTelemetry.solana_cluster || 'devnet'}`}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-400 hover:text-blue-300 underline font-mono"
              >
                Voir Wallet Solscan ({testnetTelemetry.solana_cluster}) ↗
              </a>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="bg-gray-900/90 p-3.5 rounded border border-gray-800">
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-white">Solana {testnetTelemetry.solana_cluster?.toUpperCase()} (lecture seule · SIMULATED)</span>
                <span className="font-mono text-emerald-400 font-bold">
                  {formatOperational(testnetTelemetry.solana_balance_sol, 'number')} SOL
                </span>
              </div>
              <p className="text-gray-400 text-[11px] leading-relaxed">
                Plus-value on-chain : non mesurée (pas de DEX Jupiter/Jito sur Devnet — actions simulées, non signées et non diffusées).
              </p>
              <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-800 text-[11px] text-gray-400">
                <span>
                  Actions simulées (non signées) :{' '}
                  <strong className="text-white">
                    {formatOperational(testnetTelemetry.solana_tx_count, 'integer')}
                  </strong>
                </span>
                <span className="text-amber-400">Aucune transaction diffusée</span>
              </div>
            </div>

            <div className="bg-gray-900/90 p-3.5 rounded border border-gray-800">
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-white">Binance Spot Testnet (Carnet L2 Réel)</span>
                <span className="font-mono text-emerald-400 font-bold">
                  {formatOperational(testnetTelemetry.binance_free_usdt, 'number')} USDT
                </span>
              </div>
              <p className="text-gray-400 text-[11px] leading-relaxed">
                Cycle mesuré <code className="text-gray-300">OPEN BUY</code> puis <code className="text-gray-300">CLOSE SELL</code> sur le carnet Spot Testnet.
              </p>
              <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-800 text-[11px] text-gray-400">
                <span>
                  Positions ouvertes :{' '}
                  <strong className="text-white">
                    {Object.keys(testnetTelemetry.binance_open_positions || {}).length > 0
                      ? Object.entries(testnetTelemetry.binance_open_positions)
                          .map(([sym, p]) => `${p.qty} ${sym} @ $${p.entry_price}`)
                          .join(', ')
                      : 'Aucune (Flat)'}
                  </strong>
                </span>
                <span
                  className={
                    typeof testnetTelemetry.binance_realized_pnl_usd === 'number'
                      ? testnetTelemetry.binance_realized_pnl_usd >= 0
                        ? 'text-emerald-400 font-semibold'
                        : 'text-red-400 font-semibold'
                      : 'text-gray-500 font-semibold'
                  }
                >
                  PnL Réel CEX :{' '}
                  {formatMetric(
                    testnetTelemetry.binance_realized_pnl_usd,
                    testnetTelemetry.source,
                    'signedMoney'
                  )}{' '}
                  USDT <SourceBadge source={testnetTelemetry.source} />
                </span>
              </div>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3 text-[11px]">
            <div className="bg-gray-900/90 px-3 py-2 rounded border border-gray-800">
              <div className="text-gray-500">
                PnL réalisé (fenêtre {formatMetric(liveRecent.trades, livePop.source, 'integer')})
              </div>
              <div className="font-mono font-bold text-sm text-gray-100">
                {formatMetric(liveRecent.pnl_usd, livePop.source, 'signedMoney')}
              </div>
            </div>
            <div className="bg-gray-900/90 px-3 py-2 rounded border border-gray-800">
              <div className="text-gray-500">Win rate réel (sur PnL réalisé)</div>
              <div className="font-mono font-bold text-sm text-gray-100">
                {formatMetric(liveRecent.win_rate_pct, livePop.source, 'rate')} ·{' '}
                {formatMetric(liveRecent.wins, livePop.source, 'integer')}/
                {formatMetric(liveRecent.trades, livePop.source, 'integer')}
              </div>
            </div>
            <div className="bg-gray-900/90 px-3 py-2 rounded border border-gray-800">
              <div className="text-gray-500">PnL paper cumulé (autre population)</div>
              <div className="font-mono font-bold text-sm text-amber-300">
                {formatMetric(paper.cumulative_pnl_usd, paper.source, 'signedMoney')}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4-Pod Allocation & Attribution Matrix */}
      <div className="bg-gray-900 p-5 rounded-lg border border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            Matrice des 4 Strategy Pods Rust (Allocation &amp; Attribution PnL)
          </h3>
          <span className="text-xs text-gray-400">
            TTL PolicyEnvelope : {statusData?.policy_envelope?.ttl_seconds || 900}s
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(POD_META).map(([podKey, meta]) => {
            const alloc = allocations[podKey] || { enabled: false, capital_weight: 0 };
            const pnl = attribution[podKey];
            return (
              <div
                key={podKey}
                className={`p-3.5 rounded-lg border ${
                  alloc.enabled
                    ? 'bg-gray-800/70 border-gray-700'
                    : 'bg-gray-900/40 border-gray-800 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white">{meta.label}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded font-medium ${
                      alloc.enabled
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-gray-700 text-gray-400'
                    }`}
                  >
                    {alloc.enabled ? `${Math.round(alloc.capital_weight * 100)}% Capital` : 'OFF'}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1">{meta.desc}</p>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-700/60 text-xs">
                  <span className="text-gray-400">
                    Biais : <strong className="text-gray-200">{alloc.directional_bias || 'NEUTRAL'}</strong>
                  </span>
                  <span
                    className={
                      typeof pnl === 'number'
                        ? pnl >= 0
                          ? 'text-emerald-400 font-semibold'
                          : 'text-red-400 font-semibold'
                        : 'text-gray-500 font-semibold'
                    }
                  >
                    {isTestnetMode ? 'PnL Modèle : ' : 'PnL : '}
                    {formatMetric(pnl, paper.source, 'signedMoney')}
                  </span>
                  <SourceBadge source={paper.source} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Execution Ledger */}
      <div className="bg-gray-900 p-5 rounded-lg border border-gray-800">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h3 className="text-base font-semibold text-white">
              {executionRowSource === 'MEASURED'
                ? 'Journal d’Exécution Live (Testnet / Devnet)'
                : executionRowSource === 'FIXTURE'
                  ? `${POLICY_SANITY_CHECK_LABEL} (engine-rs)`
                  : 'Journal d’Exécution (source non attribuée)'}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              {executionRowSource === 'MEASURED'
                ? `${totalExecutions > 0 ? `Affichage ${startIndex + 1}–${endIndex} sur ${totalExecutions} ordres` : 'Aucun ordre enregistré'} — colonne PnL : realized_pnl_usd`
                : executionRowSource === 'FIXTURE'
                  ? `${totalExecutions > 0 ? `Affichage ${startIndex + 1}–${endIndex} sur ${totalExecutions} lignes` : 'Aucune ligne enregistrée'} — fixture synthétique, arithmétique d’edge déclaré, pas une simulation de fill ni un journal de fills ; aucun ordre live`
                  : `${totalExecutions > 0 ? `Affichage ${startIndex + 1}–${endIndex} sur ${totalExecutions} ordres` : 'Aucun ordre enregistré'} — provenance absente, PnL non attribué`}
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-gray-400">
            <label htmlFor="exec-page-size" className="whitespace-nowrap">
              Lignes / page :
            </label>
            <select
              id="exec-page-size"
              value={pageSize}
              onChange={handlePageSizeChange}
              className="bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-2 py-1 focus:outline-none focus:border-emerald-500"
            >
              <option value={5}>5</option>
              <option value={8}>8</option>
              <option value={15}>15</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400">
                <th className="pb-2 pr-3">Date / Heure</th>
                <th className="pb-2 pr-3">Actif</th>
                <th className="pb-2 pr-3">Pod</th>
                <th className="pb-2 pr-3">Venue</th>
                <th className="pb-2 pr-3">Sens</th>
                <th className="pb-2 pr-3">Notional</th>
                <th className="pb-2 pr-3">
                  <span className="flex items-center gap-1.5">
                    {executionRowSource === 'FIXTURE'
                      ? 'PnL fixture (edge déclaré)'
                      : isTestnetMode
                        ? 'PnL Réel (vs Modèle Paper)'
                        : executionRowSource === 'MEASURED'
                          ? 'PnL Réalisé'
                          : 'PnL (source non attribuée)'}
                    <SourceBadge source={executionRowSource} />
                  </span>
                </th>
                <th className="pb-2">Signal Quant / Rationale</th>
              </tr>
            </thead>
            <tbody>
              {paginatedExecutions.map((ex, idx) => {
                const formattedDate = ex.timestamp_ms
                  ? new Date(Number(ex.timestamp_ms)).toLocaleString('fr-FR', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })
                  : '—';

                const isDevnetTx = isTestnetMode && ex.venue === 'SOLANA_DEVNET_ONCHAIN';
                const isBinanceTestnet = isTestnetMode && ex.venue === 'BINANCE_TESTNET_LIVE';
                const realPnl = ex.realized_pnl_usd;
                const simPnl = ex.simulated_pnl_usd ?? ex.realized_pnl_usd;
                const rowSource = ex.source ?? executionRowSource;

                return (
                  <tr key={`${ex.timestamp_ms || 'row'}-${startIndex + idx}`} className="border-b border-gray-800/60">
                    <td className="py-2 pr-3 font-mono text-[11px] text-gray-400 whitespace-nowrap">
                      {formattedDate}
                    </td>
                    <td className="py-2 pr-3 font-semibold text-white whitespace-nowrap">{ex.symbol}</td>
                    <td className="py-2 pr-3 text-blue-300 whitespace-nowrap">{ex.pod_id}</td>
                    <td className="py-2 pr-3 text-gray-400 whitespace-nowrap">{ex.venue}</td>
                    <td
                      className={`py-2 pr-3 font-bold ${
                        ex.side === 'BUY' ? 'text-emerald-400' : 'text-amber-400'
                      }`}
                    >
                      {ex.side}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">${Number(ex.notional_usd || 0).toFixed(0)}</td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {isDevnetTx ? (
                        <div className="flex flex-col">
                          <span className="text-gray-300 font-medium">
                            {formatMetric(realPnl, rowSource, 'number')} SOL{' '}
                            <span className="text-[10px] text-amber-400">(SIMULATED · non signé)</span>
                          </span>
                          <span
                            className={`text-[10px] ${
                              typeof simPnl === 'number' && simPnl >= 0
                                ? 'text-purple-300'
                                : 'text-red-400'
                            }`}
                          >
                            Modèle Paper : {formatMetric(simPnl, rowSource, 'signedMoney')}
                          </span>
                        </div>
                      ) : isBinanceTestnet ? (
                        <div className="flex flex-col">
                          {ex.pnl_type === 'TESTNET_OPEN_LONG' ? (
                            <span className="text-blue-300 font-medium">
                              Position ouverte ({formatMetric(0.0, rowSource, 'money')})
                            </span>
                          ) : ex.pnl_type === 'TESTNET_CLOSE_LONG' ? (
                            <span
                              className={
                                typeof realPnl === 'number' && realPnl >= 0
                                  ? 'text-emerald-400 font-semibold'
                                  : 'text-red-400 font-semibold'
                              }
                            >
                              Réel : {formatMetric(realPnl, rowSource, 'signedMoney')}
                            </span>
                          ) : (
                            <span className="text-gray-300 font-medium">Ordre exécuté (Spot)</span>
                          )}
                          <span
                            className={`text-[10px] ${
                              typeof simPnl === 'number' && simPnl >= 0
                                ? 'text-purple-300'
                                : 'text-red-400'
                            }`}
                          >
                            Modèle Paper : {formatMetric(simPnl, rowSource, 'signedMoney')}
                          </span>
                        </div>
                      ) : (
                        <span className="text-emerald-400 font-semibold">
                          {formatMetric(realPnl, rowSource, 'signedMoney')}
                        </span>
                      )}
                    </td>
                    <td className="py-2 text-gray-400">
                      <span>{ex.rationale}</span>
                      {isDevnetTx && !ex.is_simulated && ex.tx_signature && ex.tx_signature.length > 20 && (
                        <a
                          href={`https://solscan.io/tx/${ex.tx_signature}?cluster=${testnetTelemetry?.solana_cluster || 'devnet'}`}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-2 text-blue-400 hover:text-blue-300 underline font-mono text-[11px]"
                        >
                          [Solscan ↗]
                        </a>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex flex-wrap items-center justify-between gap-3 mt-4 pt-3 border-t border-gray-800 text-xs">
            <span className="text-gray-400">
              Page <strong className="text-white">{safePage}</strong> sur{' '}
              <strong className="text-white">{totalPages}</strong>
            </span>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setCurrentPage(1)}
                disabled={safePage <= 1}
                title="Première page"
                className="p-1.5 rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:pointer-events-none transition"
              >
                <ChevronsLeft className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, Math.min(p, totalPages) - 1))}
                disabled={safePage <= 1}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:pointer-events-none transition"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Précédent
              </button>

              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, Math.min(p, totalPages) + 1))}
                disabled={safePage >= totalPages}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:pointer-events-none transition"
              >
                Suivant
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setCurrentPage(totalPages)}
                disabled={safePage >= totalPages}
                title="Dernière page"
                className="p-1.5 rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:pointer-events-none transition"
              >
                <ChevronsRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Autonomous Cognitive Loop, Pro Technical Analysis (Ichimoku/Fib/RSI) & Strategy Palace */}
      <div className="bg-gray-900 p-5 rounded-lg border border-purple-500/30 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-800 pb-3">
          <div>
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-purple-400" />
              Cerveau Stratégique Warm-Path — Analyse Technique Pro &amp; Mémoire « Strategy Palace »
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Réveil auto-reprogrammable :{' '}
              <strong className="text-emerald-400">
                dans {cognitive.seconds_until_next_wakeup ?? 60}s
              </strong>{' '}
              — <span className="italic text-gray-300">{cognitive.wakeup_reason || 'Surveillance active'}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <select
              value={cognitive.active_model || 'deepseek/deepseek-v4.1-flash-1017'}
              onChange={(e) => handleCognitiveConfigChange({ preferred_model: e.target.value })}
              className="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-purple-500"
              title="Modèle Frontier Ultra-Low-Cost (Agent Feuille Solana)"
            >
              <option value="deepseek/deepseek-v4.1-flash-1017">
                DeepSeek v4.1 Flash 1017 ($0.028/M in • $0.080/M out)
              </option>
              <option value="deepseek/deepseek-v4.1-flash">
                DeepSeek v4.1 Flash ($0.028/M in • $0.080/M out)
              </option>
              <option value="z-ai/glm-5.3-flash">
                GLM 5.3 Flash ($0.048/M in • $0.160/M out)
              </option>
              <option value="qwen/qwen3.7-flash">
                Qwen 3.7 Flash ($0.030/M in • $0.130/M out)
              </option>
              <option value="z-ai/glm-5.3">
                GLM 5.3 Reasoning ($0.079/M in • $1.40/M out)
              </option>
            </select>

            <select
              value={cognitive.base_interval_sec || 120}
              onChange={(e) =>
                handleCognitiveConfigChange({ base_interval_sec: Number(e.target.value) })
              }
              className="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-purple-500"
              title="Période de réflexion de base"
            >
              <option value={60}>Période max : 60s</option>
              <option value={120}>Période max : 120s</option>
              <option value={300}>Période max : 300s (5m)</option>
              <option value={600}>Période max : 600s (10m)</option>
            </select>

            <button
              type="button"
              onClick={handleTriggerReflection}
              disabled={reflecting}
              className="px-3 py-1 rounded bg-purple-600 hover:bg-purple-500 text-white font-semibold disabled:opacity-50 transition"
            >
              {reflecting ? '⏳ Analyse TA & LLM...' : '⚡ Forcer Réflexion LLM'}
            </button>

            <button
              type="button"
              onClick={() => setShowLLMModal(true)}
              className="px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition"
              title="Inspecter la production LLM (transcripts bruts, latence, coût)"
            >
              <span className="flex items-center gap-1 text-xs">
                <ScrollText className="w-3.5 h-3.5 text-purple-400" />
                Inspection LLM
              </span>
            </button>
          </div>
        </div>

        {/* Solana Ecosystem Technical Analysis (Ichimoku, Fibonacci 0.618, RSI 14) & Compiled Rust Rules */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">
            Confluences Techniques Écosystème Solana 15m (SOL • JUP • RAY — Ichimoku • Fibonacci 0.618 • RSI 14)
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            {['SOL/USDT', 'JUP/USDT', 'RAY/USDT'].map((sym) => {
              const snap = taSnapshots[sym] || {};
              const ich = snap.ichimoku || {};
              const fib = snap.fibonacci || {};
              const rsi = snap.rsi || {};
              const rule = assetOverrides[sym.replace('/', '-')] || {};
              return (
                <div key={sym} className="bg-gray-800/60 p-3 rounded border border-gray-700/80 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white">{sym}</span>
                    <span className="font-mono text-emerald-400 font-semibold">
                      ${Number(snap.last_price || 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-300 space-y-0.5">
                    <div>
                      <span className="text-gray-400">Ichimoku :</span>{' '}
                      <strong className="text-blue-300">{ich.kumo_regime || 'N/A'}</strong> (Tenkan $
                      {ich.tenkan_sen ?? '—'} / Kijun ${ich.kijun_sen ?? '—'})
                    </div>
                    <div>
                      <span className="text-gray-400">Fibonacci 0.618 :</span>{' '}
                      <strong className="text-amber-300">${fib.golden_pocket_618 ?? '—'}</strong>{' '}
                      <span className="text-gray-400">
                        (Proche: {fib.nearest_level || '0.618'} à {fib.distance_to_nearest_bps ?? 0} bps)
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">RSI (14) :</span>{' '}
                      <strong
                        className={
                          Number(rsi.rsi_14 || 50) >= 70
                            ? 'text-red-400'
                            : Number(rsi.rsi_14 || 50) <= 35
                              ? 'text-emerald-400'
                              : 'text-gray-200'
                        }
                      >
                        {rsi.rsi_14 ?? 50}
                      </strong>{' '}
                      ({rsi.regime || 'NEUTRAL'}) | OBI L2: {snap.obi_l2 ?? 0}
                    </div>
                  </div>
                  <div className="pt-1.5 border-t border-gray-700/70 text-[10px] text-purple-300 font-mono">
                    Règle Rust : OBI &gt;= {rule.entry_obi_threshold ?? 0.08} | RSI &lt;={' '}
                    {rule.max_rsi_long ?? 70} | TP {rule.take_profit_bps ?? 45}bps / SL{' '}
                    {rule.stop_loss_bps ?? 28}bps
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Strategy Palace Memory Drawers */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">
            Mémoire Continue « Strategy Palace » (Continuité des Thèses &amp; Décisions Stratégiques)
          </h4>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {palaceDrawers.length === 0 ? (
              <p className="text-xs text-gray-500 italic">
                Initialisation du premier tiroir mémoire en cours...
              </p>
            ) : (
              palaceDrawers.slice(0, 6).map((drw) => {
                const ts = drw.timestamp_ms
                  ? new Date(Number(drw.timestamp_ms)).toLocaleString('fr-FR', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })
                  : '';
                return (
                  <div
                    key={drw.drawer_id}
                    className="p-3 rounded bg-gray-800/70 border border-gray-700/80 text-xs space-y-1"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] text-gray-400">{ts}</span>
                        <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold text-[10px]">
                          {drw.thesis_continuity}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-[10px]">
                          {drw.model_used || 'no model call'}
                        </span>
                        <SourceBadge source={drw.source} />
                        <span className="text-[10px] text-gray-400">
                          ({drw.thinking_depth} •{' '}
                          {formatMetric(drw.tokens_used, drw.source, 'integer')} tok •{' '}
                          {formatMetric(drw.cost_usd, drw.source, 'cost')})
                        </span>
                      </div>
                      <span className="text-[11px] text-emerald-400 font-medium">
                        Réveil programmé : {drw.next_wakeup_sec}s
                      </span>
                    </div>
                    <p className="text-gray-200">{drw.ta_confluence_notes}</p>
                    <p className="text-gray-400 text-[11px]">
                      <strong className="text-gray-300">Hypothèse :</strong> {drw.hypothesis} |{' '}
                      <strong className="text-amber-300">Invalidation :</strong>{' '}
                      {drw.invalidation_condition}
                    </p>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Warm-Path Catalyst & Solana Exclusive RSS Feed */}
      <div className="bg-gray-900 p-5 rounded-lg border border-gray-800 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            Flux RSS &amp; Catalyseurs Exclusifs Écosystème Solana (`leaf-solana`)
          </h3>
          <div className="space-y-2">
            {(statusData?.solana_rss?.items || []).map((rss, idx) => (
              <div
                key={`rss-${idx}`}
                className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded bg-purple-950/30 border border-purple-500/30 text-xs"
              >
                <div>
                  <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold mr-2">
                    RSS • {rss.source}
                  </span>
                  <span className="text-gray-200">{rss.title}</span>
                </div>
                <span className="text-emerald-400 font-mono text-[11px]">
                  Sentiment {(Number(rss.sentiment || 0.5) * 100).toFixed(0)}% ({rss.impact || 'HIGH'})
                </span>
              </div>
            ))}
            {catalysts.map((cat, idx) => (
              <div
                key={idx}
                className="flex flex-wrap items-center justify-between gap-2 p-3 rounded bg-gray-800/60 border border-gray-700/70 text-xs"
              >
                <div>
                  <span className="font-bold text-white mr-2">{cat.asset}</span>
                  <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 mr-2">
                    {cat.catalyst_type}
                  </span>
                  <span className="text-gray-300">{cat.summary}</span>
                </div>
                <span className="text-emerald-400 font-semibold">
                  Conviction {(Number(cat.conviction || 0) * 100).toFixed(0)}% ({cat.directional_bias})
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <LLMInspectionModal
        apiBase={apiBase}
        open={showLLMModal}
        onClose={() => setShowLLMModal(false)}
      />
    </div>
  );
};

export default Dashboard;

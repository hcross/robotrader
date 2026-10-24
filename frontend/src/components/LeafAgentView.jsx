import React, { useEffect, useState, useCallback } from 'react';
import {
  Cpu,
  Shield,
  Zap,
  Rss,
  Sparkles,
  ScrollText,
  AlertTriangle,
  ArrowLeft,
  Activity,
} from 'lucide-react';
import Dashboard from './Dashboard';
import LLMInspectionModal from './LLMInspectionModal';

const LeafAgentView = ({ leafId, statusData, apiBase, onRefresh, onBackToMaster }) => {
  const [leafDetail, setLeafDetail] = useState(null);
  const [reflecting, setReflecting] = useState(false);
  const [liquidating, setLiquidating] = useState(false);
  const [showLLMModal, setShowLLMModal] = useState(false);

  const hierarchyLeaves = statusData?.hierarchy?.leaves || [];
  const summaryLeaf = hierarchyLeaves.find((l) => l.id === leafId) || {};

  const fetchDetail = useCallback(async () => {
    if (!leafId) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/leaf/${leafId}`);
      if (res.ok) {
        const data = await res.json();
        setLeafDetail(data);
      }
    } catch {
      // ignore offline
    }
  }, [apiBase, leafId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail, statusData]);

  const leaf = leafDetail?.leaf || summaryLeaf;
  const rssItems = leafDetail?.rss_feed?.items || [];
  const drawers = leafDetail?.mempalace_drawers || [];

  const handleLeafReflect = async () => {
    setReflecting(true);
    try {
      await fetch(`${apiBase}/api/v1/leaf/${leafId}/reflect`, { method: 'POST' });
      await fetchDetail();
      if (onRefresh) await onRefresh();
    } finally {
      setReflecting(false);
    }
  };

  const handlePostureChange = async (newPosture) => {
    try {
      await fetch(`${apiBase}/api/v1/leaf/${leafId}/mandate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ risk_posture: newPosture }),
      });
      await fetchDetail();
      if (onRefresh) await onRefresh();
    } catch {
      // ignore
    }
  };

  const handleEmergencyLiquidate = async () => {
    setLiquidating(true);
    try {
      await fetch(`${apiBase}/api/v1/leaf/${leafId}/liquidate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason: `Liquidation d'urgence depuis l'onglet ${leaf.name || leafId}`,
        }),
      });
      await fetchDetail();
      if (onRefresh) await onRefresh();
    } finally {
      setLiquidating(false);
    }
  };

  if (leafId === 'leaf-solana') {
    return (
      <div className="space-y-6">
        <div className="bg-gradient-to-r from-purple-950/50 via-gray-900 to-emerald-950/40 p-4 rounded-xl border border-purple-500/40 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs">
              <button
                type="button"
                onClick={onBackToMaster}
                className="flex items-center gap-1 px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700"
              >
                <ArrowLeft className="w-3 h-3" /> Orchestrateur Maître
              </button>
              <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold">
                Branche Feuille P0 • Solana L1 &amp; DEX Exclusif
              </span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                Modèle : {leaf.model || 'deepseek/deepseek-v4.1-flash-1017'}
              </span>
              <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono">
                MemPalace : wing=leaf_solana
              </span>
            </div>
            <h2 className="text-lg font-bold text-white mt-1.5">
              ☀️ Robot Feuille Solana (`leaf-solana`) — Périmètre Purifié : SOL/USDT, JUP/USDT, RAY/USDT, SOL-DEVNET
            </h2>
            <p className="text-xs text-gray-300 mt-0.5">
              Aucun trading hors-Solana (BTC et ETH ont été intégralement retirés de cette branche et délégués à leurs
              robots feuilles dédiés). Capital alloué par l&apos;Orchestrateur :{' '}
              <strong className="text-emerald-400">
                ${Number(leaf.allocated_capital_usd ?? 6500).toLocaleString()}
              </strong>{' '}
              ({leaf.risk_posture || 'AGGRESSIVE'}).
            </p>
          </div>
          {Number(leaf.allocated_capital_usd ?? 6500) > 0 && (
            <button
              type="button"
              onClick={handleEmergencyLiquidate}
              disabled={liquidating}
              className="px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/40 text-red-200 border border-red-500/40 text-xs font-semibold transition"
            >
              {liquidating ? 'Liquidation...' : '🛑 Liquider vers Dry Powder'}
            </button>
          )}
        </div>

        <Dashboard statusData={statusData} apiBase={apiBase} onRefresh={onRefresh} />
      </div>
    );
  }

  const taMetrics = leaf.ta_metrics || {};

  return (
    <div className="space-y-6">
      {/* Header Banner for Dedicated Blockchain Leaf Agent */}
      <div className="bg-gray-900 p-5 rounded-xl border border-blue-500/30 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-800 pb-4">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <button
                type="button"
                onClick={onBackToMaster}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Retour Orchestrateur Maître
              </button>
              <span className="px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-semibold">
                {leaf.tier || 'LEAF_AGENT'} • {leaf.category}
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono">
                LLM : {leaf.model || 'deepseek/deepseek-v4.1-flash-1017'}
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono">
                MemPalace : {leaf.mempalace_wing}
              </span>
            </div>

            <h2 className="text-xl font-bold text-white mt-2">
              {leaf.name || leafId} — Isolation Écosystème {leaf.chain} ({leaf.symbol})
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Moteur d&apos;exécution : <strong className="text-gray-200">{leaf.execution_engine}</strong> • Actifs
              strictement autorisés :{' '}
              <code className="text-emerald-400">{(leaf.exclusive_assets || []).join(', ')}</code>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={leaf.risk_posture || 'BALANCED'}
              onChange={(e) => handlePostureChange(e.target.value)}
              className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-1.5 text-xs font-semibold"
            >
              <option value="AGGRESSIVE">Mandat : AGGRESSIVE</option>
              <option value="BALANCED">Mandat : BALANCED</option>
              <option value="DEFENSIVE">Mandat : DEFENSIVE</option>
              <option value="HIBERNATION">Mandat : HIBERNATION</option>
            </select>

            <button
              type="button"
              onClick={handleLeafReflect}
              disabled={reflecting}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {reflecting ? 'Réflexion Flash 1017...' : '⚡ Forcer Réflexion Locale'}
            </button>

            <button
              type="button"
              onClick={() => setShowLLMModal(true)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs transition"
            >
              <ScrollText className="w-3.5 h-3.5 text-purple-400" />
              Transcripts
            </button>

            {Number(leaf.allocated_capital_usd || 0) > 0 && (
              <button
                type="button"
                onClick={handleEmergencyLiquidate}
                disabled={liquidating}
                className="px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/40 text-red-300 border border-red-500/40 text-xs font-semibold transition"
              >
                {liquidating ? 'Liquidation...' : '🛑 Liquider → Dry Powder'}
              </button>
            )}
          </div>
        </div>

        {/* 4 Key Metrics for this Blockchain Leaf */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-gray-800">
            <div className="text-[11px] uppercase text-gray-400">Capital Alloué par l&apos;Orchestrateur</div>
            <div className="text-2xl font-bold text-white mt-0.5">
              ${Number(leaf.allocated_capital_usd || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">
              Poids portefeuille maître : {Number(leaf.weight_pct || 0).toFixed(1)}%
            </div>
          </div>

          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-gray-800">
            <div className="text-[11px] uppercase text-gray-400">Prix Spot ({leaf.symbol}/USD)</div>
            <div className="text-2xl font-bold text-emerald-400 mt-0.5">
              ${Number(leaf.last_price_usd || 0).toLocaleString('en-US', { maximumFractionDigits: 4 })}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">
              Cycle réflexion : {leaf.base_interval_sec || 180}s
            </div>
          </div>

          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-gray-800">
            <div className="text-[11px] uppercase text-gray-400">PnL Réalisé &amp; Sharpe</div>
            <div
              className={`text-2xl font-bold mt-0.5 ${
                Number(leaf.realized_pnl_usd || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}
            >
              {Number(leaf.realized_pnl_usd || 0) >= 0 ? '+' : ''}$
              {Number(leaf.realized_pnl_usd || 0).toFixed(2)}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">
              Sharpe Ratio : <strong className="text-white">{leaf.sharpe_ratio}</strong> • Win Rate :{' '}
              <strong className="text-white">{leaf.win_rate_pct}%</strong>
            </div>
          </div>

          <div className="bg-gray-950/70 p-3.5 rounded-lg border border-gray-800">
            <div className="text-[11px] uppercase text-gray-400">Thèse Active Locale</div>
            <div className="text-xs text-gray-200 mt-1 line-clamp-3">{leaf.last_hypothesis}</div>
          </div>
        </div>
      </div>

      {/* Ecosystem-Specific Technical / On-Chain Tools & Dedicated RSS Feeds */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Outils d&apos;Analyse Technique &amp; Métriques On-Chain Spécifiques ({leaf.chain})
          </h3>
          <div className="grid grid-cols-2 gap-2.5 text-xs">
            {Object.entries(taMetrics).map(([k, v]) => (
              <div key={k} className="p-3 rounded-lg bg-gray-950/70 border border-gray-800">
                <div className="text-[10px] uppercase tracking-wider text-gray-400">
                  {k.replace(/_/g, ' ')}
                </div>
                <div className="text-sm font-mono font-bold text-emerald-300 mt-0.5">{String(v)}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Rss className="w-4 h-4 text-amber-400" />
            Flux RSS Exclusifs à la Blockchain {leaf.chain}
          </h3>
          <div className="space-y-2">
            {rssItems.map((item, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg bg-gray-950/70 border border-gray-800 text-xs space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold text-[10px]">
                    {item.source}
                  </span>
                  <span className="font-mono text-[10px] text-emerald-400">
                    Sentiment {(Number(item.sentiment || 0.5) * 100).toFixed(0)}% • {item.impact}
                  </span>
                </div>
                <div className="text-gray-200">{item.title}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Dedicated MemPalace Wing Drawers */}
      <div className="bg-gray-900 p-5 rounded-xl border border-purple-500/30 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            Mémoire Infinie MemPalace de l&apos;Agent Feuille (<code>wing={leaf.mempalace_wing}</code>)
          </h3>
          <span className="text-xs text-gray-400">
            Lisible en temps réel par l&apos;Orchestrateur Maître (Kimi K3.1 Pro)
          </span>
        </div>

        {drawers.length === 0 ? (
          <div className="p-4 rounded-lg bg-gray-950/60 border border-gray-800 text-xs text-gray-400 flex items-center justify-between">
            <span>
              Aucun tiroir de réflexion supplémentaire enregistré dans <code>{leaf.mempalace_wing}</code> pour cette
              session. Cliquez sur « ⚡ Forcer Réflexion Locale » pour générer une thèse DeepSeek v4.1 Flash 1017.
            </span>
          </div>
        ) : (
          <div className="space-y-2">
            {drawers.map((drw) => (
              <div
                key={drw.drawer_id}
                className="p-3 rounded-lg bg-gray-950/80 border border-gray-800 text-xs space-y-1"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold text-[10px]">
                      {drw.thesis_continuity}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-[10px]">
                      {drw.model_used}
                    </span>
                    <span className="text-[11px] text-gray-400">
                      wing: <code>{drw.wing}</code> • {drw.tokens_used || 0} tok
                    </span>
                  </div>
                  <span className="text-[11px] text-emerald-400">
                    Prochain réveil : {drw.next_wakeup_sec}s
                  </span>
                </div>
                <p className="text-gray-200">{drw.ta_confluence_notes}</p>
                <p className="text-gray-400 text-[11px]">
                  <strong className="text-gray-300">Hypothèse :</strong> {drw.hypothesis} |{' '}
                  <strong className="text-amber-300">Invalidation :</strong> {drw.invalidation_condition}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <LLMInspectionModal
        apiBase={apiBase}
        open={showLLMModal}
        onClose={() => setShowLLMModal(false)}
      />
    </div>
  );
};

export default LeafAgentView;

import React, { useEffect, useState, useCallback } from 'react';
import ChatInterface from './components/ChatInterface';
import MasterOverview from './components/MasterOverview';
import LeafAgentView from './components/LeafAgentView';

const resolveApiBase = () => {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
};

const API_BASE = resolveApiBase();

const PRIMARY_LEAF_TABS = [
  { id: 'leaf-solana', label: '☀️ Solana', badge: 'P0' },
  { id: 'leaf-bitcoin', label: '₿ Bitcoin', badge: 'P0' },
  { id: 'leaf-ethereum', label: 'Ξ Ethereum', badge: 'P0' },
  { id: 'leaf-hyperliquid', label: '⚡ Hyperliquid', badge: 'P0' },
  { id: 'leaf-sui', label: '💧 Sui', badge: 'P0' },
  { id: 'leaf-binance-cex', label: '📊 Binance CEX', badge: 'MULTI' },
  { id: 'leaf-bnb', label: '🟡 BNB Chain', badge: 'P1' },
  { id: 'leaf-xrp', label: '✕ XRP Ledger', badge: 'P1' },
  { id: 'leaf-ton', label: '💎 TON (Gram)', badge: 'P1' },
  { id: 'leaf-tron', label: '🔺 TRON', badge: 'P1' },
  { id: 'leaf-avalanche', label: '🔺 Avalanche', badge: 'P1' },
  { id: 'leaf-cosmos', label: '⚛️ Cosmos (Atom)', badge: 'P1' },
  { id: 'leaf-paper-sandbox', label: '🧪 Paper Sandbox', badge: 'PAPER' },
];

// Offline skeleton — deliberately carries no performance numbers.
const FALLBACK_STATUS = {
  architecture: 'hybrid_rust_python_v2',
  hierarchy_version: 'v3_hierarchical_multi_ecosystem',
  kill_switch: { active: false, reason: null, max_daily_drawdown_limit_pct: 3.0 },
  policy_envelope: {
    envelope_id: 'offline',
    global_regime: 'OFFLINE',
    ttl_seconds: 0,
    pod_allocations: {},
  },
  engine_metrics: {
    backtest_fixture: null,
    paper_model: null,
    live_testnet: null,
    executions: [],
    executions_source: null,
  },
  catalysts: [],
  cost_guard: {},
  hierarchy: {
    master_orchestrator: {
      model: 'moonshotai/kimi-k3.1-pro',
      leaf_default_model: 'deepseek/deepseek-v4.1-flash-1017',
    },
    treasury: {
      // Cold offline skeleton: no invented portfolio, no invented aggregate.
      total_capital_usd: null,
      deployed_capital_usd: null,
      dry_powder_usd: null,
      dry_powder_ratio: null,
      min_dry_powder_ratio: 0.2,
      active_leaves_count: null,
      total_realized_pnl_usd: null,
      source: 'BOOTSTRAP',
    },
    openrouter_credit: { credit_balance_usd: null },
    leaves: [],
  },
};

function App() {
  const [statusData, setStatusData] = useState(FALLBACK_STATUS);
  const [backendConnected, setBackendConnected] = useState(false);
  const [lastSuccessAt, setLastSuccessAt] = useState(null);
  const [offlineSince, setOfflineSince] = useState(null);
  const [activeTab, setActiveTab] = useState('master');
  const reqSeqRef = React.useRef(0);
  const lastSuccessRef = React.useRef(null);

  const markOffline = useCallback(() => {
    setBackendConnected(false);
    // Degraded only after at least one success; a cold start stays on the
    // skeleton without an OFFLINE timestamp.
    setOfflineSince((prev) => prev || (lastSuccessRef.current ? new Date() : null));
  }, []);

  const fetchStatus = useCallback(async () => {
    const seq = ++reqSeqRef.current;
    try {
      const res = await fetch(`${API_BASE}/api/v1/status`);
      if (res.ok) {
        const data = await res.json();
        if (seq === reqSeqRef.current) {
          const now = new Date();
          lastSuccessRef.current = now;
          setStatusData(data);
          setLastSuccessAt(now);
          setOfflineSince(null);
          setBackendConnected(true);
        }
      } else if (seq === reqSeqRef.current) {
        markOffline();
      }
    } catch {
      if (seq === reqSeqRef.current) {
        markOffline();
      }
    }
  }, [markOffline]);

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 4000);
    return () => clearInterval(timer);
  }, [fetchStatus]);

  const handleRegimeChange = async (preset) => {
    reqSeqRef.current += 1;
    try {
      const res = await fetch(`${API_BASE}/api/v1/policy/regime`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset }),
      });
      if (res.ok) {
        await fetchStatus();
      }
    } catch {
      // Fallback preview when running UI standalone
    }
  };

  const handleToggleKillSwitch = async () => {
    reqSeqRef.current += 1;
    const nextActive = !statusData.kill_switch?.active;
    try {
      const res = await fetch(`${API_BASE}/api/v1/risk/kill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          active: nextActive,
          reason: nextActive ? 'Operator UI Emergency Stop' : 'Operator Reset',
        }),
      });
      if (res.ok) {
        await fetchStatus();
      }
    } catch {
      setStatusData((prev) => ({
        ...prev,
        kill_switch: { ...prev.kill_switch, active: nextActive },
      }));
    }
  };

  // A failed poll after a success swaps the whole render payload for the cold
  // skeleton: no retained performance or treasury value can survive.
  const renderData = offlineSince ? FALLBACK_STATUS : statusData;
  const isKilled = renderData.kill_switch?.active;
  const sniperEnabled = Boolean(renderData.policy_envelope?.pod_allocations?.pod_sniper?.enabled);
  const onchainAlphaEnabled = Boolean(
    renderData.policy_envelope?.pod_allocations?.pod_onchain_alpha?.enabled ||
      renderData.policy_envelope?.pod_allocations?.pod_solana_alpha?.enabled
  );
  const activePreset = sniperEnabled
    ? 'FULL_SWARM'
    : onchainAlphaEnabled
      ? 'RISK_ON_HIGH_VOL'
      : 'DEFENSIVE';

  const allLeaves = renderData?.hierarchy?.leaves || [];
  const primaryIds = new Set(PRIMARY_LEAF_TABS.map((t) => t.id));
  const secondaryLeaves = allLeaves.filter((l) => !primaryIds.has(l.id));

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-emerald-400 to-purple-400">
            Robotrader v3 ⚡ Architecture Hiérarchique Multi-Écosystèmes
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Orchestrateur Maître : <code className="text-indigo-300">moonshotai/kimi-k3.1-pro</code> |
            26 Sous-Agents Feuilles :{' '}
            <code className="text-emerald-400">deepseek/deepseek-v4.1-flash-1017</code> | Hot-Path :{' '}
            <code className="text-blue-400">engine-rs (&lt;50µs)</code>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => handleRegimeChange('DEFENSIVE')}
            className={`px-3 py-1.5 text-xs font-medium rounded border transition ${
              activePreset === 'DEFENSIVE'
                ? 'bg-blue-600/30 border-blue-400 text-blue-200'
                : 'bg-gray-800 hover:bg-gray-700 border-gray-700 text-gray-300'
            }`}
          >
            🛡️ Carry Défensif
          </button>
          <button
            onClick={() => handleRegimeChange('RISK_ON_HIGH_VOL')}
            className={`px-3 py-1.5 text-xs font-medium rounded border transition ${
              activePreset === 'RISK_ON_HIGH_VOL'
                ? 'bg-emerald-600/30 border-emerald-400 text-emerald-200'
                : 'bg-gray-800 hover:bg-gray-700 border-gray-700 text-gray-300'
            }`}
          >
            📈 Risk-On (Pods 1-3)
          </button>
          <button
            onClick={() => handleRegimeChange('FULL_SWARM')}
            className={`px-3 py-1.5 text-xs font-medium rounded border transition ${
              activePreset === 'FULL_SWARM'
                ? 'bg-purple-600/30 border-purple-400 text-purple-200'
                : 'bg-gray-800 hover:bg-gray-700 border-gray-700 text-gray-300'
            }`}
          >
            ⚡ Full Swarm (+Sniper)
          </button>
          <button
            onClick={handleToggleKillSwitch}
            className={`px-3 py-1.5 text-xs font-bold rounded transition-colors ${
              isKilled
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                : 'bg-red-600 hover:bg-red-500 text-white'
            }`}
          >
            {isKilled ? '✅ Réactiver Moteur' : '🛑 Kill-Switch'}
          </button>
          <span
            className={`text-xs px-2.5 py-1 rounded-full border ${
              backendConnected
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
            }`}
          >
            {offlineSince && lastSuccessAt
              ? `OFFLINE — last success ${lastSuccessAt.toLocaleTimeString('fr-FR')}`
              : backendConnected
                ? 'IPC Live'
                : 'Backend hors ligne'}
          </span>
        </div>
      </header>

      {/* Hierarchical Navigation Bar: Home (Master Orchestrator) + 26 Dedicated Leaf Tabs */}
      <nav className="mb-6 flex flex-wrap items-center gap-1.5 bg-gray-900/90 p-2 rounded-xl border border-gray-800">
        <button
          type="button"
          onClick={() => setActiveTab('master')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
            activeTab === 'master'
              ? 'bg-indigo-600 text-white shadow'
              : 'bg-gray-800/80 hover:bg-gray-700 text-gray-200 border border-gray-700'
          }`}
        >
          👑 Orchestrateur Maître (Accueil)
        </button>

        <div className="h-4 w-px bg-gray-800 mx-1" />

        {PRIMARY_LEAF_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 ${
              activeTab === tab.id
                ? 'bg-purple-600 text-white font-semibold shadow'
                : 'bg-gray-950/70 hover:bg-gray-800 text-gray-300 border border-gray-800'
            }`}
          >
            <span>{tab.label}</span>
          </button>
        ))}

        {/* Selector for P2/P3 Specialized & Watch Leaf Robots (Aptos, Chainlink, Stacks, NEAR, Cardano, Polkadot, Dogecoin, ICP, Canton, Celo, Tezos, Flow, EOS) */}
        <select
          value={
            !primaryIds.has(activeTab) && activeTab !== 'master' ? activeTab : ''
          }
          onChange={(e) => {
            if (e.target.value) setActiveTab(e.target.value);
          }}
          className={`px-2.5 py-1.5 rounded-lg text-xs border focus:outline-none ${
            !primaryIds.has(activeTab) && activeTab !== 'master'
              ? 'bg-purple-600 text-white border-purple-400 font-semibold'
              : 'bg-gray-950 text-gray-300 border-gray-800'
          }`}
        >
          <option value="">
            + Autres Blockchains Feuilles ({secondaryLeaves.length || 13} P2/P3)...
          </option>
          {(secondaryLeaves.length > 0
            ? secondaryLeaves
            : [
                { id: 'leaf-aptos', name: 'Aptos', symbol: 'APT', tier: 'P2' },
                { id: 'leaf-chainlink', name: 'Chainlink', symbol: 'LINK', tier: 'P2' },
                { id: 'leaf-stacks', name: 'Stacks (Blockstack)', symbol: 'STX', tier: 'P2' },
                { id: 'leaf-near', name: 'NEAR Protocol', symbol: 'NEAR', tier: 'P2' },
                { id: 'leaf-cardano', name: 'Cardano', symbol: 'ADA', tier: 'P2' },
                { id: 'leaf-polkadot', name: 'Polkadot', symbol: 'DOT', tier: 'P2' },
                { id: 'leaf-dogecoin', name: 'Dogecoin', symbol: 'DOGE', tier: 'P2' },
                { id: 'leaf-icp', name: 'Internet Computer', symbol: 'ICP', tier: 'P2' },
                { id: 'leaf-canton', name: 'Canton Network', symbol: 'CC', tier: 'P3' },
                { id: 'leaf-celo', name: 'Celo', symbol: 'CELO', tier: 'P3' },
                { id: 'leaf-tezos', name: 'Tezos', symbol: 'XTZ', tier: 'P3' },
                { id: 'leaf-flow', name: 'Flow', symbol: 'FLOW', tier: 'P3' },
                { id: 'leaf-eos', name: 'EOS (Vaulta)', symbol: 'EOS', tier: 'P3' },
              ]
          ).map((lf) => (
            <option key={lf.id} value={lf.id}>
              [{lf.tier}] {lf.name} ({lf.symbol})
            </option>
          ))}
        </select>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {activeTab === 'master' ? (
            <MasterOverview
              statusData={renderData}
              apiBase={API_BASE}
              onRefresh={fetchStatus}
              onSelectLeaf={(leafId) => setActiveTab(leafId)}
              offlineSince={offlineSince}
            />
          ) : (
            <LeafAgentView
              leafId={activeTab}
              statusData={renderData}
              apiBase={API_BASE}
              onRefresh={fetchStatus}
              onBackToMaster={() => setActiveTab('master')}
              offlineSince={offlineSince}
            />
          )}
        </div>

        <div className="lg:col-span-1 h-[calc(100vh-180px)]">
          <ChatInterface apiBase={API_BASE} onCommandExecuted={fetchStatus} />
        </div>
      </div>
    </div>
  );
}

export default App;

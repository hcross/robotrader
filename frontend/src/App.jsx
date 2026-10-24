import React, { useEffect, useState, useCallback } from 'react';
import ChatInterface from './components/ChatInterface';
import Dashboard from './components/Dashboard';

const resolveApiBase = () => {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
};

const API_BASE = resolveApiBase();

// Offline skeleton — deliberately carries no performance numbers. A hardcoded
// "100% win rate" demo payload used to be rendered before the first successful
// poll and was indistinguishable from live telemetry.
const FALLBACK_STATUS = {
  architecture: 'hybrid_rust_python_v2',
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
};

function App() {
  const [statusData, setStatusData] = useState(FALLBACK_STATUS);
  const [backendConnected, setBackendConnected] = useState(false);
  const reqSeqRef = React.useRef(0);

  const fetchStatus = useCallback(async () => {
    const seq = ++reqSeqRef.current;
    try {
      const res = await fetch(`${API_BASE}/api/v1/status`);
      if (res.ok) {
        const data = await res.json();
        if (seq === reqSeqRef.current) {
          setStatusData(data);
          setBackendConnected(true);
        }
      }
    } catch {
      if (seq === reqSeqRef.current) {
        setBackendConnected(false);
      }
    }
  }, []);

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

  const isKilled = statusData.kill_switch?.active;
  const sniperEnabled = Boolean(statusData.policy_envelope?.pod_allocations?.pod_sniper?.enabled);
  const solanaEnabled = Boolean(statusData.policy_envelope?.pod_allocations?.pod_solana_alpha?.enabled);
  const activePreset = sniperEnabled
    ? 'FULL_SWARM'
    : solanaEnabled
      ? 'RISK_ON_HIGH_VOL'
      : 'DEFENSIVE';

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-emerald-400 to-purple-500">
            Robotrader v2 ⚡ Hybrid Rust Hot-Path + AI Meta-Controller
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Engine: <code className="text-emerald-400">engine-rs (Tokio)</code> | Policy:{' '}
            <code className="text-blue-400">{statusData.policy_envelope?.envelope_id}</code> | Regime:{' '}
            <span className="font-semibold text-amber-300">
              {sniperEnabled ? 'FULL_SWARM (+SNIPER)' : statusData.policy_envelope?.global_regime}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-3">
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
            {backendConnected ? 'IPC Live' : 'Backend hors ligne'}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Dashboard statusData={statusData} apiBase={API_BASE} onRefresh={fetchStatus} />
        </div>

        <div className="lg:col-span-1 h-[calc(100vh-140px)]">
          <ChatInterface apiBase={API_BASE} onCommandExecuted={fetchStatus} />
        </div>
      </div>
    </div>
  );
}

export default App;

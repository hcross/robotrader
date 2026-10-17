import React from 'react';
import { Activity, TrendingUp, DollarSign, Shield, Cpu, Zap } from 'lucide-react';

const POD_META = {
  pod_carry: {
    label: 'Pod 1 — Delta-Neutral Carry',
    desc: 'Funding Rate & Spot-Perp Basis Arbitrage',
  },
  pod_momentum: {
    label: 'Pod 2 — Intraday Orderflow & Vol',
    desc: 'L2 OBI + CVD + Volatility Breakout (Post-Only Maker)',
  },
  pod_solana_alpha: {
    label: 'Pod 3 — Solana Smart-Money',
    desc: 'Whale Copy & Catalyst Swaps (Jupiter v6 + Jito)',
  },
  pod_sniper: {
    label: 'Pod 4 — DEX Atomic Sniper',
    desc: 'Raydium / Pump.fun Pool Launch (<5ms Rust + Jito)',
  },
};

const StatCard = ({ title, value, subtitle, icon: Icon, color }) => (
  <div className="bg-gray-900 p-4 rounded-lg shadow border border-gray-800">
    <div className="flex items-center justify-between mb-1">
      <h3 className="text-gray-400 text-xs font-medium uppercase tracking-wider">{title}</h3>
      <Icon className={`w-4 h-4 ${color}`} />
    </div>
    <p className="text-2xl font-bold text-white">{value}</p>
    {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
  </div>
);

const Dashboard = ({ statusData }) => {
  const metrics = statusData?.engine_metrics || {};
  const allocations = statusData?.policy_envelope?.pod_allocations || {};
  const attribution = metrics.pod_pnl_attribution || {};
  const executions = metrics.executions || [];
  const catalysts = statusData?.catalysts || [];
  const costGuard = statusData?.cost_guard || {};

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Equity Actuelle"
          value={`$${Number(metrics.final_equity_usd || 10000).toLocaleString()}`}
          subtitle={`Net PnL: +$${Number(metrics.net_profit_usd || 0).toFixed(2)} (+${Number(metrics.total_return_pct || 0).toFixed(2)}%)`}
          icon={DollarSign}
          color="text-emerald-400"
        />
        <StatCard
          title="Ratio de Sharpe"
          value={Number(metrics.sharpe_ratio || 0).toFixed(2)}
          subtitle={`Win Rate: ${Number(metrics.win_rate_pct || 0).toFixed(0)}% (${metrics.total_trades || 0} trades)`}
          icon={TrendingUp}
          color="text-blue-400"
        />
        <StatCard
          title="HardRiskGate (&lt;50µs)"
          value={`${metrics.rejected_orders || 0} Rug Bloqué`}
          subtitle={`Max DD: ${Number(metrics.max_drawdown_pct || 0).toFixed(2)}% / Limite 3.0%`}
          icon={Shield}
          color="text-amber-400"
        />
        <StatCard
          title="CostGuard LLM"
          value={`$${Number(costGuard.total_spent_usd || 0).toFixed(3)}`}
          subtitle={`Plafond: $${Number(costGuard.daily_budget_usd || 5).toFixed(2)}/j (Auto-refill OFF)`}
          icon={Cpu}
          color="text-purple-400"
        />
      </div>

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
            const pnl = Number(attribution[podKey] || 0);
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
                  <span className={pnl >= 0 ? 'text-emerald-400 font-semibold' : 'text-red-400 font-semibold'}>
                    PnL : {pnl >= 0 ? `+$${pnl.toFixed(2)}` : `-$${Math.abs(pnl).toFixed(2)}`}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Execution Ledger */}
      <div className="bg-gray-900 p-5 rounded-lg border border-gray-800">
        <h3 className="text-base font-semibold text-white mb-3">
          Journal d&apos;Exécution Déterministe (`engine-rs`)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400">
                <th className="pb-2">Actif</th>
                <th className="pb-2">Pod</th>
                <th className="pb-2">Venue</th>
                <th className="pb-2">Sens</th>
                <th className="pb-2">Notional</th>
                <th className="pb-2">PnL Réalisé</th>
                <th className="pb-2">Signal Quant / Rationale</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((ex, idx) => (
                <tr key={idx} className="border-b border-gray-800/60">
                  <td className="py-2 font-semibold text-white">{ex.symbol}</td>
                  <td className="py-2 text-blue-300">{ex.pod_id}</td>
                  <td className="py-2 text-gray-400">{ex.venue}</td>
                  <td
                    className={`py-2 font-bold ${
                      ex.side === 'BUY' ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                  >
                    {ex.side}
                  </td>
                  <td className="py-2">${Number(ex.notional_usd || 0).toFixed(0)}</td>
                  <td className="py-2 text-emerald-400 font-semibold">
                    +${Number(ex.realized_pnl_usd || 0).toFixed(2)}
                  </td>
                  <td className="py-2 text-gray-400">{ex.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Warm-Path Catalyst Feed */}
      <div className="bg-gray-900 p-5 rounded-lg border border-gray-800">
        <h3 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          Flux Catalyseurs Warm-Path (`CatalystScout` -&gt; `MetaAllocator`)
        </h3>
        <div className="space-y-2">
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
  );
};

export default Dashboard;

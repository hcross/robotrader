import React, { useEffect, useRef, useState, useMemo } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, RefreshCw, ScrollText, X } from 'lucide-react';

const PAGE_SIZE = 25;

const statusBadge = (call) => {
  if (call.status === 'no_api_key') {
    return <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">no key</span>;
  }
  if (call.status === 'fallback_failed') {
    return <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">fallback KO</span>;
  }
  if (call.status === 'llm_skipped_budget') {
    return <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">budget</span>;
  }
  if (call.status === 'truncated_output' || call.truncated) {
    return (
      <span className="px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-300" title="Complétion coupée par la limite de jetons">
        truncated
      </span>
    );
  }
  if (call.parsed_ok) {
    return <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">parsed</span>;
  }
  return <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">parse fail</span>;
};

const kindBadge = (call) => {
  const kind = call.kind;
  const agent = call.agent || '';
  if (kind === 'master_reflection' || agent === 'MasterOrchestrator/MacroLoop') {
    return (
      <span className="px-2 py-0.5 rounded bg-indigo-500/30 text-indigo-200 border border-indigo-400/40 font-semibold text-[10px]">
        👑 Orchestrateur Maître
      </span>
    );
  }
  if (agent === 'Leaf/leaf-solana' || agent === 'Orchestrator/CognitiveLoop') {
    return (
      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold text-[10px]">
        ☀️ Agent Solana
      </span>
    );
  }
  if (kind === 'leaf_reflection' || agent.startsWith('Leaf/')) {
    return (
      <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-semibold text-[10px]">
        🌿 {agent.replace('Leaf/', '') || kind}
      </span>
    );
  }
  return (
    <span
      className={`px-1.5 py-0.5 rounded ${
        kind === 'reflection' ? 'bg-purple-500/20 text-purple-300' : 'bg-blue-500/20 text-blue-300'
      }`}
    >
      {kind}
    </span>
  );
};

const formatAgentDisplay = (agent) => {
  if (agent === 'MasterOrchestrator/MacroLoop') return 'MasterOrchestrator/MacroLoop (Portefeuille Maître)';
  if (agent === 'Orchestrator/CognitiveLoop') return 'Leaf/leaf-solana (Solana • historique)';
  if (agent === 'Leaf/leaf-solana') return 'Leaf/leaf-solana (Solana)';
  return agent;
};

const PromptBlock = ({ label, text }) => (
  <div className="space-y-1">
    <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">{label}</div>
    <pre className="text-[10px] font-mono whitespace-pre-wrap break-words max-h-64 overflow-y-auto bg-gray-950 text-gray-300 rounded p-2 border border-gray-800">
      {text || '—'}
    </pre>
  </div>
);

const AttemptRow = ({ attempt }) => (
  <tr className="border-b border-gray-800">
    <td className="py-0.5 pr-2 font-mono text-gray-300">
      {attempt.model}
      {attempt.phase === 'escalated' && (
        <span className="ml-1 text-orange-400" title={`Relance après troncature (max_tokens=${attempt.max_tokens})`}>
          ↻
        </span>
      )}
    </td>
    <td className="py-0.5 pr-2 text-gray-400">{attempt.latency_ms} ms</td>
    <td className={`py-0.5 pr-2 ${attempt.ok ? 'text-emerald-400' : 'text-red-400'}`}>
      {attempt.ok ? 'OK' : 'KO'}
    </td>
    <td className="py-0.5 pr-2 text-gray-400">{attempt.prompt_tokens}</td>
    <td className="py-0.5 pr-2 text-gray-400">{attempt.completion_tokens}</td>
    <td
      className={`py-0.5 pr-2 ${attempt.finish_reason === 'length' ? 'text-orange-400' : 'text-gray-500'}`}
      title={`max_tokens=${attempt.max_tokens ?? '—'}`}
    >
      {attempt.finish_reason || '—'}
    </td>
    <td className="py-0.5 text-gray-500 break-words max-w-[16rem]">{attempt.error || '—'}</td>
  </tr>
);

const ToolRow = ({ tool }) => (
  <div className="flex items-center gap-2 text-[10px] font-mono">
    <span className={tool.ok ? 'text-emerald-400' : 'text-red-400'}>{tool.ok ? '✓' : '✗'}</span>
    <span className="text-gray-300">{tool.name}</span>
    <span className="text-gray-500">{tool.duration_ms} ms</span>
    {tool.error && <span className="text-red-400 break-all">{tool.error}</span>}
  </div>
);

const LLMInspectionModal = ({
  apiBase = 'http://localhost:8000',
  open,
  onClose,
  initialAgentFilter = '',
}) => {
  const [calls, setCalls] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [triggeringMaster, setTriggeringMaster] = useState(false);
  const [error, setError] = useState(null);
  const [agentFilter, setAgentFilter] = useState(initialAgentFilter || '');
  const [modelFilter, setModelFilter] = useState('');
  const [depthFilter, setDepthFilter] = useState('');
  const [expanded, setExpanded] = useState({});
  const [knownValues, setKnownValues] = useState({ agents: [], models: [], depths: [] });

  const reqSeqRef = useRef(0);

  useEffect(() => {
    if (open && initialAgentFilter !== undefined) {
      setAgentFilter(initialAgentFilter);
    }
  }, [open, initialAgentFilter]);

  // Anti-stale guard: only the latest fetch may mutate state (repo idiom of the 4s poll).
  const loadCalls = async (nextOffset) => {
    const seq = ++reqSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        offset: String(nextOffset),
        limit: String(PAGE_SIZE),
      });
      if (agentFilter) params.set('agent', agentFilter);
      if (modelFilter) params.set('model', modelFilter);
      if (depthFilter) params.set('depth', depthFilter);
      const res = await fetch(`${apiBase}/api/v1/llm/calls?${params.toString()}`);
      const payload = await res.json();
      if (seq !== reqSeqRef.current) return; // stale response
      const callList = payload.calls || [];
      setCalls(callList);
      setTotal(payload.total || 0);
      setOffset(nextOffset);

      const facets = payload.facets || {};
      setKnownValues((prev) => ({
        agents: [
          ...new Set([
            'MasterOrchestrator/MacroLoop',
            'Leaf/leaf-solana',
            ...prev.agents,
            ...(facets.agents || []),
            ...callList.map((c) => c.agent).filter(Boolean),
          ]),
        ],
        models: [
          ...new Set([
            ...prev.models,
            ...(facets.models || []),
            ...callList.map((c) => c.model_used || c.model_requested).filter(Boolean),
          ]),
        ],
        depths: [
          ...new Set([
            ...prev.depths,
            ...(facets.depths || []),
            ...callList.map((c) => c.thinking_depth).filter(Boolean),
          ]),
        ],
      }));
    } catch (exc) {
      if (seq === reqSeqRef.current) setError(String(exc));
    } finally {
      if (seq === reqSeqRef.current) setLoading(false);
    }
  };

  const handleTriggerMasterReflection = async () => {
    setTriggeringMaster(true);
    try {
      await fetch(`${apiBase}/api/v1/master/reflect`, { method: 'POST' });
      await loadCalls(0);
    } catch (exc) {
      setError(String(exc));
    } finally {
      setTriggeringMaster(false);
    }
  };

  // Fetch on open and on any filter/page change.
  useEffect(() => {
    if (open) {
      loadCalls(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, apiBase, agentFilter, modelFilter, depthFilter]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const selectCls =
    'bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-purple-500';

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;
  const rangeLabel = useMemo(
    () => `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} / ${total}`,
    [offset, total]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 border border-gray-800 rounded-lg shadow-2xl w-full max-w-4xl max-h-[85vh] overflow-y-auto flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 sticky top-0 bg-gray-900 z-10">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <ScrollText className="w-4 h-4 text-purple-400" />
            Inspection Production LLM — Transcripts Bruts
          </h3>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleTriggerMasterReflection}
              disabled={triggeringMaster}
              className="px-2.5 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-200 text-xs font-semibold flex items-center gap-1 disabled:opacity-50"
              title="Lancer immédiatement un cycle de réflexion de l'Orchestrateur Maître (Kimi K3.1 Pro)"
            >
              👑 {triggeringMaster ? 'Réflexion Orchestrateur…' : '+ Réflexion Orchestrateur'}
            </button>
            <button
              type="button"
              onClick={() => loadCalls(offset)}
              className="px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs flex items-center gap-1"
              title="Rafraîchir"
            >
              <RefreshCw className="w-3 h-3" />
              Rafraîchir
            </button>
            <button type="button" onClick={onClose} className="text-gray-400 hover:text-white" title="Fermer">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Quick Hierarchy Filter Tabs */}
        <div className="flex flex-wrap items-center gap-2 px-4 py-2 bg-gray-950/60 border-b border-gray-800 text-xs">
          <span className="text-[11px] text-gray-400 font-medium mr-1">Vue rapide :</span>
          {[
            { id: '', label: 'Tous les Transcripts' },
            { id: 'MasterOrchestrator/MacroLoop', label: '👑 Orchestrateur Maître (Kimi K3.1 Pro)' },
            { id: 'Leaf/leaf-solana', label: '☀️ Agent Feuille Solana (leaf-solana)' },
          ].map((tab) => (
            <button
              key={tab.id || 'all'}
              type="button"
              onClick={() => setAgentFilter(tab.id)}
              className={`px-2.5 py-1 rounded-md border text-xs font-medium transition ${
                agentFilter === tab.id
                  ? 'bg-indigo-600/30 border-indigo-400 text-white shadow-sm'
                  : 'bg-gray-800/80 border-gray-700 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-b border-gray-800">
          <select
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            className={selectCls}
            title="Filtrer par agent"
          >
            <option value="">Agent : tous</option>
            {knownValues.agents.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <select
            value={modelFilter}
            onChange={(e) => setModelFilter(e.target.value)}
            className={selectCls}
            title="Filtrer par modèle"
          >
            <option value="">Modèle : tous</option>
            {knownValues.models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select
            value={depthFilter}
            onChange={(e) => setDepthFilter(e.target.value)}
            className={selectCls}
            title="Filtrer par profondeur cognitive"
          >
            <option value="">Profondeur : toutes</option>
            {knownValues.depths.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <span className="text-xs text-gray-500 ml-auto font-mono">{rangeLabel}</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => canPrev && loadCalls(offset - PAGE_SIZE)}
              disabled={!canPrev}
              className="p-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-40"
              title="Page précédente"
            >
              <ChevronLeft className="w-3 h-3" />
            </button>
            <button
              type="button"
              onClick={() => canNext && loadCalls(offset + PAGE_SIZE)}
              disabled={!canNext}
              className="p-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-40"
              title="Page suivante"
            >
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        <div className="px-4 py-3 space-y-2">
          {loading && <div className="text-xs text-gray-400 py-6 text-center">Chargement des transcripts…</div>}
          {error && <div className="text-xs text-red-400 py-6 text-center">Erreur : {error}</div>}
          {!loading && !error && calls.length === 0 && (
            <div className="text-xs text-gray-500 py-6 text-center">
              Aucun transcript LLM enregistré — déclenchez une réflexion pour en produire.
            </div>
          )}
          {calls.map((call) => {
            const isOpen = expanded[call.entry_id];
            const isMaster =
              call.agent === 'MasterOrchestrator/MacroLoop' || call.kind === 'master_reflection';
            return (
              <div
                key={call.entry_id}
                className={`rounded border ${
                  isMaster
                    ? 'bg-indigo-950/25 border-indigo-500/40'
                    : 'bg-gray-800/60 border-gray-700/80'
                }`}
              >
                <button
                  type="button"
                  onClick={() => setExpanded((prev) => ({ ...prev, [call.entry_id]: !prev[call.entry_id] }))}
                  className="w-full text-left px-3 py-2 flex flex-wrap items-center gap-2 hover:bg-gray-800/80"
                >
                  <span className="text-gray-400">
                    {isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  </span>
                  <span className="font-mono text-xs text-gray-200">
                    {new Date(call.timestamp_ms).toLocaleTimeString('fr-FR')}
                  </span>
                  {kindBadge(call)}
                  <span className="text-xs text-gray-200 font-medium">
                    {formatAgentDisplay(call.agent)}
                  </span>
                  <span className="text-[10px] font-mono text-gray-400">{call.model_used || call.model_requested}</span>
                  <span className="text-[10px] text-gray-400 font-mono">{call.thinking_depth}</span>
                  {statusBadge(call)}
                  <span className="ml-auto flex items-center gap-3 font-mono text-[10px] text-gray-400">
                    <span title="Tokens prompt / completion">
                      ↗{call.prompt_tokens} ↙{call.completion_tokens}
                    </span>
                    <span title="Latence totale">{call.latency_ms} ms</span>
                    <span title="Coût estimé">${Number(call.cost_usd || 0).toFixed(6)}</span>
                  </span>
                </button>
                {isOpen && (
                  <div className="px-3 pb-3 pt-1 space-y-2 border-t border-gray-800">
                    <PromptBlock label="System prompt" text={call.system_prompt} />
                    <PromptBlock label="User prompt" text={call.user_prompt} />
                    <PromptBlock label="Completion brute" text={call.raw_completion} />
                    {call.error && (
                      <div className="text-[10px] text-red-400 font-mono">Transport error : {call.error}</div>
                    )}
                    {call.attempts?.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                          Tentatives (failover)
                        </div>
                        <table className="text-[10px] font-mono w-full">
                          <thead>
                            <tr className="text-gray-600">
                              <th className="text-left py-0.5 pr-2">modèle</th>
                              <th className="text-left py-0.5 pr-2">latence</th>
                              <th className="text-left py-0.5 pr-2">état</th>
                              <th className="text-left py-0.5 pr-2">tok in</th>
                              <th className="text-left py-0.5 pr-2">tok out</th>
                              <th className="text-left py-0.5 pr-2">finish</th>
                              <th className="text-left py-0.5">erreur</th>
                            </tr>
                          </thead>
                          <tbody>
                            {call.attempts.map((att, i) => (
                              <AttemptRow key={i} attempt={att} />
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    {call.tool_calls?.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                          Tool calls du cycle
                        </div>
                        <div className="bg-gray-950 rounded p-2 border border-gray-800 space-y-0.5">
                          {call.tool_calls.map((tc, i) => (
                            <ToolRow key={i} tool={tc} />
                          ))}
                        </div>
                      </div>
                    )}
                    {Object.keys(call.meta || {}).length > 0 && (
                      <div className="text-[10px] font-mono text-gray-500">
                        {Object.entries(call.meta)
                          .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                          .join(' · ')}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default LLMInspectionModal;
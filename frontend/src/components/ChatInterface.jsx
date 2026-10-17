import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User } from 'lucide-react';

const ChatInterface = ({ apiBase = 'http://localhost:8000', onCommandExecuted }) => {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      content:
        'Copilote Robotrader v2 actif (Warm-Path Meta-Controller). Demandez un `backtest`, un passage en mode `defensive carry`, `full swarm` ou `kill switch`.',
    },
  ]);
  const [input, setInput] = useState('');
  const wsRef = useRef(null);

  useEffect(() => {
    const wsUrl = apiBase.replace(/^http/, 'ws') + '/ws/chat';
    try {
      const ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setMessages((prev) => [
            ...prev,
            { role: payload.role || 'agent', content: payload.content },
          ]);
          if (onCommandExecuted) onCommandExecuted();
        } catch {
          // Ignore malformed frame
        }
      };
      wsRef.current = ws;
      return () => ws.close();
    } catch {
      return undefined;
    }
  }, [apiBase, onCommandExecuted]);

  const sendCommand = async (cmdText) => {
    const trimmed = cmdText.trim();
    if (!trimmed) return;

    setMessages((prev) => [...prev, { role: 'user', content: trimmed }]);
    setInput('');

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(trimmed);
      return;
    }

    try {
      const res = await fetch(`${apiBase}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: trimmed }),
      });
      if (res.ok) {
        const payload = await res.json();
        setMessages((prev) => [
          ...prev,
          { role: payload.role || 'agent', content: payload.content },
        ]);
        if (onCommandExecuted) onCommandExecuted();
        return;
      }
    } catch {
      // Offline preview response
    }

    setMessages((prev) => [
      ...prev,
      {
        role: 'agent',
        content: `Commande "${trimmed}" enregistrée pour la PolicyEnvelope.`,
      },
    ]);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg shadow-lg border border-gray-800 overflow-hidden">
      <div className="bg-gray-800/80 p-3.5 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center">
          <Bot className="w-5 h-5 text-blue-400 mr-2" />
          <h2 className="text-sm font-semibold text-white">Warm-Path Copilot (`Orchestrator`)</h2>
        </div>
        <span className="text-[11px] text-emerald-400 font-mono">Strands A2A</span>
      </div>

      <div className="px-3 py-2 bg-gray-900 border-b border-gray-800 flex flex-wrap gap-1.5">
        {['backtest', 'defensive carry', 'full swarm', 'kill switch', 'resume'].map((preset) => (
          <button
            key={preset}
            onClick={() => sendCommand(preset)}
            className="text-[11px] px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700"
          >
            {preset}
          </button>
        ))}
      </div>

      <div className="flex-1 p-4 overflow-y-auto space-y-3 text-xs">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] p-3 rounded-lg ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-100 border border-gray-700'
              }`}
            >
              <div className="flex items-center mb-1 opacity-80">
                {msg.role === 'agent' ? (
                  <Bot size={13} className="mr-1 text-blue-300" />
                ) : (
                  <User size={13} className="mr-1" />
                )}
                <span className="text-[10px] font-bold uppercase">{msg.role}</span>
              </div>
              <p className="leading-relaxed">{msg.content}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="p-3 bg-gray-800/80 border-t border-gray-700 flex">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendCommand(input)}
          placeholder="Directive stratégique (ex: backtest, defensive carry)..."
          className="flex-1 bg-gray-900 text-white text-xs rounded-l-lg px-3 py-2 border border-gray-700 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={() => sendCommand(input)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-2 rounded-r-lg transition-colors"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
};

export default ChatInterface;

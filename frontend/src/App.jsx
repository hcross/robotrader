import React from 'react';
import ChatInterface from './components/ChatInterface';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <header className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">
          Robotrader 🤖
        </h1>
        <div className="text-sm text-gray-400">
          Status: <span className="text-green-400">Online</span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-150px)]">
        <div className="lg:col-span-2 space-y-6 overflow-y-auto">
          <Dashboard />
          {/* Placeholder for more widgets */}
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Market Analysis</h3>
            <p className="text-gray-400">Waiting for agent insights...</p>
          </div>
        </div>

        <div className="lg:col-span-1 h-full">
          <ChatInterface />
        </div>
      </div>
    </div>
  );
}

export default App;

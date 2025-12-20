import React, { useState } from 'react';
import { Send, Bot, User } from 'lucide-react';

const ChatInterface = () => {
    const [messages, setMessages] = useState([
        { role: 'agent', content: 'Hello! I am your Robotrader Orchestrator. How can I help you today?' }
    ]);
    const [input, setInput] = useState('');

    const handleSend = () => {
        if (!input.trim()) return;

        const newMessages = [...messages, { role: 'user', content: input }];
        setMessages(newMessages);
        setInput('');

        // Mock response
        setTimeout(() => {
            setMessages(prev => [...prev, { role: 'agent', content: `I received your command: "${input}". Processing...` }]);
        }, 1000);
    };

    return (
        <div className="flex flex-col h-full bg-gray-800 rounded-lg shadow-lg overflow-hidden">
            <div className="bg-gray-700 p-4 border-b border-gray-600 flex items-center">
                <Bot className="w-6 h-6 text-blue-400 mr-2" />
                <h2 className="text-lg font-semibold text-white">Orchestrator Chat</h2>
            </div>

            <div className="flex-1 p-4 overflow-y-auto space-y-4">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] p-3 rounded-lg ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-600 text-gray-100'}`}>
                            <div className="flex items-center mb-1">
                                {msg.role === 'agent' ? <Bot size={16} className="mr-1" /> : <User size={16} className="mr-1" />}
                                <span className="text-xs font-bold uppercase">{msg.role}</span>
                            </div>
                            <p>{msg.content}</p>
                        </div>
                    </div>
                ))}
            </div>

            <div className="p-4 bg-gray-700 border-t border-gray-600 flex">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Type your command..."
                    className="flex-1 bg-gray-600 text-white rounded-l-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                    onClick={handleSend}
                    className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-r-lg transition-colors"
                >
                    <Send size={20} />
                </button>
            </div>
        </div>
    );
};

export default ChatInterface;

import React from 'react';
import { Activity, TrendingUp, DollarSign, Shield } from 'lucide-react';

const StatCard = ({ title, value, icon: Icon, color }) => (
    <div className="bg-gray-800 p-4 rounded-lg shadow-md border border-gray-700">
        <div className="flex items-center justify-between mb-2">
            <h3 className="text-gray-400 text-sm font-medium">{title}</h3>
            <Icon className={`w-5 h-5 ${color}`} />
        </div>
        <p className="text-2xl font-bold text-white">{value}</p>
    </div>
);

const Dashboard = () => {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard title="Total Portfolio" value="$12,450.00" icon={DollarSign} color="text-green-400" />
                <StatCard title="24h Profit" value="+$320.50" icon={TrendingUp} color="text-blue-400" />
                <StatCard title="Active Agents" value="5" icon={Activity} color="text-purple-400" />
                <StatCard title="Risk Level" value="Moderate" icon={Shield} color="text-yellow-400" />
            </div>

            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
                <h3 className="text-lg font-semibold text-white mb-4">Active Positions</h3>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-gray-300">
                        <thead>
                            <tr className="border-b border-gray-600">
                                <th className="pb-2">Asset</th>
                                <th className="pb-2">Type</th>
                                <th className="pb-2">Entry Price</th>
                                <th className="pb-2">Current Price</th>
                                <th className="pb-2">PNL</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="border-b border-gray-700">
                                <td className="py-2 font-medium text-white">SOL</td>
                                <td className="py-2 text-green-400">LONG</td>
                                <td className="py-2">$145.20</td>
                                <td className="py-2">$148.50</td>
                                <td className="py-2 text-green-400">+$330.00</td>
                            </tr>
                            <tr>
                                <td className="py-2 font-medium text-white">JUP</td>
                                <td className="py-2 text-green-400">LONG</td>
                                <td className="py-2">$1.20</td>
                                <td className="py-2">$1.18</td>
                                <td className="py-2 text-red-400">-$20.00</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;

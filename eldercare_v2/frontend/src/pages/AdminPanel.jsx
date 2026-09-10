import React, { useState } from 'react';
import { Settings, Database, Users, BarChart3 } from 'lucide-react';

const AdminPanel = ({ API_BASE }) => {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto">
      <h2 className="text-white text-2xl font-bold">Admin Panel</h2>

      <div className="flex gap-4 border-b border-gray-700">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
            activeTab === 'overview'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-white'
          }`}
        >
          <BarChart3 size={18} className="inline mr-2" />
          Overview
        </button>
        <button
          onClick={() => setActiveTab('users')}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
            activeTab === 'users'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-white'
          }`}
        >
          <Users size={18} className="inline mr-2" />
          Users
        </button>
        <button
          onClick={() => setActiveTab('database')}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
            activeTab === 'database'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-white'
          }`}
        >
          <Database size={18} className="inline mr-2" />
          Database
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
            activeTab === 'settings'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-white'
          }`}
        >
          <Settings size={18} className="inline mr-2" />
          Settings
        </button>
      </div>

      {activeTab === 'overview' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-white font-bold mb-2">System Status</h3>
            <p className="text-green-400">✓ All systems operational</p>
          </div>
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-white font-bold mb-2">Database</h3>
            <p className="text-blue-400">✓ Connected to PostgreSQL</p>
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-white font-bold mb-4">User Management</h3>
          <p className="text-gray-400">User management interface - coming soon</p>
        </div>
      )}

      {activeTab === 'database' && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-white font-bold mb-4">Database</h3>
          <p className="text-gray-400">Database management - coming soon</p>
        </div>
      )}

      {activeTab === 'settings' && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-white font-bold mb-4">Settings</h3>
          <p className="text-gray-400">Configuration settings - coming soon</p>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;

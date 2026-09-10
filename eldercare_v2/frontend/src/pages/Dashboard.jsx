import React, { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { AlertCircle, TrendingUp, Users, Activity, Zap } from 'lucide-react';
import axios from 'axios';

const Dashboard = ({ API_BASE }) => {
  const [stats, setStats] = useState({
    totalPatients: 0,
    activeMonitoring: 0,
    sosAlertsToday: 0,
    fallDetections: 0,
  });
  
  const [activityData, setActivityData] = useState([]);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };

      // Load stats
      const [statsRes, activityRes, alertsRes] = await Promise.all([
        axios.get(`${API_BASE}/dashboard/stats`, { headers }),
        axios.get(`${API_BASE}/dashboard/activity-distribution`, { headers }),
        axios.get(`${API_BASE}/dashboard/recent-alerts?limit=5`, { headers }),
      ]);

      setStats(statsRes.data);
      setActivityData(activityRes.data);
      setRecentAlerts(alertsRes.data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-white">Loading dashboard...</div>;
  }

  return (
    <div className="p-8 space-y-8">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Patients"
          value={stats.totalPatients}
          icon={<Users className="text-blue-400" size={28} />}
          trend="+2 this month"
        />
        <StatCard
          title="Active Monitoring"
          value={stats.activeMonitoring}
          icon={<Activity className="text-green-400" size={28} />}
          trend="Real-time"
          highlight
        />
        <StatCard
          title="SOS Alerts Today"
          value={stats.sosAlertsToday}
          icon={<AlertCircle className="text-orange-400" size={28} />}
          trend={stats.sosAlertsToday > 5 ? '⚠️ High' : '✓ Normal'}
        />
        <StatCard
          title="Falls Detected"
          value={stats.fallDetections}
          icon={<Zap className="text-red-400" size={28} />}
          trend="This week"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity Distribution */}
        <div className="lg:col-span-2 bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-white text-lg font-semibold mb-4">Activity Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={activityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis dataKey="activity" stroke="#999" />
              <YAxis stroke="#999" />
              <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Activity Breakdown Pie */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-white text-lg font-semibold mb-4">Breakdown</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={activityData}
                dataKey="count"
                nameKey="activity"
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
              >
                {activityData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={ACTIVITY_COLORS[index % ACTIVITY_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Alerts */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-white text-lg font-semibold mb-4">Recent SOS Alerts</h3>
        <div className="space-y-3">
          {recentAlerts.length > 0 ? (
            recentAlerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-4 rounded-lg border-l-4 ${
                  alert.severity === 'CRITICAL'
                    ? 'bg-red-900/20 border-red-500'
                    : alert.severity === 'HIGH'
                    ? 'bg-orange-900/20 border-orange-500'
                    : 'bg-yellow-900/20 border-yellow-500'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-white font-semibold">{alert.alert_type}</p>
                    <p className="text-gray-300 text-sm">{alert.message}</p>
                  </div>
                  <span className={`px-3 py-1 rounded text-xs font-semibold ${
                    alert.resolved ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'
                  }`}>
                    {alert.resolved ? 'Resolved' : 'Active'}
                  </span>
                </div>
                <p className="text-gray-400 text-xs mt-2">{new Date(alert.notified_at).toLocaleString()}</p>
              </div>
            ))
          ) : (
            <p className="text-gray-400">No recent alerts</p>
          )}
        </div>
      </div>
    </div>
  );
};

function StatCard({ title, value, icon, trend, highlight }) {
  return (
    <div className={`p-6 rounded-lg border transition-all ${
      highlight
        ? 'bg-gradient-to-br from-green-900/30 to-emerald-900/30 border-green-600/50 shadow-lg shadow-green-500/20'
        : 'bg-gray-800 border-gray-700 hover:border-gray-600'
    }`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-gray-400 text-sm">{title}</p>
          <p className="text-white text-3xl font-bold mt-2">{value}</p>
          <p className="text-gray-500 text-xs mt-2">{trend}</p>
        </div>
        <div className="p-3 rounded-lg bg-gray-700/50">{icon}</div>
      </div>
    </div>
  );
}

const ACTIVITY_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6'];

export default Dashboard;

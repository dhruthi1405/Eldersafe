import React, { useState, useEffect } from 'react';
import { CheckCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';

const SOSAlerts = ({ API_BASE, onAlertsRead }) => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAlerts();
    const interval = setInterval(loadAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadAlerts = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_BASE}/sos-events`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAlerts(response.data);
      onAlertsRead?.();
      setLoading(false);
    } catch (error) {
      console.error('Failed to load alerts:', error);
      setLoading(false);
    }
  };

  const resolveAlert = async (alertId) => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_BASE}/sos-events/${alertId}/resolve`, {
        notes: 'Resolved by caretaker'
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      loadAlerts();
    } catch (error) {
      console.error('Failed to resolve alert:', error);
    }
  };

  if (loading) return <div className="p-8 text-white">Loading alerts...</div>;

  const activeAlerts = alerts.filter(a => !a.resolved);
  const resolvedAlerts = alerts.filter(a => a.resolved);

  return (
    <div className="p-8 space-y-6 max-w-4xl mx-auto">
      <h2 className="text-white text-2xl font-bold">SOS Alerts</h2>

      {/* Active Alerts */}
      <div>
        <h3 className="text-white text-lg font-semibold mb-4">Active Alerts ({activeAlerts.length})</h3>
        <div className="space-y-3">
          {activeAlerts.length === 0 ? (
            <div className="bg-green-900/20 border border-green-600 rounded-lg p-4 text-green-300">
              ✓ No active alerts - All clear!
            </div>
          ) : (
            activeAlerts.map((alert) => (
              <div
                key={alert.id}
                className="bg-red-900/20 border border-red-600 rounded-lg p-4 flex justify-between items-start"
              >
                <div className="flex-1">
                  <h4 className="text-white font-bold">{alert.alert_type}</h4>
                  <p className="text-gray-300 text-sm mt-1">{alert.message}</p>
                  <p className="text-gray-400 text-xs mt-2">{new Date(alert.notified_at).toLocaleString()}</p>
                </div>
                <button
                  onClick={() => resolveAlert(alert.id)}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg"
                >
                  Resolve
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Resolved Alerts */}
      <div>
        <h3 className="text-white text-lg font-semibold mb-4">Resolved Alerts ({resolvedAlerts.length})</h3>
        <div className="space-y-3">
          {resolvedAlerts.slice(0, 10).map((alert) => (
            <div
              key={alert.id}
              className="bg-gray-800 border border-gray-700 rounded-lg p-4 flex items-start gap-3 opacity-75"
            >
              <CheckCircle className="text-green-400 flex-shrink-0" size={20} />
              <div className="flex-1">
                <h4 className="text-gray-300 font-semibold">{alert.alert_type}</h4>
                <p className="text-gray-400 text-sm">{alert.message}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SOSAlerts;

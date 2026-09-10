import React, { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import axios from 'axios';

const Timeline = ({ API_BASE }) => {
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patients, setPatients] = useState([]);
  const [timelineData, setTimelineData] = useState([]);

  const formatDuration = (seconds = 0) => {
    const totalMinutes = Math.round(seconds / 60);
    if (totalMinutes < 60) return `${totalMinutes}m`;
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
  };

  const activityChartData = Object.values(
    timelineData.reduce((acc, item) => {
      const label = item.activity_label || 'unknown';
      if (!acc[label]) {
        acc[label] = { activity: label, duration_seconds: 0, duration_minutes: 0 };
      }
      acc[label].duration_seconds += item.duration_seconds || 0;
      acc[label].duration_minutes = Math.round(acc[label].duration_seconds / 60);
      return acc;
    }, {})
  ).sort((a, b) => b.duration_seconds - a.duration_seconds);

  const safetyChartData = Object.values(
    timelineData.reduce((acc, item) => {
      const date = item.date;
      if (!acc[date]) {
        acc[date] = { date, fall_incidents: 0, gait_issues: 0 };
      }
      acc[date].fall_incidents += item.fall_incidents || 0;
      acc[date].gait_issues += item.gait_issues || 0;
      return acc;
    }, {})
  ).sort((a, b) => new Date(a.date) - new Date(b.date));

  useEffect(() => {
    loadPatients();
  }, []);

  const loadPatients = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_BASE}/patients`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPatients(response.data);
    } catch (error) {
      console.error('Failed to load patients:', error);
    }
  };

  const loadTimeline = async (patientId) => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_BASE}/patients/${patientId}/timeline?days=30`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTimelineData(response.data);
    } catch (error) {
      console.error('Failed to load timeline:', error);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto">
      <h2 className="text-white text-2xl font-bold">Activity Timeline</h2>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <label className="block text-gray-300 font-semibold mb-3">Select Patient</label>
        <select
          value={selectedPatient || ''}
          onChange={(e) => {
            setSelectedPatient(parseInt(e.target.value));
            loadTimeline(parseInt(e.target.value));
          }}
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white"
        >
          <option value="">-- Choose a patient --</option>
          {patients.map((patient) => (
            <option key={patient.id} value={patient.id}>
              {patient.full_name}
            </option>
          ))}
        </select>
      </div>

      {selectedPatient && timelineData.length > 0 && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {activityChartData.slice(0, 4).map((activity) => (
              <div key={activity.activity} className="bg-gray-800 rounded-lg p-5 border border-gray-700">
                <p className="text-gray-400 capitalize">{activity.activity}</p>
                <p className="text-white text-2xl font-bold mt-2">
                  {formatDuration(activity.duration_seconds)}
                </p>
              </div>
            ))}
          </div>

          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-white text-lg font-bold mb-4">Activity Duration</h3>
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={activityChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="activity" stroke="#999" />
                <YAxis stroke="#999" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1f2937', border: 'none' }}
                  formatter={(value, name, props) => [
                    formatDuration(props.payload.duration_seconds),
                    'Duration'
                  ]}
                />
                <Bar dataKey="duration_minutes" name="Minutes" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-white text-lg font-bold mb-4">Safety Events</h3>
            <ResponsiveContainer width="100%" height={340}>
              <LineChart data={safetyChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="date" stroke="#999" />
                <YAxis stroke="#999" allowDecimals={false} />
                <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="fall_incidents"
                  stroke="#ef4444"
                  name="Fall Incidents"
                  strokeWidth={2}
                />
                <Line
                  type="monotone"
                  dataKey="gait_issues"
                  stroke="#f59e0b"
                  name="Gait Issues"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
};

export default Timeline;

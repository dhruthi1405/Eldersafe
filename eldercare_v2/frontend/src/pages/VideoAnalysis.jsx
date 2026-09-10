import React, { useState, useRef } from 'react';
import { Upload, Play, Download, Loader } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import SkeletonVisualizer from '../components/SkeletonVisualizer';

const VideoAnalysis = ({ API_BASE }) => {
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [processingStatus, setProcessingStatus] = useState('');
  const [predictions, setPredictions] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const fileInputRef = useRef(null);

  React.useEffect(() => {
    loadPatients();
  }, []);

  const maxFallConfidence = predictions?.predictions?.length
    ? Math.max(...predictions.predictions.map((pred) => pred.fall_confidence || 0))
    : 0;

  const activityCounts = predictions?.predictions?.length
    ? predictions.predictions.reduce((acc, pred) => {
        const label = pred.activity_label || 'other';
        const isWarmup = label === 'other' && (pred.activity_confidence || 0) === 0;
        if (!isWarmup) {
          acc[label] = (acc[label] || 0) + 1;
        }
        return acc;
      }, {})
    : {};

  const primaryActivity = Object.entries(activityCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'other';

  const visiblePredictions = predictions?.predictions?.length
    ? [
        ...predictions.predictions.filter((pred) => pred.fall_status === 'FALLING'),
        ...predictions.predictions.filter((pred) => (
          pred.fall_status !== 'FALLING'
          && pred.activity_label !== 'other'
          && (pred.activity_confidence || 0) > 0
        )),
        ...predictions.predictions.filter((pred) => (
          pred.fall_status !== 'FALLING'
          && (pred.activity_label === 'other' || (pred.activity_confidence || 0) === 0)
        )),
      ].slice(0, 20)
    : [];

  const loadPatients = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_BASE}/patients`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPatients(response.data);
    } catch (error) {
      console.error('Failed to load patients:', error);
      toast.error('Failed to load patients');
    }
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!selectedPatient) {
      toast.error('Please select a patient first');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('patient_id', selectedPatient);

    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API_BASE}/sessions/upload`, formData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProcessingStatus(`Uploading... ${percentCompleted}%`);
        }
      });

      setSessionId(response.data.session_id);
      toast.success('Video uploaded! Processing has started...');
      setProcessingStatus('Processing started...');

      // Poll for status
      pollForCompletion(response.data.session_id);
    } catch (error) {
      console.error('Upload failed:', error);
      toast.error('Failed to upload video');
      setUploading(false);
    }
  };

  const pollForCompletion = async (sId) => {
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes max

    const poll = async () => {
      if (attempts >= maxAttempts) {
        toast.error('Processing timeout');
        setUploading(false);
        return;
      }

      try {
        const token = localStorage.getItem('token');
        const response = await axios.get(`${API_BASE}/sessions/${sId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        setProcessingStatus(`Status: ${response.data.session.status}`);

        if (response.data.session.status === 'completed') {
          setPredictions(response.data);
          setShowResults(true);
          setUploading(false);
          toast.success('Video processing completed!');
        } else if (response.data.session.status === 'failed') {
          toast.error('Video processing failed');
          setUploading(false);
        } else {
          attempts++;
          setTimeout(poll, 2000); // Check every 2 seconds
        }
      } catch (error) {
        console.error('Poll error:', error);
        attempts++;
        setTimeout(poll, 2000);
      }
    };

    poll();
  };

  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto">
      {/* Upload Section */}
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700">
        <h2 className="text-white text-2xl font-bold mb-6">Upload & Analyze Video</h2>

        {/* Patient Selection */}
        <div className="mb-6">
          <label className="block text-gray-300 text-sm font-semibold mb-3">Select Patient</label>
          <select
            value={selectedPatient || ''}
            onChange={(e) => setSelectedPatient(parseInt(e.target.value))}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">-- Choose a patient --</option>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.full_name} ({patient.patient_id})
              </option>
            ))}
          </select>
        </div>

        {/* File Upload Area */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-600 rounded-lg p-12 text-center hover:border-blue-500 transition-colors cursor-pointer bg-gray-700/30"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleFileSelect}
            disabled={uploading}
            className="hidden"
          />
          <Upload className="mx-auto text-gray-400 mb-4" size={48} />
          <p className="text-white text-lg font-semibold mb-2">Drag & drop video here</p>
          <p className="text-gray-400 text-sm">or click to select (MP4, AVI, MOV, etc.)</p>
          {uploading && <p className="text-blue-400 text-sm mt-4">{processingStatus}</p>}
        </div>

        {uploading && (
          <div className="mt-6 bg-blue-900/20 border border-blue-600 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <Loader className="animate-spin text-blue-400" size={20} />
              <div>
                <p className="text-white font-semibold">{processingStatus}</p>
                <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
                  <div className="bg-blue-500 h-2 rounded-full animate-pulse" style={{ width: '66%' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Results Section */}
      {showResults && predictions && (
        <div className="space-y-6">
          {/* Video Preview */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-white text-lg font-bold mb-4">Analysis Results</h3>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Skeleton Visualizer */}
              <div className="lg:col-span-2">
                <SkeletonVisualizer sessionId={sessionId} API_BASE={API_BASE} />
              </div>

              {/* Statistics */}
              <div className="space-y-3">
                <StatItem label="Total Frames" value={predictions.total_frames} />
                <StatItem label="Duration" value={`${(predictions.total_frames / 30).toFixed(1)}s`} />
                <StatItem
                  label="Fall Detected"
                  value={predictions.fall_detected ? '✓ Yes' : '✗ No'}
                  highlight={predictions.fall_detected}
                />
                <StatItem
                  label="Max Fall Confidence"
                  value={`${(maxFallConfidence * 100).toFixed(1)}%`}
                  highlight={predictions.fall_detected}
                />
                <StatItem
                  label="Primary Activity"
                  value={primaryActivity.toUpperCase()}
                  highlight={false}
                />
                <StatItem
                  label="Processing Status"
                  value={predictions.session.status}
                  highlight={predictions.session.status === 'completed'}
                />
              </div>
            </div>
          </div>

          {/* Predictions Table */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 overflow-auto">
            <h3 className="text-white text-lg font-bold mb-4">Frame-by-Frame Analysis</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-3 px-4 text-gray-300">Frame</th>
                  <th className="text-left py-3 px-4 text-gray-300">Time</th>
                  <th className="text-left py-3 px-4 text-gray-300">Activity</th>
                  <th className="text-left py-3 px-4 text-gray-300">Confidence</th>
                  <th className="text-left py-3 px-4 text-gray-300">Fall Conf</th>
                  <th className="text-left py-3 px-4 text-gray-300">Status</th>
                  <th className="text-left py-3 px-4 text-gray-300">Gait Risk</th>
                </tr>
              </thead>
              <tbody>
                {visiblePredictions.map((pred, idx) => (
                  <tr key={idx} className="border-b border-gray-700 hover:bg-gray-700/50">
                    <td className="py-3 px-4 text-gray-300">{pred.frame_idx}</td>
                    <td className="py-3 px-4 text-gray-300">{pred.timestamp_s.toFixed(2)}s</td>
                    <td className="py-3 px-4">
                      <span className="bg-blue-900/50 text-blue-300 px-2 py-1 rounded text-xs">
                        {pred.activity_label.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-300">{(pred.activity_confidence * 100).toFixed(1)}%</td>
                    <td className="py-3 px-4 text-gray-300">{(pred.fall_confidence * 100).toFixed(1)}%</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        pred.fall_status === 'FALLING'
                          ? 'bg-red-900/50 text-red-300'
                          : 'bg-green-900/50 text-green-300'
                      }`}>
                        {pred.fall_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-300">{pred.gait_risk_level}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {predictions.predictions.length > visiblePredictions.length && (
              <p className="text-gray-400 text-sm mt-4">
                Showing confirmed activity frames first. Initial OTHER rows are warm-up frames while the sequence model fills its context window. {predictions.predictions.length - visiblePredictions.length} more frames are hidden.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

function StatItem({ label, value, highlight }) {
  return (
    <div className={`p-4 rounded-lg ${highlight ? 'bg-red-900/20 border border-red-600' : 'bg-gray-700'}`}>
      <p className="text-gray-400 text-sm">{label}</p>
      <p className={`text-lg font-bold mt-1 ${highlight ? 'text-red-300' : 'text-white'}`}>{value}</p>
    </div>
  );
}

export default VideoAnalysis;

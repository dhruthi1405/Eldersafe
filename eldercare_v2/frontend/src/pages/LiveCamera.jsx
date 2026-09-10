import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Camera, Loader, Save, Square, Video } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import SkeletonVisualizer from '../components/SkeletonVisualizer';

const RECORDING_LIMIT_SECONDS = 30;

const LiveCamera = ({ API_BASE }) => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patients, setPatients] = useState([]);
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [recordedUrl, setRecordedUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [predictions, setPredictions] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [recordingSecondsLeft, setRecordingSecondsLeft] = useState(RECORDING_LIMIT_SECONDS);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);

  useEffect(() => {
    loadPatients();

    return () => {
      clearRecordingTimer();
      stopCameraStream();
      if (recordedUrl) {
        URL.revokeObjectURL(recordedUrl);
      }
    };
  }, []);

  useEffect(() => {
    if (!isRecording) {
      clearRecordingTimer();
      setRecordingSecondsLeft(RECORDING_LIMIT_SECONDS);
      return;
    }

    recordingTimerRef.current = window.setInterval(() => {
      setRecordingSecondsLeft((prev) => {
        if (prev <= 1) {
          stopRecording();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return clearRecordingTimer;
  }, [isRecording]);

  const maxFallConfidence = predictions?.predictions?.length
    ? Math.max(...predictions.predictions.map((pred) => pred.fall_confidence || 0))
    : 0;

  const activityCounts = useMemo(() => (
    predictions?.predictions?.length
      ? predictions.predictions.reduce((acc, pred) => {
          const label = pred.activity_label || 'other';
          const isWarmup = label === 'other' && (pred.activity_confidence || 0) === 0;
          if (!isWarmup) {
            acc[label] = (acc[label] || 0) + 1;
          }
          return acc;
        }, {})
      : {}
  ), [predictions]);

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
        headers: { Authorization: `Bearer ${token}` },
      });
      setPatients(response.data);
    } catch (error) {
      console.error('Failed to load patients:', error);
      toast.error('Failed to load patients');
    }
  };

  const clearRecordingTimer = () => {
    if (recordingTimerRef.current) {
      window.clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  };

  const stopCameraStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setIsStreaming(false);
  };

  const startCamera = async () => {
    if (!selectedPatient) {
      toast.error('Please select a patient');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user',
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsStreaming(true);
      toast.success('Camera started');
    } catch (error) {
      console.error('Failed to access camera:', error);
      toast.error('Failed to access camera. Check browser permissions.');
    }
  };

  const stopCamera = () => {
    if (isRecording) {
      stopRecording();
    }
    stopCameraStream();
  };

  const getSupportedMimeType = () => {
    if (typeof MediaRecorder === 'undefined') return '';

    const candidates = [
      'video/webm;codecs=vp9',
      'video/webm;codecs=vp8',
      'video/webm',
      'video/mp4',
    ];

    return candidates.find((mime) => MediaRecorder.isTypeSupported(mime)) || '';
  };

  const startRecording = () => {
    if (!streamRef.current) {
      toast.error('Start the camera first');
      return;
    }

    if (typeof MediaRecorder === 'undefined') {
      toast.error('This browser does not support webcam recording');
      return;
    }

    try {
      const mimeType = getSupportedMimeType();
      const recorder = mimeType
        ? new MediaRecorder(streamRef.current, { mimeType })
        : new MediaRecorder(streamRef.current);

      recordedChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const finalMimeType = mimeType || 'video/webm';
        const blob = new Blob(recordedChunksRef.current, { type: finalMimeType });
        recordedChunksRef.current = [];

        if (recordedUrl) {
          URL.revokeObjectURL(recordedUrl);
        }

        setRecordedBlob(blob);
        setRecordedUrl(URL.createObjectURL(blob));
        setIsRecording(false);
        toast.success('Recording saved. You can now process it.');
      };

      recorder.onerror = (event) => {
        console.error('MediaRecorder error:', event);
        setIsRecording(false);
        toast.error('Recording failed');
      };

      mediaRecorderRef.current = recorder;
      recorder.start(1000);
      setRecordedBlob(null);
      setRecordedUrl((oldUrl) => {
        if (oldUrl) {
          URL.revokeObjectURL(oldUrl);
        }
        return null;
      });
      setShowResults(false);
      setPredictions(null);
      setSessionId(null);
      setProcessingStatus('');
      setIsRecording(true);
      setRecordingSecondsLeft(RECORDING_LIMIT_SECONDS);
      toast.success('Recording started');
    } catch (error) {
      console.error('Failed to start recording:', error);
      toast.error('Failed to start recording');
    }
  };

  const stopRecording = () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder) return;

    if (recorder.state !== 'inactive') {
      recorder.stop();
    }
    mediaRecorderRef.current = null;
    clearRecordingTimer();
  };

  const uploadRecording = async () => {
    if (!recordedBlob) {
      toast.error('Record a clip first');
      return;
    }

    if (!selectedPatient) {
      toast.error('Please select a patient');
      return;
    }

    setUploading(true);
    setProcessingStatus('Preparing recording...');

    const extension = recordedBlob.type.includes('mp4') ? 'mp4' : 'webm';
    const file = new File(
      [recordedBlob],
      `live-camera-${Date.now()}.${extension}`,
      { type: recordedBlob.type || 'video/webm' },
    );

    const formData = new FormData();
    formData.append('file', file);
    formData.append('patient_id', String(selectedPatient));

    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API_BASE}/sessions/upload`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const total = progressEvent.total || 1;
          const percentCompleted = Math.round((progressEvent.loaded * 100) / total);
          setProcessingStatus(`Uploading recording... ${percentCompleted}%`);
        },
      });

      setSessionId(response.data.session_id);
      setProcessingStatus('Processing started...');
      toast.success('Recording uploaded. Processing started...');
      pollForCompletion(response.data.session_id);
    } catch (error) {
      console.error('Failed to upload recording:', error);
      toast.error('Failed to upload recording');
      setUploading(false);
      setProcessingStatus('');
    }
  };

  const pollForCompletion = async (sId) => {
    let attempts = 0;
    const maxAttempts = 300;

    const poll = async () => {
      if (attempts >= maxAttempts) {
        toast.error('Processing timeout');
        setUploading(false);
        setProcessingStatus('Processing timed out');
        return;
      }

      try {
        const token = localStorage.getItem('token');
        const response = await axios.get(`${API_BASE}/sessions/${sId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        setProcessingStatus(`Status: ${response.data.session.status}`);

        if (response.data.session.status === 'completed') {
          setPredictions(response.data);
          setShowResults(true);
          setUploading(false);
          toast.success('Live camera clip processed successfully');
          return;
        }

        if (response.data.session.status === 'failed') {
          setUploading(false);
          toast.error('Processing failed');
          return;
        }

        attempts += 1;
        window.setTimeout(poll, 2000);
      } catch (error) {
        console.error('Polling error:', error);
        attempts += 1;
        window.setTimeout(poll, 2000);
      }
    };

    poll();
  };

  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-white text-2xl font-bold mb-6">Live Camera Recording</h2>

        <div className="mb-6">
          <label className="block text-gray-300 font-semibold mb-3">Select Patient</label>
          <select
            value={selectedPatient || ''}
            onChange={(e) => setSelectedPatient(e.target.value ? parseInt(e.target.value, 10) : null)}
            disabled={isStreaming || uploading}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white"
          >
            <option value="">-- Choose a patient --</option>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.full_name} ({patient.patient_id})
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center border border-gray-700">
            {isStreaming ? (
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-center text-gray-500">
                <Camera size={64} className="mx-auto mb-3" />
                <p>Camera preview</p>
              </div>
            )}
          </div>

          <div className="bg-gray-900/50 rounded-lg border border-gray-700 p-4">
            <h3 className="text-white font-semibold mb-3">Recorded Clip</h3>
            {recordedUrl ? (
              <video
                src={recordedUrl}
                controls
                className="w-full rounded-lg border border-gray-700 bg-black mb-4"
              />
            ) : (
              <div className="aspect-video bg-black rounded-lg border border-gray-700 flex items-center justify-center text-gray-500 mb-4">
                <div className="text-center">
                  <Video size={48} className="mx-auto mb-2" />
                  <p>No recording yet</p>
                </div>
              </div>
            )}

            <div className="space-y-2 text-sm text-gray-300">
              <p>Maximum clip length: {RECORDING_LIMIT_SECONDS} seconds</p>
              {isRecording && (
                <p className="text-red-300 font-semibold">
                  Recording... {recordingSecondsLeft}s remaining
                </p>
              )}
              {processingStatus && (
                <p className="text-blue-300">{processingStatus}</p>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-3 mt-6">
          <button
            onClick={startCamera}
            disabled={isStreaming || uploading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg flex items-center gap-2 transition-colors"
          >
            <Camera size={20} /> Start Camera
          </button>

          <button
            onClick={startRecording}
            disabled={!isStreaming || isRecording || uploading}
            className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg flex items-center gap-2 transition-colors"
          >
            <Video size={20} /> Start Recording
          </button>

          <button
            onClick={stopRecording}
            disabled={!isRecording}
            className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg flex items-center gap-2 transition-colors"
          >
            <Square size={20} /> Stop Recording
          </button>

          <button
            onClick={uploadRecording}
            disabled={!recordedBlob || uploading || isRecording}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg flex items-center gap-2 transition-colors"
          >
            {uploading ? <Loader size={20} className="animate-spin" /> : <Save size={20} />}
            Process Recording
          </button>

          <button
            onClick={stopCamera}
            disabled={!isStreaming}
            className="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 text-white px-6 py-3 rounded-lg transition-colors"
          >
            Stop Camera
          </button>
        </div>
      </div>

      {uploading && (
        <div className="bg-blue-900/20 border border-blue-600 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <Loader className="animate-spin text-blue-400" size={20} />
            <div>
              <p className="text-white font-semibold">{processingStatus || 'Processing recording...'}</p>
              <p className="text-blue-300 text-sm">Your recorded webcam clip is being analyzed by the backend.</p>
            </div>
          </div>
        </div>
      )}

      {showResults && predictions && (
        <div className="space-y-6">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-white text-lg font-bold mb-4">Live Camera Analysis Results</h3>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <SkeletonVisualizer sessionId={sessionId} API_BASE={API_BASE} />
              </div>

              <div className="space-y-3">
                <StatItem label="Total Frames" value={predictions.total_frames} />
                <StatItem label="Duration" value={`${(predictions.total_frames / 30).toFixed(1)}s`} />
                <StatItem
                  label="Fall Detected"
                  value={predictions.fall_detected ? 'Yes' : 'No'}
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

export default LiveCamera;

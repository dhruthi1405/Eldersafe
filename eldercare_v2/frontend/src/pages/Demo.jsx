import React, { useState } from 'react';
import { Play, Lightbulb, Zap } from 'lucide-react';

const Demo = ({ API_BASE }) => {
  const [selectedDemo, setSelectedDemo] = useState(null);

  const demos = [
    {
      id: 'video_upload',
      title: 'Video Upload & Analysis',
      description: 'Upload a video file and watch the AI analyze it in real-time',
      icon: '📹',
      steps: [
        'Select a patient from the list',
        'Upload a video file (MP4, AVI, MOV)',
        'AI processes the video and detects falls',
        'View annotated skeleton video and predictions',
      ]
    },
    {
      id: 'live_camera',
      title: 'Live Camera Detection',
      description: 'Real-time fall detection from webcam feed',
      icon: '📷',
      steps: [
        'Select a patient',
        'Enable camera access',
        'AI analyzes live video stream',
        'Automatic fall alerts if detected',
      ]
    },
    {
      id: 'patient_monitoring',
      title: 'Patient Monitoring',
      description: 'Track patient activities and health metrics',
      icon: '📊',
      steps: [
        'View patient profile and history',
        'Check 30-day activity timeline',
        'Monitor gait analysis results',
        'Track fall incidents and trends',
      ]
    },
    {
      id: 'sos_alerts',
      title: 'SOS Alert System',
      description: 'Real-time notifications to caregivers',
      icon: '🚨',
      steps: [
        'Fall detected automatically',
        'Caretaker receives instant notification',
        'Alert includes video timestamp and confidence',
        'One-click incident resolution',
      ]
    }
  ];

  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-white text-3xl font-bold mb-2">Feature Demo</h2>
        <p className="text-gray-400">Learn how ElderCare AI works</p>
      </div>

      {/* Demo Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {demos.map((demo) => (
          <div
            key={demo.id}
            className="bg-gray-800 rounded-lg border border-gray-700 hover:border-blue-500 transition-all cursor-pointer group"
            onClick={() => setSelectedDemo(selectedDemo === demo.id ? null : demo.id)}
          >
            <div className="p-6">
              <div className="text-4xl mb-3">{demo.icon}</div>
              <h3 className="text-white font-bold text-lg mb-2">{demo.title}</h3>
              <p className="text-gray-400 text-sm mb-4">{demo.description}</p>
              
              {selectedDemo === demo.id && (
                <div className="mt-4 pt-4 border-t border-gray-700 space-y-2">
                  {demo.steps.map((step, idx) => (
                    <div key={idx} className="flex gap-2 text-gray-300 text-sm">
                      <span className="text-blue-400 font-bold flex-shrink-0">{idx + 1}.</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              )}
              
              <button className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg flex items-center justify-center gap-2 group-hover:translate-x-1 transition-transform">
                <Play size={16} /> Learn More
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Features Overview */}
      <div className="bg-gradient-to-br from-blue-900/20 to-cyan-900/20 rounded-lg p-8 border border-blue-600/50">
        <h3 className="text-white text-xl font-bold mb-4 flex items-center gap-2">
          <Lightbulb className="text-yellow-400" size={24} />
          Key Features
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300">
          <div className="flex gap-2">
            <Zap className="text-blue-400 flex-shrink-0" size={20} />
            <span><strong>AI-Powered Fall Detection</strong> - Detects falls in real-time with 95%+ accuracy</span>
          </div>
          <div className="flex gap-2">
            <Zap className="text-green-400 flex-shrink-0" size={20} />
            <span><strong>Activity Recognition</strong> - Identifies 7 different daily activities</span>
          </div>
          <div className="flex gap-2">
            <Zap className="text-orange-400 flex-shrink-0" size={20} />
            <span><strong>Gait Analysis</strong> - Assesses fall risk based on walking patterns</span>
          </div>
          <div className="flex gap-2">
            <Zap className="text-red-400 flex-shrink-0" size={20} />
            <span><strong>Instant Alerts</strong> - Notifies caregivers immediately when fall detected</span>
          </div>
          <div className="flex gap-2">
            <Zap className="text-purple-400 flex-shrink-0" size={20} />
            <span><strong>Historical Timeline</strong> - 30-day activity and incident tracking</span>
          </div>
          <div className="flex gap-2">
            <Zap className="text-indigo-400 flex-shrink-0" size={20} />
            <span><strong>Multi-User Access</strong> - Doctors, caretakers, and admins</span>
          </div>
        </div>
      </div>

      {/* Quick Start */}
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700">
        <h3 className="text-white text-xl font-bold mb-4">Quick Start</h3>
        <ol className="space-y-3 text-gray-300">
          <li className="flex gap-3">
            <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 font-semibold">1</span>
            <span>Go to <strong>Patient Management</strong> and add a patient</span>
          </li>
          <li className="flex gap-3">
            <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 font-semibold">2</span>
            <span>Navigate to <strong>Upload Video</strong> or <strong>Live Camera</strong></span>
          </li>
          <li className="flex gap-3">
            <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 font-semibold">3</span>
            <span>Select your patient and start analyzing</span>
          </li>
          <li className="flex gap-3">
            <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 font-semibold">4</span>
            <span>View results, predictions, and alerts</span>
          </li>
        </ol>
      </div>
    </div>
  );
};

export default Demo;

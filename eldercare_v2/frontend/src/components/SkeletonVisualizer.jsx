import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Download } from 'lucide-react';

const SkeletonVisualizer = ({ sessionId, API_BASE }) => {
  const [skeletonData, setSkeletonData] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [currentFrame, setCurrentFrame] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const canvasRef = useRef(null);

  useEffect(() => {
    fetchSkeletonData();

    return () => {
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, [sessionId]);

  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentFrame((prev) => {
        if (!skeletonData) return prev;
        return (prev + 1) % skeletonData.skeleton_frames.length;
      });
    }, 30); // ~30 FPS

    return () => clearInterval(interval);
  }, [isPlaying, skeletonData]);

  useEffect(() => {
    if (skeletonData) {
      drawSkeleton();
    }
  }, [currentFrame, skeletonData]);

  const fetchSkeletonData = async () => {
    try {
      setLoadError('');
      setSkeletonData(null);
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
        setVideoUrl(null);
      }

      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/sessions/${sessionId}/video/skeleton`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error(`Skeleton result failed with ${response.status}`);
      }

      const contentType = response.headers.get('content-type') || '';
      const contentDisposition = response.headers.get('content-disposition') || '';
      if (
        contentType.includes('video') ||
        contentType.includes('octet-stream') ||
        contentDisposition.includes('.mp4')
      ) {
        const blob = await response.blob();
        setVideoUrl(URL.createObjectURL(blob));
        return;
      }

      if (contentType.includes('json')) {
        const data = await response.json();
        setSkeletonData(data);
      }
    } catch (error) {
      console.error('Failed to fetch skeleton data:', error);
      setLoadError('Could not load the skeleton result.');
    }
  };

  const drawSkeleton = () => {
    if (!canvasRef.current || !skeletonData) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const frame = skeletonData.skeleton_frames[currentFrame];

    if (!frame) return;

    // Clear canvas
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw keypoints
    const scale = 200; // Scale factor for display
    const keypoints = frame.keypoints;

    // Draw skeleton lines (COCO format connections)
    const connections = [
      [0, 1], [1, 2],           // head
      [0, 3], [3, 4], [4, 5],   // left arm
      [0, 6], [6, 7], [7, 8],   // right arm
      [0, 9], [9, 10], [10, 11], // left leg
      [0, 12], [12, 13], [13, 14], // right leg
    ];

    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth = 2;
    connections.forEach(([start, end]) => {
      if (keypoints[start] && keypoints[end]) {
        ctx.beginPath();
        ctx.moveTo(keypoints[start][0] * scale, keypoints[start][1] * scale);
        ctx.lineTo(keypoints[end][0] * scale, keypoints[end][1] * scale);
        ctx.stroke();
      }
    });

    // Draw keypoints
    ctx.fillStyle = '#ff00ff';
    keypoints.forEach((point) => {
      ctx.beginPath();
      ctx.arc(point[0] * scale, point[1] * scale, 4, 0, 2 * Math.PI);
      ctx.fill();
    });

    // Draw info text
    ctx.fillStyle = '#fff';
    ctx.font = '14px Arial';
    ctx.fillText(`Frame: ${frame.frame_idx} / ${skeletonData.total_frames}`, 10, 20);
    ctx.fillText(`Time: ${frame.timestamp.toFixed(2)}s`, 10, 40);
    ctx.fillText(`Activity: ${frame.activity}`, 10, 60);
    ctx.fillText(`Fall Status: ${frame.fall_status}`, 10, 80);
    ctx.fillText(`Confidence: ${(frame.confidence * 100).toFixed(1)}%`, 10, 100);
  };

  if (videoUrl) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between gap-4 mb-4">
          <h3 className="text-white text-lg font-bold">Skeleton Overview Video</h3>
          <a
            href={videoUrl}
            download={`skeleton-session-${sessionId}.mp4`}
            className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded-lg flex items-center gap-2 text-sm"
          >
            <Download size={16} />
            Download
          </a>
        </div>
        <video
          src={videoUrl}
          controls
          autoPlay
          muted
          className="w-full rounded-lg border border-gray-600 bg-black"
        />
      </div>
    );
  }

  if (loadError) {
    return <div className="text-red-300">{loadError}</div>;
  }

  if (!skeletonData) {
    return <div className="text-white">Loading skeleton data...</div>;
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h3 className="text-white text-lg font-bold mb-4">Skeleton Visualization</h3>

      {/* Canvas for skeleton display */}
      <canvas
        ref={canvasRef}
        width={400}
        height={600}
        className="bg-black rounded-lg border border-gray-600 w-full mb-4"
      />

      {/* Controls */}
      <div className="flex items-center gap-4 mb-4">
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
        >
          {isPlaying ? <Pause size={18} /> : <Play size={18} />}
          {isPlaying ? 'Pause' : 'Play'}
        </button>

        <input
          type="range"
          min="0"
          max={skeletonData.total_frames - 1}
          value={currentFrame}
          onChange={(e) => {
            setCurrentFrame(parseInt(e.target.value));
            setIsPlaying(false);
          }}
          className="flex-1"
        />

        <span className="text-gray-300 text-sm">
          {currentFrame + 1} / {skeletonData.total_frames}
        </span>
      </div>

      {/* Mode indicator */}
      {skeletonData.mode === 'demo' && (
        <div className="bg-blue-900/20 border border-blue-600 rounded p-3 text-blue-300 text-sm">
          📊 Demo Mode: Showing skeleton data. Real ML pipeline would extract actual pose keypoints.
        </div>
      )}
    </div>
  );
};

export default SkeletonVisualizer;

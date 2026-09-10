# Pipeline - ML Data Processing & Inference

**The heart of the ML system: Pose extraction → Temporal models → Predictions**

---

## 📋 Overview

The pipeline handles **end-to-end ML processing**:

1. **Video Ingestion** → Raw MP4/AVI files
2. **Pose Extraction** → Hybrid YOLO v8 + MediaPipe (17 COCO keypoints per frame)
3. **Feature Extraction** → Convert poses to 51-dim feature vectors
4. **Temporal Buffering** → Collect 30 frames (~1 second @ 30fps)
5. **Model Inference** → TCN-BiLSTM models for activity + fall detection
6. **Risk Assessment** → Gait analyzer computes fall risk biomechanics
7. **Alert Generation** → SOSDetector triggers 5 alert types
8. **Output** → Annotated skeleton video + CSV predictions + alerts

---

## 🚀 Quick Start

### **Process a Single Video**
```bash
cd /path/to/ElderCareProject
python pipeline/inference.py --source video.mp4 --show-live
# Outputs: skeleton_video.mp4 + predictions.csv
```

### **Batch Process Dataset**
```bash
python run.py stage-extract
# Extracts poses from all videos in datasets/raw/ → datasets/processed/pose/
```

### **Train Models**
```bash
python run.py stage-train
# Trains binary_fall_best.pth and activity_best.pth
```

### **Full Pipeline from Backend** (via Docker)
```bash
curl -X POST http://localhost:8000/api/sessions/upload \
  -F "file=@patient_video.mp4" \
  -F "patient_id=1"
# Backend automatically calls InferenceEngine.run_video()
```

---

## 📂 Files & Purpose

### **Core Inference**

#### **`inference.py`** ⭐ MAIN ENTRY POINT
**Purpose:** Production-ready inference engine for video processing

**Key Class:** `InferenceEngine`

```python
from pipeline.inference import InferenceEngine

engine = InferenceEngine(
    root_dir="/path/to/models",
    enable_alerts=True,
    show_live=False
)

# Process video - returns list of predictions
predictions = engine.run_video(
    source="patient_video.mp4",
    out_video="skeleton.mp4",
    out_csv="predictions.csv",
    frame_skip=3  # Process every 3rd frame for speed
)
```

**Returns:**
```python
[
  {
    "frame_idx": 0,
    "timestamp_s": 0.0,
    "label": "walk",
    "confidence": 0.95,
    "fall_confidence": 0.02,
    "fall_status": "NOT FALLING",
    "activity_label": "walking",
    "activity_confidence": 0.97,
    "gait_risk": 0.35,
    "gait_level": "LOW"
  },
  ...
]
```

**Features:**
- Loads both models (fall + activity)
- Manages frame buffering
- Calls GaitAnalyzer for risk scoring
- Integrates with SOSDetector for alerts
- Renders skeleton video with pose overlays
- Lazy-loads alert modules (graceful degradation if missing)
- GPU/CPU automatic selection

**Configuration from `configs/config.py`:**
```python
MODEL_CONFIG = {
    "fall_model_path": "models/binary_fall_best.pth",
    "activity_model_path": "models/activity_best.pth",
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "confidence_threshold": 0.35,
}
```

**Data Flow Inside Engine:**
```
1. Open video with cv2.VideoCapture()
2. For each frame:
   a. HybridPoseExtractor.extract(frame) → pose dict
   b. Convert to feature vector (51 dims)
   c. Add to frame_buffer (max 30 frames)
   d. If buffer full:
      - Run models on sequence
      - Update gait analyzer
      - Check for alerts
      - Append to predictions list
   e. Write skeleton frame to output video
3. Return predictions list + write CSV
```

---

#### **`pose_extractor.py`** 
**Purpose:** Hybrid YOLO v8 + MediaPipe pose extraction

**Key Class:** `HybridPoseExtractor`

```python
from pipeline.pose_extractor import HybridPoseExtractor, YOLO_KP_NAMES

extractor = HybridPoseExtractor(
    yolo_weights="yolov8n-pose.pt",
    conf_threshold=0.35
)

# Process frame
frame = cv2.imread("image.jpg")
keypoints = extractor.extract(frame)

# keypoints = {
#   "nose": (0.5, 0.3, 0.95),           # (x_norm, y_norm, confidence)
#   "left_eye": (0.48, 0.25, 0.92),
#   "right_eye": (0.52, 0.25, 0.93),
#   ...
# }
```

**COCO 17 Keypoints:**
```
Head (5):       nose, left_eye, right_eye, left_ear, right_ear
Upper Body (6): left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist
Lower Body (6): left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle
```

**Hybrid Extraction Strategy:**
1. **YOLO v8-pose** detects bounding box + 17 keypoints
   - Fast, good for full-body poses
   - Input: RGB frame
   - Output: xy coordinates + confidence
   
2. **MediaPipe Holistic** extracts 33 landmarks
   - Robust, handles occlusion better
   - Input: RGB frame
   - Output: xyz + visibility score

3. **Merge logic:**
   - For each of 17 COCO joints
   - If both sources confident (>0.35): blend them (weighted average)
   - Else: take highest confidence source
   - Result: Best of both worlds

**Visualization:**
```python
# Render skeleton on frame
skeleton_frame = extractor.render_skeleton(
    frame,
    keypoints,
    label="walking",
    confidence=0.95
)
cv2.imwrite("skeleton_overlay.jpg", skeleton_frame)
```

**Color scheme:**
- 🔵 Head (blue): Eyes, ears, nose
- 🔷 Arms (cyan): Shoulders, elbows, wrists
- 🟢 Torso (green): Connection between shoulders and hips
- 🔴 Legs (magenta): Hips, knees, ankles

---

#### **`gait_analyzer.py`**
**Purpose:** Fall risk assessment via biomechanics (proactive detection)

**Key Class:** `GaitAnalyzer`

```python
from pipeline.gait_analyzer import GaitAnalyzer

analyzer = GaitAnalyzer()

# Feed with poses frame by frame
for frame_idx, keypoints in enumerate(pose_sequence):
    result = analyzer.update(keypoints, frame_idx)
    # result = {
    #   "risk_score": 0.45,      # 0-1
    #   "risk_level": "MEDIUM",  # LOW / MEDIUM / HIGH
    #   "features": {...}        # Detailed biomechanics
    # }
```

**Risk Factors Analyzed:**

| Factor | Healthy | At-Risk | High-Risk |
|--------|---------|---------|-----------|
| **COM Instability** | < 0.10 | 0.10-0.20 | > 0.20 |
| **Trunk Sway** | < 0.05 | 0.05-0.10 | > 0.10 |
| **Step Symmetry** | > 0.90 | 0.80-0.90 | < 0.80 |
| **Knee Flexion** | Normal | Reduced | Very reduced |

**Risk Thresholds (from config):**
```python
GAIT_THRESHOLDS = {
    "high_risk_score": 0.70,      # High risk if score > 0.70
    "medium_risk_score": 0.40,    # Medium risk if score > 0.40
    "min_gait_speed_ms": 0.60,    # Meters per second
    "max_trunk_sway": 0.08,       # Normalized by shoulder width
    "min_step_symmetry": 0.85,    # L/R symmetry ratio
    "max_com_instability": 0.10,  # Normalized by hip width
}
```

**Use Case:**
- Elder walks in video (not falling, but unsteady gait)
- Model predicts "walk" + 0.05 fall confidence
- GaitAnalyzer detects high trunk sway + COM instability
- Raises HIGH RISK alert to caregiver → **proactive intervention**

---

### **Data Extraction (Batch Processing)**

#### **`extract_pipeline.py`**
**Purpose:** Extract poses from raw video datasets in batch

**Functions:**

```python
# Process specific dataset
process_le2i_dataset(output_csv="poses_le2i.csv")
process_multiple_cameras_dataset()
process_hmdb51_dataset()
process_generic_dataset(folder_path="datasets/raw/my_videos/")

# Merge all into one CSV
merge_all_datasets(output_csv="all_poses.csv")
```

**Input:** Raw videos from `datasets/raw/`
**Output:** CSV files in `datasets/processed/pose/`

**CSV Format:**
```
dataset_name,video,frame_idx,label,nose_x,nose_y,nose_conf,left_eye_x,...,right_ankle_conf
le2i,fall_001.mp4,0,1,0.5,0.3,0.95,0.48,0.25,0.92,...,0.45
le2i,fall_001.mp4,1,1,0.5,0.32,0.94,0.49,0.27,0.91,...,0.46
```

---

#### **`clean_*.py` Files**
**Purpose:** Data cleaning and normalization

Files:
- `clean_single_csv.py` - Clean one CSV file
- `clean_le2i_csv.py` - Format conversion for LE2I dataset
- `clean_multiple_cameras_csv.py` - Handle multi-view videos
- `clean_all_poses.py` - Bulk cleaning

**Operations:**
- Remove null/NaN values
- Normalize coordinates (0-1 range)
- Balance class distributions (equal falls & non-falls)
- Remove outliers
- Forward-fill missing values

```bash
python pipeline/clean_all_poses.py
# Input: datasets/processed/pose/*.csv
# Output: datasets/processed/pose/*_cleaned.csv
```

---

### **Supporting Utilities**

#### **`dataset_loader.py`**
```python
# Scan raw dataset directory and build manifest
manifest = build_manifest("datasets/raw/")
# Returns: CSV with all videos + auto-detected labels
```

#### **`normalize_all_poses.py`**
```python
# Normalize coordinate ranges across dataset
normalize_dataset("datasets/processed/all_poses.csv")
```

#### **`synthetic_generator.py`**
```python
# Generate synthetic pose sequences for training
# Useful for data augmentation
synthetic_poses = generate_synthetic_falls(count=100)
```

#### **`merge_cleaned.py`**
```python
# Combine multiple CSV files
merge_datasets(["cleaned_1.csv", "cleaned_2.csv"], output="merged.csv")
```

---

## 🔄 Data Flow Example: End-to-End

```
Raw Video (patient_123.mp4)
   ↓
[InferenceEngine initialized]
   - Load fall model from models/binary_fall_best.pth
   - Load activity model from models/activity_best.pth
   - Create HybridPoseExtractor
   - Create GaitAnalyzer
   ↓
[For each frame in video]
   - HybridPoseExtractor.extract(frame)
     ├─ YOLO v8 detects 17 keypoints
     ├─ MediaPipe detects 33 landmarks
     └─ Merge → best 17 keypoints
   - Convert keypoints to 51-dim feature vector
   - frame_buffer.append(features)
   ↓
[When buffer has 30 frames]
   - Stack features: shape (30, 51)
   - Run through Activity model → 7-class output
     └─ Most likely: "walking" (0.95 conf)
   - Run through Fall model → binary output
     └─ Most likely: "no_fall" (0.98 conf)
   - GaitAnalyzer.update() → risk assessment
     └─ Risk score: 0.35 (LOW)
   ↓
[Check for alerts]
   - Not falling, activity is walking, risk is low
   - No alerts triggered
   ↓
[Append to predictions list]
   {
     "frame_idx": 30,
     "timestamp_s": 1.0,
     "activity_label": "walking",
     "activity_confidence": 0.95,
     "fall_confidence": 0.02,
     "fall_status": "NOT FALLING",
     "gait_risk": 0.35,
     "gait_level": "LOW"
   }
   ↓
[Render skeleton frame]
   - Draw 17 keypoints + connections
   - Label: "WALKING 95%"
   - Write to output video (skeleton_123.mp4)
   ↓
[Repeat for all frames]
   ↓
[Final outputs]
   ✓ skeleton_123.mp4 (video with pose overlays)
   ✓ predictions_123.csv (frame-by-frame data)
   ✓ Alert notifications (if any triggered)
```

---

## ⚙️ Configuration

All settings in `configs/config.py`:

```python
# Model paths
MODEL_CONFIG = {
    "fall_model_path": "models/binary_fall_best.pth",
    "activity_model_path": "models/activity_best.pth",
    "device": "cuda",  # or "cpu"
}

# Alert thresholds
ALERT_THRESHOLDS = {
    "fall_confidence_threshold": 0.75,
    "wave_count_trigger": 3,
    "wave_window_seconds": 10,
    "prolonged_sleep_hours": 15,
    "inactivity_alert_minutes": 120,
    "alert_cooldown_minutes": 30,
}

# Gait analysis
GAIT_THRESHOLDS = {
    "high_risk_score": 0.70,
    "medium_risk_score": 0.40,
    "max_trunk_sway": 0.08,
    "min_step_symmetry": 0.85,
}
```

---

## 🚨 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Cannot import pose_extractor" | Wrong working directory | Run from `ElderCareProject/` root |
| YOLO model downloads (1st run) | Model weights not cached | Wait ~5min for download, or pre-download |
| "CUDA out of memory" | GPU too small | Set `DEVICE=cpu` in config, or reduce batch size |
| No keypoints detected | Person too small/obscured | Increase video resolution, lower `conf_threshold` |
| Skeleton video won't generate | Video codec issue | Try MP4V codec or different input format |

---

## 📊 Performance Metrics

| Task | Time (GPU) | Time (CPU) | Notes |
|------|-----------|-----------|-------|
| YOLO pose extraction (1 frame) | ~5ms | ~50ms | Nano model |
| MediaPipe extraction (1 frame) | ~10ms | ~30ms | Fast variant |
| Model inference (30 frames) | ~20ms | ~200ms | Batch inference |
| Gait analysis | ~5ms | ~5ms | Lightweight math |
| Full video (500 frames @ 30fps) | ~10sec | ~90sec | With frame_skip=3 |

**Tips for Performance:**
1. Use `frame_skip=3` or higher for speed
2. Use GPU if available (`cuda`)
3. Reduce video resolution if possible
4. Process offline (don't stream live)

---

## 🔗 Integration Points

### **From Backend**
```python
# eldercare_v2/backend/main.py
from pipeline.inference import InferenceEngine

engine = InferenceEngine(root_dir="/app")
predictions = engine.run_video(
    source="/app/uploads/video.mp4",
    out_video="/app/outputs/skeleton.mp4",
    out_csv="/app/outputs/predictions.csv"
)

# Store predictions in database
for pred in predictions:
    db.add(Prediction(**pred))
db.commit()
```

### **From Training**
```python
# models/binary_fall_train.py
from pipeline.pose_extractor import YOLO_KP_NAMES

# Load dataset with poses
df = pd.read_csv("datasets/processed/all_poses.csv")

# Extract features for model input
features = df[[f"{name}_{axis}" for name in YOLO_KP_NAMES 
               for axis in ["x", "y", "conf"]]].values
```

---

## 📚 Further Reading

- [models/README.md](../models/README.md) - Model architecture & training
- [configs/README.md](../configs/README.md) - All configuration options
- [alerts/README.md](../alerts/README.md) - Alert system integration
- [AGENTS.md](../AGENTS.md) - Full project context

---

**Status:** ✅ Production Ready  
**Last Updated:** December 2025

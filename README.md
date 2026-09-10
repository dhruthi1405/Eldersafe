# ElderCare AI v2.0 - Complete Project Overview

**Professional AI-Powered Fall Detection & Healthcare Monitoring System**

> A full-stack healthcare platform combining modern web technology with cutting-edge ML pose estimation for real-time fall detection and elderly care monitoring.

---

## 🏗️ Project Architecture

```
ElderCareProject/
├── eldercare_v2/              # ⭐ MAIN PRODUCTION APP (Start here!)
│   ├── backend/               # FastAPI REST API + async processing
│   ├── frontend/              # React 18 + Tailwind CSS dashboard
│   ├── database/              # PostgreSQL schema
│   └── docker-compose.yml     # Complete infrastructure orchestration
│
├── pipeline/                  # ML data processing pipeline
│   ├── inference.py           # 🚀 Main inference engine (produces predictions)
│   ├── pose_extractor.py      # Hybrid YOLO v8 + MediaPipe pose extraction
│   ├── gait_analyzer.py       # Fall risk assessment via biomechanics
│   └── extract_pipeline.py    # Batch processing for datasets
│
├── models/                    # Trained ML models
│   ├── binary_fall_best.pth   # Fall detection (95%+ accuracy)
│   ├── activity_best.pth      # Activity recognition (7 classes)
│   ├── tcn_lstm_model.py      # Model architecture (TCN-BiLSTM)
│   ├── binary_fall_train.py   # Fall training script
│   └── activity_train.py      # Activity training script
│
├── alerts/                    # Real-time SOS system
│   ├── sos_detector.py        # 5 alert types: fall, wave, sleep, inactivity, risk
│   ├── email_alert.py         # Gmail SMTP notifications
│   └── firebase_alert.py      # Mobile push notifications
│
├── configs/                   # Centralized configuration
│   └── config.py              # All thresholds, paths, credentials in one place
│
├── datasets/                  # Data storage
│   ├── raw/                   # Raw videos stored locally
│   └── processed/             # Extracted poses as CSV files
│
├── eldercare_flutter_app/     # Mobile app (separate, not fully integrated)
│   └── lib/                   # Flutter code
│
├── run.py                     # Master CLI for entire pipeline
└── AGENTS.md                  # AI agent instructions
```

---

## 🚀 Quick Start (30 seconds)

---

## 🎬 Demo Video

The demo video is part of the repository, but GitHub does not auto-play videos when someone opens the repo page. Viewers need to click the file or the link below to play it.

- [Open demo video](Demo%20video.mp4)

If you want an always-visible preview on the README itself, the usual option is to add a short animated GIF or a linked thumbnail instead of relying on auto-play.

### **Option 1: Docker (Recommended)**
```bash
cd eldercare_v2
docker-compose up --build
# Services ready:
#   Frontend: http://localhost:5173
#   Backend: http://localhost:8000/docs (Swagger)
#   Database: localhost:5432
```

### **Option 2: Manual Setup**
```bash
# Terminal 1 - Backend
cd eldercare_v2/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 2 - Frontend
cd eldercare_v2/frontend
npm install
npm run dev

# Terminal 3 - Database (requires PostgreSQL installed)
psql -U eldercare_user -d eldercare_db < database/schema.sql
```

---

## 📊 What This System Does

### **Core Features**
1. **Video Processing** - Upload videos of elderly patients
2. **Pose Estimation** - Extract skeleton keypoints (17 joints per frame) using YOLO v8 + MediaPipe
3. **Activity Recognition** - Classify: walking, sitting, standing, eating, sleeping, waving, other
4. **Fall Detection** - Real-time binary classification with 95%+ accuracy
5. **Gait Analysis** - Proactive fall risk assessment using biomechanics
6. **Alert System** - 5 alert types (fall, wave-SOS, prolonged sleep, inactivity, high risk)
7. **Notifications** - Email + Firebase push to caregiver devices
8. **Dashboard** - Real-time timeline, alerts, patient management, statistics

---

## 📁 Folder Breakdown

### **🎯 eldercare_v2/** (Production Application)
**Status:** ✅ Complete and running

| Component | Purpose | Tech Stack | Port |
|-----------|---------|-----------|------|
| **backend/** | REST API + async processing | FastAPI, PostgreSQL, SQLAlchemy | 8000 |
| **frontend/** | Web dashboard | React 18, Tailwind, Recharts, Vite | 5173 |
| **database/** | Schema & migrations | PostgreSQL 15 | 5432 |
| **docker-compose.yml** | Orchestration | 4 services (postgres, backend, frontend, redis) | - |

**Read:** [eldercare_v2/README.md](eldercare_v2/README.md) for detailed setup

---

### **🧠 pipeline/** (ML Data Processing)
**Status:** ✅ Complete

| File | Purpose | Input | Output |
|------|---------|-------|--------|
| **inference.py** | Main inference engine | Video file (.mp4, .avi) | Predictions + skeleton video |
| **pose_extractor.py** | Hybrid pose detection | Video frames | 17 COCO keypoints per frame |
| **gait_analyzer.py** | Fall risk scoring | Pose sequences | Risk score (0-1) + level |
| **extract_pipeline.py** | Batch processing | Raw video datasets | CSV pose files |

**Read:** [pipeline/README.md](pipeline/README.md) for data flows

---

### **🤖 models/** (Trained ML Models)
**Status:** ✅ Complete

| File | Type | Classes | Accuracy | Size |
|------|------|---------|----------|------|
| **binary_fall_best.pth** | PyTorch model | fall / no_fall | 95%+ | ~50MB |
| **activity_best.pth** | PyTorch model | 7 activities | - | - |
| **tcn_lstm_model.py** | Architecture | - | - | - |

**Read:** [models/README.md](models/README.md) for training & model details

---

### **🚨 alerts/** (SOS Detection & Notifications)
**Status:** ✅ Complete

5 Alert Types:
- **FALL** - Immediate fall detection (threshold: 0.75+ confidence)
- **WAVE_SOS** - 3+ wave gestures in 10 second window
- **PROLONGED_SLEEP** - Sleeping > 15 hours continuously
- **PROLONGED_INACTIVITY** - No movement for 2+ hours
- **FALL_RISK** - Gait analysis high-risk warning (0.70+ score)

**Read:** [alerts/README.md](alerts/README.md) for configuration

---

### **⚙️ configs/** (Configuration Management)
**Status:** ✅ Complete

Single source of truth for all settings:
```python
# Access from anywhere:
from configs.config import ALERT_THRESHOLDS, MODEL_CONFIG, EMAIL_CONFIG
```

**Read:** [configs/README.md](configs/README.md) for all settings

---

### **📦 datasets/** (Data Storage)
**Status:** ⚠️ Partial (structure exists, some datasets may be placeholder)

Raw datasets are stored locally under `datasets/raw/` and are not meant to be committed to GitHub.

Typical local dataset folders include fall videos, activity recognition videos, and multi-camera capture sets.

**Read:** [datasets/README.md](datasets/README.md) for management

---

### **📱 eldercare_flutter_app/** (Mobile App)
**Status:** ⚠️ Incomplete (separate project, not fully integrated)

- Firebase integration
- Push notification handling
- Alert viewer
- **Issue:** No documented API contracts with backend

### **🖼️ App Screenshots**

The `App/` folder contains a few UI screenshots from the mobile experience:

- [dashboard.jpeg](App/dashboard.jpeg)
- [notification.jpeg](App/notification.jpeg)
- [Dasshboard.jpeg](App/Dasshboard.jpeg)

---

## 🔄 Data Flow Pipeline

```
User uploads video
    ↓
Backend receives /api/sessions/upload
    ↓
InferenceEngine.run_video() spawned
    ↓
HybridPoseExtractor processes each frame
    ├─ YOLO v8 detects 17 keypoints
    └─ MediaPipe extracts 33 landmarks → merged
    ↓
Temporal buffering (30 frames = ~1 second @ 30fps)
    ↓
TCN-BiLSTM models (activity + fall)
    ├─ Activity Classifier → 7 classes
    └─ Fall Detector → fall/no-fall (binary)
    ↓
GaitAnalyzer computes risk score
    ↓
SOSDetector checks for alerts
    ├─ Fall? Send FALL alert
    ├─ Wave? Send WAVE_SOS alert
    └─ etc...
    ↓
EmailAlertSender + FirebaseAlertSender
    ↓
Notifications delivered to caregiver
    ↓
Backend stores to PostgreSQL
    ├─ predictions table (frame-level)
    ├─ sos_events table (alert history)
    └─ activity_timeline table (aggregates)
    ↓
Frontend displays real-time dashboard
```

---

## 🔌 API Endpoints (20+ endpoints)

**Authentication:**
- `POST /api/auth/login` - Login with credentials
- `GET /api/auth/me` - Get current user

**Video Processing:**
- `POST /api/sessions/upload` - Upload video for processing
- `GET /api/sessions/{id}` - Get session details
- `GET /api/sessions/{id}/predictions` - Get frame predictions
- `GET /api/sessions/{id}/video/skeleton` - Download skeleton video

**Patient Management:**
- `GET /api/patients` - List all patients
- `POST /api/patients` - Create patient
- `GET /api/patients/{id}` - Get patient details

**Dashboard:**
- `GET /api/dashboard/stats` - Statistics (total sessions, falls, etc.)
- `GET /api/dashboard/activity-distribution` - Activity percentages
- `GET /api/dashboard/recent-alerts` - Last 5 alerts

**Alerts:**
- `GET /api/alerts` - Alert history
- `POST /api/alerts/{id}/acknowledge` - Mark alert as addressed

**Full API docs:** `http://localhost:8000/docs` (Swagger UI)

---

## 🛠️ Technology Stack

### **Backend**
- **Framework:** FastAPI (Python 3.9+)
- **Database:** PostgreSQL 15
- **ORM:** SQLAlchemy
- **Async:** Uvicorn + async/await
- **Auth:** JWT + role-based access

### **Frontend**
- **Framework:** React 18
- **Bundler:** Vite
- **Styling:** Tailwind CSS
- **Charts:** Recharts
- **State:** Zustand
- **HTTP:** Axios

### **ML/CV**
- **Pose Detection:** YOLO v8-pose + MediaPipe
- **Deep Learning:** PyTorch
- **Model:** TCN-BiLSTM (temporal convolution + bidirectional LSTM)
- **Computer Vision:** OpenCV
- **Data:** Pandas, NumPy, scikit-learn

### **Infrastructure**
- **Containerization:** Docker + Docker Compose
- **Cache:** Redis
- **Notifications:** Firebase Cloud Messaging (FCM)
- **Email:** Gmail SMTP

---

## 📈 Model Performance

| Model | Task | Accuracy | F1-Score | Deployment |
|-------|------|----------|----------|-----------|
| **binary_fall_best.pth** | Fall detection | 95%+ | - | Production ✅ |
| **activity_best.pth** | Activity recognition | - | - | Production ✅ |

---

## 📚 Detailed Documentation

Each folder has detailed README files:

| Folder | README | Contents |
|--------|--------|----------|
| `eldercare_v2/` | [README.md](eldercare_v2/README.md) | Setup, endpoints, architecture |
| `pipeline/` | [README.md](pipeline/README.md) | Data flows, processing pipeline |
| `models/` | [README.md](models/README.md) | Model specs, training, inference |
| `alerts/` | [README.md](alerts/README.md) | Alert types, configuration, extending |
| `configs/` | [README.md](configs/README.md) | All configurable settings |
| `datasets/` | [README.md](datasets/README.md) | Dataset management, formats |

---

## ⚙️ Environment Setup

Create `.env` file in `eldercare_v2/backend/`:
```bash
# Database
DATABASE_URL=postgresql://eldercare_user:secure_password_123@localhost:5432/eldercare_db

# Auth
SECRET_KEY=your_secret_key_change_in_production

# Alerts
ALERT_EMAIL=your_email@gmail.com
ALERT_PASSWORD=your_app_password

# Firebase
FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
FCM_DEVICE_TOKENS=token1,token2,token3

# ML Pipeline
MODEL_ROOT=/app/models
CONFIDENCE_THRESHOLD=0.35
```

---

## 🚨 Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Port 8000 already in use | Another service running | `lsof -i :8000` then kill the process |
| PostgreSQL connection refused | DB not running | `docker-compose up postgres` |
| Models won't load | File paths wrong | Check `configs/config.py` paths |
| CUDA out of memory | GPU too small | Set `DEVICE=cpu` in config |
| Poses missing in output | Person not detected | Lower `confidence_threshold` in config |
| Alert spam | No cooldown | Check `ALERT_COOLDOWN_MIN=30` |

---

## 📊 Status Summary

### ✅ Complete (Production Ready)
- Fullstack application (backend, frontend, database)
- ML pipeline (pose extraction, models, training)
- Alert system (5 alert types)
- Docker orchestration
- API documentation

### ⚠️ Incomplete (Needs Work)
- Mobile app integration (Flutter app exists but not connected)
- Unit/integration tests (no test suite)
- CI/CD pipeline (no GitHub Actions)
- API error handling edge cases

### 🗑️ Deprecated
- `flask_server_v2_redesigned.py` - Replaced by FastAPI

---

## 🎯 Next Steps

1. **Read the main folders README** → Start with `eldercare_v2/README.md`
2. **Deploy locally** → `docker-compose up --build`
3. **Test the API** → Open `http://localhost:8000/docs`
4. **Upload a test video** → Use frontend at `http://localhost:5173`
5. **Check the logs** → `docker-compose logs -f backend`

---

## 📞 Support

- **Architecture Questions:** See [eldercare_v2/README.md](eldercare_v2/README.md)
- **Setup Issues:** See [eldercare_v2/README.md](eldercare_v2/README.md)
- **ML Pipeline:** See [pipeline/README.md](pipeline/README.md)
- **Configuration:** See [configs/config.py](configs/config.py)
- **Model Training:** See [models/train.py](models/train.py)

---

**Last Updated:** December 2025  
**Version:** ElderCare AI v2.0  
**Status:** Production-ready ✅

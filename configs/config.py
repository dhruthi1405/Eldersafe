"""
ElderCare AI - Central Configuration
=====================================
Edit paths, email credentials, and thresholds here before running.
"""

import os

# ─────────────────────────────────────────────
#  PROJECT PATHS
# ─────────────────────────────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ─────────────────────────────────────────────
#  EMAIL / ALERT SETTINGS
# ─────────────────────────────────────────────
EMAIL_CONFIG = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": os.environ.get("ALERT_EMAIL", "your_email@gmail.com"),
    "sender_password": os.environ.get("ALERT_PASSWORD", "your_app_password"),
    "recipient_emails": [
        os.environ.get("RECIPIENT_EMAIL", "caregiver@example.com"),
    ],
}

# ─────────────────────────────────────────────
#  SOS / ALERT THRESHOLDS
# ─────────────────────────────────────────────
ALERT_THRESHOLDS = {
    "prolonged_sleep_hours":    15,      # Alert if sleeping > 15 hours
    "wave_count_trigger":       3,       # 3 waves = SOS
    "wave_window_seconds":      10,      # Waves must occur within 10s window
    "fall_confidence_threshold": 0.75,  # Model confidence to trigger fall alert
    "inactivity_alert_minutes": 120,    # Alert if no movement for 2 hours
    "cooldown_minutes":         30,     # Don't re-alert within 30 minutes
}

# ─────────────────────────────────────────────
#  GAIT ANALYSIS THRESHOLDS
#  (proactive fall risk — before fall happens)
# ─────────────────────────────────────────────
GAIT_THRESHOLDS = {
    # Risk score levels (0.0 – 1.0)
    "high_risk_score":      0.70,   # above this → immediate caregiver alert
    "medium_risk_score":    0.40,   # above this → dashboard warning

    # Clinical gait metrics
    "min_gait_speed":       0.60,   # m/s  — below this is fall risk
    "max_trunk_sway":       0.08,   # normalised units (~8° equivalent)
    "min_step_symmetry":    0.85,   # 85% symmetry minimum
    "max_com_instability":  0.10,   # centre-of-mass lateral offset

    # Analysis window
    "analysis_window_frames": 90,   # ~3 seconds at 30 fps
    "min_frames_to_analyse":  30,   # need at least 1 second of data

    # Weights for combined risk score
    "weight_com":           0.35,
    "weight_sway":          0.25,
    "weight_symmetry":      0.25,
    "weight_knee":          0.15,
}

# ─────────────────────────────────────────────
#  ACTIVITY TRACKING RULES
#  Controls which activities trigger alerts
#  vs which are just logged to the timeline
# ─────────────────────────────────────────────
ACTIVITY_RULES = {
    # Immediate email alert
    "fall":  {
        "alert":    True,
        "timeline": True,
        "message":  "FALL DETECTED — elder may need immediate help",
    },
    # SOS signal — count-based alert
    "wave":  {
        "alert":    True,
        "timeline": True,
        "message":  "SOS WAVE SIGNAL — elder is calling for help",
    },
    # Time-based alert (prolonged)
    "sleep": {
        "alert":    True,   # only if duration > ALERT_THRESHOLDS["prolonged_sleep_hours"]
        "timeline": True,
        "message":  "PROLONGED SLEEP — elder has been sleeping unusually long",
    },
    # Timeline only — no alert
    "walk":  {"alert": False, "timeline": True,  "message": ""},
    "sit":   {"alert": False, "timeline": True,  "message": ""},
    "stand": {"alert": False, "timeline": True,  "message": ""},
    "eat":   {"alert": False, "timeline": True,  "message": ""},
    "other": {"alert": False, "timeline": False, "message": ""},
}

# ─────────────────────────────────────────────
#  MODEL SETTINGS
# ─────────────────────────────────────────────
MODEL_CONFIG = {
    "yolo_weights":           "yolov8n-pose.pt",
    "yolo_conf_threshold":    0.35,
    "sequence_length":        30,
    "fall_detection_threshold": 0.15,
    "fall_confirm_frames":    3,
    "activity_confirm_frames": 3,
    "activity_vote_window":    15,
    "tcn_num_channels":       [64, 128, 256],
    "tcn_kernel_size":        3,
    "lstm_hidden":            256,
    "lstm_layers":            2,
    "num_classes":            8,
    "class_names":            ["fall", "walk", "sit", "stand", "eat", "sleep", "wave", "other"],
    "frame_skip":             3,
    "batch_size":             32,
    "epochs":                 50,
    "learning_rate":          1e-3,
    "weight_decay":           1e-4,
    "early_stopping_patience": 10,
}

# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
DASHBOARD_CONFIG = {
    "host":                "0.0.0.0",
    "port":                8050,
    "debug":               False,
    "refresh_interval_ms": 2000,
}

# ─────────────────────────────────────────────
#  ACTIVITY COLOURS  (used in dashboard)
# ─────────────────────────────────────────────
ACTIVITY_COLOR_MAP = {
    "fall":      "#FF3B3B",
    "walk":      "#4ECDC4",
    "sit":       "#45B7D1",
    "stand":     "#96CEB4",
    "eat":       "#FFEAA7",
    "sleep":     "#6C5CE7",
    "wave":      "#FD79A8",
    "other":     "#636e72",
    "fall_risk": "#FF8C00",   # proactive gait risk colour
}

# Gait risk level colours for dashboard gauge
GAIT_RISK_COLORS = {
    "LOW":     "#00b894",
    "MEDIUM":  "#fdcb6e",
    "HIGH":    "#d63031",
    "unknown": "#636e72",
}

# ─────────────────────────────────────────────
#  LABEL REMAP  (raw dataset → unified label)
# ─────────────────────────────────────────────
LABEL_REMAP = {
    # UCF50
    "WalkingWithDog": "walk",
    "TaiChi":         "other",
    "Swing":          "other",
    "HorseRace":      "other",
    "eating":         "eat",
    "sitting":        "sit",
    "standing":       "stand",
    "sleeping":       "sleep",
    "waving":         "wave",
    # HMDB51
    "walk":           "walk",
    "sit":            "sit",
    "stand":          "stand",
    "eat":            "eat",
    "sleep":          "sleep",
    "wave":           "wave",
    "fall_floor":     "fall",
    # HAR Dataset
    "WALKING":        "walk",
    "SITTING":        "sit",
    "STANDING":       "stand",
    "LAYING":         "sleep",
    # Fall datasets
    "__fall__":       "fall",
    "__no_fall__":    "other",
}

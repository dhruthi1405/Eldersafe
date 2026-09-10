-- ElderCare Database Schema (PostgreSQL)
-- Professional Production Database

-- Users & Authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50), -- 'admin', 'caretaker', 'doctor'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Patients
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(10),
    medical_conditions TEXT,
    emergency_contact VARCHAR(255),
    emergency_phone VARCHAR(20),
    caretaker_id INTEGER REFERENCES users(id),
    doctor_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Video Uploads & Analysis
CREATE TABLE video_sessions (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    session_type VARCHAR(50), -- 'upload', 'live_camera', 'recorded'
    video_path VARCHAR(512),
    video_duration FLOAT,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(50), -- 'pending', 'processing', 'completed', 'failed'
    processed_at TIMESTAMP,
    output_skeleton_video VARCHAR(512),
    created_by INTEGER REFERENCES users(id)
);

-- Frame-by-Frame Predictions
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES video_sessions(id),
    frame_idx INTEGER,
    timestamp_s FLOAT,
    activity_label VARCHAR(50), -- 'walk', 'sit', 'stand', 'eat', 'sleep', 'wave'
    activity_confidence FLOAT,
    fall_confidence FLOAT,
    fall_status VARCHAR(50), -- 'FALLING', 'NOT_FALLING'
    gait_risk_score FLOAT,
    gait_risk_level VARCHAR(50), -- 'LOW', 'MEDIUM', 'HIGH'
    is_fall_alert BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOS Alerts & Events
CREATE TABLE sos_events (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    session_id INTEGER REFERENCES video_sessions(id),
    alert_type VARCHAR(50), -- 'FALL', 'PROLONGED_SITTING', 'GAIT_ANOMALY'
    severity VARCHAR(50), -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    confidence FLOAT,
    message TEXT,
    video_timestamp FLOAT,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    caretaker_notified BOOLEAN DEFAULT FALSE,
    doctor_notified BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    notes TEXT
);

-- Notifications Log
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    recipient_id INTEGER REFERENCES users(id),
    patient_id INTEGER REFERENCES patients(id),
    sos_event_id INTEGER REFERENCES sos_events(id),
    notification_type VARCHAR(50), -- 'email', 'push', 'sms'
    status VARCHAR(50), -- 'pending', 'sent', 'failed'
    sent_at TIMESTAMP,
    read_at TIMESTAMP
);

-- Patient Timeline (Activity History)
CREATE TABLE activity_timeline (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    date DATE,
    activity_label VARCHAR(50),
    duration_seconds INTEGER,
    fall_incidents INTEGER DEFAULT 0,
    gait_issues INTEGER DEFAULT 0,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vital Signs & Health Metrics (if needed)
CREATE TABLE health_metrics (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    recorded_date DATE,
    metric_type VARCHAR(100), -- 'heart_rate', 'blood_pressure', 'temperature'
    metric_value FLOAT,
    unit VARCHAR(20),
    recorded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Log
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(255),
    table_name VARCHAR(100),
    record_id INTEGER,
    old_values TEXT,
    new_values TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Indexes for Performance
CREATE INDEX idx_patients_caretaker ON patients(caretaker_id);
CREATE INDEX idx_video_sessions_patient ON video_sessions(patient_id);
CREATE INDEX idx_predictions_session ON predictions(session_id);
CREATE INDEX idx_sos_events_patient ON sos_events(patient_id);
CREATE INDEX idx_notifications_recipient ON notifications(recipient_id);
CREATE INDEX idx_activity_timeline_patient ON activity_timeline(patient_id);

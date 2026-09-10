"""
SQLAlchemy ORM Models
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50))  # 'admin', 'caretaker', 'doctor'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patients_as_caretaker = relationship("Patient", foreign_keys="Patient.caretaker_id")
    patients_as_doctor = relationship("Patient", foreign_keys="Patient.doctor_id")


class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(Date)
    gender = Column(String(10))
    medical_conditions = Column(Text)
    emergency_contact = Column(String(255))
    emergency_phone = Column(String(20))
    caretaker_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    video_sessions = relationship("VideoSession", back_populates="patient")
    sos_events = relationship("SOSEvent", back_populates="patient")
    activity_timeline = relationship("ActivityTimeline", back_populates="patient")
    health_metrics = relationship("HealthMetrics", back_populates="patient")


class VideoSession(Base):
    __tablename__ = "video_sessions"
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    session_type = Column(String(50))  # 'upload', 'live_camera', 'recorded'
    video_path = Column(String(512))
    video_duration = Column(Float)
    upload_time = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String(50), default="pending")  # 'pending', 'processing', 'completed', 'failed'
    processed_at = Column(DateTime)
    output_skeleton_video = Column(String(512))
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    patient = relationship("Patient", back_populates="video_sessions")
    predictions = relationship("Prediction", back_populates="session")
    sos_events = relationship("SOSEvent", back_populates="session")


class Prediction(Base):
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("video_sessions.id"), nullable=False)
    frame_idx = Column(Integer)
    timestamp_s = Column(Float)
    activity_label = Column(String(50))  # 'walk', 'sit', 'stand', 'eat', 'sleep', 'wave'
    activity_confidence = Column(Float)
    fall_confidence = Column(Float)
    fall_status = Column(String(50))  # 'FALLING', 'NOT_FALLING'
    gait_risk_score = Column(Float)
    gait_risk_level = Column(String(50))  # 'LOW', 'MEDIUM', 'HIGH'
    is_fall_alert = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("VideoSession", back_populates="predictions")


class SOSEvent(Base):
    __tablename__ = "sos_events"
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("video_sessions.id"))
    alert_type = Column(String(50))  # 'FALL', 'PROLONGED_SITTING', 'GAIT_ANOMALY'
    severity = Column(String(50))  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    confidence = Column(Float)
    message = Column(Text)
    video_timestamp = Column(Float)
    notified_at = Column(DateTime, default=datetime.utcnow)
    caretaker_notified = Column(Boolean, default=False)
    doctor_notified = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    notes = Column(Text)
    
    # Relationships
    patient = relationship("Patient", back_populates="sos_events")
    session = relationship("VideoSession", back_populates="sos_events")
    notifications = relationship("Notification", back_populates="sos_event")


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    sos_event_id = Column(Integer, ForeignKey("sos_events.id"))
    notification_type = Column(String(50))  # 'email', 'push', 'sms'
    status = Column(String(50), default="pending")  # 'pending', 'sent', 'failed'
    sent_at = Column(DateTime)
    read_at = Column(DateTime)
    
    # Relationships
    sos_event = relationship("SOSEvent", back_populates="notifications")


class ActivityTimeline(Base):
    __tablename__ = "activity_timeline"
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    date = Column(Date, nullable=False)
    activity_label = Column(String(50))
    duration_seconds = Column(Integer)
    fall_incidents = Column(Integer, default=0)
    gait_issues = Column(Integer, default=0)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="activity_timeline")


class HealthMetrics(Base):
    __tablename__ = "health_metrics"
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    recorded_date = Column(Date)
    metric_type = Column(String(100))  # 'heart_rate', 'blood_pressure', 'temperature'
    metric_value = Column(Float)
    unit = Column(String(20))
    recorded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="health_metrics")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255))
    table_name = Column(String(100))
    record_id = Column(Integer)
    old_values = Column(Text)
    new_values = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

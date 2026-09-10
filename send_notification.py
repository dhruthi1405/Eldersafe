#!/usr/bin/env python3
"""
Send any type of alert notification to Flutter app
Usage:
  python send_notification.py --type FALL
  python send_notification.py --type WAVE_SOS
  python send_notification.py --type PROLONGED_SLEEP
  python send_notification.py --type PROLONGED_INACTIVITY
  python send_notification.py --type FALL_RISK
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alerts.sos_detector import SOSEvent, AlertType
from alerts.firebase_alert import FirebaseAlertSender

ALERT_CONFIGS = {
    "FALL": {
        "confidence": 0.95,
        "activity": "fall",
        "message": "🚨 FALL DETECTED — Senior fell down, immediate assistance needed!",
    },
    "WAVE_SOS": {
        "confidence": 0.92,
        "activity": "wave",
        "message": "🆘 SOS SIGNAL — Senior waving for help, needs immediate assistance!",
    },
    "PROLONGED_SLEEP": {
        "confidence": 0.88,
        "activity": "sleep",
        "message": "😴 PROLONGED SLEEP — Senior sleeping for extended period (>8 hours)",
    },
    "PROLONGED_INACTIVITY": {
        "confidence": 0.85,
        "activity": "sit",
        "message": "⚠️ INACTIVITY ALERT — Senior inactive for extended period (>2 hours)",
    },
    "FALL_RISK": {
        "confidence": 0.78,
        "activity": "walk",
        "message": "⚠️ HIGH FALL RISK — Gait analysis shows unstable walking pattern",
    },
}

def send_notification(alert_type: str, device_token: str) -> bool:
    """Send a notification of specified type"""
    
    if alert_type not in ALERT_CONFIGS:
        print(f"❌ Unknown alert type: {alert_type}")
        print(f"Available types: {', '.join(ALERT_CONFIGS.keys())}")
        return False
    
    config = ALERT_CONFIGS[alert_type]
    
    print(f"🚀 Sending {alert_type} notification...")
    
    # Create event
    event = SOSEvent(
        alert_type=AlertType[alert_type],
        timestamp=time.time(),
        activity_label=config["activity"],
        confidence=config["confidence"],
        message=config["message"],
        video_timestamp_s=42.5,
    )
    
    # Initialize Firebase
    sender = FirebaseAlertSender()
    
    if not sender.available:
        print("❌ Firebase NOT available")
        return False
    
    # Override device token
    import os
    os.environ["FCM_DEVICE_TOKEN"] = device_token
    
    # Send
    success = sender.send(event)
    
    if success:
        print(f"✅ {alert_type} notification sent!")
        print(f"   Confidence: {config['confidence']:.0%}")
        print(f"   Activity: {config['activity'].upper()}")
        print(f"   Message: {config['message']}")
    else:
        print(f"❌ Failed to send {alert_type} notification")
    
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send alert notification to Flutter app")
    parser.add_argument("--type", default="FALL", choices=list(ALERT_CONFIGS.keys()),
                        help="Alert type to send")
    parser.add_argument("--token", required=True, help="FCM device token")
    args = parser.parse_args()
    
    import os
    os.environ["FIREBASE_KEY_PATH"] = "C:\\ElderCareProject\\serviceAccountKey.json"
    
    success = send_notification(args.type, args.token)
    sys.exit(0 if success else 1)

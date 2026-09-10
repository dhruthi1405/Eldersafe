#!/usr/bin/env python3
"""
Quick script to send a test fall notification to your Flutter app
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alerts.sos_detector import SOSEvent, AlertType
from alerts.firebase_alert import FirebaseAlertSender

def send_test_fall_notification():
    """Send a test FALL notification to all registered devices"""
    
    print("🚀 Sending test FALL notification...")
    
    # Create test event
    test_event = SOSEvent(
        alert_type=AlertType.FALL,
        timestamp=time.time(),
        activity_label="fall",
        confidence=0.95,
        message="TEST FALL DETECTED — ElderCare AI System Test",
        video_timestamp_s=42.5,
    )
    
    # Initialize Firebase alert sender
    sender = FirebaseAlertSender()
    
    if not sender.available:
        print("❌ Firebase NOT available. Make sure:")
        print("   1. pip install firebase-admin")
        print("   2. serviceAccountKey.json exists in project root")
        return False
    
    # Send notification
    success = sender.send(test_event)
    
    if success:
        print("✅ Test FALL notification sent successfully!")
        print(f"   Alert Type: {test_event.alert_type.name}")
        print(f"   Confidence: {test_event.confidence:.0%}")
        print(f"   Message: {test_event.message}")
        return True
    else:
        print("❌ Failed to send notification. Check:")
        print("   1. Firebase service account key is valid")
        print("   2. Device tokens are registered (FCM_DEVICE_TOKEN env var)")
        return False

if __name__ == "__main__":
    success = send_test_fall_notification()
    sys.exit(0 if success else 1)

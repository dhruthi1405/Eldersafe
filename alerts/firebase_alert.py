"""
firebase_alert.py
==================
Sends instant push notifications to mobile devices via Firebase Cloud Messaging (FCM).

Setup:
  1. Create Firebase project at https://console.firebase.google.com
  2. Download service account JSON key
  3. Set env vars:
       FIREBASE_KEY_PATH=/path/to/serviceAccountKey.json
       FCM_DEVICE_TOKEN=your_device_token (from mobile app registration)
       FCM_DEVICE_TOKENS=token1,token2,token3 (multiple devices, comma-separated)

Installation:
  pip install firebase-admin
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alerts.sos_detector import AlertType, SOSEvent

DEVICE_TOKEN_STORE = Path(
    os.getenv(
        "FCM_DEVICE_TOKENS_FILE",
        str(Path(__file__).resolve().parents[1] / "runtime" / "mobile_device_tokens.json"),
    )
)

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("[Firebase] WARNING: firebase-admin not installed. Run: pip install firebase-admin")


_NOTIFICATION_TITLES = {
    AlertType.FALL: "🚨 FALL DETECTED",
    AlertType.WAVE_SOS: "🆘 SOS SIGNAL",
    AlertType.PROLONGED_SLEEP: "😴 PROLONGED SLEEP",
    AlertType.PROLONGED_INACTIVITY: "⚠️ INACTIVITY",
    AlertType.FALL_RISK: "⚠️ HIGH FALL RISK",
}

_NOTIFICATION_COLORS = {
    AlertType.FALL: "#FF3B3B",
    AlertType.WAVE_SOS: "#FF8C00",
    AlertType.PROLONGED_SLEEP: "#6C5CE7",
    AlertType.PROLONGED_INACTIVITY: "#636e72",
    AlertType.FALL_RISK: "#D97706",
}


class FirebaseAlertSender:
    """Send instant push notifications via Firebase Cloud Messaging (FCM)"""

    def __init__(self, service_account_key_path: Optional[str] = None):
        """
        Initialize Firebase app.
        
        Args:
            service_account_key_path: Path to serviceAccountKey.json
                                     If None, reads from FIREBASE_KEY_PATH env var
        """
        if not FIREBASE_AVAILABLE:
            self.available = False
            return

        self.available = False
        self.app = None

        key_path = service_account_key_path or os.getenv("FIREBASE_KEY_PATH")
        if not key_path or not os.path.exists(key_path):
            print(
                "[Firebase] WARNING: Service account key not found.\n"
                "           Set FIREBASE_KEY_PATH env var with path to serviceAccountKey.json"
            )
            return

        try:
            cred = credentials.Certificate(key_path)
            try:
                self.app = firebase_admin.get_app("eldersafe")
            except ValueError:
                self.app = firebase_admin.initialize_app(cred, name="eldersafe")
            self.available = True
            print("[Firebase] ✓ Initialized successfully")
        except Exception as e:
            print(f"[Firebase] ERROR: Failed to initialize - {e}")

    def _get_device_tokens(self) -> List[str]:
        """
        Get list of device tokens from env vars.
        Supports:
          - Single: FCM_DEVICE_TOKEN=abc123
          - Multiple: FCM_DEVICE_TOKENS=abc123,def456,ghi789
        """
        tokens = []

        # Single token
        single = os.getenv("FCM_DEVICE_TOKEN", "").strip()
        if single and "your_token" not in single.lower():
            tokens.append(single)

        # Multiple tokens
        multi = os.getenv("FCM_DEVICE_TOKENS", "").strip()
        if multi and "your_token" not in multi.lower():
            tokens.extend([t.strip() for t in multi.split(",") if t.strip()])

        if DEVICE_TOKEN_STORE.exists():
            try:
                payload = json.loads(DEVICE_TOKEN_STORE.read_text(encoding="utf-8"))
                stored_tokens = [
                    entry.get("device_token", "").strip()
                    for entry in payload.get("tokens", [])
                    if entry.get("device_token")
                ]
                tokens.extend([token for token in stored_tokens if token])
            except Exception as e:
                print(f"[Firebase] WARNING: Failed to read device token store - {e}")

        return list(set(tokens))  # Remove duplicates

    def send(self, event: SOSEvent) -> bool:
        """Send push notification for a single event"""
        if not self.available:
            return False

        tokens = self._get_device_tokens()
        if not tokens:
            print("[Firebase] No device tokens configured.")
            return False

        title = _NOTIFICATION_TITLES.get(event.alert_type, "⚠️ ALERT")
        color = _NOTIFICATION_COLORS.get(event.alert_type, "#333333")

        # Build notification payload
        notification = messaging.Notification(
            title=title,
            body=f"{event.activity_label.upper()} | Confidence: {event.confidence:.0%}",
        )

        # Build data payload
        data = {
            "alert_type": event.alert_type.name,
            "activity_label": event.activity_label,
            "confidence": f"{event.confidence:.0%}",
            "message": event.message[:200],  # Truncate long messages
            "timestamp": datetime.fromtimestamp(event.timestamp).isoformat(),
            "color": color,
        }

        if event.video_timestamp_s is not None:
            m, s = divmod(int(event.video_timestamp_s), 60)
            data["video_timestamp"] = f"{m:02d}:{s:02d}"

        try:
            for token in tokens:
                try:
                    message = messaging.Message(
                        notification=notification,
                        data=data,
                        token=token,
                        android=messaging.AndroidConfig(
                            priority="high",
                            notification=messaging.AndroidNotification(
                                color=color,
                                sound="default",
                                click_action="FLUTTER_NOTIFICATION_CLICK",
                            ),
                        ),
                        apns=messaging.APNSConfig(
                            payload=messaging.APNSPayload(
                                aps=messaging.Aps(
                                    alert=messaging.ApsAlert(
                                        title=title,
                                        body=data["message"],
                                    ),
                                    sound="default",
                                    badge=1,
                                    mutable_content=True,
                                )
                            ),
                        ),
                    )
                    messaging.send(message, app=self.app)
                except Exception as e:
                    print(f"[Firebase] Failed for token {token[:10]}...: {e}")
                    continue

            print(f"[Firebase] Push sent to {len(tokens)} device(s): {event.alert_type.name}")
            return True

        except Exception as e:
            print(f"[Firebase] ERROR: {e}")
            return False

    def send_activity(
        self,
        activity_label: str,
        confidence: float,
        duration_seconds: int,
        video_timestamp_s: Optional[float] = None
    ) -> bool:
        """
        Send activity update (non-critical) to Flutter app.
        
        This broadcasts detected activities like walk, sit, stand, eat, sleep
        without triggering urgent alerts (those go via send() method).
        
        Args:
            activity_label: Activity type ('walk', 'sit', 'stand', 'eat', 'sleep', 'fall', 'wave')
            confidence: Model confidence (0.0 - 1.0)
            duration_seconds: How long activity has been detected
            video_timestamp_s: Optional video timestamp in seconds
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.available:
            return False

        tokens = self._get_device_tokens()
        if not tokens:
            return False

        # Activity icons
        icons = {
            'walk': '🚶',
            'sit': '🪑',
            'stand': '🧍',
            'eat': '🍽️',
            'sleep': '😴',
            'fall': '⚠️',
            'wave': '🆘',
        }
        icon = icons.get(activity_label.lower(), '📊')

        # Activity colors
        colors = {
            'walk': '#4CAF50',
            'sit': '#2196F3',
            'stand': '#FF9800',
            'eat': '#F44336',
            'sleep': '#9C27B0',
            'fall': '#FF3B3B',
            'wave': '#FF8C00',
        }
        color = colors.get(activity_label.lower(), '#9E9E9E')

        # Format duration
        hours, remainder = divmod(duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            duration_str = f"{hours}h {minutes}m"
        elif minutes > 0:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"

        # Build notification
        notification = messaging.Notification(
            title=f"{icon} {activity_label.title()}",
            body=f"Confidence: {confidence * 100:.1f}% | Duration: {duration_str}",
        )

        # Build data payload
        data = {
            'activity_label': activity_label,
            'confidence': str(confidence),
            'duration_seconds': str(duration_seconds),
            'timestamp': datetime.utcnow().isoformat(),
            'alert_type': 'ACTIVITY',
        }

        if video_timestamp_s is not None:
            m, s = divmod(int(video_timestamp_s), 60)
            data['video_timestamp'] = f"{m:02d}:{s:02d}"

        try:
            for token in tokens:
                try:
                    message = messaging.Message(
                        notification=notification,
                        data=data,
                        token=token,
                        android=messaging.AndroidConfig(
                            priority="normal",  # Normal priority for activities (not urgent)
                            notification=messaging.AndroidNotification(
                                color=color,
                                click_action="FLUTTER_NOTIFICATION_CLICK",
                            ),
                        ),
                        apns=messaging.APNSConfig(
                            payload=messaging.APNSPayload(
                                aps=messaging.Aps(
                                    alert=messaging.ApsAlert(
                                        title=f"{icon} {activity_label.title()}",
                                        body=f"Confidence: {confidence * 100:.1f}%",
                                    ),
                                    mutable_content=True,
                                    badge=0,  # Don't trigger badge for activities
                                )
                            ),
                        ),
                    )
                    messaging.send(message, app=self.app)
                except Exception as e:
                    print(f"[Activity] Failed for token {token[:10]}...: {e}")
                    continue

            print(f"[Activity] {icon} {activity_label} sent to {len(tokens)} device(s)")
            return True

        except Exception as e:
            print(f"[Activity] ERROR: {e}")
            return False

    def send_bulk(self, events: List[SOSEvent]) -> int:
        """Send multiple notifications"""
        return sum(1 for e in events if self.send(e))


class MultiAlertSender:
    """Send notifications via both Email and Firebase"""

    def __init__(self, enable_email: bool = True, enable_firebase: bool = True):
        """
        Initialize multi-channel alerting.
        
        Args:
            enable_email: Send email alerts
            enable_firebase: Send push notifications
        """
        self.email_sender = None
        self.firebase_sender = None

        if enable_email:
            try:
                from alerts.email_alert import AlertSender
                self.email_sender = AlertSender()
            except Exception as e:
                print(f"[AlertSender] Email init failed: {e}")

        if enable_firebase:
            self.firebase_sender = FirebaseAlertSender()

    def send(self, event: SOSEvent, extra_recipients: Optional[List[str]] = None) -> bool:
        """Send alert via all available channels"""
        results = []

        if self.email_sender:
            results.append(self.email_sender.send(event, extra_recipients))

        if self.firebase_sender and self.firebase_sender.available:
            results.append(self.firebase_sender.send(event))

        return any(results)

    def send_bulk(self, events: List[SOSEvent]) -> int:
        """Send multiple alerts"""
        return sum(1 for e in events if self.send(e))


if __name__ == "__main__":
    # Test Firebase connection
    print("Testing Firebase configuration...")

    sender = FirebaseAlertSender()

    if not sender.available:
        print("Firebase not initialized. Check:")
        print("  1. FIREBASE_KEY_PATH env var set?")
        print("  2. Path to serviceAccountKey.json valid?")
        print("  3. firebase-admin installed? (pip install firebase-admin)")
        sys.exit(1)

    tokens = sender._get_device_tokens()
    print(f"Device tokens configured: {len(tokens)}")
    for i, token in enumerate(tokens, 1):
        print(f"  {i}. {token[:20]}...{token[-10:]}")

    if not tokens:
        print("\nNo tokens found. Set FCM_DEVICE_TOKEN or FCM_DEVICE_TOKENS env vars")
        sys.exit(1)

    print("\n✓ Firebase configured and ready!")
    print("Device tokens are registered and will receive notifications.")

"""
email_alert.py
===============
Sends email alerts when SOS events are triggered.

Setup:
    Option A (recommended): Gmail API OAuth
        Set env vars:
            GMAIL_OAUTH_CLIENT_ID=...
            GMAIL_OAUTH_CLIENT_SECRET=...
            GMAIL_OAUTH_REFRESH_TOKEN=...
            GMAIL_OAUTH_SENDER_EMAIL=your_email@gmail.com

    Option B: SMTP with Gmail App Password
        Set env vars:
            ALERT_EMAIL=your_email@gmail.com
            ALERT_PASSWORD=your_16char_app_password
            RECIPIENT_EMAIL=caregiver@example.com
"""

from __future__ import annotations

import base64
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alerts.sos_detector import AlertType, SOSEvent
from configs.config import EMAIL_CONFIG, ALERT_THRESHOLDS


_COLORS: dict = {
    AlertType.FALL: ("#FF3B3B", "🚨 FALL DETECTED"),
    AlertType.WAVE_SOS: ("#FF8C00", "🆘 SOS WAVE SIGNAL"),
    AlertType.PROLONGED_SLEEP: ("#6C5CE7", "😴 PROLONGED SLEEP ALERT"),
    AlertType.PROLONGED_INACTIVITY: ("#636e72", "⚠️ INACTIVITY ALERT"),
    AlertType.FALL_RISK: ("#D97706", "⚠️ HIGH FALL RISK"),
}

_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f5f5; margin: 0; padding: 20px; }}
    .card {{ background: white; border-radius: 12px; padding: 32px;
             max-width: 540px; margin: 0 auto;
             box-shadow: 0 4px 24px rgba(0,0,0,0.10); }}
    .badge {{ display: inline-block; background: {color}; color: white;
              border-radius: 24px; padding: 6px 18px; font-weight: 700;
              font-size: 14px; letter-spacing: 0.5px; margin-bottom: 20px; }}
    h1 {{ margin: 0 0 8px; font-size: 22px; color: #1a1a2e; }}
    .meta {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
    .detail {{ background: #f9f9f9; border-left: 4px solid {color};
               padding: 14px 18px; border-radius: 4px; margin-bottom: 20px; }}
    .detail p {{ margin: 4px 0; font-size: 14px; color: #333; }}
    .footer {{ font-size: 12px; color: #aaa; text-align: center; margin-top: 24px; }}
    .threshold {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px;
                  padding: 10px 14px; font-size: 13px; color: #856404; white-space: pre-line; }}
  </style>
</head>
<body>
<div class="card">
  <div class="badge">{title}</div>
  <h1>ElderCare AI Alert</h1>
  <p class="meta">Triggered at {timestamp}</p>
  <div class="detail">
    <p><strong>Event:</strong> {alert_type}</p>
    <p><strong>Activity:</strong> {activity_label}</p>
    <p><strong>Confidence:</strong> {confidence}</p>
    {video_ts_line}
  </div>
  <p><strong>Message:</strong><br>{message}</p>
  <div class="threshold">
    <strong>Active Thresholds:</strong><br>
    Fall confidence: {fall_threshold}% | Wave trigger: {wave_count}x in {wave_window}s | Sleep limit: {sleep_hours}h
  </div>
  <p class="footer">Sent by ElderCare AI Monitoring System</p>
</div>
</body>
</html>
"""


def _format_html(event: SOSEvent) -> str:
    color, title = _COLORS.get(event.alert_type, ("#333", "⚠️ ALERT"))

    vts_line = ""
    if event.video_timestamp_s is not None:
        m, s = divmod(int(event.video_timestamp_s), 60)
        vts_line = f"<p><strong>Video timestamp:</strong> {m:02d}:{s:02d}</p>"

    thr = ALERT_THRESHOLDS

    return _HTML_TEMPLATE.format(
        color=color,
        title=title,
        timestamp=datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
        alert_type=event.alert_type.name.replace("_", " ").title(),
        activity_label=event.activity_label.upper(),
        confidence=f"{event.confidence:.0%}",
        video_ts_line=vts_line,
        message=event.message.replace("\n", "<br>"),
        fall_threshold=int(thr["fall_confidence_threshold"] * 100),
        wave_count=thr["wave_count_trigger"],
        wave_window=thr["wave_window_seconds"],
        sleep_hours=thr["prolonged_sleep_hours"],
    )


class AlertSender:
    def __init__(self):
        self.cfg = EMAIL_CONFIG
        self.oauth_client_id = os.getenv("GMAIL_OAUTH_CLIENT_ID", "").strip()
        self.oauth_client_secret = os.getenv("GMAIL_OAUTH_CLIENT_SECRET", "").strip()
        self.oauth_refresh_token = os.getenv("GMAIL_OAUTH_REFRESH_TOKEN", "").strip()
        self.oauth_sender_email = os.getenv(
            "GMAIL_OAUTH_SENDER_EMAIL",
            self.cfg.get("sender_email", ""),
        ).strip()
        self.oauth_token_uri = os.getenv(
            "GMAIL_OAUTH_TOKEN_URI",
            "https://oauth2.googleapis.com/token",
        ).strip()
        self._validate()

    def _oauth_configured(self) -> bool:
        return bool(
            self.oauth_client_id
            and self.oauth_client_secret
            and self.oauth_refresh_token
            and self.oauth_sender_email
        )

    def _validate(self) -> None:
        if self._oauth_configured():
            print(f"[AlertSender] Gmail OAuth enabled for {self.oauth_sender_email}")
            return

        if (
            not self.cfg.get("sender_email")
            or "your_email" in self.cfg["sender_email"]
            or not self.cfg.get("sender_password")
            or "your_password" in self.cfg["sender_password"]
        ):
            print(
                "[AlertSender] WARNING: Email not configured. "
                "Set Gmail OAuth env vars or ALERT_EMAIL/ALERT_PASSWORD."
            )

    def _build_message(self, recipients: List[str], subject: str, event: SOSEvent) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.oauth_sender_email if self._oauth_configured() else self.cfg["sender_email"]
        msg["To"] = ", ".join(recipients)

        html_part = MIMEText(_format_html(event), "html", "utf-8")
        plain_part = MIMEText(
            f"ElderCare Alert: {event.alert_type.name}\n"
            f"Activity: {event.activity_label}\n"
            f"Confidence: {event.confidence:.0%}\n"
            f"Message: {event.message}\n"
            f"Time: {datetime.fromtimestamp(event.timestamp)}\n",
            "plain",
            "utf-8",
        )

        msg.attach(plain_part)
        msg.attach(html_part)
        return msg

    def _send_via_gmail_oauth(self, msg: MIMEMultipart) -> bool:
        if not self._oauth_configured():
            return False

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except Exception as e:
            print(f"[Email][OAuth] Missing Gmail API dependencies: {e}")
            return False

        try:
            creds = Credentials(
                token=None,
                refresh_token=self.oauth_refresh_token,
                token_uri=self.oauth_token_uri,
                client_id=self.oauth_client_id,
                client_secret=self.oauth_client_secret,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            creds.refresh(Request())

            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
            service.users().messages().send(userId="me", body={"raw": raw}).execute()

            print("[Email][OAuth] Alert sent successfully via Gmail API")
            return True
        except Exception as e:
            print(f"[Email][OAuth] FAILED to send alert: {e}")
            return False

    def _send_via_smtp(self, recipients: List[str], msg: MIMEMultipart) -> bool:
        try:
            with smtplib.SMTP(self.cfg["smtp_host"], self.cfg["smtp_port"]) as server:
                server.starttls()
                server.login(self.cfg["sender_email"], self.cfg["sender_password"])
                server.sendmail(self.cfg["sender_email"], recipients, msg.as_string())

            print(f"[Email][SMTP] Alert sent to {recipients}")
            return True
        except Exception as e:
            print(f"[Email][SMTP] FAILED to send alert: {e}")
            return False

    def send_login_success_email(
        self,
        *,
        recipient_email: str,
        user_name: Optional[str] = None,
        provider: str = "email/password",
        login_time: Optional[datetime] = None,
    ) -> bool:
        """Send a sign-in confirmation email, similar to standard websites."""
        if not recipient_email:
            return False

        when = login_time or datetime.utcnow()
        display_name = (user_name or "User").strip() or "User"

        subject = "[ElderCare] Login Successful"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.oauth_sender_email if self._oauth_configured() else self.cfg["sender_email"]
        msg["To"] = recipient_email

        plain_part = MIMEText(
            "Hello {name},\n\n"
            "Your ElderCare account was signed in successfully.\n"
            "Provider: {provider}\n"
            "Time (UTC): {time}\n\n"
            "If this wasn't you, please change your password and review account access.\n"
            "- ElderCare Security"
            .format(name=display_name, provider=provider, time=when.strftime("%Y-%m-%d %H:%M:%S")),
            "plain",
            "utf-8",
        )

        html_part = MIMEText(
            (
                "<html><body style='font-family:Segoe UI,Arial,sans-serif;background:#f7f7f7;padding:20px;'>"
                "<div style='max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:28px;border:1px solid #ececec;'>"
                "<h2 style='margin:0 0 12px;color:#1f2937;'>Login Successful</h2>"
                "<p style='color:#374151;'>Hi <strong>{name}</strong>, your ElderCare account was just accessed successfully.</p>"
                "<p style='color:#4b5563;'><strong>Provider:</strong> {provider}<br/>"
                "<strong>Time (UTC):</strong> {time}</p>"
                "<p style='color:#b91c1c;margin-top:18px;'>If this was not you, change your password immediately.</p>"
                "<p style='color:#9ca3af;font-size:12px;margin-top:20px;'>ElderCare Security Notification</p>"
                "</div></body></html>"
            ).format(name=display_name, provider=provider, time=when.strftime("%Y-%m-%d %H:%M:%S")),
            "html",
            "utf-8",
        )

        msg.attach(plain_part)
        msg.attach(html_part)

        recipients = [recipient_email]
        if self._oauth_configured() and self._send_via_gmail_oauth(msg):
            return True
        return self._send_via_smtp(recipients, msg)

    def send(self, event: SOSEvent, extra_recipients: Optional[List[str]] = None, recipient_email: Optional[str] = None) -> bool:
        _, title = _COLORS.get(event.alert_type, ("#333", "⚠️ ALERT"))
        subject = f"[ElderCare] {title} — {event.activity_label.upper()}"

        recipients = list(self.cfg["recipient_emails"])
        
        # Use recipient_email if provided (from Flask API)
        if recipient_email:
            recipients = [recipient_email]
        # Otherwise use extra_recipients if provided
        elif extra_recipients:
            recipients.extend(extra_recipients)

        if not recipients:
            print("[Email] No recipients configured.")
            return False

        msg = self._build_message(recipients, subject, event)

        if self._oauth_configured() and self._send_via_gmail_oauth(msg):
            return True

        if self._send_via_smtp(recipients, msg):
            return True

        print(f"[Email] FAILED to send alert via all channels: {event.alert_type.name}")
        return False

    def send_bulk(self, events: List[SOSEvent]) -> int:
        return sum(1 for e in events if self.send(e))


if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Send a test fall alert")
    args = parser.parse_args()

    if args.test:
        test_event = SOSEvent(
            alert_type=AlertType.FALL,
            timestamp=time.time(),
            activity_label="fall",
            confidence=0.91,
            message="FALL DETECTED (conf=91%) — TEST ALERT",
            video_timestamp_s=37.5,
        )
        sender = AlertSender()
        ok = sender.send(test_event)
        print("Test email sent!" if ok else "Test email FAILED. Check credentials.")
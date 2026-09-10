# Alerts

This folder contains the alerting and notification logic.

## Files

- `sos_detector.py` - fall, inactivity, wave, sleep, and gait-risk detection
- `email_alert.py` - email notifications
- `firebase_alert.py` - push notifications

## Purpose

The alert layer watches model output and sends caregiver notifications when configured thresholds are crossed.

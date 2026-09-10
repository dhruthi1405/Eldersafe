"""
sos_detector.py
================
Real-time SOS event detection from inference results.

Detects:
  1. FALL                  -> immediate alert
  2. WAVE x 3              -> SOS wave alert within wave_window_seconds
  3. PROLONGED SLEEP       -> sleeping > prolonged_sleep_hours continuously
  4. PROLONGED INACTIVITY  -> no movement for inactivity_alert_minutes
  5. PROACTIVE FALL RISK   -> high gait risk warning

All alerts are rate-limited by cooldown_minutes to prevent spam.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Deque, Dict, List, Optional, Tuple

from configs.config import ALERT_THRESHOLDS


class AlertType(Enum):
    FALL = auto()
    WAVE_SOS = auto()
    PROLONGED_SLEEP = auto()
    PROLONGED_INACTIVITY = auto()
    FALL_RISK = auto()


@dataclass
class SOSEvent:
    alert_type: AlertType
    timestamp: float
    activity_label: str
    confidence: float
    message: str
    video_timestamp_s: Optional[float] = None


@dataclass
class DetectorState:
    wave_timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=20))
    sleep_start: Optional[float] = None
    current_activity: str = "other"
    last_movement_time: Optional[float] = None
    last_alert_time: Dict[AlertType, float] = field(default_factory=dict)


class SOSDetector:
    """
    Feed one prediction at a time via .update(); collect emitted events.
    """

    def __init__(self):
        self.cfg = ALERT_THRESHOLDS
        self.state = DetectorState()
        self._events: List[SOSEvent] = []

    @property
    def events(self) -> List[SOSEvent]:
        evts = list(self._events)
        self._events.clear()
        return evts

    def _cooldown_ok(self, atype: AlertType) -> bool:
        last = self.state.last_alert_time.get(atype)
        if last is None:
            return True
        return (time.time() - last) >= self.cfg["cooldown_minutes"] * 60

    def _emit(
        self,
        atype: AlertType,
        label: str,
        conf: float,
        msg: str,
        vid_ts: Optional[float] = None,
    ) -> None:
        if not self._cooldown_ok(atype):
            return

        evt = SOSEvent(
            alert_type=atype,
            timestamp=time.time(),
            activity_label=label,
            confidence=conf,
            message=msg,
            video_timestamp_s=vid_ts,
        )
        self._events.append(evt)
        self.state.last_alert_time[atype] = time.time()
        print(f"[SOS] {atype.name}: {msg}")

    def check_proactive_fall_risk(
        self,
        gait_result: dict,
        video_timestamp_s: Optional[float] = None,
    ) -> Optional[SOSEvent]:
        """
        Returns a proactive fall-risk event when gait risk is high.
        """
        risk_score = float(gait_result.get("risk_score", 0.0))
        risk_level = str(gait_result.get("risk_level", "LOW")).upper()

        if risk_level == "HIGH" and self._cooldown_ok(AlertType.FALL_RISK):
            evt = SOSEvent(
                alert_type=AlertType.FALL_RISK,
                timestamp=time.time(),
                activity_label="walking",
                confidence=risk_score,
                message=(
                    f"HIGH FALL RISK DETECTED\n"
                    f"Risk Score: {risk_score:.0%}\n"
                    f"Trunk Sway: {gait_result.get('trunk_sway', 0.0):.3f}\n"
                    f"Step Asymmetry: {gait_result.get('step_asymmetry', 0.0):.3f}\n"
                    f"Recommend: Check on elder immediately"
                ),
                video_timestamp_s=video_timestamp_s,
            )
            self.state.last_alert_time[AlertType.FALL_RISK] = time.time()
            print(f"[SOS] FALL_RISK: {evt.message}")
            return evt

        return None

    def update(
        self,
        activity_label: str,
        confidence: float,
        video_timestamp_s: Optional[float] = None,
        gait_result: Optional[dict] = None,
    ) -> List[SOSEvent]:
        """
        Call once per inference step.
        Returns list of new SOS events.
        """
        now = time.time()
        self.state.current_activity = activity_label

        # 1. Fall detection
        if (
            activity_label == "fall"
            and confidence >= self.cfg["fall_confidence_threshold"]
        ):
            self._emit(
                AlertType.FALL,
                activity_label,
                confidence,
                f"FALL DETECTED (conf={confidence:.0%})",
                video_timestamp_s,
            )

        # 2. Wave SOS
        if activity_label == "wave":
            self.state.wave_timestamps.append(now)

            window = self.cfg["wave_window_seconds"]
            recent = [t for t in self.state.wave_timestamps if now - t <= window]
            self.state.wave_timestamps = deque(recent, maxlen=20)

            if len(recent) >= self.cfg["wave_count_trigger"]:
                self._emit(
                    AlertType.WAVE_SOS,
                    activity_label,
                    confidence,
                    f"SOS WAVE DETECTED ({len(recent)} waves in {window}s)",
                    video_timestamp_s,
                )
                self.state.wave_timestamps.clear()

        # 3. Prolonged sleep
        if activity_label == "sleep":
            if self.state.sleep_start is None:
                self.state.sleep_start = now
            else:
                sleep_hours = (now - self.state.sleep_start) / 3600.0
                if sleep_hours >= self.cfg["prolonged_sleep_hours"]:
                    self._emit(
                        AlertType.PROLONGED_SLEEP,
                        activity_label,
                        confidence,
                        f"PROLONGED SLEEP: {sleep_hours:.1f} hours",
                        video_timestamp_s,
                    )
        else:
            self.state.sleep_start = None

        # 4. Inactivity
        active_labels = {"walk", "eat", "wave", "stand"}
        if activity_label in active_labels:
            self.state.last_movement_time = now
        elif self.state.last_movement_time is not None:
            idle_minutes = (now - self.state.last_movement_time) / 60.0
            if idle_minutes >= self.cfg["inactivity_alert_minutes"]:
                self._emit(
                    AlertType.PROLONGED_INACTIVITY,
                    activity_label,
                    confidence,
                    f"NO MOVEMENT for {idle_minutes:.0f} minutes",
                    video_timestamp_s,
                )

        # 5. Proactive gait-based alert
        if gait_result is not None:
            evt = self.check_proactive_fall_risk(
                gait_result,
                video_timestamp_s=video_timestamp_s,
            )
            if evt is not None:
                self._events.append(evt)

        return self.events

    def simulate(self, timeline: List[Tuple[float, str, float]]) -> List[SOSEvent]:
        """
        timeline: [(video_timestamp_s, label, confidence), ...]
        """
        all_events: List[SOSEvent] = []
        for ts, label, conf in timeline:
            evts = self.update(label, conf, video_timestamp_s=ts)
            all_events.extend(evts)
        return all_events
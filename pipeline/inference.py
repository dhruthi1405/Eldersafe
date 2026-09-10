from __future__ import annotations

import argparse
import collections
import os
import sys
import time
from pathlib import Path
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configs.config import MODEL_CONFIG, ROOT_DIR
from pipeline.pose_extractor import HybridPoseExtractor, YOLO_KP_NAMES
from pipeline.gait_analyzer import GaitAnalyzer
from models.tcn_lstm_model import build_model
from models.activity_model import build_activity_model

# Note: Alert imports are lazy-loaded in __init__ to avoid import errors when alerts module unavailable


ACTIVITY_CLASSES = ["walk", "sit", "stand", "eat", "sleep", "wave", "other"]
BINARY_CLASSES = ["no_fall", "fall"]


def _kps_to_feature(kps: dict) -> np.ndarray:
    row = []
    for name in YOLO_KP_NAMES:
        val = kps.get(name, (0.0, 0.0, 0.0))

        if isinstance(val, dict):
            x = float(val.get("x", 0.0))
            y = float(val.get("y", 0.0))
            c = float(val.get("conf", 0.0))
        elif isinstance(val, (tuple, list)) and len(val) >= 3:
            x, y, c = float(val[0]), float(val[1]), float(val[2])
        else:
            x, y, c = 0.0, 0.0, 0.0

        row += [x, y, c]
    return np.array(row, dtype=np.float32)


def _feature_coord_indices(axis: str) -> List[int]:
    offset = 0 if axis == "x" else 1
    return [i * 3 + offset for i in range(len(YOLO_KP_NAMES))]


def _flatten_kps_for_gait(kps: dict) -> dict:
    flat = {}
    for name in YOLO_KP_NAMES:
        val = kps.get(name, (0.0, 0.0, 0.0))

        if isinstance(val, dict):
            x = float(val.get("x", 0.0))
            y = float(val.get("y", 0.0))
            c = float(val.get("conf", 0.0))
        elif isinstance(val, (tuple, list)) and len(val) >= 3:
            x, y, c = float(val[0]), float(val[1]), float(val[2])
        else:
            x, y, c = 0.0, 0.0, 0.0

        flat[f"{name}_x"] = x
        flat[f"{name}_y"] = y
        flat[f"{name}_conf"] = c

    return flat


def _pose_quality(kps: dict) -> Tuple[int, float]:
    confs = []
    for name in YOLO_KP_NAMES:
        val = kps.get(name, (0.0, 0.0, 0.0))

        if isinstance(val, dict):
            c = float(val.get("conf", 0.0))
        elif isinstance(val, (tuple, list)) and len(val) >= 3:
            c = float(val[2])
        else:
            c = 0.0

        confs.append(c)

    detected = sum(c > 0.2 for c in confs)
    avg_conf = float(np.mean(confs)) if confs else 0.0
    return detected, avg_conf


def _fall_posture_score(kps: dict) -> Tuple[int, str]:
    def get(name: str) -> Tuple[float, float, float]:
        val = kps.get(name, (0.0, 0.0, 0.0))
        if isinstance(val, dict):
            return (
                float(val.get("x", 0.0)),
                float(val.get("y", 0.0)),
                float(val.get("conf", 0.0)),
            )
        if isinstance(val, (tuple, list)) and len(val) >= 3:
            return float(val[0]), float(val[1]), float(val[2])
        return 0.0, 0.0, 0.0

    confident_points = []
    for name in YOLO_KP_NAMES:
        x, y, c = get(name)
        if c > 0.2:
            confident_points.append((x, y))

    score = 0
    reasons = []

    if confident_points:
        xs = [p[0] for p in confident_points]
        ys = [p[1] for p in confident_points]
        bbox_w = max(xs) - min(xs)
        bbox_h = max(ys) - min(ys)
        aspect = bbox_w / (bbox_h + 1e-6)
        if aspect >= 0.95:
            score += 1
            reasons.append(f"wide_body={aspect:.2f}")

    ls = get("left_shoulder")
    rs = get("right_shoulder")
    lh = get("left_hip")
    rh = get("right_hip")
    la = get("left_ankle")
    ra = get("right_ankle")
    nose = get("nose")

    if min(ls[2], rs[2], lh[2], rh[2]) > 0.2:
        shoulder_x = (ls[0] + rs[0]) / 2.0
        shoulder_y = (ls[1] + rs[1]) / 2.0
        hip_x = (lh[0] + rh[0]) / 2.0
        hip_y = (lh[1] + rh[1]) / 2.0
        torso_horizontal = abs(shoulder_x - hip_x) / (abs(shoulder_y - hip_y) + 1e-6)
        if torso_horizontal >= 0.55:
            score += 1
            reasons.append(f"torso_sideways={torso_horizontal:.2f}")

        if nose[2] > 0.2:
            head_above_hips = hip_y - nose[1]
            if head_above_hips <= 0.09:
                score += 1
                reasons.append(f"head_low={head_above_hips:.2f}")

        if min(la[2], ra[2]) > 0.2:
            ankle_y = (la[1] + ra[1]) / 2.0
            ankles_below_hips = ankle_y - hip_y
            if ankles_below_hips <= 0.07:
                score += 1
                reasons.append(f"legs_not_below={ankles_below_hips:.2f}")

    return score, ",".join(reasons) if reasons else "upright"


def _sitting_posture_score(kps: dict) -> Tuple[int, str]:
    def get(name: str) -> Tuple[float, float, float]:
        val = kps.get(name, (0.0, 0.0, 0.0))
        if isinstance(val, dict):
            return (
                float(val.get("x", 0.0)),
                float(val.get("y", 0.0)),
                float(val.get("conf", 0.0)),
            )
        if isinstance(val, (tuple, list)) and len(val) >= 3:
            return float(val[0]), float(val[1]), float(val[2])
        return 0.0, 0.0, 0.0

    def angle(a, b, c) -> Optional[float]:
        if min(a[2], b[2], c[2]) <= 0.2:
            return None
        v1 = np.array([a[0] - b[0], a[1] - b[1]], dtype=np.float32)
        v2 = np.array([c[0] - b[0], c[1] - b[1]], dtype=np.float32)
        denom = (np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-6
        cosang = float(np.clip(np.dot(v1, v2) / denom, -1.0, 1.0))
        return float(np.degrees(np.arccos(cosang)))

    ls = get("left_shoulder")
    rs = get("right_shoulder")
    lh = get("left_hip")
    rh = get("right_hip")
    lk = get("left_knee")
    rk = get("right_knee")
    la = get("left_ankle")
    ra = get("right_ankle")

    score = 0
    reasons = []

    if min(ls[2], rs[2], lh[2], rh[2]) > 0.2:
        shoulder_x = (ls[0] + rs[0]) / 2.0
        shoulder_y = (ls[1] + rs[1]) / 2.0
        hip_x = (lh[0] + rh[0]) / 2.0
        hip_y = (lh[1] + rh[1]) / 2.0
        torso_vertical = abs(shoulder_y - hip_y)
        torso_lean = abs(shoulder_x - hip_x) / (torso_vertical + 1e-6)
        if torso_vertical >= 0.12 and torso_lean <= 0.85:
            score += 1
            reasons.append(f"upright_torso={torso_lean:.2f}")

    knee_angles = [a for a in (angle(lh, lk, la), angle(rh, rk, ra)) if a is not None]
    if knee_angles:
        min_knee_angle = min(knee_angles)
        if 45.0 <= min_knee_angle <= 145.0:
            score += 1
            reasons.append(f"bent_knee={min_knee_angle:.0f}")

    thigh_ratios = []
    for hip, knee in ((lh, lk), (rh, rk)):
        if min(hip[2], knee[2]) > 0.2:
            thigh_ratios.append(abs(knee[0] - hip[0]) / (abs(knee[1] - hip[1]) + 1e-6))
    if thigh_ratios and max(thigh_ratios) >= 0.35:
        score += 1
        reasons.append(f"folded_hip={max(thigh_ratios):.2f}")

    if min(lh[2], rh[2], lk[2], rk[2], la[2], ra[2]) > 0.2:
        hip_y = (lh[1] + rh[1]) / 2.0
        knee_y = (lk[1] + rk[1]) / 2.0
        ankle_y = (la[1] + ra[1]) / 2.0
        if ankle_y > knee_y > hip_y:
            score += 1
            reasons.append("legs_below_hips")

    return score, ",".join(reasons) if reasons else "not_sitting"


def _sleep_posture_score(kps: dict) -> Tuple[int, str]:
    def get(name: str) -> Tuple[float, float, float]:
        val = kps.get(name, (0.0, 0.0, 0.0))
        if isinstance(val, dict):
            return (
                float(val.get("x", 0.0)),
                float(val.get("y", 0.0)),
                float(val.get("conf", 0.0)),
            )
        if isinstance(val, (tuple, list)) and len(val) >= 3:
            return float(val[0]), float(val[1]), float(val[2])
        return 0.0, 0.0, 0.0

    confident_points = []
    for name in YOLO_KP_NAMES:
        x, y, c = get(name)
        if c > 0.2:
            confident_points.append((x, y))

    score = 0
    reasons = []

    if confident_points:
        xs = [p[0] for p in confident_points]
        ys = [p[1] for p in confident_points]
        bbox_w = max(xs) - min(xs)
        bbox_h = max(ys) - min(ys)
        aspect = bbox_w / (bbox_h + 1e-6)
        if aspect >= 0.65:
            score += 1
            reasons.append(f"wide_body={aspect:.2f}")

    ls = get("left_shoulder")
    rs = get("right_shoulder")
    lh = get("left_hip")
    rh = get("right_hip")
    la = get("left_ankle")
    ra = get("right_ankle")
    nose = get("nose")

    if min(ls[2], rs[2], lh[2], rh[2]) > 0.2:
        shoulder_x = (ls[0] + rs[0]) / 2.0
        shoulder_y = (ls[1] + rs[1]) / 2.0
        hip_x = (lh[0] + rh[0]) / 2.0
        hip_y = (lh[1] + rh[1]) / 2.0
        torso_horizontal = abs(shoulder_x - hip_x) / (abs(shoulder_y - hip_y) + 1e-6)
        if torso_horizontal >= 0.45:
            score += 1
            reasons.append(f"horizontal_torso={torso_horizontal:.2f}")

        if nose[2] > 0.2:
            head_hip_gap = abs(nose[1] - hip_y)
            if head_hip_gap <= 0.28:
                score += 1
                reasons.append(f"head_level={head_hip_gap:.2f}")

        if min(la[2], ra[2]) > 0.2:
            ankle_y = (la[1] + ra[1]) / 2.0
            if abs(ankle_y - hip_y) <= 0.45:
                score += 1
                reasons.append(f"legs_level={abs(ankle_y - hip_y):.2f}")

    return score, ",".join(reasons) if reasons else "not_sleeping"


def _eating_posture_score(kps: dict) -> Tuple[int, str]:
    def get(name: str) -> Tuple[float, float, float]:
        val = kps.get(name, (0.0, 0.0, 0.0))
        if isinstance(val, dict):
            return (
                float(val.get("x", 0.0)),
                float(val.get("y", 0.0)),
                float(val.get("conf", 0.0)),
            )
        if isinstance(val, (tuple, list)) and len(val) >= 3:
            return float(val[0]), float(val[1]), float(val[2])
        return 0.0, 0.0, 0.0

    def dist(a, b) -> float:
        return float(np.hypot(a[0] - b[0], a[1] - b[1]))

    nose = get("nose")
    left_wrist = get("left_wrist")
    right_wrist = get("right_wrist")
    left_elbow = get("left_elbow")
    right_elbow = get("right_elbow")
    left_shoulder = get("left_shoulder")
    right_shoulder = get("right_shoulder")

    score = 0
    reasons = []

    wrist_face_distances = []
    for wrist in (left_wrist, right_wrist):
        if min(wrist[2], nose[2]) > 0.2:
            wrist_face_distances.append(dist(wrist, nose))

    if wrist_face_distances:
        nearest = min(wrist_face_distances)
        if nearest <= 0.22:
            score += 1
            reasons.append(f"hand_near_face={nearest:.2f}")

    for wrist, elbow, shoulder, side in (
        (left_wrist, left_elbow, left_shoulder, "left"),
        (right_wrist, right_elbow, right_shoulder, "right"),
    ):
        if min(wrist[2], elbow[2], shoulder[2]) > 0.2:
            upper = dist(shoulder, elbow)
            lower = dist(elbow, wrist)
            direct = dist(shoulder, wrist)
            if direct < (upper + lower) * 0.72:
                score += 1
                reasons.append(f"{side}_arm_bent")
            if wrist[1] <= shoulder[1] + 0.18:
                score += 1
                reasons.append(f"{side}_hand_high")

    return score, ",".join(reasons) if reasons else "not_eating"


class InferenceEngine:
    def __init__(
        self,
        root_dir: str,
        binary_model_path: Optional[str] = None,
        activity_model_path: Optional[str] = None,
        yolo_weights: str = "yolov8n-pose.pt",
        enable_alerts: bool = False,
        enable_email_alerts: bool = True,
        enable_firebase_alerts: bool = True,
        show_live: bool = False,
        fall_threshold: Optional[float] = None,
    ):
        self.root_dir = root_dir
        self.mc = MODEL_CONFIG
        self.seq_len = self.mc["sequence_length"]
        self.show_live = show_live
        self.enable_alerts = enable_alerts
        self.fall_threshold = (
            float(fall_threshold)
            if fall_threshold is not None
            else float(self.mc.get("fall_detection_threshold", 0.5))
        )
        self.fall_confirm_frames = int(self.mc.get("fall_confirm_frames", 3))
        self.activity_confirm_frames = int(self.mc.get("activity_confirm_frames", 3))
        self.fall_counter = 0
        self.activity_counter_label = "other"
        self.activity_counter = 0
        self.confirmed_activity_label = "other"
        self.confirmed_activity_conf = 0.0
        self.activity_vote_window = int(self.mc.get("activity_vote_window", 15))
        self.activity_history: Deque[Tuple[str, float]] = collections.deque(maxlen=self.activity_vote_window)
        self.frame_count = 0  # For debug logging
        self.coord_min, self.coord_scale = self._load_training_coord_normalization()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        self.binary_model_path = binary_model_path or os.path.join(root_dir, "models", "binary_fall_best.pth")
        print(f"Loading binary fall model: {self.binary_model_path}")

        self.binary_model = build_model(num_classes=2).to(self.device)
        checkpoint = torch.load(self.binary_model_path, map_location=self.device)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            self.binary_model.load_state_dict(checkpoint["model_state_dict"])
        else:
            self.binary_model.load_state_dict(checkpoint)
        self.binary_model.eval()

        self.activity_model_path = activity_model_path or os.path.join(root_dir, "models", "activity_best.pth")
        print(f"Loading activity model: {self.activity_model_path}")

        checkpoint = torch.load(self.activity_model_path, map_location=self.device)
        if isinstance(checkpoint, dict) and checkpoint.get("model_type") == "activity_stats":
            self.activity_model = build_activity_model(num_classes=len(ACTIVITY_CLASSES)).to(self.device)
            self.activity_model.load_state_dict(checkpoint["model_state_dict"])
        else:
            self.activity_model = build_model(num_classes=len(ACTIVITY_CLASSES)).to(self.device)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                self.activity_model.load_state_dict(checkpoint["model_state_dict"])
            else:
                self.activity_model.load_state_dict(checkpoint)
        self.activity_model.eval()

        print("Both models loaded successfully.")

        self.extractor = HybridPoseExtractor(yolo_weights=yolo_weights)
        self.frame_buffer: Deque[np.ndarray] = collections.deque(maxlen=self.seq_len)
        self.gait_analyzer = GaitAnalyzer()
        self.last_gait_result = {"risk_score": 0.0, "risk_level": "unknown"}

        # Lazy-load alert modules only when needed
        try:
            from alerts.sos_detector import SOSDetector
            self.sos_detector = SOSDetector()
        except ImportError as e:
            print(f"⚠️  Warning: SOSDetector not available: {e}")
            self.sos_detector = None
        
        # Initialize alert sender (email, firebase, or both)
        if enable_alerts:
            if enable_email_alerts or enable_firebase_alerts:
                try:
                    from alerts.firebase_alert import MultiAlertSender
                    self.alert_sender = MultiAlertSender(
                        enable_email=enable_email_alerts,
                        enable_firebase=enable_firebase_alerts
                    )
                    print(f"[Alerts] Email: {enable_email_alerts} | Firebase: {enable_firebase_alerts}")
                except ImportError as e:
                    print(f"⚠️  Warning: MultiAlertSender not available: {e}")
                    self.alert_sender = None
            else:
                self.alert_sender = None
        else:
            self.alert_sender = None

        self.sos_log_path = os.path.join(root_dir, "logs", "sos_alerts.csv")
        os.makedirs(os.path.join(root_dir, "logs"), exist_ok=True)

    def _load_training_coord_normalization(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        try:
            import pandas as pd

            coord_cols = []
            for name in YOLO_KP_NAMES:
                coord_cols.extend([f"{name}_x", f"{name}_y"])

            source_files = [
                os.path.join(self.root_dir, "datasets", "processed", "pose", "fall_video_dataset", "hybrid_pose_clean.csv"),
                os.path.join(self.root_dir, "datasets", "processed", "pose", "har_video_dataset", "hybrid_pose_clean.csv"),
                os.path.join(self.root_dir, "datasets", "processed", "pose", "hmdb51", "hybrid_pose_clean.csv"),
                os.path.join(self.root_dir, "datasets", "processed", "pose", "le2i_imvia", "hybrid_pose_clean.csv"),
                os.path.join(self.root_dir, "datasets", "processed", "pose", "multiple_cameras_fall", "hybrid_pose_clean.csv"),
                os.path.join(self.root_dir, "datasets", "processed", "synthetic_pose.csv"),
            ]

            frames = []
            for path in source_files:
                if os.path.exists(path):
                    frames.append(pd.read_csv(path, low_memory=False, usecols=lambda c: c in coord_cols))

            if not frames:
                print("Training coordinate normalization unavailable; using live normalized coordinates.")
                return None, None

            df = pd.concat(frames, ignore_index=True)
            df[coord_cols] = df[coord_cols].clip(lower=0)

            mins = df[coord_cols].min().astype(np.float32).values
            maxs = df[coord_cols].max().astype(np.float32).values
            scale = maxs - mins
            scale[scale == 0] = 1.0

            print("Loaded training coordinate normalization for live inference.")
            return mins, scale
        except Exception as e:
            print(f"Training coordinate normalization failed: {e}")
            return None, None

    def _prepare_model_feature(self, feat: np.ndarray, frame_shape: Tuple[int, int, int]) -> np.ndarray:
        # Live hybrid extraction already returns normalized coordinates. The model
        # training CSV used normalized coordinates, while some intermediate CSVs
        # contain pixel-scale values. Applying the mixed normalizer here made
        # normal walking look like a high-confidence fall.
        return feat.astype(np.float32)

    def _confirm_activity(self, label: str, confidence: float) -> Tuple[str, float]:
        if label == self.activity_counter_label:
            self.activity_counter += 1
        else:
            self.activity_counter_label = label
            self.activity_counter = 1

        if label == "other" or self.activity_counter >= self.activity_confirm_frames:
            self.confirmed_activity_label = label
            self.confirmed_activity_conf = confidence

        return self.confirmed_activity_label, self.confirmed_activity_conf

    def _smooth_activity(self, label: str, confidence: float) -> Tuple[str, float]:
        self.activity_history.append((label, confidence))

        scores = collections.defaultdict(float)
        counts = collections.Counter()

        for hist_label, hist_conf in self.activity_history:
            if hist_label == "other" and hist_conf < 0.50:
                continue

            weight = max(float(hist_conf), 0.25)
            if hist_label == self.confirmed_activity_label:
                weight *= 1.10

            scores[hist_label] += weight
            counts[hist_label] += 1

        if not scores:
            return self._confirm_activity(label, confidence)

        best_label = max(scores, key=scores.get)
        best_count = counts[best_label]
        min_votes = 2 if best_label in {"sleep", "sit", "eat", "wave"} else self.activity_confirm_frames

        if best_label == self.confirmed_activity_label or best_count >= min_votes:
            self.confirmed_activity_label = best_label
            self.confirmed_activity_conf = min(0.99, scores[best_label] / max(best_count, 1))
        elif self.confirmed_activity_label == "other":
            self.confirmed_activity_label = label
            self.confirmed_activity_conf = confidence

        return self.confirmed_activity_label, self.confirmed_activity_conf

    def _predict_sequence(self, seq: np.ndarray) -> Tuple[str, float, float, str, float, float]:
        x = torch.from_numpy(seq).unsqueeze(0).to(self.device)

        with torch.no_grad():
            binary_probs = F.softmax(self.binary_model(x), dim=-1)[0].cpu().numpy()
            no_fall_conf = float(binary_probs[0])
            fall_conf = float(binary_probs[1])

            # DEBUG: Always log fall confidence
            if fall_conf > 0.10:
                print(
                    f"Fall confidence: {fall_conf:.4f} | "
                    f"No-fall confidence: {no_fall_conf:.4f} | "
                    f"Threshold: {self.fall_threshold:.4f} | "
                    f"{'DETECTED' if fall_conf >= self.fall_threshold else 'LOW'}"
                )

            activity_probs = F.softmax(self.activity_model(x), dim=-1)[0].cpu().numpy()
            act_idx = int(activity_probs.argmax())
            act_label = ACTIVITY_CLASSES[act_idx]
            act_conf = float(activity_probs[act_idx])

            if fall_conf >= self.fall_threshold:
                print(f"FALL DETECTED (conf={fall_conf:.4f})")
                return "fall", fall_conf, fall_conf, act_label, act_conf, no_fall_conf

            return act_label, act_conf, fall_conf, act_label, act_conf, no_fall_conf

    def process_frame(self, frame: np.ndarray, video_ts: float = 0.0) -> Tuple[np.ndarray, str, float, dict, float, str, float, float, int, float]:
        kps = self.extractor.extract(frame)
        pose_kp_count, pose_avg_conf = _pose_quality(kps)
        posture_score, posture_reason = _fall_posture_score(kps)
        sitting_score, sitting_reason = _sitting_posture_score(kps)
        sleep_score, sleep_reason = _sleep_posture_score(kps)
        eating_score, eating_reason = _eating_posture_score(kps)

        gait_input = _flatten_kps_for_gait(kps)
        self.last_gait_result = self.gait_analyzer.update(gait_input)

        feat = self._prepare_model_feature(_kps_to_feature(kps), frame.shape)
        self.frame_buffer.append(feat)

        final_label = "other"
        final_conf = 0.0
        fall_conf = 0.0
        no_fall_conf = 0.0
        activity_label = "other"
        activity_conf = 0.0

        if len(self.frame_buffer) == self.seq_len:
            seq = np.stack(list(self.frame_buffer))
            final_label, final_conf, fall_conf, activity_label, activity_conf, no_fall_conf = self._predict_sequence(seq)
            if final_label == "fall" and posture_score < 1:
                print(
                    f"Suppressing fall: conf={fall_conf:.4f}, "
                    f"posture_score={posture_score}, posture={posture_reason}"
                )
                final_label = activity_label
                final_conf = activity_conf
                fall_conf = 0.0

            gait_score = float(self.last_gait_result.get("risk_score", 0.0) or 0.0)
            if (
                final_label != "fall"
                and sleep_score >= 2
                and (
                    "horizontal_torso" in sleep_reason
                    or ("wide_body" in sleep_reason and "head_level" in sleep_reason and "legs_level" in sleep_reason)
                )
                and pose_kp_count >= 10
                and pose_avg_conf >= 0.35
                and activity_label in {"walk", "sit", "stand", "eat", "other"}
            ):
                print(
                    f"Correcting activity to sleep: model={activity_label} "
                    f"({activity_conf:.2f}), sleep_score={sleep_score}, "
                    f"reason={sleep_reason}"
                )
                activity_label = "sleep"
                activity_conf = max(activity_conf, 0.85)
                final_label = "sleep"
                final_conf = activity_conf

            if (
                final_label != "fall"
                and sleep_score >= 2
                and (
                    "horizontal_torso" in sleep_reason
                    or ("wide_body" in sleep_reason and "head_level" in sleep_reason)
                )
                and pose_kp_count >= 8
                and pose_avg_conf >= 0.25
                and activity_label in {"sit", "eat"}
                and activity_conf < 0.90
            ):
                print(
                    f"Correcting low-confidence {activity_label} to sleep: "
                    f"model_conf={activity_conf:.2f}, sleep_score={sleep_score}, "
                    f"reason={sleep_reason}"
                )
                activity_label = "sleep"
                activity_conf = max(activity_conf, 0.80)
                final_label = "sleep"
                final_conf = activity_conf

            if (
                final_label != "fall"
                and activity_label == "eat"
                and (activity_conf < 0.65 or eating_score < 2)
            ):
                corrected_label = "other"
                corrected_conf = min(activity_conf, 0.45)
                if (
                    sitting_score >= 3
                    and sleep_score < 3
                    and "upright_torso" in sitting_reason
                    and pose_kp_count >= 10
                    and pose_avg_conf >= 0.35
                ):
                    corrected_label = "sit"
                    corrected_conf = 0.80

                print(
                    f"Rejecting weak eat activity: model_conf={activity_conf:.2f}, "
                    f"eating_score={eating_score}, reason={eating_reason}; "
                    f"using {corrected_label}"
                )
                activity_label = corrected_label
                activity_conf = corrected_conf
                final_label = activity_label
                final_conf = activity_conf

            if (
                final_label != "fall"
                and activity_label == "other"
                and posture_score == 0
                and sitting_score < 2
                and sleep_score < 3
                and 0.25 <= gait_score <= 0.65
            ):
                activity_label = "walk"
                activity_conf = max(activity_conf, 0.75)
                final_label = "walk"
                final_conf = activity_conf

            if (
                final_label != "fall"
                and sitting_score >= 3
                and sleep_score < 3
                and "upright_torso" in sitting_reason
                and pose_kp_count >= 10
                and pose_avg_conf >= 0.35
                and activity_label in {"walk", "stand", "other"}
            ):
                print(
                    f"Correcting activity to sit: model={activity_label} "
                    f"({activity_conf:.2f}), sitting_score={sitting_score}, "
                    f"reason={sitting_reason}"
                )
                activity_label = "sit"
                activity_conf = max(activity_conf, 0.85)
                final_label = "sit"
                final_conf = activity_conf

            if final_label != "fall":
                activity_label, activity_conf = self._smooth_activity(activity_label, activity_conf)
                final_label = activity_label
                final_conf = activity_conf

        fall_candidate = (
            fall_conf >= self.fall_threshold
            and posture_score >= 1
            and pose_kp_count >= 10
            and pose_avg_conf >= 0.35
        )
        if fall_candidate:
            self.fall_counter += 1
        else:
            self.fall_counter = 0

        fall_status = "FALLING" if self.fall_counter >= self.fall_confirm_frames else "NOT FALLING"
        if fall_status != "FALLING" and final_label == "fall":
            final_label = activity_label
            final_conf = activity_conf
            fall_conf = 0.0

        events = []
        if self.sos_detector and len(self.frame_buffer) == self.seq_len:
            events = self.sos_detector.update(
                final_label,
                final_conf,
                video_timestamp_s=video_ts,
                gait_result=self.last_gait_result,
            )

        if events and self.alert_sender:
            self.alert_sender.send_bulk(events)
            self._log_sos_events(events, video_ts)

        skel = self.extractor.render_skeleton(
            frame,
            kps,
            label=None,
            confidence=0.0,
        )

        risk_level = self.last_gait_result.get("risk_level", "unknown")
        risk_score = self.last_gait_result.get("risk_score", 0.0)

        if fall_status == "FALLING":
            panel_color = (0, 0, 190)
            status_text = "FALL DETECTED"
            status_color = (255, 255, 255)
        else:
            panel_color = (20, 85, 20)
            status_text = "NO FALL"
            status_color = (180, 255, 180)

        h, w = skel.shape[:2]
        panel_w = min(max(300, int(w * 0.36)), w - 24)
        panel_h = 116
        panel = skel.copy()
        cv2.rectangle(panel, (12, 12), (12 + panel_w, 12 + panel_h), (10, 10, 10), -1)
        cv2.rectangle(panel, (12, 12), (12 + panel_w, 44), panel_color, -1)
        skel = cv2.addWeighted(panel, 0.78, skel, 0.22, 0)
        cv2.rectangle(skel, (12, 12), (12 + panel_w, 12 + panel_h), (70, 70, 70), 1)

        cv2.putText(skel, status_text, (24, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.62, status_color, 2, cv2.LINE_AA)
        cv2.putText(skel, f"Fall conf: {fall_conf:.2f}", (24, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 230, 255), 1, cv2.LINE_AA)
        cv2.putText(skel, f"Activity: {activity_label.upper()} ({activity_conf:.2f})", (24, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (245, 245, 245), 1, cv2.LINE_AA)
        cv2.putText(skel, f"Gait risk: {risk_level} ({risk_score:.2f})", (24, 114), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (210, 210, 210), 1, cv2.LINE_AA)

        return (
            skel,
            final_label,
            final_conf,
            self.last_gait_result,
            fall_conf,
            activity_label,
            activity_conf,
            no_fall_conf,
            pose_kp_count,
            pose_avg_conf,
        )

    def _log_sos_events(self, events, video_ts: float):
        import pandas as pd

        rows = []
        for event in events:
            rows.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "video_ts": video_ts,
                "alert_type": str(getattr(event, "alert_type", "unknown")),
                "message": str(getattr(event, "message", "")),
                "confidence": str(getattr(event, "confidence", "")),
            })

        df_new = pd.DataFrame(rows)

        if os.path.exists(self.sos_log_path):
            df_old = pd.read_csv(self.sos_log_path)
            df_all = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df_all = df_new

        df_all.to_csv(self.sos_log_path, index=False)

    def _create_video_writer(self, out_video: str, fps: float, frame_skip: int, w: int, h: int):
        os.makedirs(os.path.dirname(os.path.abspath(out_video)), exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_video, fourcc, fps / max(frame_skip, 1), (w, h))

        if not writer.isOpened():
            raise RuntimeError("Could not open VideoWriter with mp4v codec")

        print("Using video codec: mp4v")
        return writer

    def run_video(
        self,
        source,
        out_video: Optional[str] = None,
        out_csv: Optional[str] = None,
        frame_skip: int = 3,
    ) -> List[dict]:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise IOError(f"Cannot open source: {source}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        effective_frame_skip = frame_skip

        if total_frames > 0:
            estimated_samples = max(1, total_frames // max(frame_skip, 1))
            if estimated_samples < self.seq_len:
                effective_frame_skip = max(1, total_frames // self.seq_len)
                print(
                    f"Short video detected: {total_frames} frames gives only "
                    f"{estimated_samples} samples at frame_skip={frame_skip}. "
                    f"Using frame_skip={effective_frame_skip} for inference."
                )

        writer: Optional[cv2.VideoWriter] = None
        if out_video:
            writer = self._create_video_writer(out_video, fps, effective_frame_skip, w, h)

        rows: List[dict] = []
        fi = 0
        t0 = time.time()
        last_processed_frame: Optional[np.ndarray] = None

        print(f"Processing: {source}")

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if fi % effective_frame_skip != 0:
                fi += 1
                continue

            vid_ts = fi / fps
            last_processed_frame = frame
            (
                skel,
                final_label,
                final_conf,
                gait,
                fall_conf,
                activity_label,
                activity_conf,
                no_fall_conf,
                pose_kp_count,
                pose_avg_conf,
            ) = self.process_frame(frame, video_ts=vid_ts)

            if writer:
                writer.write(skel)

            if self.show_live:
                cv2.imshow("ElderSafe - Skeleton", skel)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            smooth_status = "FALLING" if self.fall_counter >= self.fall_confirm_frames else "NOT FALLING"

            rows.append({
                "frame_idx": fi,
                "timestamp_s": vid_ts,
                "label": final_label,
                "confidence": final_conf,
                "no_fall_confidence": no_fall_conf,
                "fall_confidence": fall_conf,
                "fall_status": smooth_status,
                "activity_label": activity_label,
                "activity_confidence": activity_conf,
                "pose_keypoints_detected": pose_kp_count,
                "pose_avg_confidence": pose_avg_conf,
                "gait_risk": gait.get("risk_score", 0.0),
                "gait_level": gait.get("risk_level", "unknown"),
            })

            if fi % 100 == 0:
                print(
                    f"Frame {fi} | Status: {smooth_status} | "
                    f"FallConf: {fall_conf:.4f} | "
                    f"PoseKP: {pose_kp_count}/17 ({pose_avg_conf:.2f}) | "
                    f"Activity: {activity_label} ({activity_conf:.2f}) | "
                    f"Gait: {gait.get('risk_level', '?')} | "
                    f"{time.time() - t0:.1f}s elapsed"
                )

            fi += 1

        should_pad_tail = (
            total_frames > 0
            and last_processed_frame is not None
            and len(rows) >= self.seq_len
            and len(rows) < self.seq_len * 3
        )

        if should_pad_tail:
            print(
                f"Adding {self.seq_len} tail padding frames so end-of-video "
                "falls have enough temporal context."
            )
            for pad_idx in range(self.seq_len):
                pad_fi = fi + pad_idx * max(effective_frame_skip, 1)
                vid_ts = pad_fi / fps
                (
                    skel,
                    final_label,
                    final_conf,
                    gait,
                    fall_conf,
                    activity_label,
                    activity_conf,
                    no_fall_conf,
                    pose_kp_count,
                    pose_avg_conf,
                ) = self.process_frame(last_processed_frame, video_ts=vid_ts)

                if writer:
                    writer.write(skel)

                smooth_status = "FALLING" if self.fall_counter >= self.fall_confirm_frames else "NOT FALLING"

                rows.append({
                    "frame_idx": pad_fi,
                    "timestamp_s": vid_ts,
                    "label": final_label,
                    "confidence": final_conf,
                    "no_fall_confidence": no_fall_conf,
                    "fall_confidence": fall_conf,
                    "fall_status": smooth_status,
                    "activity_label": activity_label,
                    "activity_confidence": activity_conf,
                    "pose_keypoints_detected": pose_kp_count,
                    "pose_avg_confidence": pose_avg_conf,
                    "gait_risk": gait.get("risk_score", 0.0),
                    "gait_level": gait.get("risk_level", "unknown"),
                    "is_tail_padding": True,
                })

        cap.release()
        if writer:
            writer.release()
            print(f"Skeleton video saved: {out_video}")
        if self.show_live:
            cv2.destroyAllWindows()

        if out_csv and rows:
            import pandas as pd
            df = pd.DataFrame(rows)
            df.to_csv(out_csv, index=False)
            print(f"Predictions CSV saved: {out_csv}")

        return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", default=ROOT_DIR)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out_video", default=None)
    parser.add_argument("--out_csv", default=None)
    parser.add_argument("--binary_model_path", default=None)
    parser.add_argument("--activity_model_path", default=None)
    parser.add_argument("--yolo_weights", default="yolov8n-pose.pt")
    parser.add_argument("--frame_skip", type=int, default=3)
    parser.add_argument("--enable_alerts", action="store_true")
    parser.add_argument("--enable_email", action="store_true", default=True, help="Enable email alerts (default: True)")
    parser.add_argument("--disable_email", action="store_false", dest="enable_email", help="Disable email alerts")
    parser.add_argument("--enable_firebase", action="store_true", default=True, help="Enable Firebase push notifications (default: True)")
    parser.add_argument("--disable_firebase", action="store_false", dest="enable_firebase", help="Disable Firebase notifications")
    parser.add_argument("--show_live", action="store_true")
    parser.add_argument("--fall_threshold", type=float, default=None)
    args = parser.parse_args()

    source = int(args.source) if str(args.source).isdigit() else args.source

    engine = InferenceEngine(
        root_dir=args.root_dir,
        binary_model_path=args.binary_model_path,
        activity_model_path=args.activity_model_path,
        yolo_weights=args.yolo_weights,
        enable_alerts=args.enable_alerts,
        enable_email_alerts=args.enable_email,
        enable_firebase_alerts=args.enable_firebase,
        show_live=args.show_live,
        fall_threshold=args.fall_threshold,
    )

    engine.run_video(
        source,
        out_video=args.out_video,
        out_csv=args.out_csv,
        frame_skip=args.frame_skip,
    )

"""
pose_extractor.py
==================
Hybrid YOLO-v8 + MediaPipe pose extractor.

YOLO detects bounding boxes and 17 COCO keypoints.
MediaPipe provides 33 landmarks with visibility scores.
The two are merged: for each of the 17 COCO joints, whichever
source has higher confidence wins (or they are blended when both confident).
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from ultralytics import YOLO


# ── COCO 17 keypoint names (YOLO order) ──────────────────────────────────────
YOLO_KP_NAMES: List[str] = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# MediaPipe landmark indices → COCO 17 joint names
_MP_IDX: Dict[str, int] = {
    "nose": 0,
    "left_eye": 2, "right_eye": 5,
    "left_ear": 7, "right_ear": 8,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}

# COCO skeleton connectivity for rendering
SKELETON_EDGES: List[Tuple[str, str]] = [
    ("nose", "left_eye"), ("nose", "right_eye"),
    ("left_eye", "left_ear"), ("right_eye", "right_ear"),
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
]

_REGION_COLORS: Dict[str, Tuple[int, int, int]] = {
    "head":  (255, 220,  80),
    "arm":   (80, 220, 255),
    "torso": (80, 255, 140),
    "leg":   (255, 100, 180),
}

KP_Dict = Dict[str, Tuple[float, float, float]]  # name → (x_norm, y_norm, conf)


def _edge_color(a: str, b: str) -> Tuple[int, int, int]:
    head_joints = {"nose", "left_eye", "right_eye", "left_ear", "right_ear"}
    arm_joints = {
        "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow",
        "left_wrist", "right_wrist"
    }
    leg_joints = {
        "left_hip", "right_hip",
        "left_knee", "right_knee",
        "left_ankle", "right_ankle"
    }

    if a in head_joints or b in head_joints:
        return _REGION_COLORS["head"]
    if a in arm_joints or b in arm_joints:
        return _REGION_COLORS["arm"]
    if a in leg_joints or b in leg_joints:
        return _REGION_COLORS["leg"]
    return _REGION_COLORS["torso"]


class HybridPoseExtractor:
    """
    Merges YOLO-pose and MediaPipe keypoints for robust skeleton estimation.
    """

    def __init__(self, yolo_weights: str = "yolov8n-pose.pt", conf_threshold: float = 0.35):
        self.yolo = YOLO(yolo_weights)
        self.conf_threshold = conf_threshold
        self._mp_pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.4,
            min_tracking_confidence=0.4,
        )

    def _yolo_keypoints(self, frame: np.ndarray) -> KP_Dict:
        h, w = frame.shape[:2]
        results = self.yolo(frame, conf=self.conf_threshold, verbose=False)

        if not results:
            return {}

        r = results[0]
        if r.keypoints is None or r.keypoints.xy is None or len(r.keypoints.xy) == 0:
            return {}

        xy = r.keypoints.xy[0].cpu().numpy()
        conf = (
            r.keypoints.conf[0].cpu().numpy()
            if r.keypoints.conf is not None
            else np.ones(len(YOLO_KP_NAMES), dtype=np.float32)
        )

        return {
            name: (
                float(xy[i, 0]) / max(w, 1),
                float(xy[i, 1]) / max(h, 1),
                float(conf[i]),
            )
            for i, name in enumerate(YOLO_KP_NAMES)
        }

    def _mp_keypoints(self, frame: np.ndarray) -> KP_Dict:
        if frame is None or frame.size == 0:
            return {}

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self._mp_pose.process(rgb)

        if not res.pose_landmarks:
            return {}

        lm = res.pose_landmarks.landmark
        return {
            name: (float(lm[idx].x), float(lm[idx].y), float(lm[idx].visibility))
            for name, idx in _MP_IDX.items()
        }

    @staticmethod
    def _merge(yolo_kps: KP_Dict, mp_kps: KP_Dict) -> KP_Dict:
        merged: KP_Dict = {}

        for name in set(yolo_kps) | set(mp_kps):
            yv = yolo_kps.get(name)
            mv = mp_kps.get(name)

            if yv is None and mv is None:
                continue
            if yv is None:
                merged[name] = mv  # type: ignore[assignment]
                continue
            if mv is None:
                merged[name] = yv
                continue

            yx, yy, yc = yv
            mx, my, mc = mv

            if yc > 0.35 and mc > 0.35:
                t = yc + mc + 1e-8
                merged[name] = (
                    (yx * yc + mx * mc) / t,
                    (yy * yc + my * mc) / t,
                    max(yc, mc),
                )
            elif yc >= mc:
                merged[name] = yv
            else:
                merged[name] = mv

        return merged

    def extract(self, frame: np.ndarray) -> KP_Dict:
        if frame is None or frame.size == 0:
            return {}

        try:
            yolo_kps = self._yolo_keypoints(frame)
        except Exception:
            yolo_kps = {}

        try:
            mp_kps = self._mp_keypoints(frame)
        except Exception:
            mp_kps = {}

        return self._merge(yolo_kps, mp_kps)

    @staticmethod
    def render_skeleton(
        frame: np.ndarray,
        kps: KP_Dict,
        label: Optional[str] = None,
        confidence: float = 0.0,
        black_bg: bool = True,
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        canvas = np.zeros_like(frame) if black_bg else frame.copy()

        pts: Dict[str, Tuple[int, int, float]] = {}
        for name, (nx, ny, c) in kps.items():
            px, py = int(nx * w), int(ny * h)
            pts[name] = (px, py, c)

        for a, b in SKELETON_EDGES:
            if a in pts and b in pts:
                ax, ay, ac = pts[a]
                bx, by, bc = pts[b]
                if ac > 0.2 and bc > 0.2:
                    color = _edge_color(a, b)
                    thick = max(1, int(min(1.0, (ac + bc) / 2) * 3))
                    cv2.line(canvas, (ax, ay), (bx, by), color, thick, cv2.LINE_AA)

        for name, (px, py, c) in pts.items():
            if c > 0.2:
                r = max(3, int(c * 7))
                cv2.circle(canvas, (px, py), r, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(canvas, (px, py), r, _edge_color(name, name), 1, cv2.LINE_AA)

        if label:
            from configs.config import ACTIVITY_COLOR_MAP

            color_hex = ACTIVITY_COLOR_MAP.get(label, "#ffffff")
            r_c = int(color_hex[1:3], 16)
            g_c = int(color_hex[3:5], 16)
            b_c = int(color_hex[5:7], 16)

            text = f"{label.upper()}  {confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.8, 2)
            cv2.rectangle(canvas, (10, 10), (14 + tw, 14 + th + 4), (0, 0, 0), -1)
            cv2.putText(
                canvas,
                text,
                (12, 12 + th),
                cv2.FONT_HERSHEY_DUPLEX,
                0.8,
                (b_c, g_c, r_c),
                2,
                cv2.LINE_AA,
            )

        return canvas


def keypoints_to_row(video: str, frame_idx: int, label: int, kps: KP_Dict, dataset: str) -> Dict:
    row: Dict = {
        "dataset_name": dataset,
        "video": video,
        "frame_idx": frame_idx,
        "label": label,
    }

    for name in YOLO_KP_NAMES:
        x, y, c = kps.get(name, (0.0, 0.0, 0.0))
        row[f"{name}_x"] = x
        row[f"{name}_y"] = y
        row[f"{name}_conf"] = c

    return row


def pose_feature_columns() -> List[str]:
    cols: List[str] = []
    for name in YOLO_KP_NAMES:
        cols += [f"{name}_x", f"{name}_y", f"{name}_conf"]
    return cols


def _process_video(
    video_path: str,
    out_csv: str,
    render_skeleton_path: Optional[str],
    frame_skip: int,
    yolo_weights: str,
    label_name: Optional[str],
    dataset_name: str,
) -> None:
    extractor = HybridPoseExtractor(yolo_weights=yolo_weights)
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise IOError(f"Cannot open: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer: Optional[cv2.VideoWriter] = None

    if render_skeleton_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(render_skeleton_path, fourcc, fps, (w, h))

    rows: List[Dict] = []
    fi = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame is None or frame.size == 0:
            fi += 1
            continue

        if fi % frame_skip == 0:
            try:
                kps = extractor.extract(frame)
                rows.append(keypoints_to_row(os.path.basename(video_path), fi, 0, kps, dataset_name))

                if writer:
                    skel = extractor.render_skeleton(frame, kps, label=label_name)
                    writer.write(skel)

            except Exception as e:
                print(f"Failed frame in {video_path}: {e}")

        fi += 1

    cap.release()

    if writer:
        writer.release()
        print(f"Skeleton video saved → {render_skeleton_path}")

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    print(f"Pose CSV saved → {out_csv} ({len(df)} rows)")


def extract_pose_from_video(video_path: str, frame_skip: int = 3):
    extractor = HybridPoseExtractor()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open {video_path}")
        return None

    results = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame is None or frame.size == 0:
            frame_idx += 1
            continue

        if frame_idx % frame_skip == 0:
            try:
                kps = extractor.extract(frame)

                row = {}
                for name in YOLO_KP_NAMES:
                    x, y, conf = kps.get(name, (0.0, 0.0, 0.0))
                    row[f"{name}_x"] = x
                    row[f"{name}_y"] = y
                    row[f"{name}_conf"] = conf

                results.append(row)

            except Exception as e:
                print(f"Failed frame in {video_path}: {e}")

        frame_idx += 1

    cap.release()
    return results


def extract_pose_from_image_folder(folder_path: str, frame_skip: int = 3):
    extractor = HybridPoseExtractor()

    image_exts = (".jpg", ".jpeg", ".png")
    image_files = sorted(
        [f for f in os.listdir(folder_path) if f.lower().endswith(image_exts)]
    )

    if not image_files:
        print(f"No images found in {folder_path}")
        return None

    results = []

    for idx, image_file in enumerate(image_files):
        if idx % frame_skip != 0:
            continue

        image_path = os.path.join(folder_path, image_file)
        frame = cv2.imread(image_path)

        if frame is None or frame.size == 0:
            print(f"Failed to read image: {image_path}")
            continue

        try:
            kps = extractor.extract(frame)

            row = {}
            for name in YOLO_KP_NAMES:
                x, y, conf = kps.get(name, (0.0, 0.0, 0.0))
                row[f"{name}_x"] = x
                row[f"{name}_y"] = y
                row[f"{name}_conf"] = conf

            results.append(row)

        except Exception as e:
            print(f"Failed image: {image_path} -> {e}")

    return results


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--out_csv", required=True)
    parser.add_argument("--render_skeleton", default=None)
    parser.add_argument("--frame_skip", type=int, default=3)
    parser.add_argument("--yolo_weights", default="yolov8n-pose.pt")
    parser.add_argument("--label_name", default=None)
    parser.add_argument("--dataset_name", default="unknown")
    args = parser.parse_args()

    _process_video(
        args.video,
        args.out_csv,
        args.render_skeleton,
        args.frame_skip,
        args.yolo_weights,
        args.label_name,
        args.dataset_name,
    )
import os
import math
import random
import pandas as pd

YOLO_KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# Only minority classes
MINORITY_CLASSES = ["walk", "sit", "stand", "eat", "sleep", "wave"]


def _base_pose(label: str):
    pose = {
        "nose": (0.50, 0.18),
        "left_eye": (0.47, 0.16),
        "right_eye": (0.53, 0.16),
        "left_ear": (0.44, 0.17),
        "right_ear": (0.56, 0.17),
        "left_shoulder": (0.43, 0.28),
        "right_shoulder": (0.57, 0.28),
        "left_elbow": (0.39, 0.40),
        "right_elbow": (0.61, 0.40),
        "left_wrist": (0.36, 0.54),
        "right_wrist": (0.64, 0.54),
        "left_hip": (0.45, 0.50),
        "right_hip": (0.55, 0.50),
        "left_knee": (0.46, 0.70),
        "right_knee": (0.54, 0.70),
        "left_ankle": (0.46, 0.90),
        "right_ankle": (0.54, 0.90),
    }

    if label == "sit":
        pose["left_hip"] = (0.45, 0.58)
        pose["right_hip"] = (0.55, 0.58)
        pose["left_knee"] = (0.43, 0.72)
        pose["right_knee"] = (0.57, 0.72)
        pose["left_ankle"] = (0.41, 0.84)
        pose["right_ankle"] = (0.59, 0.84)

    elif label == "eat":
        pose["left_elbow"] = (0.42, 0.36)
        pose["right_elbow"] = (0.58, 0.36)
        pose["left_wrist"] = (0.46, 0.30)
        pose["right_wrist"] = (0.54, 0.30)

    elif label == "sleep":
        pose = {
            "nose": (0.25, 0.55),
            "left_eye": (0.23, 0.54),
            "right_eye": (0.27, 0.54),
            "left_ear": (0.21, 0.55),
            "right_ear": (0.29, 0.55),
            "left_shoulder": (0.35, 0.56),
            "right_shoulder": (0.43, 0.56),
            "left_elbow": (0.50, 0.57),
            "right_elbow": (0.57, 0.57),
            "left_wrist": (0.64, 0.58),
            "right_wrist": (0.71, 0.58),
            "left_hip": (0.46, 0.60),
            "right_hip": (0.55, 0.60),
            "left_knee": (0.66, 0.61),
            "right_knee": (0.75, 0.61),
            "left_ankle": (0.83, 0.62),
            "right_ankle": (0.91, 0.62),
        }

    elif label == "wave":
        pose["right_elbow"] = (0.60, 0.30)
        pose["right_wrist"] = (0.62, 0.20)

    elif label == "walk":
        pose["left_wrist"] = (0.34, 0.54)
        pose["right_wrist"] = (0.66, 0.54)

    return pose


def _apply_noise(x, y, scale=0.01):
    x += random.uniform(-scale, scale)
    y += random.uniform(-scale, scale)
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    return x, y


def _animate_pose(base, label, t, seq_len):
    pose = dict(base)
    denom = max(seq_len, 1)

    if label == "walk":
        swing = math.sin(2 * math.pi * t / denom)
        pose["left_wrist"] = (pose["left_wrist"][0] - 0.03 * swing, pose["left_wrist"][1])
        pose["right_wrist"] = (pose["right_wrist"][0] + 0.03 * swing, pose["right_wrist"][1])
        pose["left_ankle"] = (pose["left_ankle"][0] + 0.03 * swing, pose["left_ankle"][1])
        pose["right_ankle"] = (pose["right_ankle"][0] - 0.03 * swing, pose["right_ankle"][1])

    elif label == "wave":
        lift = 0.10 * abs(math.sin(2 * math.pi * t / denom))
        pose["right_elbow"] = (0.60, 0.30)
        pose["right_wrist"] = (0.62, 0.22 - lift)

    elif label == "eat":
        chew = 0.03 * abs(math.sin(2 * math.pi * t / denom))
        pose["right_elbow"] = (0.58, 0.34)
        pose["right_wrist"] = (0.54, 0.28 + chew)
        pose["left_elbow"] = (0.42, 0.34)
        pose["left_wrist"] = (0.46, 0.30 + 0.5 * chew)

    elif label == "stand":
        bob = 0.01 * math.sin(2 * math.pi * t / denom)
        for k, (x, y) in pose.items():
            pose[k] = (x, y + bob)

    elif label == "sit":
        bob = 0.008 * math.sin(2 * math.pi * t / denom)
        for k, (x, y) in pose.items():
            pose[k] = (x, y + bob)

    elif label == "sleep":
        still = 0.003 * math.sin(2 * math.pi * t / denom)
        for k, (x, y) in pose.items():
            pose[k] = (x, y + still)

    return pose


def _row_from_pose(video_name, frame_idx, label, pose):
    row = {
        "dataset_name": "synthetic",
        "video": video_name,
        "frame_idx": frame_idx,
        "label": label,
    }

    noise_scale = 0.012
    if label == "sleep":
        noise_scale = 0.004
    elif label in ("stand", "sit"):
        noise_scale = 0.008

    for kp in YOLO_KP_NAMES:
        x, y = pose.get(kp, (0.0, 0.0))
        x, y = _apply_noise(x, y, scale=noise_scale)
        conf = random.uniform(0.80, 0.99)

        row[f"{kp}_x"] = x
        row[f"{kp}_y"] = y
        row[f"{kp}_conf"] = conf

    return row


def generate_synthetic_pose_csv(
    root_dir: str,
    sequences_per_class: int = 500,
    seq_len: int = 30,
    seed: int = 42,
):
    random.seed(seed)

    out_dir = os.path.join(root_dir, "datasets", "processed")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "synthetic_pose.csv")

    rows = []

    for label in MINORITY_CLASSES:
        for seq_id in range(sequences_per_class):
            video_name = f"synthetic_{label}_{seq_id:04d}.mp4"
            base = _base_pose(label)

            speed = random.uniform(0.8, 1.2)
            phase_shift = random.randint(0, max(seq_len - 1, 0))
            flip_x = random.random() < 0.5 and label in {"walk", "stand", "sit", "eat"}

            for t in range(seq_len):
                t_scaled = int((t * speed + phase_shift)) % seq_len
                pose = _animate_pose(base, label, t_scaled, seq_len)

                if flip_x:
                    flipped_pose = {}
                    for kp, (x, y) in pose.items():
                        flipped_pose[kp] = (1.0 - x, y)
                    pose = flipped_pose

                rows.append(_row_from_pose(video_name, t, label, pose))

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)

    print(f"Synthetic CSV saved: {out_csv}")
    print(f"Minority classes: {MINORITY_CLASSES}")
    print(f"Sequences per class: {sequences_per_class}")
    print(f"Sequence length: {seq_len}")
    print(f"Rows: {len(df)}")


if __name__ == "__main__":
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    generate_synthetic_pose_csv(
        root_dir=ROOT_DIR,
        sequences_per_class=500,
        seq_len=30,
        seed=42,
    )
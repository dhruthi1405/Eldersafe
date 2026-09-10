import os
import pandas as pd

KEYPOINT_MAP = {
    "Nose": "nose",
    "Left Eye": "left_eye",
    "Right Eye": "right_eye",
    "Left Ear": "left_ear",
    "Right Ear": "right_ear",
    "Left Shoulder": "left_shoulder",
    "Right Shoulder": "right_shoulder",
    "Left Elbow": "left_elbow",
    "Right Elbow": "right_elbow",
    "Left Wrist": "left_wrist",
    "Right Wrist": "right_wrist",
    "Left Hip": "left_hip",
    "Right Hip": "right_hip",
    "Left Knee": "left_knee",
    "Right Knee": "right_knee",
    "Left Ankle": "left_ankle",
    "Right Ankle": "right_ankle",
}

EXPECTED_ORDER = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


def convert_single_csv(csv_path: str, label_name: str, dataset_name: str):
    df = pd.read_csv(csv_path)

    required = {"Frame", "Keypoint", "X", "Y", "Confidence"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {csv_path}: {missing}")

    df = df.copy()
    df["Keypoint"] = df["Keypoint"].map(KEYPOINT_MAP)

    df = df.dropna(subset=["Keypoint"])

    rows = []
    for frame_id, group in df.groupby("Frame"):
        row = {
            "dataset_name": dataset_name,
            "video": os.path.splitext(os.path.basename(csv_path))[0],
            "frame_idx": int(frame_id),
            "label": label_name,
        }

        for kp in EXPECTED_ORDER:
            row[f"{kp}_x"] = 0.0
            row[f"{kp}_y"] = 0.0
            row[f"{kp}_conf"] = 0.0

        for _, r in group.iterrows():
            kp = r["Keypoint"]
            row[f"{kp}_x"] = float(r["X"])
            row[f"{kp}_y"] = float(r["Y"])
            row[f"{kp}_conf"] = float(r["Confidence"])

        rows.append(row)

    return rows


def convert_fall_dataset_csvs(root_dir: str):
    base_dir = os.path.join(root_dir, "datasets", "raw", "fall_video_dataset")
    out_dir = os.path.join(root_dir, "datasets", "processed", "pose", "fall_video_dataset")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "hybrid_pose.csv")

    all_rows = []

    for split_name, label_name in [("Fall", "fall"), ("No_Fall", "other")]:
        csv_dir = os.path.join(base_dir, split_name, "Keypoints_CSV")
        if not os.path.exists(csv_dir):
            print(f"Missing folder: {csv_dir}")
            continue

        for file in os.listdir(csv_dir):
            if file.lower().endswith(".csv"):
                csv_path = os.path.join(csv_dir, file)
                try:
                    rows = convert_single_csv(csv_path, label_name, "fall_video_dataset")
                    all_rows.extend(rows)
                    print(f"Converted: {file} ({len(rows)} frames)")
                except Exception as e:
                    print(f"Failed: {csv_path} -> {e}")

    if not all_rows:
        print("No fall_video_dataset CSV data converted.")
        return

    out_df = pd.DataFrame(all_rows)
    out_df.to_csv(out_csv, index=False)
    print(f"Saved converted CSV: {out_csv} ({len(out_df)} rows)")
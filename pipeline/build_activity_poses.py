from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from configs.config import ROOT_DIR
from pipeline.pose_extractor import YOLO_KP_NAMES


ACTIVITY_CLASSES = {"walk", "sit", "stand", "eat", "sleep", "wave", "other"}


def _pose_cols() -> list[str]:
    cols: list[str] = []
    for name in YOLO_KP_NAMES:
        cols.extend([f"{name}_x", f"{name}_y", f"{name}_conf"])
    return cols


def _load_source(path: Path, source_type: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["label"] = df["label"].fillna("other").astype(str).str.strip().str.lower()
    df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"
    df = df[df["label"].isin(ACTIVITY_CLASSES)].copy()
    df["source_type"] = source_type
    return df


def build_activity_poses(root_dir: str = ROOT_DIR) -> str:
    root = Path(root_dir)
    out_path = root / "datasets" / "processed" / "activity_poses.csv"

    sources = [
        (
            root / "datasets" / "processed" / "pose" / "har_video_dataset" / "hybrid_pose_clean.csv",
            "real_har",
        ),
        (
            root / "datasets" / "processed" / "pose" / "hmdb51" / "hybrid_pose_clean.csv",
            "real_hmdb51",
        ),
        (
            root / "datasets" / "processed" / "synthetic_pose.csv",
            "synthetic",
        ),
    ]

    frames = []
    for path, source_type in sources:
        if not path.exists():
            print(f"Skipping missing source: {path}")
            continue
        frame = _load_source(path, source_type)
        frames.append(frame)
        print(f"Loaded {path} ({len(frame)} rows)")

    if not frames:
        raise FileNotFoundError("No activity pose sources were found.")

    df = pd.concat(frames, ignore_index=True)

    required_cols = ["dataset_name", "video", "frame_idx", "label"] + _pose_cols()
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df[required_cols + ["source_type"]].copy()

    coord_cols = [col for col in df.columns if col.endswith("_x") or col.endswith("_y")]
    conf_cols = [col for col in df.columns if col.endswith("_conf")]

    for col in coord_cols + conf_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Activity sources are intended to match live inference: normalized 0..1
    # coordinates. Clip small extractor/annotation outliers instead of applying a
    # global min/max normalization that would reintroduce dataset artifacts.
    df[coord_cols] = df[coord_cols].clip(lower=0.0, upper=1.0)
    df[conf_cols] = df[conf_cols].clip(lower=0.0, upper=1.0)

    df = df.drop_duplicates(subset=["dataset_name", "video", "frame_idx"], keep="first")
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    os.makedirs(out_path.parent, exist_ok=True)
    df.to_csv(out_path, index=False)

    print("\nActivity dataset saved:", out_path)
    print("Rows:", len(df))
    print("Label distribution:")
    print(df["label"].value_counts())
    print("\nCoordinate range:")
    print(df[coord_cols].describe().loc[["min", "max", "mean"]])

    return str(out_path)


if __name__ == "__main__":
    build_activity_poses()

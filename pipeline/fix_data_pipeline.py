"""
fix_data_pipeline.py
===================
FIX for corrupted training data:

PROBLEM: 
- normalize_all_poses.py normalized ALL datasets together
- This mixed pixel-scale fall data (0-1920) with already-normalized activity data (0-1)
- Result: activity coordinates got compressed to 0.0001, poisoning the activity model

SOLUTION:
- Build separate activity_train.csv from HMDB51 + synthetic (already clean)
- Build separate fall_train.csv from LE2I + multiple_cameras (pixel-scale, properly normalized)
- Point models to their respective clean CSVs
"""

import os
import pandas as pd
from pathlib import Path


YOLO_KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


def convert_eldersafe_le2i_csv(
    root_dir: str = ".",
    source_csv: str = r"C:\ElderSafe_Project\output\features_raw.csv",
):
    """
    Convert the old ElderSafe LE2I YOLO pose CSV into ElderCare's 17-keypoint
    training format.

    Old columns:
      video, frame_idx, label, kp_0_nose_x, kp_0_nose_y, kp_0_nose_conf, ...

    New columns:
      nose_x, nose_y, nose_conf, ..., video, dataset_name, frame_idx, label
    """
    print("\n" + "=" * 60)
    print("CONVERTING ELDERSAFE LE2I CSV")
    print("=" * 60)

    source_path = Path(source_csv)
    if not source_path.exists():
        print(f"Source not found: {source_path}")
        return None

    old_df = pd.read_csv(source_path, low_memory=False)
    print(f"Loaded old ElderSafe CSV: {source_path}")
    print(f"Rows: {len(old_df)}")

    rows = {}
    for idx, name in enumerate(YOLO_KP_NAMES):
        for suffix in ["x", "y", "conf"]:
            old_col = f"kp_{idx}_{name}_{suffix}"
            new_col = f"{name}_{suffix}"
            if old_col not in old_df.columns:
                raise ValueError(f"Missing expected old column: {old_col}")
            rows[new_col] = pd.to_numeric(old_df[old_col], errors="coerce").fillna(0.0)

    converted = pd.DataFrame(rows)
    converted["video"] = old_df.get("video", "unknown").astype(str)
    converted["dataset_name"] = "le2i_eldersafe"
    converted["frame_idx"] = pd.to_numeric(old_df.get("frame_idx", 0), errors="coerce").fillna(0).astype(int)

    label_values = pd.to_numeric(old_df.get("label", 0), errors="coerce").fillna(0).astype(int)
    converted["label"] = label_values.map({1: "fall", 0: "other"}).fillna("other")

    coord_cols = [c for c in converted.columns if c.endswith("_x") or c.endswith("_y")]
    conf_cols = [c for c in converted.columns if c.endswith("_conf")]
    converted[coord_cols] = converted[coord_cols].clip(lower=0.0, upper=1.0)
    converted[conf_cols] = converted[conf_cols].clip(lower=0.0, upper=1.0)

    all_zero_pose = (converted[coord_cols + conf_cols].sum(axis=1) == 0.0)
    zero_count = int(all_zero_pose.sum())
    if zero_count:
        converted = converted.loc[~all_zero_pose].copy()
        print(f"Dropped all-zero pose rows: {zero_count}")

    converted = converted.drop_duplicates().sort_values(["video", "frame_idx"]).reset_index(drop=True)

    output_path = (
        Path(root_dir)
        / "datasets"
        / "processed"
        / "pose"
        / "le2i_eldersafe"
        / "hybrid_pose_clean.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    converted.to_csv(output_path, index=False)

    print(f"Saved converted LE2I source: {output_path}")
    print(f"Rows: {len(converted)}")
    print("Label distribution:")
    print(converted["label"].value_counts().to_string())
    print("Coordinate range:")
    print(f"min={converted[coord_cols].min().min():.6f}, max={converted[coord_cols].max().max():.6f}")

    return output_path


def build_activity_train_csv(root_dir: str = "."):
    """
    Build clean activity training CSV from HMDB51 + synthetic sources.
    These are already normalized (0-1 range), don't double-normalize.
    """
    print("\n" + "="*60)
    print("BUILDING CLEAN ACTIVITY TRAINING CSV")
    print("="*60)
    
    pose_dir = Path(root_dir) / "datasets" / "processed" / "pose"
    all_dfs = []
    
    # Only include activity datasets. They should already be close to live
    # normalized coordinates, but extractor/annotation outliers still need
    # clipping to match inference.
    activity_datasets = ["hmdb51", "har_video_dataset"]
    
    for dataset_name in activity_datasets:
        csv_path = pose_dir / dataset_name / "hybrid_pose_clean.csv"
        if not csv_path.exists():
            csv_path = pose_dir / dataset_name / "hybrid_pose.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            print(f"✓ Loaded {dataset_name}: {len(df)} rows, columns: {list(df.columns)}")
            print(f"  Sample nose_x range: {df['nose_x'].min():.6f} - {df['nose_x'].max():.6f}")
            all_dfs.append(df)
        else:
            print(f"⚠ Not found: {csv_path}")
    
    # Include synthetic data (also already normalized)
    synthetic_csv = Path(root_dir) / "datasets" / "processed" / "synthetic_pose.csv"
    if synthetic_csv.exists():
        syn_df = pd.read_csv(synthetic_csv)
        print(f"✓ Loaded synthetic: {len(syn_df)} rows")
        print(f"  Sample nose_x range: {syn_df['nose_x'].min():.6f} - {syn_df['nose_x'].max():.6f}")
        all_dfs.append(syn_df)
    else:
        print(f"⚠ Not found: {synthetic_csv}")
    
    if not all_dfs:
        print("❌ No activity datasets found!")
        return None
    
    # Merge without min/max re-normalizing. The old global min/max step mixed
    # pixel-scale fall data with normalized activity data and crushed activity
    # coordinates near zero.
    activity_df = pd.concat(all_dfs, ignore_index=True)
    
    print(f"\n✓ Merged: {len(activity_df)} rows")
    
    # Clean: deduplicate, fill NaNs, shuffle
    initial_rows = len(activity_df)
    activity_df = activity_df.drop_duplicates()
    print(f"  After dedup: {len(activity_df)} rows (removed {initial_rows - len(activity_df)})")
    
    activity_df["label"] = activity_df["label"].fillna("other").astype(str).str.strip().str.lower()
    activity_df.loc[activity_df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"
    activity_df = activity_df[
        activity_df["label"].isin(["walk", "sit", "stand", "eat", "sleep", "wave", "other"])
    ].copy()

    coord_cols = [c for c in activity_df.columns if c.endswith("_x") or c.endswith("_y")]
    conf_cols = [c for c in activity_df.columns if c.endswith("_conf")]

    for col in coord_cols + conf_cols:
        activity_df[col] = pd.to_numeric(activity_df[col], errors="coerce").fillna(0.0)

    activity_df[coord_cols] = activity_df[coord_cols].clip(lower=0.0, upper=1.0)
    activity_df[conf_cols] = activity_df[conf_cols].clip(lower=0.0, upper=1.0)
    
    # Verify normalization ranges
    x_cols = [c for c in activity_df.columns if c.endswith("_x")]
    x_min = activity_df[x_cols].min().min()
    x_max = activity_df[x_cols].max().max()
    print(f"✓ X coordinate range: {x_min:.6f} - {x_max:.6f} (should be ~0-1)")
    
    # Shuffle and save
    activity_df = activity_df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    output_path = Path(root_dir) / "datasets" / "processed" / "activity_train.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    activity_df.to_csv(output_path, index=False)
    
    print(f"\n✅ Saved: {output_path}")
    print(f"   Rows: {len(activity_df)}")
    print(f"   Columns: {len(activity_df.columns)}")
    
    # Show label distribution
    if "label" in activity_df.columns:
        print("\n   Label distribution:")
        for label, count in activity_df["label"].value_counts().items():
            print(f"     {label}: {count} ({count/len(activity_df)*100:.1f}%)")
    
    return output_path


def build_fall_train_csv_v2(root_dir: str = "."):
    """Build fall_train.csv from fall_video_dataset, converted LE2I, and multiple_cameras_fall."""
    print("\n" + "=" * 60)
    print("BUILDING CLEAN FALL TRAINING CSV V2")
    print("=" * 60)

    pose_dir = Path(root_dir) / "datasets" / "processed" / "pose"
    fall_datasets = ["fall_video_dataset", "le2i_eldersafe", "multiple_cameras_fall"]
    all_dfs = []

    for dataset_name in fall_datasets:
        csv_path = pose_dir / dataset_name / "hybrid_pose_clean.csv"
        if not csv_path.exists():
            csv_path = pose_dir / dataset_name / "hybrid_pose.csv"

        if not csv_path.exists():
            print(f"Missing fall source: {csv_path}")
            continue

        df = pd.read_csv(csv_path, low_memory=False)
        df["label"] = df["label"].fillna("other").astype(str).str.strip().str.lower()
        df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"
        df = df[df["label"].isin(["fall", "other"])].copy()
        df["dataset_name"] = dataset_name

        if dataset_name == "fall_video_dataset":
            parts = []
            for label in ["fall", "other"]:
                part = df[df["label"] == label]
                parts.append(part.sample(n=min(len(part), 12000), random_state=42))
            df = pd.concat(parts, ignore_index=True)

        print(f"Loaded {dataset_name}: {len(df)} rows")
        print(df["label"].value_counts().to_string())
        all_dfs.append(df)

    if not all_dfs:
        print("No fall datasets found.")
        return None

    fall_df = pd.concat(all_dfs, ignore_index=True).drop_duplicates()

    coord_cols = [c for c in fall_df.columns if c.endswith("_x") or c.endswith("_y")]
    conf_cols = [c for c in fall_df.columns if c.endswith("_conf")]

    for col in coord_cols + conf_cols:
        fall_df[col] = pd.to_numeric(fall_df[col], errors="coerce").fillna(0.0)

    normalized_frames = []
    for dataset_name, source_df in fall_df.groupby("dataset_name", sort=False):
        source_df = source_df.copy()
        coord_min = source_df[coord_cols].min().min()
        coord_max = source_df[coord_cols].max().max()

        if coord_min < -0.25 or coord_max > 1.25:
            for col in coord_cols:
                col_min = source_df[col].min()
                col_max = source_df[col].max()
                if pd.isna(col_min) or pd.isna(col_max) or col_max == col_min:
                    source_df[col] = 0.0
                else:
                    source_df[col] = (source_df[col] - col_min) / (col_max - col_min)

        source_df[coord_cols] = source_df[coord_cols].clip(lower=0.0, upper=1.0)
        source_df[conf_cols] = source_df[conf_cols].clip(lower=0.0, upper=1.0)
        normalized_frames.append(source_df)

    fall_df = pd.concat(normalized_frames, ignore_index=True)
    fall_df = fall_df.sample(frac=1, random_state=42).reset_index(drop=True)

    output_path = Path(root_dir) / "datasets" / "processed" / "fall_train.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fall_df.to_csv(output_path, index=False)

    print(f"\nSaved: {output_path}")
    print(f"Rows: {len(fall_df)}")
    print(f"Columns: {len(fall_df.columns)}")
    print("Label distribution:")
    print(fall_df["label"].value_counts().to_string())
    print("Source distribution:")
    print(fall_df["dataset_name"].value_counts().to_string())
    print("Coordinate range:")
    print(f"min={fall_df[coord_cols].min().min():.6f}, max={fall_df[coord_cols].max().max():.6f}")

    return output_path


def build_fall_binary_from_all_poses(root_dir: str = "."):
    """
    Build a binary fall dataset from all_poses.csv.

    fall stays fall. Every non-fall activity label becomes other so the binary
    model learns that walking, sitting, standing, eating, sleeping, and waving
    are safe no-fall states.
    """
    print("\n" + "=" * 60)
    print("BUILDING BINARY FALL DATASET FROM ALL_POSES")
    print("=" * 60)

    input_path = Path(root_dir) / "datasets" / "processed" / "all_poses.csv"
    if not input_path.exists():
        print(f"Missing source: {input_path}")
        return None

    df = pd.read_csv(input_path, low_memory=False)
    print(f"Loaded: {input_path}")
    print(f"Rows: {len(df)}")
    print("Original label distribution:")
    print(df["label"].astype(str).str.lower().value_counts().to_string())

    df["label"] = df["label"].fillna("other").astype(str).str.strip().str.lower()
    df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"
    df["label"] = df["label"].apply(lambda value: "fall" if value == "fall" else "other")

    coord_cols = [c for c in df.columns if c.endswith("_x") or c.endswith("_y")]
    conf_cols = [c for c in df.columns if c.endswith("_conf")]
    feature_cols = coord_cols + conf_cols

    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df[coord_cols] = df[coord_cols].clip(lower=0.0, upper=1.0)
    df[conf_cols] = df[conf_cols].clip(lower=0.0, upper=1.0)

    output_path = Path(root_dir) / "datasets" / "processed" / "fall_binary_from_all_poses.csv"
    df.to_csv(output_path, index=False)

    print(f"\nSaved: {output_path}")
    print(f"Rows: {len(df)}")
    print("Binary label distribution:")
    print(df["label"].value_counts().to_string())
    if "dataset_name" in df.columns:
        print("Source distribution:")
        print(df["dataset_name"].value_counts().to_string())
        print("Binary labels by source:")
        print(pd.crosstab(df["dataset_name"], df["label"]).to_string())
    print("Coordinate range:")
    print(f"min={df[coord_cols].min().min():.6f}, max={df[coord_cols].max().max():.6f}")

    return output_path


def _clean_pose_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    coord_cols = [c for c in df.columns if c.endswith("_x") or c.endswith("_y")]
    conf_cols = [c for c in df.columns if c.endswith("_conf")]

    for col in coord_cols + conf_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    coord_min = df[coord_cols].min().min()
    coord_max = df[coord_cols].max().max()
    if coord_min < -0.25 or coord_max > 1.25:
        for col in coord_cols:
            col_min = df[col].min()
            col_max = df[col].max()
            if pd.isna(col_min) or pd.isna(col_max) or col_max == col_min:
                df[col] = 0.0
            else:
                df[col] = (df[col] - col_min) / (col_max - col_min)

    df[coord_cols] = df[coord_cols].clip(lower=0.0, upper=1.0)
    df[conf_cols] = df[conf_cols].clip(lower=0.0, upper=1.0)

    all_zero_pose = df[coord_cols + conf_cols].sum(axis=1) == 0.0
    if all_zero_pose.any():
        df = df.loc[~all_zero_pose].copy()

    return df


def build_fall_binary_train_csv(root_dir: str = "."):
    """
    Build the final binary fall training dataset.

    Sources:
      - fall_video_dataset: fall + no-fall
      - multiple_cameras_fall: fall + no-fall
      - le2i_eldersafe: converted LE2I fall + no-fall
      - activity_train.csv: normal no-fall examples, excluding sleep for now

    Output labels are only: fall, other.
    """
    print("\n" + "=" * 60)
    print("BUILDING FINAL BINARY FALL TRAINING CSV")
    print("=" * 60)

    root = Path(root_dir)
    pose_dir = root / "datasets" / "processed" / "pose"
    parts = []

    fall_sources = {
        "fall_video_dataset": pose_dir / "fall_video_dataset" / "hybrid_pose_clean.csv",
        "multiple_cameras_fall": pose_dir / "multiple_cameras_fall" / "hybrid_pose_clean.csv",
        "le2i_eldersafe": pose_dir / "le2i_eldersafe" / "hybrid_pose_clean.csv",
    }

    for dataset_name, csv_path in fall_sources.items():
        if not csv_path.exists():
            alt_path = csv_path.with_name("hybrid_pose.csv")
            csv_path = alt_path if alt_path.exists() else csv_path
        if not csv_path.exists():
            print(f"Missing fall source: {csv_path}")
            continue

        df = pd.read_csv(csv_path, low_memory=False)
        df["dataset_name"] = dataset_name
        df["label"] = df["label"].fillna("other").astype(str).str.strip().str.lower()
        df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"
        df["label"] = df["label"].apply(lambda value: "fall" if value == "fall" else "other")
        df = _clean_pose_frame(df)
        parts.append(df)
        print(f"Loaded {dataset_name}: {len(df)} rows")
        print(df["label"].value_counts().to_string())

    activity_csv = root / "datasets" / "processed" / "activity_train.csv"
    if activity_csv.exists():
        act_df = pd.read_csv(activity_csv, low_memory=False)
        act_df["label"] = act_df["label"].fillna("other").astype(str).str.strip().str.lower()
        # Sleep/lying can look like a fallen posture; keep it for activity
        # recognition, but exclude it from the binary fall model until we have
        # stronger bed/lying no-fall coverage.
        act_df = act_df[~act_df["label"].isin(["fall", "sleep", "nan", "none", "null"])].copy()
        act_df["label"] = "other"
        act_df = _clean_pose_frame(act_df)
        parts.append(act_df)
        print(f"Loaded activity no-fall examples: {len(act_df)} rows")
        print(act_df["dataset_name"].value_counts().to_string())
    else:
        print(f"Missing activity source: {activity_csv}")

    if not parts:
        print("No sources found.")
        return None

    final_df = pd.concat(parts, ignore_index=True).drop_duplicates()
    final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)

    output_path = root / "datasets" / "processed" / "fall_binary_train.csv"
    final_df.to_csv(output_path, index=False)

    coord_cols = [c for c in final_df.columns if c.endswith("_x") or c.endswith("_y")]
    print(f"\nSaved: {output_path}")
    print(f"Rows: {len(final_df)}")
    print("Binary label distribution:")
    print(final_df["label"].value_counts().to_string())
    print("Source distribution:")
    print(final_df["dataset_name"].value_counts().to_string())
    print("Binary labels by source:")
    print(pd.crosstab(final_df["dataset_name"], final_df["label"]).to_string())
    print("Coordinate range:")
    print(f"min={final_df[coord_cols].min().min():.6f}, max={final_df[coord_cols].max().max():.6f}")

    return output_path


def build_fall_train_csv(root_dir: str = "."):
    """
    Build clean fall training CSV from LE2I + multiple_cameras.
    These are pixel-scale (0-1920+), need proper normalization.
    """
    print("\n" + "="*60)
    print("BUILDING CLEAN FALL TRAINING CSV")
    print("="*60)
    
    pose_dir = Path(root_dir) / "datasets" / "processed" / "pose"
    all_dfs = []
    
    # Only include fall datasets (pixel-scale)
    fall_datasets = ["le2i_imvia", "multiple_cameras_fall"]
    
    for dataset_name in fall_datasets:
        csv_path = pose_dir / dataset_name / "hybrid_pose.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            print(f"✓ Loaded {dataset_name}: {len(df)} rows")
            print(f"  Sample nose_x range: {df['nose_x'].min():.1f} - {df['nose_x'].max():.1f} (pixel-scale)")
            all_dfs.append(df)
        else:
            print(f"⚠ Not found: {csv_path}")
    
    if not all_dfs:
        print("❌ No fall datasets found!")
        return None
    
    fall_df = pd.concat(all_dfs, ignore_index=True)
    print(f"\n✓ Merged: {len(fall_df)} rows")
    
    # Clean
    initial_rows = len(fall_df)
    fall_df = fall_df.drop_duplicates()
    print(f"  After dedup: {len(fall_df)} rows (removed {initial_rows - len(fall_df)})")
    
    # Normalize ONLY these columns independently (fall-specific)
    coord_cols = [c for c in fall_df.columns 
                  if c.endswith(("_x", "_y"))]
    
    print(f"\n  Normalizing {len(coord_cols)} coordinate columns...")
    for col in coord_cols:
        col_min = fall_df[col].min()
        col_max = fall_df[col].max()
        
        if pd.isna(col_min) or pd.isna(col_max):
            fall_df[col] = 0.0
        elif col_max == col_min:
            fall_df[col] = 0.0
        else:
            fall_df[col] = (fall_df[col] - col_min) / (col_max - col_min)
    
    # Verify
    x_cols = [c for c in fall_df.columns if c.endswith("_x")]
    x_min = fall_df[x_cols].min().min()
    x_max = fall_df[x_cols].max().max()
    print(f"✓ X coordinate range after normalization: {x_min:.6f} - {x_max:.6f}")
    
    # Shuffle and save
    fall_df = fall_df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    output_path = Path(root_dir) / "datasets" / "processed" / "fall_train.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fall_df.to_csv(output_path, index=False)
    
    print(f"\n✅ Saved: {output_path}")
    print(f"   Rows: {len(fall_df)}")
    print(f"   Columns: {len(fall_df.columns)}")
    
    # Show label distribution
    if "label" in fall_df.columns:
        print("\n   Label distribution:")
        for label, count in fall_df["label"].value_counts().items():
            print(f"     {label}: {count} ({count/len(fall_df)*100:.1f}%)")
    
    return output_path


if __name__ == "__main__":
    import sys
    
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    print("\n" + "🔧 DATA PIPELINE FIX".center(60, "="))
    print("Separating activity and fall training data to prevent corruption")
    
    activity_csv = build_activity_train_csv(root_dir)
    fall_csv = build_fall_train_csv_v2(root_dir)
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    if activity_csv:
        print(f"\n1. Update models/activity_train.py:")
        print(f"   TRAINING_CSV = '{activity_csv}'")
    
    if fall_csv:
        print(f"\n2. Update models/binary_fall_train.py:")
        print(f"   TRAINING_CSV = '{fall_csv}'")
    
    print(f"\n3. Retrain models:")
    print(f"   python models/activity_train.py")
    print(f"   python models/binary_fall_train.py")
    
    print("\n" + "="*60)

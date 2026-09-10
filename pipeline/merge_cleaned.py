import pandas as pd

files = [
    "datasets/processed/pose/fall_video_dataset/hybrid_pose_clean.csv",
    "datasets/processed/pose/har_video_dataset/hybrid_pose_clean.csv",
    "datasets/processed/pose/hmdb51/hybrid_pose_clean.csv",
    "datasets/processed/pose/le2i_imvia/hybrid_pose_clean.csv",
    "datasets/processed/pose/multiple_cameras_fall/hybrid_pose_clean.csv",
    "datasets/processed/synthetic_pose.csv",
]

dfs = []

for f in files:
    df = pd.read_csv(f, low_memory=False)

    if "dataset_name" not in df.columns:
        dataset_name = f.split("/")[-2]
        df["dataset_name"] = dataset_name

    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"

    dfs.append(df)
    print(f"Loaded: {f} -> {len(df)} rows")

all_df = pd.concat(dfs, ignore_index=True)

all_df = all_df.dropna(subset=["video", "frame_idx"])
all_df = all_df.drop_duplicates()

if {"dataset_name", "video", "frame_idx"}.issubset(all_df.columns):
    all_df = all_df.drop_duplicates(
        subset=["dataset_name", "video", "frame_idx"],
        keep="first"
    )

all_df = all_df.sort_values(
    ["dataset_name", "video", "frame_idx"]
).reset_index(drop=True)

out_path = "datasets/processed/all_poses.csv"
all_df.to_csv(out_path, index=False)

print("\nMerged successfully.")
print(f"Saved: {out_path}")
print("\nFinal label distribution:")
print(all_df["label"].value_counts(dropna=False))
print(f"\nTotal rows: {len(all_df)}")
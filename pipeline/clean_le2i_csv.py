import pandas as pd

CSV_PATH = "datasets/processed/pose/le2i_imvia/hybrid_pose.csv"
OUT_PATH = "datasets/processed/pose/le2i_imvia/hybrid_pose_clean.csv"


def clean_le2i_csv(csv_path, out_path):
    print(f"\nCleaning LE2I: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)

    print("\nBefore cleaning:")
    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())

    # remove exact duplicate rows
    df = df.drop_duplicates()

    # remove duplicate frame entries per video
    if {"video", "frame_idx"}.issubset(df.columns):
        df = df.drop_duplicates(subset=["video", "frame_idx"], keep="first")

    # fix frame index
    df["frame_idx"] = pd.to_numeric(df["frame_idx"], errors="coerce")
    df = df.dropna(subset=["frame_idx"])
    df["frame_idx"] = df["frame_idx"].astype(int)

    # standardize text columns
    df["video"] = df["video"].astype(str).str.strip()
    df["dataset_name"] = df["dataset_name"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip().str.lower()

    # keep only valid labels
    valid_labels = {"fall", "other"}
    df = df[df["label"].isin(valid_labels)].copy()

    # convert pose columns to numeric
    pose_cols = [c for c in df.columns if c not in ["video", "dataset_name", "frame_idx", "label"]]
    for col in pose_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # optional: fill missing pose values with 0
    df[pose_cols] = df[pose_cols].fillna(0.0)

    # sort nicely
    df = df.sort_values(["video", "frame_idx"]).reset_index(drop=True)

    print("\nAfter cleaning:")
    print("Rows:", len(df))
    print("\nLabel counts:")
    print(df["label"].value_counts(dropna=False))

    df.to_csv(out_path, index=False)
    print(f"\nSaved cleaned file: {out_path}")


if __name__ == "__main__":
    clean_le2i_csv(CSV_PATH, OUT_PATH)
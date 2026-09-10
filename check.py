import pandas as pd

CSV_PATH = "datasets/processed/all_poses.csv"
SEQ_LEN = 30


def main():
    print(f"Loading: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, low_memory=False)

    print("\n" + "=" * 60)
    print("FINAL DATASET CHECK")
    print("=" * 60)

    # 1. shape
    print("\n[1] Shape")
    print(df.shape)

    # 2. null values
    print("\n[2] Total null values")
    print(df.isnull().sum().sum())

    # 3. labels
    print("\n[3] Label distribution")
    print(df["label"].value_counts(dropna=False))

    # 4. dataset distribution
    print("\n[4] Dataset distribution")
    print(df["dataset_name"].value_counts(dropna=False))

    # 5. unique labels
    print("\n[5] Unique labels")
    print(sorted(df["label"].dropna().astype(str).unique()))

    # 6. duplicate rows
    print("\n[6] Exact duplicate rows")
    print(df.duplicated().sum())

    # 7. duplicate frame entries
    print("\n[7] Duplicate (dataset_name, video, frame_idx)")
    dup_frames = df.duplicated(subset=["dataset_name", "video", "frame_idx"]).sum()
    print(dup_frames)

    # 8. non-numeric column check
    print("\n[8] Non-numeric columns (expected: video, dataset_name, label)")
    non_numeric = []
    for col in df.columns:
        if df[col].dtype == "object" and col not in ["video", "dataset_name", "label"]:
            non_numeric.append(col)
    print(non_numeric if non_numeric else "None")

    # 9. pose column range check
    print("\n[9] Pose column min/max check")
    pose_cols = [c for c in df.columns if c not in ["video", "dataset_name", "frame_idx", "label"]]
    stats = df[pose_cols].describe().loc[["min", "max"]]
    print(stats)

    # 10. sequence length check
    print("\n[10] Videos shorter than sequence length")
    video_lengths = df.groupby(["dataset_name", "video"]).size()
    short_videos = (video_lengths < SEQ_LEN).sum()
    print(f"Videos shorter than {SEQ_LEN} frames:", short_videos)
    print("Total videos:", len(video_lengths))

    # 11. frame_idx sanity
    print("\n[11] frame_idx stats")
    print(df["frame_idx"].describe())

    # 12. sample rows
    print("\n[12] Random sample rows")
    print(df.sample(5, random_state=42))

    # 13. ready/not ready summary
    print("\n" + "=" * 60)
    print("READY CHECK")
    print("=" * 60)

    issues = []

    if df.isnull().sum().sum() != 0:
        issues.append("Null values present")

    expected_labels = {"eat", "fall", "other", "sit", "sleep", "stand", "walk", "wave"}
    found_labels = set(df["label"].dropna().astype(str).unique())
    if expected_labels != found_labels:
        issues.append(f"Label mismatch. Found: {sorted(found_labels)}")

    if dup_frames > 0:
        issues.append(f"Duplicate frame entries found: {dup_frames}")

    if non_numeric:
        issues.append(f"Unexpected non-numeric columns: {non_numeric}")

    if issues:
        print("Dataset NOT fully ready. Issues found:")
        for issue in issues:
            print("-", issue)
    else:
        print("Dataset looks READY for training ✅")


if __name__ == "__main__":
    main()
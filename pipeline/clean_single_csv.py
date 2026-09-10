import pandas as pd

CSV_PATH = "datasets/processed/pose/hmdb51/hybrid_pose.csv"

FINAL_LABELS = {"fall", "walk", "sit", "stand", "eat", "sleep", "wave", "other"}


def infer_hmdb_label(video):
    v = str(video).strip().lower()

    if "walk" in v:
        return "walk"

    if "sit" in v:
        return "sit"

    if "stand" in v:
        return "stand"

    if "eat" in v or "chew" in v:
        return "eat"

    if "wave" in v:
        return "wave"

    if "sleep" in v or "lie" in v or "lay" in v:
        return "sleep"

    return None   # drop irrelevant actions


def clean_hmdb_csv(path):
    print(f"\nCleaning HMDB: {path}")
    df = pd.read_csv(path, low_memory=False)

    print("\nColumns:")
    print(df.columns.tolist())

    print("\nSample video names:")
    print(df["video"].dropna().astype(str).head(20).tolist())

    # infer label from video name
    df["label"] = df["video"].apply(infer_hmdb_label)

    # drop irrelevant actions
    before = len(df)
    df = df[df["label"].notna()].copy()

    # basic cleanup
    df = df.drop_duplicates()

    df["frame_idx"] = pd.to_numeric(df["frame_idx"], errors="coerce")
    df = df.dropna(subset=["frame_idx"])
    df["frame_idx"] = df["frame_idx"].astype(int)

    print(f"\nRows before filtering: {before}")
    print(f"Rows after filtering : {len(df)}")

    print("\nAfter cleaning:")
    print(df["label"].value_counts(dropna=False))

    out_path = path.replace(".csv", "_clean.csv")
    df.to_csv(out_path, index=False)

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    clean_hmdb_csv(CSV_PATH)
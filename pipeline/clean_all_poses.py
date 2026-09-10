import pandas as pd

INPUT = "datasets/processed/all_poses.csv"
OUTPUT = "datasets/processed/all_poses.csv"  # overwrite


df = pd.read_csv(INPUT, low_memory=False)

print("\nBefore cleaning:")
print("Rows:", len(df))

# remove exact duplicates
df = df.drop_duplicates()

# remove duplicate frames across datasets
if {"dataset_name", "video", "frame_idx"}.issubset(df.columns):
    df = df.drop_duplicates(subset=["dataset_name", "video", "frame_idx"], keep="first")

# ensure numeric pose columns
pose_cols = [c for c in df.columns if c not in ["video", "dataset_name", "frame_idx", "label"]]

for col in pose_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# fill missing (just in case)
df[pose_cols] = df[pose_cols].fillna(0.0)

# clean labels again (safety)
df["label"] = df["label"].astype(str).str.strip().str.lower()

# final shuffle (IMPORTANT)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

print("\nAfter cleaning:")
print("Rows:", len(df))

df.to_csv(OUTPUT, index=False)

print("\nFinal cleaned dataset saved.")
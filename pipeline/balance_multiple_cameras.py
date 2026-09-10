import pandas as pd

INPUT = "datasets/processed/pose/multiple_cameras_fall/hybrid_pose_clean.csv"
OUTPUT = INPUT   # overwrite same file


df = pd.read_csv(INPUT)

print("\nBefore balancing:")
print(df["label"].value_counts())

# separate classes
fall_df = df[df["label"] == "fall"]
other_df = df[df["label"] == "other"]

# downsample "other"
other_sampled = other_df.sample(n=len(fall_df), random_state=42)

# combine
df_balanced = pd.concat([fall_df, other_sampled]).sample(frac=1).reset_index(drop=True)

print("\nAfter balancing:")
print(df_balanced["label"].value_counts())

# overwrite cleaned file
df_balanced.to_csv(OUTPUT, index=False)

print(f"\nUpdated (balanced) file saved: {OUTPUT}")
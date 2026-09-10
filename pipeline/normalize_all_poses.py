import pandas as pd

INPUT = "datasets/processed/all_poses.csv"
OUTPUT = "datasets/processed/all_poses.csv"  # overwrite same file


def main():
    df = pd.read_csv(INPUT, low_memory=False)

    print("\nBefore normalization:")
    print("Shape:", df.shape)

    coord_cols = [
        c for c in df.columns
        if c.endswith("_x") or c.endswith("_y")
    ]

    print("\nCoordinate columns:")
    print(coord_cols)

    print("\nBefore min/max:")
    print(df[coord_cols].describe().loc[["min", "max"]])

    # clip negatives first
    df[coord_cols] = df[coord_cols].clip(lower=0)

    # normalize each coordinate column independently to 0..1
    for col in coord_cols:
        col_min = df[col].min()
        col_max = df[col].max()

        if pd.isna(col_min) or pd.isna(col_max):
            df[col] = 0.0
        elif col_max == col_min:
            df[col] = 0.0
        else:
            df[col] = (df[col] - col_min) / (col_max - col_min)

    print("\nAfter min/max:")
    print(df[coord_cols].describe().loc[["min", "max"]])

    df.to_csv(OUTPUT, index=False)
    print(f"\nNormalized dataset saved: {OUTPUT}")


if __name__ == "__main__":
    main()
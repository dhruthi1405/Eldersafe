import pandas as pd
import os

OUTPUT_DIR = "outputs"


def load_csv(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        print(f"[WARNING] File not found: {path}")
        return None
    return pd.read_csv(path)


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def get_best_row(df, metric):
    if metric not in df.columns:
        print(f"[WARNING] Metric '{metric}' not found.")
        return None
    return df.loc[df[metric].idxmax()]


def print_metrics(row):
    for col, val in row.items():
        print(f"{col:30}: {val}")


def activity_model_results():
    df = load_csv("activity_training_log.csv")
    if df is None:
        return

    print_section("ACTIVITY MODEL RESULTS")

    best = get_best_row(df, "macro_f1")
    final = df.iloc[-1]

    print("\n👉 Best Epoch (by Macro F1):")
    print_metrics(best)

    print("\n👉 Final Epoch:")
    print_metrics(final)


def binary_fall_results():
    df = load_csv("binary_fall_training_log.csv")
    if df is None:
        return

    print_section("BINARY FALL MODEL RESULTS")

    best = get_best_row(df, "fall_f1")
    final = df.iloc[-1]

    print("\n👉 Best Epoch (by Fall F1):")
    print_metrics(best)

    print("\n👉 Final Epoch:")
    print_metrics(final)


def main_training_results():
    df = load_csv("training_log.csv")
    if df is None:
        return

    print_section("MAIN TRAINING RESULTS")

    best = get_best_row(df, "fall_f1")
    final = df.iloc[-1]

    print("\n👉 Best Epoch (by Fall F1):")
    print_metrics(best)

    print("\n👉 Final Epoch:")
    print_metrics(final)


def summary():
    print_section("FINAL SUMMARY (IMPORTANT METRICS)")

    act = load_csv("activity_training_log.csv")
    fall = load_csv("binary_fall_training_log.csv")

    if act is not None:
        best_act = get_best_row(act, "macro_f1")
        print("\n📊 Activity Model:")
        print(f"Accuracy      : {best_act.get('val_accuracy', 'N/A')}")
        print(f"Macro F1      : {best_act.get('macro_f1', 'N/A')}")

    if fall is not None:
        best_fall = get_best_row(fall, "fall_f1")
        print("\n🚨 Fall Model:")
        print(f"Accuracy      : {best_fall.get('val_accuracy', 'N/A')}")
        print(f"Precision     : {best_fall.get('fall_precision', 'N/A')}")
        print(f"Recall        : {best_fall.get('fall_recall', 'N/A')}")
        print(f"F1 Score      : {best_fall.get('fall_f1', 'N/A')}")


if __name__ == "__main__":
    activity_model_results()
    binary_fall_results()
    main_training_results()
    summary()
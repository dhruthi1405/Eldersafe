import os
import numpy as np
import pandas as pd
import torch
import shap
import matplotlib.pyplot as plt

from models.tcn_lstm_model import build_model
from pipeline.pose_extractor import YOLO_KP_NAMES
from configs.config import MODEL_CONFIG


def pose_feature_columns():
    cols = []
    for name in YOLO_KP_NAMES:
        cols += [f"{name}_x", f"{name}_y", f"{name}_conf"]
    return cols


def build_sequences(df: pd.DataFrame, seq_len: int = 30):
    feature_cols = pose_feature_columns()
    sequences = []
    labels = []

    if "video" not in df.columns:
        raise ValueError("CSV must contain 'video' column")

    for video_name, group in df.groupby("video"):
        if "frame_idx" in group.columns:
            group = group.sort_values("frame_idx")

        x = group[feature_cols].fillna(0.0).values

        if len(x) < seq_len:
            continue

        for i in range(len(x) - seq_len + 1):
            sequences.append(x[i:i + seq_len])

            if "label" in group.columns:
                labels.append(group["label"].iloc[0])
            else:
                labels.append("unknown")

    return np.array(sequences, dtype=np.float32), labels, feature_cols


def load_model(model_path: str):
    model = build_model()

    state = torch.load(model_path, map_location="cpu")
    if isinstance(state, dict) and "model_state_dict" in state:
        model.load_state_dict(state["model_state_dict"])
    else:
        model.load_state_dict(state)

    model.eval()
    return model


def explain_model(root_dir: str, num_samples: int = 20):
    csv_path = os.path.join(root_dir, "datasets", "processed", "all_poses.csv")
    model_path = os.path.join(root_dir, "models", "best_model.pt")
    out_dir = os.path.join(root_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing dataset: {csv_path}")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Missing model: {model_path}")

    df = pd.read_csv(csv_path)
    seq_len = MODEL_CONFIG.get("sequence_length", 30)

    X, y, feature_cols = build_sequences(df, seq_len=seq_len)

    if len(X) == 0:
        raise ValueError("No valid sequences found for explanation")

    X = X[:num_samples]
    model = load_model(model_path)

    background = torch.tensor(X[: min(5, len(X))], dtype=torch.float32)
    samples = torch.tensor(X, dtype=torch.float32)

    explainer = shap.DeepExplainer(model, background)
    shap_values = explainer.shap_values(samples)

    # Multi-class handling
    if isinstance(shap_values, list):
        sv = np.mean(np.abs(np.stack(shap_values, axis=0)), axis=0)
    else:
        sv = np.abs(shap_values)

    # sv shape expected: (N, T, F)
    mean_importance = sv.mean(axis=(0, 1))

    importance_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": mean_importance
    }).sort_values("importance", ascending=False)

    out_csv = os.path.join(out_dir, "feature_importance.csv")
    importance_df.to_csv(out_csv, index=False)

    plt.figure(figsize=(12, 6))
    top_n = min(20, len(importance_df))
    top_df = importance_df.head(top_n).iloc[::-1]
    plt.barh(top_df["feature"], top_df["importance"])
    plt.xlabel("Mean |SHAP value|")
    plt.ylabel("Feature")
    plt.title("Top Pose Features for Prediction")
    plt.tight_layout()

    out_png = os.path.join(out_dir, "feature_importance.png")
    plt.savefig(out_png, dpi=200)
    plt.close()

    print(f"Saved explainability CSV: {out_csv}")
    print(f"Saved explainability plot: {out_png}")
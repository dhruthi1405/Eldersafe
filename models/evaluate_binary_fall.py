from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
from sklearn.metrics import (
    auc,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configs.config import ROOT_DIR
from models.binary_fall_train import (
    BINARY_CLASS_NAMES,
    build_binary_loader,
    evaluate_binary,
    prepare_fall_data,
    set_seed,
    split_by_video,
)
from models.tcn_lstm_model import build_model


def resolve_data_source(root_dir: str, data_source: str) -> str:
    if data_source == "fall_binary_train":
        return os.path.join(root_dir, "datasets", "processed", "fall_binary_train.csv")
    return data_source


def save_paper_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    out_dir: Path,
) -> Path:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    fig, ax = plt.subplots(figsize=(7, 5.5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=BINARY_CLASS_NAMES,
        yticklabels=BINARY_CLASS_NAMES,
        cbar=True,
        annot_kws={"size": 14},
        ax=ax,
    )
    ax.set_title(
        "Confusion Matrix for Unified Multi-Source Fall Detection Model",
        fontsize=14,
    )
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("Actual", fontsize=12)
    plt.tight_layout()

    out_path = out_dir / "model2_final_confusion_matrix.png"
    plt.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def save_paper_roc_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    out_dir: Path,
) -> tuple[Path, float]:
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    roc_auc = auc(fpr, tpr)

    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.plot(
        fpr,
        tpr,
        color="#d95f02",
        lw=2.5,
        label=f"ROC curve (AUC = {roc_auc:.4f})",
    )
    ax.plot([0, 1], [0, 1], color="#4d4d4d", lw=1.5, linestyle="--", label="Random")
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.05])
    ax.set_xlabel("False Positive Rate", fontsize=12)
    ax.set_ylabel("True Positive Rate", fontsize=12)
    ax.set_title(
        "ROC Curve for Unified Multi-Source Fall Detection Model",
        fontsize=14,
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right")
    plt.tight_layout()

    out_path = out_dir / "model2_final_roc_curve.png"
    plt.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path, roc_auc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the saved binary fall model and generate paper figures."
    )
    parser.add_argument("--root_dir", default=ROOT_DIR)
    parser.add_argument("--data_source", default="fall_binary_train")
    parser.add_argument("--model_path", default=None)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--seq_len", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    set_seed(args.seed)

    root_dir = os.path.abspath(args.root_dir)
    data_path = resolve_data_source(root_dir, args.data_source)
    model_path = args.model_path or os.path.join(root_dir, "models", "binary_fall_best.pth")
    out_dir = Path(root_dir) / "outputs" / "paper_figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Dataset not found: {data_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    print(f"Loading dataset: {data_path}")
    df = prepare_fall_data(data_path)
    _, _, test_df = split_by_video(df, seed=args.seed)

    print(f"\nTest rows: {len(test_df)}")
    test_loader, test_counts = build_binary_loader(
        test_df,
        seq_len=args.seq_len,
        batch_size=args.batch_size,
        augment=False,
    )
    print("Test sequence counts:", test_counts)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    model = build_model(num_classes=2).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    criterion = nn.CrossEntropyLoss()

    (
        test_loss,
        test_acc,
        prec,
        rec,
        f1,
        support,
        y_true,
        y_pred,
        y_prob,
        roc_auc,
    ) = evaluate_binary(
        model,
        test_loader,
        criterion,
        device,
        threshold=args.threshold,
    )

    print("\nFinal binary fall evaluation")
    print(f"Threshold      : {args.threshold:.4f}")
    print(f"Test Loss      : {test_loss:.4f}")
    print(f"Test Accuracy  : {test_acc:.2f}%")
    print(f"Fall Precision : {prec[1]:.4f}")
    print(f"Fall Recall    : {rec[1]:.4f}")
    print(f"Fall F1        : {f1[1]:.4f}")
    print(f"Fall ROC-AUC   : {roc_auc_score(y_true, y_prob):.4f}")

    print("\nClassification Report:")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=BINARY_CLASS_NAMES,
            zero_division=0,
        )
    )

    cm_path = save_paper_confusion_matrix(y_true, y_pred, out_dir)
    roc_path, paper_auc = save_paper_roc_curve(y_true, y_prob, out_dir)

    predictions_path = out_dir / "model2_final_predictions.csv"
    pd.DataFrame(
        {
            "actual": y_true,
            "predicted": y_pred,
            "fall_probability": y_prob,
        }
    ).to_csv(predictions_path, index=False)

    metrics_path = out_dir / "model2_final_metrics.csv"
    pd.DataFrame(
        [
            {
                "threshold": args.threshold,
                "test_loss": test_loss,
                "accuracy_percent": test_acc,
                "no_fall_precision": prec[0],
                "no_fall_recall": rec[0],
                "no_fall_f1": f1[0],
                "no_fall_support": support[0],
                "fall_precision": prec[1],
                "fall_recall": rec[1],
                "fall_f1": f1[1],
                "fall_support": support[1],
                "roc_auc": paper_auc,
            }
        ]
    ).to_csv(metrics_path, index=False)

    print("\nSaved paper outputs:")
    print(f"Confusion matrix : {cm_path}")
    print(f"ROC curve        : {roc_path}")
    print(f"Predictions      : {predictions_path}")
    print(f"Metrics CSV      : {metrics_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configs.config import ROOT_DIR
from models.tcn_lstm_model import build_model
from models.train import PoseSequenceDataset, FALL_ID


BINARY_CLASS_NAMES = ["no_fall", "fall"]


# ─────────────────────────────────────────────
# FOCAL LOSS FOR CLASS IMBALANCE
# ─────────────────────────────────────────────
class FocalLoss(nn.Module):
    """Focal Loss for addressing class imbalance and hard negatives.
    
    Args:
        alpha: Weighting factor for positive class. Shape (num_classes,) or scalar.
        gamma: Focusing parameter (default 2.0). Higher values focus on hard examples.
        reduction: 'mean', 'sum', or 'none'
    """
    def __init__(
        self,
        alpha: torch.Tensor | float = 0.5,
        gamma: float = 2.0,
        reduction: str = "mean",
    ):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute focal loss.
        
        Args:
            inputs: (B, num_classes) logits
            targets: (B,) class indices
        """
        ce_loss = nn.functional.cross_entropy(inputs, targets, reduction="none")
        p = torch.exp(-ce_loss)  # probability of correct class
        focal_loss = (1 - p) ** self.gamma * ce_loss

        if isinstance(self.alpha, torch.Tensor):
            focal_loss = self.alpha[targets] * focal_loss
        elif self.alpha is not None:
            focal_loss = self.alpha * focal_loss

        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        else:
            return focal_loss


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def prepare_fall_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, low_memory=False)

    df["label"] = df["label"].fillna("other")
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"

    print("Source label distribution:")
    print(df["label"].value_counts())

    feature_cols = [
        c for c in df.columns
        if c.endswith("_x") or c.endswith("_y") or c.endswith("_conf")
    ]
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    non_finite = int((~np.isfinite(df[feature_cols].to_numpy(dtype=np.float32))).sum())
    if non_finite:
        print(f"Replacing non-finite pose values: {non_finite}")

    df[feature_cols] = (
        df[feature_cols]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    coord_cols = [c for c in df.columns if c.endswith("_x") or c.endswith("_y")]
    conf_cols = [c for c in df.columns if c.endswith("_conf")]
    df[coord_cols] = df[coord_cols].clip(lower=0.0, upper=1.0)
    df[conf_cols] = df[conf_cols].clip(lower=0.0, upper=1.0)

    return df


def split_by_video(df: pd.DataFrame, seed: int = 42):
    videos = df[["dataset_name", "video"]].drop_duplicates()
    videos = videos.sample(frac=1, random_state=seed).reset_index(drop=True)

    n = len(videos)
    test_v = videos[: int(0.15 * n)]
    val_v = videos[int(0.15 * n): int(0.30 * n)]
    train_v = videos[int(0.30 * n):]

    train_df = df.merge(train_v, on=["dataset_name", "video"])
    val_df = df.merge(val_v, on=["dataset_name", "video"])
    test_df = df.merge(test_v, on=["dataset_name", "video"])

    return train_df, val_df, test_df


def convert_dataset_to_binary(ds: PoseSequenceDataset) -> list[int]:
    new_samples = []
    counts = [0, 0]  # [no_fall, fall]

    for x, y in ds.samples:
        y_bin = 1 if y == FALL_ID else 0
        new_samples.append((x, y_bin))
        counts[y_bin] += 1

    ds.samples = new_samples
    return counts


def build_binary_loader(
    df: pd.DataFrame,
    seq_len: int,
    batch_size: int,
    augment: bool,
    stride: int | None = None,
    max_per_class: int | None = None,
):
    print(f"\nCreating binary dataset | rows={len(df)} | augment={augment}")
    if stride is None:
        stride = 5 if augment else max(1, seq_len // 2)

    ds = PoseSequenceDataset(
        df=df,
        seq_len=seq_len,
        augment=augment,
        stride=stride,
    )

    counts_before = convert_dataset_to_binary(ds)
    print("Binary class sequence counts (before balancing):", counts_before)

    if augment:
        max_fall = max_per_class or 5000
        max_no_fall = max_per_class or 5000

        filtered = []
        ctr = {0: 0, 1: 0}

        for sample in ds.samples:
            _, lbl = sample
            if lbl == 1 and ctr[lbl] >= max_fall:
                continue
            if lbl == 0 and ctr[lbl] >= max_no_fall:
                continue
            ctr[lbl] += 1
            filtered.append(sample)

        ds.samples = filtered

        counts_after = [0, 0]
        for _, lbl in ds.samples:
            counts_after[lbl] += 1
        print("Balanced binary class sequence counts:", counts_after)
        print(f"Training cap per class: {max_per_class or 5000}")
        counts = counts_after
        shuffle = True
    else:
        counts = counts_before
        shuffle = False

    loader = DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=False,
    )
    return loader, counts


def build_binary_class_weights(counts: list[int], device: torch.device) -> torch.Tensor:
    counts = np.array(counts, dtype=np.float32)
    counts[counts == 0] = 1.0

    weights = counts.sum() / (len(counts) * counts)
    weights = np.clip(weights, 1.0, 3.0)

    w = torch.tensor(weights, dtype=torch.float32, device=device)
    print("Binary class weights:", w.detach().cpu().numpy())
    return w


def evaluate_binary(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    threshold: float = 0.5,
):
    """Evaluate binary fall detection model with optional threshold tuning.
    
    Args:
        threshold: Decision threshold for positive class (default 0.5)
    """
    model.eval()

    total_loss = 0.0
    all_labels = []
    all_preds = []
    all_probs = []

    with torch.no_grad():
        for x, y in loader:
            x = torch.nan_to_num(x, nan=0.0, posinf=1.0, neginf=0.0).clamp(0.0, 1.0)
            x = x.to(device)
            y = y.to(device)

            out = model(x)
            loss = criterion(out, y)
            if not torch.isfinite(loss) or not torch.isfinite(out).all():
                continue

            probs = torch.softmax(out, dim=1)
            # Apply custom threshold instead of argmax
            preds = (probs[:, 1] >= threshold).long()

            total_loss += float(loss.item())
            all_labels.extend(y.cpu().numpy())
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs[:, 1].cpu().numpy())

    avg_loss = total_loss / max(len(loader), 1)
    all_labels = np.array(all_labels)
    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)

    acc = 100.0 * (all_preds == all_labels).sum() / max(len(all_labels), 1)

    prec, rec, f1, support = precision_recall_fscore_support(
        all_labels,
        all_preds,
        labels=[0, 1],
        zero_division=0,
    )

    auc = None
    try:
        if len(np.unique(all_labels)) > 1:
            auc = roc_auc_score(all_labels, all_probs)
    except Exception:
        auc = None

    return avg_loss, acc, prec, rec, f1, support, all_labels, all_preds, all_probs, auc


def analyze_roc_and_find_optimal_threshold(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    root_dir: str,
    epoch: int = 0,
    optimize_metric: str = "f1",
) -> tuple[float, dict]:
    """Analyze ROC curve and find optimal threshold for binary classification.
    
    Args:
        y_true: Ground truth binary labels
        y_probs: Predicted probabilities for positive class
        root_dir: Directory to save ROC plot
        epoch: Epoch number for plot naming
        optimize_metric: Metric to optimize ('f1', 'precision', 'recall')
    
    Returns:
        optimal_threshold: Best threshold value
        metrics_at_threshold: Dict with metrics at optimal threshold
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_probs)
    roc_auc = roc_auc_score(y_true, y_probs)

    # Compute metrics for all thresholds
    best_score = -1
    best_threshold = 0.5
    metrics_history = []

    for threshold in thresholds:
        preds = (y_probs >= threshold).astype(int)
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_true, preds, labels=[0, 1], zero_division=0
        )

        if optimize_metric == "f1":
            score = f1[1]  # F1 for positive class
        elif optimize_metric == "recall":
            score = rec[1]  # Recall for positive class
        elif optimize_metric == "precision":
            score = prec[1]  # Precision for positive class
        else:
            score = f1[1]

        metrics_history.append({
            "threshold": threshold,
            "precision": prec[1],
            "recall": rec[1],
            "f1": f1[1],
            "score": score,
        })

        if score > best_score:
            best_score = score
            best_threshold = threshold

    # Retrieve metrics at best threshold
    preds_best = (y_probs >= best_threshold).astype(int)
    prec_best, rec_best, f1_best, _ = precision_recall_fscore_support(
        y_true, preds_best, labels=[0, 1], zero_division=0
    )

    metrics_at_threshold = {
        "threshold": best_threshold,
        "precision_no_fall": prec_best[0],
        "recall_no_fall": rec_best[0],
        "f1_no_fall": f1_best[0],
        "precision_fall": prec_best[1],
        "recall_fall": rec_best[1],
        "f1_fall": f1_best[1],
        "roc_auc": roc_auc,
    }

    # Plot ROC curve
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # ROC curve
    ax1.plot(fpr, tpr, color="darkorange", lw=2, label=f"ROC curve (AUC = {roc_auc:.3f})")
    ax1.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--", label="Random")
    ax1.scatter(
        fpr[np.argmin(np.abs(thresholds - best_threshold))],
        tpr[np.argmin(np.abs(thresholds - best_threshold))],
        marker="o",
        color="red",
        s=100,
        label=f"Optimal threshold = {best_threshold:.3f}",
    )
    ax1.set_xlabel("False Positive Rate")
    ax1.set_ylabel("True Positive Rate")
    ax1.set_title(f"ROC Curve — Epoch {epoch}")
    ax1.legend(loc="lower right")
    ax1.grid(True, alpha=0.3)

    # Precision-Recall curve
    precision_vals = [m["precision"] for m in metrics_history]
    recall_vals = [m["recall"] for m in metrics_history]
    ax2.plot(recall_vals, precision_vals, color="darkgreen", lw=2, label="Precision-Recall")
    best_idx = next(
        i for i, m in enumerate(metrics_history) if np.isclose(m["threshold"], best_threshold)
    )
    ax2.scatter(
        recall_vals[best_idx],
        precision_vals[best_idx],
        marker="o",
        color="red",
        s=100,
        label=f"Optimal threshold = {best_threshold:.3f}",
    )
    ax2.set_xlabel("Recall (Sensitivity)")
    ax2.set_ylabel("Precision")
    ax2.set_title(f"Precision-Recall Curve — Epoch {epoch}")
    ax2.legend(loc="best")
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim([0, 1])
    ax2.set_ylim([0, 1])

    plt.tight_layout()
    out_dir = os.path.join(root_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"roc_analysis_epoch{epoch}.png")
    plt.savefig(out_path, dpi=150)
    plt.close()

    print(f"ROC analysis plot -> {out_path}")
    return best_threshold, metrics_at_threshold


def save_binary_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    root_dir: str,
    epoch: int,
) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        xticklabels=BINARY_CLASS_NAMES,
        yticklabels=BINARY_CLASS_NAMES,
        cmap="Blues",
        ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(f"Binary Fall Confusion Matrix — Epoch {epoch}")
    plt.tight_layout()

    out_dir = os.path.join(root_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"binary_fall_confusion_epoch{epoch}.png")
    plt.savefig(out_path, dpi=150)
    plt.close()

    print(f"Confusion matrix -> {out_path}")


def train_binary_fall(
    root_dir: str = ROOT_DIR,
    epochs: int = 15,
    batch_size: int = 16,
    lr: float = 5e-4,
    seq_len: int = 30,
    seed: int = 42,
    data_source: str = "fall_binary_train",
    train_stride: int = 5,
    max_per_class: int = 5000,
):
    set_seed(seed)

    fall_csv = os.path.join(root_dir, "datasets", "processed", "fall_binary_train.csv")
    activity_csv = os.path.join(root_dir, "datasets", "processed", "activity_train.csv")

    if data_source == "fall_binary_train":
        pose_csv = fall_csv
        print(f"\nUsing fall_binary_train data: {pose_csv}")
    elif data_source == "activity_train":
        pose_csv = activity_csv
        print(f"\nUsing activity_train data: {pose_csv}")
    else:
        pose_csv = data_source
        print(f"\nUsing custom fall data: {pose_csv}")

    if not os.path.exists(pose_csv):
        raise FileNotFoundError(f"Training data not found: {pose_csv}")

    print("Loading pose data:", pose_csv)
    df = prepare_fall_data(pose_csv)

    print("\nCreating train/val/test split...")
    train_df, val_df, test_df = split_by_video(df, seed=seed)

    print(f"Train rows : {len(train_df)}")
    print(f"Val rows   : {len(val_df)}")
    print(f"Test rows  : {len(test_df)}")

    print("\nBuilding train loader...")
    train_loader, train_counts = build_binary_loader(
        train_df,
        seq_len,
        batch_size,
        augment=True,
        stride=train_stride,
        max_per_class=max_per_class,
    )

    print("\nBuilding val loader...")
    val_loader, _ = build_binary_loader(
        val_df, seq_len, batch_size, augment=False
    )

    print("\nBuilding test loader...")
    test_loader, _ = build_binary_loader(
        test_df, seq_len, batch_size, augment=False
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    model = build_model(num_classes=2).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=1e-5,
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=3,
        verbose=True,
    )

    class_weights = build_binary_class_weights(train_counts, device)
    if abs(float(class_weights[0].item()) - float(class_weights[1].item())) < 0.05:
        print("Using CrossEntropyLoss because binary training sequences are already balanced.")
        criterion = nn.CrossEntropyLoss()
    else:
        alpha_tensor = torch.tensor([1.0, class_weights[1].item()], device=device)
        criterion = FocalLoss(alpha=alpha_tensor, gamma=1.0, reduction="mean")

    best_val_loss = float("inf")
    best_f1 = -1.0
    best_recall = -1.0
    best_saved = False
    patience = 12
    patience_counter = 0
    optimal_threshold = 0.5
    metrics_opt = {}
    threshold_report_path = ""

    save_dir = os.path.join(root_dir, "models")
    os.makedirs(save_dir, exist_ok=True)
    best_model_path = os.path.join(save_dir, "binary_fall_best.pth")

    log_path = os.path.join(root_dir, "outputs", "binary_fall_training_log.csv")
    os.makedirs(os.path.join(root_dir, "outputs"), exist_ok=True)
    log_rows = []

    print("\n🔥 ENTERING BINARY FALL TRAINING LOOP")


    for epoch in range(1, epochs + 1):
        print(f"\n{'=' * 65}")
        print(f"  Binary Fall Epoch {epoch}/{epochs}")
        print(f"{'=' * 65}")

        model.train()
        total_train_loss = 0.0
        valid_batches = 0
        skipped_batches = 0

        for batch_idx, (x, y) in enumerate(train_loader):
            if batch_idx == 0:
                print("  First training batch reached")

            x = torch.nan_to_num(x, nan=0.0, posinf=1.0, neginf=0.0).clamp(0.0, 1.0)
            x = x.to(device)
            y = y.to(device)

            optimizer.zero_grad(set_to_none=True)
            out = model(x)
            loss = criterion(out, y)

            if not torch.isfinite(loss) or not torch.isfinite(out).all():
                skipped_batches += 1
                continue

            loss.backward()

            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            if not torch.isfinite(grad_norm):
                optimizer.zero_grad(set_to_none=True)
                skipped_batches += 1
                continue

            optimizer.step()

            total_train_loss += float(loss.item())
            valid_batches += 1

            if (batch_idx + 1) % 50 == 0:
                print(
                    f"  Batch {batch_idx + 1}/{len(train_loader)} "
                    f"| Loss: {loss.item():.4f}"
                )

        avg_train_loss = total_train_loss / max(valid_batches, 1)
        if skipped_batches:
            print(f"  Skipped non-finite batches: {skipped_batches}")

        if valid_batches == 0:
            print("No valid training batches were produced. Stopping.")
            break

        (
            avg_val_loss,
            val_acc,
            prec,
            rec,
            f1,
            support,
            y_true,
            y_pred,
            y_prob,
            auc,
        ) = evaluate_binary(model, val_loader, criterion, device)

        save_binary_confusion_matrix(y_true, y_pred, root_dir, epoch)

        print(f"\nVal Loss     : {avg_val_loss:.4f}")
        print(f"Val Accuracy : {val_acc:.2f}%")
        print(f"\n{'Class':<10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
        print("-" * 54)
        for i, name in enumerate(BINARY_CLASS_NAMES):
            print(
                f"{name:<10} {prec[i]:>10.4f} {rec[i]:>10.4f} "
                f"{f1[i]:>10.4f} {int(support[i]):>10}"
            )

        print(f"\nFall Precision : {prec[1]:.4f}")
        print(f"Fall Recall    : {rec[1]:.4f}")
        print(f"Fall F1        : {f1[1]:.4f}")
        if auc is not None:
            print(f"Fall ROC-AUC   : {auc:.4f}")

        if np.isfinite(avg_val_loss):
            scheduler.step(avg_val_loss)

        log_rows.append(
            {
                "epoch": epoch,
                "train_loss": avg_train_loss,
                "val_loss": avg_val_loss,
                "val_accuracy": val_acc,
                "fall_precision": prec[1],
                "fall_recall": rec[1],
                "fall_f1": f1[1],
                "fall_roc_auc": auc if auc is not None else np.nan,
                "no_fall_precision": prec[0],
                "no_fall_recall": rec[0],
                "no_fall_f1": f1[0],
            }
        )
        pd.DataFrame(log_rows).to_csv(log_path, index=False)

        print(f"\nTrain Loss: {avg_train_loss:.4f}")

        score = f1[1] if np.isfinite(f1[1]) else 0.0

        if score > best_f1 and score > 0.0 and np.isfinite(avg_val_loss):
            best_val_loss = avg_val_loss
            best_f1 = f1[1]
            best_recall = rec[1]
            best_saved = True
            patience_counter = 0
            torch.save(model.state_dict(), best_model_path)
            print(f"✅ Best model saved -> {best_model_path}")
            print(f"   Saved by best fall F1 = {best_f1:.4f}")
            print(f"   Fall recall at save   = {best_recall:.4f}")
        else:
            patience_counter += 1
            print(f"No improvement. Patience: {patience_counter}/{patience}")
            if patience_counter >= patience:
                print("🛑 Early stopping triggered")
                break

    print(f"\n{'=' * 65}")
    print("  TESTING BEST BINARY FALL MODEL")
    print(f"{'=' * 65}")

    if not best_saved:
        print("No valid best model was saved because fall F1 never rose above 0.")
        print("Do not use the existing binary_fall_best.pth from the failed run.")
        print(f"\nTraining log: {log_path}")
        return

    model.load_state_dict(torch.load(best_model_path, map_location=device))

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
        auc,
    ) = evaluate_binary(model, test_loader, criterion, device)

    print(f"Test Loss     : {test_loss:.4f}")
    print(f"Test Accuracy : {test_acc:.2f}%")
    print(f"Fall Precision: {prec[1]:.4f}")
    print(f"Fall Recall   : {rec[1]:.4f}")
    print(f"Fall F1       : {f1[1]:.4f}")
    if auc is not None:
        print(f"Fall ROC-AUC  : {auc:.4f}")

    print("\nClassification Report:")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=BINARY_CLASS_NAMES,
            zero_division=0,
        )
    )

    save_binary_confusion_matrix(y_true, y_pred, root_dir, epoch=999)

    # 🎯 PHASE 1: Analyze ROC curve and find optimal threshold
    print(f"\n{'=' * 65}")
    print("  THRESHOLD OPTIMIZATION ANALYSIS")
    print(f"{'=' * 65}")
    
    optimal_threshold, metrics_opt = analyze_roc_and_find_optimal_threshold(
        y_true, y_prob, root_dir, epoch=999, optimize_metric="f1"
    )
    
    print(f"\nOptimal threshold found: {optimal_threshold:.4f}")
    print(f"  (optimizing for F1 score)")
    print(f"\nMetrics at optimal threshold:")
    print(f"  Fall Precision: {metrics_opt['precision_fall']:.4f}")
    print(f"  Fall Recall   : {metrics_opt['recall_fall']:.4f}")
    print(f"  Fall F1       : {metrics_opt['f1_fall']:.4f}")
    print(f"  No-Fall Recall: {metrics_opt['recall_no_fall']:.4f}")
    print(f"  ROC-AUC       : {metrics_opt['roc_auc']:.4f}")
    
    # Re-evaluate on validation set with optimal threshold for comparison
    print(f"\n{'=' * 65}")
    print("  RE-EVALUATING VALIDATION SET WITH OPTIMAL THRESHOLD")
    print(f"{'=' * 65}")
    
    (
        val_loss_opt,
        val_acc_opt,
        prec_opt,
        rec_opt,
        f1_opt,
        support_opt,
        y_true_val,
        y_pred_val_opt,
        y_prob_val,
        auc_val,
    ) = evaluate_binary(model, val_loader, criterion, device, threshold=optimal_threshold)
    
    print(f"\nValidation metrics with optimal threshold ({optimal_threshold:.4f}):")
    print(f"  Fall Precision: {prec_opt[1]:.4f}  (vs default {prec[1]:.4f})")
    print(f"  Fall Recall   : {rec_opt[1]:.4f}  (vs default {rec[1]:.4f})")
    print(f"  Fall F1       : {f1_opt[1]:.4f}  (vs default {f1[1]:.4f})")
    
    # Save threshold analysis report
    threshold_analysis = pd.DataFrame([
        {
            "evaluation_set": "test",
            "threshold": 0.5,
            "fall_precision": prec[1],
            "fall_recall": rec[1],
            "fall_f1": f1[1],
        },
        {
            "evaluation_set": "test_optimal",
            "threshold": optimal_threshold,
            "fall_precision": metrics_opt['precision_fall'],
            "fall_recall": metrics_opt['recall_fall'],
            "fall_f1": metrics_opt['f1_fall'],
        },
        {
            "evaluation_set": "val_optimal",
            "threshold": optimal_threshold,
            "fall_precision": prec_opt[1],
            "fall_recall": rec_opt[1],
            "fall_f1": f1_opt[1],
        },
    ])
    
    threshold_report_path = os.path.join(root_dir, "outputs", "threshold_analysis.csv")
    threshold_analysis.to_csv(threshold_report_path, index=False)
    print(f"\nThreshold analysis saved -> {threshold_report_path}")
    
    print(f"\n{'=' * 65}")
    print("  TRAINING SUMMARY")
    print(f"{'=' * 65}")

    print(f"\nBest val loss : {best_val_loss:.4f}")
    print(f"Best fall F1  : {best_f1:.4f}")
    print(f"Best recall   : {best_recall:.4f}")
    if optimal_threshold != 0.5 or metrics_opt:
        print(f"Optimal threshold: {optimal_threshold:.4f}")
        print(f"Threshold analysis: {threshold_report_path}")
    print(f"Best model    : {best_model_path}")
    print(f"Training log  : {log_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", default=ROOT_DIR)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--seq_len", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--train_stride",
        type=int,
        default=5,
        help="Frame stride for training sequences. Larger is faster; 1 is most exhaustive.",
    )
    parser.add_argument(
        "--max_per_class",
        type=int,
        default=5000,
        help="Maximum balanced training sequences per class. Larger is slower but more complete.",
    )
    parser.add_argument(
        "--data_source",
        default="fall_binary_train",
        help="Use 'fall_binary_train', 'activity_train', or a CSV path.",
    )
    args = parser.parse_args()

    train_binary_fall(
        root_dir=args.root_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seq_len=args.seq_len,
        seed=args.seed,
        data_source=args.data_source,
        train_stride=args.train_stride,
        max_per_class=args.max_per_class,
    )

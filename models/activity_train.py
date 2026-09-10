from __future__ import annotations

import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    f1_score,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configs.config import ROOT_DIR
from models.activity_model import build_activity_model
from pipeline.pose_extractor import YOLO_KP_NAMES


ACTIVITY_CLASSES = ["walk", "sit", "stand", "eat", "sleep", "wave", "other"]
ACTIVITY_LABEL_TO_ID = {name: i for i, name in enumerate(ACTIVITY_CLASSES)}
ID_TO_ACTIVITY = {i: name for name, i in ACTIVITY_LABEL_TO_ID.items()}


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _pose_cols() -> List[str]:
    cols = []
    for n in YOLO_KP_NAMES:
        cols += [f"{n}_x", f"{n}_y", f"{n}_conf"]
    return cols


def prepare_activity_data(root_dir: str, data_source: str = "activity_train") -> pd.DataFrame:
    # FIX: Use activity_train.csv (clean, already normalized activity data)
    # instead of corrupted all_poses.csv
    activity_csv = os.path.join(root_dir, "datasets", "processed", "activity_train.csv")
    all_csv = os.path.join(root_dir, "datasets", "processed", "all_poses.csv")
    if data_source not in {"activity_train", "all_poses"}:
        activity_csv = data_source
    
    # Try to use clean activity_train.csv first
    if data_source != "all_poses" and os.path.exists(activity_csv):
        print(f"\n✓ Using clean activity data: {activity_csv}")
        df = pd.read_csv(activity_csv, low_memory=False)
    else:
        print(f"\n⚠ activity_train.csv not found, falling back to all_poses.csv")
        print(f"  Run: python pipeline/fix_data_pipeline.py")
        df = pd.read_csv(all_csv, low_memory=False)
        
        # Remove fall for activity model
        df = df[df["label"] != "fall"].copy()

    # Ensure labels are clean
    df["label"] = df["label"].fillna("other").astype(str).str.strip().str.lower()
    df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"
    df["label"] = df["label"].apply(lambda x: x if x in ACTIVITY_CLASSES else "other")

    print("\nFinal activity label distribution:")
    print(df["label"].value_counts())
    
    # Show coordinate ranges to verify normalization
    if "nose_x" in df.columns:
        print(f"\n✓ nose_x range: {df['nose_x'].min():.6f} - {df['nose_x'].max():.6f} (should be ~0-1)")

    return df


class ActivitySequenceDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        seq_len: int = 30,
        augment: bool = False,
        stride: int = 5,
        min_activity_frames: int = 8,
        min_other_frames: int = 20,
    ):
        self.seq_len = seq_len
        self.augment = augment
        self.stride = stride
        self.min_activity_frames = min_activity_frames
        self.min_other_frames = min_other_frames
        self.feat_cols = _pose_cols()
        self.samples = []

        grouped = df.groupby(["dataset_name", "video"])
        total_groups = len(grouped)

        print(f"Building activity sequences from {total_groups} videos...")

        for idx, ((dataset_name, video), g) in enumerate(grouped, start=1):
            if idx % 100 == 0 or idx == total_groups:
                print(f"  Processed {idx}/{total_groups} videos")

            g = g.sort_values("frame_idx").reset_index(drop=True)
            feats = g[self.feat_cols].fillna(0).values.astype(np.float32)
            labels = g["label"].values
            n = len(feats)

            if n < seq_len:
                continue

            for start in range(0, n - seq_len + 1, stride):
                window = feats[start:start + seq_len]
                window_labels = labels[start:start + seq_len]

                label_name = self._get_window_label(window_labels)
                if label_name is None:
                    continue

                label_id = ACTIVITY_LABEL_TO_ID[label_name]
                self.samples.append((window, label_id))

        print(f"Finished building activity dataset. Total sequences: {len(self.samples)}")

    def _get_window_label(self, window_labels: np.ndarray) -> str | None:
        window_labels = np.array(window_labels)

        # Separate real activities from "other"
        real_labels = [x for x in window_labels if x != "other"]

        if len(real_labels) > 0:
            vc = pd.Series(real_labels).value_counts()
            top_real = vc.index[0]
            top_real_count = int(vc.iloc[0])

            if top_real_count >= self.min_activity_frames:
                return top_real

        other_count = int(np.sum(window_labels == "other"))
        if other_count >= self.min_other_frames:
            return "other"

        # ambiguous window
        return None

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x, y = self.samples[idx]
        x = x.copy()
        if self.augment:
            x = self._augment(x)
        x = np.nan_to_num(x, nan=0.0, posinf=1.0, neginf=0.0)
        x = np.clip(x, 0.0, 1.0).astype(np.float32)
        return torch.from_numpy(x), torch.tensor(y, dtype=torch.long)

    def _augment(self, x):
        x_coord = x[:, 0::3]
        y_coord = x[:, 1::3]
        conf = x[:, 2::3]

        x_coord = x_coord + np.random.normal(0, 0.018, x_coord.shape).astype(np.float32)
        y_coord = y_coord + np.random.normal(0, 0.018, y_coord.shape).astype(np.float32)

        if np.random.rand() < 0.75:
            center = np.array([0.5, 0.5], dtype=np.float32)
            pts = np.stack([x_coord, y_coord], axis=-1)
            angle = np.deg2rad(np.random.uniform(-10.0, 10.0))
            scale = np.random.uniform(0.90, 1.10)
            cos_a = np.cos(angle) * scale
            sin_a = np.sin(angle) * scale
            rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)
            pts = (pts - center) @ rot.T + center
            pts += np.random.uniform(-0.04, 0.04, size=pts.shape).astype(np.float32)
            x_coord = pts[:, :, 0]
            y_coord = pts[:, :, 1]

        if np.random.rand() < 0.5:
            x_coord = 1 - x_coord

        if np.random.rand() < 0.35:
            kp_drop = np.random.rand(x_coord.shape[1]) < 0.08
            for kp_idx, should_drop in enumerate(kp_drop):
                if should_drop:
                    x_coord[:, kp_idx] = 0.0
                    y_coord[:, kp_idx] = 0.0
                    conf[:, kp_idx] = 0.0

        x[:, 0::3] = np.clip(x_coord, 0, 1)
        x[:, 1::3] = np.clip(y_coord, 0, 1)
        x[:, 2::3] = np.clip(conf, 0, 1)

        return x


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


def build_activity_loader(df, seq_len, batch_size, augment, balanced_sampler: bool = False):
    print(f"\nCreating activity dataset | rows={len(df)} | augment={augment}")

    ds = ActivitySequenceDataset(
        df=df,
        seq_len=seq_len,
        augment=augment,
        stride=2 if augment else 5,
        min_activity_frames=6,
        min_other_frames=18,
    )

    counts_before = [0] * len(ACTIVITY_CLASSES)
    for _, lbl in ds.samples:
        counts_before[lbl] += 1
    print("Activity class sequence counts (before balancing):", counts_before)

    if augment:
        # Hard cap other so it doesn't crush everything
        max_caps = {
            # Preserve more samples for the weaker motion classes.
            ACTIVITY_LABEL_TO_ID["walk"]: 9000,
            ACTIVITY_LABEL_TO_ID["sit"]: 6000,
            ACTIVITY_LABEL_TO_ID["stand"]: 9000,
            ACTIVITY_LABEL_TO_ID["eat"]: 5000,
            ACTIVITY_LABEL_TO_ID["sleep"]: 5000,
            ACTIVITY_LABEL_TO_ID["wave"]: 5000,
            ACTIVITY_LABEL_TO_ID["other"]: 6000,
        }

        filtered = []
        ctr = {i: 0 for i in range(len(ACTIVITY_CLASSES))}

        for sample in ds.samples:
            _, lbl = sample
            if ctr[lbl] >= max_caps[lbl]:
                continue
            ctr[lbl] += 1
            filtered.append(sample)

        ds.samples = filtered

        counts_after = [0] * len(ACTIVITY_CLASSES)
        for _, lbl in ds.samples:
            counts_after[lbl] += 1
        print("Balanced activity class sequence counts:", counts_after)
        counts = counts_after
    else:
        counts = counts_before

    sampler = None
    shuffle = bool(augment)
    if balanced_sampler and ds.samples:
        sample_labels = np.array([lbl for _, lbl in ds.samples], dtype=np.int64)
        sample_counts = np.bincount(sample_labels, minlength=len(ACTIVITY_CLASSES)).astype(np.float32)
        sample_counts[sample_counts == 0] = 1.0
        sample_weights = np.array([1.0 / sample_counts[lbl] for lbl in sample_labels], dtype=np.float32)
        sampler = WeightedRandomSampler(
            weights=torch.from_numpy(sample_weights),
            num_samples=len(sample_weights),
            replacement=True,
        )
        shuffle = False
        print("Using balanced weighted sampler for activity training.")

    loader = DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        sampler=sampler,
        num_workers=0,
        pin_memory=False,
    )
    return loader, counts


def build_activity_class_weights(counts, device):
    counts = np.array(counts, dtype=np.float32)
    counts[counts == 0] = 1.0

    weights = np.sqrt(counts.sum() / (len(counts) * counts))
    weights = np.clip(weights, 1.0, 4.0)

    weights = torch.tensor(weights, dtype=torch.float32, device=device)
    print("Activity class weights:", weights.detach().cpu().numpy())
    return weights


def evaluate_activity(model, loader, criterion, device):
    model.eval()

    total_loss = 0.0
    all_labels = []
    all_preds = []
    all_probs = []

    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            y = y.to(device)

            out = model(x)
            loss = criterion(out, y)
            probs = torch.softmax(out, dim=1)
            preds = torch.argmax(out, dim=1)

            total_loss += loss.item()
            all_labels.extend(y.cpu().numpy())
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    avg_loss = total_loss / max(len(loader), 1)
    all_labels = np.array(all_labels)
    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)

    acc = 100.0 * (all_preds == all_labels).sum() / max(len(all_labels), 1)
    prec, rec, f1, support = precision_recall_fscore_support(
        all_labels,
        all_preds,
        labels=list(range(len(ACTIVITY_CLASSES))),
        zero_division=0,
    )
    macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)

    return avg_loss, acc, prec, rec, f1, support, macro_f1, all_labels, all_preds, all_probs


def save_activity_confusion_matrix(y_true, y_pred, root_dir, epoch, output_dir=None):
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(ACTIVITY_CLASSES))))
    out_dir = output_dir or os.path.join(root_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    cm_df = pd.DataFrame(cm, index=ACTIVITY_CLASSES, columns=ACTIVITY_CLASSES)
    cm_csv_path = os.path.join(out_dir, f"activity_confusion_epoch{epoch}.csv")
    cm_df.to_csv(cm_csv_path, index_label="actual_predicted")

    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        xticklabels=ACTIVITY_CLASSES,
        yticklabels=ACTIVITY_CLASSES,
        cmap="Blues",
        ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(f"Activity Confusion Matrix — Epoch {epoch}")
    plt.tight_layout()

    out_path = os.path.join(out_dir, f"activity_confusion_epoch{epoch}.png")
    plt.savefig(out_path, dpi=150)
    plt.close()

    print(f"Confusion matrix -> {out_path}")
    print(f"Confusion matrix CSV -> {cm_csv_path}")


def save_activity_epoch_metrics(
    root_dir: str,
    epoch: int,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
    prec: np.ndarray,
    rec: np.ndarray,
    f1: np.ndarray,
    support: np.ndarray,
    output_dir: str = None,
) -> None:
    out_dir = output_dir or os.path.join(root_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    report_rows = []
    for idx, name in enumerate(ACTIVITY_CLASSES):
        report_rows.append({
            "class": name,
            "precision": float(prec[idx]),
            "recall": float(rec[idx]),
            "f1": float(f1[idx]),
            "support": int(support[idx]),
        })
    report_path = os.path.join(out_dir, f"activity_report_epoch{epoch}.csv")
    pd.DataFrame(report_rows).to_csv(report_path, index=False)

    pred_rows = []
    for i, (actual_id, pred_id) in enumerate(zip(y_true, y_pred)):
        row = {
            "sample_idx": i,
            "actual": ACTIVITY_CLASSES[int(actual_id)],
            "predicted": ACTIVITY_CLASSES[int(pred_id)],
            "correct": int(actual_id == pred_id),
            "confidence": float(np.max(y_prob[i])) if len(y_prob) else 0.0,
        }
        if len(y_prob):
            for class_idx, class_name in enumerate(ACTIVITY_CLASSES):
                row[f"prob_{class_name}"] = float(y_prob[i][class_idx])
        pred_rows.append(row)

    predictions_path = os.path.join(out_dir, f"activity_predictions_epoch{epoch}.csv")
    pd.DataFrame(pred_rows).to_csv(predictions_path, index=False)
    print(f"Classification report CSV -> {report_path}")
    print(f"Prediction details CSV -> {predictions_path}")


def train_activity(
    root_dir: str = ROOT_DIR,
    epochs: int = 20,
    batch_size: int = 16,
    lr: float = 1e-4,
    seq_len: int = 30,
    seed: int = 42,
    balanced_sampler: bool = True,
    data_source: str = "activity_train",
):
    set_seed(seed)

    print("Loading activity data...")
    df = prepare_activity_data(root_dir, data_source=data_source)

    print("\nCreating train/val/test split...")
    train_df, val_df, test_df = split_by_video(df, seed=seed)

    print(f"Train rows : {len(train_df)}")
    print(f"Val rows   : {len(val_df)}")
    print(f"Test rows  : {len(test_df)}")

    print("\nBuilding train loader...")
    train_loader, train_counts = build_activity_loader(
        train_df,
        seq_len,
        batch_size,
        augment=True,
        balanced_sampler=balanced_sampler,
    )

    print("\nBuilding val loader...")
    val_loader, _ = build_activity_loader(
        val_df, seq_len, batch_size, augment=False
    )

    print("\nBuilding test loader...")
    test_loader, _ = build_activity_loader(
        test_df, seq_len, batch_size, augment=False
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    model = build_activity_model(num_classes=len(ACTIVITY_CLASSES)).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=5e-4,
        eps=1e-6,
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=4,
        verbose=True,
    )

    class_weights = build_activity_class_weights(train_counts, device)
    criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.05)

    best_val_loss = float("inf")
    best_macro_f1 = -1.0
    patience = 12
    patience_counter = 0

    save_dir = os.path.join(root_dir, "models")
    os.makedirs(save_dir, exist_ok=True)
    best_model_path = os.path.join(save_dir, "activity_best.pth")

    outputs_dir = os.path.join(root_dir, "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(outputs_dir, "activity_runs", run_id)
    os.makedirs(run_dir, exist_ok=True)

    log_path = os.path.join(run_dir, "activity_training_log.csv")
    latest_log_path = os.path.join(outputs_dir, "activity_training_log.csv")
    log_rows = []

    print(f"Activity run id : {run_id}")
    print(f"Run output dir  : {run_dir}")

    print("\n🔥 ENTERING ACTIVITY TRAINING LOOP")

    for epoch in range(1, epochs + 1):
        print(f"\n{'=' * 65}")
        print(f"  Activity Epoch {epoch}/{epochs}")
        print(f"{'=' * 65}")

        model.train()
        total_train_loss = 0.0
        skipped_batches = 0

        for batch_idx, (x, y) in enumerate(train_loader):
            if batch_idx == 0:
                print("  First training batch reached")

            x = x.to(device)
            y = y.to(device)
            x = torch.nan_to_num(x, nan=0.0, posinf=1.0, neginf=0.0).clamp(0.0, 1.0)

            optimizer.zero_grad()
            out = model(x)
            if not torch.isfinite(out).all():
                skipped_batches += 1
                optimizer.zero_grad(set_to_none=True)
                continue

            loss = criterion(out, y)
            if not torch.isfinite(loss):
                skipped_batches += 1
                optimizer.zero_grad(set_to_none=True)
                continue

            loss.backward()

            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.25)
            if not torch.isfinite(grad_norm):
                skipped_batches += 1
                optimizer.zero_grad(set_to_none=True)
                continue
            optimizer.step()

            total_train_loss += loss.item()

            if (batch_idx + 1) % 50 == 0:
                print(
                    f"  Batch {batch_idx + 1}/{len(train_loader)} "
                    f"| Loss: {loss.item():.4f}"
                )

        if skipped_batches:
            print(f"  Skipped non-finite batches: {skipped_batches}")

        avg_train_loss = total_train_loss / max(len(train_loader) - skipped_batches, 1)

        (
            avg_val_loss,
            val_acc,
            prec,
            rec,
            f1,
            support,
            macro_f1,
            y_true,
            y_pred,
            y_prob,
        ) = evaluate_activity(model, val_loader, criterion, device)

        save_activity_confusion_matrix(y_true, y_pred, root_dir, epoch, output_dir=run_dir)
        save_activity_epoch_metrics(
            root_dir,
            epoch,
            y_true,
            y_pred,
            y_prob,
            prec,
            rec,
            f1,
            support,
            output_dir=run_dir,
        )

        print(f"\nVal Loss     : {avg_val_loss:.4f}")
        print(f"Val Accuracy : {val_acc:.2f}%")
        print(f"Macro F1     : {macro_f1:.4f}")
        pred_counts = np.bincount(y_pred, minlength=len(ACTIVITY_CLASSES))
        pred_dist = {ACTIVITY_CLASSES[i]: int(pred_counts[i]) for i in range(len(ACTIVITY_CLASSES))}
        mean_conf = float(np.max(y_prob, axis=1).mean()) if len(y_prob) else 0.0
        print(f"Predicted distribution: {pred_dist}")
        print(f"Mean prediction confidence: {mean_conf:.4f}")
        print(f"\n{'Class':<10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
        print("-" * 54)
        for i, name in enumerate(ACTIVITY_CLASSES):
            print(
                f"{name:<10} {prec[i]:>10.4f} {rec[i]:>10.4f} "
                f"{f1[i]:>10.4f} {int(support[i]):>10}"
            )

        scheduler.step(macro_f1)

        log_rows.append(
            {
                "epoch": epoch,
                "train_loss": avg_train_loss,
                "val_loss": avg_val_loss,
                "val_accuracy": val_acc,
                "macro_f1": macro_f1,
                "walk_f1": f1[ACTIVITY_LABEL_TO_ID["walk"]],
                "sit_f1": f1[ACTIVITY_LABEL_TO_ID["sit"]],
                "stand_f1": f1[ACTIVITY_LABEL_TO_ID["stand"]],
                "eat_f1": f1[ACTIVITY_LABEL_TO_ID["eat"]],
                "sleep_f1": f1[ACTIVITY_LABEL_TO_ID["sleep"]],
                "wave_f1": f1[ACTIVITY_LABEL_TO_ID["wave"]],
                "other_f1": f1[ACTIVITY_LABEL_TO_ID["other"]],
            }
        )
        log_df = pd.DataFrame(log_rows)
        log_df.to_csv(log_path, index=False)
        log_df.to_csv(latest_log_path, index=False)

        print(f"\nTrain Loss: {avg_train_loss:.4f}")

        if macro_f1 > best_macro_f1:
            best_val_loss = avg_val_loss
            best_macro_f1 = macro_f1
            patience_counter = 0
            torch.save(
                {
                    "model_type": "activity_stats",
                    "model_state_dict": model.state_dict(),
                    "activity_classes": ACTIVITY_CLASSES,
                    "seq_len": seq_len,
                },
                best_model_path,
            )
            print(f"✅ Best model saved -> {best_model_path}")
            best_summary_path = os.path.join(run_dir, "activity_best_epoch_summary.csv")
            latest_best_summary_path = os.path.join(outputs_dir, "activity_best_epoch_summary.csv")
            best_summary_df = pd.DataFrame([{
                "run_id": run_id,
                "epoch": epoch,
                "val_loss": avg_val_loss,
                "val_accuracy": val_acc,
                "macro_f1": macro_f1,
                "mean_confidence": mean_conf,
                "predicted_distribution": pred_dist,
            }])
            best_summary_df.to_csv(best_summary_path, index=False)
            best_summary_df.to_csv(latest_best_summary_path, index=False)
            print(f"Best epoch summary -> {best_summary_path}")
        else:
            patience_counter += 1
            print(f"No macro-F1 improvement. Patience: {patience_counter}/{patience}")
            if patience_counter >= patience:
                print("🛑 Early stopping triggered")
                break

    print(f"\n{'=' * 65}")
    print("  TESTING BEST ACTIVITY MODEL")
    print(f"{'=' * 65}")

    checkpoint = torch.load(best_model_path, map_location=device)
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    (
        test_loss,
        test_acc,
        prec,
        rec,
        f1,
        support,
        macro_f1,
        y_true,
        y_pred,
        y_prob,
    ) = evaluate_activity(model, test_loader, criterion, device)

    print(f"Test Loss     : {test_loss:.4f}")
    print(f"Test Accuracy : {test_acc:.2f}%")
    print(f"Test Macro F1 : {macro_f1:.4f}")

    print("\nClassification Report:")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=ACTIVITY_CLASSES,
            zero_division=0,
        )
    )

    save_activity_confusion_matrix(y_true, y_pred, root_dir, epoch=999, output_dir=run_dir)
    save_activity_epoch_metrics(
        root_dir,
        999,
        y_true,
        y_pred,
        y_prob,
        prec,
        rec,
        f1,
        support,
        output_dir=run_dir,
    )

    print(f"\nBest val loss  : {best_val_loss:.4f}")
    print(f"Best macro F1  : {best_macro_f1:.4f}")
    print(f"Best model     : {best_model_path}")
    print(f"Training log   : {log_path}")
    print(f"Latest log     : {latest_log_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", default=ROOT_DIR)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--seq_len", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data_source", default="activity_train", help="Use 'activity_train', 'all_poses', or a CSV path.")
    parser.add_argument("--no_balanced_sampler", action="store_true")
    args = parser.parse_args()

    train_activity(
        root_dir=args.root_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seq_len=args.seq_len,
        seed=args.seed,
        balanced_sampler=not args.no_balanced_sampler,
        data_source=args.data_source,
    )

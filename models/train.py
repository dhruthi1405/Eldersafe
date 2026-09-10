from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_recall_fscore_support,
)
from sklearn.preprocessing import label_binarize

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configs.config import MODEL_CONFIG, ROOT_DIR
from models.tcn_lstm_model import build_model
from pipeline.pose_extractor import YOLO_KP_NAMES


CLASS_NAMES = MODEL_CONFIG["class_names"]
LABEL_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}
FALL_ID = LABEL_TO_ID["fall"]
OTHER_ID = LABEL_TO_ID["other"]


# ─────────────────────────────────────────────
# FEATURE COLUMNS
# ─────────────────────────────────────────────
def _pose_cols() -> List[str]:
    cols = []
    for n in YOLO_KP_NAMES:
        cols += [f"{n}_x", f"{n}_y", f"{n}_conf"]
    return cols


# ─────────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────────
class PoseSequenceDataset(Dataset):
    def __init__(self, df, seq_len=30, augment=False, stride=1):
        self.seq_len = seq_len
        self.augment = augment
        self.feat_cols = _pose_cols()
        self.samples = []

        grouped = df.groupby(["dataset_name", "video"])
        total_groups = len(grouped)

        print(f"Building sequences from {total_groups} videos...")

        for idx, ((dataset_name, video), g) in enumerate(grouped, start=1):
            if idx % 100 == 0 or idx == total_groups:
                print(f"  Processed {idx}/{total_groups} videos")

            g = g.sort_values("frame_idx").reset_index(drop=True)
            feats = g[self.feat_cols].fillna(0).values.astype(np.float32)

            labels = g["label"].map(LABEL_TO_ID)
            if labels.isna().any():
                unknown = g.loc[labels.isna(), "label"].unique()
                print(f"  ⚠ Unknown labels: {unknown}")
                labels = labels.fillna(OTHER_ID)

            labels = labels.values.astype(int)
            n = len(feats)

            if n < seq_len:
                pad = np.zeros((seq_len - n, feats.shape[1]), dtype=np.float32)
                feats = np.vstack([feats, pad])
                pad_label = labels[-1] if len(labels) > 0 else OTHER_ID
                labels = np.concatenate(
                    [labels, np.full(seq_len - n, pad_label, dtype=int)]
                )
                n = seq_len

            for start in range(0, n - seq_len + 1, stride):
                window = feats[start:start + seq_len]
                window_labels = labels[start:start + seq_len]

                # Fall-sensitive majority vote
                # 5+ fall frames in 30-frame window → label as fall
                fall_count = (window_labels == FALL_ID).sum()
                if fall_count >= 5:
                    label = FALL_ID
                else:
                    label = int(np.bincount(window_labels).argmax())

                self.samples.append((window, label))

        print(f"Finished building dataset. Total sequences: {len(self.samples)}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x, y = self.samples[idx]
        x = x.copy()
        if self.augment:
            x = self._augment(x)
        return torch.from_numpy(x), torch.tensor(y, dtype=torch.long)

    def _augment(self, x):
        jitter = np.random.normal(0, 0.01, x.shape).astype(np.float32)
        jitter[:, 2::3] = 0  # do not perturb confidence columns
        x = np.clip(x + jitter, 0, 1)

        # horizontal flip
        if np.random.rand() < 0.5:
            x[:, 0::3] = 1 - x[:, 0::3]

        return x


# ─────────────────────────────────────────────
# DATALOADER
# ─────────────────────────────────────────────
def _build_loader(df, seq_len, batch_size, augment, num_classes):
    print(f"\nCreating dataset | rows={len(df)} | augment={augment}")

    t0 = time.time()
    ds = PoseSequenceDataset(
        df=df,
        seq_len=seq_len,
        augment=augment,
        stride=1 if augment else max(1, seq_len // 2),
    )
    print(f"Dataset creation time: {time.time() - t0:.2f} sec")

    counts = [0] * num_classes
    for _, lbl in ds.samples:
        counts[lbl] += 1
    print("Class sequence counts (before balancing):", counts)

    if augment:
        # Stronger no-fall learning:
        # reduce fall cap, increase other cap
        MAX_FALL = 12000
        MAX_OTHER = 30000

        filtered = []
        class_ctr = {i: 0 for i in range(num_classes)}

        for sample in ds.samples:
            _, lbl = sample

            if lbl == FALL_ID and class_ctr[lbl] >= MAX_FALL:
                continue
            if lbl == OTHER_ID and class_ctr[lbl] >= MAX_OTHER:
                continue

            class_ctr[lbl] += 1
            filtered.append(sample)

        ds.samples = filtered

        counts = [0] * num_classes
        for _, lbl in ds.samples:
            counts[lbl] += 1
        print("Balanced class sequence counts:", counts)

        sampler = None
        shuffle = True
    else:
        sampler = None
        shuffle = False

    print("Creating DataLoader...")
    loader = DataLoader(
        ds,
        batch_size=batch_size,
        sampler=sampler,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=False,
    )
    print("DataLoader ready")
    return loader, counts


# ─────────────────────────────────────────────
# CLASS WEIGHTS
# ─────────────────────────────────────────────
def _build_class_weights(counts, device):
    counts = np.array(counts, dtype=np.float32)
    counts[counts == 0] = 1.0

    weights = counts.sum() / (len(counts) * counts)

    # keep weighting mild
    weights = np.clip(weights, 1.0, 3.0)

    # slight extra boost to "other" so fall is not over-predicted
    weights[OTHER_ID] = max(weights[OTHER_ID], 1.5)

    weights = torch.tensor(weights, dtype=torch.float32, device=device)
    print("Class weights:", weights.detach().cpu().numpy())
    return weights


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────
def _evaluate_and_print(
    epoch, epochs, all_labels, all_preds, all_probs,
    avg_val_loss, epoch_time, num_classes, root_dir
):
    val_acc = 100.0 * (all_preds == all_labels).sum() / max(len(all_labels), 1)

    precision, recall, f1, support = precision_recall_fscore_support(
        all_labels,
        all_preds,
        labels=list(range(num_classes)),
        zero_division=0,
    )

    print(f"\n{'=' * 65}")
    print(f"  Epoch {epoch}/{epochs} Results")
    print(f"{'=' * 65}")
    print(f"  Val Loss     : {avg_val_loss:.4f}")
    print(f"  Val Accuracy : {val_acc:.2f}%")
    print()
    print(f"  {'Class':<10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print(f"  {'-' * 54}")

    for i, name in enumerate(CLASS_NAMES):
        print(
            f"  {name:<10} {precision[i]:>10.4f} {recall[i]:>10.4f} "
            f"{f1[i]:>10.4f} {int(support[i]):>10}"
        )

    fi = FALL_ID
    print(f"\n  ⚠  FALL DETECTION")
    print(f"     Precision : {precision[fi]:.4f}")
    print(f"     Recall    : {recall[fi]:.4f}   ← how many real falls caught")
    print(f"     F1 Score  : {f1[fi]:.4f}")

    # Binary fall vs no-fall metrics
    binary_true = (all_labels == FALL_ID).astype(int)
    binary_pred = (all_preds == FALL_ID).astype(int)
    b_prec, b_rec, b_f1, _ = precision_recall_fscore_support(
        binary_true, binary_pred, average="binary", zero_division=0
    )

    print(f"\n  🔍 BINARY FALL vs NO-FALL")
    print(f"     Precision : {b_prec:.4f}")
    print(f"     Recall    : {b_rec:.4f}")
    print(f"     F1 Score  : {b_f1:.4f}")

    try:
        y_bin = label_binarize(all_labels, classes=list(range(num_classes)))
        auc_list = []

        print(f"\n  ROC-AUC (one-vs-rest):")
        for i, name in enumerate(CLASS_NAMES):
            if y_bin[:, i].sum() > 0:
                auc = roc_auc_score(y_bin[:, i], all_probs[:, i])
                auc_list.append(auc)
                marker = " ← fall" if name == "fall" else ""
                print(f"    {name:<10}: {auc:.4f}{marker}")

        if auc_list:
            print(f"    {'macro avg':<10}: {np.mean(auc_list):.4f}")

    except Exception as e:
        print(f"  ROC-AUC skipped: {e}")

    print(f"\n  Full Classification Report:")
    print(classification_report(
        all_labels,
        all_preds,
        target_names=CLASS_NAMES,
        zero_division=0,
    ))

    cm = confusion_matrix(all_labels, all_preds, labels=list(range(num_classes)))
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        xticklabels=CLASS_NAMES,
        yticklabels=CLASS_NAMES,
        cmap="Blues",
        ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(f"Confusion Matrix — Epoch {epoch}")
    plt.tight_layout()

    out_dir = os.path.join(root_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    cm_path = os.path.join(out_dir, f"confusion_matrix_epoch{epoch}.png")
    plt.savefig(cm_path, dpi=150)
    plt.close()

    print(f"  Confusion matrix → {cm_path}")
    print(f"  Epoch time: {epoch_time:.2f} sec")

    return val_acc, f1[fi], b_f1


# ─────────────────────────────────────────────
# MAIN TRAIN
# ─────────────────────────────────────────────
def train(root_dir, epochs=50, batch_size=32, lr=1e-3, seq_len=30, seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    pose_csv = os.path.join(root_dir, "datasets", "processed", "all_poses.csv")
    print("Loading pose data:", pose_csv)
    df = pd.read_csv(pose_csv, low_memory=False)

    df["label"] = df["label"].fillna("other")
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df.loc[df["label"].isin(["nan", "none", "null", ""]), "label"] = "other"

    print("Rows:", len(df))
    print("Label distribution:\n", df["label"].value_counts())

    print("\nCreating train/val/test split...")
    videos = df[["dataset_name", "video"]].drop_duplicates()
    videos = videos.sample(frac=1, random_state=seed).reset_index(drop=True)

    n = len(videos)
    test_v = videos[:int(0.15 * n)]
    val_v = videos[int(0.15 * n):int(0.30 * n)]
    train_v = videos[int(0.30 * n):]

    df_train = df.merge(train_v, on=["dataset_name", "video"])
    df_val = df.merge(val_v, on=["dataset_name", "video"])
    df_test = df.merge(test_v, on=["dataset_name", "video"])

    print(f"Train rows : {len(df_train)}")
    print(f"Val rows   : {len(df_val)}")
    print(f"Test rows  : {len(df_test)}")

    num_classes = MODEL_CONFIG["num_classes"]

    print("\nBuilding train loader...")
    train_loader, train_counts = _build_loader(
        df_train, seq_len, batch_size, True, num_classes
    )

    print("\nBuilding val loader...")
    val_loader, _ = _build_loader(
        df_val, seq_len, batch_size, False, num_classes
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    in_features = len(_pose_cols())
    model = build_model(in_features=in_features).to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=lr,
        weight_decay=MODEL_CONFIG.get("weight_decay", 1e-4),
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=3, verbose=True
    )

    class_weights = _build_class_weights(train_counts, device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    best_val_loss = float("inf")
    patience = MODEL_CONFIG.get("early_stopping_patience", 10)
    patience_counter = 0

    save_dir = os.path.join(root_dir, "models")
    os.makedirs(save_dir, exist_ok=True)
    best_model_path = os.path.join(save_dir, "tcn_bilstm_best.pth")

    log_path = os.path.join(root_dir, "outputs", "training_log.csv")
    os.makedirs(os.path.join(root_dir, "outputs"), exist_ok=True)
    log_rows = []

    print("\n🔥 ENTERING TRAINING LOOP")

    for epoch in range(1, epochs + 1):
        print(f"\n{'=' * 65}")
        print(f"  Epoch {epoch}/{epochs}")
        print(f"{'=' * 65}")

        model.train()
        total_loss = 0.0
        epoch_start = time.time()

        for batch_idx, (x, y) in enumerate(train_loader):
            if batch_idx == 0:
                print("  First training batch reached")

            x, y = x.to(device), y.to(device)

            optimizer.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item()

            if (batch_idx + 1) % 50 == 0:
                print(
                    f"  Batch {batch_idx + 1}/{len(train_loader)} "
                    f"| Loss: {loss.item():.4f}"
                )

        avg_train_loss = total_loss / max(len(train_loader), 1)
        print(f"\n  Epoch {epoch} training loss: {avg_train_loss:.4f}")

        model.eval()
        val_loss = 0.0
        all_preds = []
        all_labels = []
        all_probs = []

        with torch.no_grad():
            for batch_idx, (x, y) in enumerate(val_loader):
                if batch_idx == 0:
                    print("  First validation batch reached")

                x, y = x.to(device), y.to(device)
                out = model(x)
                loss = criterion(out, y)

                val_loss += loss.item()

                probs = torch.softmax(out, dim=1)
                preds = torch.argmax(out, dim=1)

                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(y.cpu().numpy())
                all_probs.extend(probs.cpu().numpy())

        all_preds = np.array(all_preds)
        all_labels = np.array(all_labels)
        all_probs = np.array(all_probs)

        avg_val_loss = val_loss / max(len(val_loader), 1)
        epoch_time = time.time() - epoch_start

        val_acc, fall_f1, binary_fall_f1 = _evaluate_and_print(
            epoch,
            epochs,
            all_labels,
            all_preds,
            all_probs,
            avg_val_loss,
            epoch_time,
            num_classes,
            root_dir,
        )

        scheduler.step(avg_val_loss)

        precision, recall, f1, _ = precision_recall_fscore_support(
            all_labels,
            all_preds,
            labels=list(range(num_classes)),
            zero_division=0,
        )

        binary_true = (all_labels == FALL_ID).astype(int)
        binary_pred = (all_preds == FALL_ID).astype(int)
        b_prec, b_rec, b_f1, _ = precision_recall_fscore_support(
            binary_true, binary_pred, average="binary", zero_division=0
        )

        log_rows.append({
            "epoch": epoch,
            "train_loss": avg_train_loss,
            "val_loss": avg_val_loss,
            "val_accuracy": val_acc,
            "fall_precision": precision[FALL_ID],
            "fall_recall": recall[FALL_ID],
            "fall_f1": f1[FALL_ID],
            "binary_fall_precision": b_prec,
            "binary_fall_recall": b_rec,
            "binary_fall_f1": b_f1,
        })
        pd.DataFrame(log_rows).to_csv(log_path, index=False)

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0
            torch.save(model.state_dict(), best_model_path)
            print(f"\n  ✅ Best model saved → {best_model_path}")
        else:
            patience_counter += 1
            print(f"\n  No improvement. Patience: {patience_counter}/{patience}")
            if patience_counter >= patience:
                print("  🛑 Early stopping triggered")
                break

    print(f"\n{'=' * 65}")
    print("  TRAINING COMPLETE")
    print(f"{'=' * 65}")
    print(f"  Best val loss  : {best_val_loss:.4f}")
    print(f"  Best model     : {best_model_path}")
    print(f"  Training log   : {log_path}")
    print(f"  Confusion maps : outputs/confusion_matrix_epochN.png")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", default=ROOT_DIR)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seq_len", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train(
        root_dir=args.root_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seq_len=args.seq_len,
        seed=args.seed,
    )
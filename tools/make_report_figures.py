from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


ROOT = Path(r"C:\ElderCareProject")
REPORT_IMAGES = ROOT / "ElderCare_AI_Project_Report_Overleaf" / "images"
PAPER_FIGURES = ROOT / "outputs" / "paper_figures"
ACTIVITY_RUN = ROOT / "outputs" / "activity_runs" / "20260423_045449"

REPORT_IMAGES.mkdir(parents=True, exist_ok=True)


def box(ax, x, y, w, h, title, subtitle="", fc="#ffffff", ec="#2b6cb0"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        linewidth=1.6,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h * 0.62,
        title,
        ha="center",
        va="center",
        fontsize=10,
        weight="bold",
        color="#1a202c",
    )
    if subtitle:
        ax.text(
            x + w / 2,
            y + h * 0.34,
            subtitle,
            ha="center",
            va="center",
            fontsize=8.5,
            color="#4a5568",
        )


def arrow(ax, start, end, color="#4a5568"):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.4, shrinkA=4, shrinkB=4),
    )


def save(fig, name):
    path = REPORT_IMAGES / name
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def make_system_architecture():
    fig, ax = plt.subplots(figsize=(13, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(
        0.5,
        0.96,
        "ElderCare AI Full System Architecture",
        ha="center",
        fontsize=16,
        weight="bold",
        color="#1a202c",
    )

    items = [
        (0.06, 0.76, "Video Input", "uploaded video / live stream", "#e6fffa", "#2c7a7b"),
        (0.28, 0.76, "Pose Extraction", "YOLOv8 + MediaPipe keypoints", "#eef2ff", "#5a67d8"),
        (0.50, 0.76, "Temporal Sequences", "30-frame pose windows", "#ebf8ff", "#3182ce"),
        (0.72, 0.76, "Inference Engine", "fall + activity + gait", "#f5f3ff", "#6b46c1"),
        (0.17, 0.50, "Fall Detection", "binary fall / no-fall model", "#fff5f5", "#e53e3e"),
        (0.39, 0.50, "Activity Recognition", "walk, sit, stand, eat, sleep, wave, other", "#f0fff4", "#38a169"),
        (0.61, 0.50, "Gait Risk Analysis", "low / medium / high risk", "#fffaf0", "#dd6b20"),
        (0.83, 0.50, "SOS Alerts", "fall and high-risk events", "#fff5f5", "#c53030"),
        (0.28, 0.24, "FastAPI Backend", "REST API and processing control", "#edf2f7", "#4a5568"),
        (0.50, 0.24, "PostgreSQL Database", "patients, sessions, predictions, alerts", "#edf2f7", "#4a5568"),
        (0.72, 0.24, "React Dashboard", "caregiver monitoring interface", "#edf2f7", "#4a5568"),
    ]
    for x, y, title, sub, fc, ec in items:
        box(ax, x, y, 0.17, 0.105, title, sub, fc, ec)

    arrow(ax, (0.23, 0.81), (0.28, 0.81))
    arrow(ax, (0.45, 0.81), (0.50, 0.81))
    arrow(ax, (0.67, 0.81), (0.72, 0.81))
    arrow(ax, (0.80, 0.76), (0.25, 0.605))
    arrow(ax, (0.80, 0.76), (0.47, 0.605))
    arrow(ax, (0.80, 0.76), (0.69, 0.605))
    arrow(ax, (0.69, 0.50), (0.83, 0.555))
    arrow(ax, (0.915, 0.50), (0.805, 0.345))
    arrow(ax, (0.255, 0.50), (0.365, 0.345))
    arrow(ax, (0.475, 0.50), (0.365, 0.345))
    arrow(ax, (0.695, 0.50), (0.365, 0.345))
    arrow(ax, (0.45, 0.295), (0.50, 0.295))
    arrow(ax, (0.67, 0.295), (0.72, 0.295))

    ax.text(
        0.5,
        0.10,
        "The dashboard converts model predictions into patient-session summaries, skeleton videos, activity context, and alert history.",
        ha="center",
        fontsize=10,
        color="#4a5568",
    )
    save(fig, "system_architecture.png")


def make_ml_architecture():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(
        0.5,
        0.95,
        "Machine Learning Architecture",
        ha="center",
        fontsize=16,
        weight="bold",
    )

    ys = [0.80, 0.65, 0.50, 0.35, 0.20]
    labels = [
        ("Pose Sequence Input", "30 frames x 51 pose features"),
        ("Input Projection + Normalization", "coordinate and confidence values scaled to 0-1"),
        ("TCN Encoder", "local motion pattern extraction"),
        ("BiLSTM + Temporal Attention", "bidirectional temporal context and informative time-step weighting"),
        ("Prediction Heads", "fall/no-fall and seven-class activity output"),
    ]
    for y, (title, sub) in zip(ys, labels):
        box(ax, 0.30, y, 0.40, 0.095, title, sub, "#eef2ff", "#5a67d8")
    for y1, y2 in zip(ys[:-1], ys[1:]):
        arrow(ax, (0.50, y1), (0.50, y2 + 0.095))

    box(ax, 0.06, 0.18, 0.20, 0.13, "Fall Output", "fall / no-fall\nAcc. 76.99%, F1 82.13%", "#fff5f5", "#e53e3e")
    box(ax, 0.74, 0.18, 0.20, 0.13, "Activity Output", "walk, sit, stand, eat,\nsleep, wave, other", "#f0fff4", "#38a169")
    arrow(ax, (0.37, 0.20), (0.26, 0.245), "#e53e3e")
    arrow(ax, (0.63, 0.20), (0.74, 0.245), "#38a169")

    save(fig, "ml_architecture.png")


def make_app_architecture():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.95, "Application Architecture", ha="center", fontsize=16, weight="bold")

    box(ax, 0.07, 0.72, 0.22, 0.12, "React Dashboard", "upload video, view results,\nreview alerts", "#ebf8ff", "#3182ce")
    box(ax, 0.39, 0.72, 0.22, 0.12, "FastAPI Backend", "REST endpoints and\nsession management", "#edf2f7", "#4a5568")
    box(ax, 0.71, 0.72, 0.22, 0.12, "PostgreSQL", "patients, sessions,\npredictions, alerts", "#f0fff4", "#38a169")

    box(ax, 0.22, 0.43, 0.22, 0.12, "Inference Pipeline", "pose extraction and\nmodel prediction", "#f5f3ff", "#6b46c1")
    box(ax, 0.56, 0.43, 0.22, 0.12, "Output Generation", "skeleton video,\nmetrics, alert event", "#fffaf0", "#dd6b20")
    box(ax, 0.39, 0.17, 0.22, 0.12, "Caregiver Review", "fall status, activity,\ngait risk, alert history", "#fff5f5", "#e53e3e")

    arrow(ax, (0.29, 0.78), (0.39, 0.78))
    arrow(ax, (0.61, 0.78), (0.71, 0.78))
    arrow(ax, (0.50, 0.72), (0.35, 0.55))
    arrow(ax, (0.44, 0.49), (0.56, 0.49))
    arrow(ax, (0.67, 0.43), (0.61, 0.29))
    arrow(ax, (0.50, 0.17), (0.20, 0.72))
    arrow(ax, (0.67, 0.55), (0.78, 0.72))

    save(fig, "app_architecture.png")


def make_testing_workflow():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.95, "Model and Application Testing Workflow", ha="center", fontsize=16, weight="bold")

    steps = [
        ("Load Processed Data", "fall and activity CSV files"),
        ("Build Test Sequences", "video-level split, 30-frame windows"),
        ("Evaluate Saved Models", "precision, recall, F1, ROC-AUC"),
        ("Generate Figures", "confusion matrix and ROC curve"),
        ("Run Inference on Videos", "skeleton overlay and predictions"),
        ("Verify Dashboard", "session results and alert display"),
    ]
    coords = [(0.08, 0.72), (0.39, 0.72), (0.70, 0.72), (0.70, 0.42), (0.39, 0.42), (0.08, 0.42)]
    for (x, y), (title, sub) in zip(coords, steps):
        box(ax, x, y, 0.22, 0.12, title, sub, "#eef2ff", "#5a67d8")

    arrow(ax, (0.30, 0.78), (0.39, 0.78))
    arrow(ax, (0.61, 0.78), (0.70, 0.78))
    arrow(ax, (0.81, 0.72), (0.81, 0.54))
    arrow(ax, (0.70, 0.48), (0.61, 0.48))
    arrow(ax, (0.39, 0.48), (0.30, 0.48))

    box(ax, 0.28, 0.16, 0.44, 0.12, "Final Validation", "model metrics + visual output + application flow confirmed", "#f0fff4", "#38a169")
    arrow(ax, (0.19, 0.42), (0.41, 0.28))
    arrow(ax, (0.81, 0.42), (0.59, 0.28))

    save(fig, "testing_workflow.png")


def make_activity_performance():
    classes = ["Walk", "Sit", "Stand", "Eat", "Sleep", "Wave", "Other"]
    f1_scores = [72.06, 93.02, 65.65, 100.0, 100.0, 100.0, 53.85]
    colors = ["#3182ce", "#38a169", "#dd6b20", "#805ad5", "#2c7a7b", "#d53f8c", "#718096"]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(classes, f1_scores, color=colors)
    ax.set_ylim(0, 110)
    ax.set_ylabel("F1-score (%)")
    ax.set_title("Activity Recognition Per-Class F1-score", fontsize=15, weight="bold")
    ax.grid(axis="y", alpha=0.25)
    for bar, score in zip(bars, f1_scores):
        ax.text(bar.get_x() + bar.get_width() / 2, score + 2, f"{score:.2f}%", ha="center", fontsize=9)
    ax.text(
        0.5,
        -0.14,
        "Validation accuracy: 80.86%, Macro F1: 83.51%",
        transform=ax.transAxes,
        ha="center",
        fontsize=10,
        color="#4a5568",
    )
    plt.tight_layout()
    save(fig, "activity_confusion.png")
    shutil.copy2(REPORT_IMAGES / "activity_confusion.png", REPORT_IMAGES / "activity_performance.png")


def copy_existing_figures():
    copies = [
        (PAPER_FIGURES / "model2_final_confusion_matrix.png", REPORT_IMAGES / "model2_final_confusion_matrix.png"),
        (PAPER_FIGURES / "model2_final_roc_curve.png", REPORT_IMAGES / "model2_final_roc_curve.png"),
        (PAPER_FIGURES / "fall_only_architecture.png", REPORT_IMAGES / "fall_only_architecture.png"),
    ]
    existing_activity = ACTIVITY_RUN / "activity_confusion_epoch999.png"
    if existing_activity.exists():
        copies.append((existing_activity, REPORT_IMAGES / "activity_confusion_latest_run.png"))

    for src, dst in copies:
        if src.exists():
            shutil.copy2(src, dst)
            print(f"Copied: {dst}")
        else:
            print(f"Missing, skipped: {src}")


def main():
    copy_existing_figures()
    make_system_architecture()
    make_ml_architecture()
    make_app_architecture()
    make_testing_workflow()
    make_activity_performance()


if __name__ == "__main__":
    main()

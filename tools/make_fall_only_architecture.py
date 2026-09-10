from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


ROOT = Path(r"C:\ElderCareProject")
OUT_DIR = ROOT / "outputs" / "paper_figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def add_box(
    ax,
    xy,
    width,
    height,
    title,
    subtitle="",
    face="#ffffff",
    edge="#2b6cb0",
    title_color="#1a365d",
    subtitle_color="#4a5568",
    fontsize=9.5,
):
    x, y = xy
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.035",
        linewidth=1.4,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(box)
    ax.text(
        x + width / 2,
        y + height * 0.62,
        title,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=title_color,
        weight="bold",
    )
    if subtitle:
        ax.text(
            x + width / 2,
            y + height * 0.34,
            subtitle,
            ha="center",
            va="center",
            fontsize=fontsize - 1.4,
            color=subtitle_color,
        )


def arrow(ax, start, end, color="#4a5568", lw=1.15, style="-|>"):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle=style, color=color, lw=lw, shrinkA=4, shrinkB=4),
    )


def main():
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.965,
        "Fall-Only Comparative Architecture of the Proposed System",
        ha="center",
        va="center",
        fontsize=15,
        weight="bold",
        color="#1a202c",
    )

    # Shared input and pose extraction.
    add_box(
        ax,
        (0.34, 0.86),
        0.32,
        0.07,
        "Video input",
        "elderly monitoring video stream",
        face="#e6fffa",
        edge="#319795",
        title_color="#234e52",
    )
    add_box(
        ax,
        (0.25, 0.74),
        0.50,
        0.085,
        "Pose estimation",
        "YOLOv8 pose for Model 1; hybrid YOLOv8 + MediaPipe for Model 2",
        face="#eef2ff",
        edge="#5a67d8",
        title_color="#3730a3",
    )
    arrow(ax, (0.50, 0.86), (0.50, 0.825))

    # Split line.
    ax.plot([0.50, 0.50], [0.71, 0.18], "--", lw=1.0, color="#cbd5e0", alpha=0.9)
    ax.text(
        0.25,
        0.695,
        "Model 1: Single-dataset fall detector",
        ha="center",
        va="center",
        fontsize=10,
        color="#2b6cb0",
        weight="bold",
    )
    ax.text(
        0.75,
        0.695,
        "Model 2: Unified multi-source fall detector",
        ha="center",
        va="center",
        fontsize=10,
        color="#2f855a",
        weight="bold",
    )

    # Branch arrows from pose box.
    arrow(ax, (0.42, 0.74), (0.25, 0.66), color="#2b6cb0")
    arrow(ax, (0.58, 0.74), (0.75, 0.66), color="#2f855a")

    # Left branch.
    left_x = 0.08
    w = 0.34
    y_positions = [0.59, 0.47, 0.35, 0.23]
    add_box(
        ax,
        (left_x, y_positions[0]),
        w,
        0.075,
        "Feature extraction",
        "8 biomechanical motion features from skeleton",
        face="#ebf8ff",
        edge="#3182ce",
    )
    add_box(
        ax,
        (left_x, y_positions[1]),
        w,
        0.075,
        "Temporal windowing",
        "30-frame sequence window",
        face="#ebf8ff",
        edge="#3182ce",
    )
    add_box(
        ax,
        (left_x, y_positions[2]),
        w,
        0.075,
        "TCN + Transformer encoder",
        "local motion patterns + long-range temporal context",
        face="#f5f3ff",
        edge="#6b46c1",
    )
    add_box(
        ax,
        (left_x, y_positions[3]),
        w,
        0.085,
        "Binary fall decision",
        "Le2i only: Acc. 85.25%, Recall 95.56%, AUC 0.949",
        face="#fff5f5",
        edge="#e53e3e",
        title_color="#742a2a",
    )
    for y1, y2 in zip(y_positions[:-1], y_positions[1:]):
        arrow(ax, (left_x + w / 2, y1), (left_x + w / 2, y2 + 0.075))
    ax.text(
        left_x + w / 2,
        0.17,
        "ElderSafe TCNTE",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#2b6cb0",
        weight="bold",
    )

    # Right branch.
    right_x = 0.58
    y_positions = [0.59, 0.47, 0.35, 0.23]
    add_box(
        ax,
        (right_x, y_positions[0]),
        w,
        0.075,
        "Unified binary pose dataset",
        "674,212 rows: 234,752 fall + 439,460 no-fall",
        face="#f0fff4",
        edge="#38a169",
        title_color="#22543d",
    )
    add_box(
        ax,
        (right_x, y_positions[1]),
        w,
        0.075,
        "Keypoint normalization",
        "51 pose channels scaled to common coordinate range",
        face="#f0fff4",
        edge="#38a169",
        title_color="#22543d",
    )
    add_box(
        ax,
        (right_x, y_positions[2]),
        w,
        0.075,
        "TCN + BiLSTM + temporal attention",
        "30-frame pose sequences; balanced train windows",
        face="#f5f3ff",
        edge="#6b46c1",
    )
    add_box(
        ax,
        (right_x, y_positions[3]),
        w,
        0.085,
        "Binary fall decision",
        "Unified test: Acc. 76.99%, Recall 83.35%, AUC 0.8207",
        face="#fff5f5",
        edge="#e53e3e",
        title_color="#742a2a",
    )
    for y1, y2 in zip(y_positions[:-1], y_positions[1:]):
        arrow(ax, (right_x + w / 2, y1), (right_x + w / 2, y2 + 0.075))
    ax.text(
        right_x + w / 2,
        0.17,
        "ElderCare AI TCN-BiLSTM",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#2f855a",
        weight="bold",
    )

    ax.text(
        0.5,
        0.075,
        "Comparison objective: in-domain sensitivity on Le2i versus robustness under unified multi-source training",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#4a5568",
    )

    png_path = OUT_DIR / "fall_only_architecture.png"
    pdf_path = OUT_DIR / "fall_only_architecture.pdf"
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved PNG: {png_path}")
    print(f"Saved PDF: {pdf_path}")


if __name__ == "__main__":
    main()

import os
import pandas as pd
from configs.config import LABEL_REMAP


VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv")


def _infer_label_from_path(path: str) -> str:
    p = path.lower()

    # fall / non-fall heuristics
    if "fall" in p:
        return "fall"
    if "adl" in p or "no_fall" in p or "nofall" in p:
        return "other"

    # check remap keys
    for key, value in LABEL_REMAP.items():
        if key.lower() in p:
            return value

    return "other"


def build_manifest(root_dir: str) -> None:
    raw_dir = os.path.join(root_dir, "datasets", "raw")
    out_dir = os.path.join(root_dir, "metadata")
    os.makedirs(out_dir, exist_ok=True)

    rows = []

    if not os.path.exists(raw_dir):
        raise FileNotFoundError(f"Raw dataset folder not found: {raw_dir}")

    for dataset_name in os.listdir(raw_dir):
        dataset_path = os.path.join(raw_dir, dataset_name)

        if not os.path.isdir(dataset_path):
            continue

        for current_root, _, files in os.walk(dataset_path):
            for file in files:
                if file.lower().endswith(VIDEO_EXTS):
                    full_path = os.path.join(current_root, file)
                    rel_path = os.path.relpath(full_path, root_dir)
                    label = _infer_label_from_path(full_path)

                    rows.append({
                        "dataset_name": dataset_name,
                        "video_path": full_path,
                        "relative_path": rel_path,
                        "video_file": file,
                        "label": label,
                    })

    df = pd.DataFrame(rows)

    out_csv = os.path.join(out_dir, "global_manifest.csv")
    df.to_csv(out_csv, index=False)

    print(f"Saved manifest: {out_csv}")
    print(f"Total videos found: {len(df)}")

    if len(df) > 0:
        print("\nLabel distribution:")
        print(df["label"].value_counts())
    else:
        print("\nNo videos found. Check dataset folder structure.")
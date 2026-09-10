import os
import re
import pandas as pd

from pipeline.pose_extractor import extract_pose_from_video, extract_pose_from_image_folder

VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv")
IMAGE_EXTS = (".jpg", ".jpeg", ".png")
LE2I_FALL_PRE_FRAMES = 15
LE2I_FALL_POST_FRAMES = 60
MULTICAM_FALL_PRE_FRAMES = 15
MULTICAM_FALL_POST_FRAMES = 60


def _out_csv_path(root_dir: str, dataset_name: str):
    out_dir = os.path.join(root_dir, "datasets", "processed", "pose", dataset_name)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, "hybrid_pose.csv")


def _is_image_folder(folder_path: str) -> bool:
    if not os.path.isdir(folder_path):
        return False
    try:
        files = os.listdir(folder_path)
    except Exception:
        return False
    return any(f.lower().endswith(IMAGE_EXTS) for f in files)


def _write_rows(csv_path: str, rows: list, write_header: bool):
    if not rows:
        return write_header

    df = pd.DataFrame(rows)
    mode = "w" if write_header else "a"
    df.to_csv(csv_path, mode=mode, index=False, header=write_header)
    return False


# =========================
# LE2I HELPERS
# =========================
def load_le2i_annotations(txt_path: str):
    with open(txt_path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    integer_lines = []
    frame_rows = []
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 1:
            try:
                integer_lines.append(int(parts[0]))
            except ValueError:
                continue
        else:
            try:
                frame_rows.append([int(float(part)) for part in parts])
            except ValueError:
                continue

    if len(integer_lines) >= 2:
        fall_start = integer_lines[0]
        fall_end = integer_lines[1]
        return fall_start, fall_end

    # Some LE2I annotation files in this copy contain only per-frame bounding
    # boxes. The second column is a posture/person state; use non-zero state
    # rows as the annotated event interval instead of failing the video.
    event_frames = [row[0] for row in frame_rows if len(row) >= 2 and row[1] > 0]
    if event_frames:
        return min(event_frames), max(event_frames)

    if len(frame_rows) >= 2:
        frame_numbers = [row[0] for row in frame_rows if row]
        return min(frame_numbers), max(frame_numbers)

    if len(lines) < 2:
        return None, None

    return None, None


def _expanded_interval_contains(frame_number: int, start: int, end: int, pre: int, post: int) -> bool:
    return (start - pre) <= frame_number <= (end + post)


def _find_child_dir(parent: str, names: tuple) -> str:
    if not os.path.isdir(parent):
        return None
    wanted = {name.lower() for name in names}
    for item in os.listdir(parent):
        path = os.path.join(parent, item)
        if os.path.isdir(path) and item.lower() in wanted:
            return path
    return None


def process_le2i_dataset(root_dir: str, dataset_name: str, frame_skip: int = 3):
    dataset_path = os.path.join(root_dir, "datasets", "raw", dataset_name)
    output_csv = _out_csv_path(root_dir, dataset_name)

    print(f"\nProcessing LE2I dataset: {dataset_name}")
    print(f"Source: {dataset_path}")

    if not os.path.exists(dataset_path):
        print(f"Dataset not found: {dataset_path}")
        return

    if os.path.exists(output_csv):
        os.remove(output_csv)

    write_header = True
    total_rows = 0

    for scene in os.listdir(dataset_path):
        scene_path = os.path.join(dataset_path, scene)
        if not os.path.isdir(scene_path):
            continue

        nested_dirs = [scene_path]
        for item in os.listdir(scene_path):
            sub = os.path.join(scene_path, item)
            if os.path.isdir(sub):
                nested_dirs.append(sub)

        for candidate_root in nested_dirs:
            video_dir = _find_child_dir(candidate_root, ("Videos", "Video"))
            ann_dir = _find_child_dir(
                candidate_root,
                ("Annotation_files", "Annotations_files", "Annotation", "Annotations"),
            )

            if not video_dir or not ann_dir:
                continue

            for file in os.listdir(video_dir):
                if not file.lower().endswith(VIDEO_EXTS):
                    continue

                video_path = os.path.join(video_dir, file)
                txt_name = file.rsplit(".", 1)[0] + ".txt"
                txt_path = os.path.join(ann_dir, txt_name)

                if not os.path.exists(txt_path):
                    print(f"Missing annotation for: {video_path}")
                    continue

                try:
                    fall_start, fall_end = load_le2i_annotations(txt_path)
                    if fall_start is None:
                        print(f"Bad annotation file: {txt_path}")
                        continue

                    pose_data = extract_pose_from_video(video_path, frame_skip)

                    if pose_data:
                        rows = []
                        for i, frame in enumerate(pose_data):
                            frame_number = i * frame_skip + 1
                            label = "fall" if _expanded_interval_contains(
                                frame_number,
                                fall_start,
                                fall_end,
                                LE2I_FALL_PRE_FRAMES,
                                LE2I_FALL_POST_FRAMES,
                            ) else "other"

                            frame["video"] = file
                            frame["dataset_name"] = dataset_name
                            frame["frame_idx"] = frame_number
                            frame["label"] = label
                            rows.append(frame)

                        write_header = _write_rows(output_csv, rows, write_header)
                        total_rows += len(rows)
                        print(f"Processed LE2I video: {file} ({len(rows)} frames)")
                    else:
                        print(f"No pose data: {file}")

                except Exception as e:
                    print(f"Failed LE2I video: {video_path} -> {e}")

    if total_rows == 0:
        print("No LE2I data extracted.")
        return

    print(f"Saved: {output_csv} ({total_rows} rows)")


# =========================
# MULTIPLE CAMERAS HELPERS
# =========================
def load_multiple_cameras_annotations(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    df["chute"] = df["chute"].astype(int)
    df["cam"] = df["cam"].astype(int)
    df["start"] = df["start"].astype(int)
    df["end"] = df["end"].astype(int)
    df["label"] = df["label"].astype(int)

    return df


def map_multiple_cameras_label(x: int) -> str:
    return "fall" if x == 1 else "other"


def parse_chute_cam_from_path(video_path: str):
    p = video_path.lower().replace("\\", "/")

    chute_match = re.search(r"chute(\d+)", p)
    cam_match = re.search(r"cam(\d+)\.(avi|mp4|mov|mkv)$", p)

    if not chute_match or not cam_match:
        return None, None

    chute_id = int(chute_match.group(1))
    cam_id = int(cam_match.group(1))
    return chute_id, cam_id


def process_multiple_cameras_dataset(root_dir: str, dataset_name: str, frame_skip: int = 3):
    dataset_path = os.path.join(root_dir, "datasets", "raw", dataset_name)
    output_csv = _out_csv_path(root_dir, dataset_name)

    print(f"\nProcessing multiple cameras dataset: {dataset_name}")
    print(f"Source: {dataset_path}")

    if not os.path.exists(dataset_path):
        print(f"Dataset not found: {dataset_path}")
        return

    ann_csv = os.path.join(dataset_path, "data_tuple3.csv")
    if not os.path.exists(ann_csv):
        print(f"Annotation CSV not found: {ann_csv}")
        return

    ann_df = load_multiple_cameras_annotations(ann_csv)

    if os.path.exists(output_csv):
        os.remove(output_csv)

    write_header = True
    total_rows = 0

    for current_root, dirs, files in os.walk(dataset_path):
        for file in files:
            if not file.lower().endswith(VIDEO_EXTS):
                continue

            video_path = os.path.join(current_root, file)

            chute_id, cam_id = parse_chute_cam_from_path(video_path)
            if chute_id is None or cam_id is None:
                continue

            video_ann = ann_df[
                (ann_df["chute"] == chute_id) &
                (ann_df["cam"] == cam_id)
            ].copy()

            if video_ann.empty:
                print(f"No annotation found for: {video_path}")
                continue

            try:
                pose_data = extract_pose_from_video(video_path, frame_skip)

                if pose_data:
                    rows = []
                    for i, frame in enumerate(pose_data):
                        frame_number = i * frame_skip

                        matched = video_ann[
                            (video_ann["start"] <= frame_number) &
                            (video_ann["end"] >= frame_number)
                        ]

                        fall_intervals = video_ann[video_ann["label"] == 1]
                        in_expanded_fall = any(
                            _expanded_interval_contains(
                                frame_number,
                                int(row["start"]),
                                int(row["end"]),
                                MULTICAM_FALL_PRE_FRAMES,
                                MULTICAM_FALL_POST_FRAMES,
                            )
                            for _, row in fall_intervals.iterrows()
                        )

                        if in_expanded_fall:
                            label = "fall"
                        elif not matched.empty:
                            raw_label = int(matched.iloc[0]["label"])
                            label = map_multiple_cameras_label(raw_label)
                        else:
                            label = "other"

                        frame["video"] = f"chute{chute_id:02d}_cam{cam_id}"
                        frame["dataset_name"] = dataset_name
                        frame["frame_idx"] = frame_number
                        frame["label"] = label
                        rows.append(frame)

                    write_header = _write_rows(output_csv, rows, write_header)
                    total_rows += len(rows)
                    print(f"Processed multiple-cameras video: chute{chute_id:02d} cam{cam_id} ({len(rows)} frames)")
                else:
                    print(f"No pose data: {video_path}")

            except Exception as e:
                print(f"Failed video: {video_path} -> {e}")

    if total_rows == 0:
        print("No multiple-cameras data extracted.")
        return

    print(f"Saved: {output_csv} ({total_rows} rows)")


# =========================
# GENERIC DATASET PROCESSOR
# =========================
def process_generic_dataset(root_dir: str, dataset_name: str, frame_skip: int = 3):
    dataset_path = os.path.join(root_dir, "datasets", "raw", dataset_name)
    output_csv = _out_csv_path(root_dir, dataset_name)

    print(f"\nProcessing generic dataset: {dataset_name}")
    print(f"Source: {dataset_path}")

    if not os.path.exists(dataset_path):
        print(f"Dataset not found: {dataset_path}")
        return

    if os.path.exists(output_csv):
        os.remove(output_csv)

    write_header = True
    total_rows = 0

    for current_root, dirs, files in os.walk(dataset_path):
        for file in files:
            if file.lower().endswith(VIDEO_EXTS):
                video_path = os.path.join(current_root, file)

                try:
                    pose_data = extract_pose_from_video(video_path, frame_skip)

                    if pose_data:
                        rows = []
                        for i, frame in enumerate(pose_data):
                            frame["video"] = file
                            frame["dataset_name"] = dataset_name
                            frame["frame_idx"] = i * frame_skip
                            rows.append(frame)

                        write_header = _write_rows(output_csv, rows, write_header)
                        total_rows += len(rows)
                        print(f"Processed video: {file} ({len(pose_data)} frames)")
                    else:
                        print(f"No pose data: {file}")

                except Exception as e:
                    print(f"Failed video: {video_path} -> {e}")

        for d in dirs:
            folder_path = os.path.join(current_root, d)

            if _is_image_folder(folder_path):
                try:
                    pose_data = extract_pose_from_image_folder(folder_path, frame_skip)

                    if pose_data:
                        folder_name = os.path.basename(folder_path)
                        rows = []
                        for i, frame in enumerate(pose_data):
                            frame["video"] = folder_name
                            frame["dataset_name"] = dataset_name
                            frame["frame_idx"] = i * frame_skip
                            rows.append(frame)

                        write_header = _write_rows(output_csv, rows, write_header)
                        total_rows += len(rows)
                        print(f"Processed image folder: {folder_name} ({len(pose_data)} frames)")
                    else:
                        print(f"No pose data in folder: {folder_path}")

                except Exception as e:
                    print(f"Failed image folder: {folder_path} -> {e}")

    if total_rows == 0:
        print("No data extracted.")
        return

    print(f"Saved: {output_csv} ({total_rows} rows)")


# =========================
# DISPATCHER
# =========================
def process_dataset(root_dir: str, dataset_name: str, frame_skip: int = 3):
    if dataset_name == "le2i_imvia":
        process_le2i_dataset(root_dir, dataset_name, frame_skip)
    elif dataset_name == "multiple_cameras_fall":
        process_multiple_cameras_dataset(root_dir, dataset_name, frame_skip)
    else:
        process_generic_dataset(root_dir, dataset_name, frame_skip)


def merge_all_datasets(root_dir: str):
    base_dir = os.path.join(root_dir, "datasets", "processed", "pose")
    all_dfs = []

    if os.path.exists(base_dir):
        for dataset in os.listdir(base_dir):
            csv_path = os.path.join(base_dir, dataset, "hybrid_pose.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                all_dfs.append(df)

    synthetic_csv = os.path.join(root_dir, "datasets", "processed", "synthetic_pose.csv")
    if os.path.exists(synthetic_csv):
        syn_df = pd.read_csv(synthetic_csv)
        all_dfs.append(syn_df)
        print(f"Included synthetic data: {synthetic_csv} ({len(syn_df)} rows)")

    if not all_dfs:
        print("No CSVs found to merge.")
        return

    final_df = pd.concat(all_dfs, ignore_index=True)
    out_path = os.path.join(root_dir, "datasets", "processed", "all_poses.csv")
    final_df.to_csv(out_path, index=False)
    print(f"Merged dataset saved: {out_path} ({len(final_df)} rows)")


def run_extraction(root_dir: str, frame_skip: int = 3, yolo_weights: str = "yolov8n-pose.pt", only_dataset=None):
    raw_dir = os.path.join(root_dir, "datasets", "raw")

    if not os.path.exists(raw_dir):
        raise FileNotFoundError(f"Raw dataset directory not found: {raw_dir}")

    if only_dataset:
        process_dataset(root_dir, only_dataset, frame_skip=frame_skip)
    else:
        for dataset_name in os.listdir(raw_dir):
            dataset_path = os.path.join(raw_dir, dataset_name)
            if os.path.isdir(dataset_path):
                process_dataset(root_dir, dataset_name, frame_skip=frame_skip)

    merge_all_datasets(root_dir)

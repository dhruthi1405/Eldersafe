#!/usr/bin/env python3
"""
run.py  —  ElderCare AI  Master Pipeline
==========================================
Single entry point for every stage of the pipeline.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from configs.config import ROOT_DIR, EMAIL_CONFIG


def stage_init(root_dir: str) -> None:
    dirs = [
        os.path.join(root_dir, "datasets", "raw"),
        os.path.join(root_dir, "datasets", "processed"),
        os.path.join(root_dir, "datasets", "processed", "pose"),
        os.path.join(root_dir, "metadata"),
        os.path.join(root_dir, "models"),
        os.path.join(root_dir, "logs"),
        os.path.join(root_dir, "outputs"),
    ]

    for d in dirs:
        os.makedirs(d, exist_ok=True)

    print(f"✓ Project initialized at: {os.path.abspath(root_dir)}")


def stage_scan(root_dir: str) -> None:
    from pipeline.dataset_loader import build_manifest
    build_manifest(root_dir)


def stage_extract(
    root_dir: str,
    frame_skip: int,
    yolo_weights: str,
    dataset_name: str | None,
) -> None:
    from pipeline.extract_pipeline import run_extraction
    run_extraction(
        root_dir,
        frame_skip=frame_skip,
        yolo_weights=yolo_weights,
        only_dataset=dataset_name,
    )


def stage_convert_fall_csv(root_dir: str) -> None:
    from pipeline.fall_csv_converter import convert_fall_dataset_csvs
    convert_fall_dataset_csvs(root_dir)


def stage_synth(root_dir: str) -> None:
    from pipeline.synthetic_generator import generate_synthetic_pose_csv
    generate_synthetic_pose_csv(root_dir, sequences_per_class=200, seq_len=30)


def stage_train(
    root_dir: str,
    epochs: int,
    batch_size: int,
    lr: float,
    seq_len: int,
    seed: int,
) -> None:
    from models.train import train
    train(
        root_dir,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        seq_len=seq_len,
        seed=seed,
    )


def stage_train_fall_binary(
    root_dir: str,
    epochs: int,
    batch_size: int,
    lr: float,
    seq_len: int,
    seed: int,
) -> None:
    from models.binary_fall_train import train_binary_fall
    train_binary_fall(
        root_dir=root_dir,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        seq_len=seq_len,
        seed=seed,
    )


def stage_train_activity(
    root_dir: str,
    epochs: int,
    batch_size: int,
    lr: float,
    seq_len: int,
    seed: int,
) -> None:
    from models.activity_train import train_activity
    train_activity(
        root_dir=root_dir,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        seq_len=seq_len,
        seed=seed,
    )


def stage_explain(root_dir: str) -> None:
    from pipeline.explain import explain_model
    explain_model(root_dir)


def stage_infer(
    root_dir: str,
    source: str,
    out_video: str | None,
    out_csv: str | None,
    binary_model_path: str | None,
    activity_model_path: str | None,
    frame_skip: int,
    enable_alerts: bool,
    show_live: bool,
    fall_threshold: float,
) -> None:
    from pipeline.inference import InferenceEngine

    if out_video is None:
        base = (
            os.path.splitext(os.path.basename(source))[0]
            if isinstance(source, str)
            else "webcam"
        )
        out_video = os.path.join(root_dir, "outputs", f"{base}_skeleton.mp4")

    if out_csv is None:
        base = os.path.splitext(os.path.basename(out_video))[0]
        out_csv = os.path.join(root_dir, "outputs", f"{base}_predictions.csv")

    engine = InferenceEngine(
        root_dir=root_dir,
        binary_model_path=binary_model_path,
        activity_model_path=activity_model_path,
        enable_alerts=enable_alerts,
        show_live=show_live,
        fall_threshold=fall_threshold,
    )

    src = int(source) if str(source).isdigit() else source
    engine.run_video(
        src,
        out_video=out_video,
        out_csv=out_csv,
        frame_skip=frame_skip,
    )

    print(f"\n✓ Skeleton video: {out_video}")
    print(f"✓ Predictions CSV: {out_csv}")


def stage_dashboard(root_dir: str, port: int, debug: bool) -> None:
    from dashboard.dashboard import create_app
    app = create_app(root_dir)
    print(f"\n🚀 Dashboard → http://localhost:{port}\n")
    app.run(debug=debug, host="0.0.0.0", port=port)


def stage_test_email(root_dir: str) -> None:
    import time
    from alerts.sos_detector import AlertType, SOSEvent
    from alerts.email_alert import AlertSender

    event = SOSEvent(
        alert_type=AlertType.FALL,
        timestamp=time.time(),
        activity_label="fall",
        confidence=0.91,
        message="TEST ALERT — ElderCare AI is configured correctly.",
        video_timestamp_s=12.5,
    )

    sender = AlertSender()
    ok = sender.send(event)

    if ok:
        print(f"✓ Test email sent to: {EMAIL_CONFIG['recipient_emails']}")
    else:
        print("✗ Email failed. Check ALERT_EMAIL and ALERT_PASSWORD env vars.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ElderCare AI Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "init",
            "scan",
            "extract",
            "convert_fall_csv",
            "synth",
            "train",
            "train_fall_binary",
            "train_activity",
            "explain",
            "infer",
            "dashboard",
            "test_email",
            "all",
        ],
        help="Pipeline stage to run",
    )

    parser.add_argument("--root_dir", default=ROOT_DIR)

    parser.add_argument("--frame_skip", type=int, default=3)
    parser.add_argument("--yolo_weights", default="yolov8n-pose.pt")
    parser.add_argument("--dataset_name", default=None)

    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seq_len", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--source", default=None, help="Video path or webcam index")
    parser.add_argument("--out_video", default=None)
    parser.add_argument("--out_csv", default=None)
    parser.add_argument("--binary_model_path", default=None)
    parser.add_argument("--activity_model_path", default=None)
    parser.add_argument("--fall_threshold", type=float, default=0.50)
    parser.add_argument("--enable_alerts", action="store_true")
    parser.add_argument("--show_live", action="store_true")

    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    root = args.root_dir

    if args.stage == "all":
        stages = ["init", "scan", "extract", "train", "infer", "dashboard"]
    else:
        stages = [args.stage]

    for stage in stages:
        print(f"\n{'=' * 60}")
        print(f"  STAGE: {stage.upper()}")
        print(f"{'=' * 60}\n")

        if stage == "init":
            stage_init(root)

        elif stage == "scan":
            stage_scan(root)

        elif stage == "extract":
            stage_extract(root, args.frame_skip, args.yolo_weights, args.dataset_name)

        elif stage == "convert_fall_csv":
            stage_convert_fall_csv(root)

        elif stage == "synth":
            stage_synth(root)

        elif stage == "train":
            stage_train(root, args.epochs, args.batch_size, args.lr, args.seq_len, args.seed)

        elif stage == "train_fall_binary":
            stage_train_fall_binary(root, args.epochs, args.batch_size, args.lr, args.seq_len, args.seed)

        elif stage == "train_activity":
            stage_train_activity(root, args.epochs, args.batch_size, args.lr, args.seq_len, args.seed)

        elif stage == "explain":
            stage_explain(root)

        elif stage == "infer":
            if args.source is None:
                parser.error("--source is required for the infer stage")
            stage_infer(
                root,
                args.source,
                args.out_video,
                args.out_csv,
                args.binary_model_path,
                args.activity_model_path,
                args.frame_skip,
                args.enable_alerts,
                args.show_live,
                args.fall_threshold,
            )

        elif stage == "dashboard":
            stage_dashboard(root, args.port, args.debug)

        elif stage == "test_email":
            stage_test_email(root)

    print("\n✓ Done.")


if __name__ == "__main__":
    main()
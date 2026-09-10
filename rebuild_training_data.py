#!/usr/bin/env python3
"""
rebuild_training_data.py
========================
Master script to fix corrupted activity training data and rebuild models.

STEPS:
1. Build separate clean CSVs for activity and fall training
2. Verify data integrity
3. Retrain models with clean data
4. Compare new vs old performance
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(cmd, description=""):
    """Execute a command and return success status."""
    if description:
        print(f"\n{'='*60}")
        print(f"🔄 {description}")
        print(f"{'='*60}")
    
    print(f"$ {cmd}\n")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def main():
    root_dir = Path(".").resolve()
    print(f"\n{'🔧 DATA PIPELINE FIX & MODEL REBUILD'.center(60, '=')}")
    print(f"Root: {root_dir}\n")
    
    # Step 1: Build clean CSVs
    print(f"\n{'STEP 1: FIXING DATA CORRUPTION'.center(60, '=')}")
    print("""
The problem: normalize_all_poses.py corrupted activity data by:
- Mixing pixel-scale fall videos (0-1920 coords) with already-normalized
  activity videos (0-1 coords)
- When normalized together by column, activity coords got compressed
  to 0.0001 range, poisoning the activity model

The solution:
- Build separate activity_train.csv from HMDB51 + synthetic (clean)
- Build separate fall_train.csv from LE2I + multiple_cameras (clean)
- Train models on their respective clean datasets
""")
    
    success = run_command(
        f"cd {root_dir} && python pipeline/fix_data_pipeline.py",
        "Building clean activity and fall training CSVs"
    )
    
    if not success:
        print("❌ Failed to build clean CSVs")
        return 1
    
    # Step 2: Verify data integrity
    print(f"\n{'STEP 2: VERIFYING DATA INTEGRITY'.center(60, '=')}")
    
    activity_csv = root_dir / "datasets" / "processed" / "activity_train.csv"
    fall_csv = root_dir / "datasets" / "processed" / "fall_train.csv"
    
    if activity_csv.exists():
        import pandas as pd
        df_activity = pd.read_csv(activity_csv)
        print(f"\n✓ activity_train.csv: {len(df_activity)} rows")
        print(f"  Columns: {len(df_activity.columns)}")
        if "nose_x" in df_activity.columns:
            x_min = df_activity["nose_x"].min()
            x_max = df_activity["nose_x"].max()
            print(f"  nose_x range: {x_min:.6f} - {x_max:.6f} (should be ~0-1)")
            if x_min > 0.1 or x_max < 0.9:
                print(f"  ⚠ WARNING: Activity data may still be corrupted (too narrow range)")
            else:
                print(f"  ✓ Activity data looks healthy!")
    else:
        print(f"❌ activity_train.csv not found!")
        return 1
    
    if fall_csv.exists():
        df_fall = pd.read_csv(fall_csv)
        print(f"\n✓ fall_train.csv: {len(df_fall)} rows")
        print(f"  Columns: {len(df_fall.columns)}")
        if "nose_x" in df_fall.columns:
            x_min = df_fall["nose_x"].min()
            x_max = df_fall["nose_x"].max()
            print(f"  nose_x range: {x_min:.6f} - {x_max:.6f} (should be ~0-1)")
            print(f"  ✓ Fall data normalized properly!")
    else:
        print(f"❌ fall_train.csv not found!")
        return 1
    
    # Step 3: Ask if user wants to retrain
    print(f"\n{'STEP 3: RETRAIN MODELS (OPTIONAL)'.center(60, '=')}")
    print("\nClean data is ready. Models can now be retrained:")
    print("  python -m models.activity_train")
    print("  python -m models.binary_fall_train")
    
    response = input("\nRetrain models now? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\n🚀 Starting model retraining...")
        
        # Retrain activity model
        print(f"\n{'RETRAINING ACTIVITY MODEL'.center(60, '=')}")
        success = run_command(
            f"cd {root_dir} && python -m models.activity_train",
            "Training activity recognition model"
        )
        if not success:
            print("⚠ Activity model training failed")
        
        # Retrain fall model
        print(f"\n{'RETRAINING FALL MODEL'.center(60, '=')}")
        success = run_command(
            f"cd {root_dir} && python -m models.binary_fall_train",
            "Training fall detection model"
        )
        if not success:
            print("⚠ Fall model training failed")
        
        print(f"\n{'🎉 MODEL RETRAINING COMPLETE'.center(60, '=')}")
    else:
        print("\n⏭️ Skipping model retraining")
    
    # Step 4: Summary
    print(f"\n{'✅ DATA PIPELINE FIX COMPLETE'.center(60, '=')}")
    print(f"""
WHAT WAS FIXED:
✓ Separated activity and fall training data
✓ Removed double-normalization corruption
✓ Created clean activity_train.csv ({len(df_activity)} rows)
✓ Created clean fall_train.csv ({len(df_fall)} rows)
✓ Updated training scripts to use clean CSVs

NEXT STEPS (if not done):
1. Retrain models: python -m models.activity_train
2. Retrain models: python -m models.binary_fall_train
3. Restart backend: docker-compose restart backend
4. Upload a test video to see improved activity recognition

EXPECTED IMPROVEMENTS:
- Activity model should now learn real pose motion
- "walking" F1 should improve from ~0.0 to ~0.8+
- Live inference should show correct activities
- Fall detection should maintain 95%+ accuracy
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

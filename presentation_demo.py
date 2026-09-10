#!/usr/bin/env python3
"""
Presentation Demo Script - ElderCare AI
========================================
One-command setup to showcase the entire system.
"""

import subprocess
import sys
import time
import os
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def run_cmd(cmd, description):
    print(f"🚀 {description}")
    print(f"   Command: {' '.join(cmd)}\n")
    subprocess.run(cmd)


def main():
    os.chdir(ROOT_DIR)
    
    print_section("ELDERCARE AI - PRESENTATION DEMO")
    
    # Menu
    print("Choose a demo mode:\n")
    print("  1) Video Upload & Analysis (Dashboard only)")
    print("  2) Live Webcam Detection (Real-time)")
    print("  3) Full System (Dashboard + Backend)")
    print("  4) Process & View Results\n")
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        print_section("STARTING DASHBOARD - VIDEO UPLOAD MODE")
        print("📺 Dashboard will open at: http://localhost:8050")
        print("   1. Upload a video file")
        print("   2. Watch real-time analysis")
        print("   3. See fall detection + activity timeline\n")
        
        time.sleep(2)
        webbrowser.open("http://localhost:8050")
        
        cmd = [sys.executable, "run.py", "--stage", "dashboard", "--port", "8050", "--debug"]
        run_cmd(cmd, "Launching Dashboard...")
    
    elif choice == "2":
        print_section("STARTING LIVE WEBCAM DETECTION")
        print("📹 Webcam will start in a new window")
        print("   - Shows skeleton pose overlay")
        print("   - Real-time fall confidence")
        print("   - Activity classification\n")
        print("Press 'q' to stop.\n")
        
        time.sleep(2)
        
        cmd = [
            sys.executable, "run.py",
            "--stage", "infer",
            "--source", "0",
            "--show_live",
            "--enable_alerts"
        ]
        run_cmd(cmd, "Starting webcam inference...")
    
    elif choice == "3":
        print_section("STARTING FULL SYSTEM")
        print("System running in background...")
        print("📊 Dashboard: http://localhost:8050")
        print("🔌 Backend API: http://localhost:5000")
        print("📱 Flutter app can connect to backend\n")
        
        time.sleep(2)
        
        # Start dashboard in new window
        import platform
        if platform.system() == "Windows":
            subprocess.Popen([sys.executable, "run.py", "--stage", "dashboard", "--port", "8050"])
        else:
            subprocess.Popen([sys.executable, "run.py", "--stage", "dashboard", "--port", "8050"])
        
        time.sleep(3)
        webbrowser.open("http://localhost:8050")
        
        # Start Flask backend
        cmd = [sys.executable, "flask_server_v2_redesigned.py"]
        run_cmd(cmd, "Starting Flask backend...")
    
    elif choice == "4":
        print_section("PROCESSING & VIEWING RESULTS")
        
        video_file = input("Enter video path (or press Enter for default): ").strip()
        if not video_file:
            video_file = "test_video.mp4"  # Change to your default
        
        if not os.path.exists(video_file):
            print(f"❌ Video not found: {video_file}")
            return
        
        print_section("STEP 1: RUNNING INFERENCE")
        cmd = [
            sys.executable, "run.py",
            "--stage", "infer",
            "--source", video_file,
            "--enable_alerts"
        ]
        run_cmd(cmd, f"Processing {video_file}...")
        
        print_section("STEP 2: LAUNCHING DASHBOARD TO VIEW RESULTS")
        time.sleep(2)
        webbrowser.open("http://localhost:8050")
        
        cmd = [sys.executable, "run.py", "--stage", "dashboard", "--port", "8050"]
        run_cmd(cmd, "Displaying results in dashboard...")
    
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✓ Demo stopped.")

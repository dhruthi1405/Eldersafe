import os

root = "datasets/raw/multiple_cameras_fall"

for current_root, dirs, files in os.walk(root):
    for f in files:
        if f.lower().endswith((".avi", ".mp4", ".mov", ".mkv")):
            print(os.path.join(current_root, f))
            break
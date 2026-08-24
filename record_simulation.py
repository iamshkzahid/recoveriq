#!/usr/bin/env python3
"""
RecoverIQ — Simulation & Interactive Screen Recorder Wrapper
Alias for video_generation/record_clips.py
"""
import subprocess
import sys
from pathlib import Path

def main():
    script_path = Path(__file__).parent / "video_generation" / "record_clips.py"
    cmd = [sys.executable, str(script_path)]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()

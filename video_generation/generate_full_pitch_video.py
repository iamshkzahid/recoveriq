#!/usr/bin/env python3
"""
RecoverIQ — Complete End-to-End Automated Pitch Video Generator
Runs:
1. TTS Voiceover Generation (Edge-TTS)
2. Playwright Automated HD Screen Recording (5 Clips)
3. FFmpeg Master Video Stitching & Output (`recoveriq_pitch.mp4`)
"""

import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent

def run_step(step_name: str, script_name: str):
    print(f"\n=======================================================")
    print(f"🚀 EXECUTING: {step_name}")
    print(f"=======================================================\n")
    script_path = BASE_DIR / script_name
    t0 = time.time()
    res = subprocess.run([sys.executable, str(script_path)], check=True)
    dt = time.time() - t0
    print(f"\n✅ {step_name} completed in {dt:.2f}s")

def main():
    print("🎬 STARTING FULL AUTOMATED PITCH VIDEO GENERATION...")
    
    # Step 1: Generate TTS Audio
    run_step("Step 1: TTS Audio Voiceovers", "generate_audio.py")
    
    # Step 2: Record Screen Clips with Playwright
    run_step("Step 2: Automated Playwright Screen Capture", "record_clips.py")
    
    # Step 3: Stitch & Compile Final Video
    run_step("Step 3: Master Video Stitching & Rendering", "build_video.py")

    final_video = Path("/Users/zahidshaikh/Desktop/Project/recoveriq_pitch.mp4")
    if final_video.exists():
        print(f"\n🎉 SUCCESS! Video generated at: {final_video}")
    else:
        print("\n❌ Error: Output video not found.")

if __name__ == "__main__":
    main()

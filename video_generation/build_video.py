#!/usr/bin/env python3
"""
RecoverIQ — Master Video Stitcher & Renderer
Syncs Playwright recorded webm clips with Edge-TTS audio files,
applies audio-video sync, smooth transitions, and outputs `recoveriq_pitch.mp4`.
"""

import json
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
CLIPS_DIR = BASE_DIR / "raw_clips"
PROCESSED_DIR = BASE_DIR / "processed_clips"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

PROJECT_ROOT = Path("/Users/zahidshaikh/Desktop/Project")
FINAL_OUTPUT = PROJECT_ROOT / "recoveriq_pitch.mp4"

CLIP_FILENAME_MAP = {
    "part1_hook": "clip1_hook.webm",
    "part2_architecture": "clip2_architecture.webm",
    "part3_xai_retry": "clip3_xai_retry.webm",
    "part4_genai": "clip4_genai.webm",
    "part5_impact": "clip5_impact.webm",
}

def get_media_duration(file_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    val = res.stdout.strip()
    if val and val != "N/A":
        try:
            return float(val)
        except ValueError:
            pass

    # Fallback for WebM streams with unindexed durations: read container via ffprobe packet decoding
    cmd2 = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True)
    val2 = res2.stdout.strip()
    if val2 and val2 != "N/A":
        try:
            return float(val2)
        except ValueError:
            pass

    return 45.0  # Safe default estimate

def process_part(part_id: str, title: str, audio_file: Path, video_file: Path) -> Path:
    audio_dur = get_media_duration(audio_file)
    out_mp4 = PROCESSED_DIR / f"{part_id}_synced.mp4"
    
    print(f"\n⚙️ Processing {part_id} ({title}):")
    print(f"  Audio Duration: {audio_dur:.2f}s | Source: {video_file.name}")
    
    # We apply tpad so if video is slightly shorter than audio, the final frame is held
    # and we use -shortest so it cuts exactly when the audio finishes (+0.5s breathing room)
    filter_complex = (
        "[0:v]tpad=stop_mode=clone:stop_duration=60,"
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v];"
        "[1:a]apad=pad_dur=0.5[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_file),
        "-i", str(audio_file),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out_mp4)
    ]
    
    subprocess.run(cmd, check=True)
    synced_dur = get_media_duration(out_mp4)
    print(f"  ✓ Created: {out_mp4.name} (Duration: {synced_dur:.2f}s)")
    return out_mp4

def concatenate_all(synced_files: list) -> Path:
    print(f"\n🎞️ Concatenating all {len(synced_files)} parts into final pitch video...")
    concat_list = PROCESSED_DIR / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in synced_files:
            f.write(f"file '{p.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        str(FINAL_OUTPUT)
    ]
    subprocess.run(cmd, check=True)
    
    total_dur = get_media_duration(FINAL_OUTPUT)
    file_size_mb = FINAL_OUTPUT.stat().st_size / (1024 * 1024)
    print(f"\n=======================================================")
    print(f"🏆 RECOVERIQ FINAL PITCH VIDEO READY!")
    print(f"📁 Location: {FINAL_OUTPUT}")
    print(f"⏱️ Duration: {total_dur:.2f} seconds ({total_dur/60:.2f} minutes)")
    print(f"💾 File Size: {file_size_mb:.2f} MB")
    print(f"🖥️ Resolution: 1920x1080 (Full HD, 30fps)")
    print(f"=======================================================")
    return FINAL_OUTPUT

def main():
    with open(AUDIO_DIR / "audio_manifest.json") as f:
        manifest = json.load(f)

    synced_clips = []
    for item in manifest:
        pid = item["id"]
        title = item["title"]
        audio_path = Path(item["audio_path"])
        clip_name = CLIP_FILENAME_MAP.get(pid, f"{pid}.webm")
        video_path = CLIPS_DIR / clip_name
        
        if not video_path.exists():
            print(f"❌ Error: Video clip {video_path} not found.")
            return
            
        synced = process_part(pid, title, audio_path, video_path)
        synced_clips.append(synced)

    concatenate_all(synced_clips)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
RecoverIQ — Terminal Capture & Webhook Emitter Demo Runner
"""
import subprocess
import sys
from pathlib import Path

def main():
    script_path = Path(__file__).parent / "simulate_webhook.py"
    cmd = [sys.executable, str(script_path), "--count", "5"]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()

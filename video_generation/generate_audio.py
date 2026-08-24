#!/usr/bin/env python3
"""
RecoverIQ — TTS Voiceover Generator
Generates high-fidelity neural voiceovers for the 5-part Razorpay Hackathon pitch video.
Uses edge-tts with crisp, professional voice and precise timestamps.
"""

import asyncio
import os
import subprocess
import json
from pathlib import Path
import edge_tts

OUTPUT_DIR = Path(__file__).parent / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Voice: en-IN-PrabhatNeural or en-US-AndrewMultilingualNeural or en-US-ChristopherNeural
VOICE = "en-IN-PrabhatNeural"  # Professional Indian English Tech Voice
RATE = "+4%"
PITCH = "+0Hz"

SCRIPT_PARTS = [
    {
        "id": "part1_hook",
        "title": "Part 1: The Hook & Problem Statement",
        "text": (
            "Every year, billions in Gross Merchandise Value are lost to transient payment failures and abandoned checkout carts across the digital economy. "
            "In high-velocity commerce, a failed payment isn't just lost revenue—it is direct customer churn. "
            "RecoverIQ turns critical payment failure points into autonomously recovered revenue. "
            "By combining predictive machine learning, explainable risk scoring, and generative AI, "
            "RecoverIQ acts as an autonomous revenue guardian for Razorpay merchants, maximizing transaction success rates without adding operational friction."
        ),
    },
    {
        "id": "part2_architecture",
        "title": "Part 2: Architecture & Cryptographic Webhooks",
        "text": (
            "Let's look at the underlying architecture. Enterprise payment recovery demands zero-trust cryptographic security and sub-millisecond reliability. "
            "Notice our simulated webhook emitter running in the terminal. It does not rely on mock state—it generates authentic Razorpay payment dot failed payloads "
            "and cryptographically signs each request with HMAC SHA-256 over raw byte streams. "
            "On the backend, our high-performance FastAPI engine verifies the cryptographic signature, enforces an in-memory TTL idempotency ledger, "
            "and dispatches the recovery pipeline in under fifteen milliseconds, making it fully ready for massive enterprise volume."
        ),
    },
    {
        "id": "part3_xai_retry",
        "title": "Part 3: Explainable AI & Smart Retries",
        "text": (
            "Next, let's explore our Live Risk Predictor. Unlike black-box algorithms, RecoverIQ is built on the principle of Explainable AI. "
            "The model does not merely output a risk percentage—it provides merchants with an exact factor attribution breakdown using dynamic visual indicators. "
            "For instance, when evaluating Yes Bank Netbanking for a high-value transaction, the model attributes elevated risk to historical bank downtime spikes, "
            "multi-step authentication drop-offs, and high-value scrutiny. "
            "For soft infrastructure failures like bank timeouts, RecoverIQ autonomously schedules intelligent retries during peak uptime windows without bothering the customer."
        ),
    },
    {
        "id": "part4_genai",
        "title": "Part 4: GenAI Contextual Messaging & BNPL Recovery",
        "text": (
            "For hard customer declines—such as insufficient funds or credit limit caps—generic static emails simply do not convert. "
            "RecoverIQ leverages generative AI powered by Gemini to compose hyper-personalized, contextual recovery outreach. "
            "Watch as our agent analyzes the exact failure reason, the order value, and the preferred channel, dynamically drafting a tailored WhatsApp message "
            "that automatically recommends a flexible three-month No-Cost EMI payment link. "
            "By transforming an embarrassing failure into an attractive financing alternative, RecoverIQ dramatically boosts recovery conversion."
        ),
    },
    {
        "id": "part5_impact",
        "title": "Part 5: Observability, Audit Trail & Business Impact",
        "text": (
            "Finally, RecoverIQ provides merchants with a complete observability suite. "
            "From real-time failure heatmaps mapping bank latency by the hour, to channel conversion analytics and an immutable compliance audit trail, "
            "every recovery action is transparently logged. "
            "In our benchmark simulations, RecoverIQ achieved an eighty-one percent AUC-ROC and recovered over twenty-seven percent of lost GMV. "
            "At Razorpay's scale of 1.5 million daily failures, this architecture represents over eighteen hundred crore rupees in recovered merchant revenue annually. "
            "RecoverIQ: turning failed payments into recovered revenue."
        ),
    },
]

def get_audio_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except Exception:
        return 0.0

async def generate_audio_file(part_info: dict) -> dict:
    file_id = part_info["id"]
    text = part_info["text"]
    out_path = OUTPUT_DIR / f"{file_id}.mp3"
    print(f"Generating TTS for {file_id} ({part_info['title']})...")
    
    # Try edge-tts first
    success = False
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
            await communicate.save(str(out_path))
            success = True
            break
        except Exception as e:
            print(f"  [Attempt {attempt+1}] edge-tts error: {e}. Retrying...")
            await asyncio.sleep(1)
            
    if not success:
        print("  Falling back to gTTS...")
        from gtts import gTTS
        tts = gTTS(text=text, lang='en', tld='co.in', slow=False)
        tts.save(str(out_path))

    duration = get_audio_duration(out_path)
    print(f"  ✓ Saved: {out_path.name} | Duration: {duration:.2f}s")
    return {
        "id": file_id,
        "title": part_info["title"],
        "text": text,
        "audio_path": str(out_path),
        "duration": duration
    }

async def main():
    print(f"🎙️ Starting audio synthesis with Edge-TTS ({VOICE})...\n")
    results = []
    for part in SCRIPT_PARTS:
        res = await generate_audio_file(part)
        results.append(res)
    
    manifest_path = OUTPUT_DIR / "audio_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)

    total = sum(r["duration"] for r in results)
    print(f"\n✨ All voiceovers generated successfully!")
    print(f"📊 Total voiceover duration: {total:.2f} seconds ({total/60:.2f} minutes)")
    print(f"📄 Manifest saved to: {manifest_path}")

if __name__ == "__main__":
    asyncio.run(main())

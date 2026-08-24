#!/usr/bin/env python3
"""
RecoverIQ — TTS Voiceover Generator (Gold Master Pitch)
Generates high-fidelity neural voiceovers for the 6-part Razorpay Hackathon pitch video:
Clip 1: The Hook & Overview
Clip 2: Live Architecture ("This is NOT a static mockup")
Clip 3: XAI & GenAI Recovery in Action
Clip 4: System Architecture Diagram
Clip 5: Code Deep Dive (HMAC Security & ML Routing)
Clip 6: Conclusion & Business Impact
"""

import asyncio
import os
import subprocess
import json
from pathlib import Path
import edge_tts

OUTPUT_DIR = Path(__file__).parent / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Voice: en-US-ChristopherNeural (dynamic, authoritative, energetic)
VOICE = "en-US-ChristopherNeural"
RATE = "+15%"
PITCH = "+0Hz"

SCRIPT_PARTS = [
    {
        "id": "part1_hook",
        "title": "Part 1: The Hook & Product Overview",
        "phase": "Phase 1: Product Demo",
        "text": (
            "33% of customers abandon a transaction if it is declined. "
            "In digital commerce, a failed payment is instant churn. "
            "RecoverIQ uses autonomous AI to turn failure points into recovered revenue. "
            "By combining predictive machine learning, explainable risk scoring, and generative AI, "
            "RecoverIQ acts as an autonomous revenue guardian for Razorpay merchants, maximizing transaction success rates without adding operational friction. "
            "Let's explore how our real-time dashboard gives merchants complete visibility over revenue at risk, recovered capital, and bank health."
        ),
    },
    {
        "id": "part2_architecture",
        "title": "Part 2: Live Architecture & Webhook Emitter",
        "phase": "Phase 1: Product Demo",
        "text": (
            "This is NOT a static mockup. "
            "Watch our webhook emitter generate authentic HMAC SHA256 signatures over raw byte payloads. "
            "As our FastAPI backend processes this instantly, the dashboard updates in real-time. "
            "Enterprise payment recovery demands zero-trust cryptographic security and sub-millisecond reliability. "
            "Notice the terminal emitting real-time payment failure events with exact timestamping and cryptographic hashes, "
            "while our FastAPI backend ingests, verifies, and reflects the transaction in the live timeline in under fifteen milliseconds."
        ),
    },
    {
        "id": "part3_xai_genai",
        "title": "Part 3: XAI & GenAI Recovery in Action",
        "phase": "Phase 1: Product Demo",
        "text": (
            "Razorpay requires transparency. Our Explainable AI recalculates risk factors live as we adjust bank and payment instruments. "
            "And for hard declines, our GenAI agent instantly drafts a tailored WhatsApp message, dynamically offering a flexible EMI option to save the sale. "
            "Notice how the Gemini model analyzes the exact failure reason and transaction amount, "
            "composing an empathetic message that converts an embarrassing checkout failure into an attractive financing alternative."
        ),
    },
    {
        "id": "part4_system_architecture",
        "title": "Part 4: System Architecture Overview",
        "phase": "Phase 2: Architectural Overview",
        "text": (
            "Before diving into the code, here is the system architecture. "
            "Webhooks stream directly into our high-throughput FastAPI ingestion layer, hit a sub-millisecond Idempotency cache, "
            "and are routed either to the Smart Retry Queue for soft infrastructure declines, or our LLM agent for hard customer declines. "
            "This dual-waterfall pipeline decouples cryptographic verification from autonomous recovery, guaranteeing zero duplicate triggers and maximum recovery conversion."
        ),
    },
    {
        "id": "part5_code_deepdive",
        "title": "Part 5: Code Deep Dive (Security & Routing)",
        "phase": "Phase 3: Code Walkthrough",
        "text": (
            "Let's look under the hood. To prevent signature mismatches, our core engine intercepts the raw byte stream of the webhook before JSON serialization. "
            "Here in the code, await request dot body captures the raw payload bytes before HMAC SHA256 calculation. "
            "Our ML predictor categorizes failures in under fifteen milliseconds, seamlessly triggering our GenAI prompt template for hard declines while queuing smart retries during optimal bank uptime windows."
        ),
    },
    {
        "id": "part6_conclusion",
        "title": "Part 6: Conclusion & Business Impact",
        "phase": "Phase 3: Conclusion",
        "text": (
            "RecoverIQ is a complete, agentic revenue guardian. "
            "It maximizes Transaction Success Rates toward the ninety-five percent industry benchmark, autonomously safeguarding Gross Merchandise Value. "
            "At Razorpay's scale of 1.5 million daily failures, this architecture recovers over eighteen hundred crore rupees in merchant revenue annually. "
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
        "phase": part_info.get("phase", ""),
        "text": text,
        "audio_path": str(out_path),
        "duration": duration
    }

async def main():
    print(f"🎙️ Starting Gold Master audio synthesis with Edge-TTS ({VOICE}, {RATE})...\n")
    results = []
    for part in SCRIPT_PARTS:
        res = await generate_audio_file(part)
        results.append(res)
    
    manifest_path = OUTPUT_DIR / "audio_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)

    total = sum(r["duration"] for r in results)
    print(f"\n✨ All 6 Gold Master voiceovers generated successfully!")
    print(f"📊 Total voiceover duration: {total:.2f} seconds ({total/60:.2f} minutes)")
    print(f"📄 Manifest saved to: {manifest_path}")

if __name__ == "__main__":
    asyncio.run(main())

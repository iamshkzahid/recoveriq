#!/usr/bin/env python3
"""
RecoverIQ — Playwright Automated Screen Recorder
Automates 5 high-definition (1920x1080) screen recordings aligned with each pitch audio segment.
"""

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
CLIPS_DIR = BASE_DIR / "raw_clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

APP_URL = "http://localhost:3000"
SPLIT_URL = f"file://{BASE_DIR}/split_screen.html"

async def load_manifest():
    with open(AUDIO_DIR / "audio_manifest.json") as f:
        return json.load(f)

async def record_clip_1(browser, duration):
    """Clip 1: Dashboard Overview, KPI Cards, and Recovery Heatmap (~40s)"""
    dest = CLIPS_DIR / "clip1_hook.webm"
    if dest.exists():
        print(f"\n⚡ Clip 1 already exists ({dest.stat().st_size / (1024*1024):.2f}MB). Skipping...")
        return

    print(f"\n🎬 Recording Clip 1: Dashboard Overview (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c1"
    temp_dir.mkdir(exist_ok=True)
    
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(APP_URL, wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # 1. Hover on logo and header
    await page.hover(".logo-container")
    await page.wait_for_timeout(3000)

    # 2. Hover smoothly over the 4 KPI cards
    kpi_cards = await page.query_selector_all(".kpi-card")
    for card in kpi_cards:
        await card.hover()
        await page.wait_for_timeout(3500)

    # 3. Smooth scroll down to failure heatmap & channel performance
    await page.evaluate("window.scrollBy({ top: 350, behavior: 'smooth' })")
    await page.wait_for_timeout(5000)

    # Hover over heatmap cells
    cells = await page.query_selector_all(".heatmap-cell")
    for cell in cells[10:16]:
        await cell.hover()
        await page.wait_for_timeout(800)

    # 4. Scroll right to the live timeline
    await page.evaluate("window.scrollBy({ top: 200, behavior: 'smooth' })")
    await page.wait_for_timeout(6000)

    # 5. Scroll back to top
    await page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
    await page.wait_for_timeout(5000)

    await context.close()
    
    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 1: {dest.name}")

async def record_clip_2(browser, duration):
    """Clip 2: Webhook Emitter & Terminal Split-Screen (~47s)"""
    dest = CLIPS_DIR / "clip2_architecture.webm"
    if dest.exists():
        print(f"\n⚡ Clip 2 already exists ({dest.stat().st_size / (1024*1024):.2f}MB). Skipping...")
        return

    print(f"\n🎬 Recording Clip 2: Webhooks & Architecture (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c2"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(SPLIT_URL, wait_until="networkidle")
    
    # Let the animated terminal run and show multiple real-time webhook logs
    t_start = time.time()
    while time.time() - t_start < duration + 2:
        await page.wait_for_timeout(2000)

    await context.close()
    
    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 2: {dest.name}")

async def record_clip_3(browser, duration):
    """Clip 3: Explainable AI (XAI) & Live Risk Predictor (~48s)"""
    dest = CLIPS_DIR / "clip3_xai_retry.webm"
    print(f"\n🎬 Recording Clip 3: Explainable AI (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c3"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(APP_URL, wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # Scroll directly to Risk Predictor Panel
    await page.evaluate("""
        const el = document.querySelector('.risk-card');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    """)
    await page.wait_for_timeout(3000)

    # 1. Select Yes Bank (first select)
    selects = await page.query_selector_all(".risk-inputs select")
    if len(selects) >= 2:
        await selects[0].select_option("Yes Bank")
        await page.wait_for_timeout(2000)

        # 2. Select Netbanking (second select)
        await selects[1].select_option("netbanking")
        await page.wait_for_timeout(2000)

    # 3. Enter 75000 amount
    amt_input = await page.query_selector(".risk-inputs input[type='number']")
    if amt_input:
        await amt_input.fill("75000")
        await page.wait_for_timeout(2000)

    # 4. Click Predict
    predict_btn = await page.query_selector(".predict-btn")
    if predict_btn:
        await predict_btn.click()
        await page.wait_for_timeout(10000)  # Showcase red XAI factors and progress bars

    # Hover on XAI factor rows
    xai_rows = await page.query_selector_all(".xai-factor-row")
    for row in xai_rows:
        await row.hover()
        await page.wait_for_timeout(1500)

    # 5. Switch to Low Risk (HDFC + UPI + 500)
    if len(selects) >= 2:
        await selects[0].select_option("HDFC")
        await page.wait_for_timeout(1500)
        await selects[1].select_option("UPI")
        await page.wait_for_timeout(1500)
    
    if amt_input:
        await amt_input.fill("500")
        await page.wait_for_timeout(1500)
        
    if predict_btn:
        await predict_btn.click()
        await page.wait_for_timeout(8000)  # Showcase green safe bars

    await context.close()

    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 3: {dest.name}")

async def record_clip_4(browser, duration):
    """Clip 4: GenAI Contextual Messaging & Typewriter Effect (~43s)"""
    dest = CLIPS_DIR / "clip4_genai.webm"
    print(f"\n🎬 Recording Clip 4: GenAI Recovery (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c4"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(APP_URL, wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # Scroll to Timeline Card
    await page.evaluate("""
        const el = document.querySelector('.timeline-card');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    """)
    await page.wait_for_timeout(3000)

    # Find the GenAI button
    genai_btn = await page.query_selector(".genai-btn")
    if genai_btn:
        await genai_btn.hover()
        await page.wait_for_timeout(2000)
        await genai_btn.click()
        print("  Triggered ✨ Draft AI Message!")
        
        # Wait for skeleton loader -> typewriter streaming -> completed text
        await page.wait_for_timeout(18000)
        
        # Hover over generated box
        msg_box = await page.query_selector(".genai-message-box")
        if msg_box:
            await msg_box.hover()
            await page.wait_for_timeout(8000)

    # Scroll a bit inside timeline
    await page.evaluate("window.scrollBy({ top: 150, behavior: 'smooth' })")
    await page.wait_for_timeout(8000)

    await context.close()

    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 4: {dest.name}")

async def record_clip_5(browser, duration):
    """Clip 5: Observability, Heatmap, Metrics & Final Summary (~45s)"""
    dest = CLIPS_DIR / "clip5_impact.webm"
    print(f"\n🎬 Recording Clip 5: Observability & Impact (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c5"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(APP_URL, wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # 1. Focus on Failure Heatmap
    await page.evaluate("""
        const el = document.querySelector('.heatmap-card');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    """)
    await page.wait_for_timeout(6000)

    # 2. Focus on Channel Performance Chart
    await page.evaluate("""
        const el = document.querySelector('.channel-card');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    """)
    await page.wait_for_timeout(6000)

    # 3. Smooth scroll to top KPI Cards
    await page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
    await page.wait_for_timeout(4000)

    # Hover on Recovery Rate and Revenue Recovered
    kpi_cards = await page.query_selector_all(".kpi-card")
    if len(kpi_cards) >= 3:
        await kpi_cards[1].hover()  # Revenue Recovered
        await page.wait_for_timeout(4000)
        await kpi_cards[2].hover()  # Recovery Rate
        await page.wait_for_timeout(4000)

    # Click Run Simulation to show live activity
    sim_btn = await page.query_selector(".simulate-btn")
    if sim_btn:
        await sim_btn.click()
        await page.wait_for_timeout(8000)

    await context.close()

    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 5: {dest.name}")

async def main():
    manifest = await load_manifest()
    dur_map = {item["id"]: item["duration"] for item in manifest}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        await record_clip_1(browser, dur_map.get("part1_hook", 40.0))
        await record_clip_2(browser, dur_map.get("part2_architecture", 47.0))
        await record_clip_3(browser, dur_map.get("part3_xai_retry", 48.0))
        await record_clip_4(browser, dur_map.get("part4_genai", 43.0))
        await record_clip_5(browser, dur_map.get("part5_impact", 45.0))

        await browser.close()

    print("\n🎉 All 5 video clips captured successfully!")

if __name__ == "__main__":
    asyncio.run(main())

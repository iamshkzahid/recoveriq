#!/usr/bin/env python3
"""
RecoverIQ — Master Screen Recorder (Gold Master Pitch)
Automates 6 high-definition (1920x1080) screen recordings:
1. Product Overview (Dashboard with Glowing Yellow Cursor)
2. Live Architecture (Split-Screen Webhooks & HMAC Verification)
3. XAI & GenAI Recovery in Action (Live Yes Bank XAI + ₹25k WhatsApp EMI Typing)
4. System Architecture Diagram (Full High-Resolution Diagram Pan/Zoom)
5. Code Deep Dive (VSCode Large-Font View with HMAC & ML Highlights)
6. Conclusion & Business Impact (Live KPI Cards & Compliance Audit Log)
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
ARCH_URL = f"file://{BASE_DIR}/architecture_diagram.html"
CODE_URL = f"file://{BASE_DIR}/code_viewer.html"

CURSOR_JS = """
(function() {
  if (document.getElementById('playwright-custom-cursor')) return;
  const cursor = document.createElement('div');
  cursor.id = 'playwright-custom-cursor';
  cursor.innerHTML = `
    <div class="cursor-pointer-dot"></div>
    <div class="cursor-ripple"></div>
  `;
  const style = document.createElement('style');
  style.textContent = `
    #playwright-custom-cursor {
      position: fixed;
      top: 150px;
      left: 200px;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: rgba(255, 220, 0, 0.85);
      border: 2.5px solid #ffffff;
      box-shadow: 0 0 18px #ffd600, 0 0 36px rgba(255, 214, 0, 0.9);
      pointer-events: none;
      z-index: 9999999;
      transform: translate(-50%, -50%);
      transition: top 0.45s cubic-bezier(0.25, 1, 0.5, 1), 
                  left 0.45s cubic-bezier(0.25, 1, 0.5, 1), 
                  transform 0.15s ease, 
                  background 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .cursor-pointer-dot {
      width: 8px;
      height: 8px;
      background: #111111;
      border-radius: 50%;
    }
    #playwright-custom-cursor.clicking {
      transform: translate(-50%, -50%) scale(0.7);
      background: #ff5252;
      border-color: #ffffff;
      box-shadow: 0 0 25px #ff5252;
    }
    .cursor-ripple {
      position: absolute;
      width: 100%;
      height: 100%;
      border-radius: 50%;
      border: 3px solid #ffd600;
      opacity: 0;
      pointer-events: none;
    }
    #playwright-custom-cursor.clicking .cursor-ripple {
      animation: cursorRippleAnim 0.5s ease-out;
    }
    @keyframes cursorRippleAnim {
      0% { transform: scale(1); opacity: 1; border-color: #ffd600; }
      100% { transform: scale(3.2); opacity: 0; border-color: #ff5252; }
    }
  `;
  document.head.appendChild(style);
  document.body.appendChild(cursor);
  
  window.__moveCursor = function(x, y) {
    const c = document.getElementById('playwright-custom-cursor');
    if (c) {
      c.style.left = x + 'px';
      c.style.top = y + 'px';
    }
  };
  
  window.__clickCursor = function() {
    const c = document.getElementById('playwright-custom-cursor');
    if (c) {
      c.classList.add('clicking');
      setTimeout(() => c.classList.remove('clicking'), 320);
    }
  };
})();
"""

async def init_cursor(page):
    await page.evaluate(CURSOR_JS)
    await page.wait_for_timeout(300)

async def move_cursor_to_element(page, selector, offset_x=0, offset_y=0, wait_after=0.6):
    try:
        box = await page.evaluate(f"""
            (function() {{
                const el = document.querySelector('{selector}');
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {{ x: r.left + r.width / 2, y: r.top + r.height / 2 }};
            }})()
        """)
        if box:
            target_x = box["x"] + offset_x
            target_y = box["y"] + offset_y
            await page.evaluate(f"window.__moveCursor({target_x}, {target_y})")
            await page.wait_for_timeout(int(wait_after * 1000))
        else:
            await page.hover(selector)
    except Exception:
        pass

async def click_element_with_cursor(page, selector, offset_x=0, offset_y=0, wait_after=1.0):
    await move_cursor_to_element(page, selector, offset_x, offset_y, wait_after=0.4)
    await page.evaluate("window.__clickCursor()")
    await page.wait_for_timeout(180)
    try:
        await page.click(selector)
    except Exception:
        pass
    await page.wait_for_timeout(int(wait_after * 1000))

async def load_manifest():
    with open(AUDIO_DIR / "audio_manifest.json") as f:
        return json.load(f)

# ── Clip 1: Product Overview & Hook (~33s) ──
async def record_clip_1(browser, duration):
    dest = CLIPS_DIR / "clip1_hook.webm"
    print(f"\n🎬 Recording Clip 1: Product Overview & Hook (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c1"
    temp_dir.mkdir(exist_ok=True)
    
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(APP_URL, wait_until="networkidle")
    await init_cursor(page)
    await page.wait_for_timeout(1000)

    # Yellow cursor points to brand logo
    await move_cursor_to_element(page, ".logo-container", wait_after=2.0)

    # Hover across all 4 top KPI cards
    await move_cursor_to_element(page, ".kpi-grid .kpi-card:nth-child(1)", wait_after=2.5)
    await move_cursor_to_element(page, ".kpi-grid .kpi-card:nth-child(2)", wait_after=2.5)
    await move_cursor_to_element(page, ".kpi-grid .kpi-card:nth-child(3)", wait_after=2.5)
    await move_cursor_to_element(page, ".kpi-grid .kpi-card:nth-child(4)", wait_after=2.5)

    # Smooth scroll down to Heatmap and Channel performance
    await page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' })")
    await page.wait_for_timeout(2000)

    await move_cursor_to_element(page, ".heatmap-card", wait_after=2.0)
    await move_cursor_to_element(page, ".channel-card", wait_after=2.5)

    # Scroll back to top
    await page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
    await move_cursor_to_element(page, ".simulate-btn", wait_after=2.0)

    await page.wait_for_timeout(max(1000, int((duration - 20) * 1000)))
    await context.close()
    
    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        if dest.exists(): dest.unlink()
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 1: {dest.name}")

# ── Clip 2: Live Architecture & Webhook Emitter (~32s) ──
async def record_clip_2(browser, duration):
    dest = CLIPS_DIR / "clip2_architecture.webm"
    print(f"\n🎬 Recording Clip 2: Live Architecture & Webhook Emitter (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c2"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(SPLIT_URL, wait_until="networkidle")
    await init_cursor(page)
    await page.wait_for_timeout(1000)

    # Yellow cursor points to terminal titlebar and prompt
    await move_cursor_to_element(page, ".terminal-header", wait_after=2.5)
    await move_cursor_to_element(page, ".terminal-body", wait_after=3.5)

    # Yellow cursor moves to the live dashboard on the right pane
    await move_cursor_to_element(page, ".web-header", wait_after=3.0)

    t_start = time.time()
    while time.time() - t_start < duration + 1:
        await page.wait_for_timeout(2000)

    await context.close()
    
    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        if dest.exists(): dest.unlink()
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 2: {dest.name}")

# ── Clip 3: XAI & GenAI Recovery in Action (~27s) ──
async def record_clip_3(browser, duration):
    dest = CLIPS_DIR / "clip3_xai_genai.webm"
    print(f"\n🎬 Recording Clip 3: XAI & GenAI Recovery in Action (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c3"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(APP_URL, wait_until="networkidle")
    await init_cursor(page)
    await page.wait_for_timeout(1000)

    # 1. Quick demonstration of XAI Risk Predictor
    await page.evaluate("""
        const el = document.querySelector('.risk-card');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    """)
    await page.wait_for_timeout(1500)

    selects = await page.query_selector_all(".risk-inputs select")
    if len(selects) >= 2:
        await move_cursor_to_element(page, ".risk-inputs .input-group:nth-child(1) select", wait_after=0.6)
        await selects[0].select_option("Yes Bank")
        await page.wait_for_timeout(800)
        await click_element_with_cursor(page, ".predict-btn", wait_after=2.0)

    # 2. Scroll to Timeline Card for GenAI demonstration
    await page.evaluate("""
        const el = document.querySelector('.timeline-card');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    """)
    await page.wait_for_timeout(1500)

    # Injected glowing yellow cursor glides directly to the ₹25,000 transaction
    await move_cursor_to_element(page, ".timeline-item:nth-child(1)", wait_after=1.0)

    # Yellow cursor hovers and clicks ✨ Draft AI Message
    genai_btn = await page.query_selector(".timeline-item:nth-child(1) .genai-btn")
    if genai_btn:
        print("  ⚡ Yellow cursor clicking ✨ Draft AI Message on ₹25k transaction...")
        await click_element_with_cursor(page, ".timeline-item:nth-child(1) .genai-btn", wait_after=1.0)
    else:
        any_btn = await page.query_selector(".genai-btn")
        if any_btn:
            await click_element_with_cursor(page, ".genai-btn", wait_after=1.0)

    # Skeleton loader -> typewriter streaming -> completed green WhatsApp message
    await page.wait_for_timeout(12000)

    # Yellow cursor hovers over the rendered message box and Gemini badge to highlight them
    await move_cursor_to_element(page, ".genai-message-box", wait_after=2.0)
    await move_cursor_to_element(page, ".genai-model-badge", wait_after=2.0)

    await page.wait_for_timeout(max(1000, int((duration - 22) * 1000)))
    await context.close()

    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        if dest.exists(): dest.unlink()
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 3: {dest.name}")

# ── Clip 4: System Architecture Diagram Overview (~26s) ──
async def record_clip_4(browser, duration):
    dest = CLIPS_DIR / "clip4_system_architecture.webm"
    print(f"\n🎬 Recording Clip 4: System Architecture Diagram (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c4"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(ARCH_URL, wait_until="networkidle")
    await init_cursor(page)
    await page.wait_for_timeout(1000)

    # Yellow cursor traverses through the architectural blocks:
    # Webhooks -> FastAPI -> ML Router -> Dual Waterfall -> Dashboard
    nodes = await page.query_selector_all(".arch-node")
    if len(nodes) >= 5:
        await move_cursor_to_element(page, ".arch-node:nth-child(1)", wait_after=3.5) # Webhook
        await move_cursor_to_element(page, ".diagram-grid > .arch-node:nth-child(3)", wait_after=4.0) # FastAPI
        await move_cursor_to_element(page, ".diagram-grid > .arch-node:nth-child(5)", wait_after=4.5) # ML Router
        await move_cursor_to_element(page, ".dual-waterfall-col", wait_after=5.0) # Dual Waterfall
        await move_cursor_to_element(page, ".diagram-grid > .arch-node:nth-child(9)", wait_after=4.5) # Dashboard

    # Hover across footer metrics
    await move_cursor_to_element(page, ".arch-footer", wait_after=3.0)

    await page.wait_for_timeout(max(1000, int((duration - 24) * 1000)))
    await context.close()

    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        if dest.exists(): dest.unlink()
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 4: {dest.name}")

# ── Clip 5: Code Deep Dive (Security & Routing in VSCode View) (~26s) ──
async def record_clip_5(browser, duration):
    dest = CLIPS_DIR / "clip5_code_deepdive.webm"
    print(f"\n🎬 Recording Clip 5: Code Deep Dive (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c5"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(CODE_URL, wait_until="networkidle")
    await init_cursor(page)
    await page.wait_for_timeout(1000)

    # 1. Focus on Webhook HMAC SHA-256 and raw bytes: await request.body()
    await page.evaluate("window.__scrollToSection('security')")
    await page.wait_for_timeout(1000)

    await move_cursor_to_element(page, "#calloutBox", wait_after=2.5)
    await move_cursor_to_element(page, "#codeBlock", offset_x=-150, offset_y=-40, wait_after=3.5) # request.body()
    await move_cursor_to_element(page, "#codeBlock", offset_x=-120, offset_y=40, wait_after=3.5)  # hmac.new()
    await move_cursor_to_element(page, "#codeBlock", offset_x=-120, offset_y=110, wait_after=3.0) # idempotency_cache

    # 2. Focus on AI Routing Section
    await page.evaluate("window.__scrollToSection('routing')")
    await page.wait_for_timeout(1000)
    await move_cursor_to_element(page, "#calloutBox", wait_after=2.5)
    await move_cursor_to_element(page, "#codeBlock", offset_x=-120, offset_y=0, wait_after=3.0)

    await page.wait_for_timeout(max(1000, int((duration - 19) * 1000)))
    await context.close()

    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        if dest.exists(): dest.unlink()
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 5: {dest.name}")

# ── Clip 6: Conclusion & Business Impact (~24s) ──
async def record_clip_6(browser, duration):
    dest = CLIPS_DIR / "clip6_conclusion.webm"
    print(f"\n🎬 Recording Clip 6: Conclusion & Business Impact (Target: {duration:.2f}s)...")
    temp_dir = CLIPS_DIR / "temp_c6"
    temp_dir.mkdir(exist_ok=True)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(temp_dir),
        record_video_size={"width": 1920, "height": 1080}
    )
    page = await context.new_page()
    await page.goto(APP_URL, wait_until="networkidle")
    await init_cursor(page)
    await page.wait_for_timeout(1000)

    # 1. Hover on Revenue Recovered and Recovery Rate KPI Cards
    await move_cursor_to_element(page, ".kpi-grid .kpi-card:nth-child(2)", wait_after=2.0)
    await move_cursor_to_element(page, ".kpi-grid .kpi-card:nth-child(3)", wait_after=2.0)

    # 2. Trigger final simulation run
    sim_btn = await page.query_selector(".simulate-btn")
    if sim_btn:
        await click_element_with_cursor(page, ".simulate-btn", wait_after=2.0)

    # 3. Scroll down to show Audit Log Table
    await page.evaluate("""
        const el = document.querySelector('.audit-card');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    """)
    await page.wait_for_timeout(1500)
    await move_cursor_to_element(page, ".audit-card", wait_after=3.0)

    await page.wait_for_timeout(max(1000, int((duration - 15) * 1000)))
    await context.close()

    video_files = list(temp_dir.glob("*.webm"))
    if video_files:
        if dest.exists(): dest.unlink()
        shutil.move(str(video_files[0]), str(dest))
        shutil.rmtree(temp_dir)
        print(f"  ✓ Saved Clip 6: {dest.name}")

async def main():
    manifest = await load_manifest()
    dur_map = {item["id"]: item["duration"] for item in manifest}

    print("🚀 Launching Headless Chromium for Gold Master Recordings...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        await record_clip_1(browser, dur_map.get("part1_hook", 33.0))
        await record_clip_2(browser, dur_map.get("part2_architecture", 32.0))
        await record_clip_3(browser, dur_map.get("part3_xai_genai", 27.0))
        await record_clip_4(browser, dur_map.get("part4_system_architecture", 26.0))
        await record_clip_5(browser, dur_map.get("part5_code_deepdive", 26.0))
        await record_clip_6(browser, dur_map.get("part6_conclusion", 24.0))

        await browser.close()

    print("\n🎉 All 6 Gold Master video clips captured successfully!")

if __name__ == "__main__":
    asyncio.run(main())

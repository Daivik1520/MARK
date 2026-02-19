"""
MARK — Browser Copilot
Headful Playwright automation: natural language → browser actions.
User watches the browser click, type, and navigate in real-time.
"""

import os
import json
import asyncio
import requests
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODELS = [
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-4-maverick:free",
]

PLAN_SYSTEM_PROMPT = """You are a browser automation planner. Given a task description, output a JSON array of steps.
Each step is an object with:
- "action": one of "goto", "click", "type", "scroll", "wait", "screenshot", "extract"
- "selector": CSS selector (for click/type) — use simple, robust selectors
- "value": URL (for goto), text (for type), direction "up"/"down" (for scroll), or seconds (for wait)
- "description": brief human-readable description of what this step does

Rules:
- Output ONLY valid JSON. No markdown, no explanation.
- Use robust selectors: prefer [name=...], [placeholder=...], [aria-label=...], or text-based selectors.
- For search bars, prefer input[name="q"] or input[type="search"].
- For clicks, use text-based selectors like 'text=Submit' or 'button:has-text("Buy")' when possible.
- Include a wait step (1-2 seconds) after navigation and form submissions.
- Be practical — don't plan steps that require login unless mentioned.
- Maximum 12 steps.

Example output:
[
  {"action": "goto", "value": "https://www.google.com", "description": "Open Google"},
  {"action": "type", "selector": "input[name='q']", "value": "best restaurants NYC", "description": "Type search query"},
  {"action": "click", "selector": "input[name='btnK']", "description": "Click search button"},
  {"action": "wait", "value": "2", "description": "Wait for results"},
  {"action": "extract", "description": "Read the search results"}
]
"""


def _run_async(coro):
    """Run an async coroutine synchronously in a dedicated event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_action_plan(task_description):
    """Use AI to decompose a task into browser action steps."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: {task_description}"},
    ]

    for model in MODELS:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "max_tokens": 2048, "temperature": 0.2},
                timeout=25,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    # Strip markdown fences if present
                    if content.startswith("```"):
                        lines = content.split("\n")
                        if lines[-1].strip() == "```":
                            lines = lines[1:-1]
                        else:
                            lines = lines[1:]
                        content = "\n".join(lines)
                    return json.loads(content)
            elif resp.status_code in (402, 404):
                continue
            elif resp.status_code == 429:
                import time
                time.sleep(2)
                continue
        except json.JSONDecodeError:
            continue
        except Exception:
            continue

    return None


async def _execute_steps(steps, headless=False):
    """Execute a list of browser action steps using Playwright in headful mode."""
    results = []
    screenshot_path = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--start-maximized"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for i, step in enumerate(steps):
            action = step.get("action", "")
            selector = step.get("selector", "")
            value = step.get("value", "")
            desc = step.get("description", f"Step {i+1}")

            try:
                if action == "goto":
                    url = value if value.startswith("http") else f"https://{value}"
                    await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    results.append(f"✅ {desc}")

                elif action == "click":
                    if selector.startswith("text="):
                        await page.get_by_text(selector[5:]).first.click(timeout=8000)
                    else:
                        await page.click(selector, timeout=8000)
                    results.append(f"✅ {desc}")

                elif action == "type":
                    if selector:
                        await page.fill(selector, value, timeout=8000)
                    results.append(f"✅ {desc}")

                elif action == "scroll":
                    direction = -300 if value.lower() == "up" else 300
                    await page.evaluate(f"window.scrollBy(0, {direction})")
                    results.append(f"✅ {desc}")

                elif action == "wait":
                    wait_sec = float(value) if value else 2
                    wait_sec = min(wait_sec, 10)  # Safety cap
                    await asyncio.sleep(wait_sec)
                    results.append(f"✅ {desc}")

                elif action == "screenshot":
                    screenshot_path = os.path.expanduser("~/Desktop/browser_copilot_screenshot.png")
                    await page.screenshot(path=screenshot_path)
                    results.append(f"✅ {desc} → saved to Desktop")

                elif action == "extract":
                    text = await page.evaluate("() => document.body.innerText")
                    # Truncate for AI
                    snippet = text[:1500].strip()
                    results.append(f"✅ {desc}\n📄 Content: {snippet[:500]}...")

                elif action == "press":
                    await page.keyboard.press(value or "Enter")
                    results.append(f"✅ {desc}")

                else:
                    results.append(f"⚠️ Unknown action: {action}")

            except Exception as e:
                results.append(f"❌ {desc}: {str(e)[:100]}")

        # Always take a final screenshot
        if not screenshot_path:
            screenshot_path = os.path.expanduser("~/Desktop/browser_copilot_result.png")
            try:
                await page.screenshot(path=screenshot_path)
            except Exception:
                pass

        # Keep browser open for 5 seconds so user can see the result
        await asyncio.sleep(5)
        await browser.close()

    return results, screenshot_path


def browser_do(task):
    """
    Execute a browser task described in natural language.
    Launches a visible browser window and performs the steps automatically.
    
    Args:
        task: Plain English description of what to do in the browser
    
    Returns:
        Status summary + screenshot path
    """
    if not task:
        return "❌ Please describe what you want me to do in the browser."

    # Step 1: Get action plan from AI
    steps = _get_action_plan(task)
    if not steps or not isinstance(steps, list):
        return "❌ Could not generate a browser action plan. Please try rephrasing your request."

    # Step 2: Execute in headful mode
    try:
        results, screenshot = _run_async(_execute_steps(steps, headless=False))
    except Exception as e:
        return f"❌ Browser execution failed: {str(e)[:200]}"

    # Step 3: Build summary
    completed = sum(1 for r in results if r.startswith("✅"))
    total = len(results)

    summary = (
        f"🌐 **Browser Copilot Complete**\n\n"
        f"📋 Task: {task}\n"
        f"✅ Steps completed: {completed}/{total}\n\n"
    )
    summary += "\n".join(results)

    if screenshot:
        summary += f"\n\n📸 Screenshot saved: {screenshot}"

    return summary

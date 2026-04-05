"""
MARK — Browser Copilot
Headful Playwright automation: natural language → browser actions.
User watches the browser click, type, and navigate in real-time.
Powered by local Gemma 2 2B for action planning.
"""

import os
import json
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

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
    """Use local Gemma AI to decompose a task into browser action steps."""
    try:
        from core.local_llm import local_chat
        response = local_chat(
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {task_description}"},
            ],
            max_tokens=2048,
            temperature=0.2,
        )
        if not response:
            return None
        content = response.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            content = "\n".join(lines)
        return json.loads(content)
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"  ✗ Browser copilot AI error: {e}")
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
                    wait_sec = min(wait_sec, 10)
                    await asyncio.sleep(wait_sec)
                    results.append(f"✅ {desc}")

                elif action == "screenshot":
                    screenshot_path = os.path.expanduser("~/Desktop/browser_copilot_screenshot.png")
                    await page.screenshot(path=screenshot_path)
                    results.append(f"✅ {desc} → saved to Desktop")

                elif action == "extract":
                    text = await page.evaluate("() => document.body.innerText")
                    snippet = text[:1500].strip()
                    results.append(f"✅ {desc}\n📄 Content: {snippet[:500]}...")

                elif action == "press":
                    await page.keyboard.press(value or "Enter")
                    results.append(f"✅ {desc}")

                else:
                    results.append(f"⚠️ Unknown action: {action}")

            except Exception as e:
                results.append(f"❌ {desc}: {str(e)[:100]}")

        if not screenshot_path:
            screenshot_path = os.path.expanduser("~/Desktop/browser_copilot_result.png")
            try:
                await page.screenshot(path=screenshot_path)
            except Exception:
                pass

        await asyncio.sleep(5)
        await browser.close()

    return results, screenshot_path


def browser_do(task):
    """
    Execute a browser task described in natural language.
    Launches a visible browser window and performs the steps automatically.
    """
    if not task:
        return "❌ Please describe what you want me to do in the browser."

    steps = _get_action_plan(task)
    if not steps or not isinstance(steps, list):
        return "❌ Could not generate a browser action plan. Please try rephrasing your request."

    try:
        results, screenshot = _run_async(_execute_steps(steps, headless=False))
    except Exception as e:
        return f"❌ Browser execution failed: {str(e)[:200]}"

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

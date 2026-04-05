"""
MARK — Automated Data Extractor
Scrapes structured data from websites using Playwright + BeautifulSoup.
Outputs CSV or JSON to the Desktop.
Powered by Groq for fast AI planning.
"""

import os
import csv
import json
import asyncio
import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

_groq_client = None

def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client

SCRAPE_PLAN_PROMPT = """You are a web scraping planner. Given a task, output a JSON object with:
- "steps": array of Playwright steps (same format as browser copilot: goto, click, type, wait, scroll)
- "extract_selectors": object with CSS selectors to extract repeated items:
  - "container": CSS selector for the repeating item container (e.g. ".product-card", "tr", ".search-result")
  - "fields": object mapping field names to CSS selectors RELATIVE to the container
    e.g. {"title": "h2 a", "price": ".price", "link": "a@href", "image": "img@src"}
    Use @attr to extract an attribute instead of text.

Rules:
- Output ONLY valid JSON. No markdown.
- Use robust selectors.
- Maximum 8 navigation steps.
- The extract_selectors should target the MAIN repeated data on the page.

Example:
{
  "steps": [
    {"action": "goto", "value": "https://www.amazon.com", "description": "Open Amazon"},
    {"action": "type", "selector": "#twotabsearchtextbox", "value": "laptops", "description": "Search"},
    {"action": "click", "selector": "#nav-search-submit-button", "description": "Submit search"},
    {"action": "wait", "value": "3", "description": "Wait for results"}
  ],
  "extract_selectors": {
    "container": "[data-component-type='s-search-result']",
    "fields": {
      "title": "h2 a span",
      "price": ".a-price .a-offscreen",
      "link": "h2 a@href",
      "rating": ".a-icon-alt"
    }
  }
}
"""


def _run_async(coro):
    """Run async coroutine in a dedicated event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_scrape_plan(task):
    """Use Groq AI to generate a scraping plan."""
    try:
        client = _get_groq()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SCRAPE_PLAN_PROMPT},
                {"role": "user", "content": f"Task: {task}"},
            ],
            max_tokens=2048,
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
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
        print(f"  ✗ Scrape planner AI error: {e}")
        return None


async def _navigate_and_extract(steps, selectors, max_items=20):
    """Navigate using Playwright, then extract structured data with BeautifulSoup."""
    extracted = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Execute navigation steps
        for step in steps:
            action = step.get("action", "")
            selector = step.get("selector", "")
            value = step.get("value", "")

            try:
                if action == "goto":
                    url = value if value.startswith("http") else f"https://{value}"
                    await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                elif action == "click":
                    if selector.startswith("text="):
                        await page.get_by_text(selector[5:]).first.click(timeout=8000)
                    else:
                        await page.click(selector, timeout=8000)
                elif action == "type":
                    if selector:
                        await page.fill(selector, value, timeout=8000)
                elif action == "scroll":
                    direction = -500 if value.lower() == "up" else 500
                    await page.evaluate(f"window.scrollBy(0, {direction})")
                elif action == "wait":
                    await asyncio.sleep(min(float(value or 2), 10))
                elif action == "press":
                    await page.keyboard.press(value or "Enter")
            except Exception as e:
                print(f"  ⚠️ Scrape nav step failed: {e}")

        # Get page HTML
        html = await page.content()
        await browser.close()

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    container_sel = selectors.get("container", "")
    fields = selectors.get("fields", {})

    if not container_sel or not fields:
        # Fallback: try to find tables
        return _extract_tables(soup, max_items)

    containers = soup.select(container_sel)[:max_items]

    for container in containers:
        row = {}
        for field_name, field_selector in fields.items():
            try:
                # Handle @attr notation
                if "@" in field_selector:
                    sel_part, attr = field_selector.rsplit("@", 1)
                    el = container.select_one(sel_part.strip()) if sel_part.strip() else container
                    row[field_name] = el.get(attr, "") if el else ""
                else:
                    el = container.select_one(field_selector)
                    row[field_name] = el.get_text(strip=True) if el else ""
            except Exception:
                row[field_name] = ""

        # Skip empty rows
        if any(v for v in row.values()):
            extracted.append(row)

    return extracted


def _extract_tables(soup, max_items=20):
    """Fallback: extract data from HTML tables."""
    tables = soup.find_all("table")
    if not tables:
        return []

    results = []
    table = tables[0]  # Use first table
    headers = []

    # Get headers
    thead = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]

    # Get rows
    rows = table.find_all("tr")
    for row in rows[:max_items + 1]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        values = [c.get_text(strip=True) for c in cells]

        if not headers:
            headers = values
            continue

        if len(values) == len(headers):
            results.append(dict(zip(headers, values)))
        elif values:
            results.append({f"col_{i}": v for i, v in enumerate(values)})

    return results


def _save_results(data, task, output_format="csv"):
    """Save extracted data to Desktop as CSV or JSON."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Clean task name for filename
    clean_name = "".join(c if c.isalnum() or c == " " else "" for c in task[:40]).strip().replace(" ", "_")
    base = f"scraped_{clean_name}_{timestamp}"
    desktop = os.path.expanduser("~/Desktop")

    if output_format.lower() == "json":
        path = os.path.join(desktop, f"{base}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        path = os.path.join(desktop, f"{base}.csv")
        if data:
            keys = list(data[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)

    return path


def scrape_data(task, output_format="csv", max_items="20"):
    """
    Scrape structured data from a website based on a natural language task.

    Args:
        task: What to scrape (e.g. "Go to Amazon and search for laptops under $1000")
        output_format: "csv" or "json"
        max_items: Maximum number of items to extract (default 20)

    Returns:
        Summary with file path
    """
    if not task:
        return "❌ Please describe what data to extract."

    try:
        max_items = int(max_items)
    except (ValueError, TypeError):
        max_items = 20

    # Step 1: Get scraping plan from AI
    plan = _get_scrape_plan(task)
    if not plan:
        return "❌ Could not generate a scraping plan. Try rephrasing."

    steps = plan.get("steps", [])
    selectors = plan.get("extract_selectors", {})

    if not steps:
        return "❌ No navigation steps generated."

    # Step 2: Navigate and extract
    try:
        data = _run_async(_navigate_and_extract(steps, selectors, max_items))
    except Exception as e:
        return f"❌ Scraping failed: {str(e)[:200]}"

    if not data:
        return "⚠️ Navigation succeeded but no data could be extracted. The page structure may not match the expected selectors."

    # Step 3: Save results
    path = _save_results(data, task, output_format)

    return (
        f"📊 **Data Extraction Complete**\n\n"
        f"📋 Task: {task}\n"
        f"✅ Extracted: {len(data)} items\n"
        f"💾 Saved to: {path}\n\n"
        f"📝 Fields: {', '.join(data[0].keys()) if data else 'none'}"
    )
